from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from PIL import ImageFont

PAPER = 255
INK = 18
SECONDARY = 82
MUTED = 102
DIVIDER = 194
PANEL = 242

BASE_WIDTH = 1072
BASE_HEIGHT = 1448


def project_root() -> Path:
    """Resolve repository assets for editable installs and CLI use."""
    candidates = (Path.cwd(), Path(__file__).resolve().parents[3])
    for candidate in candidates:
        if (candidate / "assets/fonts/NotoSansCJKsc-Regular.otf").is_file():
            return candidate
    raise FileNotFoundError("assets/fonts/NotoSansCJKsc-Regular.otf is missing")


@lru_cache(maxsize=64)
def font(size: int) -> ImageFont.FreeTypeFont:
    path = project_root() / "assets/fonts/NotoSansCJKsc-Regular.otf"
    return ImageFont.truetype(str(path), size=size)


def scaled(value: int | float, width: int = BASE_WIDTH) -> int:
    return max(1, round(float(value) * width / BASE_WIDTH))
