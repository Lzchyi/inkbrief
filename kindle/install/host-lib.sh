#!/bin/sh

kb_host_die() {
    printf '%s\n' "error: $*" >&2
    exit 1
}

kb_host_canonical_dir() {
    [ -d "$1" ] || return 1
    (CDPATH= cd "$1" 2>/dev/null && pwd -P)
}

kb_host_firmware() {
    kb_version_file=$1/system/version.txt
    [ -r "$kb_version_file" ] || return 1
    sed -n 's/^Kindle \([0-9][0-9.]*\).*$/\1/p' "$kb_version_file" | head -n 1
}

kb_host_probe_value() {
    kb_probe_key=$1
    kb_probe_file=$2
    [ -r "$kb_probe_file" ] || return 1
    awk -F= -v key="$kb_probe_key" '$1 == key { print substr($0, length(key) + 2) }' \
        "$kb_probe_file" | head -n 1
}

kb_host_model_from_id() {
    case "$1" in
        22D|25T|23A|2AQ|2AP|1XH|22C) printf '%s\n' KT5 ;;
        *) return 1 ;;
    esac
}

kb_host_usb_model() {
    command -v ioreg >/dev/null 2>&1 || return 1
    kb_models=
    kb_model_count=0
    while IFS= read -r kb_serial; do
        case "$kb_serial" in
            G09?????????????) ;;
            *) continue ;;
        esac
        kb_model_id=$(printf '%s' "$kb_serial" | cut -c4-6)
        kb_model=$(kb_host_model_from_id "$kb_model_id" 2>/dev/null || \
            printf 'NOT-KT5-%s' "$kb_model_id")
        kb_models=$kb_model
        kb_model_count=$((kb_model_count + 1))
    done <<EOF
$(ioreg -p IOUSB -l -w 0 2>/dev/null |
    sed -n 's/.*"USB Serial Number" = "\([A-Z0-9][A-Z0-9]*\)".*/\1/p')
EOF
    [ "$kb_model_count" -gt 0 ] || return 1
    if [ "$kb_model_count" -ne 1 ]; then
        printf '%s\n' AMBIGUOUS
        return 0
    fi
    printf '%s\n' "$kb_models"
}

kb_host_is_mountpoint() {
    kb_mount=$1
    if [ "${KINDLE_BRIEF_ALLOW_FAKE_MOUNT:-0}" = 1 ]; then
        return 0
    fi
    kb_parent=$(dirname "$kb_mount")
    kb_device=$(df -P "$kb_mount" 2>/dev/null | awk 'NR == 2 { print $1 }')
    kb_parent_device=$(df -P "$kb_parent" 2>/dev/null | awk 'NR == 2 { print $1 }')
    [ -n "$kb_device" ] && [ "$kb_device" != "$kb_parent_device" ]
}

kb_host_validate_mount() {
    kb_mount=$(kb_host_canonical_dir "$1") || kb_host_die "mount path does not exist: $1"
    case "$kb_mount" in
        /|'') kb_host_die "refusing unsafe mount path" ;;
    esac
    kb_host_is_mountpoint "$kb_mount" || \
        kb_host_die "path is not a mounted volume: $kb_mount"
    [ -d "$kb_mount/documents" ] || \
        kb_host_die "target has no Kindle documents directory"
    [ -d "$kb_mount/system" ] || kb_host_die "target has no Kindle system directory"
    [ -r "$kb_mount/system/version.txt" ] || \
        kb_host_die "Kindle firmware is not detectable on target"
    printf '%s\n' "$kb_mount"
}

kb_host_sha256() {
    if command -v shasum >/dev/null 2>&1; then
        shasum -a 256 "$1" | awk '{print $1}'
    elif command -v sha256sum >/dev/null 2>&1; then
        sha256sum "$1" | awk '{print $1}'
    else
        return 1
    fi
}

kb_host_valid_sha256() {
    [ "${#1}" -eq 64 ] || return 1
    case "$1" in
        *[!0-9a-f]*) return 1 ;;
    esac
}

kb_host_owned_dir() {
    [ -d "$1" ] && [ -f "$1/.kindle-brief-owned" ] &&
        [ "$(sed -n '1p' "$1/.kindle-brief-owned")" = "kindle-brief-owned-v1" ]
}
