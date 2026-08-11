# Firmware update safety

InkBrief is pinned to Kindle KT5 firmware `5.19.2.0.1`. A firmware update can
remove or disable a jailbreak, KUAL, or other homebrew components, so do not
leave automatic updates enabled on a jailbroken device.

Firmware update blocking is deliberately kept separate from InkBrief. It is
firmware- and jailbreak-stack-specific; the dashboard must not guess which OTA
files are safe to rename or delete. On this SpringBreak/hdnext device, use the
currently maintained KUAL OTA tool supplied by the jailbreak community:

1. Keep Airplane Mode enabled while preparing the block.
2. In KUAL, run **Rename OTA Binaries → Rename**.
3. Remove only clearly identified pending Amazon update files if the tool asks
   you to; do not delete arbitrary `.bin` files from the Kindle.
4. Run the tool's status check, reboot if it requests one, and confirm the
   update block before enabling Wi-Fi.
5. Keep a recovery copy of the current firmware and the device backup before
   changing this state.

The maintained procedure and its firmware-specific caveats are documented by
[KindleModding](https://kindlemodding.org/jailbreaking/post-jailbreak/disable-ota.html).
Do not install an unrelated legacy OTA blocker or a package copied from a
different Kindle model.

To intentionally restore firmware updates later, use the same KUAL tool's
**Restore** action while Airplane Mode is enabled, then perform the desired
manual update. InkBrief itself never modifies OTA binaries, update services, or
the Kindle system partition.
