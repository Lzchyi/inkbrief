"""Strict loading of renderer/device profiles discovered outside application config."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

import yaml

from .config import DashboardConfig
from .models import DeviceProfile

_MAX_PROFILE_BYTES = 65_536


class ProfileError(ValueError):
    """Raised when a device profile is missing, unsafe, or inconsistent."""


def load_device_profile(path: str | Path) -> DeviceProfile:
    """Load the rendering fields from a strict version-one device profile."""

    profile_path = Path(path)
    try:
        if profile_path.stat().st_size > _MAX_PROFILE_BYTES:
            raise ProfileError("device profile exceeds the 64 KiB safety limit")
        raw = yaml.safe_load(profile_path.read_text(encoding="utf-8"))
    except ProfileError:
        raise
    except (OSError, UnicodeError, yaml.YAMLError) as exc:
        raise ProfileError(f"cannot read device profile: {profile_path}") from exc
    root = _mapping("profile", raw)
    _only_keys(
        "profile",
        root,
        {
            "id",
            "name",
            "model_code",
            "width",
            "height",
            "dpi",
            "orientation",
            "grayscale_bits",
            "touch",
        },
    )
    for required in ("id", "name", "model_code", "width", "height", "grayscale_bits"):
        if required not in root:
            raise ProfileError(f"profile.{required} is required")

    if "dpi" in root and _integer("profile.dpi", root["dpi"]) <= 0:
        raise ProfileError("profile.dpi must be positive")
    orientation = _string("profile.orientation", root.get("orientation", "portrait"))
    if orientation not in {"portrait", "landscape"}:
        raise ProfileError("profile.orientation must be portrait or landscape")
    touch = _touch(_mapping("profile.touch", root.get("touch", {})))
    return DeviceProfile(
        profile_id=_string("profile.id", root["id"]),
        model=_string("profile.name", root["name"]),
        width=_integer("profile.width", root["width"]),
        height=_integer("profile.height", root["height"]),
        rotation=touch["rotation"],
        grayscale_bits=_integer("profile.grayscale_bits", root["grayscale_bits"]),
        model_code=_string("profile.model_code", root["model_code"]),
    )


def load_profile_for_config(
    config: DashboardConfig,
    config_path: str | Path,
    *,
    override: str | Path | None = None,
) -> DeviceProfile:
    """Resolve the selected profile beside the config and enforce its exact identity."""

    path = (
        Path(override)
        if override is not None
        else Path(config_path).parent / "device-profiles" / f"{config.device.profile}.yaml"
    )
    profile = load_device_profile(path)
    if profile.profile_id != config.device.profile:
        raise ProfileError(
            f"device profile ID {profile.profile_id!r} does not match config "
            f"{config.device.profile!r}"
        )
    if profile.profile_id != config.publishing.profile:
        raise ProfileError("device profile does not match publishing.profile")
    return profile


def _touch(raw: Mapping[str, Any]) -> dict[str, int]:
    allowed = {
        "rotation",
        "mirror_x",
        "mirror_y",
        "raw_min_x",
        "raw_max_x",
        "raw_min_y",
        "raw_max_y",
    }
    _only_keys("profile.touch", raw, allowed)
    rotation = _integer("profile.touch.rotation", raw.get("rotation", 0))
    if rotation not in {0, 90, 180, 270}:
        raise ProfileError("profile.touch.rotation must be 0, 90, 180, or 270")
    for name in ("mirror_x", "mirror_y"):
        if name in raw and not isinstance(raw[name], bool):
            raise ProfileError(f"profile.touch.{name} must be true or false")
    limits: dict[str, int | None] = {}
    for name in ("raw_min_x", "raw_max_x", "raw_min_y", "raw_max_y"):
        limits[name] = (
            None if raw.get(name) is None else _integer(f"profile.touch.{name}", raw[name])
        )
    for minimum, maximum in (("raw_min_x", "raw_max_x"), ("raw_min_y", "raw_max_y")):
        if (limits[minimum] is None) != (limits[maximum] is None):
            raise ProfileError(f"profile.touch {minimum}/{maximum} must be provided together")
        lower = limits[minimum]
        upper = limits[maximum]
        if lower is not None and upper is not None and lower >= upper:
            raise ProfileError(f"profile.touch {minimum} must be lower than {maximum}")
    return {"rotation": rotation}


def _mapping(name: str, value: Any) -> Mapping[str, Any]:
    if not isinstance(value, Mapping) or any(not isinstance(key, str) for key in value):
        raise ProfileError(f"{name} must be a string-keyed mapping")
    return value


def _only_keys(name: str, value: Mapping[str, Any], allowed: set[str]) -> None:
    unknown = sorted(set(value) - allowed)
    if unknown:
        raise ProfileError(f"{name} contains unknown field(s): {', '.join(unknown)}")


def _string(name: str, value: Any) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ProfileError(f"{name} must be a non-empty string")
    return value.strip()


def _integer(name: str, value: Any) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ProfileError(f"{name} must be an integer")
    return value
