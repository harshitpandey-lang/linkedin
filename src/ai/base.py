from __future__ import annotations

from typing import Protocol

from src.news.models import Evaluation, EvidenceVerification, GeneratedContent, NewsStory


class AIProvider(Protocol):
    def evaluate(self, story: NewsStory) -> Evaluation: ...
    def generate_content(self, story: NewsStory, evidence: str = "") -> GeneratedContent: ...
    def verify_evidence(self, story: NewsStory, evidence: str, claims: str = "") -> EvidenceVerification: ...
