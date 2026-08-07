#!/bin/sh
set -eu

DISPLAY_SCRIPT_DIR=$(CDPATH= cd "$(dirname "$0")" && pwd -P)
if [ -r "$DISPLAY_SCRIPT_DIR/common.sh" ]; then
    . "$DISPLAY_SCRIPT_DIR/common.sh"
else
    . "$DISPLAY_SCRIPT_DIR/../launcher/common.sh"
fi

image=${1:-}
[ -n "$image" ] && [ -r "$image" ] || {
    kb_log "page image is missing or unreadable"
    exit 2
}

fbink=$(kb_find_fbink) || {
    kb_log "FBInk not found in hdnext (/var/local/kmc/bin), libkh, or PATH"
    exit 3
}

# Draw into the framebuffer without refreshing, then issue one full GC16
# refresh. Every rendered page already carries the high-contrast house icon
# matching the controller's generous top-left hotspot.
"$fbink" -q -b -c -i "$image" \
    -g halign=CENTER,valign=CENTER,w=-1,h=-1,dither
"$fbink" -q -f -W GC16 -s
