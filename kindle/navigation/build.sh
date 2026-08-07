#!/bin/sh
set -eu

NAVIGATION_DIR=$(CDPATH= cd "$(dirname "$0")" && pwd -P)
output=${1:-$NAVIGATION_DIR/touch-controller-armhf}

if [ -n "${ZIG:-}" ]; then
    command -v "$ZIG" >/dev/null 2>&1 || {
        printf '%s\n' "error: ZIG does not name an executable" >&2
        exit 2
    }
    "$ZIG" cc -target arm-linux-musleabihf \
        -std=c11 -Os -Wall -Wextra -Werror -static -mcpu=cortex_a7 \
        "$NAVIGATION_DIR/touch_controller.c" -o "$output"
    compiler=
else
    compiler=${CC:-arm-linux-gnueabihf-gcc}
    command -v "$compiler" >/dev/null 2>&1 || {
        printf '%s\n' "error: install a hard-float cross-compiler, set CC, or set ZIG" >&2
        exit 2
    }
    target=$($compiler -dumpmachine 2>/dev/null || true)
    case "$target" in
        arm*-linux-*eabihf*) ;;
        *)
            printf '%s\n' "error: compiler target '$target' is not ARM hard-float" >&2
            exit 2
            ;;
    esac
    "$compiler" \
        -std=c11 -Os -Wall -Wextra -Werror -static \
        -ffunction-sections -fdata-sections \
        -march=armv7-a -mfpu=vfpv3-d16 -mfloat-abi=hard \
        -Wl,--gc-sections -s \
        "$NAVIGATION_DIR/touch_controller.c" -o "$output"
fi
chmod 0755 "$output"

if [ -n "${compiler:-}" ]; then
    readelf_tool=${READELF:-}
    compiler_dir=$(dirname "$(command -v "$compiler")")
    compiler_name=$(basename "$compiler")
    compiler_prefix=${compiler_name%gcc}
    if [ -z "$readelf_tool" ] && [ -x "$compiler_dir/${compiler_prefix}readelf" ]; then
        readelf_tool=$compiler_dir/${compiler_prefix}readelf
    elif [ -z "$readelf_tool" ] && command -v readelf >/dev/null 2>&1; then
        readelf_tool=readelf
    fi
    if [ -z "$readelf_tool" ]; then
        printf '%s\n' "error: no readelf tool is available to verify the ABI" >&2
        exit 3
    fi
    "$readelf_tool" -A "$output" |
        grep -F 'Tag_ABI_VFP_args: VFP registers' >/dev/null || {
            printf '%s\n' "error: output is not tagged for the hard-float ABI" >&2
            exit 3
        }
fi

if command -v shasum >/dev/null 2>&1; then
    shasum -a 256 "$output" | awk '{print $1}' > "$output.sha256"
elif command -v sha256sum >/dev/null 2>&1; then
    sha256sum "$output" | awk '{print $1}' > "$output.sha256"
else
    printf '%s\n' "error: no SHA-256 tool is available" >&2
    exit 3
fi
printf '%s\n' kindlehf-armv7-hardfloat-static > "$output.abi"
printf '%s\n' "$output"
