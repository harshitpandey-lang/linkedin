from __future__ import annotations

import os
from pathlib import Path
import httpx

from .base import PublishResult


class InstagramPublisher:
    def __init__(self, token: str | None = None, account_id: str | None = None):
        self.token = token or os.environ["INSTAGRAM_ACCESS_TOKEN"]
        self.account_id = account_id or os.environ["INSTAGRAM_ACCOUNT_ID"]

    def publish(self, caption: str, image: Path) -> PublishResult:
        public_url = os.getenv("IMAGE_PUBLIC_URL")
        if not public_url:
            return PublishResult(False, error="IMAGE_PUBLIC_URL is required for Instagram publishing")
        base = f"https://graph.facebook.com/v20.0/{self.account_id}"
        try:
            container = httpx.post(f"{base}/media", params={"image_url": public_url, "caption": caption, "access_token": self.token}, timeout=30)
            container.raise_for_status()
            creation_id = container.json()["id"]
            result = httpx.post(f"{base}/media_publish", params={"creation_id": creation_id, "access_token": self.token}, timeout=30)
            result.raise_for_status()
            return PublishResult(True, result.json().get("id", ""))
        except (httpx.HTTPError, KeyError) as exc:
            return PublishResult(False, error=str(exc))
