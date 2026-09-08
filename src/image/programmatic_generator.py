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
    return ImageFont.load_default(size=size)


def wrap_text(draw, text: str, font, width: int) -> str:
    lines = []
    line = ""
    for word in text.split():
        candidate = f"{line} {word}".strip()
        if draw.textbbox((0, 0), candidate, font=font)[2] <= width:
            line = candidate
            continue
        if line:
            lines.append(line)
        line = ""
        for char in word:
            if line and draw.textbbox((0, 0), line + char, font=font)[2] > width:
                lines.append(line)
                line = ""
            line += char
    if line:
        lines.append(line)
    return "\n".join(lines)


def fit_text(draw, text, width, height, size, bold=False):
    for font_size in range(size, 23, -2):
        font = _font(font_size, bold)
        wrapped = wrap_text(draw, text, font, width)
        box = draw.multiline_textbbox((0, 0), wrapped, font=font, spacing=12)
        if box[2] - box[0] <= width and box[3] - box[1] <= height:
            return wrapped, font, box
    raise ValueError("Image text cannot fit safely at a readable font size")


def create_graphic(headline: str, support: str, output: Path, width: int = 1080, height: int = 1080, brand: dict | None = None) -> Path:
    if (width, height) != (1080, 1080):
        raise ValueError("Social images must be 1080x1080")
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
    for text, y, height_limit, size, bold, color in ((headline, 300, 340, 72, True, colors[1]), (support, 700, 280, 32, False, "#B8C4D9")):
        wrapped, font, box = fit_text(draw, text, width - 160, height_limit, size, bold)
        draw.multiline_text((80 - box[0], y - box[1]), wrapped, fill=color, font=font, spacing=12)
    output.parent.mkdir(parents=True, exist_ok=True)
    image.save(output, format="PNG", optimize=True)
    return output
