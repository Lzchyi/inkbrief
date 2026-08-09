from dataclasses import FrozenInstanceError
from datetime import UTC, datetime, timedelta, timezone

import pytest
from kindle_brief.models import (
    BriefStory,
    DeviceProfile,
    HourlyForecast,
    PageArtifact,
    PageID,
    ReleaseManifest,
    SourceStatus,
    WeatherSnapshot,
)


def test_brief_story_keeps_only_unique_safe_https_article_urls() -> None:
    story = BriefStory(
        headline="A grounded headline",
        summary="A grounded summary.",
        why_it_matters="It affects readers.",
        article_ids=("article-1",),
        article_urls=(
            "https://example.com/story",
            "http://example.com/insecure",
            "javascript:alert(1)",
            "https://user:secret@example.com/private",
            "https://example.com/white space",
            "https://example.com:0/invalid-port",
            "https://example.com/story",
        ),
    )

    assert story.article_urls == ("https://example.com/story",)


def test_source_timestamp_is_normalized_to_utc_and_model_is_frozen() -> None:
    local_time = datetime(2026, 8, 8, 7, 0, tzinfo=timezone(timedelta(hours=8)))
    status = SourceStatus("Open-Meteo", local_time)

    assert status.fetched_at == datetime(2026, 8, 7, 23, 0, tzinfo=UTC)
    with pytest.raises(FrozenInstanceError):
        status.source = "changed"  # type: ignore[misc]


def test_naive_datetime_is_rejected() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        SourceStatus("Open-Meteo", datetime(2026, 8, 8, 7, 0))


def test_weather_validates_ranges() -> None:
    status = SourceStatus("Open-Meteo", datetime.now(UTC))

    with pytest.raises(ValueError, match="humidity_pct"):
        WeatherSnapshot(
            observed_at=datetime.now(UTC),
            temperature_c=29,
            condition_code="cloudy",
            condition_text="Mostly cloudy",
            high_c=32,
            low_c=25,
            humidity_pct=101,
            rain_probability_pct=68,
            status=status,
        )


def test_hourly_weather_is_utc_normalized_and_sorted() -> None:
    status = SourceStatus(
        "Open-Meteo",
        datetime.now(UTC),
        attribution="Open-Meteo",
        license_url="https://open-meteo.com/en/license",
    )
    first = HourlyForecast(
        timestamp=datetime(2026, 8, 8, 7, tzinfo=timezone(timedelta(hours=8))),
        temperature_c=28,
        condition_code="cloudy",
        condition_text="Cloudy",
        rain_probability_pct=40,
        cloud_cover_pct=80,
    )
    second = HourlyForecast(
        timestamp=datetime(2026, 8, 8, 0, tzinfo=UTC),
        temperature_c=29,
        condition_code="rain",
        condition_text="Rain",
        rain_probability_pct=70,
        cloud_cover_pct=90,
    )

    with pytest.raises(ValueError, match="sorted"):
        WeatherSnapshot(
            observed_at=datetime.now(UTC),
            temperature_c=29,
            condition_code="cloudy",
            condition_text="Mostly cloudy",
            high_c=32,
            low_c=25,
            humidity_pct=82,
            rain_probability_pct=68,
            status=status,
            hourly=(second, first),
        )


def test_manifest_requires_unique_pages_matching_profile() -> None:
    profile = DeviceProfile("test-profile", "Test Kindle", 100, 200)
    page = PageArtifact(PageID.HOME, "pages/home.png", "a" * 64, 1000, 100, 200)

    manifest = ReleaseManifest(
        schema_version=1,
        dashboard_version="0.1.0",
        release_id="b" * 64,
        generated_at=datetime.now(UTC),
        profile=profile,
        pages=(page,),
    )
    assert manifest.pages == (page,)

    with pytest.raises(ValueError, match="unique"):
        ReleaseManifest(
            schema_version=1,
            dashboard_version="0.1.0",
            release_id="b" * 64,
            generated_at=datetime.now(UTC),
            profile=profile,
            pages=(page, page),
        )
