from __future__ import annotations

import feedparser
import httpx

from .normalization import normalize_entry
from .models import NewsStory


def discover_sources(sources: list[dict], timeout: float = 20) -> list[NewsStory]:
    stories: list[NewsStory] = []
    for source in sources:
        if not source.get("enabled", True) or source.get("source_type") != "rss":
            continue
        response = httpx.get(source["url"], timeout=timeout, follow_redirects=True)
        response.raise_for_status()
        feed = feedparser.parse(response.content)
        stories.extend(normalize_entry(dict(entry), source) for entry in feed.entries if entry.get("title"))
    return stories
