from __future__ import annotations

import re

from kindle_brief.models import BriefStory
from kindle_brief.news.dedupe import StoryCluster

from .base import AIProvider

_SENTENCE = re.compile(r"(?<=[.!?])\s+")
_WHY = {
    "malaysia": "This may affect people, policy, or public life in Malaysia.",
    "ai_tech": "This may shape the tools and platforms used to build technology.",
    "apple_dev": "This may affect Apple users or software developers.",
    "business": "This may influence Malaysia's economy, markets, or companies.",
    "insurance": "This may affect coverage, regulation, or financial protection.",
    "f1": "This matters for the current Formula 1 season.",
    "science": "This adds useful evidence or context about science and space.",
    "travel": "This may be useful for planning or everyday technology choices.",
}


def _truncate(value: str, limit: int) -> str:
    value = " ".join(value.split())
    if len(value) <= limit:
        return value
    shortened = value[: limit - 1].rsplit(" ", 1)[0].rstrip(" ,;:-")
    return f"{shortened}…"


def extractive_summary(cluster: StoryCluster) -> str:
    excerpts = [article.excerpt for article in cluster.articles if article.excerpt.strip()]
    if not excerpts:
        return "Open the source for the full report."
    sentences = [part.strip() for part in _SENTENCE.split(excerpts[0]) if part.strip()]
    summary = " ".join(sentences[:2]) or excerpts[0]
    return _truncate(summary, 360)


class FallbackProvider(AIProvider):
    name = "deterministic-fallback"

    def rank_articles(
        self,
        clusters: tuple[StoryCluster, ...],
        *,
        max_stories: int,
    ) -> tuple[StoryCluster, ...]:
        return clusters[:max_stories]

    def summarize_articles(
        self,
        clusters: tuple[StoryCluster, ...],
    ) -> tuple[BriefStory, ...]:
        return tuple(
            BriefStory(
                headline=_truncate(cluster.representative.title, 150),
                summary=extractive_summary(cluster),
                why_it_matters=_WHY.get(
                    cluster.representative.category,
                    "This was selected for recency, relevance, and source quality.",
                ),
                article_ids=cluster.article_ids,
                article_urls=tuple(article.url for article in cluster.articles),
            )
            for cluster in clusters
        )
