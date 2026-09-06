from __future__ import annotations

from dataclasses import dataclass

from .models import NewsStory


@dataclass(frozen=True)
class VerificationResult:
    verified: bool
    reason: str = ""


def verify_story(story: NewsStory) -> VerificationResult:
    if not story.title.strip() or not str(story.source_url).startswith(("http://", "https://")):
        return VerificationResult(False, "Missing title or valid source URL")
    if story.reliability < 0.5:
        return VerificationResult(False, "Source reliability is below the configured threshold")
    return VerificationResult(True)
