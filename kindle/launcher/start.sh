#!/bin/sh
set -eu

START_SCRIPT_DIR=$(CDPATH= cd "$(dirname "$0")" && pwd -P)
. "$START_SCRIPT_DIR/common.sh"

if kb_pid=$(kb_read_pid 2>/dev/null); then
    kb_show_message "Dashboard is already running (PID $kb_pid)" || true
    exit 0
fi

mkdir -p "$KB_STATE_DIR"
: > "$KB_LOG_FILE"
if command -v nohup >/dev/null 2>&1; then
    nohup /bin/sh "$KB_APP_ROOT/bin/dashboard.sh" </dev/null \
        >> "$KB_LOG_FILE" 2>&1 &
else
    /bin/sh "$KB_APP_ROOT/bin/dashboard.sh" </dev/null \
        >> "$KB_LOG_FILE" 2>&1 &
fi
launcher_pid=$!

# Confirm that launch did not fail immediately, while returning promptly to
# KUAL. This action never enables autostart or performs a network update.
sleep 1
if kill -0 "$launcher_pid" 2>/dev/null; then
    exit 0
fi

kb_show_message "Dashboard failed to start. Open Diagnostics." || true
exit 1
