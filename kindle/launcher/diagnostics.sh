#!/bin/sh
set -u

DIAGNOSTICS_SCRIPT_DIR=$(CDPATH= cd "$(dirname "$0")" && pwd -P)
. "$DIAGNOSTICS_SCRIPT_DIR/common.sh"

display_result=0
[ "${1:-}" = "--display" ] && display_result=1

version=unknown
[ -r "$KB_APP_ROOT/VERSION" ] && IFS= read -r version < "$KB_APP_ROOT/VERSION"
firmware=unknown
[ -r /mnt/us/system/version.txt ] && IFS= read -r firmware < /mnt/us/system/version.txt

if kb_pid=$(kb_read_pid 2>/dev/null); then
    running="yes (PID $kb_pid)"
else
    running=no
fi
if fbink=$(kb_find_fbink 2>/dev/null); then
    fbink_status=$fbink
else
    fbink_status=missing
fi
if [ -x "$KB_APP_ROOT/bin/touch-controller" ]; then
    touch_status=installed
else
    touch_status=missing
fi
if [ -r "$KB_APP_ROOT/config/base-url" ]; then
    update_status=configured
else
    update_status=not-configured
fi
page_count=0
cache_page_root=
if kb_owned_cache_dir "$KB_APP_ROOT/cache/current"; then
    cache_page_root=$KB_APP_ROOT/cache/current/pages
elif [ ! -e "$KB_APP_ROOT/cache/current" ] && \
     kb_owned_cache_dir "$KB_APP_ROOT/cache/previous"; then
    cache_page_root=$KB_APP_ROOT/cache/previous/pages
fi
for page_id in home weather f1 morning-brief headlines; do
    if { [ -n "$cache_page_root" ] && [ -r "$cache_page_root/$page_id.png" ]; } || \
       [ -r "$KB_APP_ROOT/pages/$page_id.png" ]; then
        page_count=$((page_count + 1))
    fi
done

report="Kindle Brief $version
Firmware: $firmware
Running: $running
FBInk: $fbink_status
Touch: $touch_status
Update: $update_status
Pages: $page_count/5"
printf '%s\n' "$report"

if [ "$display_result" -eq 1 ]; then
    kb_fbink=$(kb_find_fbink 2>/dev/null || true)
    if [ -n "$kb_fbink" ]; then
        "$kb_fbink" -q -c -f -m -M -S 2 "$report" >/dev/null 2>&1 || true
    fi
fi
exit 0
