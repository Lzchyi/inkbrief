from __future__ import annotations

from pathlib import Path

import pytest
from kindle_brief.config import load_config
from kindle_brief.models import DeviceProfile
from kindle_brief.profiles import ProfileError, load_device_profile, load_profile_for_config

ROOT = Path(__file__).parents[2]


def test_checked_in_profile_loads_with_updater_model_code() -> None:
    config_path = ROOT / "config/config.example.yaml"
    profile = load_profile_for_config(load_config(config_path), config_path)

    assert profile.profile_id == "kt5"
    assert profile.model_code == "KT5"
    assert (profile.width, profile.height) == (1072, 1448)


def test_profile_rejects_identity_mismatch(tmp_path: Path) -> None:
    profile_path = tmp_path / "wrong.yaml"
    profile_path.write_text(
        "id: wrong\nname: Test\nmodel_code: KT5\nwidth: 1072\nheight: 1448\ngrayscale_bits: 4\n",
        encoding="utf-8",
    )
    config_path = ROOT / "config/config.example.yaml"

    with pytest.raises(ProfileError, match="does not match"):
        load_profile_for_config(load_config(config_path), config_path, override=profile_path)


def test_profile_rejects_unbounded_renderer_dimensions(tmp_path: Path) -> None:
    profile_path = tmp_path / "huge.yaml"
    profile_path.write_text(
        "id: huge\nname: Huge\nmodel_code: HUGE\nwidth: 10001\nheight: 1448\ngrayscale_bits: 4\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="10000"):
        load_device_profile(profile_path)

    with pytest.raises(ValueError, match="10000"):
        DeviceProfile("huge", "Huge", 10001, 1448)
