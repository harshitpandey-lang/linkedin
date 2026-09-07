# Project handoff

## Overview and status

This is a Python 3.12 AI-news social-post pipeline. It discovers RSS stories, obtains source-page evidence, asks Gemini to score and verify a candidate, creates a branded PNG, uploads it to Supabase Storage, stores the post record, and can publish it to LinkedIn and Instagram. The implementation and mock-based tests pass locally; no real provider credentials are configured or exercised in this repository.

## Architecture and file structure

```text
src/
  ai/            provider protocol, Gemini integration, centralized prompts
  config/        YAML and environment loading
  database/      Supabase post repository, modern-key client, and ImageStorage
  image/         programmatic image generation and validation
  news/          RSS discovery, normalization, filtering, ranking, verification, duplicate checks
  pipeline/      orchestrator
  social/        LinkedIn and Instagram publishers
scripts/publish_approved.py
config/          application, brand, and RSS-source configuration
  supabase/migrations/001_initial.sql
  supabase/migrations/002_evidence_metadata.sql
.github/workflows/daily_ai_news.yml
tests/
```

## Implemented features

- RSS discovery, freshness filtering, URL/title duplicate checks, and a database duplicate window.
- Evidence fetching from a source page; stories without source evidence are rejected.
- Gemini evidence verification before selection and again against generated social copy.
- Local PNG generation and validation, then deterministic Supabase Storage upload at `YYYY/MM/DD/{run_id}.png`.
- Persisted `image_storage_path` and `image_public_url`; local artifact paths are never persisted as permanent media references.
- Persisted `evidence_verified` and `evidence_reason`; apply migration `002_evidence_metadata.sql` to existing projects.
- Approval-mode publishing retrieves the image from Storage. Already successful platforms are skipped on retries.
- Instagram publishes the stored post-specific public URL.
- LinkedIn resolves a configured person from `/v2/userinfo`, or an organization/page from an organization ID or matching author URN; it initializes an image upload, uploads the PNG, then creates a REST Posts API image post.

## API integrations and variables

Gemini uses the Google Generative Language API. Supabase uses the Python client for `posts` and public Storage bucket `social-posts`. Instagram uses the Meta Graph API media-container flow. LinkedIn uses `/rest/images?action=initializeUpload` and `/rest/posts` with a configurable `Linkedin-Version` header.

Required configuration names: `GEMINI_API_KEY`, `GEMINI_MODEL`, `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `LINKEDIN_ACCESS_TOKEN`, `LINKEDIN_AUTHOR_TYPE`, `LINKEDIN_ORGANIZATION_ID`, `LINKEDIN_AUTHOR_URN`, `LINKEDIN_API_VERSION`, `INSTAGRAM_ACCESS_TOKEN`, `INSTAGRAM_ACCOUNT_ID`, `AUTO_PUBLISH`, and `LOG_LEVEL`. `LINKEDIN_CLIENT_ID`, `LINKEDIN_CLIENT_SECRET`, `META_APP_ID`, and `META_APP_SECRET` are needed to obtain/refresh OAuth tokens but are not read during publishing.

## Supabase schema and Storage workflow

`posts` includes source metadata, generated text, image paths/URLs, lifecycle/approval states, per-platform status, post IDs, errors, timestamps, and a unique `run_id`; it also has a unique `news_url`. The migration creates the public `social-posts` bucket. The server-only service-role key uploads PNGs and returns their public URLs. Approval publishing downloads the object using its stored key, so GitHub runners do not depend on a prior runner's filesystem.

## GitHub Actions

The daily workflow installs the pinned dependency set, runs pytest, runs Ruff, then runs `python -m src.main` daily at 09:00 UTC or on manual dispatch. Configure the Gemini and Supabase secrets before running the application. With `AUTO_PUBLISH=false`, the application does not construct social publishers. The workflow does not prove live platform APIs are functional.

## Known limitations and issues

- Repository-level tests use synthetic credentials and mocked platform calls. No live Gemini, Supabase, LinkedIn, or Meta calls have been verified in this environment.
- A live, no-network Supabase construction smoke test passed using the configured URL and secret key; it verified the database builder and Storage client headers. No database query or Storage upload was attempted.
- The safe application run was not completed because `GEMINI_API_KEY` is not present in the execution environment; startup now reports that requirement clearly before making external calls.
- The safe live path should be run with `AUTO_PUBLISH=false` only after the configured Gemini and Supabase secrets are available; it creates a pending record and does not call social APIs.
- HTML evidence extraction is deliberately lightweight and may include navigation text or fail on paywalls/JavaScript-rendered pages.
- The public Storage bucket is necessary for Instagram's URL ingestion; use a carefully scoped bucket policy.
- LinkedIn API versions and app-product access change; keep `LINKEDIN_API_VERSION` current. Person mode requires a token accepted by `/v2/userinfo` and a `urn:li:person:*` author URN if configured; organization/page mode requires `LINKEDIN_ORGANIZATION_ID` or a `urn:li:organization:*` author URN.
- LinkedIn post IDs are read case-insensitively from the REST response header, with the response body ID as a fallback for compatible clients and test doubles. An empty `AUTO_PUBLISH` workflow variable resolves to `false`; automatic publishing remains disabled by default.
- When `AUTO_PUBLISH=false`, `src.main` does not construct LinkedIn or Instagram publishers, so those platform credentials are not required for approval-mode pipeline runs.
- GitHub Actions can expose unset optional variables as empty strings. LinkedIn now treats empty `LINKEDIN_AUTHOR_TYPE` and `LINKEDIN_API_VERSION` as unset defaults, and the application applies the same empty-safe fallback to `LOG_LEVEL` and `GEMINI_MODEL`.
- The LinkedIn integration fixture now returns upload metadata only from `initializeUpload` and returns `x-restli-id: urn:li:share:1` only from `/rest/posts`. This prevents a successful mock response from losing its post ID while preserving the complete image-publishing flow.
- `SUPABASE_SERVICE_ROLE_KEY` is a server-only modern Supabase Secret Key in `sb_secret_...` format. PyPI `supabase==2.31.0` still has a legacy JWT-only local key check, while the official upstream source has removed that obsolete validation. The dependency is pinned to the official `supabase-py` `src/supabase` package at commit `bb7ecc5`; `get_client()` now uses the public `create_client(url, key)` API directly, and database plus Storage clients inherit the real key without internal mutation or a fake bootstrap key.
- The dependency graph pins `pydantic==2.13.5`, which satisfies `realtime==2.31.0` and `storage3==2.31.0` requirements of `pydantic>=2.11.7,<3.0.0`. The prior `pydantic==2.9.2` pin was incompatible with the Supabase stack.
- Gemini uses the REST `v1beta/models/{model}:generateContent` endpoint with the documented `x-goog-api-key` header. The default is stable `gemini-2.5-flash`; the retired Gemini 2.0 Flash identifier was removed from config and examples. On HTTP 404, the provider queries `v1beta/models`, filters for `generateContent`, and reports compatible models without exposing the API key.
- Database schema migrations must be applied manually. Migration `002_evidence_metadata.sql` is required for the current record payload.

## Next steps

1. Run the safe `AUTO_PUBLISH=false` workflow with the configured Gemini and Supabase secrets and inspect the pending database record.
2. Apply migration `002_evidence_metadata.sql` if the existing project has only migration `001`.
3. Add LinkedIn credentials/scopes and Meta credentials/permissions only when publication is intentionally enabled.
4. Consider a stronger article-text extractor and a durable per-platform publishing lock for high-concurrency triggering.

## Changelog

- 2026-09-06: wired ImageStorage into orchestration; removed static Instagram image configuration; implemented LinkedIn image upload + REST post creation; made approval publishing storage-backed; added evidence-based verification; applied duplicate-window query filtering; added mocked integration coverage and updated documentation.
- 2026-09-07: retained selected-story evidence through content validation, validated person versus organization/page author URNs, and added retry/idempotency coverage.
- 2026-09-07: hardened per-source discovery and approval publishing failures, persisted evidence metadata, added Gemini transient retries, added the Ruff workflow step, and expanded safe approval-mode coverage.
