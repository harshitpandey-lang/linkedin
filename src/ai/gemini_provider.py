from __future__ import annotations

import json
import logging
import time

import httpx

from src.news.models import Evaluation, EvidenceVerification, GeneratedContent, NewsStory
from .prompts import CONTENT_PROMPT, RANKING_PROMPT, VERIFICATION_PROMPT

logger = logging.getLogger(__name__)
DEFAULT_GEMINI_MODEL = "gemini-2.5-flash"


class GeminiProvider:
    def __init__(self, api_key: str, model: str = DEFAULT_GEMINI_MODEL, timeout: float = 60, retries: int = 3):
        self.api_key, self.model, self.timeout, self.retries = api_key, model, timeout, max(1, retries)

    @property
    def _model_name(self) -> str:
        return self.model.removeprefix("models/")

    def available_models(self) -> list[str]:
        response = httpx.get(
            "https://generativelanguage.googleapis.com/v1beta/models",
            headers={"x-goog-api-key": self.api_key},
            timeout=self.timeout,
        )
        response.raise_for_status()
        models = response.json().get("models", [])
        return [
            item["name"].removeprefix("models/")
            for item in models
            if "generateContent" in item.get("supportedGenerationMethods", []) and item.get("name")
        ]

    def _json(self, prompt: str) -> dict:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self._model_name}:generateContent"
        for attempt in range(self.retries):
            try:
                response = httpx.post(url, headers={"x-goog-api-key": self.api_key, "Content-Type": "application/json"}, json={"contents": [{"parts": [{"text": prompt}]}], "generationConfig": {"responseMimeType": "application/json"}}, timeout=self.timeout)
                response.raise_for_status()
                text = response.json()["candidates"][0]["content"]["parts"][0]["text"]
                payload = json.loads(text)
                if not isinstance(payload, dict):
                    raise ValueError("Gemini returned a non-object JSON response")
                return payload
            except httpx.HTTPStatusError as exc:
                status = exc.response.status_code
                if status == 404:
                    try:
                        available = self.available_models()
                    except (httpx.HTTPError, KeyError, TypeError, ValueError) as discovery_error:
                        available = []
                        logger.warning("Could not discover Gemini models after a 404: %s", discovery_error)
                    options = ", ".join(available[:10]) or "none returned for this API key"
                    raise RuntimeError(f"Gemini model '{self._model_name}' is unavailable (HTTP 404). Use GEMINI_MODEL with a model that supports generateContent; available models: {options}") from exc
                if status not in {429, 500, 502, 503, 504} or attempt == self.retries - 1:
                    logger.error("Gemini request failed for model %s with status %s", self._model_name, status)
                    raise RuntimeError(f"Gemini request failed for model {self._model_name} with status {status}") from exc
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
