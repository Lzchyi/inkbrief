#!/bin/sh
set -eu

INSTALL_DIR=$(CDPATH= cd "$(dirname "$0")" && pwd -P)
. "$INSTALL_DIR/host-lib.sh"

if [ "$#" -eq 0 ]; then
    set -- /Volumes/Kindle /Volumes/Kindle\ *
fi

matches=
match_count=0
for candidate in "$@"; do
    [ -d "$candidate/documents" ] || continue
    [ -r "$candidate/system/version.txt" ] || continue
    canonical=$(kb_host_canonical_dir "$candidate") || continue
    if ! kb_host_is_mountpoint "$canonical"; then
        continue
    fi
    firmware=$(kb_host_firmware "$canonical" 2>/dev/null || true)
    [ -n "$firmware" ] || continue
    matches=${matches}${canonical}'	'${firmware}'
'
    match_count=$((match_count + 1))
done

if [ "$match_count" -eq 0 ]; then
    printf '%s\n' "error: no unambiguous Kindle USB mass-storage mount found" >&2
    exit 2
fi
if [ "$match_count" -ne 1 ]; then
    printf '%s\n' "error: multiple Kindle-like mounts found; pass one exact mount path" >&2
    printf '%b' "$matches" >&2
    exit 3
fi

model=$(kb_host_usb_model 2>/dev/null || printf '%s' unknown)
printf '%b' "$matches" | awk -F '\t' -v model="$model" \
    '{ printf "mount=%s\nfirmware=%s\nmodel_code=%s\n", $1, $2, model }'
