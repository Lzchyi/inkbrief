from __future__ import annotations

from abc import ABC, abstractmethod

from kindle_brief.models import BriefStory
from kindle_brief.news.dedupe import StoryCluster


class AIProviderError(RuntimeError):
    """A transport, quota, response, or schema failure safe to fall back from."""


class AIProvider(ABC):
    name: str

    @abstractmethod
    def rank_articles(
        self,
        clusters: tuple[StoryCluster, ...],
        *,
        max_stories: int,
    ) -> tuple[StoryCluster, ...]:
        """Select and order source-grounded clusters."""

    @abstractmethod
    def summarize_articles(
        self,
        clusters: tuple[StoryCluster, ...],
    ) -> tuple[BriefStory, ...]:
        """Return summaries that reference only supplied article IDs."""

    def create_brief(
        self,
        clusters: tuple[StoryCluster, ...],
        *,
        max_stories: int,
    ) -> tuple[BriefStory, ...]:
        selected = self.rank_articles(clusters, max_stories=max_stories)
        return self.summarize_articles(selected)
