from __future__ import annotations

import math

from PIL import Image, ImageDraw


def moon_phase_image(
    size: int, phase_angle: float, *, paper: int = 255, ink: int = 18
) -> Image.Image:
    """Render a smooth lunar disc from 0° new through 180° full to 360° new."""
    scale = 3
    high_size = size * scale
    radius = (high_size - 4 * scale) / 2
    center = high_size / 2
    phase = phase_angle % 360.0
    cosine = math.cos(math.radians(phase))
    image = Image.new("L", (high_size, high_size), paper)
    pixels = image.load()

    for py in range(high_size):
        y = (py + 0.5 - center) / radius
        if abs(y) > 1:
            continue
        edge = math.sqrt(max(0.0, 1.0 - y * y))
        boundary = cosine * edge if phase <= 180 else -cosine * edge
        for px in range(high_size):
            x = (px + 0.5 - center) / radius
            if x * x + y * y > 1:
                continue
            lit = x >= boundary if phase <= 180 else x <= boundary
            pixels[px, py] = paper if lit else ink

    draw = ImageDraw.Draw(image)
    inset = 2 * scale
    draw.ellipse(
        (inset, inset, high_size - inset - 1, high_size - inset - 1), outline=ink, width=scale
    )
    return image.resize((size, size), Image.Resampling.LANCZOS)
