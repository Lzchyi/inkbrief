from __future__ import annotations

import math
from collections import Counter
from datetime import UTC, datetime

from .dedupe import StoryCluster

_LOW_VALUE = {
    "according to leaks",
    "celebrity",
    "discount",
    "grab the",
    "last day to get",
    "on sale",
    "shocking",
    "you won't believe",
    "rumour",
    "rumor",
    "save $",
    "viral",
    "best ever",
}
_DIVERSITY_SCORE_WINDOW = 5.0


def cluster_score(
    cluster: StoryCluster,
    *,
    now: datetime,
    category_weights: dict[str, float],
) -> float:
    now = now.astimezone(UTC)
    article = cluster.representative
    timestamp = article.published_at or article.fetched_at
    age_hours = max(0.0, (now - timestamp).total_seconds() / 3600)
    recency = max(0.0, 5.0 - math.log2(age_hours + 1.0))
    corroboration = min(4.0, max(0, len(cluster.sources) - 1) * 1.5)
    title = article.title.casefold()
    penalty = 6.0 if any(term in title for term in _LOW_VALUE) else 0.0
    return float(category_weights.get(article.category, 1.0)) + recency + corroboration - penalty


def rank_clusters(
    clusters: list[StoryCluster] | tuple[StoryCluster, ...],
    *,
    now: datetime,
    category_weights: dict[str, float],
    limit: int = 30,
) -> tuple[StoryCluster, ...]:
    if limit <= 0:
        return ()
    scored = sorted(
        (
            (cluster_score(cluster, now=now, category_weights=category_weights), cluster)
            for cluster in clusters
        ),
        key=lambda item: (
            item[0],
            item[1].representative.published_at or item[1].representative.fetched_at,
            item[1].representative.article_id,
        ),
        reverse=True,
    )
    ordered = tuple(cluster for _, cluster in scored)
    if limit < 3 or len(ordered) < 3:
        return ordered[:limit]

    category_cap = max(2, math.ceil(limit * 0.4))
    source_cap = max(2, math.ceil(limit * 0.25))
    eligible_floor = scored[0][0] - _DIVERSITY_SCORE_WINDOW
    eligible = tuple(cluster for score, cluster in scored if score >= eligible_floor)
    selected: list[StoryCluster] = []
    selected_ids: set[int] = set()
    categories: Counter[str] = Counter()
    sources: Counter[str] = Counter()

    def add(cluster: StoryCluster) -> None:
        selected.append(cluster)
        selected_ids.add(id(cluster))
        categories[cluster.representative.category.casefold()] += 1
        sources[cluster.representative.source.casefold()] += 1

    # Put the strongest viable representative of each category near the top.
    for cluster in eligible:
        category = cluster.representative.category.casefold()
        source = cluster.representative.source.casefold()
        if category not in categories and sources[source] < source_cap:
            add(cluster)
            if len(selected) == limit:
                return tuple(selected)

    # If one publisher is the only source for a category, keep the category seed.
    for cluster in eligible:
        category = cluster.representative.category.casefold()
        if category not in categories:
            add(cluster)
            if len(selected) == limit:
                return tuple(selected)

    # Fill by the original score order while diverse alternatives remain.
    for cluster in ordered:
        if id(cluster) in selected_ids:
            continue
        category = cluster.representative.category.casefold()
        source = cluster.representative.source.casefold()
        if categories[category] >= category_cap or sources[source] >= source_cap:
            continue
        add(cluster)
        if len(selected) == limit:
            return tuple(selected)

    # Never leave blank slots merely because the available pool is concentrated.
    for cluster in ordered:
        if id(cluster) not in selected_ids:
            add(cluster)
            if len(selected) == limit:
                break
    return tuple(selected)
