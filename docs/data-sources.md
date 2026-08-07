# Data sources and attribution

Live refreshes combine remote public data with local calculations. Source
availability and licensing can change; verify terms before redistributing a
dashboard beyond personal use.

## Structured data

| Data | Implementation | Terms and attribution | Network behavior |
| --- | --- | --- | --- |
| Weather | [Open-Meteo Forecast API](https://open-meteo.com/en/docs) | Data attribution is required under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/); also review [Open-Meteo terms](https://open-meteo.com/en/terms). | Sends configured latitude/longitude and requested forecast fields. No key is required for the non-commercial API tier. |
| Location search (optional) | [Open-Meteo Geocoding API](https://open-meteo.com/en/docs/geocoding-api) | Results are based on [GeoNames](https://www.geonames.org/), whose data is [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). Credit GeoNames with a link or reference and review its [data and web-service terms](https://www.geonames.org/export/) plus the [Open-Meteo licence](https://open-meteo.com/en/license). | Sends the entered place name and optional language/country filters only when location search is used. Configured coordinates avoid this lookup. |
| Formula 1 schedule and standings | [Jolpica F1 API](https://github.com/jolpica/jolpica-f1) | [CC BY-NC-SA 4.0](https://creativecommons.org/licenses/by-nc-sa/4.0/); use is non-commercial and attribution/share-alike obligations apply. | Requests the next race plus bounded driver and constructor standings with a meaningful user agent. |
| Astronomy | [Astronomy Engine](https://github.com/cosinekitty/astronomy) | MIT | Calculated locally from date, time, and coordinates; no astronomy service request. |
| Chinese lunar date | [lunar-python](https://github.com/6tail/lunar-python) | MIT | Calculated locally. |
| Circuit outlines | [bacinger/f1-circuits](https://github.com/bacinger/f1-circuits) | MIT; the pinned source and attribution are in `assets/tracks/`. | Bundled at build time; no request. |

Open-Meteo and Jolpica attribution is carried in source status metadata. The
rendered design should retain source labels where space permits; publishing the
underlying static metadata does not remove the requirement to credit the data
providers.

The Kindle pages are bitmap PNGs: provider names and short licence labels can
be readable in a footer, but they cannot be clickable links. Full terms and
URLs are maintained here and, for weather and F1, in source-status metadata.
If a bitmap is redistributed by itself, keep its visible credit and accompany
it with accessible Open-Meteo, GeoNames (when geocoding was used), and Jolpica
links; do not treat the bitmap footer as the complete attribution notice.

At verification on 2026-08-07, Open-Meteo documented 10,000 daily calls for
personal non-commercial use and Jolpica documented 4 requests per second and
500 per hour. These limits are not contractual constants; recheck current terms
before changing the hourly schedule or adding locations.

## RSS and Atom feeds

The verified registry is `config/feeds.yaml`. It includes sources for:

- Malaysia: Bernama, Free Malaysia Today, and Malaysiakini
- Business: Bursa Malaysia corporate newsroom
- AI and technology: OpenAI, Google AI, Google DeepMind, Hugging Face, Ars
  Technica, TechCrunch, and The Verge
- Apple development: Apple Developer news and releases, and Swift.org
- Formula 1: FIA, Motorsport.com, and BBC Sport
- Science and space: NASA and ESA

RSS content remains the property of each publisher and is subject to its own
terms. Kindle Brief stores normalized headlines, source names, links, dates,
and short feed-provided excerpts for a personal, noncommercial brief. It does
not fetch full article pages. Keep attribution and source links intact. Do not
redistribute RSS-derived pages, snapshots, or excerpts commercially—or beyond
personal use—without confirming each publisher's terms or obtaining permission.

The Morning Brief retains compact visible publisher names for source-backed
cards; summarization does not remove them. Because the page is a bitmap, consult
the static snapshot or original feed record for the clickable article URL.

On 2026-08-08, the live `feeds-check` returned HTTP 200 with non-empty entries
for all 20 enabled feeds. This 20/20 result is a point-in-time availability
check, not a promise that every publisher endpoint will remain available.

The parser:

- requires an HTTPS registry URL;
- sends a bounded personal-dashboard user agent;
- strips markup rather than rendering feed HTML;
- stops reading a response once its decoded body exceeds 8 MiB;
- canonicalizes article URLs;
- assigns stable IDs from feed identity and URL;
- treats remote text only as data;
- deduplicates near-equivalent stories before ranking; and
- limits articles by age and page capacity.

## Known gaps

No dependable official Bank Negara Malaysia or Life Insurance Association of
Malaysia RSS feed was verified on 2026-08-07. The `insurance` category is
therefore a declared gap, not silently filled with scraped or invented data.

Also observed during verification:

- The Star's advertised RSS directory pointed to feeds returning 404.
- Malay Mail's advertised feeds returned 403.
- Anthropic had no verified direct RSS feed.

These are observations, not permanent claims. Recheck an official source
before enabling it. Never convert an ordinary web page into an unreviewed
scraper merely to make a category appear populated.

## Failure and staleness policy

Each remote source can fail independently. Successful responses are written to
the local last-success cache. A later live build may use cached data within
`refresh.max_stale_hours` and marks the source stale. It does not label stale
data as newly fetched. A cold run with no usable current or cached foundation
fails and leaves the previously deployed GitHub Pages version untouched.

`feeds-check` is a diagnostic snapshot, not a publish step:

```sh
PYTHONPATH=backend .venv/bin/python -m kindle_brief.cli feeds-check \
  --feeds config/feeds.yaml --timeout 20
```

Respect source rate limits. The hourly workflow intentionally fetches only the
small set of endpoints needed for one dashboard.
