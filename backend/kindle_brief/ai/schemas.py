from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

from kindle_brief.models import BriefStory
from kindle_brief.news.dedupe import StoryCluster

RANKING_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "ranked_article_ids": {
            "type": "array",
            "items": {"type": "string"},
            "minItems": 1,
            "maxItems": 12,
        }
    },
    "required": ["ranked_article_ids"],
    "additionalProperties": False,
}

BRIEF_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "stories": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "headline": {"type": "string"},
                    "summary": {"type": "string"},
                    "why_it_matters": {"type": "string"},
                    "article_ids": {
                        "type": "array",
                        "items": {"type": "string"},
                        "minItems": 1,
                    },
                },
                "required": ["headline", "summary", "why_it_matters", "article_ids"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["stories"],
    "additionalProperties": False,
}


def validate_ranked_ids(
    payload: Mapping[str, Any],
    clusters: tuple[StoryCluster, ...],
    *,
    max_stories: int,
) -> tuple[StoryCluster, ...]:
    raw = payload.get("ranked_article_ids")
    if not isinstance(raw, list) or not raw:
        raise ValueError("ranked_article_ids must be a non-empty list")
    by_id = {cluster.representative.article_id: cluster for cluster in clusters}
    chosen: list[StoryCluster] = []
    seen: set[str] = set()
    for item in raw:
        if not isinstance(item, str) or item not in by_id:
            raise ValueError("AI ranking referenced an unknown article ID")
        if item not in seen:
            chosen.append(by_id[item])
            seen.add(item)
        if len(chosen) == max_stories:
            break
    if not chosen:
        raise ValueError("AI ranking selected no valid stories")
    return tuple(chosen)


def validate_brief_stories(
    payload: Mapping[str, Any],
    allowed_ids: Iterable[str],
    *,
    expected_max: int,
) -> tuple[BriefStory, ...]:
    allowed = set(allowed_ids)
    raw = payload.get("stories")
    if not isinstance(raw, list) or not raw or len(raw) > expected_max:
        raise ValueError("stories must be a non-empty bounded list")
    stories: list[BriefStory] = []
    referenced: set[str] = set()
    for item in raw:
        if not isinstance(item, dict):
            raise ValueError("each story must be an object")
        article_ids = item.get("article_ids")
        if not isinstance(article_ids, list) or not article_ids:
            raise ValueError("each story requires article_ids")
        if any(
            not isinstance(article_id, str) or article_id not in allowed
            for article_id in article_ids
        ):
            raise ValueError("AI summary referenced an unknown article ID")
        duplicate_ids = referenced & set(article_ids)
        if duplicate_ids:
            raise ValueError("an article ID cannot be assigned to multiple AI stories")
        referenced.update(article_ids)
        story = BriefStory(
            headline=str(item.get("headline", "")).strip(),
            summary=str(item.get("summary", "")).strip(),
            why_it_matters=str(item.get("why_it_matters", "")).strip(),
            article_ids=tuple(article_ids),
        )
        if len(story.headline) > 180 or len(story.summary) > 520 or len(story.why_it_matters) > 240:
            raise ValueError("AI story exceeds e-ink length limits")
        stories.append(story)
    return tuple(stories)
