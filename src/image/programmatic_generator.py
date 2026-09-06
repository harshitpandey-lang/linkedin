from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


def _font(size: int, bold: bool = False):
    candidates = ["C:/Windows/Fonts/arialbd.ttf" if bold else "C:/Windows/Fonts/arial.ttf", "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf"]
    for candidate in candidates:
        try:
            return ImageFont.truetype(candidate, size)
        except OSError:
            continue
    return ImageFont.load_default()


def create_graphic(headline: str, support: str, output: Path, width: int = 1080, height: int = 1080, brand: dict | None = None) -> Path:
    colors = (brand or {}).get("primary_colors", ["#0B132B", "#F4F1DE"])
    accent = (brand or {}).get("secondary_colors", ["#5BC0BE"])[0]
    image = Image.new("RGB", (width, height), colors[0])
    draw = ImageDraw.Draw(image)
    for x in range(0, width, 60):
        draw.line((x, 0, x, height), fill="#172447", width=1)
    for y in range(0, height, 60):
        draw.line((0, y, width, y), fill="#172447", width=1)
    draw.rectangle((80, 100, 150, 112), fill=accent)
    draw.text((80, 150), "AI BRIEFING", fill=accent, font=_font(30, True))
    draw.multiline_text((80, 300), headline[:100], fill=colors[1], font=_font(72, True), spacing=14)
    draw.multiline_text((80, 700), support[:180], fill="#B8C4D9", font=_font(32), spacing=8)
    output.parent.mkdir(parents=True, exist_ok=True)
    image.save(output, format="PNG", optimize=True)
    return output
