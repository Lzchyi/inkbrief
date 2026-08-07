# Rollback

Choose the smallest rollback that matches the failure. Kindle Brief content,
application files, homebrew prerequisites, and the jailbreak are separate
layers.

## Failed or bad content update

The updater downloads to an owned staging directory and verifies the KT5
profile plus all hashes before promotion. A failed download or checksum leaves
`cache/current` unchanged. After a successful update, the former cache is kept
as `cache/previous` for diagnosis.

Ordinary promotion errors and caught termination signals restore `current`.
FAT cannot make the two directory renames power-loss atomic: abrupt power loss
or `SIGKILL` in that narrow window may leave the owned release only at
`cache/previous`. Dashboard startup uses that owned fallback before bundled
pages, Diagnostics counts it, and the next launch or manual update restores it
to `cache/current` before attempting a download.

There is no automatic rollback button for `previous`. Preserve both caches and
fix the static deployment or base URL first. A newly verified update can replace
the bad current release without touching the application or books.

## Application package rollback

The host installer stages each owned release and retains one owned
`/mnt/us/kindle-brief/previous` application version on upgrade. Do not manually
swap directories while the dashboard is running. Stop it, preserve diagnostics,
and reinstall a previously verified host package only after checking its
manifest and exact KT5/firmware target.

## Remove Kindle Brief

Stop the dashboard, connect USB, confirm the exact mount, then:

```sh
./kindle/install/detect.sh /Volumes/Kindle
./kindle/install/uninstall.sh /Volumes/Kindle
```

The uninstaller removes only Kindle Brief-owned application and Dashboard
paths. It leaves books, Calibre metadata, KUAL, FBInk, KPM, hdnext, and the
jailbreak in place.

## Library recovery

Application rollback should never require a full storage restore. If a
path-by-path comparison proves user data is missing, close Calibre and restore
only those confirmed files from the verified dated backup. Reconnect and let
Calibre rescan afterward.

## Jailbreak removal

This repository does not automate jailbreak removal. Current hdnext has no
project-safe one-click uninstaller, and a factory reset/firmware procedure may
erase content. Follow the current official guidance linked from
[Recovery](recovery.md) only after a fresh verified backup.

The current real-device state has not been jailbroken or installed by this
project, so no rollback action is presently required. See the
[deployment log](deployment-log.md).
