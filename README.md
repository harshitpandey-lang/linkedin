# AI News Social Agent

A configuration-driven Python 3.12 pipeline that discovers recent AI news, verifies source evidence, generates structured Gemini content, creates a validated 1080x1080 branded PNG, stores it durably in Supabase, and optionally publishes independently to LinkedIn and Instagram.

## Architecture

`src/news` discovers, normalizes, filters, ranks, verifies, and detects duplicates. `src/ai` contains the provider contract, Gemini implementation, prompts, and Pydantic schemas. `src/image` creates and validates the Pillow fallback graphic. `src/database` owns Supabase records and storage. `src/social` owns independent platform publishers. `src/pipeline/orchestrator.py` coordinates the stages and approval/idempotency decisions.

## Setup

1. Create Python 3.12+ and install dependencies: `python -m pip install --upgrade pip`, then `python -m pip install -r requirements.txt`. The requirements pin Pydantic to the version range required by the Supabase 2.31 dependency graph.
2. Copy `.env.example` to `.env` and fill only credentials you own. Never commit `.env`.
3. Apply `supabase/migrations/001_initial.sql`, then `002_evidence_metadata.sql`, in the Supabase SQL editor. The `social-posts` bucket must be public for Instagram's URL ingestion.
4. Edit `config/settings.yaml`, `config/brand.yaml`, and `config/news_sources.yaml`.
5. Run `python -m pytest -q` and `python -m ruff check .`.
6. Run `python -m src.main` only after configuring Gemini and Supabase. With `AUTO_PUBLISH=false`, LinkedIn and Instagram credentials are not required and no social publisher is constructed.

The service-role key is server-side only. Never commit `.env` or print secrets.

## Environment variables

Supported environment variables are `GEMINI_API_KEY`, `GEMINI_MODEL`, `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `LINKEDIN_CLIENT_ID`, `LINKEDIN_CLIENT_SECRET`, `LINKEDIN_ACCESS_TOKEN`, `LINKEDIN_AUTHOR_TYPE`, `LINKEDIN_ORGANIZATION_ID`, `LINKEDIN_AUTHOR_URN`, `LINKEDIN_API_VERSION`, `META_APP_ID`, `META_APP_SECRET`, `INSTAGRAM_ACCESS_TOKEN`, `INSTAGRAM_ACCOUNT_ID`, `AUTO_PUBLISH`, and `LOG_LEVEL`.

The default Gemini model is the stable `gemini-2.5-flash`, which supports `generateContent`. Set `GEMINI_MODEL` to another model returned by the Gemini Developer API `models.list` endpoint with `generateContent` in `supportedGenerationMethods`; both `gemini-...` and `models/gemini-...` forms are accepted. A model 404 discovers compatible resources, excludes TTS/image/embedding/live variants, and retries with the best stable text model before reporting both the configured and attempted resources.

`SUPABASE_SERVICE_ROLE_KEY` keeps its existing name for workflow compatibility but contains the server-only modern `sb_secret_...` key. `AUTO_PUBLISH` defaults to false, including when the environment value is empty. Optional values treat empty strings as unset.

Every generated image is uploaded to the configured Supabase Storage bucket before the post row is created. Both its `image_storage_path` and `image_public_url` are stored; Instagram receives that row-specific URL, while LinkedIn uploads the Storage-downloaded PNG through LinkedIn's image API. The bucket must be public for Instagram and the account must be Professional with publishing permissions.

## Publishing modes

`AUTO_PUBLISH=false` is the repository default and stores a `PENDING_APPROVAL` post without calling social APIs. Approve it in Supabase, then run `python scripts/publish_approved.py`; that script downloads the generated image from Storage and does not depend on the original runner's local artifact. With `AUTO_PUBLISH=true`, configured publishers are called and each platform status is recorded independently. A failed platform produces `PARTIALLY_PUBLISHED`; already successful platforms are not reposted on retries.

## GitHub Actions

`.github/workflows/daily_ai_news.yml` installs the pinned dependencies, runs pytest, runs Ruff, and then runs the pipeline daily at 09:00 UTC or through `workflow_dispatch`. Add GitHub Secrets `GEMINI_API_KEY`, `SUPABASE_URL`, and `SUPABASE_SERVICE_ROLE_KEY`. Add repository variables `AUTO_PUBLISH` and `LINKEDIN_AUTHOR_TYPE` only when needed; an unset `AUTO_PUBLISH` resolves to false. The workflow never echoes secret values.

## Approval workflow

The current mode is `AUTO_PUBLISH=false`. The pipeline discovers, verifies, generates, validates, uploads, and stores a post as `PENDING_APPROVAL`, then stops. After approval in Supabase, run `python scripts/publish_approved.py` from an environment with the required platform credentials. The script downloads the image from Storage, skips platforms already marked `PUBLISHED`, records each platform independently, and supports retries.

## Platform setup

LinkedIn later requires `LINKEDIN_ACCESS_TOKEN`, `LINKEDIN_AUTHOR_TYPE`, and either `LINKEDIN_ORGANIZATION_ID`/a matching organization URN for organization/page mode or a token accepted by `/v2/userinfo` for person mode. Instagram later requires `INSTAGRAM_ACCESS_TOKEN`, `INSTAGRAM_ACCOUNT_ID`, a Professional account, and publishing permissions. These integrations are mock-tested only; no live platform publish is claimed.

## Extending the project

Add RSS sources in `config/news_sources.yaml`. Improve prompts in `src/ai/prompts.py`. Add an AI provider implementing `evaluate` and `generate_content`. Add another social publisher implementing `PublishResult`. The programmatic image fallback works without an image-generation API.

## Troubleshooting

- `No verified, non-duplicate story available`: inspect source enablement, article age, reliability, and recent Supabase records.
- Gemini JSON errors: inspect the configured model and provider response; the Pydantic schemas intentionally reject malformed content.
- Supabase errors: verify the URL, modern server-only secret key, applied migrations, Data API access, and public `social-posts` bucket policy.
- Instagram image errors: verify the stored public URL is reachable and the account is Professional with publishing permissions.
- LinkedIn errors: verify the token scopes, author type, organization ID, and configurable API version.

See [CHATGPT.md](CHATGPT.md) for the current handoff state and known limitations.
