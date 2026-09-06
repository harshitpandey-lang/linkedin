from __future__ import annotations

from typing import Any
from datetime import datetime, timedelta, timezone


class PostRepository:
    def __init__(self, client: Any):
        self.client = client

    def recent_posts(self, days: int = 30) -> list[Any]:
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        return self.client.table("posts").select("news_url,news_title").gte("created_at", cutoff).limit(500).execute().data or []

    def find_by_news_url(self, news_url: str) -> dict[str, Any] | None:
        data = self.client.table("posts").select("*").eq("news_url", news_url).limit(1).execute().data or []
        return data[0] if data else None

    def create(self, values: dict[str, Any]) -> dict[str, Any]:
        return self.client.table("posts").insert(values).execute().data[0]

    def update(self, post_id: str, values: dict[str, Any]) -> dict[str, Any]:
        return self.client.table("posts").update(values).eq("id", post_id).execute().data[0]

    def approved_unpublished(self) -> list[Any]:
        records = self.client.table("posts").select("*").eq("approval_status", "APPROVED").execute().data or []
        return [record for record in records if not (record.get("linkedin_status") == "PUBLISHED" and record.get("instagram_status") == "PUBLISHED")]
