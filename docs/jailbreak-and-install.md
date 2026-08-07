# Jailbreak and installation

This procedure has two distinct trust and safety boundaries:

1. SpringBreak and hdnext establish homebrew access.
2. The Kindle Brief host installer copies only project-owned application files.

Do not combine the steps or automate the physical gates. The supported target
for this repository is exactly **Kindle 11th generation (2022), KT5, firmware
5.19.2.0.1**. A Paperwhite, Signature Edition, different basic Kindle, or even
a KT5 on a different firmware is out of scope for the application installer.

## Before any mutation

- Confirm the Kindle is registered, charged, and operating normally.
- Disable automatic host-side synchronization while working on the mount.
- Back up the complete user-visible Kindle storage to a dated host directory.
- Record file counts and total bytes, and open a sample of copied books.
- Preserve Calibre metadata and never use a jailbreak procedure as a library
  migration.
- Read the current canonical
  [SpringBreak guide](https://kindlemodding.org/jailbreaking/SpringBreak/) from
  start to finish.

Connect by USB and run the read-only detector:

```sh
./kindle/install/detect.sh /Volumes/Kindle
```

It must report one unambiguous mount, `model_code=KT5`, and
`firmware=5.19.2.0.1`. It does not print the complete serial number. Stop if
anything differs; do not force the installer with a guessed model.

For the already audited device and dated backup, run the read-only comparison:

```sh
./kindle/install/verify-backup.sh /Volumes/Kindle \
  device-backups/2026-08-07-kt5-pre-jailbreak
```

It must report a match before proceeding. The verifier compares all
non-regenerated paths and sizes without copying or deleting anything.

## SpringBreak v1.2 supply-chain warning

The reviewed release asset is:

- Release: [SpringBreak v1.2](https://github.com/KindleModding/SpringBreak/releases/tag/v1.2)
- Asset: [springbreak.zip](https://github.com/KindleModding/SpringBreak/releases/download/v1.2/springbreak.zip)
- SHA-256: `2880cbf765c57c3142f44d2339c4a3c70e3322a0e910f0ed2f698077078315f2`

Download that pinned URL and verify it before extraction:

```sh
curl -fL \
  https://github.com/KindleModding/SpringBreak/releases/download/v1.2/springbreak.zip \
  -o springbreak.zip
printf '%s  %s\n' \
  2880cbf765c57c3142f44d2339c4a3c70e3322a0e910f0ed2f698077078315f2 \
  springbreak.zip | shasum -a 256 -c -
```

The ZIP checksum does **not** cover the complete jailbreak execution. The
injected SpringBreak page currently downloads
`https://kindlemodding.org/jb.sh` with `curl` and executes it as root. That URL
is mutable. A `jb.sh` observation from 2026-08-07 is useful audit evidence but
must not be treated as a permanent pin. Continue only if this live root-script
risk is acceptable and the current official guide still matches the expected
flow.

## Physical SpringBreak gates

These gates follow the current guide; the user must perform and confirm each
device action.

1. On the Kindle, enable **Airplane Mode**.
2. Restart the Kindle and wait for the stock Home screen.
3. Connect USB. If the Kindle shows an MTP-style interface or a **Disconnect**
   button instead of the expected USB storage behavior, stop and return to the
   official guide.
4. Extract the verified ZIP, enter the extracted `springbreak` directory, make
   `springbreak-darwin` executable, and run `./springbreak-darwin` on macOS.
5. In the tool, select only the exact Kindle mount already verified above.
6. Eject the Kindle cleanly and unplug it.
7. On the Kindle, tap the Kindle Store entry as directed by the guide.
8. Enable Wi-Fi only when SpringBreak prompts for it.
9. As soon as SpringBreak loads, immediately enable **Airplane Mode** again.
10. Wait for the success flow and the stock UI restart. Do not interrupt it.
11. Reconnect USB and run the same `springbreak-darwin` tool again for cleanup.
12. Complete the guide's cleanup of temporary update/storage-filler artifacts,
    eject, unplug, and restart.

The second cleanup run is mandatory; skipping it can cause very long future
boots. Do not leave Wi-Fi enabled longer than the guide requires.

## hdnext, KPM, FBInk, and KUAL

The current SpringBreak flow installs the hdnext hotfix and KPM and re-enables
the Store. Do **not** layer old hotfix or OTA-blocker recipes on top of it. The
Kindle Brief runtime discovers FBInk in current hdnext/KPM locations and
refuses to start if FBInk is absent.

KPM itself can be checked from the Kindle search bar with `;kpm update`; package
installation uses `;kpm install <package>` only for a real published package.
Kindle Brief intentionally does not invent a KPM package ID or manifest, so do
not run a guessed Kindle Brief KPM command. See the current
[KPM documentation](https://kindlemodding.org/kindle-dev/kpm/).

Install KUAL using the current
[KUAL instructions](https://kindlemodding.org/jailbreaking/post-jailbreak/installing-kual-mrpi/)
and, where directed, [PEKI](https://github.com/KindleTweaks/PEKI). The current
manual K5+ route uses
[PEKI v1.0](https://github.com/KindleTweaks/PEKI/releases/tag/v1.0). Its
`PEKI.zip` asset was verified at SHA-256
`f653045909ed230496c3d8176c9901d3a6a1f693c52b488569be6a60e0852499`.
Extract it and place only the included `KUAL.jar` and `KUAL.sh` prerequisites
in `documents`; PEKI does not require MRPI for this route. This user-approved
KUAL prerequisite is separate from Kindle Brief. Kindle Brief itself creates
no book or Library document.

Stop if KUAL or FBInk cannot be verified. Do not install the dashboard into an
unknown homebrew state.

## Package and install Kindle Brief

Generate demo or live pages first, then package locally:

```sh
PYTHONPATH=backend .venv/bin/python -m kindle_brief.cli preview \
  --config config/config.example.yaml --feeds config/feeds.yaml \
  --output previews --demo
./kindle/install/package.sh
```

Reconnect the Kindle, close Calibre so it is not writing to the same volume,
and rerun the read-only detector. Then run the installer against the exact
mount:

```sh
./kindle/install/detect.sh /Volumes/Kindle
./kindle/install/install.sh /Volumes/Kindle
```

Before its first write, the installer validates the checksummed package,
hard-float ARM controller, exact mount, firmware, model, ownership markers,
symlink absence, and free space. It stages and promotes only:

- `/mnt/us/kindle-brief`
- `/mnt/us/extensions/Dashboard`

It does not write to `documents`, Calibre metadata, the book database, or boot
configuration. Reinstalling an identical package is idempotent; an upgrade
retains one owned previous application release.

For remote updates, replace the installed `config/base-url.example` with a file
named `base-url` containing one verified HTTPS Pages root. On a mounted Kindle
that path is:

```text
/Volumes/Kindle/kindle-brief/current/config/base-url
```

Do not put credentials or query-string secrets in the URL. Eject cleanly after
the file is saved.

## First launch and controls

Open KUAL → **Dashboard**:

- **Start Dashboard** displays the bundled or last downloaded pages.
- Swipe left for the next page and right for the previous page.
- Tap the visible top-left **HOME** target to return to the stock UI.
- Hold the top-right corner for at least three seconds as an independent exit.
- **Stop / Return to Library** stops a running dashboard from KUAL.
- **Update Dashboard** explicitly downloads and verifies the current release.
- **Diagnostics** reports runtime, FBInk, touch, update, and page status.

The default maximum session is 30 minutes, after which the failsafe restores
the stock Home interface. The device never performs an unattended update or
starts the dashboard at boot.

After first launch, confirm all five pages, both swipe directions, the HOME
target, the top-right hold, timeout/stop behavior, a KUAL update, and return to
Library. Also confirm existing books still open and Calibre still recognizes
the device.
