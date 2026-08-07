from datetime import UTC, date, datetime
from zoneinfo import ZoneInfo

import pytest
from kindle_brief.astronomy import (
    AstronomyCalculationError,
    calculate_astronomy,
    moon_phase_name,
    rate_stargazing,
)

MYT = ZoneInfo("Asia/Kuala_Lumpur")


def test_calculates_kuala_lumpur_sun_moon_and_best_sky_window() -> None:
    target = date(2026, 8, 8)
    snapshot = calculate_astronomy(
        target,
        latitude=3.139,
        longitude=101.6869,
        calculated_at=datetime(2026, 8, 7, 23, tzinfo=UTC),
        cloud_cover_pct=20,
        precipitation_probability_pct=10,
        visibility_m=10_000,
    )

    sunrise = snapshot.sunrise.astimezone(MYT)
    sunset = snapshot.sunset.astimezone(MYT)
    assert sunrise.date() == target and sunrise.hour == 7
    assert sunset.date() == target and sunset.hour == 19
    assert snapshot.phase_name == "Waning Crescent"
    assert snapshot.phase_fraction == pytest.approx(0.826, abs=0.002)
    assert snapshot.illumination_pct == pytest.approx(27.1, abs=0.5)
    assert snapshot.moonrise is not None
    assert snapshot.moonset is not None
    assert snapshot.best_sky_start is not None
    assert snapshot.best_sky_end is not None
    assert snapshot.best_sky_start < snapshot.best_sky_end
    assert snapshot.stargazing_rating == "Excellent"
    assert snapshot.status.attribution == "Astronomy calculations by Astronomy Engine"


@pytest.mark.parametrize(
    ("fraction", "name"),
    (
        (0.0, "New Moon"),
        (0.25, "First Quarter"),
        (0.5, "Full Moon"),
        (0.75, "Third Quarter"),
        (0.99, "New Moon"),
    ),
)
def test_moon_phase_names(fraction: float, name: str) -> None:
    assert moon_phase_name(fraction) == name


def test_stargazing_rating_penalizes_cloud_rain_moonlight_and_haze() -> None:
    rating = rate_stargazing(
        cloud_cover_pct=95,
        precipitation_probability_pct=90,
        moon_illumination_pct=100,
        moon_up_fraction=1,
        visibility_m=2_000,
    )

    assert rating == "Poor"


def test_astronomy_rejects_invalid_coordinates() -> None:
    with pytest.raises(AstronomyCalculationError, match="latitude"):
        calculate_astronomy(
            date(2026, 8, 8),
            latitude=91,
            longitude=101.6869,
            calculated_at=datetime.now(UTC),
        )
