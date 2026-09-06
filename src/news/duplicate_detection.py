from __future__ import annotations

import re
from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Protocol

from .models import NewsStory


class ExistingPost(Protocol):
    news_url: str
    news_title: str


@dataclass(frozen=True)
class DuplicateMatch:
    duplicate: bool
    reason: str = ""
    matched_url: str = ""


def _tokens(value: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", value.lower()))


def detect_duplicate(story: NewsStory, existing_posts: list[ExistingPost], threshold: float = 0.82) -> DuplicateMatch:
    story_url = str(story.source_url).rstrip("/")
    story_tokens = _tokens(story.title)
    for post in existing_posts:
        if str(post.news_url).rstrip("/") == story_url:
            return DuplicateMatch(True, "identical source URL", post.news_url)
        post_tokens = _tokens(post.news_title)
        similarity = SequenceMatcher(None, story.title.lower(), post.news_title.lower()).ratio()
        overlap = len(story_tokens & post_tokens) / max(len(story_tokens | post_tokens), 1)
        if max(similarity, overlap) >= threshold:
            return DuplicateMatch(True, "similar previously posted title", post.news_url)
    return DuplicateMatch(False)
