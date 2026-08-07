#!/bin/sh
set -eu

DASHBOARD_SCRIPT_DIR=$(CDPATH= cd "$(dirname "$0")" && pwd -P)
. "$DASHBOARD_SCRIPT_DIR/common.sh"

screen_width=1072
screen_height=1448
max_runtime=1800
home_width=180
home_height=110
corner_hold_ms=3000
touch_device=
touch_swap_axes=0
touch_invert_x=0
touch_invert_y=0

if [ -r "$KB_APP_ROOT/config/runtime.conf" ]; then
    # This file is part of the owned package. Supported values are validated
    # immediately below before they influence a process or path.
    . "$KB_APP_ROOT/config/runtime.conf"
fi
for kb_number in "$screen_width" "$screen_height" "$max_runtime" \
    "$home_width" "$home_height" "$corner_hold_ms"
do
    kb_positive_integer "$kb_number" || {
        kb_log "invalid numeric runtime configuration"
        exit 2
    }
done
[ "$max_runtime" -le 28800 ] || {
    kb_log "max_runtime may not exceed 28800 seconds"
    exit 2
}
for kb_boolean in "$touch_swap_axes" "$touch_invert_x" "$touch_invert_y"; do
    case "$kb_boolean" in
        0|1) ;;
        *) kb_log "invalid touch transform configuration"; exit 2 ;;
    esac
done
case "$touch_device" in
    ''|/dev/input/event[0-9]|/dev/input/event[0-9][0-9]) ;;
    *) kb_log "invalid touch input device"; exit 2 ;;
esac

touch_controller="$KB_APP_ROOT/bin/touch-controller"
[ -x "$touch_controller" ] || {
    kb_show_message "Dashboard touch controller is not installed" || true
    exit 3
}
[ -x "$KB_APP_ROOT/bin/fbink-display.sh" ] || exit 3

mkdir -p "$KB_STATE_DIR"
if ! mkdir "$KB_LOCK_DIR" 2>/dev/null; then
    if kb_read_pid >/dev/null 2>&1; then
        exit 0
    fi
    rmdir "$KB_LOCK_DIR" 2>/dev/null || true
    mkdir "$KB_LOCK_DIR" || exit 4
fi
printf '%s\n' "$$" > "$KB_PID_FILE"

fifo=$KB_STATE_DIR/input.$$.fifo
pages_file=$KB_STATE_DIR/pages.$$.list
controller_pid=
failsafe_pid=
cleaned=0

cleanup() {
    [ "$cleaned" -eq 0 ] || return 0
    cleaned=1
    trap - EXIT HUP INT TERM

    if [ -n "$controller_pid" ]; then
        kill -TERM "$controller_pid" 2>/dev/null || true
        wait "$controller_pid" 2>/dev/null || true
    fi

    # Restore before stopping the independent watchdog. If this process dies
    # during cleanup, the watchdog remains alive and performs the same action.
    /bin/sh "$KB_APP_ROOT/bin/restore-ui.sh" >/dev/null 2>&1 || true

    rm -f "$fifo" "$pages_file" "$KB_PID_FILE" "$KB_CONTROLLER_PID_FILE" \
        2>/dev/null || true
    rmdir "$KB_LOCK_DIR" 2>/dev/null || true
    if [ -n "$failsafe_pid" ]; then
        kill -TERM "$failsafe_pid" 2>/dev/null || true
        wait "$failsafe_pid" 2>/dev/null || true
    fi
}
trap cleanup EXIT
trap 'exit 129' HUP
trap 'exit 130' INT
trap 'exit 143' TERM

: > "$pages_file"
cache_page_root=
if kb_owned_cache_dir "$KB_APP_ROOT/cache/current"; then
    cache_page_root=$KB_APP_ROOT/cache/current/pages
elif [ ! -e "$KB_APP_ROOT/cache/current" ] && \
     kb_owned_cache_dir "$KB_APP_ROOT/cache/previous"; then
    cache_page_root=$KB_APP_ROOT/cache/previous/pages
fi
for page_id in home weather f1 morning-brief headlines; do
    for page_root in "$cache_page_root" "$KB_APP_ROOT/pages"; do
        [ -n "$page_root" ] || continue
        page_path=$page_root/$page_id.png
        if [ -r "$page_path" ]; then
            printf '%s\n' "$page_path" >> "$pages_file"
            break
        fi
    done
done

page_count=$(wc -l < "$pages_file" | tr -d ' ')
if ! kb_positive_integer "$page_count"; then
    kb_show_message "No dashboard pages cached. Run Update Dashboard." || true
    exit 5
fi

mkfifo "$fifo"
/bin/sh "$KB_APP_ROOT/bin/failsafe.sh" "$$" "$max_runtime" &
failsafe_pid=$!

set -- \
    --width "$screen_width" \
    --height "$screen_height" \
    --timeout "$max_runtime" \
    --home-width "$home_width" \
    --home-height "$home_height" \
    --hold-ms "$corner_hold_ms"
[ -z "$touch_device" ] || set -- "$@" --device "$touch_device"
[ "$touch_swap_axes" -eq 0 ] || set -- "$@" --swap-axes
[ "$touch_invert_x" -eq 0 ] || set -- "$@" --invert-x
[ "$touch_invert_y" -eq 0 ] || set -- "$@" --invert-y
"$touch_controller" "$@" > "$fifo" 2>> "$KB_LOG_FILE" &
controller_pid=$!
printf '%s\n' "$controller_pid" > "$KB_CONTROLLER_PID_FILE"

page_index=1
show_page() {
    page_path=$(sed -n "${page_index}p" "$pages_file")
    /bin/sh "$KB_APP_ROOT/bin/fbink-display.sh" "$page_path"
}
show_page

while IFS= read -r event; do
    case "$event" in
        NEXT)
            page_index=$((page_index + 1))
            [ "$page_index" -le "$page_count" ] || page_index=1
            show_page
            ;;
        PREVIOUS)
            page_index=$((page_index - 1))
            [ "$page_index" -ge 1 ] || page_index=$page_count
            show_page
            ;;
        HOME|TIMEOUT)
            break
            ;;
        ERROR:*)
            kb_log "$event"
            break
            ;;
    esac
done < "$fifo"

exit 0
