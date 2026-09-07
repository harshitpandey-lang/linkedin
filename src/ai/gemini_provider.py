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
    def _model_resource(self) -> str:
        return self.model if self.model.startswith("models/") else f"models/{self.model}"

    @property
    def _model_name(self) -> str:
        return self._model_resource.removeprefix("models/")

    def available_model_details(self) -> list[dict[str, object]]:
        response = httpx.get(
            "https://generativelanguage.googleapis.com/v1beta/models",
            headers={"x-goog-api-key": self.api_key},
            timeout=self.timeout,
        )
        response.raise_for_status()
        details = []
        for item in response.json().get("models", []):
            name = item.get("name")
            methods = item.get("supportedGenerationMethods", [])
            if isinstance(name, str) and isinstance(methods, list) and "generateContent" in methods:
                details.append({"name": name if name.startswith("models/") else f"models/{name}", "displayName": item.get("displayName", ""), "supportedGenerationMethods": methods})
        return details

    def available_models(self) -> list[str]:
        return [str(item["name"]) for item in self.available_model_details()]

    @staticmethod
    def _select_fallback(models: list[dict[str, object]], excluded_resources: set[str] | None = None) -> str | None:
        excluded_resources = excluded_resources or set()
        candidates = []
        for item in models:
            name = str(item["name"])
            label = f"{name} {item.get('displayName', '')}".lower()
            if name in excluded_resources or any(term in label for term in ("tts", "image", "embedding", "live", "audio")):
                continue
            candidates.append(name)
        preferred = ("gemini-flash-latest", "gemini-2.5-flash", "gemini-2.5-flash-lite", "gemini-flash-lite-latest", "gemini-2.5-pro", "gemini-pro-latest")
        for target in preferred:
            match = next((name for name in candidates if name.removeprefix("models/") == target), None)
            if match:
                return match
        return candidates[0] if candidates else None

    def _json(self, prompt: str) -> dict:
        configured_resource = self._model_resource
        attempted_resources: set[str] = set()
        discovered_details: list[dict[str, object]] = []
        while True:
            current_resource = self._model_resource
            attempted_resources.add(current_resource)
            fallback_resource = None
            for attempt in range(self.retries):
                try:
                    url = f"https://generativelanguage.googleapis.com/v1beta/{current_resource}:generateContent"
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
                            details = self.available_model_details()
                            for item in details:
                                if item["name"] not in {detail["name"] for detail in discovered_details}:
                                    discovered_details.append(item)
                        except (httpx.HTTPError, KeyError, TypeError, ValueError) as discovery_error:
                            logger.warning("Could not discover Gemini models after a 404: %s", discovery_error)
                        fallback_resource = self._select_fallback(discovered_details, attempted_resources)
                        if fallback_resource:
                            logger.warning("Gemini model %s was unavailable; retrying with discovered model %s", current_resource, fallback_resource)
                        break
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
            if fallback_resource:
                self.model = fallback_resource
                continue
            attempted = ", ".join(sorted(attempted_resources))
            compatible = ", ".join(str(item["name"]) for item in discovered_details) or "none returned for this API key"
            raise RuntimeError(f"Gemini model resource '{configured_resource}' and all discovered fallbacks were unavailable (HTTP 404); attempted resources: {attempted}; compatible resources discovered: {compatible}")

    def evaluate(self, story: NewsStory) -> Evaluation:
        prompt = f"{RANKING_PROMPT}\nTitle: {story.title}\nSummary: {story.summary}\nSource: {story.source_name}"
        return Evaluation.model_validate(self._json(prompt))

    def generate_content(self, story: NewsStory, evidence: str = "") -> GeneratedContent:
        prompt = f"{CONTENT_PROMPT}\nTitle: {story.title}\nSummary: {story.summary}\nEvidence: {evidence or story.raw_content}\nSource URL: {story.source_url}"
        return GeneratedContent.model_validate(self._json(prompt))

    def verify_evidence(self, story: NewsStory, evidence: str, claims: str = "") -> EvidenceVerification:
        prompt = f"{VERIFICATION_PROMPT}\nTitle: {story.title}\nSource URL: {story.source_url}\nEvidence:\n{evidence}\nClaims to check:\n{claims or story.summary}"
        return EvidenceVerification.model_validate(self._json(prompt))
