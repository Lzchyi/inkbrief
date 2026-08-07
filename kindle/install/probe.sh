#!/bin/sh
set -u

# Read-only Kindle-side probe. It writes nothing and intentionally reports only
# the non-unique model portion of the serial number.
serial=
[ -r /proc/usid ] && IFS= read -r serial < /proc/usid
model_id=
model_code=unknown
if [ "${#serial}" -ge 6 ]; then
    model_id=$(printf '%s' "$serial" | cut -c4-6)
    case "$model_id" in
        22D|25T|23A|2AQ|2AP|1XH|22C) model_code=KT5 ;;
    esac
fi

firmware=unknown
if [ -r /mnt/us/system/version.txt ]; then
    firmware=$(sed -n 's/^Kindle \([0-9][0-9.]*\).*$/\1/p' \
        /mnt/us/system/version.txt | head -n 1)
elif [ -r /etc/prettyversion.txt ]; then
    firmware=$(sed -n 's/.*Kindle[^0-9]*\([0-9][0-9.]*\).*/\1/p' \
        /etc/prettyversion.txt | head -n 1)
fi
[ -n "$firmware" ] || firmware=unknown

fbink=missing
for candidate in /var/local/kmc/bin/fbink /mnt/us/libkh/bin/fbink; do
    if [ -x "$candidate" ]; then
        fbink=$candidate
        break
    fi
done
kpm=missing
for candidate in /var/local/kmc/bin/kpm /mnt/us/libkh/bin/kpm; do
    if [ -x "$candidate" ]; then
        kpm=$candidate
        break
    fi
done

printf '%s\n' \
    "model_id=$model_id" \
    "model_code=$model_code" \
    "firmware=$firmware" \
    "machine=$(uname -m 2>/dev/null || printf unknown)" \
    "fbink=$fbink" \
    "kpm=$kpm"

controller=/mnt/us/kindle-brief/current/bin/touch-controller
if [ -x "$controller" ]; then
    "$controller" --probe 2>/dev/null || true
fi
exit 0
