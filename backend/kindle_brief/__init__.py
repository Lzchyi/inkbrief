"""Core data and configuration primitives for Kindle Brief."""

from .cache import CacheCorruptionError, CacheEntry, JsonCache
from .config import ConfigError, DashboardConfig, load_config

__version__ = "0.1.0"

__all__ = [
    "CacheCorruptionError",
    "CacheEntry",
    "ConfigError",
    "DashboardConfig",
    "JsonCache",
    "load_config",
    "__version__",
]
