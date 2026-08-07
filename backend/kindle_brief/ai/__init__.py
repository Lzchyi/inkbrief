"""Optional, pluggable AI providers with a deterministic fallback."""

from .base import AIProvider, AIProviderError
from .factory import provider_from_environment
from .fallback import FallbackProvider

__all__ = ["AIProvider", "AIProviderError", "FallbackProvider", "provider_from_environment"]
