# Deployment log

Status recorded **2026-08-09 (Asia/Kuala_Lumpur)**. This is an evidence ledger,
not an instruction to continue automatically.

| Item | State | Evidence or next gate |
| --- | --- | --- |
| Target device | Verified read-only | Kindle 11th generation (2022), model code `KT5`, firmware `5.19.2.0.1`; audited macOS mount path `/Volumes/Kindle`; approximately 9.1 GiB free. No complete serial number is recorded here. |
| User storage backup | Verified | `device-backups/2026-08-07-kt5-pre-jailbreak` matches every non-regenerated path and file checksum with the read-only verifier. Equal-size corruption and non-cache Store resource changes are covered by regression tests. |
| SpringBreak | **Verified after clean retry** | The pinned v1.2 flow reached its explicit success state. Mandatory cleanup removed all 5,000 filler directories and ended exactly with `Done! :) Have Fun With Your Jailbreak!`; the filler sandbox and injected cleanup utility were absent after restart. |
| hdnext / KPM / FBInk | **Verified** | `;kpm update` was intercepted instead of becoming a Kindle Store search. Physical diagnostics report `/var/local/kmc/bin/fbink`; the dashboard rendered through FBInk on the KT5. |
| KUAL | **Verified** | PEKI KUAL opens on the device. The Dashboard extension now includes the required `config.xml` descriptor pointing to `menu.json`; the installer also removes macOS AppleDouble sidecars that can confuse FAT-volume deployments. |
| Kindle Brief host build | Verified | Dashboard version `0.1.0`; focused renderer and physical-installer regressions, lint, format, POSIX shell syntax, deterministic rendering, release hashes, safe FBInk refresh cadence/fallback, same-release cache repair, the fake HTTPS updater, and ownership-scoped installer/uninstaller pass. The supplied weather, moon, moonrise/moonset, and motorsport icon derivatives are integrated; all active 2026 circuits use verified non-AI geometry. The KT5 layout now uses larger, darker typography, lower news density, explicit F1 session dates, and an event weekend date range. |
| Live data build | Verified on host and Pages | All 20 enabled feeds returned HTTP 200 with non-empty entries on 2026-08-08. The installed fallback uses scheduled release `f455c38e6795585f99f515ad539c9a69760a60ceae6721bf1c3a4fa64bf90712`, generated `2026-08-09T02:27:53.227917Z`; pointer, manifest, `SHA256SUMS`, bundle, and all five page hashes were reverified immediately before packaging. |
| Static hosting | **Deployed and verified** | Push-triggered [Refresh run #33](https://github.com/Lzchyi/inkbrief/actions/runs/31300367830) built and deployed larger-type release `d8702fedbf5ecaf96c1519aa787912bda21ac713f104866a7e73e32839e9e1b0`, generated `2026-08-09T07:06:15.531184Z`. The HTTPS pointer at `https://lzchyi.github.io/inkbrief/profiles/kt5/current.json` redirects over HTTPS to the account's canonical `https://www.zhenchyi.com/inkbrief/` Pages path. Current pointer, manifest, `SHA256SUMS`, bundle, and all five page hashes match; every page is 1072 × 1448 grayscale with at most 16 levels. Pages enforces HTTPS. Relevant pushes now deploy automatically in addition to the hourly schedule; schedules can still start late. |
| Kindle package | Verified on host and device | Installed package ID `728a35b7958a267195cf06af0d63777bd6b0681a3d67b6fddb75bcf153f8f8ad` embeds the Pages root `https://lzchyi.github.io/inkbrief` and five verified offline fallback pages. Physical post-copy verification matched every managed payload byte-for-byte and found no AppleDouble files or symlinks. |
| Kindle Brief install | **Installed** | Physical diagnostics report Kindle Brief `0.1.0`, firmware `5.19.2.0.1`, FBInk present, touch installed, update configured, and `Pages: 5/5`. The installer remained scoped to the two ownership-marked application/KUAL paths. |
| Physical acceptance | Core rendering verified; final controls pending | User photographs show the dashboard launching and all five pages rendering/navigating on the physical KT5. Those photographs identified the original type as too small; the corrected larger layout is published in release `d8702fedbf5ecaf96c1519aa787912bda21ac713f104866a7e73e32839e9e1b0` and now needs one on-device update pass. Top-left HOME, three-second failsafe exit, KUAL Stop, and ordinary-book reopening remain explicit final gates. |

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

The failed first application attempt was removed before the clean retry. The
verified backup remains available, SpringBreak filler was cleaned, jailbreak
state is confirmed by KPM/KUAL, and the current Kindle Brief install is scoped
and recoverable.

## Next physical gate

Run KUAL **Dashboard → Update Dashboard** and visually confirm one news page
plus the explicit F1 dates. Then verify top-left HOME, the three-second
failsafe exit, KUAL Stop, and that an ordinary Kindle book still opens. See
[Device install](device-install.md) and the full
[Jailbreak and installation guide](jailbreak-and-install.md).
