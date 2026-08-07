from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from kindle_brief.models import DashboardSnapshot, F1Session


def local_datetime(value: datetime, timezone: str) -> datetime:
    return value.astimezone(ZoneInfo(timezone))


def header_text(snapshot: DashboardSnapshot) -> str:
    local = local_datetime(snapshot.generated_at, snapshot.timezone)
    date_time = f"{local:%a} {local.day} {local:%b %Y} · {local:%H:%M}"
    return f"{date_time} · {snapshot.lunar_date.display_text}"


def clock(value: datetime | None, timezone: str, *, include_day: bool = False) -> str:
    if value is None:
        return "—"
    local = local_datetime(value, timezone)
    return f"{local:%a %H:%M}" if include_day else f"{local:%H:%M}"


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
