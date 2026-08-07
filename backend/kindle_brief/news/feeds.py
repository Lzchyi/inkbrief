from __future__ import annotations

import hashlib
import re
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from time import struct_time
from typing import Any
from urllib.parse import urlsplit

import feedparser
import httpx
import yaml

from kindle_brief.models import Article

from .normalize import canonical_url, repair_mojibake, strip_markup

USER_AGENT = "KindleBrief/0.1 (personal RSS dashboard)"
MAX_FEED_BYTES = 8 * 1024 * 1024
MAX_ENTRIES_PER_FEED = 200
MAX_TITLE_CHARS = 500
MAX_EXCERPT_CHARS = 4_000
MAX_URL_CHARS = 4_096
_MAX_REGISTRY_BYTES = 1_048_576
_MISSING_DATE_POLICIES = frozenset({"first_seen"})
_ROOT_FIELDS = frozenset({"version", "verified_at", "feeds", "known_gaps"})
_REQUIRED_FEED_FIELDS = frozenset({"id", "name", "url", "category", "attribution"})
_FEED_FIELDS = _REQUIRED_FEED_FIELDS | {
    "enabled",
    "missing_date_policy",
    "guid_link_fallback",
}
_SAFE_ID_RE = re.compile(r"[a-z0-9][a-z0-9._-]{0,127}")
_DISPLAY_PUNCTUATION = str.maketrans({"‘": "'", "’": "'", "“": '"', "”": '"'})
_FEED_HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept": "application/rss+xml, application/atom+xml, application/xml, text/xml",
}


@dataclass(frozen=True, slots=True)
class FeedDefinition:
    feed_id: str
    name: str
    url: str
    category: str
    attribution: str
    enabled: bool = True
    missing_date_policy: str = "first_seen"
    guid_link_fallback: bool = False


@dataclass(frozen=True, slots=True)
class FeedHealth:
    feed_id: str
    ok: bool
    status_code: int | None
    entry_count: int
    final_url: str | None
    error: str | None = None


def load_feed_registry(path: str | Path) -> tuple[FeedDefinition, ...]:
    registry_path = Path(path)
    try:
        size = registry_path.stat().st_size
    except OSError as exc:
        raise ValueError(f"cannot read feed registry: {registry_path}") from exc
    if size > _MAX_REGISTRY_BYTES:
        raise ValueError("feed registry exceeds the 1 MiB safety limit")
    try:
        raw = yaml.safe_load(registry_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, yaml.YAMLError) as exc:
        raise ValueError(f"cannot parse feed registry: {registry_path}") from exc
    if not isinstance(raw, Mapping) or any(not isinstance(key, str) for key in raw):
        raise ValueError("feed registry must be a string-keyed mapping")
    unknown_root = sorted(set(raw) - _ROOT_FIELDS)
    if unknown_root:
        raise ValueError(f"feed registry contains unknown field(s): {', '.join(unknown_root)}")
    for required in ("version", "feeds"):
        if required not in raw:
            raise ValueError(f"feed registry.{required} is required")
    if (
        isinstance(raw["version"], bool)
        or not isinstance(raw["version"], int)
        or raw["version"] != 1
    ):
        raise ValueError("feed registry.version must be integer 1")
    if not isinstance(raw["feeds"], list):
        raise ValueError("feed registry.feeds must be a list")
    if "verified_at" in raw:
        _required_text("feed registry.verified_at", raw["verified_at"])
    if "known_gaps" in raw and not isinstance(raw["known_gaps"], Mapping):
        raise ValueError("feed registry.known_gaps must be a mapping")

    feeds: list[FeedDefinition] = []
    seen_ids: set[str] = set()
    seen_urls: set[str] = set()
    for index, item in enumerate(raw["feeds"]):
        if not isinstance(item, Mapping) or any(not isinstance(key, str) for key in item):
            raise ValueError(f"feeds[{index}] must be a string-keyed mapping")
        unknown = sorted(set(item) - _FEED_FIELDS)
        if unknown:
            raise ValueError(f"feeds[{index}] contains unknown field(s): {', '.join(unknown)}")
        missing = sorted(_REQUIRED_FEED_FIELDS - set(item))
        if missing:
            raise ValueError(f"feeds[{index}] missing required field(s): {', '.join(missing)}")

        feed_id = _required_text(f"feeds[{index}].id", item["id"])
        if _SAFE_ID_RE.fullmatch(feed_id) is None:
            raise ValueError(f"feeds[{index}].id must be a lowercase safe identifier")
        if feed_id in seen_ids:
            raise ValueError("feed IDs must be unique")
        seen_ids.add(feed_id)

        url = _feed_url(f"feeds[{index}].url", item["url"])
        canonical = canonical_url(url)
        if canonical in seen_urls:
            raise ValueError("feed URLs must be unique")
        seen_urls.add(canonical)

        missing_date_policy = _required_text(
            f"feeds[{index}].missing_date_policy",
            item.get("missing_date_policy", "first_seen"),
        )
        if missing_date_policy not in _MISSING_DATE_POLICIES:
            supported = ", ".join(sorted(_MISSING_DATE_POLICIES))
            raise ValueError(f"feed {feed_id} missing_date_policy must be one of: {supported}")
        feeds.append(
            FeedDefinition(
                feed_id=feed_id,
                name=_required_text(f"feeds[{index}].name", item["name"]),
                url=url,
                category=_required_text(f"feeds[{index}].category", item["category"]),
                attribution=_required_text(f"feeds[{index}].attribution", item["attribution"]),
                enabled=_boolean(f"feeds[{index}].enabled", item.get("enabled", True)),
                missing_date_policy=missing_date_policy,
                guid_link_fallback=_boolean(
                    f"feeds[{index}].guid_link_fallback",
                    item.get("guid_link_fallback", False),
                ),
            )
        )
    return tuple(feeds)


def _required_text(field: str, value: object) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty string")
    return value.strip()


def _boolean(field: str, value: object) -> bool:
    if not isinstance(value, bool):
        raise ValueError(f"{field} must be true or false")
    return value


def _feed_url(field: str, value: object) -> str:
    url = _required_text(field, value)
    if len(url) > MAX_URL_CHARS or any(ord(character) < 32 for character in url):
        raise ValueError(f"{field} must be a safe HTTPS URL")
    try:
        parsed = urlsplit(url)
        port = parsed.port
    except ValueError as exc:
        raise ValueError(f"{field} must be a safe HTTPS URL") from exc
    has_credentials = parsed.username is not None or parsed.password is not None
    if parsed.scheme != "https" or not parsed.hostname or has_credentials or port == 0:
        raise ValueError(f"{field} must be a safe HTTPS URL")
    return url


def _parsed_datetime(entry: Any) -> datetime | None:
    parsed: struct_time | None = entry.get("published_parsed") or entry.get("updated_parsed")
    if parsed is None:
        return None
    return datetime(*parsed[:6], tzinfo=UTC)


def _display_text(value: object) -> str:
    repaired = repair_mojibake(str(value or ""))
    return strip_markup(repaired).translate(_DISPLAY_PUNCTUATION)


def _entry_url(entry: Any, feed: FeedDefinition) -> str:
    link = str(entry.get("link") or "").strip()
    guid = str(entry.get("id") or entry.get("guid") or "").strip()
    if feed.guid_link_fallback and (not link or not url_is_http(link)) and url_is_http(guid):
        link = guid
    return canonical_url(link or guid)


def url_is_http(value: str) -> bool:
    return value.startswith("https://") or value.startswith("http://")


def parse_feed(
    content: bytes,
    feed: FeedDefinition,
    *,
    fetched_at: datetime,
) -> tuple[Article, ...]:
    if fetched_at.tzinfo is None:
        raise ValueError("fetched_at must be timezone-aware")
    if len(content) > MAX_FEED_BYTES:
        raise ValueError(f"{feed.feed_id} exceeds the 8 MiB feed limit")
    fetched_at = fetched_at.astimezone(UTC)
    parsed = feedparser.parse(content)
    if not parsed.entries:
        detail = str(getattr(parsed, "bozo_exception", "empty feed"))
        raise ValueError(f"{feed.feed_id} returned no feed entries: {detail}")
    articles: list[Article] = []
    for entry in parsed.entries[:MAX_ENTRIES_PER_FEED]:
        title = _display_text(entry.get("title")).strip()
        url = _entry_url(entry, feed)
        if not title or not url_is_http(url) or len(url) > MAX_URL_CHARS:
            continue
        if len(title) > MAX_TITLE_CHARS:
            title = title[: MAX_TITLE_CHARS - 1].rstrip() + "…"
        identity = f"{feed.feed_id}\0{url}".encode()
        summary = _display_text(entry.get("summary") or entry.get("description"))
        if len(summary) > MAX_EXCERPT_CHARS:
            summary = summary[: MAX_EXCERPT_CHARS - 1].rstrip() + "…"
        articles.append(
            Article(
                article_id=hashlib.sha256(identity).hexdigest()[:24],
                title=title,
                url=url,
                source=feed.attribution,
                category=feed.category,
                fetched_at=fetched_at,
                published_at=_parsed_datetime(entry),
                excerpt=summary,
            )
        )
    if not articles:
        raise ValueError(f"{feed.feed_id} contained no usable entries")
    return tuple(articles)


def fetch_feed(
    client: httpx.Client,
    feed: FeedDefinition,
    *,
    fetched_at: datetime,
) -> tuple[Article, ...]:
    content, _, _ = _stream_feed(client, feed)
    return parse_feed(content, feed, fetched_at=fetched_at)


def _stream_feed(
    client: httpx.Client,
    feed: FeedDefinition,
) -> tuple[bytes, int, str]:
    body = bytearray()
    with client.stream("GET", feed.url, headers=_FEED_HEADERS) as response:
        response.raise_for_status()
        content_length = response.headers.get("Content-Length")
        if content_length is not None:
            try:
                declared_length = int(content_length)
            except ValueError:
                declared_length = -1
            if declared_length > MAX_FEED_BYTES:
                raise ValueError(f"{feed.feed_id} exceeds the 8 MiB feed limit")
        for chunk in response.iter_bytes(chunk_size=64 * 1024):
            if len(body) + len(chunk) > MAX_FEED_BYTES:
                raise ValueError(f"{feed.feed_id} exceeds the 8 MiB feed limit")
            body.extend(chunk)
        status_code = response.status_code
        final_url = str(response.url)
    return bytes(body), status_code, final_url


def check_feed(client: httpx.Client, feed: FeedDefinition) -> FeedHealth:
    try:
        content, status_code, final_url = _stream_feed(client, feed)
        parsed = feedparser.parse(content)
        ok = bool(parsed.entries)
        return FeedHealth(
            feed_id=feed.feed_id,
            ok=ok,
            status_code=status_code,
            entry_count=len(parsed.entries),
            final_url=final_url,
            error=None if ok else str(getattr(parsed, "bozo_exception", "empty feed")),
        )
    except Exception as error:
        status = error.response.status_code if isinstance(error, httpx.HTTPStatusError) else None
        return FeedHealth(feed.feed_id, False, status, 0, None, str(error))
