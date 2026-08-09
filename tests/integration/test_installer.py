from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
from dataclasses import replace
from datetime import timedelta
from pathlib import Path

import pytest
from kindle_brief.demo import demo_snapshot
from kindle_brief.models import DeviceProfile
from kindle_brief.renderer.release import build_release
from PIL import Image

REPO_ROOT = Path(__file__).resolve().parents[2]
INSTALL_SCRIPT = REPO_ROOT / "kindle" / "install" / "install.sh"
UNINSTALL_SCRIPT = REPO_ROOT / "kindle" / "install" / "uninstall.sh"
DETECT_SCRIPT = REPO_ROOT / "kindle" / "install" / "detect.sh"
PACKAGE_SCRIPT = REPO_ROOT / "kindle" / "install" / "package.sh"
VERIFY_BACKUP_SCRIPT = REPO_ROOT / "kindle" / "install" / "verify-backup.sh"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _make_fake_mount(tmp_path: Path, name: str = "Kindle") -> Path:
    mount = tmp_path / name
    (mount / "documents").mkdir(parents=True)
    (mount / "system").mkdir()
    (mount / "system" / "version.txt").write_text(
        "Kindle 5.19.2.0.1 (474059 001)", encoding="ascii"
    )
    (mount / "documents" / "existing-book.azw3").write_bytes(b"user book\x00contents")
    (mount / "metadata.calibre").write_text("calibre-owned", encoding="utf-8")
    return mount


def _make_package(
    tmp_path: Path,
    version: str,
    *,
    base_url: str | None = None,
) -> Path:
    package = tmp_path / f"package-{version}"
    app = package / "payload" / "app"
    kual = package / "payload" / "kual"
    (app / "bin").mkdir(parents=True)
    (app / "config").mkdir()
    (app / "pages").mkdir()
    kual.mkdir(parents=True)

    (app / ".kindle-brief-owned").write_text("kindle-brief-owned-v1\n", encoding="ascii")
    (kual / ".kindle-brief-owned").write_text("kindle-brief-owned-v1\n", encoding="ascii")
    (app / "VERSION").write_text(f"{version}\n", encoding="ascii")
    (app / "config" / "runtime.conf").write_text("max_runtime=1800\n", encoding="ascii")
    if base_url is not None:
        (app / "config" / "base-url").write_text(f"{base_url}\n", encoding="ascii")
    (app / "bin" / "start.sh").write_text("#!/bin/sh\nexit 0\n", encoding="ascii")
    controller = app / "bin" / "touch-controller"
    controller.write_bytes(b"fake-armhf-controller-" + version.encode("ascii"))
    (app / "TOUCH_ABI").write_text("kindlehf-armv7-hardfloat-static\n", encoding="ascii")
    (kual / "config.xml").write_text(
        '<extension><menus><menu type="json">menu.json</menu></menus></extension>\n',
        encoding="ascii",
    )
    (kual / "menu.json").write_text('{"items": []}\n', encoding="ascii")
    (kual / "start.sh").write_text("#!/bin/sh\nexit 0\n", encoding="ascii")
    for page_id in ("home", "weather", "f1", "morning-brief", "headlines"):
        (app / "pages" / f"{page_id}.png").write_bytes(
            b"png-fixture:" + page_id.encode("ascii") + b":" + version.encode("ascii")
        )

    for executable in (app / "bin" / "start.sh", controller, kual / "start.sh"):
        executable.chmod(0o755)

    payload_files = sorted(path for path in (package / "payload").rglob("*") if path.is_file())
    manifest = "".join(
        f"{_sha256(path)}  {path.relative_to(package / 'payload').as_posix()}\n"
        for path in payload_files
    )
    (package / "SHA256SUMS").write_text(manifest, encoding="ascii")
    package_id = hashlib.sha256(manifest.encode("ascii")).hexdigest()
    (package / "PACKAGE_ID").write_text(f"{package_id}\n", encoding="ascii")
    (package / "VERSION").write_text(f"{version}\n", encoding="ascii")
    (package / ".kindle-brief-package").write_text("kindle-brief-package-v1\n", encoding="ascii")
    return package


def _run(script: Path, *args: object, check: bool = False) -> subprocess.CompletedProcess[str]:
    environment = os.environ.copy()
    environment["KINDLE_BRIEF_ALLOW_FAKE_MOUNT"] = "1"
    return subprocess.run(
        ["/bin/sh", str(script), *(str(argument) for argument in args)],
        check=check,
        capture_output=True,
        text=True,
        env=environment,
    )


def _install(mount: Path, package: Path) -> subprocess.CompletedProcess[str]:
    return _run(
        INSTALL_SCRIPT,
        "--package",
        package,
        "--model",
        "KT5",
        mount,
    )


def _make_update_harness(
    tmp_path: Path,
    public: Path,
) -> tuple[Path, dict[str, str], Path]:
    app_root = tmp_path / "on-device-app"
    (app_root / "bin").mkdir(parents=True)
    (app_root / "config").mkdir()
    shutil.copy2(REPO_ROOT / "kindle" / "launcher" / "common.sh", app_root / "bin")
    shutil.copy2(REPO_ROOT / "kindle" / "launcher" / "update.sh", app_root / "bin")
    (app_root / "config" / "base-url").write_text(
        "https://updates.example.test\n", encoding="ascii"
    )

    fake_bin = tmp_path / "fake-bin"
    fake_bin.mkdir()
    fake_curl = fake_bin / "curl"
    fake_curl.write_text(
        """#!/bin/sh
output=
limit=
proto=
proto_redir=
connect_timeout=
max_time=
url=
while [ "$#" -gt 0 ]; do
    case "$1" in
        -o) output=$2; shift 2 ;;
        --max-filesize) limit=$2; shift 2 ;;
        --proto) proto=$2; shift 2 ;;
        --proto-redir) proto_redir=$2; shift 2 ;;
        --connect-timeout) connect_timeout=$2; shift 2 ;;
        --max-time) max_time=$2; shift 2 ;;
        -*) shift ;;
        *) url=$1; shift ;;
    esac
done
[ -z "${FAKE_CURL_LOG:-}" ] || \
    printf '%s\t%s\t%s\n' "$url" "$connect_timeout" "$max_time" >> "$FAKE_CURL_LOG"
[ "$proto" = '=https' ] && [ "$proto_redir" = '=https' ] || exit 92
relative=${url#https://updates.example.test/}
[ -n "$output" ] && [ "$relative" != "$url" ] || exit 2
source_file=$FAKE_RELEASE_ROOT/$relative
[ -f "$source_file" ] || exit 22
size=$(wc -c < "$source_file" | tr -d ' ')
[ -z "$limit" ] || [ "$size" -le "$limit" ] || exit 63
cp "$source_file" "$output"
""",
        encoding="ascii",
    )
    fake_sha256sum = fake_bin / "sha256sum"
    fake_sha256sum.write_text(
        """#!/bin/sh
if command -v shasum >/dev/null 2>&1; then
    exec shasum -a 256 "$@"
fi
exec /usr/bin/sha256sum "$@"
""",
        encoding="ascii",
    )
    fake_curl.chmod(0o755)
    fake_sha256sum.chmod(0o755)

    environment = os.environ.copy()
    environment.update(
        {
            "FAKE_RELEASE_ROOT": str(public),
            "KINDLE_BRIEF_ROOT": str(app_root),
            "KINDLE_BRIEF_STATE_DIR": str(tmp_path / "state"),
            "PATH": f"{fake_bin}:{environment['PATH']}",
        }
    )
    return app_root, environment, fake_bin


def _run_update(
    app_root: Path,
    environment: dict[str, str],
    *arguments: str,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["/bin/sh", str(app_root / "bin" / "update.sh"), *arguments],
        capture_output=True,
        text=True,
        env=environment,
    )


def _install_fake_date(fake_bin: Path) -> None:
    fake_date = fake_bin / "date"
    fake_date.write_text(
        """#!/bin/sh
[ "${1:-}" = '+%s' ] || exit 2
count=0
if [ -r "$FAKE_DATE_COUNT" ]; then
    IFS= read -r count < "$FAKE_DATE_COUNT" || count=0
fi
count=$((count + 1))
printf '%s\n' "$count" > "$FAKE_DATE_COUNT"
if [ "$count" -eq 1 ]; then
    printf '%s\n' "$FAKE_DATE_START"
else
    printf '%s\n' "$FAKE_DATE_NETWORK"
fi
""",
        encoding="ascii",
    )
    fake_date.chmod(0o755)


def _rewrite_release_metadata(
    public: Path,
    current: dict[str, object],
    manifest: dict[str, object],
    sums: str,
) -> None:
    profile_root = public / "profiles" / "kt5"
    release_root = profile_root / "releases" / str(current["release_id"])
    manifest_path = release_root / "manifest.json"
    sums_path = release_root / "SHA256SUMS"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
    sums_path.write_text(sums, encoding="ascii")
    current["manifest_sha256"] = _sha256(manifest_path)
    current["sha256sums_sha256"] = _sha256(sums_path)
    (profile_root / "current.json").write_text(
        json.dumps(current, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )


def test_real_packager_output_installs_on_fake_mount(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    package = tmp_path / "kindle-brief-integration"
    monkeypatch.setenv(
        "KINDLE_BRIEF_BASE_URL",
        "https://updates.example.test/kindle-brief/",
    )
    packaged = _run(PACKAGE_SCRIPT, package)
    assert packaged.returncode == 0, packaged.stderr
    assert package.is_dir()
    assert (package / "payload" / "app" / "TOUCH_ABI").read_text(
        encoding="ascii"
    ) == "kindlehf-armv7-hardfloat-static\n"
    assert "ELF 32-bit" in subprocess.check_output(
        ["file", str(package / "payload" / "app" / "bin" / "touch-controller")],
        text=True,
    )
    assert (package / "payload" / "app" / "config" / "base-url").read_text(
        encoding="ascii"
    ) == "https://updates.example.test/kindle-brief\n"
    assert (package / "payload" / "app" / "bin" / "open-url.sh").stat().st_mode & 0o111
    assert (package / "payload" / "app" / "links.tsv").is_file()
    assert (package / "payload" / "kual" / "enable-article-links.sh").stat().st_mode & 0o111

    mount = _make_fake_mount(tmp_path, "Packaged Kindle")
    installed = _install(mount, package)
    assert installed.returncode == 0, installed.stderr
    assert (mount / "kindle-brief" / "current" / "pages" / "home.png").is_file()
    assert (mount / "kindle-brief" / "current" / "links.tsv").is_file()
    assert (mount / "kindle-brief" / "current" / "config" / "base-url").read_text(
        encoding="ascii"
    ) == "https://updates.example.test/kindle-brief\n"
    assert (mount / "extensions" / "Dashboard" / "menu.json").is_file()
    config_xml = (mount / "extensions" / "Dashboard" / "config.xml").read_text(encoding="utf-8")
    assert '<menu type="json" dynamic="true">menu.json</menu>' in config_xml


@pytest.mark.parametrize(
    "base_url",
    (
        "http://updates.example.test",
        "https://user:secret@updates.example.test",
        "https://updates.example.test/root?token=secret",
        "https://updates.example.test/root\nsecond-line",
    ),
)
def test_real_packager_rejects_unsafe_base_url_before_writing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    base_url: str,
) -> None:
    package = tmp_path / "kindle-brief-invalid-url"
    monkeypatch.setenv("KINDLE_BRIEF_BASE_URL", base_url)

    packaged = _run(PACKAGE_SCRIPT, package)

    assert packaged.returncode != 0
    assert "KINDLE_BRIEF_BASE_URL" in packaged.stderr
    assert not package.exists()


def test_backup_verifier_is_read_only_and_excludes_only_regenerated_caches(
    tmp_path: Path,
) -> None:
    mount = _make_fake_mount(tmp_path, "Backup Source Kindle")
    backup = tmp_path / "backup"
    shutil.copytree(mount, backup)
    store_cache = (
        backup / ".active_content_sandbox" / "store" / "resource" / "cachedResources" / "index.html"
    )
    store_cache.parent.mkdir(parents=True)
    store_cache.write_bytes(b"regenerated store page")
    regenerated = mount / "system" / "thumbnails" / "new-thumbnail.jpg"
    regenerated.parent.mkdir()
    regenerated.write_bytes(b"regenerated")
    os.utime(mount / "documents", (1_700_000_000, 1_700_000_000))
    os.utime(mount / "documents" / "existing-book.azw3", (1_700_000_000, 1_700_000_000))
    before = {
        path.relative_to(mount): path.read_bytes() for path in mount.rglob("*") if path.is_file()
    }

    clean = _run(VERIFY_BACKUP_SCRIPT, mount, backup)
    assert clean.returncode == 0, clean.stderr
    assert "matches" in clean.stdout
    assert {
        path.relative_to(mount): path.read_bytes() for path in mount.rglob("*") if path.is_file()
    } == before

    persistent_mount = (
        mount / ".active_content_sandbox" / "store" / "resource" / "persistent" / "state"
    )
    persistent_backup = backup / persistent_mount.relative_to(mount)
    persistent_mount.parent.mkdir(parents=True)
    persistent_backup.parent.mkdir(parents=True)
    persistent_mount.write_bytes(b"current1")
    persistent_backup.write_bytes(b"current2")
    store_mismatch = _run(VERIFY_BACKUP_SCRIPT, mount, backup)
    assert store_mismatch.returncode == 1
    assert ".active_content_sandbox/store/resource/persistent/state" in store_mismatch.stderr
    persistent_mount.write_bytes(persistent_backup.read_bytes())

    (mount / "documents" / "existing-book.azw3").write_bytes(b"changed size")
    mismatch = _run(VERIFY_BACKUP_SCRIPT, mount, backup)
    assert mismatch.returncode == 1
    assert "documents/existing-book.azw3" in mismatch.stderr


def test_backup_verifier_filters_gnu_rsync_excluded_parent_diagnostics(tmp_path: Path) -> None:
    mount = _make_fake_mount(tmp_path, "GNU Rsync Source Kindle")
    backup = tmp_path / "backup"
    shutil.copytree(mount, backup)
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    fake_rsync = fake_bin / "rsync"
    fake_rsync.write_text(
        "#!/bin/sh\n"
        "printf '%s\\n' "
        "'  *deleting   .active_content_sandbox/store/resource/' "
        "'  *deleting   .active_content_sandbox/store/' "
        "'  cannot delete non-empty directory: .active_content_sandbox/store/resource' "
        "'  cannot delete non-empty directory: .active_content_sandbox/store'\n",
        encoding="ascii",
    )
    fake_rsync.chmod(0o755)
    environment = os.environ.copy()
    environment["KINDLE_BRIEF_ALLOW_FAKE_MOUNT"] = "1"
    environment["PATH"] = f"{fake_bin}{os.pathsep}{environment['PATH']}"

    clean = subprocess.run(
        ["/bin/sh", str(VERIFY_BACKUP_SCRIPT), str(mount), str(backup)],
        capture_output=True,
        text=True,
        env=environment,
    )

    assert clean.returncode == 0, clean.stderr
    assert "matches" in clean.stdout

    backed_up_book = backup / "documents" / "existing-book.azw3"
    mounted_book = mount / "documents" / "existing-book.azw3"
    mounted_book.write_bytes(backed_up_book.read_bytes().translate(bytes.maketrans(b"u", b"v")))
    assert mounted_book.stat().st_size == backed_up_book.stat().st_size
    same_size_mismatch = _run(VERIFY_BACKUP_SCRIPT, mount, backup)
    assert same_size_mismatch.returncode == 1
    assert "documents/existing-book.azw3" in same_size_mismatch.stderr


def test_host_release_is_directly_consumable_by_posix_updater(tmp_path: Path) -> None:
    public = tmp_path / "public"
    profile = DeviceProfile(
        "kt5",
        "Kindle 11th generation (2022)",
        1072,
        1448,
        model_code="KT5",
    )
    manifest = build_release(demo_snapshot(), profile, public)
    profile_root = public / "profiles" / "kt5"
    current = json.loads((profile_root / "current.json").read_text(encoding="utf-8"))
    assert current["profile_id"] == "kt5"
    assert current["model_code"] == "KT5"
    assert current["release_id"] == manifest.release_id
    assert current["links_bytes"] > 0

    release_root = profile_root / "releases" / manifest.release_id
    manifest_path = release_root / "manifest.json"
    sums_path = release_root / "SHA256SUMS"
    assert _sha256(manifest_path) == current["manifest_sha256"]
    assert _sha256(sums_path) == current["sha256sums_sha256"]
    manifest_json = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest_json["profile"]["profile_id"] == "kt5"
    assert manifest_json["profile"]["model_code"] == "KT5"

    sidecar: dict[str, str] = {}
    for line in sums_path.read_text(encoding="ascii").splitlines():
        digest, relative_path = line.split("  ", 1)
        assert len(digest) == 64
        assert relative_path not in sidecar
        sidecar[relative_path] = digest
    expected_paths = {
        "pages/home.png",
        "pages/weather.png",
        "pages/f1.png",
        "pages/morning-brief.png",
        "pages/headlines.png",
    }
    assert set(sidecar) == expected_paths
    assert sidecar == {page["path"]: page["sha256"] for page in manifest_json["pages"]}
    for relative_path, digest in sidecar.items():
        assert _sha256(release_root / relative_path) == digest

    app_root = tmp_path / "on-device-app"
    (app_root / "bin").mkdir(parents=True)
    (app_root / "config").mkdir()
    shutil.copy2(REPO_ROOT / "kindle" / "launcher" / "common.sh", app_root / "bin")
    shutil.copy2(REPO_ROOT / "kindle" / "launcher" / "update.sh", app_root / "bin")
    (app_root / "config" / "base-url").write_text(
        "https://updates.example.test\n", encoding="ascii"
    )

    fake_bin = tmp_path / "fake-bin"
    fake_bin.mkdir()
    fake_curl = fake_bin / "curl"
    fake_curl.write_text(
        """#!/bin/sh
output=
limit=
url=
while [ \"$#\" -gt 0 ]; do
    case \"$1\" in
        -o) output=$2; shift 2 ;;
        --max-filesize) limit=$2; shift 2 ;;
        --connect-timeout|--max-time) shift 2 ;;
        -*) shift ;;
        *) url=$1; shift ;;
    esac
done
relative=${url#https://updates.example.test/}
[ -n \"$output\" ] && [ \"$relative\" != \"$url\" ] || exit 2
source_file=$FAKE_RELEASE_ROOT/$relative
[ -f \"$source_file\" ] || exit 22
size=$(wc -c < \"$source_file\" | tr -d ' ')
[ -z \"$limit\" ] || [ \"$size\" -le \"$limit\" ] || exit 63
cp \"$source_file\" \"$output\"
""",
        encoding="ascii",
    )
    fake_sha256sum = fake_bin / "sha256sum"
    fake_sha256sum.write_text(
        """#!/bin/sh
if command -v shasum >/dev/null 2>&1; then
    exec shasum -a 256 \"$@\"
fi
exec /usr/bin/sha256sum \"$@\"
""",
        encoding="ascii",
    )
    fake_curl.chmod(0o755)
    fake_sha256sum.chmod(0o755)

    environment = os.environ.copy()
    environment.update(
        {
            "FAKE_RELEASE_ROOT": str(public),
            "KINDLE_BRIEF_ROOT": str(app_root),
            "KINDLE_BRIEF_STATE_DIR": str(tmp_path / "state"),
            "PATH": f"{fake_bin}:{environment['PATH']}",
        }
    )
    updated = subprocess.run(
        ["/bin/sh", str(app_root / "bin" / "update.sh")],
        capture_output=True,
        text=True,
        env=environment,
    )
    assert updated.returncode == 0, updated.stderr
    cache = app_root / "cache" / "current"
    assert (cache / "RELEASE_ID").read_text(encoding="ascii").strip() == manifest.release_id
    assert not (cache / "dashboard.tar.gz").exists()
    assert (cache / "links.tsv").read_bytes() == (release_root / "links.tsv").read_bytes()
    for relative_path in expected_paths:
        assert (cache / relative_path).read_bytes() == (release_root / relative_path).read_bytes()


def test_update_rolls_back_current_when_verified_stage_promotion_fails(tmp_path: Path) -> None:
    public = tmp_path / "public"
    profile = DeviceProfile("kt5", "Kindle", 1072, 1448, model_code="KT5")
    first = build_release(demo_snapshot(), profile, public)
    app_root, environment, fake_bin = _make_update_harness(tmp_path, public)
    installed = _run_update(app_root, environment)
    assert installed.returncode == 0, installed.stderr

    second_snapshot = replace(
        demo_snapshot(), generated_at=demo_snapshot().generated_at + timedelta(minutes=1)
    )
    second = build_release(second_snapshot, profile, public)
    assert second.release_id != first.release_id
    fake_mv = fake_bin / "mv"
    fake_mv.write_text(
        """#!/bin/sh
case "${1:-}:${2:-}" in
    */cache/.stage-*:*cache/current)
        [ "${FAIL_STAGE_PROMOTION:-0}" = 1 ] && exit 70
        ;;
esac
exec /bin/mv "$@"
""",
        encoding="ascii",
    )
    fake_mv.chmod(0o755)
    environment["FAIL_STAGE_PROMOTION"] = "1"

    failed = _run_update(app_root, environment)

    assert failed.returncode != 0
    assert "Could not promote verified dashboard update" in failed.stderr
    cache_root = app_root / "cache"
    assert (cache_root / "current" / "RELEASE_ID").read_text(
        encoding="ascii"
    ).strip() == first.release_id
    assert not list(cache_root.glob(".stage-*"))


def test_update_is_a_successful_noop_when_release_is_already_current(
    tmp_path: Path,
) -> None:
    public = tmp_path / "public"
    profile = DeviceProfile("kt5", "Kindle", 1072, 1448, model_code="KT5")
    release = build_release(demo_snapshot(), profile, public)
    app_root, environment, _ = _make_update_harness(tmp_path, public)
    installed = _run_update(app_root, environment)
    assert installed.returncode == 0, installed.stderr

    pointer_only = tmp_path / "pointer-only" / "profiles" / "kt5"
    pointer_only.mkdir(parents=True)
    shutil.copy2(public / "profiles" / "kt5" / "current.json", pointer_only)
    environment["FAKE_RELEASE_ROOT"] = str(tmp_path / "pointer-only")

    repeated = _run_update(app_root, environment)

    assert repeated.returncode == 0, repeated.stderr
    assert "Dashboard is already current" in repeated.stderr
    assert (app_root / "cache" / "current" / "RELEASE_ID").read_text(
        encoding="ascii"
    ).strip() == release.release_id
    assert not (app_root / "cache" / "previous").exists()
    assert not list((app_root / "cache").glob(".stage-*"))


def test_update_repairs_damaged_cache_with_matching_release_id(tmp_path: Path) -> None:
    public = tmp_path / "public"
    profile = DeviceProfile("kt5", "Kindle", 1072, 1448, model_code="KT5")
    release = build_release(demo_snapshot(), profile, public)
    app_root, environment, _ = _make_update_harness(tmp_path, public)
    installed = _run_update(app_root, environment)
    assert installed.returncode == 0, installed.stderr

    cache_root = app_root / "cache"
    cached_home = cache_root / "current" / "pages" / "home.png"
    cached_home.write_bytes(b"damaged-cache-page")

    repaired = _run_update(app_root, environment)

    release_home = (
        public / "profiles" / "kt5" / "releases" / release.release_id / "pages" / "home.png"
    )
    assert repaired.returncode == 0, repaired.stderr
    assert "Dashboard update installed" in repaired.stderr
    assert cached_home.read_bytes() == release_home.read_bytes()
    assert (cache_root / "previous" / "pages" / "home.png").read_bytes() == (b"damaged-cache-page")


def test_launch_update_shares_deadline_while_manual_keeps_long_timeout(
    tmp_path: Path,
) -> None:
    public = tmp_path / "public"
    profile = DeviceProfile("kt5", "Kindle", 1072, 1448, model_code="KT5")
    build_release(demo_snapshot(), profile, public)
    app_root, environment, fake_bin = _make_update_harness(tmp_path, public)
    curl_log = tmp_path / "curl.log"
    environment["FAKE_CURL_LOG"] = str(curl_log)

    installed = _run_update(app_root, environment)

    assert installed.returncode == 0, installed.stderr
    manual_calls = [line.split("\t") for line in curl_log.read_text().splitlines()]
    assert len(manual_calls) == 9
    assert all(call[1:] == ["15", "90"] for call in manual_calls)

    curl_log.unlink()
    _install_fake_date(fake_bin)
    environment.update(
        {
            "FAKE_DATE_COUNT": str(tmp_path / "date-count"),
            "FAKE_DATE_START": "100",
            "FAKE_DATE_NETWORK": "105",
        }
    )

    repeated = _run_update(app_root, environment, "--launch")

    assert repeated.returncode == 0, repeated.stderr
    assert "Dashboard is already current" in repeated.stderr
    launch_calls = [line.split("\t") for line in curl_log.read_text().splitlines()]
    assert len(launch_calls) == 1
    assert launch_calls[0][1:] == ["15", "15"]


def test_launch_update_stops_before_network_when_deadline_is_exhausted(
    tmp_path: Path,
) -> None:
    public = tmp_path / "public"
    app_root, environment, fake_bin = _make_update_harness(tmp_path, public)
    _install_fake_date(fake_bin)
    curl_log = tmp_path / "curl.log"
    environment.update(
        {
            "FAKE_CURL_LOG": str(curl_log),
            "FAKE_DATE_COUNT": str(tmp_path / "date-count"),
            "FAKE_DATE_START": "100",
            "FAKE_DATE_NETWORK": "121",
        }
    )

    expired = _run_update(app_root, environment, "--launch")

    assert expired.returncode == 4
    assert "Could not download bounded update pointer" in expired.stderr
    assert not curl_log.exists()
    assert not list((app_root / "cache").glob(".stage-*"))


@pytest.mark.parametrize(
    "endpoint",
    (
        "http://updates.example.test",
        "https://",
        "https://user:secret@updates.example.test",
        "https://updates.example.test/root?token=secret",
        "https://updates.example.test/root#fragment",
        "https://updates.example.test\nhttps://second.example.test",
        "https://" + "a" * 4090,
    ),
)
def test_update_rejects_unsafe_endpoint_before_curl(
    tmp_path: Path,
    endpoint: str,
) -> None:
    app_root, environment, _ = _make_update_harness(tmp_path, tmp_path / "public")
    (app_root / "config" / "base-url").write_text(endpoint, encoding="ascii")
    curl_log = tmp_path / "curl.log"
    environment["FAKE_CURL_LOG"] = str(curl_log)

    rejected = _run_update(app_root, environment)

    assert rejected.returncode == 2
    assert not curl_log.exists()


def test_update_rejects_symlink_endpoint_before_curl(tmp_path: Path) -> None:
    app_root, environment, _ = _make_update_harness(tmp_path, tmp_path / "public")
    endpoint = app_root / "config" / "base-url"
    endpoint.unlink()
    target = tmp_path / "endpoint-target"
    target.write_text("https://updates.example.test\n", encoding="ascii")
    endpoint.symlink_to(target)
    curl_log = tmp_path / "curl.log"
    environment["FAKE_CURL_LOG"] = str(curl_log)

    rejected = _run_update(app_root, environment)

    assert rejected.returncode == 2
    assert not curl_log.exists()


def test_update_recovers_owned_previous_before_network_failure(tmp_path: Path) -> None:
    public = tmp_path / "public"
    profile = DeviceProfile("kt5", "Kindle", 1072, 1448, model_code="KT5")
    release = build_release(demo_snapshot(), profile, public)
    app_root, environment, _ = _make_update_harness(tmp_path, public)
    installed = _run_update(app_root, environment)
    assert installed.returncode == 0, installed.stderr
    cache_root = app_root / "cache"
    (cache_root / "current").rename(cache_root / "previous")
    unavailable = tmp_path / "unavailable"
    unavailable.mkdir()
    environment["FAKE_RELEASE_ROOT"] = str(unavailable)

    failed = _run_update(app_root, environment)

    assert failed.returncode != 0
    assert "Could not download bounded update pointer" in failed.stderr
    assert (cache_root / "current" / "RELEASE_ID").read_text(
        encoding="ascii"
    ).strip() == release.release_id
    assert not (cache_root / "previous").exists()


def test_dashboard_and_diagnostics_fall_back_to_owned_previous_cache(tmp_path: Path) -> None:
    app_root = tmp_path / "runtime-app"
    bin_dir = app_root / "bin"
    previous_pages = app_root / "cache" / "previous" / "pages"
    bundled_pages = app_root / "pages"
    bin_dir.mkdir(parents=True)
    previous_pages.mkdir(parents=True)
    bundled_pages.mkdir()
    for script in ("common.sh", "dashboard.sh", "diagnostics.sh"):
        shutil.copy2(REPO_ROOT / "kindle" / "launcher" / script, bin_dir / script)
    (app_root / "cache" / "previous" / ".kindle-brief-cache").write_text(
        "kindle-brief-cache-v1\n", encoding="ascii"
    )
    for page_id in ("home", "weather", "f1", "morning-brief", "headlines"):
        (previous_pages / f"{page_id}.png").write_bytes(b"previous")
        (bundled_pages / f"{page_id}.png").write_bytes(b"bundled")
    display_log = tmp_path / "display.log"
    scripts = {
        "touch-controller": "#!/bin/sh\nprintf '%s\\n' TIMEOUT\n",
        "fbink-display.sh": ('#!/bin/sh\nprintf \'%s|%s\\n\' "$1" "$2" >> "$DISPLAY_LOG"\n'),
        "failsafe.sh": "#!/bin/sh\nexit 0\n",
        "restore-ui.sh": "#!/bin/sh\nexit 0\n",
    }
    for name, content in scripts.items():
        path = bin_dir / name
        path.write_text(content, encoding="ascii")
        path.chmod(0o755)
    environment = os.environ.copy()
    environment.update(
        {
            "DISPLAY_LOG": str(display_log),
            "KINDLE_BRIEF_ROOT": str(app_root),
            "KINDLE_BRIEF_STATE_DIR": str(tmp_path / "runtime-state"),
        }
    )

    dashboard = subprocess.run(
        ["/bin/sh", str(bin_dir / "dashboard.sh")],
        capture_output=True,
        text=True,
        env=environment,
        timeout=10,
    )
    diagnostics = subprocess.run(
        ["/bin/sh", str(bin_dir / "diagnostics.sh")],
        capture_output=True,
        text=True,
        env=environment,
        timeout=10,
    )

    assert dashboard.returncode == 0, dashboard.stderr
    assert display_log.read_text(encoding="utf-8").splitlines()[0] == (
        f"{previous_pages / 'home.png'}|full"
    )
    assert diagnostics.returncode == 0, diagnostics.stderr
    assert "Pages: 5/5" in diagnostics.stdout


@pytest.mark.parametrize(
    ("runtime_config", "events", "expected_returncode", "expected_modes", "error"),
    (
        (
            None,
            "NEXT NEXT NEXT NEXT NEXT TIMEOUT",
            0,
            ("full", "partial", "partial", "partial", "partial", "full"),
            "",
        ),
        (
            "full_refresh_every=1\n",
            "NEXT NEXT TIMEOUT",
            0,
            ("full", "full", "full"),
            "",
        ),
        (
            "full_refresh_every=0\n",
            "TIMEOUT",
            2,
            (),
            "invalid numeric runtime configuration",
        ),
        (
            "full_refresh_every=fast\n",
            "TIMEOUT",
            2,
            (),
            "invalid numeric runtime configuration",
        ),
        (
            "full_refresh_every=6\n",
            "TIMEOUT",
            2,
            (),
            "full_refresh_every may not exceed 5 page changes",
        ),
    ),
)
def test_dashboard_uses_bounded_periodic_full_refreshes(
    tmp_path: Path,
    runtime_config: str | None,
    events: str,
    expected_returncode: int,
    expected_modes: tuple[str, ...],
    error: str,
) -> None:
    app_root = tmp_path / "runtime-app"
    bin_dir = app_root / "bin"
    pages_dir = app_root / "pages"
    config_dir = app_root / "config"
    bin_dir.mkdir(parents=True)
    pages_dir.mkdir()
    config_dir.mkdir()
    for script in ("common.sh", "dashboard.sh"):
        shutil.copy2(REPO_ROOT / "kindle" / "launcher" / script, bin_dir / script)
    for page_id in ("home", "weather", "f1", "morning-brief", "headlines"):
        (pages_dir / f"{page_id}.png").write_bytes(b"page")
    if runtime_config is not None:
        (config_dir / "runtime.conf").write_text(runtime_config, encoding="ascii")
    display_log = tmp_path / "display.log"
    scripts = {
        "touch-controller": f"#!/bin/sh\nprintf '%s\\n' {events}\n",
        "fbink-display.sh": ('#!/bin/sh\nprintf \'%s|%s\\n\' "$1" "$2" >> "$DISPLAY_LOG"\n'),
        "failsafe.sh": "#!/bin/sh\nexit 0\n",
        "restore-ui.sh": "#!/bin/sh\nexit 0\n",
    }
    for name, content in scripts.items():
        path = bin_dir / name
        path.write_text(content, encoding="ascii")
        path.chmod(0o755)
    environment = os.environ.copy()
    environment.update(
        {
            "DISPLAY_LOG": str(display_log),
            "KINDLE_BRIEF_ROOT": str(app_root),
            "KINDLE_BRIEF_STATE_DIR": str(tmp_path / "runtime-state"),
        }
    )

    dashboard = subprocess.run(
        ["/bin/sh", str(bin_dir / "dashboard.sh")],
        capture_output=True,
        text=True,
        env=environment,
        timeout=10,
    )

    assert dashboard.returncode == expected_returncode, dashboard.stderr
    if expected_returncode:
        assert error in dashboard.stderr
        assert not display_log.exists()
    else:
        modes = tuple(
            line.rsplit("|", 1)[1] for line in display_log.read_text(encoding="utf-8").splitlines()
        )
        assert modes == expected_modes


def test_dashboard_tap_restores_ui_then_opens_exact_article_url(tmp_path: Path) -> None:
    app_root = tmp_path / "runtime-app"
    bin_dir = app_root / "bin"
    pages_dir = app_root / "pages"
    config_dir = app_root / "config"
    bin_dir.mkdir(parents=True)
    pages_dir.mkdir()
    config_dir.mkdir()
    for script in ("common.sh", "dashboard.sh"):
        shutil.copy2(REPO_ROOT / "kindle" / "launcher" / script, bin_dir / script)
    for page_id in ("home", "weather", "f1", "morning-brief", "headlines"):
        (pages_dir / f"{page_id}.png").write_bytes(b"page")
    article_url = "https://example.test/story?a=1&b=2"
    (app_root / "links.tsv").write_text(
        f"home 200 200 900 300 {article_url}\n",
        encoding="ascii",
    )
    (config_dir / "article-browser-enabled").write_text(
        "kindle-brief-internal-browser-risk-accepted-v1\n",
        encoding="ascii",
    )
    sequence_log = tmp_path / "sequence.log"
    scripts = {
        "touch-controller": (
            "#!/bin/sh\nprintf '%s\\n' 'TAP:300:250'\n"
            "trap 'exit 0' TERM\nwhile :; do sleep 1; done\n"
        ),
        "fbink-display.sh": "#!/bin/sh\nexit 0\n",
        "failsafe.sh": "#!/bin/sh\nexit 0\n",
        "restore-ui.sh": "#!/bin/sh\nprintf '%s\\n' restore >> \"$SEQUENCE_LOG\"\n",
        "open-url.sh": (
            "#!/bin/sh\n"
            '[ ! -e "$KINDLE_BRIEF_STATE_DIR/touch-controller.pid" ] || exit 9\n'
            'printf \'open|%s\\n\' "$1" >> "$SEQUENCE_LOG"\n'
        ),
    }
    for name, content in scripts.items():
        path = bin_dir / name
        path.write_text(content, encoding="ascii")
        path.chmod(0o755)
    environment = os.environ.copy()
    environment.update(
        {
            "KINDLE_BRIEF_ROOT": str(app_root),
            "KINDLE_BRIEF_STATE_DIR": str(tmp_path / "runtime-state"),
            "SEQUENCE_LOG": str(sequence_log),
        }
    )

    dashboard = subprocess.run(
        ["/bin/sh", str(bin_dir / "dashboard.sh")],
        capture_output=True,
        text=True,
        env=environment,
        timeout=10,
    )

    assert dashboard.returncode == 0, dashboard.stderr
    assert sequence_log.read_text(encoding="utf-8").splitlines() == [
        "restore",
        f"open|{article_url}",
    ]


def test_open_url_refuses_browser_without_explicit_risk_marker(tmp_path: Path) -> None:
    app_root = tmp_path / "runtime-app"
    bin_dir = app_root / "bin"
    bin_dir.mkdir(parents=True)
    for script in ("common.sh", "open-url.sh"):
        shutil.copy2(REPO_ROOT / "kindle" / "launcher" / script, bin_dir / script)
    environment = os.environ.copy()
    environment.update(
        {
            "KINDLE_BRIEF_ROOT": str(app_root),
            "KINDLE_BRIEF_STATE_DIR": str(tmp_path / "runtime-state"),
        }
    )

    refused = subprocess.run(
        ["/bin/sh", str(bin_dir / "open-url.sh"), "https://example.test/story"],
        capture_output=True,
        text=True,
        env=environment,
        timeout=5,
    )

    assert refused.returncode == 7
    assert "risk has not been accepted" in refused.stderr


def test_fbink_display_selects_grayscale_and_cleanup_waveforms(tmp_path: Path) -> None:
    app_root = tmp_path / "display-app"
    bin_dir = app_root / "bin"
    fake_bin = tmp_path / "fake-bin"
    bin_dir.mkdir(parents=True)
    fake_bin.mkdir()
    shutil.copy2(REPO_ROOT / "kindle" / "launcher" / "common.sh", bin_dir)
    shutil.copy2(REPO_ROOT / "kindle" / "display" / "fbink-display.sh", bin_dir)
    shutil.copy2(REPO_ROOT / "kindle" / "launcher" / "restore-ui.sh", bin_dir)
    image = tmp_path / "page.png"
    image.write_bytes(b"page")
    fbink_log = tmp_path / "fbink.log"
    fake_fbink = fake_bin / "fbink"
    fake_fbink.write_text(
        (
            '#!/bin/sh\nprintf \'%s\\n\' "$*" >> "$FBINK_LOG"\n'
            'case "$*" in\n'
            '    *"-W GL16"*) [ "${FAIL_GL16:-0}" -eq 0 ] || exit 9 ;;\n'
            "esac\n"
        ),
        encoding="ascii",
    )
    fake_fbink.chmod(0o755)
    fake_sleep = fake_bin / "sleep"
    fake_sleep.write_text("#!/bin/sh\nexit 0\n", encoding="ascii")
    fake_sleep.chmod(0o755)
    environment = os.environ.copy()
    environment.update(
        {
            "FBINK_LOG": str(fbink_log),
            "KINDLE_BRIEF_ROOT": str(app_root),
            "PATH": f"{fake_bin}:{environment['PATH']}",
            "FAIL_GL16": "0",
        }
    )
    script = bin_dir / "fbink-display.sh"

    default_full = subprocess.run(
        ["/bin/sh", str(script), str(image)],
        capture_output=True,
        text=True,
        env=environment,
    )
    partial = subprocess.run(
        ["/bin/sh", str(script), str(image), "partial"],
        capture_output=True,
        text=True,
        env=environment,
    )
    fallback_environment = environment.copy()
    fallback_environment["FAIL_GL16"] = "1"
    fallback = subprocess.run(
        ["/bin/sh", str(script), str(image), "partial"],
        capture_output=True,
        text=True,
        env=fallback_environment,
    )
    rejected = subprocess.run(
        ["/bin/sh", str(script), str(image), "fast"],
        capture_output=True,
        text=True,
        env=environment,
    )
    restored = subprocess.run(
        ["/bin/sh", str(bin_dir / "restore-ui.sh")],
        capture_output=True,
        text=True,
        env=environment,
    )

    assert default_full.returncode == 0, default_full.stderr
    assert partial.returncode == 0, partial.stderr
    assert fallback.returncode == 0, fallback.stderr
    assert "retrying with flashing GC16" in fallback.stderr
    assert rejected.returncode == 2
    assert "refresh mode must be full or partial" in rejected.stderr
    assert restored.returncode == 0, restored.stderr
    assert fbink_log.read_text(encoding="utf-8").splitlines() == [
        (f"-q -b -c -i {image} -g halign=CENTER,valign=CENTER,w=-1,h=-1,dither"),
        "-q -w -f -W GC16 -s",
        (f"-q -b -c -i {image} -g halign=CENTER,valign=CENTER,w=-1,h=-1,dither"),
        "-q -w -W GL16 -s",
        (f"-q -b -c -i {image} -g halign=CENTER,valign=CENTER,w=-1,h=-1,dither"),
        "-q -w -W GL16 -s",
        "-q -w -f -W GC16 -s",
        "-q -w -f -W GC16 -s",
    ]


def test_start_uses_cached_dashboard_when_launch_update_fails(tmp_path: Path) -> None:
    app_root = tmp_path / "runtime-app"
    bin_dir = app_root / "bin"
    config_dir = app_root / "config"
    bin_dir.mkdir(parents=True)
    config_dir.mkdir()
    for script in ("common.sh", "start.sh"):
        shutil.copy2(REPO_ROOT / "kindle" / "launcher" / script, bin_dir / script)
    (config_dir / "base-url").write_text(
        "https://updates.example.test\n",
        encoding="ascii",
    )
    (bin_dir / "update.sh").write_text(
        '#!/bin/sh\nprintf \'update:%s\\n\' "$*" >> "$START_EVENTS"\nexit 9\n',
        encoding="ascii",
    )
    (bin_dir / "dashboard.sh").write_text(
        "#!/bin/sh\nprintf '%s\\n' dashboard >> \"$START_EVENTS\"\nsleep 2\n",
        encoding="ascii",
    )
    events = tmp_path / "start-events"
    state_dir = tmp_path / "runtime-state"
    environment = os.environ.copy()
    environment.update(
        {
            "KINDLE_BRIEF_ROOT": str(app_root),
            "KINDLE_BRIEF_STATE_DIR": str(state_dir),
            "START_EVENTS": str(events),
        }
    )

    started = subprocess.run(
        ["/bin/sh", str(bin_dir / "start.sh")],
        capture_output=True,
        text=True,
        env=environment,
        timeout=5,
    )

    assert started.returncode == 0, started.stderr
    assert events.read_text(encoding="ascii").splitlines()[:2] == [
        "update:--launch",
        "dashboard",
    ]
    assert "Launch update failed; using cached dashboard pages" in (
        state_dir / "dashboard.log"
    ).read_text(encoding="utf-8")


@pytest.mark.parametrize(
    ("case", "message"),
    (
        ("pointer-schema", "Unsupported update pointer schema"),
        ("manifest-schema", "Unsupported manifest schema"),
        ("manifest-release", "Manifest release mismatch"),
        ("nested-profile", "Manifest device profile is unsupported"),
        ("page-width", "Invalid manifest page metadata"),
        ("page-byte-size", "Page byte size does not match manifest"),
    ),
)
def test_update_rejects_invalid_pointer_or_manifest_contract(
    tmp_path: Path,
    case: str,
    message: str,
) -> None:
    public = tmp_path / "public"
    profile = DeviceProfile("kt5", "Kindle", 1072, 1448, model_code="KT5")
    release = build_release(demo_snapshot(), profile, public)
    profile_root = public / "profiles" / "kt5"
    current_path = profile_root / "current.json"
    release_root = profile_root / "releases" / release.release_id
    current = json.loads(current_path.read_text(encoding="utf-8"))
    manifest = json.loads((release_root / "manifest.json").read_text(encoding="utf-8"))
    sums = (release_root / "SHA256SUMS").read_text(encoding="ascii")

    if case == "pointer-schema":
        current["schema_version"] = 2
        current_path.write_text(
            json.dumps(current, sort_keys=True, separators=(",", ":")) + "\n",
            encoding="utf-8",
        )
    else:
        if case == "manifest-schema":
            manifest["schema_version"] = 2
        elif case == "manifest-release":
            manifest["release_id"] = "f" * 64
        elif case == "nested-profile":
            manifest["profile"]["grayscale_bits"] = 8
        elif case == "page-width":
            manifest["pages"][0]["width"] = 1071
        elif case == "page-byte-size":
            manifest["pages"][0]["byte_size"] += 1
        _rewrite_release_metadata(public, current, manifest, sums)

    app_root, environment, _ = _make_update_harness(tmp_path, public)
    rejected = _run_update(app_root, environment)

    assert rejected.returncode != 0
    assert message in rejected.stderr
    assert not (app_root / "cache" / "current").exists()


def test_update_rejects_self_consistent_non_grayscale_png(tmp_path: Path) -> None:
    public = tmp_path / "public"
    profile = DeviceProfile("kt5", "Kindle", 1072, 1448, model_code="KT5")
    release = build_release(demo_snapshot(), profile, public)
    profile_root = public / "profiles" / "kt5"
    release_root = profile_root / "releases" / release.release_id
    current = json.loads((profile_root / "current.json").read_text(encoding="utf-8"))
    manifest = json.loads((release_root / "manifest.json").read_text(encoding="utf-8"))
    page_path = release_root / "pages" / "home.png"
    Image.new("RGB", (1072, 1448), "white").save(page_path)
    digest = _sha256(page_path)
    byte_size = page_path.stat().st_size
    page = next(item for item in manifest["pages"] if item["page_id"] == "home")
    page["sha256"] = digest
    page["byte_size"] = byte_size
    sums_lines = []
    for line in (release_root / "SHA256SUMS").read_text(encoding="ascii").splitlines():
        old_digest, relative_path = line.split("  ", 1)
        sums_lines.append(
            f"{digest if relative_path == 'pages/home.png' else old_digest}  {relative_path}"
        )
    _rewrite_release_metadata(public, current, manifest, "\n".join(sums_lines) + "\n")
    app_root, environment, _ = _make_update_harness(tmp_path, public)

    rejected = _run_update(app_root, environment)

    assert rejected.returncode != 0
    assert "Page PNG dimensions or type are unsupported" in rejected.stderr
    assert not (app_root / "cache" / "current").exists()


@pytest.mark.parametrize(
    "unsafe_url",
    (
        "http://example.test/not-allowed",
        "https://:443/missing-host",
        "https://example.test:0/invalid-port",
    ),
)
def test_update_rejects_unsafe_link_map_even_when_pointer_matches(
    tmp_path: Path,
    unsafe_url: str,
) -> None:
    public = tmp_path / "public"
    profile = DeviceProfile("kt5", "Kindle", 1072, 1448, model_code="KT5")
    release = build_release(demo_snapshot(), profile, public)
    profile_root = public / "profiles" / "kt5"
    current_path = profile_root / "current.json"
    current = json.loads(current_path.read_text(encoding="utf-8"))
    links_path = profile_root / "releases" / release.release_id / "links.tsv"
    links_path.write_text(
        f"home 200 200 900 300 {unsafe_url}\n",
        encoding="ascii",
    )
    current["links_sha256"] = _sha256(links_path)
    current["links_bytes"] = links_path.stat().st_size
    current_path.write_text(
        json.dumps(current, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
    app_root, environment, _ = _make_update_harness(tmp_path, public)

    rejected = _run_update(app_root, environment)

    assert rejected.returncode != 0
    assert "Link map is invalid" in rejected.stderr
    assert not (app_root / "cache" / "current").exists()


def test_update_refuses_wget_without_invoking_it(tmp_path: Path) -> None:
    public = tmp_path / "public"
    profile = DeviceProfile("kt5", "Kindle", 1072, 1448, model_code="KT5")
    build_release(demo_snapshot(), profile, public)
    app_root, environment, fake_bin = _make_update_harness(tmp_path, public)
    (fake_bin / "curl").unlink()
    (fake_bin / "wget").write_text(
        '#!/bin/sh\nprintf called > "$WGET_MARKER"\nexit 99\n',
        encoding="ascii",
    )
    (fake_bin / "wget").chmod(0o755)
    for command in ("awk", "dirname", "mkdir", "rm", "tr", "wc"):
        executable = shutil.which(command)
        assert executable is not None
        (fake_bin / command).symlink_to(executable)
    marker = tmp_path / "wget-called"
    environment["PATH"] = str(fake_bin)
    environment["WGET_MARKER"] = str(marker)

    rejected = _run_update(app_root, environment)

    assert rejected.returncode == 3
    assert "Refusing wget" in rejected.stderr
    assert not marker.exists()


def test_install_is_scoped_idempotent_and_keeps_previous_release(tmp_path: Path) -> None:
    mount = _make_fake_mount(tmp_path)
    first_package = _make_package(
        tmp_path,
        "0.1.0",
        base_url="https://packaged-one.example.test",
    )
    second_package = _make_package(
        tmp_path,
        "0.2.0",
        base_url="https://packaged-two.example.test",
    )
    book_before = (mount / "documents" / "existing-book.azw3").read_bytes()
    calibre_before = (mount / "metadata.calibre").read_bytes()

    first = _install(mount, first_package)
    assert first.returncode == 0, first.stderr
    first_id = (first_package / "PACKAGE_ID").read_text(encoding="ascii")
    assert (mount / "kindle-brief" / "current" / "PACKAGE_ID").read_text(
        encoding="ascii"
    ) == first_id
    assert (mount / "extensions" / "Dashboard" / "menu.json").is_file()
    assert not (mount / "kindle-brief" / "previous").exists()

    endpoint = mount / "kindle-brief" / "current" / "config" / "base-url"
    assert endpoint.read_text(encoding="ascii") == "https://packaged-one.example.test\n"
    endpoint.write_text("https://dashboard.example.test\n", encoding="ascii")
    current_home = mount / "kindle-brief" / "current" / "pages" / "home.png"
    current_home.write_bytes(b"damaged")
    orphan = mount / "kindle-brief" / "current" / "orphan"
    orphan.write_text("remove me", encoding="ascii")
    (mount / "extensions" / "Dashboard" / "menu.json").write_text("damaged", encoding="ascii")
    (mount / "._kindle-brief").write_bytes(b"appledouble")
    (mount / "kindle-brief" / "._current").write_bytes(b"appledouble")
    (mount / "extensions" / "._Dashboard").write_bytes(b"appledouble")
    (mount / "extensions" / "Dashboard" / "._menu.json").write_bytes(b"appledouble")
    repeated = _install(mount, first_package)
    assert repeated.returncode == 0, repeated.stderr
    assert not (mount / "kindle-brief" / "previous").exists()
    assert endpoint.read_text(encoding="ascii") == "https://dashboard.example.test\n"
    assert (
        current_home.read_bytes()
        == (first_package / "payload" / "app" / "pages" / "home.png").read_bytes()
    )
    assert not orphan.exists()
    assert (mount / "extensions" / "Dashboard" / "menu.json").read_bytes() == (
        first_package / "payload" / "kual" / "menu.json"
    ).read_bytes()
    assert not list((mount / "kindle-brief").rglob("._*"))
    assert not list((mount / "extensions" / "Dashboard").rglob("._*"))
    assert not (mount / "._kindle-brief").exists()
    assert not (mount / "extensions" / "._Dashboard").exists()

    upgraded = _install(mount, second_package)
    assert upgraded.returncode == 0, upgraded.stderr
    second_id = (second_package / "PACKAGE_ID").read_text(encoding="ascii")
    assert (mount / "kindle-brief" / "current" / "PACKAGE_ID").read_text(
        encoding="ascii"
    ) == second_id
    assert (mount / "kindle-brief" / "previous" / "PACKAGE_ID").read_text(
        encoding="ascii"
    ) == first_id
    assert (mount / "kindle-brief" / "current" / "config" / "base-url").read_text(
        encoding="ascii"
    ) == "https://dashboard.example.test\n"

    current_home.write_bytes(b"damaged again")
    repaired_upgrade = _install(mount, second_package)
    assert repaired_upgrade.returncode == 0, repaired_upgrade.stderr
    assert (
        current_home.read_bytes()
        == (second_package / "payload" / "app" / "pages" / "home.png").read_bytes()
    )
    assert (mount / "kindle-brief" / "previous" / "PACKAGE_ID").read_text(
        encoding="ascii"
    ) == first_id
    assert endpoint.read_text(encoding="ascii") == "https://dashboard.example.test\n"

    assert (mount / "documents" / "existing-book.azw3").read_bytes() == book_before
    assert (mount / "metadata.calibre").read_bytes() == calibre_before
    assert not list((mount / "kindle-brief").glob(".stage-*"))
    assert not list((mount / "kindle-brief").glob(".current.repair-*"))
    assert not list((mount / "extensions").glob(".Dashboard.stage-*"))


def test_uninstall_removes_only_owned_dashboard_paths(tmp_path: Path) -> None:
    mount = _make_fake_mount(tmp_path)
    package = _make_package(tmp_path, "0.1.0")
    assert _install(mount, package).returncode == 0
    unrelated = mount / "screensavers" / "personal.png"
    unrelated.parent.mkdir()
    unrelated.write_bytes(b"keep")

    result = _run(UNINSTALL_SCRIPT, mount)
    assert result.returncode == 0, result.stderr
    assert not (mount / "kindle-brief").exists()
    assert not (mount / "extensions" / "Dashboard").exists()
    assert (mount / "documents" / "existing-book.azw3").read_bytes() == b"user book\x00contents"
    assert (mount / "metadata.calibre").read_text(encoding="utf-8") == "calibre-owned"
    assert unrelated.read_bytes() == b"keep"

    repeated = _run(UNINSTALL_SCRIPT, mount)
    assert repeated.returncode == 0
    assert "nothing changed" in repeated.stdout


def test_install_refuses_wrong_firmware_before_writing(tmp_path: Path) -> None:
    mount = _make_fake_mount(tmp_path)
    package = _make_package(tmp_path, "0.1.0")
    (mount / "system" / "version.txt").write_text("Kindle 5.19.3 (1)", encoding="ascii")

    result = _install(mount, package)
    assert result.returncode != 0
    assert "pinned to 5.19.2.0.1" in result.stderr
    assert not (mount / "kindle-brief").exists()
    assert not (mount / "extensions").exists()


def test_install_refuses_corrupt_package_before_writing(tmp_path: Path) -> None:
    mount = _make_fake_mount(tmp_path)
    package = _make_package(tmp_path, "0.1.0")
    (package / "payload" / "app" / "VERSION").write_text("tampered\n", encoding="ascii")

    result = _install(mount, package)
    assert result.returncode != 0
    assert "checksum mismatch" in result.stderr
    assert not (mount / "kindle-brief").exists()


def test_install_refuses_unowned_kual_collision(tmp_path: Path) -> None:
    mount = _make_fake_mount(tmp_path)
    package = _make_package(tmp_path, "0.1.0")
    collision = mount / "extensions" / "Dashboard"
    collision.mkdir(parents=True)
    (collision / "menu.json").write_text("user content", encoding="utf-8")

    result = _install(mount, package)
    assert result.returncode != 0
    assert "unowned existing KUAL" in result.stderr
    assert (collision / "menu.json").read_text(encoding="utf-8") == "user content"
    assert not (mount / "kindle-brief").exists()


def test_detect_refuses_ambiguous_mounts_without_writing(tmp_path: Path) -> None:
    first = _make_fake_mount(tmp_path, "Kindle One")
    second = _make_fake_mount(tmp_path, "Kindle Two")
    snapshots = {
        path: path.read_bytes()
        for mount in (first, second)
        for path in mount.rglob("*")
        if path.is_file()
    }

    result = _run(DETECT_SCRIPT, first, second)
    assert result.returncode == 3
    assert "multiple Kindle-like mounts" in result.stderr
    assert {path: path.read_bytes() for path in snapshots} == snapshots


def test_uninstall_refuses_unowned_path_atomically(tmp_path: Path) -> None:
    mount = _make_fake_mount(tmp_path)
    package = _make_package(tmp_path, "0.1.0")
    assert _install(mount, package).returncode == 0
    marker = mount / "extensions" / "Dashboard" / ".kindle-brief-owned"
    marker.unlink()

    result = _run(UNINSTALL_SCRIPT, mount)
    assert result.returncode != 0
    assert (mount / "kindle-brief").is_dir()
    assert (mount / "extensions" / "Dashboard").is_dir()


@pytest.mark.parametrize("model", ["PW5", "KT6", "unknown"])
def test_install_accepts_only_exact_kt5_assertion(tmp_path: Path, model: str) -> None:
    mount = _make_fake_mount(tmp_path)
    package = _make_package(tmp_path, "0.1.0")
    result = _run(INSTALL_SCRIPT, "--package", package, "--model", model, mount)
    assert result.returncode != 0
    assert not (mount / "kindle-brief").exists()
