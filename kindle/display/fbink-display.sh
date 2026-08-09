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
refresh_mode=${2:-full}
case "$refresh_mode" in
    full|partial) ;;
    *)
        kb_log "refresh mode must be full or partial"
        exit 2
        ;;
esac

fbink=$(kb_find_fbink) || {
    kb_log "FBInk not found in hdnext (/var/local/kmc/bin), libkh, or PATH"
    exit 3
}

# Draw into the framebuffer without refreshing, then submit exactly one screen
# update. GL16 requests 16-level output without a black flash between page
# swipes; periodic flashing GC16 updates clear accumulated ghosting.
"$fbink" -q -b -c -i "$image" \
    -g halign=CENTER,valign=CENTER,w=-1,h=-1,dither
case "$refresh_mode" in
    full) "$fbink" -q -w -f -W GC16 -s ;;
    partial)
        if ! "$fbink" -q -w -W GL16 -s; then
            kb_log "GL16 refresh failed; retrying with flashing GC16"
            "$fbink" -q -w -f -W GC16 -s
        fi
        ;;
esac
