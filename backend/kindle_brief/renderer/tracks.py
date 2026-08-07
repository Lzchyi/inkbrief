"""Licensed circuit outlines rendered as lightweight Pillow polylines."""

from __future__ import annotations

import json
import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from types import MappingProxyType
from typing import Any

from PIL import Image, ImageDraw

Point = tuple[float, float]
Box = tuple[int, int, int, int]

SOURCE_REPOSITORY = "https://github.com/bacinger/f1-circuits"
SOURCE_COMMIT = "432a253890199d0908e7f82044c52de8268cc056"
SOURCE_DATA_SHA256 = "a0c8dfb3109a9181d096985eaa30bd692595eae9125b5b8686744600b24621b5"
SOURCE_ATTRIBUTION = "Circuit coordinates © 2019–2025 Tomislav Bacinger, MIT License"

_DEFAULT_DATA_PATH = (
    Path(__file__).resolve().parents[3] / "assets" / "tracks" / "f1-circuits.geojson"
)

# Jolpica/Ergast circuitId -> bacinger/f1-circuits feature ID. The first block is the complete
# 2026 Jolpica circuit list as returned on 2026-08-07; the remainder supports recent prior seasons.
JOLPICA_TO_SOURCE_ID: Mapping[str, str] = MappingProxyType(
    {
        "albert_park": "au-1953",
        "americas": "us-2012",
        "baku": "az-2016",
        "catalunya": "es-1991",
        "hungaroring": "hu-1986",
        "interlagos": "br-1940",
        "jeddah": "sa-2021",
        "losail": "qa-2004",
        "madring": "es-2026",
        "marina_bay": "sg-2008",
        "miami": "us-2022",
        "monaco": "mc-1929",
        "monza": "it-1922",
        "red_bull_ring": "at-1969",
        "rodriguez": "mx-1962",
        "sepang": "my-1999",
        "shanghai": "cn-2004",
        "silverstone": "gb-1948",
        "spa": "be-1925",
        "suzuka": "jp-1962",
        "vegas": "us-2023",
        "villeneuve": "ca-1978",
        "yas_marina": "ae-2009",
        "zandvoort": "nl-1948",
        "bahrain": "bh-2002",
        "estoril": "pt-1972",
        "galvez": "ar-1952",
        "hockenheimring": "de-1932",
        "imola": "it-1953",
        "indianapolis": "us-1909",
        "istanbul": "tr-2005",
        "jacarepagua": "br-1977",
        "kyalami": "za-1961",
        "magny_cours": "fr-1960",
        "mugello": "it-1914",
        "nurburgring": "de-1927",
        "portimao": "pt-2008",
        "ricard": "fr-1969",
        "sochi": "ru-2014",
        "watkins_glen": "us-1956",
    }
)

CURRENT_2026_JOLPICA_IDS = frozenset(
    {
        "albert_park",
        "americas",
        "baku",
        "catalunya",
        "hungaroring",
        "interlagos",
        "jeddah",
        "losail",
        "madring",
        "marina_bay",
        "miami",
        "monaco",
        "monza",
        "red_bull_ring",
        "rodriguez",
        "sepang",
        "shanghai",
        "silverstone",
        "spa",
        "suzuka",
        "vegas",
        "villeneuve",
        "yas_marina",
        "zandvoort",
    }
)

# Original generic loop for missing/unknown circuit IDs. It intentionally does not represent a
# real venue and is distributed under this project's licence.
_GENERIC_POINTS: tuple[Point, ...] = (
    (0.08, 0.58),
    (0.12, 0.32),
    (0.28, 0.14),
    (0.48, 0.22),
    (0.67, 0.10),
    (0.90, 0.25),
    (0.86, 0.49),
    (0.94, 0.74),
    (0.72, 0.90),
    (0.49, 0.78),
    (0.31, 0.92),
    (0.10, 0.79),
    (0.08, 0.58),
)


class TrackDataError(ValueError):
    """Raised when the licensed GeoJSON source is malformed or inconsistent."""


@dataclass(frozen=True, slots=True)
class TrackOutline:
    circuit_id: str
    name: str
    points: tuple[Point, ...]
    source_id: str | None
    attribution: str
    is_fallback: bool = False


@dataclass(frozen=True, slots=True)
class _SourceTrack:
    source_id: str
    name: str
    points: tuple[Point, ...]


def get_track_outline(
    circuit_id: str | None,
    *,
    data_path: str | Path | None = None,
) -> TrackOutline:
    """Resolve a Jolpica circuit ID, returning the original generic loop on any gap."""

    normalized_id = circuit_id.strip().lower() if isinstance(circuit_id, str) else "unknown"
    normalized_id = normalized_id or "unknown"
    source_id = JOLPICA_TO_SOURCE_ID.get(normalized_id)
    if source_id is None:
        return _generic_outline(normalized_id)

    path = Path(data_path) if data_path is not None else _DEFAULT_DATA_PATH
    try:
        source_track = load_source_tracks(path)[source_id]
    except (KeyError, OSError, TrackDataError):
        return _generic_outline(normalized_id)
    return TrackOutline(
        circuit_id=normalized_id,
        name=source_track.name,
        points=source_track.points,
        source_id=source_id,
        attribution=SOURCE_ATTRIBUTION,
    )


def draw_track(
    draw: ImageDraw.ImageDraw,
    box: Box,
    circuit_id: str | None,
    *,
    ink: int = 0,
    width: int = 4,
    padding: int = 8,
    data_path: str | Path | None = None,
) -> TrackOutline:
    """Draw a fitted, aspect-preserving monochrome circuit line into a Pillow canvas."""

    if width <= 0:
        raise ValueError("width must be positive")
    outline = get_track_outline(circuit_id, data_path=data_path)
    fitted = fit_points(outline.points, box, padding=padding)
    draw.line(fitted, fill=ink, width=width, joint="curve")
    return outline


def render_track(
    circuit_id: str | None,
    size: tuple[int, int],
    *,
    ink: int = 0,
    paper: int = 255,
    width: int = 4,
    padding: int = 8,
    data_path: str | Path | None = None,
) -> tuple[Image.Image, TrackOutline]:
    """Create a grayscale circuit image and return its provenance-bearing outline."""

    image_width, image_height = size
    if image_width <= 0 or image_height <= 0:
        raise ValueError("image dimensions must be positive")
    image = Image.new("L", size, paper)
    outline = draw_track(
        ImageDraw.Draw(image),
        (0, 0, image_width, image_height),
        circuit_id,
        ink=ink,
        width=width,
        padding=padding,
        data_path=data_path,
    )
    return image, outline


def fit_points(points: Sequence[Point], box: Box, *, padding: int = 0) -> tuple[Point, ...]:
    """Fit arbitrary Cartesian points into a box without changing their aspect ratio."""

    left, top, right, bottom = box
    if right <= left or bottom <= top:
        raise ValueError("box must have positive dimensions")
    if padding < 0 or padding * 2 >= min(right - left, bottom - top):
        raise ValueError("padding must leave a positive drawing area")
    if len(points) < 2:
        raise ValueError("at least two points are required")

    xs = [point[0] for point in points]
    ys = [point[1] for point in points]
    if any(not math.isfinite(value) for value in (*xs, *ys)):
        raise ValueError("track points must be finite")
    source_width = max(xs) - min(xs)
    source_height = max(ys) - min(ys)
    if source_width <= 0 or source_height <= 0:
        raise ValueError("track points must span both axes")

    available_width = right - left - padding * 2
    available_height = bottom - top - padding * 2
    scale = min(available_width / source_width, available_height / source_height)
    drawn_width = source_width * scale
    drawn_height = source_height * scale
    offset_x = left + padding + (available_width - drawn_width) / 2
    offset_y = top + padding + (available_height - drawn_height) / 2
    return tuple(
        (
            offset_x + (x - min(xs)) * scale,
            offset_y + (y - min(ys)) * scale,
        )
        for x, y in points
    )


@lru_cache(maxsize=8)
def load_source_tracks(data_path: str | Path = _DEFAULT_DATA_PATH) -> Mapping[str, _SourceTrack]:
    """Load and validate the pinned source dataset, keyed by its stable feature IDs."""

    path = Path(data_path)
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise TrackDataError("circuit GeoJSON is not valid JSON") from exc
    if not isinstance(raw, dict) or raw.get("type") != "FeatureCollection":
        raise TrackDataError("circuit data must be a GeoJSON FeatureCollection")
    features = raw.get("features")
    if not isinstance(features, list):
        raise TrackDataError("circuit FeatureCollection must contain a feature list")

    tracks: dict[str, _SourceTrack] = {}
    for feature in features:
        track = _parse_feature(feature)
        if track.source_id in tracks:
            raise TrackDataError(f"duplicate circuit source ID: {track.source_id}")
        tracks[track.source_id] = track
    if not tracks:
        raise TrackDataError("circuit dataset is empty")
    return MappingProxyType(tracks)


def _parse_feature(feature: Any) -> _SourceTrack:
    if not isinstance(feature, dict) or feature.get("type") != "Feature":
        raise TrackDataError("every circuit entry must be a GeoJSON Feature")
    properties = feature.get("properties")
    geometry = feature.get("geometry")
    if not isinstance(properties, dict) or not isinstance(geometry, dict):
        raise TrackDataError("circuit feature is missing properties or geometry")
    source_id = properties.get("id")
    name = properties.get("Name")
    if not isinstance(source_id, str) or not source_id or not isinstance(name, str) or not name:
        raise TrackDataError("circuit feature requires string id and Name properties")
    if geometry.get("type") != "LineString":
        raise TrackDataError(f"circuit {source_id} must use LineString geometry")
    coordinates = geometry.get("coordinates")
    if not isinstance(coordinates, list) or len(coordinates) < 3:
        raise TrackDataError(f"circuit {source_id} has insufficient coordinates")
    points = _project_coordinates(coordinates, source_id=source_id)
    return _SourceTrack(source_id=source_id, name=name, points=points)


def _project_coordinates(coordinates: list[Any], *, source_id: str) -> tuple[Point, ...]:
    geographic_points: list[Point] = []
    for coordinate in coordinates:
        if (
            not isinstance(coordinate, list)
            or len(coordinate) < 2
            or isinstance(coordinate[0], bool)
            or isinstance(coordinate[1], bool)
            or not isinstance(coordinate[0], (int, float))
            or not isinstance(coordinate[1], (int, float))
        ):
            raise TrackDataError(f"circuit {source_id} contains an invalid coordinate")
        longitude, latitude = float(coordinate[0]), float(coordinate[1])
        if not math.isfinite(longitude) or not math.isfinite(latitude):
            raise TrackDataError(f"circuit {source_id} contains a non-finite coordinate")
        geographic_points.append((longitude, latitude))

    mean_latitude_radians = math.radians(
        sum(latitude for _, latitude in geographic_points) / len(geographic_points)
    )
    longitude_scale = math.cos(mean_latitude_radians)
    return tuple(
        (longitude * longitude_scale, -latitude) for longitude, latitude in geographic_points
    )


def _generic_outline(circuit_id: str) -> TrackOutline:
    return TrackOutline(
        circuit_id=circuit_id,
        name="Circuit outline unavailable",
        points=_GENERIC_POINTS,
        source_id=None,
        attribution="Original generic fallback, Kindle Brief project",
        is_fallback=True,
    )
