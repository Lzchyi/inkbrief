from __future__ import annotations

from kindle_brief.models import BriefStory
from kindle_brief.news.dedupe import StoryCluster

from .base import AIProvider, AIProviderError
from .fallback import FallbackProvider


class ResilientProvider(AIProvider):
    """Fall back locally for any remote transport, quota, parse, or schema error."""

    def __init__(self, primary: AIProvider, fallback: AIProvider | None = None) -> None:
        self.primary = primary
        self.fallback = fallback or FallbackProvider()
        self.name = f"{primary.name}-with-fallback"
        self.last_error: str | None = None

    def rank_articles(
        self,
        clusters: tuple[StoryCluster, ...],
        *,
        max_stories: int,
    ) -> tuple[StoryCluster, ...]:
        try:
            return self.primary.rank_articles(clusters, max_stories=max_stories)
        except (AIProviderError, ValueError, KeyError, TypeError) as error:
            self.last_error = str(error)
            return self.fallback.rank_articles(clusters, max_stories=max_stories)

    def summarize_articles(
        self,
        clusters: tuple[StoryCluster, ...],
    ) -> tuple[BriefStory, ...]:
        try:
            return self.primary.summarize_articles(clusters)
        except (AIProviderError, ValueError, KeyError, TypeError) as error:
            self.last_error = str(error)
            return self.fallback.summarize_articles(clusters)
