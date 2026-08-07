"""Content-safe, atomic JSON storage for last-success provider responses."""

from __future__ import annotations

import hashlib
import os
import tempfile
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from .serialization import (
    JSONValue,
    SerializationError,
    canonical_json_dumps,
    datetime_from_json,
    datetime_to_json,
    json_loads,
    require_aware_utc,
    to_jsonable,
)

_SCHEMA_VERSION = 1
_MAX_KEY_LENGTH = 512


class CacheError(RuntimeError):
    """Base class for cache failures."""


class CacheCorruptionError(CacheError):
    """Raised when a cache entry exists but fails structural validation."""


@dataclass(frozen=True, slots=True)
class CacheEntry:
    key: str
    value: JSONValue
    stored_at: datetime
    expires_at: datetime | None

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "stored_at",
            require_aware_utc(self.stored_at, field_name="stored_at"),
        )
        if self.expires_at is not None:
            object.__setattr__(
                self,
                "expires_at",
                require_aware_utc(self.expires_at, field_name="expires_at"),
            )

    def is_stale(self, now: datetime | None = None) -> bool:
        if self.expires_at is None:
            return False
        effective_now = require_aware_utc(now or datetime.now(UTC), field_name="now")
        return effective_now >= self.expires_at


class JsonCache:
    """A key-hashed JSON cache whose writes become visible through ``os.replace``."""

    def __init__(self, root: str | Path, *, max_entry_bytes: int = 16 * 1024 * 1024) -> None:
        if max_entry_bytes <= 0:
            raise ValueError("max_entry_bytes must be positive")
        self.root = Path(root)
        self.max_entry_bytes = max_entry_bytes

    def write(
        self,
        key: str,
        value: Any,
        *,
        ttl: timedelta | None = None,
        now: datetime | None = None,
    ) -> CacheEntry:
        normalized_key = self._validate_key(key)
        stored_at = require_aware_utc(now or datetime.now(UTC), field_name="now")
        if ttl is not None and ttl <= timedelta(0):
            raise ValueError("ttl must be positive")
        expires_at = stored_at + ttl if ttl is not None else None
        json_value = to_jsonable(value)
        entry = CacheEntry(normalized_key, json_value, stored_at, expires_at)
        envelope = {
            "schema_version": _SCHEMA_VERSION,
            "key": normalized_key,
            "stored_at": datetime_to_json(stored_at),
            "expires_at": datetime_to_json(expires_at) if expires_at else None,
            "value": json_value,
        }
        encoded = canonical_json_dumps(envelope).encode("utf-8") + b"\n"
        if len(encoded) > self.max_entry_bytes:
            raise ValueError("cache entry exceeds max_entry_bytes")

        target = self.path_for(normalized_key)
        target.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temporary_name = tempfile.mkstemp(
            prefix=".cache-",
            suffix=".tmp",
            dir=target.parent,
        )
        temporary = Path(temporary_name)
        try:
            os.fchmod(descriptor, 0o600)
            with os.fdopen(descriptor, "wb") as handle:
                descriptor = -1
                handle.write(encoded)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, target)
            self._fsync_directory(target.parent)
        except Exception:
            if descriptor >= 0:
                os.close(descriptor)
            temporary.unlink(missing_ok=True)
            raise
        return entry

    def read(
        self,
        key: str,
        *,
        allow_stale: bool = True,
        now: datetime | None = None,
    ) -> CacheEntry | None:
        normalized_key = self._validate_key(key)
        target = self.path_for(normalized_key)
        try:
            stat = target.stat()
        except FileNotFoundError:
            return None
        except OSError as exc:
            raise CacheError(f"cannot inspect cache entry for {normalized_key!r}") from exc
        if stat.st_size > self.max_entry_bytes:
            raise CacheCorruptionError(f"cache entry for {normalized_key!r} is too large")
        try:
            raw = target.read_text(encoding="utf-8")
            decoded = json_loads(raw)
            entry = self._decode_entry(normalized_key, decoded)
        except (OSError, UnicodeError, SerializationError, ValueError, TypeError) as exc:
            raise CacheCorruptionError(f"cache entry for {normalized_key!r} is invalid") from exc
        if not allow_stale and entry.is_stale(now):
            return None
        return entry

    def path_for(self, key: str) -> Path:
        normalized_key = self._validate_key(key)
        digest = hashlib.sha256(normalized_key.encode("utf-8")).hexdigest()
        return self.root / digest[:2] / f"{digest}.json"

    def delete(self, key: str) -> bool:
        target = self.path_for(key)
        try:
            target.unlink()
        except FileNotFoundError:
            return False
        self._fsync_directory(target.parent)
        return True

    @staticmethod
    def _validate_key(key: str) -> str:
        if not isinstance(key, str) or not key or len(key) > _MAX_KEY_LENGTH or "\x00" in key:
            raise ValueError("cache key must be a non-empty string of at most 512 characters")
        return key

    @staticmethod
    def _decode_entry(key: str, decoded: JSONValue) -> CacheEntry:
        if not isinstance(decoded, Mapping):
            raise ValueError("cache envelope must be an object")
        required = {"schema_version", "key", "stored_at", "expires_at", "value"}
        if set(decoded) != required or decoded.get("schema_version") != _SCHEMA_VERSION:
            raise ValueError("unsupported cache envelope")
        if decoded.get("key") != key:
            raise ValueError("cache key does not match its hashed path")
        stored_at = datetime_from_json(decoded.get("stored_at"), field_name="stored_at")
        raw_expires = decoded.get("expires_at")
        expires_at = None
        if raw_expires is not None:
            expires_at = datetime_from_json(raw_expires, field_name="expires_at")
        if expires_at is not None and expires_at <= stored_at:
            raise ValueError("expires_at must be later than stored_at")
        return CacheEntry(
            key=key,
            value=decoded.get("value"),
            stored_at=stored_at,
            expires_at=expires_at,
        )

    @staticmethod
    def _fsync_directory(directory: Path) -> None:
        try:
            descriptor = os.open(directory, os.O_RDONLY)
        except OSError:
            return
        try:
            os.fsync(descriptor)
        except OSError:
            pass
        finally:
            os.close(descriptor)
