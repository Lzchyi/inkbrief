# Validation

Validation is split into deterministic host checks, optional network checks,
package safety tests, and explicit physical-device acceptance. No simulator
test is used.

## Deterministic host suite

Bootstrap once:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -e '.[dev]'
```

Run configuration, lint, and tests:

```sh
PYTHONPATH=backend .venv/bin/python -m kindle_brief.cli validate \
  --config config/config.example.yaml --feeds config/feeds.yaml
PYTHONPATH=backend .venv/bin/python -m ruff check backend tests
PYTHONPATH=backend .venv/bin/python -m ruff format --check backend tests
PYTHONPATH=backend .venv/bin/python -m pytest
```

Check every BusyBox-compatible shell script with the host parser:

```sh
find kindle -type f -name '*.sh' -exec /bin/sh -n {} \;
```

Render and package from deterministic fixtures:

```sh
PYTHONPATH=backend .venv/bin/python -m kindle_brief.cli preview \
  --config config/config.example.yaml --feeds config/feeds.yaml \
  --output previews --demo
PYTHONPATH=backend .venv/bin/python -m kindle_brief.cli build \
  --config config/config.example.yaml --feeds config/feeds.yaml \
  --output /tmp/kindle-brief-public --demo
KINDLE_BRIEF_PAGES_DIR=previews ./kindle/install/package.sh \
  /tmp/kindle-brief-package
```

The automated suite covers strict configuration, cache corruption/staleness,
weather parsing, astronomy and lunar reference dates, Jolpica parsing, RSS
normalization/deduplication/ranking, AI schema rejection/fallback, all 24 F1
track mappings, image dimensions and hotspots, deterministic release hashes,
and fake-mount install/upgrade/uninstall refusal paths.

## Visual QA

Open all five PNGs at native 1072×1448 resolution and check:

- date/time/lunar header centered and readable;
- HOME label visible in the top-left safe area;
- no clipped CJK glyphs or replacement boxes;
- no overlapping cards, rules, or text;
- weather values and units internally consistent;
- moon illumination/shape plausible for the labeled phase;
- F1 sessions ordered in the configured timezone and track recognizable;
- morning-brief summaries bounded and attributed; and
- 10–15 headlines visible when enough current items exist.

Repeat with unusually long source titles before changing typography or card
geometry.

## Network diagnostics

Feed health is informative and time-dependent:

```sh
PYTHONPATH=backend .venv/bin/python -m kindle_brief.cli feeds-check \
  --feeds config/feeds.yaml --timeout 20
```

Then perform one live build with the intended production configuration and
cache. Confirm attribution, source freshness/stale markers, and that no secret
appears under `public/`. A transient feed failure should not prompt a code
change unless reproduced and verified against the publisher.

## Release verification

For a deployed build:

1. Fetch `profiles/kt5/current.json` over HTTPS.
2. Confirm the profile/model/schema are expected.
3. Confirm the release ID is a lowercase 64-character digest.
4. Download the referenced manifest and checksum list.
5. Recompute SHA-256 for metadata and all five PNGs.
6. Confirm each PNG is exactly 1072×1448 grayscale.
7. Confirm no unexpected file path appears in the checksum list.

The Kindle updater performs the corresponding checks before promotion, but an
independent host check makes deployment errors easier to diagnose.

## Backup acceptance

Before SpringBreak or installation, verify the pre-jailbreak backup by path,
size, and, for higher assurance, a separate read-only checksum comparison.
`kindle/install/verify-backup.sh` performs a dry-run path/size comparison,
accounts for FAT directory timestamp differences, and excludes only documented
regenerated indexes/caches. Do not judge backup completeness solely by Finder's
item count.

For the audited KT5 and its existing dated backup:

```sh
./kindle/install/verify-backup.sh /Volumes/Kindle \
  device-backups/2026-08-07-kt5-pre-jailbreak
```

This command is read-only and currently passes against the real mounted device.

## Physical acceptance checklist

After user-confirmed jailbreak, homebrew prerequisites, package install, and
safe eject:

- KUAL opens and shows Dashboard actions.
- Diagnostics reports exact firmware, FBInk, touch controller, update URL, and
  five pages.
- Start displays Home without stopping the stock framework.
- Left/right swipes traverse all five pages and wrap predictably.
- The visible top-left HOME target returns to stock Home/Library.
- A three-second top-right hold also exits.
- KUAL Stop exits a running dashboard.
- The runtime limit restores the stock UI.
- Manual Update succeeds and a deliberately unavailable endpoint leaves the
  existing cache usable.
- Existing books open normally.
- Calibre reconnects with prior metadata intact.
- No Kindle Brief document appears in the Library.
- A normal restart does not autostart the dashboard.

Do not automate these physical gates or claim success before observing them on
the exact KT5 device.
