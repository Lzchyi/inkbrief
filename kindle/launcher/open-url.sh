#!/bin/sh
set -eu

OPEN_URL_SCRIPT_DIR=$(CDPATH= cd "$(dirname "$0")" && pwd -P)
. "$OPEN_URL_SCRIPT_DIR/common.sh"

[ "$#" -eq 1 ] || {
    kb_log "open-url requires exactly one article URL"
    exit 2
}
article_url=$1
kb_article_browser_enabled || {
    kb_log "article browser risk has not been accepted"
    exit 7
}
kb_valid_https_url "$article_url" || {
    kb_log "refusing invalid or non-HTTPS article URL"
    exit 2
}

browser=
for browser_candidate in \
    /usr/bin/chromium/bin/kindle_browser \
    /usr/bin/chromium/kindle_browser
do
    if [ -x "$browser_candidate" ]; then
        browser=$browser_candidate
        break
    fi
done
[ -n "$browser" ] || {
    kb_log "Kindle Chromium browser is unavailable"
    exit 3
}

# A competing Chromium process can lock or corrupt the shared stock profile.
for browser_cmdline in /proc/[0-9]*/cmdline; do
    [ -r "$browser_cmdline" ] || continue
    if tr '\000' ' ' < "$browser_cmdline" | grep -F '/kindle_browser' >/dev/null 2>&1; then
        kb_log "Kindle Chromium browser is already running"
        exit 4
    fi
done

chroot_command=$(command -v chroot 2>/dev/null || true)
[ -n "$chroot_command" ] && [ -d /chroot ] || {
    kb_log "Kindle Chromium runtime is unavailable"
    exit 3
}

export XDG_CONFIG_HOME=/mnt/us/system/browser/
export LD_LIBRARY_PATH=/usr/bin/chromium/lib:/usr/bin/chromium/usr/lib:/usr/lib/
user_agent='Mozilla/5.0 (X11; U; Linux armv7l like Android; en-us) AppleWebKit/531.2+ (KHTML, like Gecko) Version/5.0 Safari/533.2+ Kindle/3.0+'

if command -v nohup >/dev/null 2>&1; then
    nohup "$chroot_command" /chroot "$browser" "$article_url" \
        --no-zygote --no-sandbox --single-process \
        --skia-resource-cache-limit-mb=64 \
        --disable-gpu --in-process-gpu --disable-gpu-sandbox \
        --disable-gpu-compositing --enable-dom-distiller \
        --enable-distillability-service --force-device-scale-factor=2 \
        --js-flags=jitless --force-gpu-mem-available-mb=40 \
        --enable-grayscale-mode --enable-low-end-device-mode \
        --enable-low-res-tiling --disable-site-isolation-trials \
        "--user-agent=$user_agent" </dev/null >> "$KB_LOG_FILE" 2>&1 &
else
    "$chroot_command" /chroot "$browser" "$article_url" \
        --no-zygote --no-sandbox --single-process \
        --skia-resource-cache-limit-mb=64 \
        --disable-gpu --in-process-gpu --disable-gpu-sandbox \
        --disable-gpu-compositing --enable-dom-distiller \
        --enable-distillability-service --force-device-scale-factor=2 \
        --js-flags=jitless --force-gpu-mem-available-mb=40 \
        --enable-grayscale-mode --enable-low-end-device-mode \
        --enable-low-res-tiling --disable-site-isolation-trials \
        "--user-agent=$user_agent" </dev/null >> "$KB_LOG_FILE" 2>&1 &
fi
browser_pid=$!

sleep 1
if ! kill -0 "$browser_pid" 2>/dev/null; then
    wait "$browser_pid" 2>/dev/null || true
    kb_log "Kindle Chromium failed during startup"
    exit 5
fi

exit 0
