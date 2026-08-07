#!/bin/sh

# Shared Kindle-side helpers. Keep this file compatible with BusyBox ash.

KB_SCRIPT_DIR=$(CDPATH= cd "$(dirname "$0")" && pwd -P)
KB_APP_ROOT=${KINDLE_BRIEF_ROOT:-$(dirname "$KB_SCRIPT_DIR")}
KB_STATE_DIR=${KINDLE_BRIEF_STATE_DIR:-/tmp/kindle-brief}
KB_PID_FILE=$KB_STATE_DIR/dashboard.pid
KB_CONTROLLER_PID_FILE=$KB_STATE_DIR/touch-controller.pid
KB_LOCK_DIR=$KB_STATE_DIR/dashboard.lock
KB_LOG_FILE=$KB_STATE_DIR/dashboard.log

kb_log() {
    printf '%s\n' "kindle-brief: $*" >&2
    if command -v logger >/dev/null 2>&1; then
        logger -t kindle-brief -- "$*" 2>/dev/null || true
    fi
}

kb_find_command() {
    kb_name=$1
    for kb_candidate in \
        "/var/local/kmc/bin/$kb_name" \
        "/mnt/us/libkh/bin/$kb_name"
    do
        if [ -x "$kb_candidate" ]; then
            printf '%s\n' "$kb_candidate"
            return 0
        fi
    done
    command -v "$kb_name" 2>/dev/null || return 1
}

kb_find_fbink() {
    kb_find_command fbink
}

kb_valid_pid() {
    kb_pid=$1
    case "$kb_pid" in
        ''|*[!0-9]*) return 1 ;;
    esac
    [ "$kb_pid" -gt 1 ] 2>/dev/null || return 1
    kill -0 "$kb_pid" 2>/dev/null || return 1

    # Never signal an unrelated process after PID reuse.
    if [ -r "/proc/$kb_pid/cmdline" ]; then
        tr '\000' ' ' < "/proc/$kb_pid/cmdline" |
            grep -F 'kindle-brief/current/bin/dashboard.sh' >/dev/null 2>&1 || return 1
    fi
    return 0
}

kb_read_pid() {
    [ -r "$KB_PID_FILE" ] || return 1
    IFS= read -r kb_pid < "$KB_PID_FILE" || return 1
    kb_valid_pid "$kb_pid" || return 1
    printf '%s\n' "$kb_pid"
}

kb_valid_controller_pid() {
    kb_pid=$1
    case "$kb_pid" in
        ''|*[!0-9]*) return 1 ;;
    esac
    [ "$kb_pid" -gt 1 ] 2>/dev/null || return 1
    kill -0 "$kb_pid" 2>/dev/null || return 1
    if [ -r "/proc/$kb_pid/cmdline" ]; then
        tr '\000' ' ' < "/proc/$kb_pid/cmdline" |
            grep -F 'kindle-brief/current/bin/touch-controller' >/dev/null 2>&1 || return 1
    fi
    return 0
}

kb_show_message() {
    kb_message=$1
    kb_fbink=$(kb_find_fbink 2>/dev/null) || {
        kb_log "$kb_message"
        return 1
    }
    "$kb_fbink" -q -c -f -m -M -S 2 "$kb_message" >/dev/null 2>&1 || {
        kb_log "$kb_message"
        return 1
    }
}

kb_positive_integer() {
    case "$1" in
        ''|*[!0-9]*|0) return 1 ;;
    esac
    return 0
}

kb_owned_cache_dir() {
    kb_cache_dir=$1
    [ -d "$kb_cache_dir" ] && [ ! -L "$kb_cache_dir" ] && \
        [ "$(sed -n '1p' "$kb_cache_dir/.kindle-brief-cache" 2>/dev/null || true)" = \
            kindle-brief-cache-v1 ]
}
