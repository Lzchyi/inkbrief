from __future__ import annotations

import hashlib
import io
import json
import tarfile
from dataclasses import replace

from kindle_brief.demo import demo_snapshot
from kindle_brief.models import DeviceProfile, PageID
from kindle_brief.renderer.formatting import header_text
from kindle_brief.renderer.moon import moon_phase_image
from kindle_brief.renderer.release import build_release, render_pages, render_previews
from PIL import Image


def profile() -> DeviceProfile:
    return DeviceProfile("kt5", "Kindle 11th generation (2022)", 1072, 1448, model_code="KT5")


def dark_fraction(image: Image.Image) -> float:
    pixels = list(image.convert("L").get_flattened_data())
    return sum(value < 128 for value in pixels) / len(pixels)


def test_moon_rendering_tracks_new_quarter_and_full_phase() -> None:
    new = dark_fraction(moon_phase_image(180, 0))
    quarter = dark_fraction(moon_phase_image(180, 90))
    full = dark_fraction(moon_phase_image(180, 180))
    assert new > quarter > full


def test_all_pages_have_exact_profile_dimensions_and_centered_header() -> None:
    snapshot = demo_snapshot()
    images, metadata = render_pages(snapshot, profile())
    assert set(images) == set(PageID)
    for page_id, content in images.items():
        image = Image.open(io.BytesIO(content))
        assert image.size == (1072, 1448)
        assert image.mode == "L"
        page = metadata["pages"][page_id.value]
        assert page["layout"]["header"]["text"] == header_text(snapshot)
        assert abs(page["layout"]["header"]["center_x"] - 536) <= 1
        home_hotspots = [item for item in page["hotspots"] if item["name"] == "home"]
        assert len(home_hotspots) == 1
        home = home_hotspots[0]
        assert home["right"] < 180

    brief_layout = metadata["pages"][PageID.MORNING_BRIEF.value]["layout"]
    assert brief_layout["morning_brief_sources"][0] == "Source · Bernama"


def test_morning_brief_uses_stored_sources_after_headlines_rotate() -> None:
    original = demo_snapshot()
    stored_story = replace(original.morning_brief[0], sources=("Archived Publisher",))
    snapshot = replace(original, headlines=(), morning_brief=(stored_story,))

    _, metadata = render_pages(snapshot, profile())

    brief_layout = metadata["pages"][PageID.MORNING_BRIEF.value]["layout"]
    assert brief_layout["morning_brief_sources"] == ["Source · Archived Publisher"]


def test_previews_use_required_filenames(tmp_path) -> None:
    paths = render_previews(demo_snapshot(), profile(), tmp_path)
    assert {path.name for path in paths} == {
        "home.png",
        "weather.png",
        "f1.png",
        "morning-brief.png",
        "headlines.png",
    }
    assert (tmp_path / "hotspots.json").is_file()


def test_release_bundle_is_content_addressed_and_verified(tmp_path) -> None:
    manifest = build_release(demo_snapshot(), profile(), tmp_path)
    current_path = tmp_path / "profiles/kt5/current.json"
    current = json.loads(current_path.read_text(encoding="utf-8"))
    assert current["release_id"] == manifest.release_id
    assert current["profile_id"] == "kt5"
    assert current["model_code"] == "KT5"
    release_directory = current_path.parent / "releases" / manifest.release_id
    manifest_path = release_directory / "manifest.json"
    sums_path = release_directory / "SHA256SUMS"
    assert hashlib.sha256(manifest_path.read_bytes()).hexdigest() == current["manifest_sha256"]
    assert hashlib.sha256(sums_path.read_bytes()).hexdigest() == current["sha256sums_sha256"]
    manifest_payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest_payload["profile_id"] == "kt5"
    assert manifest_payload["model_code"] == "KT5"
    assert len(sums_path.read_text(encoding="utf-8").splitlines()) == 5
    bundle_path = current_path.parent / current["bundle"]
    assert hashlib.sha256(bundle_path.read_bytes()).hexdigest() == current["bundle_sha256"]
    with tarfile.open(bundle_path, "r:gz") as archive:
        assert set(archive.getnames()) == {
            "SHA256SUMS",
            "hotspots.json",
            "manifest.json",
            "snapshot.json",
            "pages/home.png",
            "pages/weather.png",
            "pages/f1.png",
            "pages/morning-brief.png",
            "pages/headlines.png",
        }
