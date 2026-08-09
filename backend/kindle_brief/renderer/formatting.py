from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from kindle_brief.models import DashboardSnapshot, F1Session


def local_datetime(value: datetime, timezone: str) -> datetime:
    return value.astimezone(ZoneInfo(timezone))


def is_night(
    value: datetime,
    timezone: str,
    *,
    sunrise: datetime | None = None,
    sunset: datetime | None = None,
) -> bool:
    """Return whether ``value`` falls outside the local daylight window."""
    local = local_datetime(value, timezone)
    if sunrise is not None and sunset is not None:
        local_sunrise = local_datetime(sunrise, timezone)
        local_sunset = local_datetime(sunset, timezone)
        local_minutes = local.hour * 60 + local.minute
        sunrise_minutes = local_sunrise.hour * 60 + local_sunrise.minute
        sunset_minutes = local_sunset.hour * 60 + local_sunset.minute
        return local_minutes < sunrise_minutes or local_minutes >= sunset_minutes
    return local.hour < 6 or local.hour >= 19


def header_text(snapshot: DashboardSnapshot) -> str:
    local = local_datetime(snapshot.generated_at, snapshot.timezone)
    date_time = f"{local:%a} {local.day} {local:%b %Y} · {local:%H:%M}"
    return f"{date_time} · {snapshot.lunar_date.display_text}"


def clock(value: datetime | None, timezone: str, *, include_day: bool = False) -> str:
    if value is None:
        return "—"
    local = local_datetime(value, timezone)
    if include_day:
        return f"{local:%a} {local.day} {local:%b} · {local:%H:%M}"
    return f"{local:%H:%M}"


def date_range(values: tuple[datetime, ...], timezone: str) -> str:
    """Format a compact, unambiguous local date range."""
    if not values:
        return "Dates unavailable"
    start = local_datetime(min(values), timezone)
    end = local_datetime(max(values), timezone)
    if start.date() == end.date():
        return f"{start.day} {start:%b %Y}"
    if start.year != end.year:
        return f"{start.day} {start:%b %Y}–{end.day} {end:%b %Y}"
    if start.month != end.month:
        return f"{start.day} {start:%b}–{end.day} {end:%b %Y}"
    return f"{start.day}–{end.day} {end:%b %Y}"


def temperature(value: float | None) -> str:
    return "—" if value is None else f"{round(value)}°"


def percentage(value: float | None) -> str:
    return "—" if value is None else f"{round(value)}%"


def next_session(
    sessions: tuple[F1Session, ...],
    now: datetime,
) -> F1Session | None:
    return next((session for session in sessions if session.starts_at >= now), None)


def countdown(target: datetime, now: datetime) -> str:
    seconds = max(0, int((target - now).total_seconds()))
    days, seconds = divmod(seconds, 86_400)
    hours, seconds = divmod(seconds, 3_600)
    minutes = seconds // 60
    if days:
        return f"{days}d {hours}h"
    if hours:
        return f"{hours}h {minutes}m"
    return f"{minutes}m"


def snapshot_is_stale(snapshot: DashboardSnapshot) -> bool:
    statuses = [
        item.status
        for item in (snapshot.weather, snapshot.astronomy, snapshot.f1)
        if item is not None
    ]
    return snapshot.degraded or any(status.stale for status in statuses)
