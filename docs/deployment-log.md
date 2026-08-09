# Deployment log

Status recorded **2026-08-09 (Asia/Kuala_Lumpur)**. This is an evidence ledger,
not an instruction to continue automatically.

| Item | State | Evidence or next gate |
| --- | --- | --- |
| Target device | Verified read-only | Kindle 11th generation (2022), model code `KT5`, firmware `5.19.2.0.1`; audited macOS mount path `/Volumes/Kindle`; approximately 9.1 GiB free. No complete serial number is recorded here. |
| User storage backup | Verified | `device-backups/2026-08-07-kt5-pre-jailbreak` matches every non-regenerated path and file checksum with the read-only verifier. Equal-size corruption and non-cache Store resource changes are covered by regression tests. |
| SpringBreak | Cleanup completed; exploit **not verified** | The pinned v1.2 cleanup removed all 5,000 filler directories and ended with `Done! :) Have Fun With Your Jailbreak!`, but the preceding on-device page stalled at GUI restart and never showed the explicit success state. A clean Airplane-mode retry is pending. |
| hdnext / KPM / FBInk | **Not active** | After restart, `;kpm update` was handled as an ordinary Kindle search. This is concrete evidence that KPM was not active; FBInk therefore remains unverified and no legacy hotfix is being layered on top. |
| KUAL | Verification failed; copied files removed | The reviewed PEKI files did not produce a KUAL Library item because script integration was inactive. The two copied files and their macOS metadata sidecars were removed before retry; the verified archive remains on the host. |
| Kindle Brief host build | Verified | Dashboard version `0.1.0`; 150 automated tests, lint, format, POSIX shell syntax, deterministic rendering, release hashes, safe FBInk refresh cadence/fallback, same-release cache repair, the fake HTTPS updater, and ownership-scoped installer/uninstaller pass. The supplied weather, moon, moonrise/moonset, and motorsport icon derivatives are integrated; all active 2026 circuits use verified non-AI geometry. |
| Live data build | Verified on host and Pages | All 20 enabled feeds returned HTTP 200 with non-empty entries on 2026-08-08. The installed fallback uses scheduled release `f455c38e6795585f99f515ad539c9a69760a60ceae6721bf1c3a4fa64bf90712`, generated `2026-08-09T02:27:53.227917Z`; pointer, manifest, `SHA256SUMS`, bundle, and all five page hashes were reverified immediately before packaging. |
| Static hosting | **Deployed and verified** | The first production [run #1](https://github.com/Lzchyi/inkbrief/actions/runs/31205917680) completed in 41 seconds; scheduled [run #28](https://github.com/Lzchyi/inkbrief/actions/runs/31283790888) also built and deployed successfully. At the latest audit all 30 repository runs had succeeded. The HTTPS pointer at `https://lzchyi.github.io/inkbrief/profiles/kt5/current.json` redirects over HTTPS to the account's canonical `https://www.zhenchyi.com/inkbrief/` Pages path. Current pointer, manifest, `SHA256SUMS`, bundle, and all five page hashes match; every page is 1072 × 1448 grayscale with at most 16 levels. Pages enforces HTTPS. GitHub's schedule can start late; it is not a real-time scheduler. |
| Kindle package | Verified on host | Dashboard package ID `baba2a3a888b7e43cdfebfd8814b1c17253d28c309a331636d25d67aa7278d8c` embeds the live Pages root `https://lzchyi.github.io/inkbrief` and the verified live release pages as its offline fallback. It is retained on the host for installation only after jailbreak verification. |
| Kindle Brief install | Rolled back cleanly | The guarded installer had written only its two ownership-marked paths. After the missing-KPM result, the tested uninstaller removed both paths; books, Calibre data, and Kindle system paths were not targeted. |
| Physical acceptance | Blocked on jailbreak retry | Dashboard UI acceptance cannot begin until `;kpm update`, KUAL, and FBInk are positively verified on the physical KT5. |

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

The failed application attempt has been fully removed. The verified backup and
host package remain available. The SpringBreak filler sandbox was cleaned, but
system-level jailbreak state must be treated as absent until KPM responds.

## Next physical gate

The next gate is a clean SpringBreak retry after an Airplane-mode restart. Do
not reinstall KUAL or Kindle Brief unless the on-device flow reaches its
explicit success state and `;kpm update` is intercepted by KPM. See
[Device install](device-install.md) and the full
[Jailbreak and installation guide](jailbreak-and-install.md).
