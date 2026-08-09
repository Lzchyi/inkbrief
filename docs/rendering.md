# Rendering and release format

Rendering is deterministic for a given `DashboardSnapshot`, device profile,
asset set, and application version. It performs no network I/O.

## KT5 target

The supported profile is:

- 1072×1448 portrait pixels
- 300 dpi
- 4-bit grayscale output
- Noto Sans CJK SC for Latin and Chinese glyph coverage

The bundled font is licensed under SIL Open Font License 1.1; see
`assets/fonts/OFL-1.1.txt`. Original dashboard SVGs are MIT-licensed under
`assets/icons/LICENSE.md`. Project-authorized raster icon derivatives have a
separate source and processing record in `assets/PROVENANCE.md`; it does not
assert a third-party licence. Circuit geometry retains its own attribution in
`assets/tracks/`.

## Common layout contract

All five pages share a centered date/time/lunar header and a visible HOME area.
The page renderer emits `hotspots.json` for host-side geometry checks and a
bounded `links.tsv` containing only HTTPS news-row hitboxes for the Kindle.
Every page carries a high-contrast HOME target in the same top-left bounds. The
Kindle display wrapper loads the
complete page without refreshing, then submits one update: flashing GC16 on
launch and every fifth page change, or non-flashing GL16 in between. This
requests low-flash 16-level updates while periodically clearing ghosting; the
bounded cadence is configurable from one to five page changes in the
package-owned `runtime.conf`.
Each update waits for the panel controller to finish before another page can
be drawn. If a GL16 request fails, the wrapper retries that framebuffer with a
flashing GC16 cleanup.

Pages are fixed images, not HTML:

- `home.png`
- `weather.png`
- `f1.png`
- `morning-brief.png`
- `headlines.png`

This keeps the Kindle runtime small and produces exact typography and line
wrapping. News remains bitmap text, but the separately verified hitboxes let a
short row tap open the corresponding original article in the Kindle browser.

## Preview

Generate stable demo pages without network access:

```sh
PYTHONPATH=backend .venv/bin/python -m kindle_brief.cli preview \
  --config config/config.example.yaml --feeds config/feeds.yaml \
  --output previews --demo
```

Use `--live` instead of `--demo` to preview current data; the two modes are
mutually exclusive and one is required. Live preview accepts
`--cache .cache/kindle-brief`.

Review every PNG at native resolution. Automated tests check exact dimensions,
grayscale mode, centered header metadata, HOME hotspot bounds, page names,
moon-phase progression, and track mappings, but they cannot judge every font
or content-length combination.

## Static release

`build --output public --live` writes a profile-scoped pointer and immutable
release. The shape is:

```text
public/
└── profiles/
    └── kt5/
        ├── current.json
        └── releases/
            └── <64-character-release-id>/
                ├── manifest.json
                ├── SHA256SUMS
                ├── dashboard.tar.gz
                ├── hotspots.json
                ├── links.tsv
                ├── snapshot.json
                └── pages/
                    ├── home.png
                    ├── weather.png
                    ├── f1.png
                    ├── morning-brief.png
                    └── headlines.png
```

The release ID is content-derived. The manifest records application version,
generation time, device profile, dimensions, sizes, and page hashes. The
pointer separately records the exact byte size and SHA-256 of `links.tsv`.
`dashboard.tar.gz` is a deterministic host-side bundle of the release files;
the Kindle updater deliberately uses direct files and does not extract it. The
pointer includes hashes for metadata the Kindle must trust before downloading
pages. Exact fields are versioned and covered by tests; consumers should reject
an unsupported schema rather than guess.

The updater downloads into a staging directory, permits exactly the five known
page paths, validates every checksum, link-map row, and the KT5 model/profile,
then atomically promotes the staged cache. A failed update leaves the current cache in place;
the former current cache is retained as `previous` after a successful change.

Hashes detect accidental corruption and mismatched files. Because the pointer
and hashes are served by the same origin, they are not an independent digital
signature. Protect the GitHub account, repository, Actions settings, and Pages
environment.

## Publishing considerations

GitHub Pages serves every file under `public`. `snapshot.json` can contain
location display names, source URLs, headlines, and feed excerpts. Inspect the
output before publishing a private location name or sensitive feed selection.
No API credential should ever enter a snapshot or release.
