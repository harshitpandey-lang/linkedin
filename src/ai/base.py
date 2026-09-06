from __future__ import annotations

from typing import Protocol

from src.news.models import Evaluation, GeneratedContent, NewsStory


class AIProvider(Protocol):
    def evaluate(self, story: NewsStory) -> Evaluation: ...
    def generate_content(self, story: NewsStory) -> GeneratedContent: ...
