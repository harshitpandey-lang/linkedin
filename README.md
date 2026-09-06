# AI News Social Agent

A configuration-driven Python 3.12 pipeline that discovers AI news, ranks and verifies one story, generates structured social content with Gemini, creates a 1080x1080 branded graphic, stores the record in Supabase, and optionally publishes to LinkedIn and Instagram.

## Architecture

`src/news` discovers, normalizes, filters, ranks, verifies, and detects duplicates. `src/ai` contains the provider contract, Gemini implementation, prompts, and Pydantic schemas. `src/image` creates and validates the Pillow fallback graphic. `src/database` owns Supabase records and storage. `src/social` owns independent platform publishers. `src/pipeline/orchestrator.py` coordinates the stages and approval/idempotency decisions.

## Setup

1. Create Python 3.12+ and install dependencies: `python -m pip install -r requirements.txt`.
2. Copy `.env.example` to `.env` and fill only credentials you own.
3. Apply `supabase/migrations/001_initial.sql` in the Supabase SQL editor.
4. Edit `config/settings.yaml`, `config/brand.yaml`, and `config/news_sources.yaml`.
5. Run credential-free tests: `python -m pytest -q`.
6. Run the pipeline locally with `python -m src.main` after configuring Gemini and Supabase.

The service-role key is server-side only. Never commit `.env` or print secrets.

## Environment variables

`GEMINI_API_KEY`, `GEMINI_MODEL`, `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `LINKEDIN_CLIENT_ID`, `LINKEDIN_CLIENT_SECRET`, `LINKEDIN_ACCESS_TOKEN`, `LINKEDIN_AUTHOR_TYPE`, `LINKEDIN_ORGANIZATION_ID`, `LINKEDIN_API_VERSION`, `META_APP_ID`, `META_APP_SECRET`, `INSTAGRAM_ACCESS_TOKEN`, `INSTAGRAM_ACCOUNT_ID`, `IMAGE_PUBLIC_URL`, `AUTO_PUBLISH`, and `LOG_LEVEL` are supported. LinkedIn and Meta OAuth setup remains user configuration; no credentials are included here.

Instagram requires the uploaded image to be publicly reachable. Set `IMAGE_PUBLIC_URL` to the URL for the stored image, or extend `ImageStorage` to publish the returned Supabase public URL before calling the Instagram publisher.

## Publishing modes

With `AUTO_PUBLISH=false`, the pipeline stores a `PENDING_APPROVAL` post and does not call social APIs. Approve it in Supabase, then run `python scripts/publish_approved.py`. With `AUTO_PUBLISH=true`, configured publishers are called and each platform status is recorded independently. A failed platform produces `PARTIALLY_PUBLISHED`; already successful platforms are not reposted by the approval script.

## GitHub Actions

`.github/workflows/daily_ai_news.yml` runs tests and then the pipeline daily at 09:00 UTC, and supports `workflow_dispatch`. Add secrets for credentials and repository variables for non-secret settings such as `AUTO_PUBLISH` and `LINKEDIN_AUTHOR_TYPE`. The workflow never echoes secret values.

## Extending the project

Add RSS sources in `config/news_sources.yaml`. Improve prompts in `src/ai/prompts.py`. Add an AI provider implementing `evaluate` and `generate_content`. Add another social publisher implementing `PublishResult`. The programmatic image fallback works without an image-generation API.

## Troubleshooting

- `No verified, non-duplicate story available`: inspect source enablement, article age, reliability, and recent Supabase records.
- Gemini JSON errors: inspect the configured model and provider response; the Pydantic schemas intentionally reject malformed content.
- Instagram image errors: verify the media URL is public and the account is Professional with publishing permissions.
- LinkedIn errors: verify the token scopes, author type, organization ID, and configurable API version.

See [CHATGPT.md](CHATGPT.md) for the current handoff state and known limitations.
