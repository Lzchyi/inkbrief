from __future__ import annotations

import hashlib
import io
import json
import tarfile
from dataclasses import replace
from datetime import UTC, datetime

from kindle_brief.demo import demo_snapshot
from kindle_brief.models import DeviceProfile, PageID
from kindle_brief.renderer import icons
from kindle_brief.renderer.formatting import clock, date_range, header_text, is_night
from kindle_brief.renderer.moon import moon_phase_image
from kindle_brief.renderer.release import build_release, render_pages, render_previews
from kindle_brief.renderer.theme import project_root
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


def test_moon_texture_stays_inside_one_aligned_disc() -> None:
    for angle in (0, 45, 90, 135, 180, 225, 270, 315):
        image = moon_phase_image(154, angle)
        assert all(image.getpixel(point) == 255 for point in ((0, 0), (153, 0), (0, 153)))


def test_custom_icon_assets_cover_weather_and_motorsport_states() -> None:
    assert icons.weather_icon_name("0", is_night=True) == "clear-night"
    assert icons.weather_icon_name("2", cloud_cover_pct=80) == "mostly-cloudy"
    assert icons.weather_icon_name("3", cloud_cover_pct=95) == "overcast"
    assert icons.weather_icon_name("1", wind_kph=45) == "windy"
    assert icons.weather_icon_name("3", visibility_km=3) == "haze"

    weather = icons.weather_asset("2", 66, cloud_cover_pct=80)
    assert weather.mode == "L"
    assert weather.size == (66, 66)
    assert weather.getextrema()[0] <= 5
    assert weather.getextrema()[1] == 255

    for name in (
        "helmet-compact",
        "helmet-compact-alt",
        "car-compact",
        "car-compact-alt",
        "calendar",
        "countdown",
        "trophy",
    ):
        asset = icons.motorsport_asset(name, 54)
        assert asset.mode == "L"
        assert asset.size == (54, 54)

    for name in ("moonrise", "moonset"):
        asset = icons.moon_horizon_asset(name, 76)
        assert asset.mode == "L"
        assert asset.size == (76, 76)


def test_every_cropped_icon_set_asset_is_present_and_readable() -> None:
    weather_names = (
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
    )
    for name in weather_names:
        assert icons.raster_asset(f"weather/icons/{name}.png", 32).size == (32, 32)

    moon_names = (
        "new-moon",
        "waxing-crescent",
        "first-quarter",
        "waxing-gibbous",
        "full-moon",
        "waning-gibbous",
        "last-quarter",
        "waning-crescent",
    )
    moon_dir = project_root() / "assets" / "moon" / "phases"
    for name in moon_names:
        with Image.open(moon_dir / f"{name}.png") as phase:
            assert phase.size == (512, 512)
            assert phase.mode == "RGBA"
    for name in ("moonrise", "moonset"):
        assert icons.moon_horizon_asset(name, 32).size == (32, 32)

    motorsport_names = (
        "helmet",
        "helmet-compact",
        "helmet-compact-alt",
        "car",
        "car-compact",
        "car-compact-alt",
        "checkered-flag",
        "calendar",
        "countdown",
        "trophy",
        "podium",
        "track",
    )
    for name in motorsport_names:
        assert icons.motorsport_asset(name, 32).size == (32, 32)


def test_night_detection_uses_the_astronomy_daylight_window() -> None:
    sunrise = datetime(2026, 8, 7, 23, 12, tzinfo=UTC)
    sunset = datetime(2026, 8, 8, 11, 23, tzinfo=UTC)

    assert not is_night(
        datetime(2026, 8, 7, 23, 30, tzinfo=UTC),
        "Asia/Kuala_Lumpur",
        sunrise=sunrise,
        sunset=sunset,
    )
    assert is_night(
        datetime(2026, 8, 7, 22, 30, tzinfo=UTC),
        "Asia/Kuala_Lumpur",
        sunrise=sunrise,
        sunset=sunset,
    )


def test_f1_dates_are_explicit_after_timezone_conversion() -> None:
    first = datetime(2026, 8, 21, 10, 30, tzinfo=UTC)
    last = datetime(2026, 8, 23, 13, 0, tzinfo=UTC)

    assert clock(first, "Asia/Kuala_Lumpur") == "18:30"
    assert clock(first, "Asia/Kuala_Lumpur", include_day=True) == "Fri 21 Aug · 18:30"
    assert date_range((first, last), "Asia/Kuala_Lumpur") == "21–23 Aug 2026"


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
