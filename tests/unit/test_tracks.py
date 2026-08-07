import hashlib
from pathlib import Path

import pytest
from kindle_brief.renderer.tracks import (
    ACTIVE_2026_JOLPICA_IDS,
    JOLPICA_2026_CIRCUIT_INVENTORY_IDS,
    JOLPICA_TO_SOURCE_ID,
    SOURCE_DATA_SHA256,
    TrackDataError,
    fit_points,
    get_track_outline,
    load_source_tracks,
    render_track,
)
from PIL import Image

TRACK_ASSETS = Path(__file__).resolve().parents[2] / "assets" / "tracks"
TRACK_DATA = TRACK_ASSETS / "f1-circuits.geojson"


def test_pinned_dataset_checksum_and_license_are_preserved() -> None:
    assert hashlib.sha256(TRACK_DATA.read_bytes()).hexdigest() == SOURCE_DATA_SHA256
    license_text = (TRACK_ASSETS / "LICENSE.f1-circuits.md").read_text(encoding="utf-8")
    assert "Copyright (c) 2019-2025 Tomislav Bacinger" in license_text
    assert "Permission is hereby granted" in license_text


def test_2026_jolpica_inventory_and_active_ids_resolve_to_licensed_tracks() -> None:
    source_tracks = load_source_tracks(TRACK_DATA)

    assert len(JOLPICA_2026_CIRCUIT_INVENTORY_IDS) == 24
    assert len(ACTIVE_2026_JOLPICA_IDS) == 23
    assert JOLPICA_2026_CIRCUIT_INVENTORY_IDS - {"jeddah"} == ACTIVE_2026_JOLPICA_IDS
    assert JOLPICA_TO_SOURCE_ID.keys() >= JOLPICA_2026_CIRCUIT_INVENTORY_IDS
    assert source_tracks.keys() >= set(JOLPICA_TO_SOURCE_ID.values())
    mapped_ids = {JOLPICA_TO_SOURCE_ID[item] for item in JOLPICA_2026_CIRCUIT_INVENTORY_IDS}
    assert source_tracks.keys() >= mapped_ids
    assert all(
        not get_track_outline(item).is_fallback for item in JOLPICA_2026_CIRCUIT_INVENTORY_IDS
    )


def test_known_track_uses_real_coordinates_and_provenance() -> None:
    outline = get_track_outline("madring")

    assert outline.name == "Circuito de Madring"
    assert outline.source_id == "es-2026"
    assert len(outline.points) > 100
    assert outline.points[0] == outline.points[-1]
    assert "MIT License" in outline.attribution


def test_unknown_track_uses_original_generic_fallback() -> None:
    outline = get_track_outline("future_unknown_circuit")

    assert outline.is_fallback is True
    assert outline.source_id is None
    assert outline.points[0] == outline.points[-1]
    assert "generic fallback" in outline.attribution


def test_render_track_returns_scalable_monochrome_art(tmp_path: Path) -> None:
    image, outline = render_track("suzuka", (320, 180), width=5, padding=12)

    assert image.mode == "L"
    assert image.size == (320, 180)
    assert image.getbbox() == (0, 0, 320, 180)
    assert image.getextrema() == (0, 255)
    assert outline.is_fallback is False

    output = tmp_path / "suzuka.png"
    image.save(output)
    assert Image.open(output).size == (320, 180)


def test_fit_points_centres_shape_and_preserves_aspect() -> None:
    fitted = fit_points(((0.0, 0.0), (2.0, 0.0), (2.0, 1.0), (0.0, 0.0)), (0, 0, 100, 100))
    xs = [point[0] for point in fitted]
    ys = [point[1] for point in fitted]

    assert max(xs) - min(xs) == pytest.approx(100)
    assert max(ys) - min(ys) == pytest.approx(50)
    assert min(ys) == pytest.approx(25)


def test_malformed_dataset_is_detectable_and_renderer_falls_back(tmp_path: Path) -> None:
    malformed = tmp_path / "tracks.geojson"
    malformed.write_text('{"type":"FeatureCollection","features":"bad"}', encoding="utf-8")

    with pytest.raises(TrackDataError):
        load_source_tracks(malformed)
    assert get_track_outline("spa", data_path=malformed).is_fallback is True
