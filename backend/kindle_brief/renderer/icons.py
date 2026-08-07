from __future__ import annotations

import math
from collections.abc import Sequence
from functools import lru_cache

from PIL import Image, ImageDraw, ImageOps

from .theme import PAPER, project_root

Point = tuple[float, float]


_WEATHER_ICON_BY_CODE: dict[int, str] = {
    0: "clear-day",
    1: "clear-day",
    2: "partly-cloudy-day",
    3: "overcast",
    45: "fog",
    48: "fog",
    51: "drizzle",
    53: "drizzle",
    55: "heavy-rain",
    56: "sleet-hail",
    57: "sleet-hail",
    61: "rain",
    63: "rain",
    65: "heavy-rain",
    66: "sleet-hail",
    67: "sleet-hail",
    71: "snow",
    73: "snow",
    75: "snow",
    77: "snow",
    80: "showers",
    81: "showers",
    82: "heavy-rain",
    85: "snow",
    86: "snow",
    95: "thunderstorm",
    96: "thunderstorm-rain",
    99: "severe-storm",
}


@lru_cache(maxsize=64)
def _asset(relative_path: str) -> Image.Image:
    path = project_root() / "assets" / relative_path
    with Image.open(path) as image:
        return image.convert("RGBA")


def raster_asset(relative_path: str, size: int) -> Image.Image:
    if size <= 0:
        raise ValueError("icon size must be positive")
    source = _asset(relative_path).resize((size, size), Image.Resampling.LANCZOS)
    gray = ImageOps.grayscale(source.convert("RGB"))
    result = Image.new("L", (size, size), PAPER)
    result.paste(gray, (0, 0), source.getchannel("A"))
    return result


def weather_icon_name(
    condition_code: str,
    *,
    is_night: bool = False,
    wind_kph: float | None = None,
    visibility_km: float | None = None,
    cloud_cover_pct: float | None = None,
) -> str:
    try:
        code = int(condition_code)
    except (TypeError, ValueError):
        code = 3
    if code in {0, 1, 2} and wind_kph is not None and wind_kph >= 40:
        return "windy"
    if code in {0, 1, 2, 3} and visibility_km is not None and visibility_km < 5:
        return "haze"
    name = _WEATHER_ICON_BY_CODE.get(code, "overcast")
    if cloud_cover_pct is not None and (
        (code == 2 and cloud_cover_pct >= 70) or (code == 3 and cloud_cover_pct < 90)
    ):
        name = "mostly-cloudy"
    if is_night:
        if name == "clear-day":
            return "clear-night"
        if name == "partly-cloudy-day":
            return "partly-cloudy-night"
    return name


def weather_asset(
    condition_code: str,
    size: int,
    *,
    is_night: bool = False,
    wind_kph: float | None = None,
    visibility_km: float | None = None,
    cloud_cover_pct: float | None = None,
) -> Image.Image:
    name = weather_icon_name(
        condition_code,
        is_night=is_night,
        wind_kph=wind_kph,
        visibility_km=visibility_km,
        cloud_cover_pct=cloud_cover_pct,
    )
    return raster_asset(f"weather/icons/{name}.png", size)


def motorsport_asset(name: str, size: int) -> Image.Image:
    if name not in {
        "helmet",
        "car",
        "checkered-flag",
        "calendar",
        "countdown",
        "trophy",
        "podium",
        "track",
        "helmet-compact",
        "car-compact",
    }:
        raise ValueError(f"unknown motorsport icon: {name}")
    return raster_asset(f"icons/motorsport/{name}.png", size)


def _scale(points: Sequence[Point], box: tuple[int, int, int, int]) -> list[Point]:
    left, top, right, bottom = box
    width, height = right - left, bottom - top
    return [(left + x * width, top + y * height) for x, y in points]


def home(
    draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int], *, ink: int, width: int
) -> None:
    roof = _scale(((0.08, 0.45), (0.5, 0.08), (0.92, 0.45)), box)
    draw.line(roof, fill=ink, width=width, joint="curve")
    left, top, right, bottom = box
    draw.line(
        _scale(((0.2, 0.4), (0.2, 0.9), (0.8, 0.9), (0.8, 0.4)), box),
        fill=ink,
        width=width,
        joint="curve",
    )
    door_left = left + (right - left) * 0.43
    door_right = left + (right - left) * 0.57
    door_top = top + (bottom - top) * 0.62
    draw.rectangle(
        (door_left, door_top, door_right, bottom * 0 + top + (bottom - top) * 0.9),
        outline=ink,
        width=width,
    )


def cloud(
    draw: ImageDraw.ImageDraw,
    box: tuple[int, int, int, int],
    *,
    ink: int,
    width: int,
    rain: bool = False,
    sun: bool = False,
) -> None:
    left, top, right, bottom = box
    w, h = right - left, bottom - top
    cloud_bottom = top + h * (0.72 if rain else 0.82)
    if sun:
        cx, cy, radius = left + w * 0.72, top + h * 0.25, w * 0.16
        draw.ellipse((cx - radius, cy - radius, cx + radius, cy + radius), outline=ink, width=width)
        for angle in range(0, 360, 45):
            radians = math.radians(angle)
            p1 = (cx + math.cos(radians) * radius * 1.25, cy + math.sin(radians) * radius * 1.25)
            p2 = (cx + math.cos(radians) * radius * 1.6, cy + math.sin(radians) * radius * 1.6)
            draw.line((p1, p2), fill=ink, width=max(1, width - 1))
    draw.ellipse(
        (left + w * 0.08, top + h * 0.38, left + w * 0.48, cloud_bottom), outline=ink, width=width
    )
    draw.ellipse(
        (left + w * 0.25, top + h * 0.2, left + w * 0.72, cloud_bottom), outline=ink, width=width
    )
    draw.ellipse(
        (left + w * 0.55, top + h * 0.34, left + w * 0.94, cloud_bottom), outline=ink, width=width
    )
    draw.rectangle((left + w * 0.25, top + h * 0.48, left + w * 0.78, cloud_bottom), fill=255)
    draw.line((left + w * 0.18, cloud_bottom, left + w * 0.84, cloud_bottom), fill=ink, width=width)
    if rain:
        for fraction in (0.3, 0.52, 0.74):
            x = left + w * fraction
            draw.line((x, top + h * 0.82, x - w * 0.04, top + h * 0.98), fill=ink, width=width)


def helmet(
    draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int], *, ink: int, width: int
) -> None:
    points = _scale(
        (
            (0.12, 0.72),
            (0.12, 0.5),
            (0.18, 0.27),
            (0.36, 0.12),
            (0.62, 0.08),
            (0.82, 0.22),
            (0.9, 0.48),
            (0.62, 0.48),
            (0.5, 0.36),
            (0.26, 0.36),
        ),
        box,
    )
    draw.line(points, fill=ink, width=width, joint="curve")
    draw.line(
        _scale(
            (
                (0.12, 0.72),
                (0.48, 0.72),
                (0.62, 0.52),
                (0.9, 0.52),
                (0.9, 0.76),
                (0.6, 0.76),
                (0.48, 0.9),
                (0.22, 0.9),
                (0.12, 0.78),
            ),
            box,
        ),
        fill=ink,
        width=width,
        joint="curve",
    )


def car(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int], *, ink: int, width: int) -> None:
    draw.line(
        _scale(
            (
                (0.06, 0.65),
                (0.25, 0.65),
                (0.36, 0.38),
                (0.68, 0.38),
                (0.82, 0.65),
                (0.95, 0.65),
                (0.95, 0.82),
                (0.06, 0.82),
                (0.06, 0.65),
            ),
            box,
        ),
        fill=ink,
        width=width,
        joint="curve",
    )
    left, top, right, bottom = box
    radius = (right - left) * 0.1
    for fraction in (0.28, 0.73):
        cx = left + (right - left) * fraction
        cy = top + (bottom - top) * 0.82
        draw.ellipse(
            (cx - radius, cy - radius, cx + radius, cy + radius), fill=255, outline=ink, width=width
        )


def category_mark(
    draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int], *, ink: int, width: int
) -> None:
    left, top, right, bottom = box
    draw.rounded_rectangle(box, radius=max(2, (right - left) // 5), outline=ink, width=width)
    draw.line(
        (
            left + (right - left) * 0.25,
            top + (bottom - top) * 0.35,
            right - (right - left) * 0.2,
            top + (bottom - top) * 0.35,
        ),
        fill=ink,
        width=width,
    )
    draw.line(
        (
            left + (right - left) * 0.25,
            top + (bottom - top) * 0.58,
            right - (right - left) * 0.32,
            top + (bottom - top) * 0.58,
        ),
        fill=ink,
        width=width,
    )
