from __future__ import annotations

from pathlib import Path
from typing import Any


class ImageStorage:
    def __init__(self, client: Any, bucket: str = "social-posts"):
        self.client, self.bucket = client, bucket

    def upload(self, path: Path, storage_path: str) -> str:
        with path.open("rb") as image:
            self.client.storage.from_(self.bucket).upload(storage_path, image, {"content-type": "image/png", "upsert": "false"})
        return self.client.storage.from_(self.bucket).get_public_url(storage_path)
