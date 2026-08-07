from pathlib import Path

import pytest
from kindle_brief.config import ConfigError, config_from_mapping, load_config


def minimal_config() -> dict[str, object]:
    return {
        "location": {
            "name": "Kuala Lumpur",
            "latitude": 3.139,
            "longitude": 101.6869,
            "timezone": "Asia/Kuala_Lumpur",
        }
    }


def test_minimal_config_uses_safe_defaults() -> None:
    config = config_from_mapping(minimal_config())

    assert config.location.name == "Kuala Lumpur"
    assert config.ai.provider == "fallback"
    assert config.refresh.dashboard_minutes == 60
    assert config.pages.home is True


def test_version_one_rejects_disabled_page_flags() -> None:
    raw = minimal_config() | {"pages": {"weather": False}}

    with pytest.raises(ConfigError, match="version 1 requires all five pages"):
        config_from_mapping(raw)


def test_config_rejects_unknown_fields_and_inline_secrets() -> None:
    unknown = minimal_config() | {"unexpected": True}
    with pytest.raises(ConfigError, match="unknown"):
        config_from_mapping(unknown)

    secret = minimal_config() | {"ai": {"provider": "gemini", "api_key": "do-not-store"}}
    with pytest.raises(ConfigError, match="must not contain a secret"):
        config_from_mapping(secret)


def test_config_requires_coordinate_pairs_and_valid_timezone() -> None:
    one_coordinate = {"location": {"name": "KL", "latitude": 3.139, "timezone": "UTC"}}
    with pytest.raises(ConfigError, match="provided together"):
        config_from_mapping(one_coordinate)

    bad_timezone = {"location": {"name": "KL", "timezone": "Not/A_Zone"}}
    with pytest.raises(ConfigError, match="IANA timezone"):
        config_from_mapping(bad_timezone)


def test_config_accepts_secret_environment_name_not_secret_value() -> None:
    raw = minimal_config() | {
        "ai": {"provider": "gemini", "model": "example-model", "credential_env": "GEMINI_API_KEY"},
        "category_weights": {"malaysia": 2.0, "science": 1.2},
    }
    config = config_from_mapping(raw)

    assert config.ai.credential_env == "GEMINI_API_KEY"
    assert [item.category for item in config.category_weights] == ["malaysia", "science"]


def test_load_config_uses_safe_yaml_loader(tmp_path: Path) -> None:
    pytest.importorskip("yaml")
    path = tmp_path / "config.yaml"
    path.write_text(
        "location:\n"
        "  name: Kuala Lumpur\n"
        "  latitude: 3.139\n"
        "  longitude: 101.6869\n"
        "  timezone: Asia/Kuala_Lumpur\n",
        encoding="utf-8",
    )

    assert load_config(path).location.timezone == "Asia/Kuala_Lumpur"


def test_checked_in_example_schema_is_supported() -> None:
    raw = minimal_config() | {
        "version": 1,
        "device": {"profile": "kt5"},
        "refresh": {
            "dashboard_minutes": 60,
            "morning_brief_local_time": "07:00",
            "request_timeout_seconds": 20,
            "max_stale_hours": 72,
        },
        "ai": {"provider": "fallback", "model": "", "max_stories": 8},
        "news": {
            "max_age_hours": 36,
            "headline_limit": 15,
            "category_weights": {"malaysia": 10, "science": 6},
        },
        "publishing": {"base_url": "", "profile": "kt5"},
    }

    config = config_from_mapping(raw)

    assert config.ai.model is None
    assert config.refresh.morning_brief_local_time.hour == 7
    assert config.news.headline_limit == 15
    assert config.publishing.base_url is None
