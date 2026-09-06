from __future__ import annotations

from .models import NewsStory


def filter_recent(stories: list[NewsStory], max_age_hours: int = 48) -> list[NewsStory]:
    return [story for story in stories if story.age_hours is None or story.age_hours <= max_age_hours]
