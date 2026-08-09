#!/bin/sh
set -eu

BROWSER_ACCESS_SCRIPT_DIR=$(CDPATH= cd "$(dirname "$0")" && pwd -P)
. "$BROWSER_ACCESS_SCRIPT_DIR/common.sh"

marker=$KB_APP_ROOT/config/article-browser-enabled
[ -d "$KB_APP_ROOT/config" ] && [ ! -L "$KB_APP_ROOT/config" ] || {
    kb_show_message "Article browser configuration is unsafe" || true
    exit 2
}
[ ! -L "$marker" ] || {
    kb_show_message "Article browser marker may not be a symlink" || true
    exit 2
}

case "${1:-}" in
    enable)
        [ "$#" -eq 1 ] || exit 2
        temporary=$KB_APP_ROOT/config/.article-browser-enabled.$$
        trap 'rm -f "$temporary" 2>/dev/null || true' EXIT HUP INT TERM
        printf '%s\n' kindle-brief-internal-browser-risk-accepted-v1 > "$temporary"
        mv "$temporary" "$marker"
        trap - EXIT HUP INT TERM
        kb_show_message "Article links enabled. Publisher pages use internal Chromium." || true
        ;;
    disable)
        [ "$#" -eq 1 ] || exit 2
        rm -f "$marker"
        kb_show_message "Article links disabled" || true
        ;;
    *)
        kb_log "usage: browser-access.sh enable|disable"
        exit 2
        ;;
esac

exit 0
