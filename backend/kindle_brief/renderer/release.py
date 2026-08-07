from __future__ import annotations

import gzip
import hashlib
import io
import json
import os
import tarfile
import tempfile
from collections.abc import Callable
from pathlib import Path
from typing import Any

from PIL import Image

from kindle_brief import __version__
from kindle_brief.models import (
    DashboardSnapshot,
    DeviceProfile,
    PageArtifact,
    PageID,
    ReleaseManifest,
)
from kindle_brief.serialization import canonical_json_dumps, datetime_to_json, to_jsonable

from .canvas import EInkCanvas
from .pages import f1, headlines, home, morning_brief, weather

Renderer = Callable[[DashboardSnapshot, int, int], EInkCanvas]

PAGE_RENDERERS: tuple[tuple[PageID, Renderer], ...] = (
    (PageID.HOME, home.render),
    (PageID.WEATHER, weather.render),
    (PageID.F1, f1.render),
    (PageID.MORNING_BRIEF, morning_brief.render),
    (PageID.HEADLINES, headlines.render),
)


def _atomic_write(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            descriptor = -1
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    except Exception:
        if descriptor >= 0:
            os.close(descriptor)
        temporary.unlink(missing_ok=True)
        raise


def _png_bytes(image: Image.Image) -> bytes:
    output = io.BytesIO()
    image.save(output, format="PNG", optimize=True, compress_level=9)
    return output.getvalue()


def render_pages(
    snapshot: DashboardSnapshot,
    profile: DeviceProfile,
) -> tuple[dict[PageID, bytes], dict[str, Any]]:
    images: dict[PageID, bytes] = {}
    metadata: dict[str, Any] = {"schema_version": 1, "pages": {}}
    for page_id, renderer in PAGE_RENDERERS:
        canvas = renderer(snapshot, profile.width, profile.height)
        image = canvas.convert_for_eink(bits=profile.grayscale_bits, dither=False)
        if image.size != (profile.width, profile.height):
            raise ValueError(f"{page_id.value} renderer returned the wrong dimensions")
        images[page_id] = _png_bytes(image)
        metadata["pages"][page_id.value] = canvas.metadata()
    return images, metadata


def render_previews(
    snapshot: DashboardSnapshot,
    profile: DeviceProfile,
    output_directory: str | Path,
) -> tuple[Path, ...]:
    output = Path(output_directory)
    images, metadata = render_pages(snapshot, profile)
    paths: list[Path] = []
    for page_id, content in images.items():
        filename = f"{page_id.value}.png"
        target = output / filename
        _atomic_write(target, content)
        paths.append(target)
    _atomic_write(
        output / "hotspots.json",
        (canonical_json_dumps(metadata) + "\n").encode("utf-8"),
    )
    return tuple(paths)


def _manifest(
    snapshot: DashboardSnapshot,
    profile: DeviceProfile,
    images: dict[PageID, bytes],
) -> ReleaseManifest:
    artifacts = tuple(
        PageArtifact(
            page_id=page_id,
            path=f"pages/{page_id.value}.png",
            sha256=hashlib.sha256(content).hexdigest(),
            byte_size=len(content),
            width=profile.width,
            height=profile.height,
        )
        for page_id, content in images.items()
    )
    identity = {
        "dashboard_version": __version__,
        "profile": to_jsonable(profile),
        "snapshot": to_jsonable(snapshot),
        "pages": [to_jsonable(artifact) for artifact in artifacts],
    }
    release_id = hashlib.sha256(canonical_json_dumps(identity).encode("utf-8")).hexdigest()
    return ReleaseManifest(
        schema_version=1,
        dashboard_version=__version__,
        release_id=release_id,
        generated_at=snapshot.generated_at,
        profile=profile,
        pages=artifacts,
    )


def _deterministic_tar_gz(files: dict[str, bytes]) -> bytes:
    compressed = io.BytesIO()
    with (
        gzip.GzipFile(fileobj=compressed, mode="wb", filename="", mtime=0) as gzip_file,
        tarfile.open(fileobj=gzip_file, mode="w", format=tarfile.PAX_FORMAT) as archive,
    ):
        for name in sorted(files):
            content = files[name]
            info = tarfile.TarInfo(name=name)
            info.size = len(content)
            info.mode = 0o644
            info.mtime = 0
            info.uid = 0
            info.gid = 0
            info.uname = ""
            info.gname = ""
            archive.addfile(info, io.BytesIO(content))
    return compressed.getvalue()


def build_release(
    snapshot: DashboardSnapshot,
    profile: DeviceProfile,
    public_root: str | Path,
) -> ReleaseManifest:
    if profile.model_code is None:
        raise ValueError("release profiles must declare model_code")
    public = Path(public_root)
    images, metadata = render_pages(snapshot, profile)
    manifest = _manifest(snapshot, profile, images)
    release_relative = Path("profiles") / profile.profile_id / "releases" / manifest.release_id
    release_directory = public / release_relative

    manifest_payload = to_jsonable(manifest)
    if not isinstance(manifest_payload, dict):
        raise TypeError("release manifest must serialize to an object")
    manifest_payload["profile_id"] = profile.profile_id
    manifest_payload["model_code"] = profile.model_code
    manifest_bytes = (canonical_json_dumps(manifest_payload) + "\n").encode("utf-8")
    snapshot_bytes = (canonical_json_dumps(snapshot) + "\n").encode("utf-8")
    metadata_bytes = (canonical_json_dumps(metadata) + "\n").encode("utf-8")
    sha256sums_bytes = "".join(
        f"{hashlib.sha256(images[page_id]).hexdigest()}  pages/{page_id.value}.png\n"
        for page_id, _ in PAGE_RENDERERS
    ).encode("utf-8")
    bundle_files = {
        "manifest.json": manifest_bytes,
        "SHA256SUMS": sha256sums_bytes,
        "snapshot.json": snapshot_bytes,
        "hotspots.json": metadata_bytes,
        **{f"pages/{page_id.value}.png": content for page_id, content in images.items()},
    }
    bundle = _deterministic_tar_gz(bundle_files)
    bundle_hash = hashlib.sha256(bundle).hexdigest()

    for name, content in bundle_files.items():
        _atomic_write(release_directory / name, content)
    _atomic_write(release_directory / "dashboard.tar.gz", bundle)

    current = {
        "schema_version": 1,
        "dashboard_version": __version__,
        "profile_id": profile.profile_id,
        "model_code": profile.model_code,
        "release_id": manifest.release_id,
        "generated_at": datetime_to_json(snapshot.generated_at),
        "manifest": f"releases/{manifest.release_id}/manifest.json",
        "manifest_sha256": hashlib.sha256(manifest_bytes).hexdigest(),
        "sha256sums_sha256": hashlib.sha256(sha256sums_bytes).hexdigest(),
        "bundle": f"releases/{manifest.release_id}/dashboard.tar.gz",
        "bundle_sha256": bundle_hash,
        "bundle_bytes": len(bundle),
    }
    _atomic_write(
        public / "profiles" / profile.profile_id / "current.json",
        (
            json.dumps(current, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
        ).encode("utf-8"),
    )
    return manifest
