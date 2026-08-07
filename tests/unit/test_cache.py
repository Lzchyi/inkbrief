from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from kindle_brief.cache import CacheCorruptionError, JsonCache
from kindle_brief.models import SourceStatus

NOW = datetime(2026, 8, 7, 23, 0, tzinfo=UTC)


def test_cache_round_trip_and_stale_policy(tmp_path: Path) -> None:
    cache = JsonCache(tmp_path)
    cache.write("weather/kuala-lumpur", {"temperature": 29}, ttl=timedelta(hours=1), now=NOW)

    fresh = cache.read("weather/kuala-lumpur", now=NOW + timedelta(minutes=59))
    assert fresh is not None
    assert fresh.value == {"temperature": 29}
    assert fresh.is_stale(NOW + timedelta(minutes=59)) is False

    stale = cache.read("weather/kuala-lumpur", now=NOW + timedelta(hours=1))
    assert stale is not None
    assert stale.is_stale(NOW + timedelta(hours=1)) is True
    assert (
        cache.read("weather/kuala-lumpur", allow_stale=False, now=NOW + timedelta(hours=1)) is None
    )


def test_cache_serializes_immutable_models_and_utc_datetimes(tmp_path: Path) -> None:
    cache = JsonCache(tmp_path)
    cache.write("status", SourceStatus("Open-Meteo", NOW), now=NOW)

    entry = cache.read("status")
    assert entry is not None
    assert entry.value == {
        "attribution": None,
        "error": None,
        "fetched_at": "2026-08-07T23:00:00Z",
        "license_url": None,
        "source": "Open-Meteo",
        "stale": False,
    }


def test_hashed_keys_cannot_escape_cache_root(tmp_path: Path) -> None:
    cache = JsonCache(tmp_path)
    cache.write("../../documents/important", {"safe": True}, now=NOW)

    path = cache.path_for("../../documents/important")
    assert path.is_relative_to(tmp_path)
    assert ".." not in path.relative_to(tmp_path).parts


def test_overwrite_leaves_no_temporary_files(tmp_path: Path) -> None:
    cache = JsonCache(tmp_path)
    cache.write("key", {"version": 1}, now=NOW)
    cache.write("key", {"version": 2}, now=NOW + timedelta(minutes=1))

    assert cache.read("key").value == {"version": 2}  # type: ignore[union-attr]
    assert not list(tmp_path.rglob("*.tmp"))


def test_corrupt_entry_is_reported_without_deleting_it(tmp_path: Path) -> None:
    cache = JsonCache(tmp_path)
    path = cache.path_for("weather")
    path.parent.mkdir(parents=True)
    path.write_text("not-json", encoding="utf-8")

    with pytest.raises(CacheCorruptionError):
        cache.read("weather")
    assert path.exists()
