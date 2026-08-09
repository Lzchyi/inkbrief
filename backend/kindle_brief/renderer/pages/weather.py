from __future__ import annotations

from kindle_brief.models import DashboardSnapshot
from kindle_brief.renderer import icons
from kindle_brief.renderer.formatting import clock, is_night, percentage, temperature
from kindle_brief.renderer.moon import moon_phase_image
from kindle_brief.renderer.theme import INK, MUTED, PANEL, SECONDARY, font, scaled

from .common import footer, label, metric, page_canvas


def render(snapshot: DashboardSnapshot, width: int, height: int):  # type: ignore[no-untyped-def]
    canvas, y = page_canvas(snapshot, width, height)
    margin = scaled(58, width)
    weather = snapshot.weather
    astronomy = snapshot.astronomy
    if weather is None:
        canvas.text(
            (width // 2, y + scaled(180, width)), "Weather unavailable", size=42, anchor="ma"
        )
        footer(canvas, snapshot, page_index=1, attribution="Weather data: Open-Meteo.com")
        return canvas

    label(canvas, margin, y, snapshot.location_name)
    hero_icon_size = scaled(240, width)
    canvas.paste(
        icons.weather_asset(
            weather.condition_code,
            hero_icon_size,
            is_night=is_night(
                snapshot.generated_at,
                snapshot.timezone,
                sunrise=astronomy.sunrise if astronomy else None,
                sunset=astronomy.sunset if astronomy else None,
            ),
            wind_kph=weather.wind_kph,
            visibility_km=weather.visibility_km,
            cloud_cover_pct=weather.cloud_cover_pct,
        ),
        (margin, y + scaled(32, width)),
    )
    canvas.text(
        (scaled(330, width), y + scaled(8, width)), temperature(weather.temperature_c), size=96
    )
    condition, condition_size = canvas.fit_text(
        weather.condition_text,
        width - scaled(595, width) - margin,
        size=36,
        minimum=30,
    )
    canvas.draw.text(
        (scaled(595, width), y + scaled(42, width)),
        condition,
        fill=INK,
        font=font(condition_size),
    )
    canvas.text(
        (scaled(595, width), y + scaled(108, width)),
        (
            f"Feels {temperature(weather.feels_like_c)} · "
            f"H {temperature(weather.high_c)} · L {temperature(weather.low_c)}"
        ),
        size=26,
        fill=SECONDARY,
    )

    grid_top = y + scaled(270, width)
    grid_bottom = grid_top + scaled(150, width)
    canvas.draw.rounded_rectangle(
        (margin, grid_top, width - margin, grid_bottom),
        radius=scaled(18, width),
        fill=PANEL,
    )
    columns = [
        margin + scaled(30, width),
        scaled(300, width),
        scaled(550, width),
        scaled(800, width),
    ]
    metric(
        canvas.draw,
        canvas,
        x=columns[0],
        y=grid_top + scaled(23, width),
        title="Humidity",
        value=percentage(weather.humidity_pct),
    )
    metric(
        canvas.draw,
        canvas,
        x=columns[1],
        y=grid_top + scaled(23, width),
        title="Rain",
        value=percentage(weather.rain_probability_pct),
    )
    metric(
        canvas.draw,
        canvas,
        x=columns[2],
        y=grid_top + scaled(23, width),
        title="Wind",
        value=f"{round(weather.wind_kph or 0)} km/h",
    )
    metric(
        canvas.draw,
        canvas,
        x=columns[3],
        y=grid_top + scaled(23, width),
        title="UV",
        value=f"{weather.uv_index or 0:g}",
    )

    y = grid_bottom + scaled(38, width)
    label(canvas, margin, y, "Hourly")
    hour_top = y + scaled(45, width)
    hourly = weather.hourly[:6]
    cell_width = (width - margin * 2) / max(1, len(hourly))
    for index, item in enumerate(hourly):
        cx = round(margin + cell_width * (index + 0.5))
        canvas.text(
            (cx, hour_top),
            clock(item.timestamp, snapshot.timezone),
            size=21,
            fill=MUTED,
            anchor="ma",
        )
        hourly_icon_size = scaled(76, width)
        canvas.paste(
            icons.weather_asset(
                item.condition_code,
                hourly_icon_size,
                is_night=is_night(
                    item.timestamp,
                    snapshot.timezone,
                    sunrise=astronomy.sunrise if astronomy else None,
                    sunset=astronomy.sunset if astronomy else None,
                ),
                cloud_cover_pct=item.cloud_cover_pct,
            ),
            (round(cx - hourly_icon_size / 2), hour_top + scaled(36, width)),
        )
        canvas.text(
            (cx, hour_top + scaled(116, width)),
            temperature(item.temperature_c),
            size=28,
            anchor="ma",
        )
        canvas.text(
            (cx, hour_top + scaled(158, width)),
            percentage(item.rain_probability_pct),
            size=19,
            fill=MUTED,
            anchor="ma",
        )
    y = hour_top + scaled(210, width)
    canvas.rule(y)

    sky_top = y + scaled(34, width)
    label(canvas, margin, sky_top, "Sun & Moon")
    moon_size = scaled(170, width)
    if astronomy:
        moon = moon_phase_image(moon_size, astronomy.phase_fraction * 360)
        canvas.paste(moon, (margin, sky_top + scaled(50, width)))
        canvas.text(
            (margin + scaled(215, width), sky_top + scaled(50, width)),
            astronomy.phase_name,
            size=34,
        )
        canvas.text(
            (margin + scaled(215, width), sky_top + scaled(105, width)),
            f"Illumination {percentage(astronomy.illumination_pct)}",
            size=25,
            fill=SECONDARY,
        )
        horizon_size = scaled(76, width)
        horizon_y = sky_top + scaled(139, width)
        moonrise_x = margin + scaled(175, width)
        moonset_x = margin + scaled(385, width)
        canvas.paste(
            icons.moon_horizon_asset("moonrise", horizon_size),
            (moonrise_x, horizon_y),
        )
        canvas.paste(
            icons.moon_horizon_asset("moonset", horizon_size),
            (moonset_x, horizon_y),
        )
        for scene_x, title, event_time in (
            (moonrise_x, "Moonrise", astronomy.moonrise),
            (moonset_x, "Moonset", astronomy.moonset),
        ):
            text_x = scene_x + scaled(80, width)
            canvas.text(
                (text_x, horizon_y + scaled(12, width)),
                title,
                size=18,
                fill=MUTED,
            )
            canvas.text(
                (text_x, horizon_y + scaled(39, width)),
                clock(event_time, snapshot.timezone),
                size=24,
                fill=SECONDARY,
            )
        sun_x = scaled(690, width)
        canvas.text((sun_x, sky_top + scaled(53, width)), "Sunrise", size=20, fill=MUTED)
        canvas.text(
            (sun_x, sky_top + scaled(84, width)),
            clock(astronomy.sunrise, snapshot.timezone),
            size=32,
        )
        canvas.text((sun_x, sky_top + scaled(136, width)), "Sunset", size=20, fill=MUTED)
        canvas.text(
            (sun_x, sky_top + scaled(171, width)),
            clock(astronomy.sunset, snapshot.timezone),
            size=32,
        )
    y = sky_top + scaled(250, width)
    canvas.rule(y)

    stars_top = y + scaled(32, width)
    label(canvas, margin, stars_top, "Stargazing")
    rating = astronomy.stargazing_rating if astronomy else "Unavailable"
    canvas.text((margin, stars_top + scaled(46, width)), rating, size=48)
    if astronomy and astronomy.best_sky_start:
        window = (
            f"Best sky: {clock(astronomy.best_sky_start, snapshot.timezone)}–"
            f"{clock(astronomy.best_sky_end, snapshot.timezone)}"
        )
    else:
        window = "No reliable viewing window"
    canvas.text(
        (margin + scaled(310, width), stars_top + scaled(55, width)),
        window,
        size=27,
        fill=SECONDARY,
    )
    canvas.text(
        (margin + scaled(310, width), stars_top + scaled(103, width)),
        (
            f"Cloud {percentage(weather.cloud_cover_pct)} · "
            f"Visibility {weather.visibility_km or 0:g} km"
        ),
        size=22,
        fill=MUTED,
    )

    footer(canvas, snapshot, page_index=1, attribution="Weather data: Open-Meteo.com · CC BY 4.0")
    return canvas
