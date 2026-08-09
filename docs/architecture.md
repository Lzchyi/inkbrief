# Architecture

Kindle Brief deliberately keeps network, parsing, ranking, astronomy, and
image rendering off the Kindle. The device is a narrow display client with a
launch-time and manual updater.

```text
Open-Meteo ─┐
Jolpica F1 ─┼─> Python data pipeline ─> immutable snapshot ─> five PNG pages
RSS feeds ──┤             │                       │                 │
local sky ──┘             └─ last-success cache  └─ manifest       │
optional AI ────────────────────────────────────────────────────────┘
                                                                    │
GitHub Pages/static HTTPS <─ content-addressed release <────────────┘
             │
             └─ launch check / manual KUAL update
                              └─> staged checksum verification
                                           │
                                  FBInk + touch controller
                                           │
                                    stock Home/Library
```

## Host-side pipeline

The `kindle_brief` package has provider-neutral immutable models. Adapters turn
remote responses into those models; local calculators derive astronomy and the
Chinese lunar date. RSS entries are normalized, deduplicated, category-ranked,
and optionally sent to a configured AI provider. Remote AI output is accepted
only after strict article-ID and length validation. Any provider transport,
parse, quota, or schema error falls back to local deterministic selection.

Cache entries are canonical JSON stored beneath a SHA-256-derived path. Writes
use a temporary file, `fsync`, and atomic replacement. A live build may use
bounded stale data when a provider is temporarily unavailable. Cache contents
are data, never executable code.

## Rendering

The renderer consumes one complete `DashboardSnapshot`; it does not make
network requests. Each page is converted to the selected device profile's
pixel dimensions and grayscale depth. The KT5 profile is portrait, 1072×1448,
300 dpi, and 4-bit grayscale.

A build produces a content-addressed release under
`profiles/kt5/releases/<release-id>/` plus `profiles/kt5/current.json`. Page
hashes and pointer metadata let the Kindle updater reject incomplete or
corrupted downloads before replacing its current cache. See
[Rendering](rendering.md) for the artifact layout.

## Kindle-side runtime

The package installs a KUAL `Dashboard` entry and a hard-float ARM runtime in
project-owned USB storage. It relies on FBInk supplied by the current hdnext
environment. Starting the dashboard:

1. Attempts one configured update with a 20-second network budget, continuing
   on failure.
2. Locates cached or package-bundled pages.
3. Starts an independent maximum-runtime failsafe.
4. Starts the touch controller, which discovers and exclusively grabs the
   touch input only while the dashboard is active.
5. Draws one page at a time: flashing GC16 on launch and every fifth page
   change, with non-flashing GL16 grayscale updates in between.
6. Releases input and asks the stock Home UI to return on every normal or
   trapped exit.

The stock framework is never stopped. There is no boot hook, cron job,
systemd unit, or other device-side autostart. Updates occur only during a
manual Dashboard launch or when the user selects **Update Dashboard** in KUAL.

## Trust boundaries

- Weather, F1, RSS, and AI responses are untrusted input. They are parsed into
  bounded internal models and rendered as text; they are never evaluated.
- The public host is trusted for availability and release selection. HTTPS and
  release hashes detect transfer corruption, but hashes served from the same
  origin are not an independent signature.
- The host installer validates mount identity, exact firmware/model,
  checksummed package contents, path ownership, symlink absence, and free
  space before its first device write.
- SpringBreak is outside the application trust boundary. Its separate risk is
  documented in [Jailbreak and installation](jailbreak-and-install.md).

## Explicit non-goals

- Replacing or hiding the stock Kindle Library
- Creating EPUB/AZW documents for dashboard pages
- Writing Calibre metadata or book records
- Device-side scraping, AI inference, or scheduled networking
- Autostarting at boot
- Supporting unverified Kindle models or firmware
- Publishing an invented KPM manifest before a real package ID and repository
  review exist
