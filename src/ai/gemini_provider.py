from __future__ import annotations

import json
import logging
import time
import math
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pydantic import BaseModel

import httpx

from src.news.models import Evaluation, EvidenceVerification, GeneratedContent, NewsStory
from .prompts import CONTENT_PROMPT, RANKING_PROMPT, VERIFICATION_PROMPT

logger = logging.getLogger(__name__)
DEFAULT_GEMINI_MODEL = "gemini-2.5-flash"


class AIOutputError(RuntimeError):
    """Invalid candidate output after bounded recovery."""


class GeminiProvider:
    def __init__(self, api_key: str, model: str = DEFAULT_GEMINI_MODEL, timeout: float = 60, retries: int = 3):
        self.api_key, self.model, self.timeout, self.retries = api_key, model, timeout, min(5, max(1, retries))

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

    @staticmethod
    def _retry_delay(attempt: int, response=None) -> float:
        value = getattr(response, "headers", {}).get("Retry-After", "")
        try:
            delay = float(value)
        except (TypeError, ValueError):
            try:
                delay = (parsedate_to_datetime(value) - datetime.now(timezone.utc)).total_seconds()
            except (TypeError, ValueError, OverflowError):
                delay = 2**attempt
        return min(30, max(0, delay)) if math.isfinite(delay) else 30

    @staticmethod
    def _parse_payload(response) -> dict:
        candidate = response.json()["candidates"][0]
        if candidate.get("finishReason", "STOP") != "STOP":
            raise ValueError("Incomplete or blocked response")
        text = "".join(part.get("text", "") for part in candidate["content"]["parts"])
        start = text.find("{")
        if start < 0:
            raise ValueError("Missing JSON object")
        payload, end = json.JSONDecoder().raw_decode(text[start:])
        if "{" in text[start + end:]:
            raise ValueError("Ambiguous multiple JSON objects")
        if not isinstance(payload, dict):
            raise ValueError("Expected JSON object")
        return payload

    def _json(self, prompt: str, schema: type[BaseModel] | None = None) -> dict:
        configured_resource = self._model_resource
        attempted_resources: set[str] = set()
        discovered_details: list[dict[str, object]] = []
        discovered = False
        statuses = {}
        if schema:
            prompt += "\nRequired JSON schema: " + json.dumps(schema.model_json_schema())
        while len(attempted_resources) < 8:
            current_resource = self._model_resource
            attempted_resources.add(current_resource)
            fallback_resource = None
            for attempt in range(self.retries):
                try:
                    url = f"https://generativelanguage.googleapis.com/v1beta/{current_resource}:generateContent"
                    response = httpx.post(url, headers={"x-goog-api-key": self.api_key, "Content-Type": "application/json"}, json={"contents": [{"parts": [{"text": prompt}]}], "generationConfig": {"responseMimeType": "application/json"}}, timeout=self.timeout)
                    response.raise_for_status()
                    payload = self._parse_payload(response)
                    if schema:
                        schema.model_validate(payload)
                    return payload
                except httpx.HTTPStatusError as exc:
                    status = exc.response.status_code
                    statuses[current_resource] = status
                    logger.warning("Gemini resource=%s status=%s attempt=%s", current_resource, status, attempt + 1)
                    if status not in {404, 429, 500, 502, 503, 504}:
                        raise RuntimeError(f"Gemini request failed for model {current_resource} with status {status}") from None
                    if status == 404 or attempt == self.retries - 1:
                        break
                    time.sleep(self._retry_delay(attempt, exc.response))
                except httpx.RequestError:
                    statuses[current_resource] = "network failure"
                    if attempt == self.retries - 1:
                        break
                    time.sleep(self._retry_delay(attempt))
                except (KeyError, IndexError, TypeError, ValueError, AttributeError):
                    logger.warning("Gemini output invalid resource=%s attempt=%s", current_resource, attempt + 1)
                    if attempt == self.retries - 1:
                        raise AIOutputError(f"Gemini response could not be validated for model {current_resource}") from None
            if not discovered:
                discovered = True
                try:
                    discovered_details = self.available_model_details()
                except httpx.HTTPStatusError as exc:
                    if exc.response.status_code in {400, 401, 403}:
                        raise RuntimeError(f"Gemini discovery failed with status {exc.response.status_code}") from None
                    logger.warning("Gemini model discovery unavailable")
                except (httpx.HTTPError, KeyError, TypeError, ValueError):
                    logger.warning("Gemini model discovery unavailable")
            fallback_resource = self._select_fallback(discovered_details, attempted_resources)
            if fallback_resource:
                self.model = fallback_resource
                continue
            break
        attempted = ", ".join(sorted(attempted_resources))
        compatible = ", ".join(str(item["name"]) for item in discovered_details) or "none"
        raise RuntimeError(f"Gemini recovery exhausted for {configured_resource}; attempted resources: {attempted}; statuses: {statuses}; compatible resources discovered: {compatible}")

    def evaluate(self, story: NewsStory) -> Evaluation:
        prompt = f"{RANKING_PROMPT}\nTitle: {story.title}\nSummary: {story.summary}\nSource: {story.source_name}"
        return Evaluation.model_validate(self._json(prompt, Evaluation))

    def generate_content(self, story: NewsStory, evidence: str = "") -> GeneratedContent:
        prompt = f"{CONTENT_PROMPT}\nTitle: {story.title}\nSummary: {story.summary}\nEvidence: {evidence or story.raw_content}\nSource URL: {story.source_url}"
        return GeneratedContent.model_validate(self._json(prompt, GeneratedContent))

    def verify_evidence(self, story: NewsStory, evidence: str, claims: str = "") -> EvidenceVerification:
        prompt = f"{VERIFICATION_PROMPT}\nTitle: {story.title}\nSource URL: {story.source_url}\nEvidence:\n{evidence}\nClaims to check:\n{claims or story.summary}"
        return EvidenceVerification.model_validate(self._json(prompt, EvidenceVerification))
