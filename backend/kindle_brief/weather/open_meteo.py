"""Small synchronous client and pure parser for Open-Meteo forecast data."""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import cast
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import httpx

from kindle_brief.models import HourlyForecast, SourceStatus, WeatherSnapshot

OPEN_METEO_ATTRIBUTION = "Weather data by Open-Meteo.com"
DEFAULT_USER_AGENT = "KindleBrief/0.1 (personal non-commercial e-ink dashboard)"

_WEATHER_CODES: dict[int, tuple[str, str]] = {
    0: ("clear", "Clear sky"),
    1: ("mainly-clear", "Mainly clear"),
    2: ("partly-cloudy", "Partly cloudy"),
    3: ("overcast", "Overcast"),
    45: ("fog", "Fog"),
    48: ("rime-fog", "Depositing rime fog"),
    51: ("light-drizzle", "Light drizzle"),
    53: ("drizzle", "Drizzle"),
    55: ("heavy-drizzle", "Heavy drizzle"),
    56: ("light-freezing-drizzle", "Light freezing drizzle"),
    57: ("freezing-drizzle", "Freezing drizzle"),
    61: ("light-rain", "Light rain"),
    63: ("rain", "Rain"),
    65: ("heavy-rain", "Heavy rain"),
    66: ("light-freezing-rain", "Light freezing rain"),
    67: ("freezing-rain", "Freezing rain"),
    71: ("light-snow", "Light snow"),
    73: ("snow", "Snow"),
    75: ("heavy-snow", "Heavy snow"),
    77: ("snow-grains", "Snow grains"),
    80: ("light-rain-showers", "Light rain showers"),
    81: ("rain-showers", "Rain showers"),
    82: ("heavy-rain-showers", "Heavy rain showers"),
    85: ("light-snow-showers", "Light snow showers"),
    86: ("snow-showers", "Snow showers"),
    95: ("thunderstorm", "Thunderstorm"),
    96: ("thunderstorm-hail", "Thunderstorm with slight hail"),
    99: ("heavy-thunderstorm-hail", "Thunderstorm with heavy hail"),
}

_OPEN_METEO_LICENSE_URL = "https://creativecommons.org/licenses/by/4.0/"


class WeatherDataError(ValueError):
    """Raised when Open-Meteo returns incomplete or malformed forecast data."""


@dataclass(frozen=True, slots=True)
class GeocodedLocation:
    """Location fields needed to make a forecast request."""

    name: str
    latitude: float
    longitude: float
    timezone: str
    country: str | None = None
    admin1: str | None = None

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise WeatherDataError("geocoding result name must be non-empty")
        if not -90 <= self.latitude <= 90:
            raise WeatherDataError("geocoding latitude must be between -90 and 90")
        if not -180 <= self.longitude <= 180:
            raise WeatherDataError("geocoding longitude must be between -180 and 180")
        try:
            ZoneInfo(self.timezone)
        except ZoneInfoNotFoundError as exc:
            raise WeatherDataError(f"unknown geocoding timezone: {self.timezone}") from exc


def _mapping(value: object, field: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise WeatherDataError(f"{field} must be an object")
    return cast(Mapping[str, object], value)


def _sequence(value: object, field: str) -> Sequence[object]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise WeatherDataError(f"{field} must be an array")
    return value


def _text(value: object, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise WeatherDataError(f"{field} must be a non-empty string")
    return value


def _number(value: object, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise WeatherDataError(f"{field} must be numeric")
    result = float(value)
    if not math.isfinite(result):
        raise WeatherDataError(f"{field} must be finite")
    return result


def _optional_number(value: object, field: str) -> float | None:
    return None if value is None else _number(value, field)


def _timezone(payload: Mapping[str, object]) -> ZoneInfo:
    name = _text(payload.get("timezone"), "timezone")
    try:
        return ZoneInfo(name)
    except ZoneInfoNotFoundError as exc:
        raise WeatherDataError(f"unknown timezone: {name}") from exc


def _parse_time(value: object, timezone: ZoneInfo, field: str) -> datetime:
    text = _text(value, field)
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise WeatherDataError(f"{field} must be an ISO 8601 datetime") from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone)
    return parsed.astimezone(UTC)


def _array_value(section: Mapping[str, object], key: str, index: int) -> object:
    values = _sequence(section.get(key), f"{key}")
    try:
        return values[index]
    except IndexError as exc:
        raise WeatherDataError(f"{key} is shorter than the time array") from exc


def _matching_hourly_index(
    hourly: Mapping[str, object], observed_at: datetime, timezone: ZoneInfo
) -> int:
    times = _sequence(hourly.get("time"), "hourly.time")
    observed_hour = observed_at.astimezone(timezone).replace(minute=0, second=0, microsecond=0)
    for index, value in enumerate(times):
        candidate = _parse_time(value, timezone, f"hourly.time[{index}]").astimezone(timezone)
        if candidate == observed_hour:
            return index
    raise WeatherDataError("hourly forecast does not contain the current local hour")


def _matching_daily_index(
    daily: Mapping[str, object], observed_at: datetime, timezone: ZoneInfo
) -> int:
    dates = _sequence(daily.get("time"), "daily.time")
    target = observed_at.astimezone(timezone).date().isoformat()
    for index, value in enumerate(dates):
        if value == target:
            return index
    raise WeatherDataError("daily forecast does not contain the current local date")


def _weather_code(value: object, field: str) -> tuple[str, str]:
    numeric = _number(value, field)
    if not numeric.is_integer():
        raise WeatherDataError(f"{field} must be an integer WMO code")
    code_number = int(numeric)
    condition_text = _WEATHER_CODES.get(
        code_number, (f"wmo-{code_number}", f"Weather code {code_number}")
    )[1]
    return str(code_number), condition_text


def _hourly_forecasts(
    hourly: Mapping[str, object], start_index: int, timezone: ZoneInfo
) -> tuple[HourlyForecast, ...]:
    times = _sequence(hourly.get("time"), "hourly.time")
    result: list[HourlyForecast] = []
    for index in range(start_index, min(len(times), start_index + 24)):
        condition_code, condition_text = _weather_code(
            _array_value(hourly, "weather_code", index), f"hourly.weather_code[{index}]"
        )
        result.append(
            HourlyForecast(
                timestamp=_parse_time(times[index], timezone, f"hourly.time[{index}]"),
                temperature_c=_number(
                    _array_value(hourly, "temperature_2m", index),
                    f"hourly.temperature_2m[{index}]",
                ),
                condition_code=condition_code,
                condition_text=condition_text,
                rain_probability_pct=_number(
                    _array_value(hourly, "precipitation_probability", index),
                    f"hourly.precipitation_probability[{index}]",
                ),
                cloud_cover_pct=_number(
                    _array_value(hourly, "cloud_cover", index),
                    f"hourly.cloud_cover[{index}]",
                ),
            )
        )
    return tuple(result)


def parse_open_meteo(payload: Mapping[str, object], *, fetched_at: datetime) -> WeatherSnapshot:
    """Parse an Open-Meteo forecast response without performing network access."""

    timezone = _timezone(payload)
    current = _mapping(payload.get("current"), "current")
    hourly = _mapping(payload.get("hourly"), "hourly")
    daily = _mapping(payload.get("daily"), "daily")

    observed_at = _parse_time(current.get("time"), timezone, "current.time")
    hourly_index = _matching_hourly_index(hourly, observed_at, timezone)
    daily_index = _matching_daily_index(daily, observed_at, timezone)

    condition_code, condition_text = _weather_code(
        current.get("weather_code"), "current.weather_code"
    )

    return WeatherSnapshot(
        observed_at=observed_at,
        temperature_c=_number(current.get("temperature_2m"), "current.temperature_2m"),
        condition_code=condition_code,
        condition_text=condition_text,
        high_c=_number(
            _array_value(daily, "temperature_2m_max", daily_index),
            "daily.temperature_2m_max",
        ),
        low_c=_number(
            _array_value(daily, "temperature_2m_min", daily_index),
            "daily.temperature_2m_min",
        ),
        humidity_pct=_number(current.get("relative_humidity_2m"), "current.relative_humidity_2m"),
        rain_probability_pct=_number(
            _array_value(hourly, "precipitation_probability", hourly_index),
            "hourly.precipitation_probability",
        ),
        status=SourceStatus(
            source="Open-Meteo",
            fetched_at=fetched_at,
            attribution=OPEN_METEO_ATTRIBUTION,
            license_url=_OPEN_METEO_LICENSE_URL,
        ),
        feels_like_c=_optional_number(
            current.get("apparent_temperature"), "current.apparent_temperature"
        ),
        wind_kph=_optional_number(current.get("wind_speed_10m"), "current.wind_speed_10m"),
        uv_index=_optional_number(
            _array_value(hourly, "uv_index", hourly_index) if "uv_index" in hourly else None,
            "hourly.uv_index",
        ),
        cloud_cover_pct=_optional_number(current.get("cloud_cover"), "current.cloud_cover"),
        hourly=_hourly_forecasts(hourly, hourly_index, timezone),
        wind_direction_deg=_optional_number(
            current.get("wind_direction_10m"), "current.wind_direction_10m"
        ),
        visibility_km=(
            _number(
                _array_value(hourly, "visibility", hourly_index),
                "hourly.visibility",
            )
            / 1_000
            if "visibility" in hourly
            else None
        ),
        precipitation_mm=_optional_number(current.get("precipitation"), "current.precipitation"),
    )


class OpenMeteoClient:
    """Key-free client for Open-Meteo's noncommercial forecast and geocoding APIs."""

    FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
    GEOCODING_URL = "https://geocoding-api.open-meteo.com/v1/search"

    def __init__(
        self,
        *,
        client: httpx.Client | None = None,
        user_agent: str = DEFAULT_USER_AGENT,
        timeout_seconds: float = 15.0,
    ) -> None:
        if not user_agent.strip():
            raise ValueError("user_agent must be non-empty")
        self._client = client or httpx.Client(timeout=timeout_seconds)
        self._owns_client = client is None
        self._headers = {"User-Agent": user_agent, "Accept": "application/json"}

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    def __enter__(self) -> OpenMeteoClient:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def resolve_location(
        self, query: str, *, country_code: str | None = None, language: str = "en"
    ) -> GeocodedLocation:
        if not query.strip():
            raise ValueError("location query must be non-empty")
        params: dict[str, str | int] = {
            "name": query,
            "count": 1,
            "language": language,
            "format": "json",
        }
        if country_code:
            params["countryCode"] = country_code
        payload = self._get_json(self.GEOCODING_URL, params=params)
        results = _sequence(payload.get("results", ()), "results")
        if not results:
            raise WeatherDataError(f"no geocoding result for {query!r}")
        result = _mapping(results[0], "results[0]")
        return GeocodedLocation(
            name=_text(result.get("name"), "results[0].name"),
            latitude=_number(result.get("latitude"), "results[0].latitude"),
            longitude=_number(result.get("longitude"), "results[0].longitude"),
            timezone=_text(result.get("timezone"), "results[0].timezone"),
            country=cast(str | None, result.get("country")),
            admin1=cast(str | None, result.get("admin1")),
        )

    def fetch_forecast(
        self,
        *,
        latitude: float,
        longitude: float,
        timezone: str,
        fetched_at: datetime | None = None,
    ) -> WeatherSnapshot:
        params = {
            "latitude": latitude,
            "longitude": longitude,
            "timezone": timezone,
            "forecast_days": 2,
            "temperature_unit": "celsius",
            "wind_speed_unit": "kmh",
            "precipitation_unit": "mm",
            "timeformat": "iso8601",
            "current": ",".join(
                (
                    "temperature_2m",
                    "apparent_temperature",
                    "relative_humidity_2m",
                    "weather_code",
                    "cloud_cover",
                    "wind_speed_10m",
                    "wind_direction_10m",
                    "precipitation",
                )
            ),
            "hourly": ",".join(
                (
                    "temperature_2m",
                    "apparent_temperature",
                    "relative_humidity_2m",
                    "precipitation_probability",
                    "precipitation",
                    "weather_code",
                    "cloud_cover",
                    "visibility",
                    "wind_speed_10m",
                    "wind_direction_10m",
                    "uv_index",
                )
            ),
            "daily": ",".join(
                (
                    "weather_code",
                    "temperature_2m_max",
                    "temperature_2m_min",
                    "sunrise",
                    "sunset",
                    "uv_index_max",
                    "precipitation_probability_max",
                )
            ),
        }
        payload = self._get_json(self.FORECAST_URL, params=params)
        return parse_open_meteo(payload, fetched_at=fetched_at or datetime.now(UTC))

    def _get_json(
        self, url: str, *, params: Mapping[str, str | int | float]
    ) -> Mapping[str, object]:
        try:
            response = self._client.get(url, params=params, headers=self._headers)
            response.raise_for_status()
            return _mapping(response.json(), "response")
        except (httpx.HTTPError, ValueError) as exc:
            raise WeatherDataError(f"Open-Meteo request failed: {exc}") from exc
