#!/bin/sh
set -eu

INSTALL_DIR=$(CDPATH= cd "$(dirname "$0")" && pwd -P)
KINDLE_DIR=$(dirname "$INSTALL_DIR")
REPO_ROOT=$(dirname "$KINDLE_DIR")
. "$INSTALL_DIR/host-lib.sh"

version=$(sed -n '1p' "$KINDLE_DIR/VERSION")
case "$version" in
    ''|*[!0-9A-Za-z._-]*) kb_host_die "invalid Kindle package version" ;;
esac

packaged_base_url=${KINDLE_BRIEF_BASE_URL:-}
if [ -n "$packaged_base_url" ]; then
    [ "${#packaged_base_url}" -le 4096 ] || \
        kb_host_die "KINDLE_BRIEF_BASE_URL is too long"
    case "$packaged_base_url" in
        https://?*) ;;
        *) kb_host_die "KINDLE_BRIEF_BASE_URL must use HTTPS" ;;
    esac
    case "$packaged_base_url" in
        *[!A-Za-z0-9._~:/?#\[\]@!$\&\'\(\)*+,\;=%-]*)
            kb_host_die "KINDLE_BRIEF_BASE_URL contains unsupported characters"
            ;;
        *\?*|*\#*)
            kb_host_die "KINDLE_BRIEF_BASE_URL must not contain a query or fragment"
            ;;
    esac
    packaged_base_rest=${packaged_base_url#https://}
    packaged_base_authority=${packaged_base_rest%%/*}
    case "$packaged_base_authority" in
        ''|*@*) kb_host_die "KINDLE_BRIEF_BASE_URL has an invalid authority" ;;
    esac
    while [ "${packaged_base_url%/}" != "$packaged_base_url" ]; do
        packaged_base_url=${packaged_base_url%/}
    done
fi

output=${1:-$KINDLE_DIR/dist/kindle-brief-$version}
output_parent=$(dirname "$output")
mkdir -p "$output_parent"
output_parent=$(kb_host_canonical_dir "$output_parent") || kb_host_die "invalid output parent"
output=$output_parent/$(basename "$output")
case "$(basename "$output")" in
    kindle-brief-*) ;;
    *) kb_host_die "package output basename must begin with kindle-brief-" ;;
esac

if [ -e "$output" ]; then
    [ -f "$output/.kindle-brief-package" ] || \
        kb_host_die "refusing to replace unowned output: $output"
    rm -rf "$output"
fi

stage=$(mktemp -d "$output_parent/.kindle-brief-package.XXXXXX")
cleanup_package() {
    rm -rf "$stage" 2>/dev/null || true
}
trap cleanup_package EXIT
trap 'exit 129' HUP
trap 'exit 130' INT
trap 'exit 143' TERM
mkdir -p "$stage/payload/app/bin" "$stage/payload/app/config" \
    "$stage/payload/app/pages" "$stage/payload/app/source" "$stage/payload/kual"

cp "$KINDLE_DIR/launcher/common.sh" "$stage/payload/app/bin/common.sh"
cp "$KINDLE_DIR/launcher/start.sh" "$stage/payload/app/bin/start.sh"
cp "$KINDLE_DIR/launcher/stop.sh" "$stage/payload/app/bin/stop.sh"
cp "$KINDLE_DIR/launcher/dashboard.sh" "$stage/payload/app/bin/dashboard.sh"
cp "$KINDLE_DIR/launcher/failsafe.sh" "$stage/payload/app/bin/failsafe.sh"
cp "$KINDLE_DIR/launcher/restore-ui.sh" "$stage/payload/app/bin/restore-ui.sh"
cp "$KINDLE_DIR/launcher/update.sh" "$stage/payload/app/bin/update.sh"
cp "$KINDLE_DIR/launcher/diagnostics.sh" "$stage/payload/app/bin/diagnostics.sh"
cp "$KINDLE_DIR/display/fbink-display.sh" "$stage/payload/app/bin/fbink-display.sh"
cp "$KINDLE_DIR/navigation/touch_controller.c" "$stage/payload/app/source/touch_controller.c"
cp "$KINDLE_DIR/install/probe.sh" "$stage/payload/app/bin/probe.sh"
cp "$KINDLE_DIR/launcher/runtime.conf" "$stage/payload/app/config/runtime.conf"
cp "$KINDLE_DIR/launcher/base-url.example" "$stage/payload/app/config/base-url.example"
if [ -n "$packaged_base_url" ]; then
    printf '%s\n' "$packaged_base_url" > "$stage/payload/app/config/base-url"
fi
cp "$KINDLE_DIR/VERSION" "$stage/payload/app/VERSION"
cp "$KINDLE_DIR/launcher/Dashboard/menu.json" "$stage/payload/kual/menu.json"
cp "$KINDLE_DIR/launcher/Dashboard/start.sh" "$stage/payload/kual/start.sh"
cp "$KINDLE_DIR/launcher/Dashboard/stop.sh" "$stage/payload/kual/stop.sh"
cp "$KINDLE_DIR/launcher/Dashboard/update.sh" "$stage/payload/kual/update.sh"
cp "$KINDLE_DIR/launcher/Dashboard/diagnostics.sh" "$stage/payload/kual/diagnostics.sh"

touch_binary=${KINDLE_BRIEF_TOUCH_BINARY:-$KINDLE_DIR/navigation/touch-controller-armhf}
[ -r "$touch_binary" ] || kb_host_die \
    "missing ARM hard-float touch controller; run kindle/navigation/build.sh"
if command -v file >/dev/null 2>&1; then
    file "$touch_binary" | grep -E 'ELF 32-bit.*ARM' >/dev/null || \
        kb_host_die "touch controller is not a 32-bit ARM ELF binary"
fi
abi_verified=0
for candidate in "${READELF:-}" arm-linux-gnueabihf-readelf readelf llvm-readelf; do
    [ -n "$candidate" ] || continue
    if command -v "$candidate" >/dev/null 2>&1 && \
       "$candidate" -A "$touch_binary" 2>/dev/null |
           grep -F 'Tag_ABI_VFP_args: VFP registers' >/dev/null; then
        abi_verified=1
        break
    fi
done
if [ "$abi_verified" -eq 0 ] && \
   [ -r "$touch_binary.abi" ] && [ -r "$touch_binary.sha256" ]; then
    pinned_abi=$(sed -n '1p' "$touch_binary.abi")
    pinned_sha=$(sed -n '1p' "$touch_binary.sha256")
    actual_touch_sha=$(kb_host_sha256 "$touch_binary") || \
        kb_host_die "cannot hash touch controller"
    if [ "$pinned_abi" = kindlehf-armv7-hardfloat-static ] && \
       [ "$pinned_sha" = "$actual_touch_sha" ]; then
        abi_verified=1
    fi
fi
[ "$abi_verified" -eq 1 ] || \
    kb_host_die "touch controller hard-float ABI could not be verified"
cp "$touch_binary" "$stage/payload/app/bin/touch-controller"
printf '%s\n' kindlehf-armv7-hardfloat-static > "$stage/payload/app/TOUCH_ABI"

pages_dir=${KINDLE_BRIEF_PAGES_DIR:-$REPO_ROOT/previews}
for page_id in home weather f1 morning-brief headlines; do
    [ -r "$pages_dir/$page_id.png" ] || \
        kb_host_die "missing rendered page: $pages_dir/$page_id.png"
    cp "$pages_dir/$page_id.png" "$stage/payload/app/pages/$page_id.png"
done

printf '%s\n' kindle-brief-owned-v1 > "$stage/payload/app/.kindle-brief-owned"
printf '%s\n' kindle-brief-owned-v1 > "$stage/payload/kual/.kindle-brief-owned"
chmod 0755 "$stage/payload/app/bin/"*.sh "$stage/payload/app/bin/touch-controller" \
    "$stage/payload/kual/"*.sh

(
    cd "$stage/payload"
    find . -type f -print | sed 's#^\./##' | LC_ALL=C sort |
        while IFS= read -r relative_path; do
            case "$relative_path" in
                *[!A-Za-z0-9._/-]*) kb_host_die "unsafe package path: $relative_path" ;;
            esac
            digest=$(kb_host_sha256 "$relative_path") || \
                kb_host_die "no SHA-256 tool is available"
            printf '%s  %s\n' "$digest" "$relative_path"
        done
) > "$stage/SHA256SUMS"

package_id=$(kb_host_sha256 "$stage/SHA256SUMS") || kb_host_die "cannot hash package manifest"
printf '%s\n' "$package_id" > "$stage/PACKAGE_ID"
printf '%s\n' "$version" > "$stage/VERSION"
printf '%s\n' kindle-brief-package-v1 > "$stage/.kindle-brief-package"
mv "$stage" "$output"
trap - EXIT HUP INT TERM
printf '%s\n' "$output"
