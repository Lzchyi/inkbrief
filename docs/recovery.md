# Recovery and uninstall

Use the narrowest recovery action first. Kindle Brief is designed so a page,
network, or touch failure does not require removing books, resetting the
device, or undoing the jailbreak.

## Return to the stock UI

While the dashboard is visible, try in this order:

1. Tap the visible top-left **HOME** target.
2. Hold the top-right corner for at least three seconds.
3. Wait for the maximum runtime (30 minutes by default).
4. Open KUAL and choose **Stop / Return to Library** if KUAL is reachable.
5. Use the Kindle's normal restart procedure only if the UI remains
   unresponsive.

The controller releases its exclusive input grab when it exits. A separate
watchdog also stops a stranded controller and requests the stock Home UI if the
dashboard shell crashes or is killed. The stock framework is not stopped by
the application.

## Diagnose without changing storage

KUAL → **Dashboard → Diagnostics** reports the installed version, firmware,
process state, FBInk path, touch-controller presence, update configuration, and
available page count. Runtime logs live in RAM at:

```text
/tmp/kindle-brief/dashboard.log
```

They disappear at reboot and do not modify the book library. Useful checks:

- `Pages: 0/5`: package pages are missing or damaged; reinstall a verified
  package.
- `FBInk: missing`: repair the current hdnext/KPM environment before launching.
- `Touch: missing`: reinstall a checksummed package; do not substitute an
  unverified binary.
- `Update: not-configured`: create the project-owned HTTPS `config/base-url`.
- Update download/checksum error: leave the current cache in place, verify the
  Pages URL and deployment, then retry with **Start Dashboard** or the manual
  update action.

## Roll back content

A failed update is staged separately and does not replace `cache/current`. A
successful update moves the former cache to `cache/previous`. The application
does not currently offer an automatic rollback menu; preserve both directories
while diagnosing. Reinstalling the host package restores its bundled pages
without touching books.

## Uninstall Kindle Brief only

First stop the dashboard. Connect USB, run the read-only detector, then:

```sh
./kindle/install/detect.sh /Volumes/Kindle
./kindle/install/uninstall.sh /Volumes/Kindle
```

The uninstaller validates the mount and refuses symlinks or unowned paths. It
removes only directories with Kindle Brief ownership markers:

- `/mnt/us/kindle-brief`
- `/mnt/us/extensions/Dashboard`

It leaves the jailbreak, hdnext, KPM, FBInk, KUAL, books, Calibre metadata, and
all other extensions unchanged. Re-running it is safe and reports that nothing
changed.

## Restore user storage

Do not restore a whole backup merely because the dashboard failed. First
compare the mounted Kindle against the pre-jailbreak backup and restore only
confirmed missing user files. Close Calibre during filesystem copies, preserve
its metadata, eject cleanly, then let Calibre rescan.

For the originally audited KT5, the dated pre-jailbreak backup is
`device-backups/2026-08-07-kt5-pre-jailbreak`. It was checked path-by-path and
with read-only content checksums for every non-regenerated file. Exclusions were
limited to macOS volume indexes/trash and Kindle-generated search, thumbnail,
KF8, and cache data. Keep that backup outside deployment artifacts and version
control.

## Removing the jailbreak

Application uninstall is not jailbreak removal. Current hdnext does not provide
a project-safe one-click uninstaller that this repository can invoke. Full
return to stock may require a factory reset and official firmware flow, which
can erase local content and has model/firmware-specific risk.

Do not automate it from this project. Back up first and follow the current
[Kindle Modding jailbreak FAQ](https://kindlemodding.org/jailbreaking/jailbreak-faq.html#can-i-un-jailbreak-my-kindle)
for the exact device state. If the device does not boot normally, stop and seek
model-specific recovery help rather than experimenting with firmware files.
