#!/bin/sh
set -eu

STOP_SCRIPT_DIR=$(CDPATH= cd "$(dirname "$0")" && pwd -P)
. "$STOP_SCRIPT_DIR/common.sh"

if kb_pid=$(kb_read_pid 2>/dev/null); then
    kill -TERM "$kb_pid" 2>/dev/null || true
    waited=0
    while kb_valid_pid "$kb_pid" && [ "$waited" -lt 8 ]; do
        sleep 1
        waited=$((waited + 1))
    done
    if kb_valid_pid "$kb_pid"; then
        kill -KILL "$kb_pid" 2>/dev/null || true
    fi
fi

/bin/sh "$KB_APP_ROOT/bin/restore-ui.sh" >/dev/null 2>&1 || true
exit 0
