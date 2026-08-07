#!/bin/sh
set -eu

INSTALL_DIR=$(CDPATH= cd "$(dirname "$0")" && pwd -P)
. "$INSTALL_DIR/host-lib.sh"

[ "$#" -eq 1 ] || {
    printf '%s\n' "usage: uninstall.sh MOUNT" >&2
    exit 2
}
mount_path=$(kb_host_validate_mount "$1")
[ -w "$mount_path" ] || kb_host_die "Kindle mount is not writable"

app_base=$mount_path/kindle-brief
extension_root=$mount_path/extensions/Dashboard
if [ -L "$app_base" ] || [ -L "$mount_path/extensions" ] || [ -L "$extension_root" ]; then
    kb_host_die "managed uninstall paths may not be symlinks"
fi

# Validate every existing target before removing either one, preventing a
# partial uninstall when a path has been replaced by user-owned content.
if [ -e "$app_base" ] && ! kb_host_owned_dir "$app_base"; then
    kb_host_die "refusing to remove unowned application directory"
fi
if [ -e "$extension_root" ] && ! kb_host_owned_dir "$extension_root"; then
    kb_host_die "refusing to remove unowned KUAL Dashboard entry"
fi

removed=0
if kb_host_owned_dir "$extension_root"; then
    rm -rf "$extension_root"
    removed=1
fi
if kb_host_owned_dir "$app_base"; then
    rm -rf "$app_base"
    removed=1
fi

if [ "$removed" -eq 1 ]; then
    printf '%s\n' "Removed Kindle Brief-owned USB files only; jailbreak and books are unchanged."
else
    printf '%s\n' "Kindle Brief is not installed; nothing changed."
fi
