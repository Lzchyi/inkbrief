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
        icon_size = scaled(270, width)
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
            (margin + scaled(8, width), y + scaled(18, width)),
        )
        details_x = scaled(405, width)
        canvas.text(
            (details_x, y),
            temperature(weather.temperature_c),
            size=104,
            stroke_width=1,
        )
        condition, condition_size = canvas.fit_text(
            weather.condition_text,
            width - details_x - margin,
            size=38,
            minimum=30,
        )
        canvas.draw.text(
            (details_x, y + scaled(139, width)),
            condition,
            fill=INK,
            font=font(condition_size),
        )
        canvas.text(
            (details_x, y + scaled(198, width)),
            f"H {temperature(weather.high_c)}   L {temperature(weather.low_c)}",
            size=29,
            fill=SECONDARY,
        )
        canvas.text(
            (details_x, y + scaled(246, width)),
            (
                f"Humidity {percentage(weather.humidity_pct)}   ·   "
                f"Rain {percentage(weather.rain_probability_pct)}"
            ),
            size=25,
            fill=SECONDARY,
        )
        y += scaled(350, width)
    canvas.rule(y)

    astronomy = snapshot.astronomy
    moon_top = y + scaled(36, width)
    if astronomy is not None:
        moon_size = scaled(140, width)
        moon = moon_phase_image(moon_size, astronomy.phase_fraction * 360)
        canvas.paste(moon, (margin + scaled(10, width), moon_top))
        canvas.text(
            (margin + scaled(178, width), moon_top + scaled(18, width)),
            astronomy.phase_name,
            size=34,
        )
        canvas.text(
            (margin + scaled(178, width), moon_top + scaled(78, width)),
            f"Stargazing: {astronomy.stargazing_rating}",
            size=26,
            fill=SECONDARY,
        )
    else:
        canvas.text((margin, moon_top + scaled(36, width)), "Sky data unavailable", size=26)
    y = moon_top + scaled(175, width)
    canvas.rule(y)

    f1 = snapshot.f1
    f1_top = y + scaled(32, width)
    f1_label_icon_size = scaled(36, width)
    canvas.paste(
        icons.motorsport_asset("trophy", f1_label_icon_size),
        (margin, f1_top - scaled(7, width)),
    )
    label(canvas, margin + scaled(48, width), f1_top, "Formula 1")
    if f1 is None:
        canvas.text((margin, f1_top + scaled(42, width)), "Schedule unavailable", size=26)
        y = f1_top + scaled(150, width)
    else:
        event, event_size = canvas.fit_text(
            f1.event_name,
            width - margin * 2,
            size=38,
            minimum=31,
        )
        canvas.draw.text(
            (margin, f1_top + scaled(47, width)),
            event,
            fill=INK,
            font=font(event_size),
        )
        upcoming = next_session(f1.sessions, snapshot.generated_at)
        if upcoming:
            canvas.text(
                (margin, f1_top + scaled(105, width)),
                (
                    f"Next: {upcoming.name} · "
                    f"{clock(upcoming.starts_at, snapshot.timezone, include_day=True)} MYT"
                ),
                size=26,
                fill=SECONDARY,
            )
        rows_y = f1_top + scaled(158, width)
        icon_size = scaled(62, width)
        canvas.paste(
            icons.motorsport_asset("helmet-compact-alt", icon_size),
            (margin, rows_y),
        )
        driver_text = "   ·   ".join(
            f"{standing.code} {standing.points:g}" for standing in f1.driver_standings[:3]
        )
        canvas.text(
            (margin + scaled(78, width), rows_y + scaled(6, width)),
            driver_text or "—",
            size=26,
        )
        rows_y += scaled(68, width)
        canvas.paste(
            icons.motorsport_asset("car-compact-alt", icon_size),
            (margin, rows_y),
        )
        constructor_text = "   ·   ".join(
            f"{standing.code} {standing.points:g}" for standing in f1.constructor_standings[:3]
        )
        canvas.text(
            (margin + scaled(78, width), rows_y + scaled(6, width)),
            constructor_text or "—",
            size=26,
        )
        y = rows_y + scaled(74, width)
    canvas.rule(y)

    news_top = y + scaled(27, width)
    label(canvas, margin, news_top, "Headlines · tap to read")
    cursor = news_top + scaled(49, width)
    for article in snapshot.headlines[:3]:
        row_top = cursor - scaled(8, width)
        canvas.text((margin, cursor), "•", size=31)
        title, title_size = canvas.fit_text(
            article.title,
            width - margin * 2 - scaled(30, width),
            size=28,
            minimum=28,
        )
        canvas.draw.text(
            (margin + scaled(34, width), cursor),
            title,
            fill=INK,
            font=font(title_size),
        )
        cursor += scaled(61, width)
        canvas.link_hotspot(
            article.url,
            left=margin,
            top=row_top,
            right=width - margin,
            bottom=cursor - scaled(8, width),
        )

    footer(
        canvas,
        snapshot,
        page_index=0,
        attribution="Weather: Open-Meteo · F1: Jolpica-F1",
    )
    return canvas
