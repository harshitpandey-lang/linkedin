from __future__ import annotations

import logging
import os

from src.ai.gemini_provider import GeminiProvider
from src.config.loader import load_settings
from src.database.repository import PostRepository
from src.database.supabase_client import get_client
from src.news.discovery import discover_sources
from src.pipeline.orchestrator import run_pipeline
from src.social.instagram import InstagramPublisher
from src.social.linkedin import LinkedInPublisher

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"), format="%(asctime)s %(levelname)s %(message)s")


def main() -> None:
    settings = load_settings()
    provider = GeminiProvider(os.environ["GEMINI_API_KEY"], settings.ai.get("model", os.getenv("GEMINI_MODEL", "gemini-2.0-flash")))
    publishers = {}
    if "linkedin" in settings.app.get("enabled_platforms", []):
        publishers["linkedin"] = LinkedInPublisher()
    if "instagram" in settings.app.get("enabled_platforms", []):
        publishers["instagram"] = InstagramPublisher()
    post_id = run_pipeline(settings, provider, PostRepository(get_client()), discover_sources, publishers)
    logging.info("Pipeline completed for post %s", post_id)


if __name__ == "__main__":
    main()
