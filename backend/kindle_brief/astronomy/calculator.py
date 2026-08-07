"""Astronomy Engine calculations for the weather-and-sky dashboard."""

from __future__ import annotations

import math
from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from astronomy import (
    Body,
    Direction,
    Equator,
    Horizon,
    Illumination,
    MoonPhase,
    Observer,
    Refraction,
    SearchAltitude,
    SearchRiseSet,
    Time,
)

from kindle_brief.models import AstronomySnapshot, SourceStatus

ASTRONOMY_ATTRIBUTION = "Astronomy calculations by Astronomy Engine"
DEFAULT_TIMEZONE = "Asia/Kuala_Lumpur"
_ASTRONOMY_LICENSE_URL = "https://github.com/cosinekitty/astronomy/blob/master/LICENSE"


class AstronomyCalculationError(ValueError):
    """Raised when a complete local-day astronomy snapshot cannot be calculated."""


def _finite(value: float, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise AstronomyCalculationError(f"{field} must be a finite number")
    return float(value)


def _percentage(value: float | None, field: str) -> float | None:
    if value is None:
        return None
    result = _finite(value, field)
    if not 0 <= result <= 100:
        raise AstronomyCalculationError(f"{field} must be between 0 and 100")
    return result


def _zone(name: str) -> ZoneInfo:
    try:
        return ZoneInfo(name)
    except ZoneInfoNotFoundError as exc:
        raise AstronomyCalculationError(f"unknown timezone: {name}") from exc


def _to_astro_time(value: datetime) -> Time:
    if value.tzinfo is None or value.utcoffset() is None:
        raise AstronomyCalculationError("astronomy datetimes must be timezone-aware")
    utc = value.astimezone(UTC)
    seconds = utc.second + utc.microsecond / 1_000_000
    return Time.Make(utc.year, utc.month, utc.day, utc.hour, utc.minute, seconds)


def _from_astro_time(value: Time | None) -> datetime | None:
    if value is None:
        return None
    return value.Utc().replace(tzinfo=UTC)


def _rise_set_in_window(
    body: Body,
    direction: Direction,
    observer: Observer,
    start: datetime,
    end: datetime,
) -> datetime | None:
    days = (end - start).total_seconds() / 86_400
    event = _from_astro_time(SearchRiseSet(body, observer, direction, _to_astro_time(start), days))
    return event if event is not None and start <= event < end else None


def _altitude_event_in_window(
    body: Body,
    direction: Direction,
    altitude: float,
    observer: Observer,
    start: datetime,
    end: datetime,
) -> datetime | None:
    days = (end - start).total_seconds() / 86_400
    event = _from_astro_time(
        SearchAltitude(body, observer, direction, _to_astro_time(start), days, altitude)
    )
    return event if event is not None and start <= event < end else None


def _moon_is_above_horizon(observer: Observer, moment: datetime) -> bool:
    astro_time = _to_astro_time(moment)
    equatorial = Equator(Body.Moon, astro_time, observer, True, True)
    horizontal = Horizon(
        astro_time,
        observer,
        equatorial.ra,
        equatorial.dec,
        Refraction.Normal,
    )
    return horizontal.altitude > 0


def moon_phase_name(phase_fraction: float) -> str:
    """Map a lunar-cycle fraction to the conventional eight phase names."""

    phase = _finite(phase_fraction, "phase_fraction")
    if not 0 <= phase < 1:
        raise AstronomyCalculationError("phase_fraction must be in [0, 1)")
    names = (
        "New Moon",
        "Waxing Crescent",
        "First Quarter",
        "Waxing Gibbous",
        "Full Moon",
        "Waning Gibbous",
        "Third Quarter",
        "Waning Crescent",
    )
    return names[int((phase * 8) + 0.5) % 8]


def rate_stargazing(
    *,
    cloud_cover_pct: float | None,
    precipitation_probability_pct: float | None,
    moon_illumination_pct: float,
    moon_up_fraction: float,
    visibility_m: float | None = None,
) -> str:
    """Return an explainable qualitative rating from weather and moonlight."""

    cloud_cover_pct = _percentage(cloud_cover_pct, "cloud_cover_pct")
    precipitation_probability_pct = _percentage(
        precipitation_probability_pct, "precipitation_probability_pct"
    )
    moon_illumination_pct = _percentage(moon_illumination_pct, "moon_illumination_pct")
    assert moon_illumination_pct is not None
    moon_up = _finite(moon_up_fraction, "moon_up_fraction")
    if not 0 <= moon_up <= 1:
        raise AstronomyCalculationError("moon_up_fraction must be between 0 and 1")
    if visibility_m is not None:
        visibility_m = _finite(visibility_m, "visibility_m")
        if visibility_m < 0:
            raise AstronomyCalculationError("visibility_m must not be negative")

    score = 100.0
    score -= 20.0 if cloud_cover_pct is None else cloud_cover_pct * 0.65
    score -= 10.0 if precipitation_probability_pct is None else precipitation_probability_pct * 0.30
    score -= moon_illumination_pct * moon_up * 0.25
    if visibility_m is not None:
        if visibility_m < 3_000:
            score -= 30
        elif visibility_m < 6_000:
            score -= 15
        elif visibility_m < 10_000:
            score -= 5

    if score >= 80:
        return "Excellent"
    if score >= 60:
        return "Good"
    if score >= 40:
        return "Fair"
    return "Poor"


def _best_night_window(
    observer: Observer, dusk: datetime, dawn: datetime
) -> tuple[datetime, datetime, float]:
    """Prefer the longest moonless part of astronomical night."""

    night_seconds = (dawn - dusk).total_seconds()
    moon_up_at_dusk = _moon_is_above_horizon(observer, dusk + timedelta(seconds=1))
    rise = _rise_set_in_window(Body.Moon, Direction.Rise, observer, dusk, dawn)
    setting = _rise_set_in_window(Body.Moon, Direction.Set, observer, dusk, dawn)

    if moon_up_at_dusk:
        moon_up_seconds = (
            night_seconds if setting is None else max(0.0, (setting - dusk).total_seconds())
        )
        if setting is not None and setting < dawn:
            return setting, dawn, min(1.0, moon_up_seconds / night_seconds)
    else:
        moon_up_seconds = 0.0 if rise is None else max(0.0, (dawn - rise).total_seconds())
        if rise is not None and dusk < rise:
            return dusk, rise, min(1.0, moon_up_seconds / night_seconds)

    return dusk, dawn, 1.0 if moon_up_at_dusk else 0.0


def calculate_astronomy(
    for_date: date,
    *,
    latitude: float,
    longitude: float,
    calculated_at: datetime,
    timezone: str = DEFAULT_TIMEZONE,
    elevation_m: float = 0.0,
    cloud_cover_pct: float | None = None,
    precipitation_probability_pct: float | None = None,
    visibility_m: float | None = None,
) -> AstronomySnapshot:
    """Calculate one civil day's Sun/Moon events and the following night window."""

    if isinstance(for_date, datetime) or not isinstance(for_date, date):
        raise TypeError("for_date must be a date")
    latitude = _finite(latitude, "latitude")
    longitude = _finite(longitude, "longitude")
    elevation_m = _finite(elevation_m, "elevation_m")
    if not -90 <= latitude <= 90:
        raise AstronomyCalculationError("latitude must be between -90 and 90")
    if not -180 <= longitude <= 180:
        raise AstronomyCalculationError("longitude must be between -180 and 180")
    if not -500 <= elevation_m <= 100_000:
        raise AstronomyCalculationError("elevation_m must be between -500 and 100000")
    if calculated_at.tzinfo is None or calculated_at.utcoffset() is None:
        raise AstronomyCalculationError("calculated_at must be timezone-aware")
    cloud_cover_pct = _percentage(cloud_cover_pct, "cloud_cover_pct")
    precipitation_probability_pct = _percentage(
        precipitation_probability_pct, "precipitation_probability_pct"
    )
    if visibility_m is not None:
        visibility_m = _finite(visibility_m, "visibility_m")
        if visibility_m < 0:
            raise AstronomyCalculationError("visibility_m must not be negative")

    local_zone = _zone(timezone)
    local_start = datetime.combine(for_date, time.min, tzinfo=local_zone)
    local_end = local_start + timedelta(days=1)
    observer = Observer(latitude, longitude, elevation_m)

    sunrise = _rise_set_in_window(Body.Sun, Direction.Rise, observer, local_start, local_end)
    sunset = _rise_set_in_window(Body.Sun, Direction.Set, observer, local_start, local_end)
    if sunrise is None or sunset is None:
        raise AstronomyCalculationError(
            f"sunrise or sunset is unavailable for {for_date.isoformat()} at this location"
        )
    moonrise = _rise_set_in_window(Body.Moon, Direction.Rise, observer, local_start, local_end)
    moonset = _rise_set_in_window(Body.Moon, Direction.Set, observer, local_start, local_end)

    local_noon = datetime.combine(for_date, time(hour=12), tzinfo=local_zone)
    phase_time = _to_astro_time(local_noon)
    phase_fraction = (MoonPhase(phase_time) % 360) / 360
    illumination_pct = Illumination(Body.Moon, phase_time).phase_fraction * 100

    night_limit = local_end + timedelta(hours=12)
    dusk = _altitude_event_in_window(
        Body.Sun, Direction.Set, -18, observer, local_noon, night_limit
    )
    dawn = (
        _altitude_event_in_window(
            Body.Sun, Direction.Rise, -18, observer, dusk + timedelta(seconds=1), night_limit
        )
        if dusk is not None
        else None
    )
    best_start: datetime | None = None
    best_end: datetime | None = None
    moon_up_fraction = 0.5
    if dusk is not None and dawn is not None and dusk < dawn:
        best_start, best_end, moon_up_fraction = _best_night_window(observer, dusk, dawn)

    rating = rate_stargazing(
        cloud_cover_pct=cloud_cover_pct,
        precipitation_probability_pct=precipitation_probability_pct,
        moon_illumination_pct=illumination_pct,
        moon_up_fraction=moon_up_fraction,
        visibility_m=visibility_m,
    )

    return AstronomySnapshot(
        calculated_at=calculated_at,
        sunrise=sunrise,
        sunset=sunset,
        phase_name=moon_phase_name(phase_fraction),
        phase_fraction=phase_fraction,
        illumination_pct=illumination_pct,
        status=SourceStatus(
            source="Astronomy Engine",
            fetched_at=calculated_at,
            attribution=ASTRONOMY_ATTRIBUTION,
            license_url=_ASTRONOMY_LICENSE_URL,
        ),
        moonrise=moonrise,
        moonset=moonset,
        best_sky_start=best_start,
        best_sky_end=best_end,
        stargazing_rating=rating,
    )
