from __future__ import annotations

from dataclasses import dataclass
from html.parser import HTMLParser

import httpx

from .models import NewsStory


@dataclass(frozen=True)
class VerificationResult:
    verified: bool
    reason: str = ""


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        if data.strip():
            self.parts.append(data.strip())


def obtain_evidence(story: NewsStory, timeout: float = 20) -> str:
    """Fetch readable source text; RSS summaries alone are not treated as proof."""
    try:
        response = httpx.get(str(story.source_url), timeout=timeout, follow_redirects=True)
        response.raise_for_status()
        parser = _TextExtractor()
        parser.feed(response.text)
        return " ".join(parser.parts)[:12000]
    except (httpx.HTTPError, UnicodeError, ValueError):
        return ""


def verify_story(story: NewsStory, provider=None, evidence: str = "") -> VerificationResult:
    if not story.title.strip() or not str(story.source_url).startswith(("http://", "https://")):
        return VerificationResult(False, "Missing title or valid source URL")
    if story.reliability < 0.5:
        return VerificationResult(False, "Source reliability is below the configured threshold")
    if not evidence:
        return VerificationResult(False, "No source evidence was available")
    if provider is None:
        return VerificationResult(False, "Evidence requires an AI verifier")
    decision = provider.verify_evidence(story, evidence)
    return VerificationResult(decision.verified, decision.reason)
