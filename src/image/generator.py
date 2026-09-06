from pathlib import Path

from src.news.models import GeneratedContent
from .programmatic_generator import create_graphic


def generate_image(content: GeneratedContent, output: Path, settings: dict, brand: dict) -> Path:
    return create_graphic(content.headline, content.image_text, output, settings.get("width", 1080), settings.get("height", 1080), brand)
