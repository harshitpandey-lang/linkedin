from __future__ import annotations

import json
import logging
import time

import httpx

from src.news.models import Evaluation, EvidenceVerification, GeneratedContent, NewsStory
from .prompts import CONTENT_PROMPT, RANKING_PROMPT, VERIFICATION_PROMPT

logger = logging.getLogger(__name__)


class GeminiProvider:
    def __init__(self, api_key: str, model: str = "gemini-2.0-flash", timeout: float = 60, retries: int = 3):
        self.api_key, self.model, self.timeout, self.retries = api_key, model, timeout, max(1, retries)

    def _json(self, prompt: str) -> dict:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent"
        for attempt in range(self.retries):
            try:
                response = httpx.post(url, params={"key": self.api_key}, json={"contents": [{"parts": [{"text": prompt}]}], "generationConfig": {"responseMimeType": "application/json"}}, timeout=self.timeout)
                response.raise_for_status()
                text = response.json()["candidates"][0]["content"]["parts"][0]["text"]
                payload = json.loads(text)
                if not isinstance(payload, dict):
                    raise ValueError("Gemini returned a non-object JSON response")
                return payload
            except httpx.HTTPStatusError as exc:
                status = exc.response.status_code
                if status not in {429, 500, 502, 503, 504} or attempt == self.retries - 1:
                    logger.error("Gemini request failed for model %s with status %s", self.model, status)
                    raise RuntimeError(f"Gemini request failed for model {self.model} with status {status}") from exc
                time.sleep(2**attempt)
            except httpx.RequestError as exc:
                if attempt == self.retries - 1:
                    logger.error("Gemini network request failed for model %s: %s", self.model, exc)
                    raise RuntimeError(f"Gemini network request failed for model {self.model}") from exc
                time.sleep(2**attempt)
            except (KeyError, IndexError, TypeError, ValueError, json.JSONDecodeError) as exc:
                logger.error("Gemini response failed validation for model %s: %s", self.model, exc)
                raise RuntimeError(f"Gemini response could not be validated for model {self.model}") from exc
        raise RuntimeError(f"Gemini request failed for model {self.model}")

    def evaluate(self, story: NewsStory) -> Evaluation:
        prompt = f"{RANKING_PROMPT}\nTitle: {story.title}\nSummary: {story.summary}\nSource: {story.source_name}"
        return Evaluation.model_validate(self._json(prompt))

    def generate_content(self, story: NewsStory, evidence: str = "") -> GeneratedContent:
        prompt = f"{CONTENT_PROMPT}\nTitle: {story.title}\nSummary: {story.summary}\nEvidence: {evidence or story.raw_content}\nSource URL: {story.source_url}"
        return GeneratedContent.model_validate(self._json(prompt))

    def verify_evidence(self, story: NewsStory, evidence: str, claims: str = "") -> EvidenceVerification:
        prompt = f"{VERIFICATION_PROMPT}\nTitle: {story.title}\nSource URL: {story.source_url}\nEvidence:\n{evidence}\nClaims to check:\n{claims or story.summary}"
        return EvidenceVerification.model_validate(self._json(prompt))
