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
`7708910a7b956473675a94286f3f4b0b2ebd960b4c9b69207b384056c9264077`.

## Runtime safety

The dashboard grabs only the selected evdev touchscreen. A visible top-left
`HOME` target exits immediately; horizontal swipes change pages; holding the
top-right corner for three seconds is a second exit path. KUAL Stop, a
30-minute controller deadline, parent-death signaling, and an independent
watchdog all release input and request stock Kindle Home. The stock framework
is never stopped.

Touch orientation and the stock-Home transition still require confirmation on
the physical KT5 after hdnext is installed. Until then, do not install or run
the package on the device.

## Update contract

Updates are manual and require `curl` with HTTPS protocol restrictions and
bounded downloads; the updater refuses `wget` because its Kindle build cannot
guarantee HTTPS-only redirects. `<base>/profiles/kt5/current.json` must use the
supported schema and name `profile_id`, `model_code`, `release_id`,
`manifest_sha256`, and `sha256sums_sha256`. The release directory must contain
`manifest.json`, `SHA256SUMS`, and exactly these checksummed files:

- `pages/home.png`
- `pages/weather.png`
- `pages/f1.png`
- `pages/morning-brief.png`
- `pages/headlines.png`

The updater downloads into an owned staging directory and promotes it only
after schemas, release identity, hashes, page metadata, 1072×1448 dimensions,
and 8-bit grayscale PNG encoding agree. Ordinary promotion failures and caught
signals restore `current`. A sudden power loss or `SIGKILL` between FAT renames
can leave only the owned `previous`; the dashboard uses it immediately and the
next manual update renames it back to `current` before network access. After a
successful update, the last cache remains as `previous`. A KPM package is
intentionally deferred in `kpm/DEFERRED.md`.
