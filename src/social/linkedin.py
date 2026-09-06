from __future__ import annotations

import os
from pathlib import Path
import httpx

from .base import PublishResult


class LinkedInPublisher:
    def __init__(self, token: str | None = None, author_type: str | None = None, organization_id: str | None = None, api_version: str | None = None):
        self.token = token or os.environ["LINKEDIN_ACCESS_TOKEN"]
        self.author_type = author_type or os.getenv("LINKEDIN_AUTHOR_TYPE", "person")
        self.organization_id = organization_id or os.getenv("LINKEDIN_ORGANIZATION_ID", "")
        self.api_version = api_version or os.getenv("LINKEDIN_API_VERSION", "v2")

    def publish(self, caption: str, image: Path) -> PublishResult:
        author = f"urn:li:organization:{self.organization_id}" if self.author_type == "organization" else "urn:li:person:me"
        headers = {"Authorization": f"Bearer {self.token}", "X-Restli-Protocol-Version": "2.0.0", "Content-Type": "application/json"}
        payload = {"author": author, "lifecycleState": "PUBLISHED", "specificContent": {"com.linkedin.ugc.ShareContent": {"shareCommentary": {"text": caption}, "shareMediaCategory": "NONE"}}, "visibility": {"com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"}}
        try:
            response = httpx.post("https://api.linkedin.com/v2/ugcPosts", headers=headers, json=payload, timeout=30)
            response.raise_for_status()
            return PublishResult(True, response.headers.get("x-restli-id", response.json().get("id", "")))
        except httpx.HTTPError as exc:
            return PublishResult(False, error=str(exc))
