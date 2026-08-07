from __future__ import annotations

import os

from .base import AIProvider
from .fallback import FallbackProvider
from .gemini import GeminiProvider
from .openai_compat import OpenAICompatibleProvider

_REMOTE_PROVIDERS = {"gemini", "groq", "openrouter", "openai"}
_STANDARD_CREDENTIALS = {
    "gemini": "GEMINI_API_KEY",
    "groq": "GROQ_API_KEY",
    "openrouter": "OPENROUTER_API_KEY",
    "openai": "OPENAI_API_KEY",
}


def validate_provider_configuration(provider: str, credential_env: str | None = None) -> str:
    """Validate selection rules without reading a secret or opening an HTTP client."""

    requested = provider.strip().lower() or "auto"
    supported = _REMOTE_PROVIDERS | {"auto", "fallback", "none", "openai_compatible"}
    if requested not in supported:
        raise ValueError(f"unsupported AI provider: {requested}")
    if requested == "openai_compatible":
        raise ValueError("openai_compatible requires an explicitly configured base URL")
    if credential_env is not None and requested not in _REMOTE_PROVIDERS:
        raise ValueError("ai.credential_env requires one explicit remote AI provider")
    return requested


def provider_from_environment(
    provider: str = "auto",
    model: str = "",
    *,
    credential_env: str | None = None,
) -> AIProvider:
    """Create a provider without ever accepting an inline credential.

    A custom credential environment variable is honored only for one explicitly
    selected provider, so a secret can never be probed against several remote hosts.
    """

    requested = validate_provider_configuration(provider, credential_env)

    candidates = [requested] if requested != "auto" else ["gemini", "groq", "openrouter", "openai"]
    if requested in {"fallback", "none"}:
        return FallbackProvider()

    for candidate in candidates:
        environment_name = credential_env or _STANDARD_CREDENTIALS[candidate]
        key = os.getenv(environment_name)
        if candidate == "gemini" and key:
            return GeminiProvider(api_key=key, model=model or "gemini-3.5-flash-lite")
        if candidate == "groq" and key:
            return OpenAICompatibleProvider(
                name="groq",
                api_key=key,
                model=model or "openai/gpt-oss-20b",
                base_url="https://api.groq.com/openai/v1",
            )
        if candidate == "openrouter" and key:
            return OpenAICompatibleProvider(
                name="openrouter",
                api_key=key,
                model=model or "openai/gpt-oss-20b:free",
                base_url="https://openrouter.ai/api/v1",
                extra_headers={"X-Title": "Kindle Brief"},
            )
        if candidate == "openai" and key:
            return OpenAICompatibleProvider(
                name="openai",
                api_key=key,
                model=model or "gpt-5.4-nano",
                base_url="https://api.openai.com/v1",
            )
    return FallbackProvider()
