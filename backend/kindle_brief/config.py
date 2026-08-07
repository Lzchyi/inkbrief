"""Strict YAML configuration loading without environment-secret interpolation."""

from __future__ import annotations

import math
import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import time
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

_AI_PROVIDERS = {
    "fallback",
    "none",
    "gemini",
    "openrouter",
    "groq",
    "openai",
    "openai_compatible",
}
_ENV_NAME_RE = re.compile(r"^[A-Z][A-Z0-9_]*$")
_MAX_CONFIG_BYTES = 1_048_576


class ConfigError(ValueError):
    """Raised when a dashboard configuration is missing, unsafe, or invalid."""


def _safe_identifier(name: str, value: str) -> None:
    if not re.fullmatch(r"[a-z0-9][a-z0-9._-]*", value):
        raise ConfigError(f"{name} must be a lowercase safe identifier")


@dataclass(frozen=True, slots=True)
class LocationConfig:
    name: str
    timezone: str
    latitude: float | None = None
    longitude: float | None = None

    def __post_init__(self) -> None:
        _nonempty("location.name", self.name)
        _validate_timezone("location.timezone", self.timezone)
        if (self.latitude is None) != (self.longitude is None):
            raise ConfigError("location latitude and longitude must be provided together")
        if self.latitude is not None and not -90 <= self.latitude <= 90:
            raise ConfigError("location.latitude must be between -90 and 90")
        if self.longitude is not None and not -180 <= self.longitude <= 180:
            raise ConfigError("location.longitude must be between -180 and 180")


@dataclass(frozen=True, slots=True)
class FeedConfig:
    name: str
    url: str
    category: str
    enabled: bool = True

    def __post_init__(self) -> None:
        _nonempty("feed.name", self.name)
        _nonempty("feed.category", self.category)
        _validate_url("feed.url", self.url)


@dataclass(frozen=True, slots=True)
class DeviceConfig:
    profile: str

    def __post_init__(self) -> None:
        _safe_identifier("device.profile", self.profile)


@dataclass(frozen=True, slots=True)
class AIConfig:
    provider: str = "fallback"
    model: str | None = None
    credential_env: str | None = None
    max_stories: int = 8

    def __post_init__(self) -> None:
        if self.provider not in _AI_PROVIDERS:
            supported = ", ".join(sorted(_AI_PROVIDERS))
            raise ConfigError(f"ai.provider must be one of: {supported}")
        if self.model is not None:
            _nonempty("ai.model", self.model)
        if self.credential_env is not None and not _ENV_NAME_RE.fullmatch(self.credential_env):
            raise ConfigError("ai.credential_env must be an uppercase environment variable name")
        if not 1 <= self.max_stories <= 20:
            raise ConfigError("ai.max_stories must be between 1 and 20")


@dataclass(frozen=True, slots=True)
class RefreshConfig:
    dashboard_minutes: int = 60
    morning_brief_local_time: time = time(7, 0)
    request_timeout_seconds: int = 20
    max_stale_hours: int = 72

    def __post_init__(self) -> None:
        if not 15 <= self.dashboard_minutes <= 1_440:
            raise ConfigError("refresh.dashboard_minutes must be between 15 and 1440")
        if not 1 <= self.request_timeout_seconds <= 120:
            raise ConfigError("refresh.request_timeout_seconds must be between 1 and 120")
        if not 1 <= self.max_stale_hours <= 720:
            raise ConfigError("refresh.max_stale_hours must be between 1 and 720")

    @property
    def morning_brief_time(self) -> time:
        """Backward-compatible short name for the configured local wall time."""

        return self.morning_brief_local_time


@dataclass(frozen=True, slots=True)
class CategoryWeight:
    category: str
    weight: float

    def __post_init__(self) -> None:
        _nonempty("category", self.category)
        if not math.isfinite(self.weight) or self.weight < 0:
            raise ConfigError("category weights must be finite and non-negative")


@dataclass(frozen=True, slots=True)
class NewsConfig:
    max_age_hours: int = 36
    headline_limit: int = 15
    category_weights: tuple[CategoryWeight, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "category_weights", tuple(self.category_weights))
        if not 1 <= self.max_age_hours <= 720:
            raise ConfigError("news.max_age_hours must be between 1 and 720")
        if not 1 <= self.headline_limit <= 50:
            raise ConfigError("news.headline_limit must be between 1 and 50")
        _require_unique(
            "category weights",
            (item.category.casefold() for item in self.category_weights),
        )


@dataclass(frozen=True, slots=True)
class F1Config:
    enabled: bool = True
    top_drivers: int = 3
    top_constructors: int = 3

    def __post_init__(self) -> None:
        if not 1 <= self.top_drivers <= 10 or not 1 <= self.top_constructors <= 10:
            raise ConfigError("F1 standing counts must be between 1 and 10")


@dataclass(frozen=True, slots=True)
class PagesConfig:
    home: bool = True
    weather: bool = True
    f1: bool = True
    morning_brief: bool = True
    headlines: bool = True

    def __post_init__(self) -> None:
        enabled = (self.home, self.weather, self.f1, self.morning_brief, self.headlines)
        if not all(enabled):
            raise ConfigError("dashboard version 1 requires all five pages to be enabled")


@dataclass(frozen=True, slots=True)
class PublishingConfig:
    profile: str
    base_url: str | None = None

    def __post_init__(self) -> None:
        _safe_identifier("publishing.profile", self.profile)
        if self.base_url is not None:
            _validate_url("publishing.base_url", self.base_url)


@dataclass(frozen=True, slots=True)
class DashboardConfig:
    location: LocationConfig
    version: int = 1
    favorites: tuple[LocationConfig, ...] = ()
    feeds: tuple[FeedConfig, ...] = ()
    device: DeviceConfig = field(default_factory=lambda: DeviceConfig("kt5"))
    ai: AIConfig = field(default_factory=AIConfig)
    refresh: RefreshConfig = field(default_factory=RefreshConfig)
    news: NewsConfig = field(default_factory=NewsConfig)
    f1: F1Config = field(default_factory=F1Config)
    pages: PagesConfig = field(default_factory=PagesConfig)
    publishing: PublishingConfig = field(default_factory=lambda: PublishingConfig("kt5"))

    def __post_init__(self) -> None:
        object.__setattr__(self, "favorites", tuple(self.favorites))
        object.__setattr__(self, "feeds", tuple(self.feeds))
        if self.version != 1:
            raise ConfigError("config.version must be 1")
        if self.publishing.profile != self.device.profile:
            raise ConfigError("publishing.profile must match device.profile")
        _require_unique("favorite names", (item.name.casefold() for item in self.favorites))
        _require_unique("feed names", (item.name.casefold() for item in self.feeds))
        _require_unique("feed URLs", (item.url for item in self.feeds))

    @property
    def category_weights(self) -> tuple[CategoryWeight, ...]:
        """Expose news weights at the original convenient location."""

        return self.news.category_weights


def load_config(path: str | Path) -> DashboardConfig:
    """Load and validate a UTF-8 YAML configuration file."""

    config_path = Path(path)
    try:
        size = config_path.stat().st_size
    except OSError as exc:
        raise ConfigError(f"cannot read config: {config_path}") from exc
    if size > _MAX_CONFIG_BYTES:
        raise ConfigError("config file exceeds the 1 MiB safety limit")
    try:
        import yaml
    except ModuleNotFoundError as exc:
        raise ConfigError("PyYAML is required to load YAML configuration") from exc
    try:
        raw = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, yaml.YAMLError) as exc:
        raise ConfigError(f"cannot parse config: {config_path}") from exc
    return config_from_mapping(_mapping("config", raw))


def config_from_mapping(raw: Mapping[str, Any]) -> DashboardConfig:
    """Validate an already-decoded YAML mapping."""

    _reject_secret_fields(raw)
    _only_keys(
        "config",
        raw,
        {
            "version",
            "location",
            "favorites",
            "feeds",
            "device",
            "ai",
            "refresh",
            "news",
            "category_weights",
            "f1",
            "pages",
            "publishing",
        },
    )
    if "location" not in raw:
        raise ConfigError("config.location is required")

    location = _location(
        "location",
        _mapping("location", raw["location"]),
        default_timezone=None,
    )
    device = _device(_mapping("device", raw.get("device", {"profile": "kt5"})))
    favorites_raw = _list("favorites", raw.get("favorites", []))
    feeds_raw = _list("feeds", raw.get("feeds", []))
    news_raw = _mapping("news", raw.get("news", {}))
    if "category_weights" in raw and "category_weights" in news_raw:
        raise ConfigError("category_weights must be configured either at top level or under news")
    top_level_weights = raw.get("category_weights")
    if top_level_weights is not None:
        news_raw = dict(news_raw)
        news_raw["category_weights"] = top_level_weights

    return DashboardConfig(
        version=_integer("version", raw.get("version", 1)),
        location=location,
        favorites=tuple(
            _location(
                f"favorites[{index}]",
                _mapping(f"favorites[{index}]", item),
                default_timezone=location.timezone,
            )
            for index, item in enumerate(favorites_raw)
        ),
        feeds=tuple(
            _feed(f"feeds[{index}]", _mapping(f"feeds[{index}]", item))
            for index, item in enumerate(feeds_raw)
        ),
        device=device,
        ai=_ai(_mapping("ai", raw.get("ai", {}))),
        refresh=_refresh(_mapping("refresh", raw.get("refresh", {}))),
        news=_news(news_raw),
        f1=_f1(_mapping("f1", raw.get("f1", {}))),
        pages=_pages(_mapping("pages", raw.get("pages", {}))),
        publishing=_publishing(
            _mapping("publishing", raw.get("publishing", {})),
            default_profile=device.profile,
        ),
    )


def _location(
    name: str,
    raw: Mapping[str, Any],
    *,
    default_timezone: str | None,
) -> LocationConfig:
    _only_keys(name, raw, {"name", "latitude", "longitude", "timezone"})
    if "name" not in raw:
        raise ConfigError(f"{name}.name is required")
    timezone_name = raw.get("timezone")
    if timezone_name is None:
        if default_timezone is None:
            raise ConfigError(f"{name}.timezone is required")
        timezone_name = default_timezone
    return LocationConfig(
        name=_string(f"{name}.name", raw["name"]),
        timezone=_string(f"{name}.timezone", timezone_name),
        latitude=_optional_number(f"{name}.latitude", raw.get("latitude")),
        longitude=_optional_number(f"{name}.longitude", raw.get("longitude")),
    )


def _device(raw: Mapping[str, Any]) -> DeviceConfig:
    _only_keys("device", raw, {"profile"})
    if "profile" not in raw:
        raise ConfigError("device.profile is required")
    return DeviceConfig(profile=_string("device.profile", raw["profile"]))


def _feed(name: str, raw: Mapping[str, Any]) -> FeedConfig:
    _only_keys(name, raw, {"name", "url", "category", "enabled"})
    for required in ("name", "url", "category"):
        if required not in raw:
            raise ConfigError(f"{name}.{required} is required")
    return FeedConfig(
        name=_string(f"{name}.name", raw["name"]),
        url=_string(f"{name}.url", raw["url"]),
        category=_string(f"{name}.category", raw["category"]),
        enabled=_boolean(f"{name}.enabled", raw.get("enabled", True)),
    )


def _ai(raw: Mapping[str, Any]) -> AIConfig:
    _only_keys("ai", raw, {"provider", "model", "credential_env", "max_stories"})
    provider = _string("ai.provider", raw.get("provider", "fallback")).lower().replace("-", "_")
    return AIConfig(
        provider=provider,
        model=_optional_nonempty_string("ai.model", raw.get("model")),
        credential_env=_optional_string("ai.credential_env", raw.get("credential_env")),
        max_stories=_integer("ai.max_stories", raw.get("max_stories", 8)),
    )


def _refresh(raw: Mapping[str, Any]) -> RefreshConfig:
    _only_keys(
        "refresh",
        raw,
        {
            "dashboard_minutes",
            "morning_brief_time",
            "morning_brief_local_time",
            "request_timeout_seconds",
            "max_stale_hours",
        },
    )
    if "morning_brief_time" in raw and "morning_brief_local_time" in raw:
        raise ConfigError("configure only one morning brief time field")
    morning_time = raw.get("morning_brief_local_time", raw.get("morning_brief_time", "07:00"))
    return RefreshConfig(
        dashboard_minutes=_integer("refresh.dashboard_minutes", raw.get("dashboard_minutes", 60)),
        morning_brief_local_time=_clock(
            "refresh.morning_brief_local_time",
            morning_time,
        ),
        request_timeout_seconds=_integer(
            "refresh.request_timeout_seconds",
            raw.get("request_timeout_seconds", 20),
        ),
        max_stale_hours=_integer("refresh.max_stale_hours", raw.get("max_stale_hours", 72)),
    )


def _news(raw: Mapping[str, Any]) -> NewsConfig:
    _only_keys("news", raw, {"max_age_hours", "headline_limit", "category_weights"})
    weights_raw = _mapping("news.category_weights", raw.get("category_weights", {}))
    return NewsConfig(
        max_age_hours=_integer("news.max_age_hours", raw.get("max_age_hours", 36)),
        headline_limit=_integer("news.headline_limit", raw.get("headline_limit", 15)),
        category_weights=tuple(
            CategoryWeight(
                _nonempty(f"news.category_weights.{key}", key),
                _number(f"news.category_weights.{key}", value),
            )
            for key, value in weights_raw.items()
        ),
    )


def _f1(raw: Mapping[str, Any]) -> F1Config:
    _only_keys("f1", raw, {"enabled", "top_drivers", "top_constructors"})
    return F1Config(
        enabled=_boolean("f1.enabled", raw.get("enabled", True)),
        top_drivers=_integer("f1.top_drivers", raw.get("top_drivers", 3)),
        top_constructors=_integer("f1.top_constructors", raw.get("top_constructors", 3)),
    )


def _pages(raw: Mapping[str, Any]) -> PagesConfig:
    allowed = {"home", "weather", "f1", "morning_brief", "headlines"}
    _only_keys("pages", raw, allowed)
    values = {key: _boolean(f"pages.{key}", raw.get(key, True)) for key in allowed}
    return PagesConfig(**values)


def _publishing(raw: Mapping[str, Any], *, default_profile: str) -> PublishingConfig:
    _only_keys("publishing", raw, {"base_url", "profile"})
    return PublishingConfig(
        profile=_string("publishing.profile", raw.get("profile", default_profile)),
        base_url=_optional_nonempty_string("publishing.base_url", raw.get("base_url")),
    )


def _reject_secret_fields(value: Any, path: str = "config") -> None:
    if isinstance(value, Mapping):
        for key, item in value.items():
            if not isinstance(key, str):
                raise ConfigError(f"{path} keys must be strings")
            normalized = key.casefold().replace("-", "_")
            if normalized in {"api_key", "apikey", "password", "secret", "token", "access_token"}:
                raise ConfigError(f"{path}.{key} must not contain a secret; use credential_env")
            _reject_secret_fields(item, f"{path}.{key}")
    elif isinstance(value, list):
        for index, item in enumerate(value):
            _reject_secret_fields(item, f"{path}[{index}]")


def _mapping(name: str, value: Any) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ConfigError(f"{name} must be a mapping")
    if any(not isinstance(key, str) for key in value):
        raise ConfigError(f"{name} keys must be strings")
    return value


def _list(name: str, value: Any) -> list[Any]:
    if not isinstance(value, list):
        raise ConfigError(f"{name} must be a list")
    return value


def _only_keys(name: str, value: Mapping[str, Any], allowed: set[str]) -> None:
    unknown = sorted(set(value) - allowed)
    if unknown:
        raise ConfigError(f"{name} contains unknown field(s): {', '.join(unknown)}")


def _string(name: str, value: Any) -> str:
    if not isinstance(value, str):
        raise ConfigError(f"{name} must be a string")
    return _nonempty(name, value)


def _optional_string(name: str, value: Any) -> str | None:
    return None if value is None else _string(name, value)


def _optional_nonempty_string(name: str, value: Any) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ConfigError(f"{name} must be a string")
    return value.strip() or None


def _nonempty(name: str, value: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ConfigError(f"{name} must be non-empty")
    return value.strip()


def _boolean(name: str, value: Any) -> bool:
    if not isinstance(value, bool):
        raise ConfigError(f"{name} must be true or false")
    return value


def _integer(name: str, value: Any) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ConfigError(f"{name} must be an integer")
    return value


def _number(name: str, value: Any) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ConfigError(f"{name} must be a number")
    converted = float(value)
    if not math.isfinite(converted):
        raise ConfigError(f"{name} must be finite")
    return converted


def _optional_number(name: str, value: Any) -> float | None:
    return None if value is None else _number(name, value)


def _clock(name: str, value: Any) -> time:
    text = _string(name, value)
    if not re.fullmatch(r"(?:[01]\d|2[0-3]):[0-5]\d", text):
        raise ConfigError(f"{name} must use 24-hour HH:MM format")
    return time.fromisoformat(text)


def _validate_timezone(name: str, value: str) -> None:
    try:
        ZoneInfo(value)
    except ZoneInfoNotFoundError as exc:
        raise ConfigError(f"{name} is not an available IANA timezone") from exc


def _validate_url(name: str, value: str) -> None:
    parsed = urlsplit(value)
    has_credentials = parsed.username is not None or parsed.password is not None
    if parsed.scheme not in {"http", "https"} or not parsed.hostname or has_credentials:
        raise ConfigError(f"{name} must be an HTTP(S) URL without embedded credentials")


def _require_unique(name: str, values: Any) -> None:
    materialized = list(values)
    if len(materialized) != len(set(materialized)):
        raise ConfigError(f"{name} must be unique")
