from __future__ import annotations

from kindle_brief.models import DashboardSnapshot
from kindle_brief.renderer import icons
from kindle_brief.renderer.formatting import clock, countdown, next_session
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
        size=46,
        minimum=32,
    )
    canvas.draw.text((margin, y + scaled(34, width)), event, fill=INK, font=font(event_size))
    canvas.text((margin, y + scaled(102, width)), f1.circuit_name, size=22, fill=SECONDARY)

    hero_top = y + scaled(150, width)
    hero_bottom = hero_top + scaled(330, width)
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
    info_x = scaled(635, width)
    if upcoming:
        next_icon_size = scaled(46, width)
        canvas.paste(
            icons.motorsport_asset("countdown", next_icon_size, background=PANEL),
            (info_x, hero_top + scaled(48, width)),
        )
        label(
            canvas,
            info_x + scaled(58, width),
            hero_top + scaled(62, width),
            "Next session",
        )
        name, name_size = canvas.fit_text(
            upcoming.name,
            width - margin - info_x,
            size=31,
            minimum=23,
        )
        canvas.draw.text(
            (info_x, hero_top + scaled(102, width)),
            name,
            fill=INK,
            font=font(name_size),
        )
        canvas.text(
            (info_x, hero_top + scaled(158, width)),
            f"{clock(upcoming.starts_at, snapshot.timezone, include_day=True)} MYT",
            size=23,
            fill=SECONDARY,
        )
        canvas.text(
            (info_x, hero_top + scaled(215, width)),
            countdown(upcoming.starts_at, snapshot.generated_at),
            size=38,
        )
    else:
        canvas.text((info_x, hero_top + scaled(125, width)), "Weekend complete", size=28)

    y = hero_bottom + scaled(38, width)
    schedule_icon_size = scaled(32, width)
    canvas.paste(
        icons.motorsport_asset("calendar", schedule_icon_size),
        (margin, y - scaled(7, width)),
    )
    label(canvas, margin + scaled(43, width), y, "Weekend schedule · MYT")
    schedule_top = y + scaled(43, width)
    sessions = f1.sessions[:6]
    row_height = scaled(55, width)
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
            size=20,
            fill=MUTED,
        )
        canvas.text((scaled(350, width), row_y), session.name, size=22)
        if upcoming and session.starts_at == upcoming.starts_at:
            canvas.text(
                (
                    width - margin - scaled(55 if session.name == "Race" else 18, width),
                    row_y,
                ),
                "NEXT",
                size=15,
                anchor="ra",
                stroke_width=1,
            )
        if session.name == "Race":
            race_icon_size = scaled(30, width)
            canvas.paste(
                icons.motorsport_asset("checkered-flag", race_icon_size),
                (
                    width - margin - race_icon_size,
                    row_y - scaled(7, width),
                ),
            )
    y = schedule_top + len(sessions) * row_height + scaled(22, width)
    canvas.rule(y)

    standings_top = y + scaled(30, width)
    half = width // 2
    standings_icon_size = scaled(54, width)
    canvas.paste(
        icons.motorsport_asset("helmet-compact", standings_icon_size),
        (margin, standings_top),
    )
    canvas.paste(
        icons.motorsport_asset("car-compact", standings_icon_size),
        (half + scaled(12, width), standings_top),
    )
    canvas.text(
        (margin + scaled(63, width), standings_top + scaled(15, width)),
        "DRIVERS",
        size=15,
        fill=MUTED,
    )
    canvas.text(
        (half + scaled(76, width), standings_top + scaled(15, width)),
        "CONSTRUCTORS",
        size=15,
        fill=MUTED,
    )
    for index, standing in enumerate(f1.driver_standings[:3]):
        row_y = standings_top + scaled(64 + index * 48, width)
        canvas.text((margin, row_y), f"{standing.position}", size=18, fill=MUTED)
        canvas.text((margin + scaled(45, width), row_y), standing.code, size=23)
        canvas.text((half - scaled(42, width), row_y), f"{standing.points:g}", size=21, anchor="ra")
    for index, standing in enumerate(f1.constructor_standings[:3]):
        row_y = standings_top + scaled(64 + index * 48, width)
        canvas.text((half + scaled(12, width), row_y), f"{standing.position}", size=18, fill=MUTED)
        canvas.text((half + scaled(58, width), row_y), standing.code, size=23)
        canvas.text((width - margin, row_y), f"{standing.points:g}", size=21, anchor="ra")

    footer(canvas, snapshot, page_index=2, attribution="F1 data: Jolpica-F1 · CC BY-NC-SA 4.0")
    return canvas
