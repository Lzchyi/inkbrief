from __future__ import annotations

from dataclasses import dataclass
from difflib import SequenceMatcher

from kindle_brief.models import Article

from .normalize import canonical_url, normalized_title, title_tokens


@dataclass(frozen=True, slots=True)
class StoryCluster:
    representative: Article
    articles: tuple[Article, ...]

    @property
    def article_ids(self) -> tuple[str, ...]:
        return tuple(article.article_id for article in self.articles)

    @property
    def sources(self) -> tuple[str, ...]:
        return tuple(dict.fromkeys(article.source for article in self.articles))


def _title_similarity(left: Article, right: Article) -> float:
    left_tokens = title_tokens(left.title)
    right_tokens = title_tokens(right.title)
    if not left_tokens or not right_tokens:
        return 0.0
    jaccard = len(left_tokens & right_tokens) / len(left_tokens | right_tokens)
    sequence = SequenceMatcher(
        None, normalized_title(left.title), normalized_title(right.title)
    ).ratio()
    return max(jaccard, sequence)


def _same_story(left: Article, right: Article, *, threshold: float) -> bool:
    if canonical_url(left.url) == canonical_url(right.url):
        return True
    if left.category != right.category:
        return False
    return _title_similarity(left, right) >= threshold


def cluster_articles(
    articles: list[Article] | tuple[Article, ...], *, threshold: float = 0.82
) -> tuple[StoryCluster, ...]:
    ordered = sorted(
        articles,
        key=lambda item: (item.published_at or item.fetched_at, item.article_id),
        reverse=True,
    )
    clusters: list[list[Article]] = []
    for article in ordered:
        target = next(
            (
                cluster
                for cluster in clusters
                if any(_same_story(article, item, threshold=threshold) for item in cluster)
            ),
            None,
        )
        if target is None:
            clusters.append([article])
        else:
            target.append(article)
    return tuple(
        StoryCluster(representative=cluster[0], articles=tuple(cluster)) for cluster in clusters
    )
