from __future__ import annotations

from kindle_brief.models import DashboardSnapshot
from kindle_brief.renderer import icons
from kindle_brief.renderer.formatting import clock, is_night, next_session, percentage, temperature
from kindle_brief.renderer.moon import moon_phase_image
from kindle_brief.renderer.theme import INK, SECONDARY, font, scaled

from .common import footer, label, page_canvas


def render(snapshot: DashboardSnapshot, width: int, height: int):  # type: ignore[no-untyped-def]
    canvas, y = page_canvas(snapshot, width, height)
    margin = scaled(58, width)
    weather = snapshot.weather

    if weather is None:
        canvas.text((margin, y + scaled(55, width)), "Weather unavailable", size=42)
        y += scaled(290, width)
    else:
        astronomy = snapshot.astronomy
        icon_size = scaled(250, width)
        weather_icon = icons.weather_asset(
            weather.condition_code,
            icon_size,
            is_night=is_night(
                snapshot.generated_at,
                snapshot.timezone,
                sunrise=astronomy.sunrise if astronomy else None,
                sunset=astronomy.sunset if astronomy else None,
            ),
            wind_kph=weather.wind_kph,
            visibility_km=weather.visibility_km,
            cloud_cover_pct=weather.cloud_cover_pct,
        )
        canvas.paste(
            weather_icon,
            (margin + scaled(18, width), y + scaled(20, width)),
        )
        details_x = scaled(415, width)
        canvas.text(
            (details_x, y + scaled(8, width)),
            temperature(weather.temperature_c),
            size=96,
            stroke_width=1,
        )
        condition, condition_size = canvas.fit_text(
            weather.condition_text,
            width - details_x - margin,
            size=34,
            minimum=25,
        )
        canvas.draw.text(
            (details_x, y + scaled(130, width)),
            condition,
            fill=INK,
            font=font(condition_size),
        )
        canvas.text(
            (details_x, y + scaled(185, width)),
            f"H {temperature(weather.high_c)}   L {temperature(weather.low_c)}",
            size=24,
            fill=SECONDARY,
        )
        canvas.text(
            (details_x, y + scaled(228, width)),
            (
                f"Humidity {percentage(weather.humidity_pct)}   ·   "
                f"Rain {percentage(weather.rain_probability_pct)}"
            ),
            size=21,
            fill=SECONDARY,
        )
        y += scaled(315, width)
    canvas.rule(y)

    astronomy = snapshot.astronomy
    moon_top = y + scaled(35, width)
    if astronomy is not None:
        moon_size = scaled(112, width)
        moon = moon_phase_image(moon_size, astronomy.phase_fraction * 360)
        canvas.paste(moon, (margin + scaled(10, width), moon_top))
        canvas.text(
            (margin + scaled(158, width), moon_top + scaled(15, width)),
            astronomy.phase_name,
            size=28,
        )
        canvas.text(
            (margin + scaled(158, width), moon_top + scaled(63, width)),
            f"Stargazing: {astronomy.stargazing_rating}",
            size=22,
            fill=SECONDARY,
        )
    else:
        canvas.text((margin, moon_top + scaled(36, width)), "Sky data unavailable", size=26)
    y = moon_top + scaled(145, width)
    canvas.rule(y)

    f1 = snapshot.f1
    f1_top = y + scaled(32, width)
    label(canvas, margin, f1_top, "Formula 1")
    if f1 is None:
        canvas.text((margin, f1_top + scaled(42, width)), "Schedule unavailable", size=26)
        y = f1_top + scaled(150, width)
    else:
        event, event_size = canvas.fit_text(
            f1.event_name,
            width - margin * 2,
            size=32,
            minimum=24,
        )
        canvas.draw.text(
            (margin, f1_top + scaled(40, width)),
            event,
            fill=INK,
            font=font(event_size),
        )
        upcoming = next_session(f1.sessions, snapshot.generated_at)
        if upcoming:
            canvas.text(
                (margin, f1_top + scaled(91, width)),
                (
                    f"Next: {upcoming.name} · "
                    f"{clock(upcoming.starts_at, snapshot.timezone, include_day=True)} MYT"
                ),
                size=21,
                fill=SECONDARY,
            )
        rows_y = f1_top + scaled(140, width)
        icon_size = scaled(54, width)
        canvas.paste(icons.motorsport_asset("helmet-compact", icon_size), (margin, rows_y))
        driver_text = "   ·   ".join(
            f"{standing.code} {standing.points:g}" for standing in f1.driver_standings[:3]
        )
        canvas.text(
            (margin + scaled(70, width), rows_y + scaled(4, width)), driver_text or "—", size=22
        )
        rows_y += scaled(60, width)
        canvas.paste(icons.motorsport_asset("car-compact", icon_size), (margin, rows_y))
        constructor_text = "   ·   ".join(
            f"{standing.code} {standing.points:g}" for standing in f1.constructor_standings[:3]
        )
        canvas.text(
            (margin + scaled(70, width), rows_y + scaled(4, width)),
            constructor_text or "—",
            size=22,
        )
        y = rows_y + scaled(70, width)
    canvas.rule(y)

    news_top = y + scaled(28, width)
    label(canvas, margin, news_top, "Headlines")
    cursor = news_top + scaled(40, width)
    for article in snapshot.headlines[:3]:
        canvas.text((margin, cursor + scaled(1, width)), "•", size=26)
        lines = canvas.wrapped_lines(
            article.title,
            width - margin * 2 - scaled(30, width),
            size=22,
            max_lines=2,
        )
        canvas.draw_lines(
            lines,
            x=margin + scaled(30, width),
            y=cursor,
            size=22,
            line_height=31,
        )
        cursor += scaled(72, width) if len(lines) > 1 else scaled(52, width)

    footer(
        canvas,
        snapshot,
        page_index=0,
        attribution="Weather: Open-Meteo · F1: Jolpica-F1",
    )
    return canvas
