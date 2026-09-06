from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


@dataclass(frozen=True)
class PublishResult:
    success: bool
    post_id: str = ""
    url: str = ""
    error: str = ""


class Publisher(Protocol):
    def publish(self, caption: str, image: Path) -> PublishResult: ...
