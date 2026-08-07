from __future__ import annotations

import math
from functools import lru_cache

from PIL import Image, ImageDraw, ImageOps

from .theme import project_root


@lru_cache(maxsize=16)
def _phase_asset(name: str, size: int) -> Image.Image:
    path = project_root() / "assets" / "moon" / "phases" / f"{name}.png"
    with Image.open(path) as source:
        return source.convert("RGBA").resize((size, size), Image.Resampling.LANCZOS)


def moon_phase_image(
    size: int, phase_angle: float, *, paper: int = 255, ink: int = 18
) -> Image.Image:
    """Render a continuously illuminated, textured lunar disc.

    The user-supplied full-moon artwork provides the surface texture while
    the analytical terminator keeps intermediate phases accurate instead of
    snapping the display to one of eight labels.
    """
    if size <= 0:
        raise ValueError("moon size must be positive")
    scale = 3
    high_size = size * scale
    phase = phase_angle % 360.0
    cosine = math.cos(math.radians(phase))
    full = _phase_asset("full-moon", high_size)
    full_gray = ImageOps.grayscale(full.convert("RGB"))
    alpha = full.getchannel("A")
    bounds = alpha.getbbox()
    if bounds is None:
        raise ValueError("moon phase assets are empty")
    left, top, right, bottom = bounds
    center_x = (left + right) / 2
    center_y = (top + bottom) / 2
    radius_x = max(1.0, (right - left) / 2)
    radius_y = max(1.0, (bottom - top) / 2)
    image = Image.new("L", (high_size, high_size), paper)
    pixels = image.load()

    for py in range(top, bottom):
        y = (py + 0.5 - center_y) / radius_y
        if abs(y) > 1:
            continue
        edge = math.sqrt(max(0.0, 1.0 - y * y))
        boundary = cosine * edge if phase <= 180 else -cosine * edge
        for px in range(left, right):
            opacity = alpha.getpixel((px, py))
            if opacity == 0:
                continue
            x = (px + 0.5 - center_x) / radius_x
            if x * x + y * y > 1:
                continue
            lit = x >= boundary if phase <= 180 else x <= boundary
            if lit:
                value = full_gray.getpixel((px, py))
            else:
                value = min(full_gray.getpixel((px, py)), ink + 30)
            pixels[px, py] = round((value * opacity + paper * (255 - opacity)) / 255)

    draw = ImageDraw.Draw(image)
    draw.ellipse(
        (left, top, right - 1, bottom - 1),
        outline=ink,
        width=scale,
    )
    return image.resize((size, size), Image.Resampling.LANCZOS)
