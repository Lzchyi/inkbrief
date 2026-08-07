from __future__ import annotations

from datetime import UTC, datetime, timedelta

import httpx
import pytest
import yaml
from kindle_brief.models import Article
from kindle_brief.news.dedupe import cluster_articles
from kindle_brief.news.feeds import (
    MAX_EXCERPT_CHARS,
    FeedDefinition,
    fetch_feed,
    load_feed_registry,
    parse_feed,
)
from kindle_brief.news.normalize import canonical_url, repair_mojibake, strip_markup
from kindle_brief.news.rank import rank_clusters

NOW = datetime(2026, 8, 7, 23, 0, tzinfo=UTC)


class _CountingFeedStream(httpx.SyncByteStream):
    def __init__(self, *, chunks: int, chunk_size: int) -> None:
        self.chunks = chunks
        self.chunk_size = chunk_size
        self.chunks_read = 0

    def __iter__(self):  # type: ignore[no-untyped-def]
        for _ in range(self.chunks):
            self.chunks_read += 1
            yield b"x" * self.chunk_size


def _valid_feed_mapping() -> dict[str, object]:
    return {
        "id": "example",
        "name": "Example",
        "url": "https://example.com/feed.xml",
        "category": "science",
        "attribution": "Example",
    }


def _write_registry(tmp_path, value: object):  # type: ignore[no-untyped-def]
    registry = tmp_path / "feeds.yaml"
    registry.write_text(yaml.safe_dump(value), encoding="utf-8")
    return registry


def article(
    article_id: str,
    title: str,
    *,
    category: str = "malaysia",
    hours_old: int = 1,
    source: str = "Source",
    url: str | None = None,
) -> Article:
    return Article(
        article_id=article_id,
        title=title,
        url=url or f"https://example.com/{article_id}",
        source=source,
        category=category,
        fetched_at=NOW,
        published_at=NOW - timedelta(hours=hours_old),
        excerpt="The first verified fact. A second useful fact.",
    )


def test_canonical_url_removes_tracking_and_fragment() -> None:
    assert canonical_url("HTTPS://Example.COM/story/?utm_source=x&b=2&a=1#section") == (
        "https://example.com/story?a=1&b=2"
    )


def test_strip_markup_extracts_readable_text() -> None:
    assert strip_markup("<p>One &amp; <strong>two</strong></p>") == "One & two"


def test_mojibake_repair_is_conservative_for_valid_unicode() -> None:
    assert repair_mojibake("FranÃ§ais â€™ Â texte \ufffd") == "Français ’ \u00a0texte ?"
    assert repair_mojibake("François — 中文") == "François — 中文"
    assert repair_mojibake("中文 FranÃ§ais â€™") == "中文 Français ’"
    assert repair_mojibake("Ângela") == "Ângela"


def test_parse_atom_uses_guid_link_fallback_and_missing_date() -> None:
    content = b"""<?xml version='1.0' encoding='utf-8'?>
    <feed xmlns='http://www.w3.org/2005/Atom'>
      <title>Example</title>
      <entry><title>Useful &amp; factual</title>
      <id>https://example.com/post</id><summary>&lt;p&gt;Summary&lt;/p&gt;</summary></entry>
    </feed>"""
    feed = FeedDefinition(
        feed_id="example",
        name="Example",
        url="https://example.com/feed.xml",
        category="science",
        attribution="Example",
        guid_link_fallback=True,
    )
    parsed = parse_feed(content, feed, fetched_at=NOW)
    assert len(parsed) == 1
    assert parsed[0].url == "https://example.com/post"
    assert parsed[0].published_at is None
    assert parsed[0].excerpt == "Summary"


def test_parse_feed_repairs_common_mojibake_before_article_creation() -> None:
    content = """<?xml version='1.0' encoding='utf-8'?>
    <rss><channel><title>Example</title><item>
      <title>Malaysiaâ€™s cafÃ© outlook â€“ update</title>
      <link>https://example.com/story</link>
      <description>PricesÂ hold; donâ€™t panic \ufffd</description>
    </item></channel></rss>""".encode()
    feed = FeedDefinition(
        feed_id="example",
        name="Example",
        url="https://example.com/feed.xml",
        category="business",
        attribution="Example",
    )

    parsed = parse_feed(content, feed, fetched_at=NOW)

    assert parsed[0].title == "Malaysia's café outlook – update"
    assert parsed[0].excerpt == "Prices hold; don't panic ?"


def test_parse_feed_normalizes_curly_quotes_for_display_only() -> None:
    content = """<?xml version='1.0' encoding='utf-8'?>
    <rss><channel><title>Example</title><item>
      <title>What&#8217;s next for &#8216;all customers&#8217; — 中文</title>
      <link>https://example.com/story</link>
      <description>She said &#8220;keep the en dash – and accents café&#8221;.</description>
    </item></channel></rss>""".encode()
    feed = FeedDefinition(
        feed_id="example",
        name="Example",
        url="https://example.com/feed.xml",
        category="business",
        attribution="Example",
    )

    parsed = parse_feed(content, feed, fetched_at=NOW)

    assert parsed[0].title == "What's next for 'all customers' — 中文"
    assert parsed[0].excerpt == 'She said "keep the en dash – and accents café".'


def test_parse_feed_bounds_remote_payload_and_excerpt() -> None:
    feed = FeedDefinition(
        feed_id="example",
        name="Example",
        url="https://example.com/feed.xml",
        category="science",
        attribution="Example",
    )
    huge_excerpt = "x" * (MAX_EXCERPT_CHARS + 100)
    content = (
        "<rss><channel><title>Example</title><item><title>Bounded</title>"
        f"<link>https://example.com/bounded</link><description>{huge_excerpt}</description>"
        "</item></channel></rss>"
    ).encode()
    parsed = parse_feed(content, feed, fetched_at=NOW)
    assert len(parsed[0].excerpt) == MAX_EXCERPT_CHARS
    assert parsed[0].excerpt.endswith("…")

    with pytest.raises(ValueError, match="8 MiB"):
        parse_feed(b" " * (8 * 1024 * 1024 + 1), feed, fetched_at=NOW)


def test_fetch_feed_stops_streaming_above_eight_mib() -> None:
    stream = _CountingFeedStream(chunks=20, chunk_size=1024 * 1024)

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["User-Agent"] == "KindleBrief/0.1 (personal RSS dashboard)"
        return httpx.Response(200, stream=stream)

    feed = FeedDefinition(
        feed_id="example",
        name="Example",
        url="https://example.com/feed.xml",
        category="science",
        attribution="Example",
    )
    with (
        httpx.Client(transport=httpx.MockTransport(handler)) as client,
        pytest.raises(ValueError, match="8 MiB"),
    ):
        fetch_feed(client, feed, fetched_at=NOW)

    assert stream.chunks_read == 9


def test_fetch_feed_parses_a_bounded_stream() -> None:
    content = b"""<rss><channel><title>Example</title><item>
    <title>Streamed story</title><link>https://example.com/story</link>
    </item></channel></rss>"""

    def handler(request: httpx.Request) -> httpx.Response:
        assert "application/rss+xml" in request.headers["Accept"]
        return httpx.Response(200, content=content)

    feed = FeedDefinition(
        feed_id="example",
        name="Example",
        url="https://example.com/feed.xml",
        category="science",
        attribution="Example",
    )
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        articles = fetch_feed(client, feed, fetched_at=NOW)

    assert [article.title for article in articles] == ["Streamed story"]


def test_feed_registry_rejects_unknown_missing_date_policy(tmp_path) -> None:
    registry = tmp_path / "feeds.yaml"
    registry.write_text(
        """
version: 1
feeds:
  - id: example
    name: Example
    url: https://example.com/feed.xml
    category: science
    attribution: Example
    missing_date_policy: every_refresh
""".strip(),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="missing_date_policy.*first_seen"):
        load_feed_registry(registry)


def test_feed_registry_rejects_oversized_yaml(tmp_path) -> None:
    registry = tmp_path / "feeds.yaml"
    registry.write_text("#" + "x" * 1_048_576, encoding="utf-8")

    with pytest.raises(ValueError, match="1 MiB"):
        load_feed_registry(registry)


def test_feed_registry_rejects_unknown_and_missing_fields(tmp_path) -> None:
    feed = _valid_feed_mapping()
    feed["unexpected"] = "value"
    with pytest.raises(ValueError, match=r"feeds\[0\] contains unknown field"):
        load_feed_registry(_write_registry(tmp_path, {"version": 1, "feeds": [feed]}))

    feed = _valid_feed_mapping()
    feed.pop("attribution")
    with pytest.raises(ValueError, match="missing required field.*attribution"):
        load_feed_registry(_write_registry(tmp_path, {"version": 1, "feeds": [feed]}))

    with pytest.raises(ValueError, match="feed registry contains unknown field"):
        load_feed_registry(
            _write_registry(
                tmp_path,
                {"version": 1, "feeds": [_valid_feed_mapping()], "unexpected": True},
            )
        )

    with pytest.raises(ValueError, match=r"feed registry\.feeds is required"):
        load_feed_registry(_write_registry(tmp_path, {"version": 1}))


@pytest.mark.parametrize(
    ("field", "value"),
    (("enabled", "true"), ("guid_link_fallback", 1)),
)
def test_feed_registry_requires_actual_booleans(tmp_path, field, value) -> None:  # type: ignore[no-untyped-def]
    feed = _valid_feed_mapping()
    feed[field] = value

    with pytest.raises(ValueError, match=rf"{field}.*true or false"):
        load_feed_registry(_write_registry(tmp_path, {"version": 1, "feeds": [feed]}))


@pytest.mark.parametrize("field", ("name", "category", "attribution"))
def test_feed_registry_requires_nonempty_descriptive_fields(tmp_path, field) -> None:  # type: ignore[no-untyped-def]
    feed = _valid_feed_mapping()
    feed[field] = "   "

    with pytest.raises(ValueError, match=rf"{field}.*non-empty string"):
        load_feed_registry(_write_registry(tmp_path, {"version": 1, "feeds": [feed]}))


@pytest.mark.parametrize(
    ("field", "value", "message"),
    (
        ("id", "../example", "lowercase safe identifier"),
        ("url", "http://example.com/feed.xml", "safe HTTPS URL"),
        ("url", "https://user:secret@example.com/feed.xml", "safe HTTPS URL"),
    ),
)
def test_feed_registry_rejects_unsafe_ids_and_urls(tmp_path, field, value, message) -> None:  # type: ignore[no-untyped-def]
    feed = _valid_feed_mapping()
    feed[field] = value

    with pytest.raises(ValueError, match=message):
        load_feed_registry(_write_registry(tmp_path, {"version": 1, "feeds": [feed]}))


@pytest.mark.parametrize("field", ("id", "url"))
def test_feed_registry_requires_unique_ids_and_urls(tmp_path, field) -> None:  # type: ignore[no-untyped-def]
    first = _valid_feed_mapping()
    second = {**_valid_feed_mapping(), "id": "second", "url": "https://example.org/feed"}
    second[field] = first[field]

    with pytest.raises(ValueError, match=rf"feed {field.upper()}s must be unique"):
        load_feed_registry(_write_registry(tmp_path, {"version": 1, "feeds": [first, second]}))


def test_deduplication_groups_matching_cross_source_headlines() -> None:
    clusters = cluster_articles(
        (
            article("a", "Central bank announces new consumer rules", source="One"),
            article("b", "Central bank announces new rules for consumers", source="Two"),
            article("c", "Space telescope returns first image", category="science"),
        ),
        threshold=0.7,
    )
    assert len(clusters) == 2
    malaysia = next(item for item in clusters if item.representative.category == "malaysia")
    assert set(malaysia.sources) == {"One", "Two"}


def test_rank_prefers_configured_category_and_corroboration() -> None:
    malaysia = cluster_articles(
        (
            article("m1", "Major policy change announced", source="One"),
            article("m2", "Major policy change is announced", source="Two"),
        ),
        threshold=0.7,
    )[0]
    technology = cluster_articles((article("t1", "Minor application update", category="ai_tech"),))[
        0
    ]
    ranked = rank_clusters(
        (technology, malaysia),
        now=NOW,
        category_weights={"malaysia": 10, "ai_tech": 2},
    )
    assert ranked[0].representative.category == "malaysia"


def test_rank_deprioritizes_promotions_and_product_leaks() -> None:
    substantive = cluster_articles(
        (article("news", "New AI safety standard enters force", category="ai_tech"),)
    )[0]
    promotion = cluster_articles(
        (article("deal", "Grab the entire gadget bundle on sale", category="ai_tech"),)
    )[0]
    leak = cluster_articles(
        (article("leak", "Cheaper headphones coming according to leaks", category="ai_tech"),)
    )[0]

    ranked = rank_clusters(
        (promotion, leak, substantive),
        now=NOW,
        category_weights={"ai_tech": 9},
        limit=3,
    )

    assert ranked[0].representative.article_id == "news"


def test_rank_seeds_categories_and_caps_dominant_sources_when_alternatives_exist() -> None:
    groups = (
        ("malaysia", "Bernama", 10),
        ("ai_tech", "DeepMind", 9),
        ("science", "NASA", 8),
        ("business", "Reuters", 7),
    )
    clusters = tuple(
        cluster_articles(
            (
                article(
                    f"{category}-{index}",
                    f"Useful {category} report {index}",
                    category=category,
                    source=source,
                ),
            )
        )[0]
        for category, source, _weight in groups
        for index in range(5)
    )
    clickbait = cluster_articles(
        (
            article(
                "clickbait",
                "Shocking viral rumour you won't believe",
                category="travel",
                source="Click Farm",
            ),
        )
    )[0]
    weights = {category: weight for category, _source, weight in groups} | {"travel": 10}

    ranked = rank_clusters(
        clusters + (clickbait,),
        now=NOW,
        category_weights=weights,
        limit=12,
    )

    assert [item.representative.category for item in ranked[:4]] == [
        "malaysia",
        "ai_tech",
        "science",
        "business",
    ]
    assert (
        max(
            sum(item.representative.category == category for item in ranked)
            for category, _source, _weight in groups
        )
        <= 5
    )
    assert (
        max(
            sum(item.representative.source == source for item in ranked)
            for _category, source, _weight in groups
        )
        <= 3
    )
    assert all(item.representative.article_id != "clickbait" for item in ranked)
