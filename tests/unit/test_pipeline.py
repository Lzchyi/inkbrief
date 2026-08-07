from __future__ import annotations

from dataclasses import replace
from datetime import date, timedelta
from typing import Any

import pytest
from kindle_brief.ai.fallback import FallbackProvider
from kindle_brief.cache import JsonCache
from kindle_brief.config import config_from_mapping
from kindle_brief.demo import demo_snapshot
from kindle_brief.models import Article, LunarDate
from kindle_brief.news.feeds import FeedDefinition
from kindle_brief.pipeline import EmptySnapshotError, refresh_live_snapshot
from kindle_brief.renderer.formatting import snapshot_is_stale


class _WeatherClient:
    def __init__(self, *, broken: bool = False) -> None:
        self.broken = broken

    def fetch_forecast(self, **_: Any):  # type: ignore[no-untyped-def]
        if self.broken:
            raise RuntimeError("weather unavailable")
        return demo_snapshot().weather


class _F1Client:
    def __init__(self, *, broken: bool = False) -> None:
        self.broken = broken

    def fetch_next(self, **_: Any):  # type: ignore[no-untyped-def]
        if self.broken:
            raise RuntimeError("F1 unavailable")
        return demo_snapshot().f1


class _CountingFallback(FallbackProvider):
    name = "counting-fallback"

    def __init__(self) -> None:
        self.calls = 0

    def create_brief(self, clusters, *, max_stories):  # type: ignore[no-untyped-def]
        self.calls += 1
        return super().create_brief(clusters, max_stories=max_stories)


def _config():  # type: ignore[no-untyped-def]
    return config_from_mapping(
        {
            "location": {
                "name": "Kuala Lumpur",
                "latitude": 3.139,
                "longitude": 101.6869,
                "timezone": "Asia/Kuala_Lumpur",
            }
        }
    )


def _feed() -> FeedDefinition:
    return FeedDefinition(
        "test-feed",
        "Test Feed",
        "https://example.com/feed.xml",
        "science",
        "Example",
    )


def _lunar(value: date) -> LunarDate:
    return LunarDate(value, "农历测试")


def test_live_refresh_reuses_bounded_last_success_and_daily_brief(tmp_path) -> None:
    now = demo_snapshot().generated_at
    article = replace(
        demo_snapshot().headlines[0],
        fetched_at=now,
        published_at=now,
    )
    provider = _CountingFallback()
    cache = JsonCache(tmp_path)

    first = refresh_live_snapshot(
        _config(),
        (_feed(),),
        cache,
        now=now,
        weather_client=_WeatherClient(),
        f1_client=_F1Client(),
        feed_client=object(),  # type: ignore[arg-type]
        feed_fetcher=lambda *_args, **_kwargs: (article,),
        ai_provider=provider,
        astronomy_calculator=lambda *_args, **_kwargs: demo_snapshot().astronomy,
        lunar_converter=_lunar,
    )
    assert first.snapshot.degraded is False
    assert provider.calls == 1

    def broken_feed(*_args, **_kwargs):  # type: ignore[no-untyped-def]
        raise RuntimeError("feed unavailable")

    def broken_astronomy(*_args, **_kwargs):  # type: ignore[no-untyped-def]
        raise RuntimeError("astronomy unavailable")

    second = refresh_live_snapshot(
        _config(),
        (_feed(),),
        cache,
        now=now + timedelta(hours=1),
        weather_client=_WeatherClient(broken=True),
        f1_client=_F1Client(broken=True),
        feed_client=object(),  # type: ignore[arg-type]
        feed_fetcher=broken_feed,
        ai_provider=provider,
        astronomy_calculator=broken_astronomy,
        lunar_converter=_lunar,
    )

    assert {"weather", "astronomy", "f1", "feed:test-feed"} <= set(second.cached_sections)
    assert second.snapshot.weather is not None and second.snapshot.weather.status.stale
    assert second.snapshot.degraded is True
    assert snapshot_is_stale(second.snapshot) is True
    assert second.snapshot.headlines == (article,)
    assert second.snapshot.morning_brief[0].sources == (article.source,)
    assert provider.calls == 1


def test_cached_daily_brief_retains_sources_when_hourly_headlines_rotate(tmp_path) -> None:
    now = demo_snapshot().generated_at
    first_article = replace(
        demo_snapshot().headlines[0],
        article_id="first-story",
        source="Bernama",
        fetched_at=now,
        published_at=now,
    )
    next_article = replace(
        demo_snapshot().headlines[1],
        article_id="next-story",
        source="BBC Sport",
        fetched_at=now + timedelta(hours=1),
        published_at=now + timedelta(hours=1),
    )
    old_article = replace(
        demo_snapshot().headlines[2],
        article_id="old-story",
        source="Old Publisher",
        fetched_at=now + timedelta(hours=2),
        published_at=now - timedelta(hours=40),
    )
    provider = _CountingFallback()
    cache = JsonCache(tmp_path)
    common = {
        "weather_client": _WeatherClient(),
        "f1_client": _F1Client(),
        "feed_client": object(),
        "ai_provider": provider,
        "astronomy_calculator": lambda *_args, **_kwargs: demo_snapshot().astronomy,
        "lunar_converter": _lunar,
    }

    first = refresh_live_snapshot(
        _config(),
        (_feed(),),
        cache,
        now=now,
        feed_fetcher=lambda *_args, **_kwargs: (first_article,),
        **common,  # type: ignore[arg-type]
    )
    second = refresh_live_snapshot(
        _config(),
        (_feed(),),
        cache,
        now=now + timedelta(hours=1),
        feed_fetcher=lambda *_args, **_kwargs: (next_article,),
        **common,  # type: ignore[arg-type]
    )
    third = refresh_live_snapshot(
        _config(),
        (_feed(),),
        cache,
        now=now + timedelta(hours=2),
        feed_fetcher=lambda *_args, **_kwargs: (old_article,),
        **common,  # type: ignore[arg-type]
    )

    assert first.snapshot.morning_brief[0].sources == ("Bernama",)
    assert second.snapshot.headlines == (next_article,)
    assert second.snapshot.morning_brief[0].article_ids == ("first-story",)
    assert second.snapshot.morning_brief[0].sources == ("Bernama",)
    assert third.snapshot.headlines == ()
    assert third.snapshot.morning_brief[0].sources == ("Bernama",)
    assert provider.calls == 1


def test_live_refresh_refuses_content_empty_cold_publish(tmp_path) -> None:
    def broken(*_args, **_kwargs):  # type: ignore[no-untyped-def]
        raise RuntimeError("unavailable")

    with pytest.raises(EmptySnapshotError, match="refusing to publish"):
        refresh_live_snapshot(
            _config(),
            (_feed(),),
            JsonCache(tmp_path),
            now=demo_snapshot().generated_at,
            weather_client=_WeatherClient(broken=True),
            f1_client=_F1Client(broken=True),
            feed_client=object(),  # type: ignore[arg-type]
            feed_fetcher=broken,
            astronomy_calculator=broken,
            lunar_converter=_lunar,
        )


def test_cached_news_alone_marks_snapshot_degraded(tmp_path) -> None:
    now = demo_snapshot().generated_at
    article: Article = replace(demo_snapshot().headlines[0], fetched_at=now, published_at=now)
    cache = JsonCache(tmp_path)
    common = {
        "weather_client": _WeatherClient(),
        "f1_client": _F1Client(),
        "feed_client": object(),
        "ai_provider": FallbackProvider(),
        "astronomy_calculator": lambda *_args, **_kwargs: demo_snapshot().astronomy,
        "lunar_converter": _lunar,
    }
    refresh_live_snapshot(
        _config(),
        (_feed(),),
        cache,
        now=now,
        feed_fetcher=lambda *_args, **_kwargs: (article,),
        **common,  # type: ignore[arg-type]
    )

    def broken_feed(*_args, **_kwargs):  # type: ignore[no-untyped-def]
        raise RuntimeError("feed unavailable")

    result = refresh_live_snapshot(
        _config(),
        (_feed(),),
        cache,
        now=now + timedelta(minutes=30),
        feed_fetcher=broken_feed,
        **common,  # type: ignore[arg-type]
    )

    assert result.cached_sections == ("feed:test-feed", "morning-brief")
    assert result.snapshot.degraded is True
    assert snapshot_is_stale(result.snapshot) is True


def test_successful_refresh_preserves_first_seen_for_recurring_undated_article(tmp_path) -> None:
    now = demo_snapshot().generated_at
    article = replace(
        demo_snapshot().headlines[0],
        fetched_at=now,
        published_at=None,
    )
    cache = JsonCache(tmp_path)

    def recurring_feed(*_args, fetched_at, **_kwargs):  # type: ignore[no-untyped-def]
        return (replace(article, fetched_at=fetched_at),)

    common = {
        "weather_client": _WeatherClient(),
        "f1_client": _F1Client(),
        "feed_client": object(),
        "feed_fetcher": recurring_feed,
        "ai_provider": FallbackProvider(),
        "astronomy_calculator": lambda *_args, **_kwargs: demo_snapshot().astronomy,
        "lunar_converter": _lunar,
    }
    first = refresh_live_snapshot(
        _config(),
        (_feed(),),
        cache,
        now=now,
        **common,  # type: ignore[arg-type]
    )
    second = refresh_live_snapshot(
        _config(),
        (_feed(),),
        cache,
        now=now + timedelta(hours=1),
        **common,  # type: ignore[arg-type]
    )
    expired = refresh_live_snapshot(
        _config(),
        (_feed(),),
        cache,
        now=now + timedelta(hours=37),
        **common,  # type: ignore[arg-type]
    )

    assert first.snapshot.headlines[0].fetched_at == now
    assert second.snapshot.headlines[0].fetched_at == now
    assert expired.snapshot.headlines == ()
