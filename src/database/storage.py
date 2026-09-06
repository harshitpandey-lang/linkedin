from __future__ import annotations

from pathlib import Path
from typing import Any
from datetime import datetime, timezone


class ImageStorage:
    def __init__(self, client: Any, bucket: str = "social-posts"):
        self.client, self.bucket = client, bucket

    def upload(self, path: Path, storage_path: str) -> str:
        with path.open("rb") as image:
            self.client.storage.from_(self.bucket).upload(storage_path, image, {"content-type": "image/png", "upsert": "false"})
        return self.client.storage.from_(self.bucket).get_public_url(storage_path)

    @staticmethod
    def storage_path_for(run_id: str, now: datetime | None = None) -> str:
        """Return the stable, date-partitioned key used for one generated image."""
        now = now or datetime.now(timezone.utc)
        return f"{now:%Y/%m/%d}/{run_id}.png"

    def download(self, storage_path: str) -> bytes:
        """Retrieve an image later, without relying on an expired runner's disk."""
        return self.client.storage.from_(self.bucket).download(storage_path)
