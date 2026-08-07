#!/bin/sh

RESTORE_SCRIPT_DIR=$(CDPATH= cd "$(dirname "$0")" && pwd -P)
. "$RESTORE_SCRIPT_DIR/common.sh"

# Kindle Brief never stops the framework or stock launcher. Starting the stock
# Home URI asks appmgrd to bring it back to the foreground after our exclusive
# input descriptor is closed. Failures are intentionally non-fatal so cleanup
# can continue on firmware variants.
if command -v lipc-set-prop >/dev/null 2>&1; then
    lipc-set-prop com.lab126.appmgrd start app://com.lab126.booklet.home \
        >/dev/null 2>&1 || true
fi

sleep 1
if kb_fbink=$(kb_find_fbink 2>/dev/null); then
    "$kb_fbink" -q -f -W GC16 -s >/dev/null 2>&1 || true
fi

exit 0
