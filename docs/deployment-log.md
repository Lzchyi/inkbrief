# Deployment log

Status recorded **2026-08-09 (Asia/Kuala_Lumpur)**. This is an evidence ledger,
not an instruction to continue automatically.

| Item | State | Evidence or next gate |
| --- | --- | --- |
| Target device | Verified read-only | Kindle 11th generation (2022), model code `KT5`, firmware `5.19.2.0.1`; audited macOS mount path `/Volumes/Kindle`; approximately 9.1 GiB free. No complete serial number is recorded here. |
| User storage backup | Verified | `device-backups/2026-08-07-kt5-pre-jailbreak` matches every non-regenerated path and file checksum with the read-only verifier. Equal-size corruption and non-cache Store resource changes are covered by regression tests. |
| SpringBreak | **Completed on device** | The user accepted the live root-script risk and completed the pinned v1.2 flow. Its mandatory second run removed all 5,000 filler directories and ended with `Done! :) Have Fun With Your Jailbreak!`; the Kindle then restarted normally to Home. |
| hdnext / KPM / FBInk | Installed by SpringBreak; functional check pending | SpringBreak's hdnext stack and hotfix completed without layering a legacy hotfix. The remaining gate is the on-device KPM command and Kindle Brief Diagnostics confirmation that FBInk is discoverable. |
| KUAL | Installed; launch check pending | The publisher-matching PEKI v1.0 archive SHA-256 is `f653045909ed230496c3d8176c9901d3a6a1f693c52b488569be6a60e0852499`. Its exact `KUAL.jar` and `KUAL.sh` were copied to `documents` and their post-copy hashes match the reviewed files. |
| Kindle Brief host build | Verified | Dashboard version `0.1.0`; 150 automated tests, lint, format, POSIX shell syntax, deterministic rendering, release hashes, safe FBInk refresh cadence/fallback, same-release cache repair, the fake HTTPS updater, and ownership-scoped installer/uninstaller pass. The supplied weather, moon, moonrise/moonset, and motorsport icon derivatives are integrated; all active 2026 circuits use verified non-AI geometry. |
| Live data build | Verified on host and Pages | All 20 enabled feeds returned HTTP 200 with non-empty entries on 2026-08-08. The installed fallback uses scheduled release `f455c38e6795585f99f515ad539c9a69760a60ceae6721bf1c3a4fa64bf90712`, generated `2026-08-09T02:27:53.227917Z`; pointer, manifest, `SHA256SUMS`, bundle, and all five page hashes were reverified immediately before packaging. |
| Static hosting | **Deployed and verified** | The first production [run #1](https://github.com/Lzchyi/inkbrief/actions/runs/31205917680) completed in 41 seconds; scheduled [run #28](https://github.com/Lzchyi/inkbrief/actions/runs/31283790888) also built and deployed successfully. At the latest audit all 30 repository runs had succeeded. The HTTPS pointer at `https://lzchyi.github.io/inkbrief/profiles/kt5/current.json` redirects over HTTPS to the account's canonical `https://www.zhenchyi.com/inkbrief/` Pages path. Current pointer, manifest, `SHA256SUMS`, bundle, and all five page hashes match; every page is 1072 × 1448 grayscale with at most 16 levels. Pages enforces HTTPS. GitHub's schedule can start late; it is not a real-time scheduler. |
| Kindle package | Built and installed | Dashboard package ID `baba2a3a888b7e43cdfebfd8814b1c17253d28c309a331636d25d67aa7278d8c` embeds the live Pages root `https://lzchyi.github.io/inkbrief` and the verified live release pages as its offline fallback. It includes initial/periodic GC16 cleanup, waited GL16 page changes, and a GC16 failure fallback. |
| Kindle Brief install | **Installed and post-copy verified** | The guarded installer revalidated model `KT5` and firmware `5.19.2.0.1`, then wrote only `/mnt/us/kindle-brief` and `/mnt/us/extensions/Dashboard`. Every packaged application and KUAL-entry file matches the host package byte-for-byte; autostart remains disabled. |
| Physical acceptance | Pending | Touch orientation, stock-Home transition, five-page navigation, GL16/GC16 ghosting and rapid-swipe behavior, launch/manual update and offline fallback, failsafes, book opening, and Calibre reconnection require the exact physical KT5. |

## Rollback readiness

- The verified pre-jailbreak backup is available and excluded from version
  control and deployment artifacts.
- The application uninstaller is tested against fake mounts and removes only
  ownership-marked Kindle Brief paths.
- Content updates retain the current cache on failure and one previous cache
  after successful promotion.
- Application upgrades retain one previous owned release.
- Full jailbreak removal is deliberately outside this project and must follow
  current model-specific official guidance.

The device now contains the SpringBreak hdnext stack, the two PEKI KUAL files,
and the two ownership-marked Kindle Brief paths. The tested project uninstaller
removes only Kindle Brief; jailbreak removal remains a separate official-guide
procedure.

## Next physical gate

The remaining gate is physical UI acceptance: open KUAL, confirm Kindle Brief
Diagnostics reports FBInk, touch controller, update URL, and all five pages;
then exercise page navigation, both exits, manual update/offline fallback, one
existing book, and Calibre reconnection. See [Device install](device-install.md)
and the full [Jailbreak and installation guide](jailbreak-and-install.md).
