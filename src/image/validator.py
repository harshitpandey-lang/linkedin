from __future__ import annotations

from pathlib import Path
from PIL import Image


def validate_image(path: Path, width: int = 1080, height: int = 1080) -> tuple[bool, str]:
    if not path.exists() or path.stat().st_size == 0:
        return False, "Image is missing or empty"
    try:
        with Image.open(path) as image:
            if image.size != (width, height):
                return False, f"Expected {width}x{height}, got {image.size}"
            image.verify()
    except Exception as exc:
        return False, f"Invalid image: {exc}"
    return True, ""
