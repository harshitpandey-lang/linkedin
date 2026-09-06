from __future__ import annotations

from typing import Any


class PostRepository:
    def __init__(self, client: Any):
        self.client = client

    def recent_posts(self, days: int = 30) -> list[Any]:
        return self.client.table("posts").select("news_url,news_title").limit(500).execute().data or []

    def create(self, values: dict[str, Any]) -> dict[str, Any]:
        return self.client.table("posts").insert(values).execute().data[0]

    def update(self, post_id: str, values: dict[str, Any]) -> dict[str, Any]:
        return self.client.table("posts").update(values).eq("id", post_id).execute().data[0]

    def approved_unpublished(self) -> list[Any]:
        return self.client.table("posts").select("*").eq("approval_status", "APPROVED").in_("status", ["STORED", "PENDING_APPROVAL"]).execute().data or []
