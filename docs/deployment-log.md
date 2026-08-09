# Deployment log

Status recorded **2026-08-09 (Asia/Kuala_Lumpur)**. This is an evidence ledger,
not an instruction to continue automatically.

| Item | State | Evidence or next gate |
| --- | --- | --- |
| Target device | Verified read-only | Kindle 11th generation (2022), model code `KT5`, firmware `5.19.2.0.1`; audited macOS mount path `/Volumes/Kindle`; approximately 9.1 GiB free. No complete serial number is recorded here. |
| User storage backup | Verified | `device-backups/2026-08-07-kt5-pre-jailbreak` matches every non-regenerated path and file checksum with the read-only verifier. Equal-size corruption and non-cache Store resource changes are covered by regression tests. |
| SpringBreak | Prepared, **not run** | v1.2 asset URL and SHA-256 are pinned in the install guide. The live mutable `jb.sh` root-download risk remains an explicit user decision. |
| hdnext / KPM / FBInk | **Not installed or verified** | These arrive only after the user completes the physical SpringBreak flow. No duplicate legacy hotfix is planned. |
| KUAL | PEKI v1.0 prepared; **not installed or verified** | The publisher-matching `PEKI.zip` SHA-256 is `f653045909ed230496c3d8176c9901d3a6a1f693c52b488569be6a60e0852499`. Its reviewed `KUAL.jar` and `KUAL.sh` remain a physical-install prerequisite. |
| Kindle Brief host build | Verified | Dashboard version `0.1.0`; 150 automated tests, lint, format, POSIX shell syntax, deterministic rendering, release hashes, safe FBInk refresh cadence/fallback, same-release cache repair, the fake HTTPS updater, and ownership-scoped installer/uninstaller pass. The supplied weather, moon, moonrise/moonset, and motorsport icon derivatives are integrated; all active 2026 circuits use verified non-AI geometry. |
| Live data build | Verified on host and Pages | All 20 enabled feeds returned HTTP 200 with non-empty entries on 2026-08-08. The first production build published non-degraded release `f40869c64f5a0353d2a97ab1c8c0a7f762106c6cdc4daa6bc3c4482eb5ba5fff`. The current scheduled release is `8847232bcecf940c8939268addd3d40fb205f4af70e9862bc9068efdda872dc3`, generated `2026-08-08T23:21:47.915992Z`; its valid snapshot is marked degraded because at least one time-dependent source warning occurred, while weather, F1, astronomy, and usable headlines remain present. |
| Static hosting | **Deployed and verified** | The first production [run #1](https://github.com/Lzchyi/inkbrief/actions/runs/31205917680) completed in 41 seconds; scheduled [run #28](https://github.com/Lzchyi/inkbrief/actions/runs/31283790888) also built and deployed successfully. At the latest audit all 30 repository runs had succeeded. The HTTPS pointer at `https://lzchyi.github.io/inkbrief/profiles/kt5/current.json` redirects over HTTPS to the account's canonical `https://www.zhenchyi.com/inkbrief/` Pages path. Current pointer, manifest, `SHA256SUMS`, bundle, and all five page hashes match; every page is 1072 × 1448 grayscale with at most 16 levels. Pages enforces HTTPS. GitHub's schedule can start late; it is not a real-time scheduler. |
| Kindle package | Prepared on host only | Dashboard package ID `22d11118074d68d739d5ab779ac1187c65635cbd59b87d8028845739a40fa21f` embeds the live Pages root `https://lzchyi.github.io/inkbrief` and passes its complete payload checksum. It includes initial/periodic GC16 cleanup, waited GL16 page changes, and a GC16 failure fallback. The updater's exact HTTPS-only redirect flags were verified against the live pointer. No package has been copied to `/Volumes/Kindle`. |
| Kindle Brief install | **Not run** | `/mnt/us/kindle-brief` and `/mnt/us/extensions/Dashboard` have not been created by this deployment. |
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

Because SpringBreak, KUAL/KPM, and Kindle Brief installation have not occurred,
there is currently no real-device mutation to roll back.

## Next physical gate

The next action requires the user at the Kindle: reconfirm the verified backup,
enable Airplane Mode, restart, and then follow the pinned SpringBreak procedure
one physical step at a time. No host automation should cross this gate without
that confirmation. See [Device install](device-install.md) and the full
[Jailbreak and installation guide](jailbreak-and-install.md).
