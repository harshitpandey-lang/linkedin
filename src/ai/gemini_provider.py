from __future__ import annotations

import json

import httpx

from src.news.models import Evaluation, EvidenceVerification, GeneratedContent, NewsStory
from .prompts import CONTENT_PROMPT, RANKING_PROMPT, VERIFICATION_PROMPT


class GeminiProvider:
    def __init__(self, api_key: str, model: str = "gemini-2.0-flash", timeout: float = 60):
        self.api_key, self.model, self.timeout = api_key, model, timeout

    def _json(self, prompt: str) -> dict:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent"
        response = httpx.post(url, params={"key": self.api_key}, json={"contents": [{"parts": [{"text": prompt}]}], "generationConfig": {"responseMimeType": "application/json"}}, timeout=self.timeout)
        response.raise_for_status()
        text = response.json()["candidates"][0]["content"]["parts"][0]["text"]
        return json.loads(text)

    def evaluate(self, story: NewsStory) -> Evaluation:
        prompt = f"{RANKING_PROMPT}\nTitle: {story.title}\nSummary: {story.summary}\nSource: {story.source_name}"
        return Evaluation.model_validate(self._json(prompt))

    def generate_content(self, story: NewsStory) -> GeneratedContent:
        prompt = f"{CONTENT_PROMPT}\nTitle: {story.title}\nSummary: {story.summary}\nEvidence: {story.raw_content}\nSource URL: {story.source_url}"
        return GeneratedContent.model_validate(self._json(prompt))

    def verify_evidence(self, story: NewsStory, evidence: str, claims: str = "") -> EvidenceVerification:
        prompt = f"{VERIFICATION_PROMPT}\nTitle: {story.title}\nSource URL: {story.source_url}\nEvidence:\n{evidence}\nClaims to check:\n{claims or story.summary}"
        return EvidenceVerification.model_validate(self._json(prompt))
