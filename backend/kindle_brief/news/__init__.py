"""RSS ingestion, normalization, deduplication, and deterministic ranking."""

from .dedupe import StoryCluster, cluster_articles
from .feeds import FeedDefinition, FeedHealth, fetch_feed, load_feed_registry
from .rank import rank_clusters

__all__ = [
    "FeedDefinition",
    "FeedHealth",
    "StoryCluster",
    "cluster_articles",
    "fetch_feed",
    "load_feed_registry",
    "rank_clusters",
]
