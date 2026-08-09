from __future__ import annotations

from dataclasses import replace

import pytest
from kindle_brief.demo import demo_snapshot
from kindle_brief.serialization import (
    SerializationError,
    brief_story_from_jsonable,
    canonical_json_dumps,
    dashboard_snapshot_from_json,
)


def test_dashboard_snapshot_json_round_trip_preserves_nested_models() -> None:
    original = demo_snapshot()
    stored_story = replace(
        original.morning_brief[0],
        sources=("Bernama",),
        article_urls=("https://example.com/story",),
    )
    snapshot = replace(original, degraded=True, morning_brief=(stored_story,))

    decoded = dashboard_snapshot_from_json(canonical_json_dumps(snapshot))

    assert decoded == snapshot
    assert decoded.degraded is True
    assert decoded.morning_brief[0].article_urls == ("https://example.com/story",)


def test_legacy_cached_brief_without_sources_remains_readable() -> None:
    story = brief_story_from_jsonable(
        {
            "headline": "A grounded headline",
            "summary": "A grounded summary.",
            "why_it_matters": "It affects readers.",
            "article_ids": ["article-1"],
        }
    )

    assert story.sources == ()
    assert story.article_urls == ()


def test_dashboard_snapshot_json_rejects_naive_generated_time() -> None:
    payload = canonical_json_dumps(demo_snapshot()).replace(
        '"generated_at":"2026-08-07T23:30:00Z"',
        '"generated_at":"2026-08-07T23:30:00"',
    )

    with pytest.raises(SerializationError, match="timezone-aware"):
        dashboard_snapshot_from_json(payload)
