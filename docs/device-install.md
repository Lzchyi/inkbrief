# Device install checklist

This is the short, canonical checklist for the supported device. Read the full
[jailbreak and installation guide](jailbreak-and-install.md) before acting.
Current physical progress is recorded separately in the
[deployment log](deployment-log.md).

## Supported target only

- Kindle 11th generation (2022)
- Model code `KT5`
- Firmware `5.19.2.0.1`
- Expected macOS USB mount `/Volumes/Kindle`

Stop on any mismatch. Do not infer support from screen size, storage capacity,
or a similar retail name.

## Read-only preflight

Close Calibre, connect USB, and run:

```sh
./kindle/install/detect.sh /Volumes/Kindle
./kindle/install/verify-backup.sh /Volumes/Kindle \
  device-backups/2026-08-07-kt5-pre-jailbreak
```

Detection must report exactly `KT5` and `5.19.2.0.1`; backup verification must
report a match. These commands do not copy, delete, or install anything.

## Physical prerequisite gate

SpringBreak and the required homebrew stack must be completed by the user on
the physical device before Kindle Brief installation. Follow the pinned
SpringBreak v1.2 procedure, its Airplane Mode gates, and its mandatory cleanup
run in the [full guide](jailbreak-and-install.md). Then verify current hdnext,
KPM, FBInk, and KUAL behavior.

Do not install duplicate legacy hotfixes. Do not invent a Kindle Brief KPM
package: this release intentionally has no published KPM ID or manifest.

## Build and package on the host

```sh
make validate
make preview
make package-kindle
```

This produces a checksummed local package from the five rendered pages. It
does not touch the Kindle.

## Explicit install gate

Only after the user confirms jailbreak/homebrew completion, reconnect the exact
device, close Calibre again, repeat detection and backup verification, then:

```sh
./kindle/install/install.sh /Volumes/Kindle
```

The installer performs all package, mount, firmware, model, ownership, symlink,
and capacity checks before its first write. It owns only:

- `/mnt/us/kindle-brief`
- `/mnt/us/extensions/Dashboard`

It does not write books, Calibre metadata, the Library database, or a boot hook.

## First-run acceptance

After a clean eject, verify KUAL Dashboard diagnostics, all five pages, both
swipe directions, top-left HOME, the three-second top-right failsafe, timeout,
manual update, stock Library return, an existing book, and Calibre reconnection.
Physical KT5 touch orientation and the stock-Home transition remain acceptance
gates until actually observed.

For removal or recovery, use [Rollback](rollback.md) and
[Recovery](recovery.md); do not factory-reset for an application-level issue.
