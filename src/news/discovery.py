from __future__ import annotations

import feedparser
import httpx
import logging

from .normalization import normalize_entry
from .models import NewsStory

logger = logging.getLogger(__name__)


def discover_sources(sources: list[dict], timeout: float = 20) -> list[NewsStory]:
    stories: list[NewsStory] = []
    for source in sources:
        if not source.get("enabled", True) or source.get("source_type") != "rss":
            continue
        try:
            response = httpx.get(source["url"], timeout=timeout, follow_redirects=True)
            response.raise_for_status()
            feed = feedparser.parse(response.content)
            for entry in feed.entries:
                if not entry.get("title"):
                    continue
                try:
                    stories.append(normalize_entry(dict(entry), source))
                except (KeyError, TypeError, ValueError) as exc:
                    logger.warning("Skipping malformed entry from %s: %s", source.get("name", source["url"]), exc)
        except Exception as exc:
            logger.warning("Skipping unavailable news source %s: %s", source.get("name", source.get("url", "unknown")), exc)
    return stories
