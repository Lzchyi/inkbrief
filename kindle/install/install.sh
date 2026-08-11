#!/bin/sh
set -eu

INSTALL_DIR=$(CDPATH= cd "$(dirname "$0")" && pwd -P)
KINDLE_DIR=$(dirname "$INSTALL_DIR")
. "$INSTALL_DIR/host-lib.sh"

usage() {
    printf '%s\n' \
        "usage: install.sh [--package DIR] [--probe FILE] [--model KT5] MOUNT" >&2
    exit 2
}

package=
probe_file=
asserted_model=
mount_argument=
while [ "$#" -gt 0 ]; do
    case "$1" in
        --package)
            [ "$#" -ge 2 ] || usage
            package=$2
            shift 2
            ;;
        --probe)
            [ "$#" -ge 2 ] || usage
            probe_file=$2
            shift 2
            ;;
        --model)
            [ "$#" -ge 2 ] || usage
            asserted_model=$2
            shift 2
            ;;
        --*) usage ;;
        *)
            [ -z "$mount_argument" ] || usage
            mount_argument=$1
            shift
            ;;
    esac
done
[ -n "$mount_argument" ] || usage

if [ -z "$package" ]; then
    version=$(sed -n '1p' "$KINDLE_DIR/VERSION")
    package=$KINDLE_DIR/dist/kindle-brief-$version
fi
package=$(kb_host_canonical_dir "$package") || kb_host_die "package directory does not exist"
[ "$(sed -n '1p' "$package/.kindle-brief-package" 2>/dev/null || true)" = \
    kindle-brief-package-v1 ] || kb_host_die "package ownership marker is missing"
[ -r "$package/SHA256SUMS" ] || kb_host_die "package manifest is missing"
[ -r "$package/PACKAGE_ID" ] || kb_host_die "package ID is missing"
IFS= read -r package_id < "$package/PACKAGE_ID"
kb_host_valid_sha256 "$package_id" || kb_host_die "package ID is malformed"
actual_package_id=$(kb_host_sha256 "$package/SHA256SUMS") || \
    kb_host_die "no SHA-256 tool is available"
[ "$actual_package_id" = "$package_id" ] || kb_host_die "package manifest was modified"
[ -f "$package/payload/app/.kindle-brief-owned" ] || \
    kb_host_die "application ownership marker is missing"
[ -f "$package/payload/kual/.kindle-brief-owned" ] || \
    kb_host_die "KUAL ownership marker is missing"
[ -x "$package/payload/app/bin/touch-controller" ] || \
    kb_host_die "package has no executable hard-float touch controller"
[ "$(sed -n '1p' "$package/payload/app/TOUCH_ABI" 2>/dev/null || true)" = \
    kindlehf-armv7-hardfloat-static ] || kb_host_die "package hard-float ABI marker is missing"
[ ! -L "$package/payload" ] || kb_host_die "package payload may not be a symlink"
if find "$package/payload" -type l -print | grep . >/dev/null 2>&1; then
    kb_host_die "package payload contains a symlink"
fi

manifest_count=0
while IFS= read -r checksum_line || [ -n "$checksum_line" ]; do
    checksum=${checksum_line%%  *}
    relative_path=${checksum_line#*  }
    [ "$relative_path" != "$checksum_line" ] || kb_host_die "malformed package manifest"
    kb_host_valid_sha256 "$checksum" || kb_host_die "malformed package checksum"
    case "$relative_path" in
        ''|/*|../*|*/../*|*/..|*//*|*[!A-Za-z0-9._/-]*)
            kb_host_die "unsafe package manifest path"
            ;;
    esac
    [ -f "$package/payload/$relative_path" ] || \
        kb_host_die "manifest file is missing: $relative_path"
    actual_checksum=$(kb_host_sha256 "$package/payload/$relative_path") || \
        kb_host_die "cannot hash package payload"
    [ "$actual_checksum" = "$checksum" ] || \
        kb_host_die "package checksum mismatch: $relative_path"
    manifest_count=$((manifest_count + 1))
done < "$package/SHA256SUMS"

payload_count=$(find "$package/payload" -type f | wc -l | tr -d ' ')
[ "$manifest_count" -eq "$payload_count" ] || \
    kb_host_die "package manifest does not cover every payload file"
while IFS= read -r payload_file; do
    relative_path=${payload_file#"$package/payload/"}
    occurrences=$(awk -v path="$relative_path" \
        'substr($0, 67) == path { count++ } END { print count + 0 }' \
        "$package/SHA256SUMS")
    [ "$occurrences" -eq 1 ] || kb_host_die "payload path is not uniquely manifested"
done <<EOF
$(find "$package/payload" -type f -print)
EOF

mount_path=$(kb_host_validate_mount "$mount_argument")
[ -w "$mount_path" ] || kb_host_die "Kindle mount is not writable"
firmware=$(kb_host_firmware "$mount_path")
[ "$firmware" = "5.19.2.0.1" ] || \
    kb_host_die "refusing firmware $firmware; this package is pinned to 5.19.2.0.1"

probe_model=
probe_firmware=
if [ -n "$probe_file" ]; then
    [ -r "$probe_file" ] || kb_host_die "probe file is unreadable"
    probe_model=$(kb_host_probe_value model_code "$probe_file" 2>/dev/null || true)
    probe_firmware=$(kb_host_probe_value firmware "$probe_file" 2>/dev/null || true)
    [ -z "$probe_firmware" ] || [ "$probe_firmware" = "$firmware" ] || \
        kb_host_die "probe firmware disagrees with mounted firmware"
fi
usb_model=$(kb_host_usb_model 2>/dev/null || true)
detected_model=$probe_model
[ -n "$detected_model" ] || detected_model=$usb_model
if [ -n "$asserted_model" ] && [ -n "$detected_model" ] && \
   [ "$asserted_model" != "$detected_model" ]; then
    kb_host_die "asserted model disagrees with detected model"
fi
[ -n "$detected_model" ] || detected_model=$asserted_model
[ "$detected_model" = KT5 ] || \
    kb_host_die "exact KT5 model is not proven; pass a read-only probe or --model KT5"

app_base=$mount_path/kindle-brief
extension_parent=$mount_path/extensions
extension_root=$extension_parent/Dashboard
if [ -L "$app_base" ] || [ -L "$extension_parent" ] || [ -L "$extension_root" ]; then
    kb_host_die "managed install paths may not be symlinks"
fi
if [ -e "$app_base" ] && ! kb_host_owned_dir "$app_base"; then
    kb_host_die "refusing unowned existing path: $app_base"
fi
if [ -e "$extension_root" ] && ! kb_host_owned_dir "$extension_root"; then
    kb_host_die "refusing unowned existing KUAL Dashboard entry"
fi
if [ -d "$app_base/current" ] && ! kb_host_owned_dir "$app_base/current"; then
    kb_host_die "refusing unowned current release"
fi
if [ -d "$app_base/previous" ] && ! kb_host_owned_dir "$app_base/previous"; then
    kb_host_die "refusing unowned previous release"
fi

required_kb=$(du -sk "$package/payload" | awk '{print $1 + 65536}')
available_kb=$(df -Pk "$mount_path" | awk 'NR == 2 { print $4 }')
[ -n "$available_kb" ] && [ "$available_kb" -ge "$required_kb" ] || \
    kb_host_die "insufficient free space (64 MiB reserve required)"

# No target write happens before every package, device, firmware, model,
# ownership, and capacity check above has passed.
mkdir -p "$app_base" "$extension_parent"
if [ ! -f "$app_base/.kindle-brief-owned" ]; then
    printf '%s\n' kindle-brief-owned-v1 > "$app_base/.kindle-brief-owned"
fi
app_stage=$app_base/.stage-$$
app_repair_backup=$app_base/.current.repair-$$
extension_stage=$extension_parent/.Dashboard.stage-$$
extension_backup=$extension_parent/.Dashboard.previous-$$
[ ! -e "$app_stage" ] && [ ! -e "$app_repair_backup" ] && \
    [ ! -e "$extension_stage" ] && [ ! -e "$extension_backup" ] || \
    kb_host_die "staging path collision"

app_repair_active=0
cleanup_install() {
    rm -rf "$app_stage" "$extension_stage" 2>/dev/null || true
    if [ "$app_repair_active" -eq 1 ] && [ -d "$app_repair_backup" ]; then
        if [ -d "$app_base/current" ] && kb_host_owned_dir "$app_base/current"; then
            rm -rf "$app_base/current" 2>/dev/null || true
        fi
        if [ ! -e "$app_base/current" ]; then
            mv "$app_repair_backup" "$app_base/current" 2>/dev/null || true
        fi
    elif [ -d "$app_repair_backup" ]; then
        rm -rf "$app_repair_backup" 2>/dev/null || true
    fi
    if [ -d "$extension_backup" ] && [ ! -e "$extension_root" ]; then
        mv "$extension_backup" "$extension_root" 2>/dev/null || true
    fi
}
trap cleanup_install EXIT
trap 'exit 129' HUP
trap 'exit 130' INT
trap 'exit 143' TERM
mkdir "$app_stage" "$extension_stage"
COPYFILE_DISABLE=1 cp -R "$package/payload/app/." "$app_stage/"
COPYFILE_DISABLE=1 cp -R "$package/payload/kual/." "$extension_stage/"
printf '%s\n' "$package_id" > "$app_stage/PACKAGE_ID"
printf '%s\n' KT5 > "$app_stage/MODEL_CODE"
printf '%s\n' "$firmware" > "$app_stage/FIRMWARE"
chmod 0755 "$app_stage/bin/"*.sh "$app_stage/bin/touch-controller" \
    "$extension_stage/"*.sh 2>/dev/null || true

# Preserve only the project-owned endpoint and explicit browser-risk choice.
# Cached pages and all user book/calibre paths are outside this transaction.
if [ -f "$app_base/current/config/base-url" ] && \
   [ ! -L "$app_base/current/config/base-url" ]; then
    endpoint_size=$(wc -c < "$app_base/current/config/base-url" | tr -d ' ')
    if [ "$endpoint_size" -le 4096 ]; then
        cp "$app_base/current/config/base-url" "$app_stage/config/base-url"
    fi
fi
if [ -f "$app_base/current/config/article-browser-enabled" ] && \
   [ ! -L "$app_base/current/config/article-browser-enabled" ] && \
   [ "$(sed -n '1p' "$app_base/current/config/article-browser-enabled")" = \
       kindle-brief-internal-browser-risk-accepted-v1 ]; then
    cp "$app_base/current/config/article-browser-enabled" \
        "$app_stage/config/article-browser-enabled"
fi

# macOS may materialize extended attributes as AppleDouble files on the
# Kindle's FAT volume even with COPYFILE_DISABLE. They are never package
# payload and must not enter the promoted application or KUAL entry.
find "$app_stage" "$extension_stage" -type f -name '._*' -exec rm -f {} \;

current_package_id=
if [ -r "$app_base/current/PACKAGE_ID" ]; then
    IFS= read -r current_package_id < "$app_base/current/PACKAGE_ID" || true
fi
if [ "$current_package_id" != "$package_id" ]; then
    if [ -d "$app_base/previous" ]; then
        rm -rf "$app_base/previous"
    fi
    if [ -d "$app_base/current" ]; then
        mv "$app_base/current" "$app_base/previous"
    fi
    if ! mv "$app_stage" "$app_base/current"; then
        if [ -d "$app_base/previous" ] && [ ! -e "$app_base/current" ]; then
            mv "$app_base/previous" "$app_base/current" || true
        fi
        kb_host_die "could not promote staged release"
    fi
else
    if ! mv "$app_base/current" "$app_repair_backup"; then
        kb_host_die "could not stage current release for repair"
    fi
    app_repair_active=1
    if ! mv "$app_stage" "$app_base/current"; then
        if [ ! -e "$app_base/current" ] && \
           mv "$app_repair_backup" "$app_base/current"; then
            app_repair_active=0
        fi
        kb_host_die "could not promote repaired release"
    fi
fi

if [ -d "$extension_root" ]; then
    mv "$extension_root" "$extension_backup"
fi
if ! mv "$extension_stage" "$extension_root"; then
    if [ -d "$extension_backup" ]; then
        mv "$extension_backup" "$extension_root" || true
    fi
    kb_host_die "could not promote KUAL entry"
fi
if [ -d "$extension_backup" ]; then
    rm -rf "$extension_backup"
fi
app_repair_active=0
if [ -d "$app_repair_backup" ]; then
    rm -rf "$app_repair_backup"
fi

# Directory creation and promotion on a macOS-mounted FAT volume can create
# additional AppleDouble files outside the staging directories.
find "$app_base" "$extension_root" -type f -name '._*' -exec rm -f {} \;
rm -f "$mount_path/._kindle-brief" "$extension_parent/._Dashboard"

trap - EXIT HUP INT TERM
printf '%s\n' \
    "Installed InkBrief package $package_id" \
    "Model: KT5" \
    "Firmware: $firmware" \
    "Autostart: disabled"
