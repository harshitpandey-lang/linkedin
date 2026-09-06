from pathlib import Path

from src.image.programmatic_generator import create_graphic
from src.image.validator import validate_image


def test_programmatic_graphic_is_valid(tmp_path: Path):
    output = create_graphic("A useful AI update", "A concise supporting line.", tmp_path / "post.png")
    assert validate_image(output) == (True, "")
