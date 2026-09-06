from __future__ import annotations

from datetime import datetime
from email.utils import parsedate_to_datetime
from typing import Any

from .models import NewsStory


def _parse_date(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value
    if not value:
        return None
    for parser in (parsedate_to_datetime, lambda item: datetime.fromisoformat(str(item).replace("Z", "+00:00"))):
        try:
            return parser(value)
        except (TypeError, ValueError, OverflowError):
            continue
    return None


def normalize_entry(entry: dict[str, Any], source: dict[str, Any]) -> NewsStory:
    summary = str(entry.get("summary", entry.get("description", ""))).strip()
    return NewsStory(
        title=str(entry.get("title", "")).strip(),
        summary=summary,
        source_name=source["name"],
        source_url=entry.get("link") or entry.get("url") or source["url"],
        published_at=_parse_date(entry.get("published") or entry.get("published_at") or entry.get("updated")),
        author=str(entry.get("author", "")).strip(),
        category=source.get("category", "AI"),
        raw_content=str(entry.get("content", summary)),
        reliability=float(source.get("reliability", 0.5)),
    )
