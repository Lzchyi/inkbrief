"""Convert Gregorian civil dates with the maintained lunar-python library."""

from __future__ import annotations

from datetime import date, datetime

from lunar_python import Solar

from kindle_brief.models import LunarDate

LUNAR_SOURCE = "lunar-python"


class LunarConversionError(ValueError):
    """Raised when a Gregorian date cannot be converted safely."""


def to_lunar_date(value: date) -> LunarDate:
    """Return the concise Chinese lunar date for a local Gregorian civil date."""

    if isinstance(value, datetime) or not isinstance(value, date):
        raise TypeError("value must be a date")
    try:
        lunar = Solar.fromYmd(value.year, value.month, value.day).getLunar()
        month = lunar.getMonthInChinese()
        day = lunar.getDayInChinese()
    except (TypeError, ValueError, IndexError) as exc:
        raise LunarConversionError(f"cannot convert Gregorian date {value.isoformat()}") from exc
    if not month or not day:
        raise LunarConversionError(f"lunar-python returned an empty date for {value.isoformat()}")
    return LunarDate(gregorian_date=value, display_text=f"农历{month}月{day}")
