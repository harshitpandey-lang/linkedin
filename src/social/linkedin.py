from __future__ import annotations

import os
from pathlib import Path
import httpx
from .base import PublishResult


class LinkedInPublisher:
    """Publish a generated PNG through LinkedIn's current Images and Posts APIs."""
    def __init__(self, token=None, author_type=None, organization_id=None, author_urn=None, api_version=None, client=None):
        self.token = token or os.environ["LINKEDIN_ACCESS_TOKEN"]
        self.author_type = author_type or os.getenv("LINKEDIN_AUTHOR_TYPE", "person")
        self.organization_id = organization_id or os.getenv("LINKEDIN_ORGANIZATION_ID", "")
        self.author_urn = author_urn or os.getenv("LINKEDIN_AUTHOR_URN", "")
        self.api_version = api_version or os.getenv("LINKEDIN_API_VERSION", "202606")
        self.client = client or httpx.Client(timeout=30)

    @property
    def headers(self):
        return {"Authorization": f"Bearer {self.token}", "Linkedin-Version": self.api_version, "X-Restli-Protocol-Version": "2.0.0"}

    def resolve_author(self) -> str:
        if self.author_type not in {"person", "organization", "page"}:
            raise ValueError("LINKEDIN_AUTHOR_TYPE must be 'person', 'organization', or 'page'")
        if self.author_urn:
            expected_prefix = "urn:li:organization:" if self.author_type in {"organization", "page"} else "urn:li:person:"
            if not self.author_urn.startswith(expected_prefix):
                raise ValueError(f"LINKEDIN_AUTHOR_URN must use {expected_prefix}")
            return self.author_urn
        if self.author_type in {"organization", "page"}:
            if not self.organization_id:
                raise ValueError("LINKEDIN_ORGANIZATION_ID or LINKEDIN_AUTHOR_URN is required for organization posting")
            return f"urn:li:organization:{self.organization_id}"
        response = self.client.get("https://api.linkedin.com/v2/userinfo", headers=self.headers)
        response.raise_for_status()
        person_id = response.json().get("sub")
        if not person_id:
            raise ValueError("LinkedIn userinfo response did not include sub; grant openid/profile or set LINKEDIN_AUTHOR_URN")
        return f"urn:li:person:{person_id}"

    def publish(self, caption: str, image: Path, image_public_url: str = "") -> PublishResult:
        try:
            author = self.resolve_author()
            init = self.client.post("https://api.linkedin.com/rest/images?action=initializeUpload", headers={**self.headers, "Content-Type": "application/json"}, json={"initializeUploadRequest": {"owner": author}})
            init.raise_for_status()
            upload = init.json()["value"]
            with image.open("rb") as file:
                binary = self.client.put(upload["uploadUrl"], content=file.read(), headers={"Content-Type": "image/png"})
            binary.raise_for_status()
            payload = {"author": author, "commentary": caption, "visibility": "PUBLIC", "distribution": {"feedDistribution": "MAIN_FEED", "targetEntities": [], "thirdPartyDistributionChannels": []}, "content": {"media": {"id": upload["image"], "altText": "AI news editorial graphic"}}, "lifecycleState": "PUBLISHED", "isReshareDisabledByAuthor": False}
            post = self.client.post("https://api.linkedin.com/rest/posts", headers={**self.headers, "Content-Type": "application/json"}, json=payload)
            post.raise_for_status()
            post_data = post.json()
            post_id = post.headers.get("x-restli-id") or post.headers.get("X-RestLi-Id") or post_data.get("id", "")
            return PublishResult(True, post_id)
        except (httpx.HTTPError, KeyError, ValueError, OSError) as exc:
            return PublishResult(False, error=str(exc))
