# Kindle runtime

This directory contains the optional, manually launched Kindle layer. It is
pinned to **KT5 / firmware 5.19.2.0.1**. It never installs a boot hook and its
host tools own only these USB paths:

- `/mnt/us/kindle-brief`
- `/mnt/us/extensions/Dashboard`

`documents`, Calibre metadata, Amazon content, and the root filesystem are
outside the install and uninstall transactions.

## Read-only checks

On macOS, `install/detect.sh` reports one unambiguous USB mass-storage mount,
firmware, and (when the USB serial can be mapped safely) model code. On the
Kindle, `install/probe.sh` reports the non-unique model ID, firmware, hdnext
FBInk/KPM paths, architecture, and touch ranges without writing anything.

## Build and package

`navigation/build.sh` accepts either an `arm-linux-gnueabihf-gcc` compiler or
`ZIG=/path/to/zig`. It emits a static ARMv7 hard-float controller plus pinned
ABI and SHA-256 sidecars. `install/package.sh` then stages the controller,
rendered pages, runtime scripts, and KUAL menu into a checksummed package.

The checked-in controller was reproducibly compiled from
`navigation/touch_controller.c` with Zig 0.16.0, target
`arm-linux-musleabihf`, CPU `cortex_a7`, and SHA-256
`6381df2bd57582c399975fd2df92294efd1475fb3313da4c4c42113b1176924d`.

## Runtime safety

The dashboard grabs only the selected evdev touchscreen. A visible top-left
`HOME` target exits immediately; horizontal swipes change pages; holding the
top-right corner for three seconds is a second exit path. A short tap on a
verified news-row hitbox releases the input grab, restores the stock UI, and
opens that row's HTTPS article in the Kindle Chromium browser only after the
user selects **Enable Article Links (Browser Risk)** in KUAL. The choice can be
revoked at any time with **Disable Article Links**. KUAL Stop, a
30-minute controller deadline, parent-death signaling, and an independent
watchdog all release input and request stock Kindle Home. The stock framework
is never stopped.

Touch orientation, swipes, and the stock-Home transition are confirmed on the
target KT5. Arbitrary article launch uses Amazon's internal Chromium entrypoint
with its stock single-process/no-sandbox flags. It is disabled by default and
still requires one physical acceptance test on firmware 5.19.2.0.1.

## Update contract

Update checks run once during each configured manual Dashboard launch and are
also available through the explicit KUAL update action. Both paths require
`curl` with HTTPS protocol restrictions and bounded downloads; the updater
refuses `wget` because its Kindle build cannot guarantee HTTPS-only redirects.
Launch checks share one 20-second network budget; the explicit manual action
keeps the 90-second per-transfer limit. The endpoint must be one regular,
bounded file containing a single public HTTPS root without userinfo, a query,
or a fragment.
`<base>/profiles/kt5/current.json` must use the supported schema and name
`profile_id`, `model_code`, `release_id`, `manifest_sha256`, and
`sha256sums_sha256`, plus bounded `links_sha256` and `links_bytes`. A pointer
matching the installed `RELEASE_ID` is a
successful no-op only after the cached manifest, checksum sidecar, five page
hashes, link map, and PNG contracts are revalidated against that pointer. A new
or locally damaged release must contain `manifest.json`, `SHA256SUMS`, the
separately checksummed `links.tsv`, and exactly these page files in
`SHA256SUMS`:

- `pages/home.png`
- `pages/weather.png`
- `pages/f1.png`
- `pages/morning-brief.png`
- `pages/headlines.png`

The updater downloads into an owned staging directory and promotes it only
after schemas, release identity, hashes, bounded HTTPS link rows, page metadata,
1072×1448 dimensions, and 8-bit grayscale PNG encoding agree. Ordinary
promotion failures and caught signals restore `current`. A sudden power loss or
`SIGKILL` between FAT renames can leave only the owned `previous`; the dashboard
uses it immediately and the next launch or manual update renames it back to
`current` before network access.
After a successful update, the last cache remains as `previous`. No update
runs at boot or on a background schedule. A KPM package is intentionally
deferred in `kpm/DEFERRED.md`.
