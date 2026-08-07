from datetime import UTC, datetime

import httpx
import pytest
from kindle_brief.weather import OpenMeteoClient, WeatherDataError, parse_open_meteo


def _forecast_payload() -> dict[str, object]:
    return {
        "timezone": "Asia/Kuala_Lumpur",
        "current": {
            "time": "2026-08-08T07:15",
            "temperature_2m": 27.5,
            "apparent_temperature": 31.2,
            "relative_humidity_2m": 84,
            "weather_code": 2,
            "cloud_cover": 65,
            "wind_speed_10m": 8.4,
            "wind_direction_10m": 205,
            "precipitation": 0.3,
        },
        "hourly": {
            "time": [
                "2026-08-08T06:00",
                "2026-08-08T07:00",
                "2026-08-08T08:00",
            ],
            "temperature_2m": [26.0, 27.0, 28.0],
            "precipitation_probability": [10, 68, 30],
            "weather_code": [1, 2, 61],
            "cloud_cover": [20, 65, 80],
            "visibility": [10_000, 8_000, 6_000],
            "uv_index": [0, 1, 3],
        },
        "daily": {
            "time": ["2026-08-08", "2026-08-09"],
            "temperature_2m_max": [32, 31],
            "temperature_2m_min": [25, 24],
        },
    }


def test_parser_matches_rain_probability_to_current_local_hour() -> None:
    snapshot = parse_open_meteo(
        _forecast_payload(), fetched_at=datetime(2026, 8, 7, 23, 20, tzinfo=UTC)
    )

    assert snapshot.observed_at == datetime(2026, 8, 7, 23, 15, tzinfo=UTC)
    assert snapshot.rain_probability_pct == 68
    assert snapshot.high_c == 32
    assert snapshot.low_c == 25
    assert snapshot.condition_code == "2"
    assert snapshot.visibility_km == 8
    assert snapshot.precipitation_mm == 0.3
    assert snapshot.wind_direction_deg == 205
    assert [hour.temperature_c for hour in snapshot.hourly] == [27, 28]
    assert snapshot.hourly[0].rain_probability_pct == 68
    assert snapshot.hourly[0].timestamp == datetime(2026, 8, 7, 23, tzinfo=UTC)
    assert snapshot.status.attribution == "Weather data by Open-Meteo.com"


def test_parser_rejects_forecast_without_matching_current_hour() -> None:
    payload = _forecast_payload()
    payload["current"] = {**payload["current"], "time": "2026-08-08T10:15"}  # type: ignore[arg-type]

    with pytest.raises(WeatherDataError, match="current local hour"):
        parse_open_meteo(payload, fetched_at=datetime.now(UTC))


def test_client_uses_explicit_timezone_and_meaningful_user_agent() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["User-Agent"].startswith("KindleBrief/")
        assert request.url.params["timezone"] == "Asia/Kuala_Lumpur"
        assert "precipitation_probability" in request.url.params["hourly"]
        return httpx.Response(200, json=_forecast_payload())

    with httpx.Client(transport=httpx.MockTransport(handler)) as http_client:
        snapshot = OpenMeteoClient(client=http_client).fetch_forecast(
            latitude=3.139,
            longitude=101.6869,
            timezone="Asia/Kuala_Lumpur",
            fetched_at=datetime(2026, 8, 7, 23, 20, tzinfo=UTC),
        )

    assert snapshot.temperature_c == 27.5
