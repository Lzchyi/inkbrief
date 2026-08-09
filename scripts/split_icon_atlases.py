from __future__ import annotations

import argparse
from collections.abc import Iterable
from pathlib import Path

from PIL import Image, ImageOps

ROOT = Path(__file__).resolve().parents[1]


def grayscale_rgba(image: Image.Image) -> Image.Image:
    rgba = image.convert("RGBA")
    gray = ImageOps.grayscale(rgba.convert("RGB"))
    return Image.merge("RGBA", (gray, gray, gray, rgba.getchannel("A")))


def normalized_icon(cell: Image.Image, size: int) -> Image.Image:
    cell = grayscale_rgba(cell)
    alpha = cell.getchannel("A")
    bounds = alpha.getbbox()
    if bounds is None:
        raise ValueError("icon cell is empty")
    cropped = cell.crop(bounds)
    padding = max(8, round(max(cropped.size) * 0.08))
    side = max(cropped.size) + padding * 2
    square = Image.new("RGBA", (side, side), (255, 255, 255, 0))
    square.alpha_composite(
        cropped,
        ((side - cropped.width) // 2, (side - cropped.height) // 2),
    )
    return square.resize((size, size), Image.Resampling.LANCZOS)


def split_grid(
    source: Image.Image,
    *,
    columns: int,
    rows: int,
    names: Iterable[str],
    output_dir: Path,
    size: int,
) -> None:
    names = tuple(names)
    if len(names) != columns * rows:
        raise ValueError("grid dimensions do not match icon names")
    output_dir.mkdir(parents=True, exist_ok=True)
    for index, name in enumerate(names):
        column = index % columns
        row = index // columns
        box = (
            round(column * source.width / columns),
            round(row * source.height / rows),
            round((column + 1) * source.width / columns),
            round((row + 1) * source.height / rows),
        )
        normalized_icon(source.crop(box), size).save(output_dir / f"{name}.png")


def split_motorsport(source: Image.Image, output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    top_names = ("helmet", "car", "checkered-flag")
    bottom_names = ("calendar", "countdown", "trophy", "podium")
    midpoint = source.height // 2
    for index, name in enumerate(top_names):
        box = (
            round(index * source.width / len(top_names)),
            0,
            round((index + 1) * source.width / len(top_names)),
            midpoint,
        )
        normalized_icon(source.crop(box), 512).save(output_dir / f"{name}.png")
    for index, name in enumerate(bottom_names):
        box = (
            round(index * source.width / len(bottom_names)),
            midpoint,
            round((index + 1) * source.width / len(bottom_names)),
            source.height,
        )
        normalized_icon(source.crop(box), 512).save(output_dir / f"{name}.png")


def crop_compact_motorsport(source_path: Path, output_dir: Path) -> None:
    """Crop the simple alternate helmet/car variants from the supplied F1 sheet."""
    source = Image.open(source_path).convert("L")
    if source.size != (1122, 1402):
        raise ValueError(f"unexpected F1 source-sheet dimensions: {source.size}")
    boxes = {
        "helmet-compact": (95, 592, 249, 736),
        "helmet-compact-alt": (318, 590, 476, 742),
        "car-compact": (588, 599, 812, 720),
        "car-compact-alt": (839, 596, 1043, 721),
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    for name, box in boxes.items():
        gray = ImageOps.autocontrast(source.crop(box), cutoff=(1, 1))
        alpha = ImageOps.invert(gray).point(
            lambda value: 0 if value < 10 else min(255, round((value - 10) * 1.22))
        )
        icon = Image.new("RGBA", gray.size, (0, 0, 0, 0))
        icon.putalpha(alpha)
        normalized_icon(icon, 512).save(output_dir / f"{name}.png")


def prepare_atlas(path: Path) -> Image.Image:
    atlas = grayscale_rgba(Image.open(path))
    if atlas.getpixel((0, 0))[3] != 0:
        raise ValueError(f"{path} does not have a transparent corner")
    atlas.save(path)
    return atlas


def main() -> None:
    parser = argparse.ArgumentParser(description="Split cleaned Kindle Brief icon atlases")
    parser.add_argument(
        "--f1-sheet",
        type=Path,
        help="optional original 1122x1402 F1.png sheet for compact alternate variants",
    )
    arguments = parser.parse_args()

    weather = prepare_atlas(ROOT / "assets/weather/atlas.png")
    split_grid(
        weather,
        columns=6,
        rows=3,
        names=(
            "clear-day",
            "clear-night",
            "partly-cloudy-day",
            "partly-cloudy-night",
            "mostly-cloudy",
            "overcast",
            "windy",
            "fog",
            "haze",
            "drizzle",
            "rain",
            "heavy-rain",
            "showers",
            "thunderstorm",
            "thunderstorm-rain",
            "snow",
            "sleet-hail",
            "severe-storm",
        ),
        output_dir=ROOT / "assets/weather/icons",
        size=384,
    )

    moon = prepare_atlas(ROOT / "assets/moon/phase-atlas.png")
    split_grid(
        moon,
        columns=4,
        rows=2,
        names=(
            "new-moon",
            "waxing-crescent",
            "first-quarter",
            "waxing-gibbous",
            "full-moon",
            "waning-gibbous",
            "last-quarter",
            "waning-crescent",
        ),
        output_dir=ROOT / "assets/moon/phases",
        size=512,
    )

    moon_horizons = prepare_atlas(ROOT / "assets/moon/horizon-atlas.png")
    split_grid(
        moon_horizons,
        columns=2,
        rows=1,
        names=("moonrise", "moonset"),
        output_dir=ROOT / "assets/moon/horizons",
        size=512,
    )

    motorsport = prepare_atlas(ROOT / "assets/icons/motorsport-atlas.png")
    split_motorsport(motorsport, ROOT / "assets/icons/motorsport")

    track = prepare_atlas(ROOT / "assets/icons/track-symbol.png")
    normalized_icon(track, 512).save(ROOT / "assets/icons/motorsport/track.png")
    if arguments.f1_sheet is not None:
        crop_compact_motorsport(arguments.f1_sheet, ROOT / "assets/icons/motorsport")


if __name__ == "__main__":
    main()
