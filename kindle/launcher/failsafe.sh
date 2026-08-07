#!/bin/sh
set -u

FAILSAFE_SCRIPT_DIR=$(CDPATH= cd "$(dirname "$0")" && pwd -P)
. "$FAILSAFE_SCRIPT_DIR/common.sh"

owner_pid=${1:-}
timeout_seconds=${2:-1800}
kb_positive_integer "$owner_pid" || exit 2
kb_positive_integer "$timeout_seconds" || exit 2

elapsed=0
while kb_valid_pid "$owner_pid"; do
    if [ "$elapsed" -ge "$timeout_seconds" ]; then
        kill -TERM "$owner_pid" 2>/dev/null || true
        sleep 3
        if kb_valid_pid "$owner_pid"; then
            kill -KILL "$owner_pid" 2>/dev/null || true
        fi
        break
    fi
    sleep 1
    elapsed=$((elapsed + 1))
done

# A SIGKILL of the shell cannot run its trap. In that case explicitly stop the
# separately parented controller so the kernel closes its grabbed input fd.
if [ -r "$KB_CONTROLLER_PID_FILE" ]; then
    IFS= read -r controller_pid < "$KB_CONTROLLER_PID_FILE" || controller_pid=
    if kb_valid_controller_pid "$controller_pid"; then
        kill -TERM "$controller_pid" 2>/dev/null || true
        sleep 1
        if kb_valid_controller_pid "$controller_pid"; then
            kill -KILL "$controller_pid" 2>/dev/null || true
        fi
    fi
fi

# If the launcher crashed or was SIGKILLed, this independent process still
# requests stock Home and a full refresh. The kernel releases EVIOCGRAB when
# the touch-controller process exits or its descriptor is closed.
/bin/sh "$KB_APP_ROOT/bin/restore-ui.sh" >/dev/null 2>&1 || true
exit 0
