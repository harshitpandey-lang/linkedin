from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv


@dataclass(frozen=True)
class Settings:
    root: Path
    app: dict[str, Any]
    ai: dict[str, Any]
    image: dict[str, Any]
    storage: dict[str, Any]
    brand: dict[str, Any]
    news_sources: list[dict[str, Any]]

    @property
    def auto_publish(self) -> bool:
        value = os.getenv("AUTO_PUBLISH") or str(self.app.get("auto_publish", False))
        return value.lower() == "true"


def _load_yaml(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as file:
        return yaml.safe_load(file) or {}


def load_settings(root: Path | None = None) -> Settings:
    root = root or Path(__file__).resolve().parents[2]
    load_dotenv(root / ".env")
    settings = _load_yaml(root / "config" / "settings.yaml")
    brand = _load_yaml(root / "config" / "brand.yaml")
    sources = _load_yaml(root / "config" / "news_sources.yaml")
    return Settings(root, settings.get("app", {}), settings.get("ai", {}), settings.get("image", {}), settings.get("storage", {}), brand, sources.get("sources", []))
