"""Local Sun and Moon calculations."""

from .calculator import (
    ASTRONOMY_ATTRIBUTION,
    AstronomyCalculationError,
    calculate_astronomy,
    moon_phase_name,
    rate_stargazing,
)

__all__ = [
    "ASTRONOMY_ATTRIBUTION",
    "AstronomyCalculationError",
    "calculate_astronomy",
    "moon_phase_name",
    "rate_stargazing",
]
