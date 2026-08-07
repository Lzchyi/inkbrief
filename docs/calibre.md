# Calibre and library safety

Kindle Brief is designed to coexist with the existing Kindle Library and
Calibre-managed books. The dashboard is an application under project-owned USB
paths, not an EPUB/AZW document.

## Before any device operation

1. Finish pending Calibre transfers and eject from Calibre if applicable.
2. Quit Calibre so it cannot write metadata while another installer uses the
   same FAT volume.
3. Verify the dated pre-jailbreak backup:

   ```sh
   ./kindle/install/verify-backup.sh /Volumes/Kindle \
     device-backups/2026-08-07-kt5-pre-jailbreak
   ```

4. Open a sample of host-backup books independently of the Kindle.

The verifier includes documents, user content, and Calibre metadata. It ignores
only documented macOS and Kindle-generated indexes, thumbnails, and caches.

## Write boundaries

Kindle Brief install and uninstall own only:

- `/mnt/us/kindle-brief`
- `/mnt/us/extensions/Dashboard`

They do not edit `documents`, `metadata.calibre`, `driveinfo.calibre`, Amazon
content, reading positions, collections, or the Library database. The installer
refuses an unowned collision instead of overwriting it.

KUAL is a separate prerequisite. Its current manual installation may place the
official KUAL launcher files in `documents`; that user-approved prerequisite is
not a Kindle Brief book and is the only documented exception in this setup.

## After installation

- Eject the USB volume cleanly before unplugging.
- Reopen an existing book and confirm its position and cover.
- Reconnect Calibre and confirm the same device/library metadata appears.
- Confirm no Kindle Brief page appears as a Library document.
- Do not ask Calibre to manage `/mnt/us/kindle-brief` or the Dashboard extension.

If anything is missing, stop synchronization and compare against the backup
before copying files. Restore only confirmed missing user data; do not replace
the entire Kindle volume to solve a dashboard problem. See
[Recovery](recovery.md).
