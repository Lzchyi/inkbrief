"""Open-Meteo weather and geocoding adapter."""

from .open_meteo import (
    OPEN_METEO_ATTRIBUTION,
    GeocodedLocation,
    OpenMeteoClient,
    WeatherDataError,
    parse_open_meteo,
)

__all__ = [
    "OPEN_METEO_ATTRIBUTION",
    "GeocodedLocation",
    "OpenMeteoClient",
    "WeatherDataError",
    "parse_open_meteo",
]
