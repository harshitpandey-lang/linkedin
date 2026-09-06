# Project handoff

## Overview and status

This is a Python 3.12 AI-news social-post pipeline. It discovers RSS stories, obtains source-page evidence, asks Gemini to score and verify a candidate, creates a branded PNG, uploads it to Supabase Storage, stores the post record, and can publish it to LinkedIn and Instagram. The implementation and mock-based tests pass locally; no real provider credentials are configured or exercised in this repository.

## Architecture and file structure

```text
src/
  ai/            provider protocol, Gemini integration, centralized prompts
  config/        YAML and environment loading
  database/      Supabase post repository and ImageStorage
  image/         programmatic image generation and validation
  news/          RSS discovery, normalization, filtering, ranking, verification, duplicate checks
  pipeline/      orchestrator
  social/        LinkedIn and Instagram publishers
scripts/publish_approved.py
config/          application, brand, and RSS-source configuration
supabase/migrations/001_initial.sql
.github/workflows/daily_ai_news.yml
tests/
```

## Implemented features

- RSS discovery, freshness filtering, URL/title duplicate checks, and a database duplicate window.
- Evidence fetching from a source page; stories without source evidence are rejected.
- Gemini evidence verification before selection and again against generated social copy.
- Local PNG generation and validation, then deterministic Supabase Storage upload at `YYYY/MM/DD/{run_id}.png`.
- Persisted `image_storage_path` and `image_public_url`; local artifact paths are never persisted as permanent media references.
- Approval-mode publishing retrieves the image from Storage. Already successful platforms are skipped on retries.
- Instagram publishes the stored post-specific public URL.
- LinkedIn resolves a configured person from `/v2/userinfo`, or an organization/page from an organization ID or matching author URN; it initializes an image upload, uploads the PNG, then creates a REST Posts API image post.

## API integrations and variables

Gemini uses the Google Generative Language API. Supabase uses the Python client for `posts` and public Storage bucket `social-posts`. Instagram uses the Meta Graph API media-container flow. LinkedIn uses `/rest/images?action=initializeUpload` and `/rest/posts` with a configurable `Linkedin-Version` header.

Required configuration names: `GEMINI_API_KEY`, `GEMINI_MODEL`, `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `LINKEDIN_ACCESS_TOKEN`, `LINKEDIN_AUTHOR_TYPE`, `LINKEDIN_ORGANIZATION_ID`, `LINKEDIN_AUTHOR_URN`, `LINKEDIN_API_VERSION`, `INSTAGRAM_ACCESS_TOKEN`, `INSTAGRAM_ACCOUNT_ID`, `AUTO_PUBLISH`, and `LOG_LEVEL`. `LINKEDIN_CLIENT_ID`, `LINKEDIN_CLIENT_SECRET`, `META_APP_ID`, and `META_APP_SECRET` are needed to obtain/refresh OAuth tokens but are not read during publishing.

## Supabase schema and Storage workflow

`posts` includes source metadata, generated text, image paths/URLs, lifecycle/approval states, per-platform status, post IDs, errors, timestamps, and a unique `run_id`; it also has a unique `news_url`. The migration creates the public `social-posts` bucket. The server-only service-role key uploads PNGs and returns their public URLs. Approval publishing downloads the object using its stored key, so GitHub runners do not depend on a prior runner's filesystem.

## GitHub Actions

The daily workflow installs dependencies, runs pytest, then runs `python -m src.main` daily at 09:00 UTC or on manual dispatch. Configure secrets before enabling actual publication. It does not prove live APIs are functional.

## Known limitations and issues

- Live Gemini, Supabase, LinkedIn, and Meta calls cannot be tested without credentials and account approval/scopes.
- HTML evidence extraction is deliberately lightweight and may include navigation text or fail on paywalls/JavaScript-rendered pages.
- The public Storage bucket is necessary for Instagram's URL ingestion; use a carefully scoped bucket policy.
- LinkedIn API versions and app-product access change; keep `LINKEDIN_API_VERSION` current. Person mode requires a token accepted by `/v2/userinfo` and a `urn:li:person:*` author URN if configured; organization/page mode requires `LINKEDIN_ORGANIZATION_ID` or a `urn:li:organization:*` author URN.
- Database schema migration must be applied manually. No live Supabase project was available for a query test.

## Next steps

1. Apply the migration and configure the bucket policy for the server-side service-role workflow.
2. Add GitHub secrets and obtain LinkedIn `w_member_social` or `w_organization_social`, plus appropriate Meta permissions.
3. Test publishing in a non-production account; validate personal and organization LinkedIn author modes.
4. Consider a stronger article-text extractor and a durable per-platform publishing lock for high-concurrency triggering.

## Changelog

- 2026-09-06: wired ImageStorage into orchestration; removed static Instagram image configuration; implemented LinkedIn image upload + REST post creation; made approval publishing storage-backed; added evidence-based verification; applied duplicate-window query filtering; added mocked integration coverage and updated documentation.
- 2026-09-07: retained selected-story evidence through content validation, validated person versus organization/page author URNs, and added retry/idempotency coverage.
