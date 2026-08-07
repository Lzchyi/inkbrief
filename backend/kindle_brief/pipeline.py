"""Live refresh orchestration with bounded last-success cache fallback."""

from __future__ import annotations

import hashlib
import os
from collections.abc import Callable, Mapping
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, replace
from datetime import UTC, date, datetime, timedelta
from typing import Any, TypeVar, cast
from zoneinfo import ZoneInfo

import httpx

from .ai.base import AIProvider
from .ai.factory import provider_from_environment
from .ai.fallback import FallbackProvider
from .ai.resilient import ResilientProvider
from .astronomy.calculator import calculate_astronomy
from .cache import CacheError, JsonCache
from .config import DashboardConfig
from .f1.jolpica import JolpicaClient
from .lunar.converter import to_lunar_date
from .models import (
    Article,
    AstronomySnapshot,
    BriefStory,
    DashboardSnapshot,
    F1Snapshot,
    LunarDate,
    SourceStatus,
    WeatherSnapshot,
)
from .news.dedupe import StoryCluster, cluster_articles
from .news.feeds import FeedDefinition, fetch_feed
from .news.rank import rank_clusters
from .serialization import (
    SerializationError,
    articles_from_jsonable,
    astronomy_snapshot_from_jsonable,
    brief_stories_from_jsonable,
    f1_snapshot_from_jsonable,
    require_aware_utc,
    weather_snapshot_from_jsonable,
)
from .weather.open_meteo import OpenMeteoClient

T = TypeVar("T")
FeedFetcher = Callable[..., tuple[Article, ...]]


class PipelineError(RuntimeError):
    """A refresh could not produce a safely publishable snapshot."""


class EmptySnapshotError(PipelineError):
    """No provider or cache supplied content suitable for publication."""


@dataclass(frozen=True, slots=True)
class PipelineResult:
    snapshot: DashboardSnapshot
    warnings: tuple[str, ...] = ()
    cached_sections: tuple[str, ...] = ()
    ai_provider: str = "deterministic-fallback"


def _error_text(error: Exception) -> str:
    text = " ".join(str(error).split()) or type(error).__name__
    return text[:300]


def _location_prefix(config: DashboardConfig) -> str:
    location = config.location
    identity = "\0".join(
        (
            location.name,
            location.timezone,
            "" if location.latitude is None else f"{location.latitude:.8f}",
            "" if location.longitude is None else f"{location.longitude:.8f}",
        )
    )
    digest = hashlib.sha256(identity.encode("utf-8")).hexdigest()[:20]
    return f"v1/location/{digest}"


def _read_cached(
    cache: JsonCache,
    key: str,
    loader: Callable[[object], T],
    *,
    now: datetime,
    max_age: timedelta,
    warnings: list[str],
) -> T | None:
    try:
        entry = cache.read(key, allow_stale=True, now=now)
    except CacheError as error:
        warnings.append(f"Ignored invalid cache for {key}: {_error_text(error)}")
        return None
    if entry is None or now - entry.stored_at >= max_age:
        return None
    try:
        return loader(entry.value)
    except (SerializationError, TypeError, ValueError) as error:
        warnings.append(f"Ignored invalid cache value for {key}: {_error_text(error)}")
        return None


def _write_cached(
    cache: JsonCache,
    key: str,
    value: object,
    *,
    now: datetime,
    max_age: timedelta,
    warnings: list[str],
) -> None:
    try:
        cache.write(key, value, ttl=max_age, now=now)
    except (CacheError, OSError, SerializationError, TypeError, ValueError) as error:
        warnings.append(f"Could not update cache for {key}: {_error_text(error)}")


def _stale_status(status: SourceStatus, error: Exception) -> SourceStatus:
    return replace(status, stale=True, error=_error_text(error))


def _coordinates_from_jsonable(value: object) -> tuple[float, float]:
    if not isinstance(value, Mapping):
        raise SerializationError("cached coordinates must be an object")
    latitude = value.get("latitude")
    longitude = value.get("longitude")
    if (
        isinstance(latitude, bool)
        or not isinstance(latitude, (int, float))
        or isinstance(longitude, bool)
        or not isinstance(longitude, (int, float))
    ):
        raise SerializationError("cached coordinates must be numeric")
    result = (float(latitude), float(longitude))
    if not -90 <= result[0] <= 90 or not -180 <= result[1] <= 180:
        raise SerializationError("cached coordinates are outside valid bounds")
    return result


def _resolve_coordinates(
    config: DashboardConfig,
    weather_client: Any,
    cache: JsonCache,
    prefix: str,
    *,
    now: datetime,
    max_age: timedelta,
    warnings: list[str],
    cached_sections: list[str],
) -> tuple[float, float] | None:
    if config.location.latitude is not None and config.location.longitude is not None:
        return config.location.latitude, config.location.longitude
    key = f"{prefix}/coordinates"
    try:
        location = weather_client.resolve_location(config.location.name)
        result = (float(location.latitude), float(location.longitude))
        _write_cached(
            cache,
            key,
            {"latitude": result[0], "longitude": result[1]},
            now=now,
            max_age=max_age,
            warnings=warnings,
        )
        return result
    except Exception as error:
        warnings.append(f"Location lookup failed: {_error_text(error)}")
        cached = _read_cached(
            cache,
            key,
            _coordinates_from_jsonable,
            now=now,
            max_age=max_age,
            warnings=warnings,
        )
        if cached is not None:
            cached_sections.append("coordinates")
        return cached


def _weather(
    config: DashboardConfig,
    weather_client: Any,
    coordinates: tuple[float, float] | None,
    cache: JsonCache,
    prefix: str,
    *,
    now: datetime,
    max_age: timedelta,
    warnings: list[str],
    cached_sections: list[str],
) -> WeatherSnapshot | None:
    key = f"{prefix}/weather"
    try:
        if coordinates is None:
            raise PipelineError("coordinates are unavailable")
        weather = weather_client.fetch_forecast(
            latitude=coordinates[0],
            longitude=coordinates[1],
            timezone=config.location.timezone,
            fetched_at=now,
        )
        _write_cached(cache, key, weather, now=now, max_age=max_age, warnings=warnings)
        return weather
    except Exception as error:
        warnings.append(f"Weather refresh failed: {_error_text(error)}")
        cached = _read_cached(
            cache,
            key,
            weather_snapshot_from_jsonable,
            now=now,
            max_age=max_age,
            warnings=warnings,
        )
        if cached is None:
            return None
        cached_sections.append("weather")
        return replace(cached, status=_stale_status(cached.status, error))


def _astronomy(
    config: DashboardConfig,
    weather: WeatherSnapshot | None,
    coordinates: tuple[float, float] | None,
    cache: JsonCache,
    prefix: str,
    *,
    local_date: date,
    now: datetime,
    max_age: timedelta,
    warnings: list[str],
    cached_sections: list[str],
    calculator: Callable[..., AstronomySnapshot],
) -> AstronomySnapshot | None:
    key = f"{prefix}/astronomy"
    try:
        if coordinates is None:
            raise PipelineError("coordinates are unavailable")
        astronomy = calculator(
            local_date,
            latitude=coordinates[0],
            longitude=coordinates[1],
            calculated_at=now,
            timezone=config.location.timezone,
            cloud_cover_pct=weather.cloud_cover_pct if weather else None,
            precipitation_probability_pct=(weather.rain_probability_pct if weather else None),
            visibility_m=(
                weather.visibility_km * 1_000
                if weather is not None and weather.visibility_km is not None
                else None
            ),
        )
        _write_cached(cache, key, astronomy, now=now, max_age=max_age, warnings=warnings)
        return astronomy
    except Exception as error:
        warnings.append(f"Astronomy refresh failed: {_error_text(error)}")
        cached = _read_cached(
            cache,
            key,
            astronomy_snapshot_from_jsonable,
            now=now,
            max_age=max_age,
            warnings=warnings,
        )
        if cached is None:
            return None
        cached_sections.append("astronomy")
        return replace(cached, status=_stale_status(cached.status, error))


def _f1(
    config: DashboardConfig,
    f1_client: Any,
    cache: JsonCache,
    *,
    now: datetime,
    max_age: timedelta,
    warnings: list[str],
    cached_sections: list[str],
) -> F1Snapshot | None:
    if not config.f1.enabled:
        return None
    key = "v1/f1/next"
    try:
        fetched = f1_client.fetch_next(fetched_at=now)
        snapshot = replace(
            fetched,
            driver_standings=fetched.driver_standings[: config.f1.top_drivers],
            constructor_standings=(fetched.constructor_standings[: config.f1.top_constructors]),
        )
        _write_cached(cache, key, snapshot, now=now, max_age=max_age, warnings=warnings)
        return snapshot
    except Exception as error:
        warnings.append(f"F1 refresh failed: {_error_text(error)}")
        cached = _read_cached(
            cache,
            key,
            f1_snapshot_from_jsonable,
            now=now,
            max_age=max_age,
            warnings=warnings,
        )
        if cached is None:
            return None
        cached_sections.append("f1")
        return replace(cached, status=_stale_status(cached.status, error))


def _feed_key(feed: FeedDefinition) -> str:
    digest = hashlib.sha256(f"{feed.feed_id}\0{feed.url}".encode()).hexdigest()[:20]
    return f"v1/feed/{digest}"


def _remote_feed_result(
    client: httpx.Client,
    feed: FeedDefinition,
    fetcher: FeedFetcher,
    now: datetime,
) -> tuple[tuple[Article, ...] | None, Exception | None]:
    try:
        articles = tuple(fetcher(client, feed, fetched_at=now))
        if not articles:
            raise ValueError("feed returned no usable articles")
        return articles, None
    except Exception as error:
        return None, error


def _preserve_first_seen(
    fresh: tuple[Article, ...],
    cached: tuple[Article, ...],
) -> tuple[Article, ...]:
    cached_undated = {
        article.article_id: article for article in cached if article.published_at is None
    }
    preserved: list[Article] = []
    for article in fresh:
        previous = cached_undated.get(article.article_id)
        if (
            article.published_at is None
            and previous is not None
            and previous.fetched_at < article.fetched_at
        ):
            article = replace(article, fetched_at=previous.fetched_at)
        preserved.append(article)
    return tuple(preserved)


def _news(
    config: DashboardConfig,
    feeds: tuple[FeedDefinition, ...],
    client: httpx.Client,
    cache: JsonCache,
    *,
    now: datetime,
    max_age: timedelta,
    warnings: list[str],
    cached_sections: list[str],
    fetcher: FeedFetcher,
) -> tuple[tuple[Article, ...], tuple[StoryCluster, ...]]:
    enabled = tuple(feed for feed in feeds if feed.enabled)
    results: list[tuple[tuple[Article, ...] | None, Exception | None]] = []
    if enabled:
        workers = min(8, len(enabled))
        with ThreadPoolExecutor(max_workers=workers, thread_name_prefix="kindle-feed") as pool:
            results = list(
                pool.map(
                    lambda feed: _remote_feed_result(client, feed, fetcher, now),
                    enabled,
                )
            )

    collected: list[Article] = []
    for feed, (fresh, error) in zip(enabled, results, strict=True):
        key = _feed_key(feed)
        if fresh is not None:
            if feed.missing_date_policy == "first_seen":
                cached = _read_cached(
                    cache,
                    key,
                    articles_from_jsonable,
                    now=now,
                    max_age=max_age,
                    warnings=warnings,
                )
                if cached is not None:
                    fresh = _preserve_first_seen(fresh, cached)
            _write_cached(cache, key, fresh, now=now, max_age=max_age, warnings=warnings)
            collected.extend(fresh)
            continue
        assert error is not None
        warnings.append(f"Feed {feed.feed_id} failed: {_error_text(error)}")
        cached = _read_cached(
            cache,
            key,
            articles_from_jsonable,
            now=now,
            max_age=max_age,
            warnings=warnings,
        )
        if cached is not None:
            collected.extend(cached)
            cached_sections.append(f"feed:{feed.feed_id}")

    cutoff = now - timedelta(hours=config.news.max_age_hours)
    recent = tuple(
        article for article in collected if (article.published_at or article.fetched_at) >= cutoff
    )
    weights = {item.category: item.weight for item in config.news.category_weights}
    ranked = rank_clusters(
        cluster_articles(recent),
        now=now,
        category_weights=weights,
        limit=config.news.headline_limit,
    )
    return tuple(cluster.representative for cluster in ranked), ranked


def _brief_period(config: DashboardConfig, local_now: datetime) -> date:
    if local_now.timetz().replace(tzinfo=None) < config.refresh.morning_brief_local_time:
        return local_now.date() - timedelta(days=1)
    return local_now.date()


def _ground_brief_sources(
    stories: tuple[BriefStory, ...],
    clusters: tuple[StoryCluster, ...],
) -> tuple[BriefStory, ...]:
    source_by_id = {
        article.article_id: article.source for cluster in clusters for article in cluster.articles
    }
    return tuple(
        replace(
            story,
            sources=tuple(
                dict.fromkeys(
                    source_by_id[article_id]
                    for article_id in story.article_ids
                    if article_id in source_by_id
                )
            ),
        )
        for story in stories
    )


def _brief(
    config: DashboardConfig,
    clusters: tuple[StoryCluster, ...],
    cache: JsonCache,
    prefix: str,
    *,
    local_now: datetime,
    now: datetime,
    max_age: timedelta,
    warnings: list[str],
    cached_sections: list[str],
    provider: AIProvider | None,
) -> tuple[tuple[BriefStory, ...], str]:
    key = f"{prefix}/brief/{_brief_period(config, local_now).isoformat()}"
    cached = _read_cached(
        cache,
        key,
        brief_stories_from_jsonable,
        now=now,
        max_age=max_age,
        warnings=warnings,
    )
    if cached is not None:
        cached_sections.append("morning-brief")
        return cached, "daily-cache"
    if not clusters:
        return (), "not-run"

    if provider is None:
        requested = os.getenv("AI_PROVIDER", config.ai.provider).strip() or config.ai.provider
        model = os.getenv("AI_MODEL", config.ai.model or "").strip()
        try:
            provider = provider_from_environment(
                requested,
                model,
                credential_env=config.ai.credential_env,
            )
        except ValueError as error:
            raise PipelineError(f"invalid AI provider configuration: {error}") from error
    effective: AIProvider = provider
    if not isinstance(effective, (FallbackProvider, ResilientProvider)):
        effective = ResilientProvider(effective)
    try:
        stories = tuple(effective.create_brief(clusters, max_stories=config.ai.max_stories))
    except Exception as error:
        warnings.append(f"AI brief failed; used deterministic fallback: {_error_text(error)}")
        effective = FallbackProvider()
        stories = effective.create_brief(clusters, max_stories=config.ai.max_stories)
    if isinstance(effective, ResilientProvider) and effective.last_error:
        warnings.append(f"AI provider fell back locally: {effective.last_error[:300]}")
    stories = _ground_brief_sources(tuple(stories), clusters)
    if stories:
        _write_cached(cache, key, stories, now=now, max_age=max_age, warnings=warnings)
    return stories, effective.name


def refresh_live_snapshot(
    config: DashboardConfig,
    feeds: tuple[FeedDefinition, ...],
    cache: JsonCache,
    *,
    now: datetime | None = None,
    weather_client: Any | None = None,
    f1_client: Any | None = None,
    feed_client: httpx.Client | None = None,
    feed_fetcher: FeedFetcher = fetch_feed,
    ai_provider: AIProvider | None = None,
    astronomy_calculator: Callable[..., AstronomySnapshot] = calculate_astronomy,
    lunar_converter: Callable[[date], LunarDate] = to_lunar_date,
) -> PipelineResult:
    """Fetch a coherent live snapshot, falling back only to bounded cached successes."""

    effective_now = require_aware_utc(now or datetime.now(UTC), field_name="now")
    local_now = effective_now.astimezone(ZoneInfo(config.location.timezone))
    max_age = timedelta(hours=config.refresh.max_stale_hours)
    warnings: list[str] = []
    cached_sections: list[str] = []
    prefix = _location_prefix(config)

    needs_http = weather_client is None or f1_client is None or feed_client is None
    owned_http = (
        httpx.Client(
            timeout=config.refresh.request_timeout_seconds,
            follow_redirects=True,
        )
        if needs_http
        else None
    )
    effective_weather = weather_client or OpenMeteoClient(client=owned_http)
    effective_f1 = f1_client or JolpicaClient(client=owned_http)
    effective_feed = feed_client or cast(httpx.Client, owned_http)
    try:
        coordinates = _resolve_coordinates(
            config,
            effective_weather,
            cache,
            prefix,
            now=effective_now,
            max_age=max_age,
            warnings=warnings,
            cached_sections=cached_sections,
        )
        weather = _weather(
            config,
            effective_weather,
            coordinates,
            cache,
            prefix,
            now=effective_now,
            max_age=max_age,
            warnings=warnings,
            cached_sections=cached_sections,
        )
        astronomy = _astronomy(
            config,
            weather,
            coordinates,
            cache,
            prefix,
            local_date=local_now.date(),
            now=effective_now,
            max_age=max_age,
            warnings=warnings,
            cached_sections=cached_sections,
            calculator=astronomy_calculator,
        )
        f1 = _f1(
            config,
            effective_f1,
            cache,
            now=effective_now,
            max_age=max_age,
            warnings=warnings,
            cached_sections=cached_sections,
        )
        headlines, clusters = _news(
            config,
            feeds,
            effective_feed,
            cache,
            now=effective_now,
            max_age=max_age,
            warnings=warnings,
            cached_sections=cached_sections,
            fetcher=feed_fetcher,
        )
        brief, provider_name = _brief(
            config,
            clusters,
            cache,
            prefix,
            local_now=local_now,
            now=effective_now,
            max_age=max_age,
            warnings=warnings,
            cached_sections=cached_sections,
            provider=ai_provider,
        )
    finally:
        if owned_http is not None:
            owned_http.close()

    try:
        lunar = lunar_converter(local_now.date())
    except Exception as error:
        warnings.append(f"Lunar conversion failed: {_error_text(error)}")
        lunar = LunarDate(local_now.date(), local_now.date().isoformat())

    missing_expected = (
        weather is None
        or astronomy is None
        or (config.f1.enabled and f1 is None)
        or (any(feed.enabled for feed in feeds) and not headlines)
    )
    snapshot = DashboardSnapshot(
        generated_at=effective_now,
        timezone=config.location.timezone,
        location_name=config.location.name,
        lunar_date=lunar,
        weather=weather,
        astronomy=astronomy,
        f1=f1,
        headlines=headlines,
        morning_brief=brief,
        degraded=(
            bool(warnings)
            or missing_expected
            or any(section != "morning-brief" for section in cached_sections)
        ),
    )
    if weather is None and f1 is None and not headlines and not brief:
        raise EmptySnapshotError(
            "refusing to publish: live providers failed and no usable cached content exists"
        )
    _write_cached(
        cache,
        f"{prefix}/snapshot",
        snapshot,
        now=effective_now,
        max_age=max_age,
        warnings=warnings,
    )
    return PipelineResult(
        snapshot=snapshot,
        warnings=tuple(warnings),
        cached_sections=tuple(dict.fromkeys(cached_sections)),
        ai_provider=provider_name,
    )
