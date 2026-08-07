"""Deterministic fixture data for offline renderer development and CI."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

from .models import (
    Article,
    AstronomySnapshot,
    BriefStory,
    DashboardSnapshot,
    F1Session,
    F1Snapshot,
    HourlyForecast,
    LunarDate,
    SourceStatus,
    Standing,
    WeatherSnapshot,
)


def demo_snapshot() -> DashboardSnapshot:
    generated = datetime(2026, 8, 7, 23, 30, tzinfo=UTC)
    open_meteo = SourceStatus(
        "open-meteo",
        generated,
        attribution="Weather data: Open-Meteo.com",
        license_url="https://creativecommons.org/licenses/by/4.0/",
    )
    jolpica = SourceStatus(
        "jolpica-f1",
        generated,
        attribution="Jolpica-F1",
        license_url="https://creativecommons.org/licenses/by-nc-sa/4.0/",
    )
    astronomy_status = SourceStatus(
        "astronomy-engine",
        generated,
        attribution="Astronomy Engine",
    )
    hourly = tuple(
        HourlyForecast(
            timestamp=generated + timedelta(hours=index),
            temperature_c=28 + (index % 3),
            condition_code="61" if index in {2, 3} else "3",
            condition_text="Rain" if index in {2, 3} else "Cloudy",
            rain_probability_pct=70 if index in {2, 3} else 30,
            cloud_cover_pct=80 - index * 4,
        )
        for index in range(8)
    )
    weather = WeatherSnapshot(
        observed_at=generated,
        temperature_c=29,
        condition_code="3",
        condition_text="Mostly Cloudy",
        high_c=32,
        low_c=25,
        humidity_pct=82,
        rain_probability_pct=68,
        status=open_meteo,
        feels_like_c=33,
        wind_kph=11,
        uv_index=5,
        cloud_cover_pct=76,
        hourly=hourly,
        wind_direction_deg=210,
        visibility_km=9.5,
        precipitation_mm=0,
    )
    astronomy = AstronomySnapshot(
        calculated_at=generated,
        sunrise=datetime(2026, 8, 7, 23, 12, tzinfo=UTC),
        sunset=datetime(2026, 8, 8, 11, 23, tzinfo=UTC),
        phase_name="Waning Crescent",
        phase_fraction=0.82,
        illumination_pct=29,
        status=astronomy_status,
        moonrise=datetime(2026, 8, 7, 18, 40, tzinfo=UTC),
        moonset=datetime(2026, 8, 8, 6, 52, tzinfo=UTC),
        best_sky_start=datetime(2026, 8, 8, 18, 0, tzinfo=UTC),
        best_sky_end=datetime(2026, 8, 8, 20, 30, tzinfo=UTC),
        stargazing_rating="Fair",
    )
    sessions = (
        F1Session("Practice 1", generated + timedelta(hours=10)),
        F1Session("Sprint Qualifying", generated + timedelta(hours=17)),
        F1Session("Sprint", generated + timedelta(days=1, hours=8)),
        F1Session("Qualifying", generated + timedelta(days=1, hours=14)),
        F1Session("Race", generated + timedelta(days=2, hours=13)),
    )
    f1 = F1Snapshot(
        season=2026,
        round_number=14,
        event_name="Belgian Grand Prix",
        circuit_name="Circuit de Spa-Francorchamps",
        sessions=sessions,
        driver_standings=(
            Standing(1, "NOR", "Lando Norris", 245),
            Standing(2, "PIA", "Oscar Piastri", 231),
            Standing(3, "VER", "Max Verstappen", 198),
        ),
        constructor_standings=(
            Standing(1, "MCL", "McLaren", 476),
            Standing(2, "RBR", "Red Bull Racing", 344),
            Standing(3, "FER", "Ferrari", 301),
        ),
        status=jolpica,
        circuit_id="spa",
    )
    categories = (
        "malaysia",
        "ai_tech",
        "business",
        "insurance",
        "f1",
        "science",
        "apple_dev",
        "malaysia",
        "science",
        "apple_dev",
        "business",
        "f1",
        "science",
        "ai_tech",
        "business",
    )
    headlines = tuple(
        Article(
            article_id=f"demo-{index}",
            title=title,
            url=f"https://example.invalid/story-{index}",
            source=source,
            category=categories[index],
            fetched_at=generated,
            published_at=generated - timedelta(minutes=index * 17),
            excerpt=summary,
        )
        for index, (title, source, summary) in enumerate(
            (
                (
                    "Malaysia announces a new national digital initiative",
                    "Bernama",
                    "The programme sets out its first implementation milestones.",
                ),
                (
                    "A compact AI model improves structured extraction",
                    "OpenAI",
                    "The release focuses on reliable structured output.",
                ),
                (
                    "Regional markets respond to the latest policy outlook",
                    "Bursa Malaysia",
                    "Investors assessed the updated outlook.",
                ),
                (
                    "Insurance industry publishes a consumer guidance update",
                    "Industry source",
                    "The guidance explains coverage questions.",
                ),
                (
                    "Teams prepare for an unusual sprint weekend",
                    "FIA",
                    "The weekend uses a revised session sequence.",
                ),
                (
                    "A space telescope maps a distant stellar nursery",
                    "NASA",
                    "The observations reveal new structural detail.",
                ),
                (
                    "Developers receive a new set of platform tools",
                    "Apple Developer",
                    "The tools refine testing and deployment.",
                ),
                (
                    "Malaysia expands a public transport pilot",
                    "Free Malaysia Today",
                    "The pilot adds routes and usage targets.",
                ),
                (
                    "Researchers publish a clearer lunar surface map",
                    "ESA",
                    "The map combines several observation campaigns.",
                ),
                (
                    "A major open-source framework reaches a stable release",
                    "Swift.org",
                    "The release resolves long-running compatibility issues.",
                ),
                (
                    "Central bank data shows steady household demand",
                    "Bernama",
                    "The latest release tracks household activity.",
                ),
                (
                    "Formula 1 confirms the next session timetable",
                    "BBC Sport",
                    "The schedule includes local start times.",
                ),
                (
                    "Scientists refine a near-Earth object forecast",
                    "NASA",
                    "Updated observations narrow the uncertainty range.",
                ),
                (
                    "A developer tool adds safer dependency checks",
                    "Ars Technica",
                    "The update flags risky packages earlier.",
                ),
                (
                    "Businesses trial a lower-energy cooling system",
                    "Bursa Malaysia",
                    "Early measurements show reduced energy use.",
                ),
            )
        )
    )
    brief = tuple(
        BriefStory(
            headline=article.title,
            summary=article.excerpt,
            why_it_matters="It may affect decisions, tools, or daily life in the coming weeks.",
            article_ids=(article.article_id,),
        )
        for article in headlines[:7]
    )
    return DashboardSnapshot(
        generated_at=generated,
        timezone="Asia/Kuala_Lumpur",
        location_name="Kuala Lumpur",
        lunar_date=LunarDate(date(2026, 8, 8), "农历六月廿六"),
        weather=weather,
        astronomy=astronomy,
        f1=f1,
        headlines=headlines,
        morning_brief=brief,
    )
