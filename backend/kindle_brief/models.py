"""Immutable, provider-neutral domain models for dashboard generation."""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from datetime import date, datetime
from enum import StrEnum
from urllib.parse import urlsplit

from .serialization import require_aware_utc

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_IDENTIFIER_RE = re.compile(r"^[a-z0-9][a-z0-9._-]*$")


class PageID(StrEnum):
    HOME = "home"
    WEATHER = "weather"
    F1 = "f1"
    MORNING_BRIEF = "morning-brief"
    HEADLINES = "headlines"


def _required_text(name: str, value: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be non-empty")


def _finite(name: str, value: float) -> None:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f"{name} must be a finite number")


def _percentage(name: str, value: float) -> None:
    _finite(name, value)
    if not 0 <= value <= 100:
        raise ValueError(f"{name} must be between 0 and 100")


def _set_utc(instance: object, field_name: str, value: datetime | None) -> None:
    if value is not None:
        object.__setattr__(instance, field_name, require_aware_utc(value, field_name=field_name))


@dataclass(frozen=True, slots=True)
class DeviceProfile:
    profile_id: str
    model: str
    width: int
    height: int
    rotation: int = 0
    grayscale_bits: int = 4
    model_code: str | None = None

    def __post_init__(self) -> None:
        if not _IDENTIFIER_RE.fullmatch(self.profile_id):
            raise ValueError("profile_id must be a lowercase safe identifier")
        _required_text("model", self.model)
        if not 1 <= self.width <= 10_000 or not 1 <= self.height <= 10_000:
            raise ValueError("screen dimensions must be between 1 and 10000 pixels")
        if self.rotation not in {0, 90, 180, 270}:
            raise ValueError("rotation must be 0, 90, 180, or 270")
        if self.grayscale_bits not in {1, 2, 4, 8}:
            raise ValueError("grayscale_bits must be 1, 2, 4, or 8")
        if self.model_code is not None and not re.fullmatch(
            r"[A-Z0-9][A-Z0-9._-]*", self.model_code
        ):
            raise ValueError("model_code must be an uppercase safe identifier")


@dataclass(frozen=True, slots=True)
class SourceStatus:
    source: str
    fetched_at: datetime
    stale: bool = False
    error: str | None = None
    attribution: str | None = None
    license_url: str | None = None

    def __post_init__(self) -> None:
        _required_text("source", self.source)
        _set_utc(self, "fetched_at", self.fetched_at)
        if self.error is not None:
            _required_text("error", self.error)
        if self.attribution is not None:
            _required_text("attribution", self.attribution)
        if self.license_url is not None:
            parsed = urlsplit(self.license_url)
            if parsed.scheme not in {"http", "https"} or not parsed.hostname:
                raise ValueError("license_url must be an HTTP(S) URL")


@dataclass(frozen=True, slots=True)
class HourlyForecast:
    timestamp: datetime
    temperature_c: float
    condition_code: str
    condition_text: str
    rain_probability_pct: float
    cloud_cover_pct: float

    def __post_init__(self) -> None:
        _set_utc(self, "timestamp", self.timestamp)
        _finite("temperature_c", self.temperature_c)
        _required_text("condition_code", self.condition_code)
        _required_text("condition_text", self.condition_text)
        _percentage("rain_probability_pct", self.rain_probability_pct)
        _percentage("cloud_cover_pct", self.cloud_cover_pct)


@dataclass(frozen=True, slots=True)
class WeatherSnapshot:
    observed_at: datetime
    temperature_c: float
    condition_code: str
    condition_text: str
    high_c: float
    low_c: float
    humidity_pct: float
    rain_probability_pct: float
    status: SourceStatus
    feels_like_c: float | None = None
    wind_kph: float | None = None
    uv_index: float | None = None
    cloud_cover_pct: float | None = None
    hourly: tuple[HourlyForecast, ...] = ()
    wind_direction_deg: float | None = None
    visibility_km: float | None = None
    precipitation_mm: float | None = None

    def __post_init__(self) -> None:
        _set_utc(self, "observed_at", self.observed_at)
        _required_text("condition_code", self.condition_code)
        _required_text("condition_text", self.condition_text)
        for name in ("temperature_c", "high_c", "low_c"):
            _finite(name, getattr(self, name))
        if self.high_c < self.low_c:
            raise ValueError("high_c must not be lower than low_c")
        _percentage("humidity_pct", self.humidity_pct)
        _percentage("rain_probability_pct", self.rain_probability_pct)
        if self.feels_like_c is not None:
            _finite("feels_like_c", self.feels_like_c)
        if self.wind_kph is not None:
            _finite("wind_kph", self.wind_kph)
            if self.wind_kph < 0:
                raise ValueError("wind_kph must not be negative")
        if self.uv_index is not None:
            _finite("uv_index", self.uv_index)
            if self.uv_index < 0:
                raise ValueError("uv_index must not be negative")
        if self.cloud_cover_pct is not None:
            _percentage("cloud_cover_pct", self.cloud_cover_pct)
        object.__setattr__(self, "hourly", tuple(self.hourly))
        hourly_timestamps = [forecast.timestamp for forecast in self.hourly]
        if hourly_timestamps != sorted(hourly_timestamps):
            raise ValueError("hourly forecasts must be sorted chronologically")
        if len(hourly_timestamps) != len(set(hourly_timestamps)):
            raise ValueError("hourly forecast timestamps must be unique")
        if self.wind_direction_deg is not None:
            _finite("wind_direction_deg", self.wind_direction_deg)
            if not 0 <= self.wind_direction_deg < 360:
                raise ValueError("wind_direction_deg must be in [0, 360)")
        for name in ("visibility_km", "precipitation_mm"):
            value = getattr(self, name)
            if value is not None:
                _finite(name, value)
                if value < 0:
                    raise ValueError(f"{name} must not be negative")


@dataclass(frozen=True, slots=True)
class AstronomySnapshot:
    calculated_at: datetime
    sunrise: datetime
    sunset: datetime
    phase_name: str
    phase_fraction: float
    illumination_pct: float
    status: SourceStatus
    moonrise: datetime | None = None
    moonset: datetime | None = None
    best_sky_start: datetime | None = None
    best_sky_end: datetime | None = None
    stargazing_rating: str = "Fair"

    def __post_init__(self) -> None:
        for name in (
            "calculated_at",
            "sunrise",
            "sunset",
            "moonrise",
            "moonset",
            "best_sky_start",
            "best_sky_end",
        ):
            _set_utc(self, name, getattr(self, name))
        _required_text("phase_name", self.phase_name)
        _required_text("stargazing_rating", self.stargazing_rating)
        _finite("phase_fraction", self.phase_fraction)
        if not 0 <= self.phase_fraction < 1:
            raise ValueError("phase_fraction must be in [0, 1)")
        _percentage("illumination_pct", self.illumination_pct)
        if (self.best_sky_start is None) != (self.best_sky_end is None):
            raise ValueError("best sky window requires both a start and an end")


@dataclass(frozen=True, slots=True)
class LunarDate:
    gregorian_date: date
    display_text: str

    def __post_init__(self) -> None:
        _required_text("display_text", self.display_text)


@dataclass(frozen=True, slots=True)
class F1Session:
    name: str
    starts_at: datetime
    ends_at: datetime | None = None

    def __post_init__(self) -> None:
        _required_text("name", self.name)
        _set_utc(self, "starts_at", self.starts_at)
        _set_utc(self, "ends_at", self.ends_at)
        if self.ends_at is not None and self.ends_at <= self.starts_at:
            raise ValueError("session ends_at must be later than starts_at")


@dataclass(frozen=True, slots=True)
class Standing:
    position: int
    code: str
    name: str
    points: float

    def __post_init__(self) -> None:
        if self.position <= 0:
            raise ValueError("position must be positive")
        _required_text("code", self.code)
        _required_text("name", self.name)
        _finite("points", self.points)
        if self.points < 0:
            raise ValueError("points must not be negative")


@dataclass(frozen=True, slots=True)
class F1Snapshot:
    season: int
    round_number: int
    event_name: str
    circuit_name: str
    sessions: tuple[F1Session, ...]
    driver_standings: tuple[Standing, ...]
    constructor_standings: tuple[Standing, ...]
    status: SourceStatus
    circuit_id: str | None = None

    def __post_init__(self) -> None:
        if self.season < 1950 or self.round_number <= 0:
            raise ValueError("invalid F1 season or round")
        _required_text("event_name", self.event_name)
        _required_text("circuit_name", self.circuit_name)
        if self.circuit_id is not None and not _IDENTIFIER_RE.fullmatch(self.circuit_id):
            raise ValueError("circuit_id must be a lowercase safe identifier")
        object.__setattr__(self, "sessions", tuple(self.sessions))
        object.__setattr__(self, "driver_standings", tuple(self.driver_standings))
        object.__setattr__(self, "constructor_standings", tuple(self.constructor_standings))
        if tuple(sorted(self.sessions, key=lambda session: session.starts_at)) != self.sessions:
            raise ValueError("sessions must be sorted chronologically")


@dataclass(frozen=True, slots=True)
class Article:
    article_id: str
    title: str
    url: str
    source: str
    category: str
    fetched_at: datetime
    published_at: datetime | None = None
    excerpt: str = ""

    def __post_init__(self) -> None:
        for name in ("article_id", "title", "url", "source", "category"):
            _required_text(name, getattr(self, name))
        _set_utc(self, "fetched_at", self.fetched_at)
        _set_utc(self, "published_at", self.published_at)


@dataclass(frozen=True, slots=True)
class BriefStory:
    headline: str
    summary: str
    why_it_matters: str
    article_ids: tuple[str, ...]
    sources: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        for name in ("headline", "summary", "why_it_matters"):
            _required_text(name, getattr(self, name))
        object.__setattr__(self, "article_ids", tuple(self.article_ids))
        if not self.article_ids or any(not item.strip() for item in self.article_ids):
            raise ValueError("article_ids must contain at least one non-empty ID")
        sources = tuple(self.sources)
        if any(not isinstance(item, str) or not item.strip() for item in sources):
            raise ValueError("sources must contain only non-empty names")
        object.__setattr__(self, "sources", tuple(dict.fromkeys(sources)))


@dataclass(frozen=True, slots=True)
class DashboardSnapshot:
    generated_at: datetime
    timezone: str
    location_name: str
    lunar_date: LunarDate
    weather: WeatherSnapshot | None = None
    astronomy: AstronomySnapshot | None = None
    f1: F1Snapshot | None = None
    headlines: tuple[Article, ...] = ()
    morning_brief: tuple[BriefStory, ...] = ()
    degraded: bool = False

    def __post_init__(self) -> None:
        _set_utc(self, "generated_at", self.generated_at)
        _required_text("timezone", self.timezone)
        _required_text("location_name", self.location_name)
        if not isinstance(self.degraded, bool):
            raise ValueError("degraded must be true or false")
        object.__setattr__(self, "headlines", tuple(self.headlines))
        object.__setattr__(self, "morning_brief", tuple(self.morning_brief))


@dataclass(frozen=True, slots=True)
class PageArtifact:
    page_id: PageID
    path: str
    sha256: str
    byte_size: int
    width: int
    height: int

    def __post_init__(self) -> None:
        _required_text("path", self.path)
        if self.path.startswith("/") or ".." in self.path.split("/"):
            raise ValueError("path must be a safe relative path")
        if not _SHA256_RE.fullmatch(self.sha256):
            raise ValueError("sha256 must be a lowercase SHA-256 digest")
        if self.byte_size <= 0 or self.width <= 0 or self.height <= 0:
            raise ValueError("artifact size and dimensions must be positive")


@dataclass(frozen=True, slots=True)
class ReleaseManifest:
    schema_version: int
    dashboard_version: str
    release_id: str
    generated_at: datetime
    profile: DeviceProfile
    pages: tuple[PageArtifact, ...]

    def __post_init__(self) -> None:
        if self.schema_version <= 0:
            raise ValueError("schema_version must be positive")
        _required_text("dashboard_version", self.dashboard_version)
        if not _SHA256_RE.fullmatch(self.release_id):
            raise ValueError("release_id must be a lowercase SHA-256 digest")
        _set_utc(self, "generated_at", self.generated_at)
        object.__setattr__(self, "pages", tuple(self.pages))
        page_ids = [page.page_id for page in self.pages]
        if not self.pages or len(set(page_ids)) != len(page_ids):
            raise ValueError("manifest pages must be non-empty and unique")
        for page in self.pages:
            if page.width != self.profile.width or page.height != self.profile.height:
                raise ValueError("every page must match the device profile dimensions")
