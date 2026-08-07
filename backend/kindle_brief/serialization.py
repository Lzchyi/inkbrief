"""Small, deterministic JSON helpers shared by caches and release builders."""

from __future__ import annotations

import json
import math
from collections.abc import Mapping, Sequence
from dataclasses import fields, is_dataclass
from datetime import UTC, date, datetime, time
from enum import Enum
from pathlib import Path
from typing import Any, TypeAlias, cast

JSONScalar: TypeAlias = None | bool | int | float | str
JSONValue: TypeAlias = JSONScalar | list["JSONValue"] | dict[str, "JSONValue"]


class SerializationError(ValueError):
    """Raised when a value cannot be represented safely as JSON."""


def require_aware_utc(value: datetime, *, field_name: str = "datetime") -> datetime:
    """Return an aware datetime normalized to UTC, rejecting naive values."""

    if value.tzinfo is None or value.utcoffset() is None:
        raise SerializationError(f"{field_name} must be timezone-aware")
    return value.astimezone(UTC)


def datetime_to_json(value: datetime) -> str:
    """Serialize an aware datetime using RFC 3339's compact UTC suffix."""

    normalized = require_aware_utc(value)
    return normalized.isoformat().replace("+00:00", "Z")


def datetime_from_json(value: object, *, field_name: str = "datetime") -> datetime:
    """Parse an RFC 3339 datetime and normalize it to UTC."""

    if not isinstance(value, str) or not value:
        raise SerializationError(f"{field_name} must be a non-empty RFC 3339 string")
    candidate = value[:-1] + "+00:00" if value.endswith("Z") else value
    try:
        parsed = datetime.fromisoformat(candidate)
    except ValueError as exc:
        raise SerializationError(f"{field_name} is not a valid RFC 3339 datetime") from exc
    return require_aware_utc(parsed, field_name=field_name)


def to_jsonable(value: Any) -> JSONValue:
    """Convert supported immutable application values to plain JSON values."""

    if value is None or isinstance(value, (bool, int, str)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise SerializationError("non-finite floats are not valid cache data")
        return value
    if isinstance(value, datetime):
        return datetime_to_json(value)
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, time):
        if value.tzinfo is not None:
            raise SerializationError("time values must not carry a timezone")
        return value.isoformat(timespec="minutes")
    if isinstance(value, Enum):
        return to_jsonable(value.value)
    if isinstance(value, Path):
        return str(value)
    if is_dataclass(value) and not isinstance(value, type):
        return {field.name: to_jsonable(getattr(value, field.name)) for field in fields(value)}
    if isinstance(value, Mapping):
        result: dict[str, JSONValue] = {}
        for key, item in value.items():
            if not isinstance(key, str):
                raise SerializationError("JSON object keys must be strings")
            result[key] = to_jsonable(item)
        return result
    if isinstance(value, (tuple, list)):
        return [to_jsonable(item) for item in value]
    raise SerializationError(f"unsupported JSON value: {type(value).__name__}")


def canonical_json_dumps(value: Any) -> str:
    """Encode a value reproducibly, suitable for hashing and atomic caches."""

    return json.dumps(
        to_jsonable(value),
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def json_loads(value: str) -> JSONValue:
    """Decode JSON while rejecting JavaScript's non-finite numeric extensions."""

    def reject_constant(constant: str) -> None:
        raise SerializationError(f"invalid JSON numeric constant: {constant}")

    try:
        decoded = json.loads(value, parse_constant=reject_constant)
    except json.JSONDecodeError as exc:
        raise SerializationError("invalid JSON") from exc
    return cast(JSONValue, decoded)


def _object(value: object, *, field_name: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping) or any(not isinstance(key, str) for key in value):
        raise SerializationError(f"{field_name} must be a string-keyed object")
    return cast(Mapping[str, object], value)


def _array(value: object, *, field_name: str) -> Sequence[object]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise SerializationError(f"{field_name} must be an array")
    return value


def _text(value: object, *, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise SerializationError(f"{field_name} must be a non-empty string")
    return value


def _number(value: object, *, field_name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise SerializationError(f"{field_name} must be a number")
    result = float(value)
    if not math.isfinite(result):
        raise SerializationError(f"{field_name} must be finite")
    return result


def _integer(value: object, *, field_name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise SerializationError(f"{field_name} must be an integer")
    return value


def _boolean(value: object, *, field_name: str) -> bool:
    if not isinstance(value, bool):
        raise SerializationError(f"{field_name} must be true or false")
    return value


def _optional_text(value: object, *, field_name: str) -> str | None:
    return None if value is None else _text(value, field_name=field_name)


def _optional_number(value: object, *, field_name: str) -> float | None:
    return None if value is None else _number(value, field_name=field_name)


def _optional_datetime(value: object, *, field_name: str) -> datetime | None:
    return None if value is None else datetime_from_json(value, field_name=field_name)


def _date_from_json(value: object, *, field_name: str) -> date:
    if not isinstance(value, str):
        raise SerializationError(f"{field_name} must be an ISO 8601 date")
    try:
        parsed = date.fromisoformat(value)
    except ValueError as exc:
        raise SerializationError(f"{field_name} must be an ISO 8601 date") from exc
    return parsed


def source_status_from_jsonable(value: object) -> Any:
    """Rebuild a :class:`SourceStatus` from cache-safe JSON data."""

    from .models import SourceStatus

    raw = _object(value, field_name="source status")
    return SourceStatus(
        source=_text(raw.get("source"), field_name="source status.source"),
        fetched_at=datetime_from_json(raw.get("fetched_at"), field_name="source status.fetched_at"),
        stale=_boolean(raw.get("stale"), field_name="source status.stale"),
        error=_optional_text(raw.get("error"), field_name="source status.error"),
        attribution=_optional_text(raw.get("attribution"), field_name="source status.attribution"),
        license_url=_optional_text(raw.get("license_url"), field_name="source status.license_url"),
    )


def hourly_forecast_from_jsonable(value: object) -> Any:
    from .models import HourlyForecast

    raw = _object(value, field_name="hourly forecast")
    return HourlyForecast(
        timestamp=datetime_from_json(raw.get("timestamp"), field_name="hourly forecast.timestamp"),
        temperature_c=_number(raw.get("temperature_c"), field_name="hourly forecast.temperature_c"),
        condition_code=_text(
            raw.get("condition_code"), field_name="hourly forecast.condition_code"
        ),
        condition_text=_text(
            raw.get("condition_text"), field_name="hourly forecast.condition_text"
        ),
        rain_probability_pct=_number(
            raw.get("rain_probability_pct"),
            field_name="hourly forecast.rain_probability_pct",
        ),
        cloud_cover_pct=_number(
            raw.get("cloud_cover_pct"), field_name="hourly forecast.cloud_cover_pct"
        ),
    )


def weather_snapshot_from_jsonable(value: object) -> Any:
    """Rebuild a validated :class:`WeatherSnapshot` from JSON data."""

    from .models import WeatherSnapshot

    raw = _object(value, field_name="weather snapshot")
    hourly = _array(raw.get("hourly"), field_name="weather snapshot.hourly")
    return WeatherSnapshot(
        observed_at=datetime_from_json(
            raw.get("observed_at"), field_name="weather snapshot.observed_at"
        ),
        temperature_c=_number(
            raw.get("temperature_c"), field_name="weather snapshot.temperature_c"
        ),
        condition_code=_text(
            raw.get("condition_code"), field_name="weather snapshot.condition_code"
        ),
        condition_text=_text(
            raw.get("condition_text"), field_name="weather snapshot.condition_text"
        ),
        high_c=_number(raw.get("high_c"), field_name="weather snapshot.high_c"),
        low_c=_number(raw.get("low_c"), field_name="weather snapshot.low_c"),
        humidity_pct=_number(raw.get("humidity_pct"), field_name="weather snapshot.humidity_pct"),
        rain_probability_pct=_number(
            raw.get("rain_probability_pct"),
            field_name="weather snapshot.rain_probability_pct",
        ),
        status=source_status_from_jsonable(raw.get("status")),
        feels_like_c=_optional_number(
            raw.get("feels_like_c"), field_name="weather snapshot.feels_like_c"
        ),
        wind_kph=_optional_number(raw.get("wind_kph"), field_name="weather snapshot.wind_kph"),
        uv_index=_optional_number(raw.get("uv_index"), field_name="weather snapshot.uv_index"),
        cloud_cover_pct=_optional_number(
            raw.get("cloud_cover_pct"), field_name="weather snapshot.cloud_cover_pct"
        ),
        hourly=tuple(hourly_forecast_from_jsonable(item) for item in hourly),
        wind_direction_deg=_optional_number(
            raw.get("wind_direction_deg"),
            field_name="weather snapshot.wind_direction_deg",
        ),
        visibility_km=_optional_number(
            raw.get("visibility_km"), field_name="weather snapshot.visibility_km"
        ),
        precipitation_mm=_optional_number(
            raw.get("precipitation_mm"),
            field_name="weather snapshot.precipitation_mm",
        ),
    )


def astronomy_snapshot_from_jsonable(value: object) -> Any:
    from .models import AstronomySnapshot

    raw = _object(value, field_name="astronomy snapshot")
    return AstronomySnapshot(
        calculated_at=datetime_from_json(
            raw.get("calculated_at"), field_name="astronomy snapshot.calculated_at"
        ),
        sunrise=datetime_from_json(raw.get("sunrise"), field_name="astronomy snapshot.sunrise"),
        sunset=datetime_from_json(raw.get("sunset"), field_name="astronomy snapshot.sunset"),
        phase_name=_text(raw.get("phase_name"), field_name="astronomy snapshot.phase_name"),
        phase_fraction=_number(
            raw.get("phase_fraction"), field_name="astronomy snapshot.phase_fraction"
        ),
        illumination_pct=_number(
            raw.get("illumination_pct"), field_name="astronomy snapshot.illumination_pct"
        ),
        status=source_status_from_jsonable(raw.get("status")),
        moonrise=_optional_datetime(raw.get("moonrise"), field_name="astronomy snapshot.moonrise"),
        moonset=_optional_datetime(raw.get("moonset"), field_name="astronomy snapshot.moonset"),
        best_sky_start=_optional_datetime(
            raw.get("best_sky_start"), field_name="astronomy snapshot.best_sky_start"
        ),
        best_sky_end=_optional_datetime(
            raw.get("best_sky_end"), field_name="astronomy snapshot.best_sky_end"
        ),
        stargazing_rating=_text(
            raw.get("stargazing_rating"),
            field_name="astronomy snapshot.stargazing_rating",
        ),
    )


def lunar_date_from_jsonable(value: object) -> Any:
    from .models import LunarDate

    raw = _object(value, field_name="lunar date")
    return LunarDate(
        gregorian_date=_date_from_json(
            raw.get("gregorian_date"), field_name="lunar date.gregorian_date"
        ),
        display_text=_text(raw.get("display_text"), field_name="lunar date.display_text"),
    )


def f1_session_from_jsonable(value: object) -> Any:
    from .models import F1Session

    raw = _object(value, field_name="F1 session")
    return F1Session(
        name=_text(raw.get("name"), field_name="F1 session.name"),
        starts_at=datetime_from_json(raw.get("starts_at"), field_name="F1 session.starts_at"),
        ends_at=_optional_datetime(raw.get("ends_at"), field_name="F1 session.ends_at"),
    )


def standing_from_jsonable(value: object) -> Any:
    from .models import Standing

    raw = _object(value, field_name="standing")
    return Standing(
        position=_integer(raw.get("position"), field_name="standing.position"),
        code=_text(raw.get("code"), field_name="standing.code"),
        name=_text(raw.get("name"), field_name="standing.name"),
        points=_number(raw.get("points"), field_name="standing.points"),
    )


def f1_snapshot_from_jsonable(value: object) -> Any:
    """Rebuild a validated :class:`F1Snapshot` from JSON data."""

    from .models import F1Snapshot

    raw = _object(value, field_name="F1 snapshot")
    sessions = _array(raw.get("sessions"), field_name="F1 snapshot.sessions")
    drivers = _array(raw.get("driver_standings"), field_name="F1 snapshot.driver_standings")
    constructors = _array(
        raw.get("constructor_standings"),
        field_name="F1 snapshot.constructor_standings",
    )
    return F1Snapshot(
        season=_integer(raw.get("season"), field_name="F1 snapshot.season"),
        round_number=_integer(raw.get("round_number"), field_name="F1 snapshot.round_number"),
        event_name=_text(raw.get("event_name"), field_name="F1 snapshot.event_name"),
        circuit_name=_text(raw.get("circuit_name"), field_name="F1 snapshot.circuit_name"),
        sessions=tuple(f1_session_from_jsonable(item) for item in sessions),
        driver_standings=tuple(standing_from_jsonable(item) for item in drivers),
        constructor_standings=tuple(standing_from_jsonable(item) for item in constructors),
        status=source_status_from_jsonable(raw.get("status")),
        circuit_id=_optional_text(raw.get("circuit_id"), field_name="F1 snapshot.circuit_id"),
    )


def article_from_jsonable(value: object) -> Any:
    from .models import Article
    from .news.normalize import repair_mojibake

    raw = _object(value, field_name="article")
    return Article(
        article_id=_text(raw.get("article_id"), field_name="article.article_id"),
        title=repair_mojibake(_text(raw.get("title"), field_name="article.title")),
        url=_text(raw.get("url"), field_name="article.url"),
        source=_text(raw.get("source"), field_name="article.source"),
        category=_text(raw.get("category"), field_name="article.category"),
        fetched_at=datetime_from_json(raw.get("fetched_at"), field_name="article.fetched_at"),
        published_at=_optional_datetime(raw.get("published_at"), field_name="article.published_at"),
        excerpt=(repair_mojibake(raw["excerpt"]) if isinstance(raw.get("excerpt"), str) else ""),
    )


def articles_from_jsonable(value: object) -> tuple[Any, ...]:
    raw = _array(value, field_name="articles")
    return tuple(article_from_jsonable(item) for item in raw)


def brief_story_from_jsonable(value: object) -> Any:
    from .models import BriefStory
    from .news.normalize import repair_mojibake

    raw = _object(value, field_name="brief story")
    article_ids = _array(raw.get("article_ids"), field_name="brief story.article_ids")
    sources = _array(raw.get("sources", ()), field_name="brief story.sources")
    return BriefStory(
        headline=repair_mojibake(_text(raw.get("headline"), field_name="brief story.headline")),
        summary=repair_mojibake(_text(raw.get("summary"), field_name="brief story.summary")),
        why_it_matters=repair_mojibake(
            _text(raw.get("why_it_matters"), field_name="brief story.why_it_matters")
        ),
        article_ids=tuple(
            _text(item, field_name="brief story.article_ids[]") for item in article_ids
        ),
        sources=tuple(_text(item, field_name="brief story.sources[]") for item in sources),
    )


def brief_stories_from_jsonable(value: object) -> tuple[Any, ...]:
    raw = _array(value, field_name="brief stories")
    return tuple(brief_story_from_jsonable(item) for item in raw)


def dashboard_snapshot_from_jsonable(value: object) -> Any:
    """Rebuild and revalidate an entire cached dashboard snapshot."""

    from .models import DashboardSnapshot

    raw = _object(value, field_name="dashboard snapshot")
    weather = raw.get("weather")
    astronomy = raw.get("astronomy")
    f1 = raw.get("f1")
    return DashboardSnapshot(
        generated_at=datetime_from_json(
            raw.get("generated_at"), field_name="dashboard snapshot.generated_at"
        ),
        timezone=_text(raw.get("timezone"), field_name="dashboard snapshot.timezone"),
        location_name=_text(
            raw.get("location_name"), field_name="dashboard snapshot.location_name"
        ),
        lunar_date=lunar_date_from_jsonable(raw.get("lunar_date")),
        weather=None if weather is None else weather_snapshot_from_jsonable(weather),
        astronomy=(None if astronomy is None else astronomy_snapshot_from_jsonable(astronomy)),
        f1=None if f1 is None else f1_snapshot_from_jsonable(f1),
        headlines=articles_from_jsonable(raw.get("headlines")),
        morning_brief=brief_stories_from_jsonable(raw.get("morning_brief")),
        degraded=_boolean(raw.get("degraded", False), field_name="dashboard snapshot.degraded"),
    )


def dashboard_snapshot_from_json(value: str) -> Any:
    return dashboard_snapshot_from_jsonable(json_loads(value))
