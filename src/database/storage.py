from __future__ import annotations

from pathlib import Path
from typing import Any
from datetime import datetime, timezone
import time
import httpx
from storage3.exceptions import StorageApiError
from src.image.validator import validate_image


class ImageStorage:
    def __init__(self, client: Any, bucket: str = "social-posts"):
        self.client, self.bucket = client, bucket

    def upload(self, path: Path, storage_path: str) -> str:
        valid, reason = validate_image(path)
        if not valid:
            raise RuntimeError(f"STORAGE rejected image: {reason}")
        bucket = self.client.storage.from_(self.bucket)
        for attempt in range(3):
            try:
                with path.open("rb") as image:
                    bucket.upload(storage_path, image, {"content-type": "image/png", "upsert": "false"})
                break
            except StorageApiError as exc:
                if str(exc.status) == "409" or exc.code in {"Duplicate", "ResourceAlreadyExists"}:
                    if bucket.download(storage_path) != path.read_bytes():
                        raise RuntimeError("STORAGE existing object differs; refusing to overwrite") from None
                    break
                if str(exc.status) not in {"429", "500", "502", "503", "504"} or attempt == 2:
                    raise RuntimeError("STORAGE upload failed; check social-posts bucket and server access") from None
            except httpx.RequestError:
                if attempt == 2:
                    raise RuntimeError("STORAGE upload network retries exhausted") from None
            time.sleep(2**attempt)
        url = bucket.get_public_url(storage_path)
        if not isinstance(url, str) or not url.startswith("https://"):
            raise RuntimeError("STORAGE did not return a valid public URL")
        return url

    @staticmethod
    def storage_path_for(run_id: str, now: datetime | None = None) -> str:
        """Return the stable, date-partitioned key used for one generated image."""
        now = now or datetime.now(timezone.utc)
        return f"{now:%Y/%m/%d}/{run_id}.png"

    def download(self, storage_path: str) -> bytes:
        """Retrieve an image later, without relying on an expired runner's disk."""
        return self.client.storage.from_(self.bucket).download(storage_path)
