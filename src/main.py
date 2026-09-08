from __future__ import annotations

import logging
import os

from src.ai.gemini_provider import GeminiProvider
from src.ai.gemini_provider import DEFAULT_GEMINI_MODEL
from src.config.loader import load_settings
from src.database.repository import PostRepository
from src.database.storage import ImageStorage
from src.database.supabase_client import get_client
from src.news.discovery import discover_sources
from src.pipeline.orchestrator import run_pipeline
from src.social.instagram import InstagramPublisher
from src.social.linkedin import LinkedInPublisher

logging.basicConfig(level=os.getenv("LOG_LEVEL") or "INFO", format="%(asctime)s %(levelname)s %(message)s")
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)


def main() -> None:
    settings = load_settings()
    gemini_key = os.getenv("GEMINI_API_KEY")
    if not gemini_key:
        raise RuntimeError("GEMINI_API_KEY is required")
    provider = GeminiProvider(os.environ["GEMINI_API_KEY"], os.getenv("GEMINI_MODEL") or settings.ai.get("model") or DEFAULT_GEMINI_MODEL, retries=settings.app.get("retry_attempts", 3))
    publishers = {}
    if settings.auto_publish:
        if "linkedin" in settings.app.get("enabled_platforms", []):
            publishers["linkedin"] = LinkedInPublisher()
        if "instagram" in settings.app.get("enabled_platforms", []):
            publishers["instagram"] = InstagramPublisher()
    client = get_client()
    post_id = run_pipeline(settings, provider, PostRepository(client), discover_sources, publishers, ImageStorage(client, settings.storage.get("bucket", "social-posts")))
    logging.info("Pipeline completed for post %s", post_id)


if __name__ == "__main__":
    main()
