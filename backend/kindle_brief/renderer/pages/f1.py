from __future__ import annotations

from kindle_brief.models import DashboardSnapshot
from kindle_brief.renderer import icons
from kindle_brief.renderer.formatting import clock, countdown, date_range, next_session
from kindle_brief.renderer.theme import INK, MUTED, PANEL, SECONDARY, font, scaled

from .common import footer, label, page_canvas


def _draw_track(canvas, snapshot, box):  # type: ignore[no-untyped-def]
    try:
        from kindle_brief.renderer.tracks import draw_track

        draw_track(
            canvas.draw,
            box,
            snapshot.f1.circuit_id if snapshot.f1 else None,
            ink=INK,
            width=scaled(7, canvas.width),
        )
    except (ImportError, ValueError):
        left, top, right, bottom = box
        points = [
            (left + (right - left) * 0.16, top + (bottom - top) * 0.57),
            (left + (right - left) * 0.3, top + (bottom - top) * 0.2),
            (left + (right - left) * 0.67, top + (bottom - top) * 0.12),
            (left + (right - left) * 0.9, top + (bottom - top) * 0.42),
            (left + (right - left) * 0.74, top + (bottom - top) * 0.82),
            (left + (right - left) * 0.42, top + (bottom - top) * 0.7),
            (left + (right - left) * 0.16, top + (bottom - top) * 0.57),
        ]
        canvas.draw.line(points, fill=INK, width=scaled(7, canvas.width), joint="curve")


def render(snapshot: DashboardSnapshot, width: int, height: int):  # type: ignore[no-untyped-def]
    canvas, y = page_canvas(snapshot, width, height)
    margin = scaled(58, width)
    f1 = snapshot.f1
    if f1 is None:
        canvas.text(
            (width // 2, y + scaled(180, width)), "F1 schedule unavailable", size=42, anchor="ma"
        )
        footer(canvas, snapshot, page_index=2, attribution="F1 data: Jolpica-F1")
        return canvas

    label(canvas, margin, y, f"Formula 1 · Round {f1.round_number}")
    event, event_size = canvas.fit_text(
        f1.event_name,
        width - margin * 2,
        size=50,
        minimum=36,
    )
    canvas.draw.text((margin, y + scaled(34, width)), event, fill=INK, font=font(event_size))
    weekend = date_range(tuple(session.starts_at for session in f1.sessions), snapshot.timezone)
    event_details, details_size = canvas.fit_text(
        f"{f1.circuit_name} · {weekend}",
        width - margin * 2,
        size=27,
        minimum=22,
    )
    canvas.draw.text(
        (margin, y + scaled(106, width)),
        event_details,
        fill=SECONDARY,
        font=font(details_size),
    )

    hero_top = y + scaled(158, width)
    hero_bottom = hero_top + scaled(350, width)
    canvas.draw.rounded_rectangle(
        (margin, hero_top, width - margin, hero_bottom),
        radius=scaled(22, width),
        fill=PANEL,
    )
    _draw_track(
        canvas,
        snapshot,
        (
            margin + scaled(35, width),
            hero_top + scaled(35, width),
            scaled(565, width),
            hero_bottom - scaled(35, width),
        ),
    )
    upcoming = next_session(f1.sessions, snapshot.generated_at)
    info_x = scaled(620, width)
    if upcoming:
        next_icon_size = scaled(52, width)
        canvas.paste(
            icons.motorsport_asset("countdown", next_icon_size, background=PANEL),
            (info_x, hero_top + scaled(48, width)),
        )
        label(
            canvas,
            info_x + scaled(65, width),
            hero_top + scaled(62, width),
            "Next session",
        )
        name, name_size = canvas.fit_text(
            upcoming.name,
            width - margin - info_x,
            size=36,
            minimum=30,
        )
        canvas.draw.text(
            (info_x, hero_top + scaled(108, width)),
            name,
            fill=INK,
            font=font(name_size),
        )
        canvas.text(
            (info_x, hero_top + scaled(171, width)),
            f"{clock(upcoming.starts_at, snapshot.timezone, include_day=True)} MYT",
            size=28,
            fill=SECONDARY,
        )
        canvas.text(
            (info_x, hero_top + scaled(237, width)),
            countdown(upcoming.starts_at, snapshot.generated_at),
            size=44,
        )
    else:
        canvas.text((info_x, hero_top + scaled(125, width)), "Weekend complete", size=28)

    y = hero_bottom + scaled(34, width)
    schedule_icon_size = scaled(36, width)
    canvas.paste(
        icons.motorsport_asset("calendar", schedule_icon_size),
        (margin, y - scaled(7, width)),
    )
    label(canvas, margin + scaled(48, width), y, "Weekend schedule · MYT")
    schedule_top = y + scaled(49, width)
    sessions = f1.sessions[:6]
    row_height = scaled(64, width)
    for index, session in enumerate(sessions):
        row_y = schedule_top + index * row_height
        if index % 2 == 0:
            canvas.draw.rectangle(
                (margin, row_y - scaled(7, width), width - margin, row_y + scaled(40, width)),
                fill=248,
            )
        canvas.text(
            (margin + scaled(18, width), row_y),
            clock(session.starts_at, snapshot.timezone, include_day=True),
            size=24,
            fill=MUTED,
        )
        canvas.text((scaled(405, width), row_y), session.name, size=27)
        if upcoming and session.starts_at == upcoming.starts_at:
            canvas.text(
                (
                    width - margin - scaled(55 if session.name == "Race" else 18, width),
                    row_y,
                ),
                "NEXT",
                size=18,
                anchor="ra",
                stroke_width=1,
            )
        if session.name == "Race":
            race_icon_size = scaled(34, width)
            canvas.paste(
                icons.motorsport_asset("checkered-flag", race_icon_size),
                (
                    width - margin - race_icon_size,
                    row_y - scaled(7, width),
                ),
            )
    y = schedule_top + len(sessions) * row_height + scaled(22, width)
    canvas.rule(y)

    standings_top = y + scaled(27, width)
    half = width // 2
    standings_icon_size = scaled(62, width)
    canvas.paste(
        icons.motorsport_asset("helmet-compact", standings_icon_size),
        (margin, standings_top),
    )
    canvas.paste(
        icons.motorsport_asset("car-compact", standings_icon_size),
        (half + scaled(12, width), standings_top),
    )
    canvas.text(
        (margin + scaled(72, width), standings_top + scaled(17, width)),
        "DRIVERS",
        size=20,
        fill=MUTED,
    )
    canvas.text(
        (half + scaled(84, width), standings_top + scaled(17, width)),
        "CONSTRUCTORS",
        size=20,
        fill=MUTED,
    )
    for index, standing in enumerate(f1.driver_standings[:3]):
        row_y = standings_top + scaled(72 + index * 52, width)
        canvas.text((margin, row_y), f"{standing.position}", size=22, fill=MUTED)
        canvas.text((margin + scaled(48, width), row_y), standing.code, size=28)
        canvas.text((half - scaled(42, width), row_y), f"{standing.points:g}", size=26, anchor="ra")
    for index, standing in enumerate(f1.constructor_standings[:3]):
        row_y = standings_top + scaled(72 + index * 52, width)
        canvas.text((half + scaled(12, width), row_y), f"{standing.position}", size=22, fill=MUTED)
        canvas.text((half + scaled(62, width), row_y), standing.code, size=28)
        canvas.text((width - margin, row_y), f"{standing.points:g}", size=26, anchor="ra")

    footer(canvas, snapshot, page_index=2, attribution="F1 data: Jolpica-F1 · CC BY-NC-SA 4.0")
    return canvas
