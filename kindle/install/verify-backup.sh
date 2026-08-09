#!/bin/sh
set -eu

INSTALL_DIR=$(CDPATH= cd "$(dirname "$0")" && pwd -P)
. "$INSTALL_DIR/host-lib.sh"

[ "$#" -eq 2 ] || {
    printf '%s\n' "usage: verify-backup.sh MOUNT BACKUP_DIRECTORY" >&2
    exit 2
}

mount_path=$(kb_host_validate_mount "$1")
backup_path=$(kb_host_canonical_dir "$2") || kb_host_die "backup directory does not exist"
[ "$mount_path" != "$backup_path" ] || kb_host_die "backup and Kindle paths are identical"
[ -d "$backup_path/documents" ] || kb_host_die "backup has no documents directory"
[ -r "$backup_path/system/version.txt" ] || kb_host_die "backup has no firmware record"
command -v rsync >/dev/null 2>&1 || kb_host_die "rsync is required for read-only comparison"

mounted_firmware=$(kb_host_firmware "$mount_path")
backup_firmware=$(kb_host_firmware "$backup_path")
[ "$mounted_firmware" = "$backup_firmware" ] || \
    kb_host_die "backup firmware does not match mounted firmware"

# --dry-run is mandatory: this command compares the live USB volume to the
# backup but cannot copy or delete anything. These are only regenerated Kindle
# or macOS caches; documents, Calibre metadata, and user content are included.
raw_differences=$(rsync \
    --archive \
    --no-times \
    --checksum \
    --dry-run \
    --omit-dir-times \
    --delete \
    --itemize-changes \
    --exclude='/.Spotlight-V100/***' \
    --exclude='/.fseventsd/***' \
    --exclude='/.Trashes/***' \
    --exclude='/.bcache/***' \
    --exclude='/.active_content_sandbox/store/resource/cachedResources/***' \
    --exclude='/documents/.cache/kf8/***' \
    --exclude='/system/Search Indexes/***' \
    --exclude='/system/thumbnails/***' \
    --exclude='/system/kf8/***' \
    --exclude='/system/fmcache/***' \
    "$mount_path/" "$backup_path/")

# Some host rsync builds still itemize an identical-size regular file when
# only its FAT-visible modification time differs. They can also warn that the
# known excluded Store-cache ancestors cannot be deleted. Discard only those
# exact cases; any content, size, mode, ownership, path, or other deletion
# change remains.
differences=$(printf '%s\n' "$raw_differences" | sed \
    -e '/^\.f\.\.[tT]\.* /d' \
    -e '/\/\.active_content_sandbox\/store.*: not empty, cannot delete$/d' \
    -e '/\/\.active_content_sandbox: not empty, cannot delete$/d' \
    -e '/^cannot delete non-empty directory: \.active_content_sandbox\(\/store\(\/resource\)\?\)\?$/d' \
    -e '/^\*deleting \.active_content_sandbox\(\/store\(\/resource\)\?\)\?\/$/d')

if [ -n "$differences" ]; then
    printf '%s\n' "Backup differs from the mounted Kindle:" >&2
    printf '%s\n' "$differences" >&2
    exit 1
fi

printf '%s\n' "Backup matches the mounted Kindle (regenerated caches excluded)."
