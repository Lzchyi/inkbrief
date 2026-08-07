# Configuration

`config/config.example.yaml` is the application configuration,
`config/feeds.yaml` is the feed registry, and
`config/device-profiles/kt5.yaml` defines the exact display target. Validate
all three before a live build:

```sh
PYTHONPATH=backend .venv/bin/python -m kindle_brief.cli validate \
  --config config/config.example.yaml --feeds config/feeds.yaml
```

Configuration is parsed with YAML safe loading, rejects unknown keys, and is
limited to 1 MiB. Secret-like fields are rejected: credentials belong in
environment variables, not YAML.

## Main configuration

### `location`

`name`, IANA `timezone`, `latitude`, and `longitude` define the displayed
location and local calculations. Coordinates must be supplied together and
remain within geographic ranges. Coordinates are sent to Open-Meteo during a
live refresh; see [Privacy and security](privacy-security.md).

### `favorites`

Optional named locations use the same fields. Names must be unique. The
current five-page build uses the primary location; favorites are retained for
future location selection and should still be valid.

### `device` and `publishing`

Both `device.profile` and `publishing.profile` must be the same safe profile
identifier. For this release, use `kt5`. `publishing.base_url` may be omitted
or left empty while rendering locally; a non-empty value must be an HTTP(S)
URL. The Kindle's separate update endpoint file requires HTTPS.

### `refresh`

- `dashboard_minutes`: reserved cadence metadata, validated as 15–1440 minutes;
  it does not rewrite the checked-in GitHub Actions cron.
- `morning_brief_local_time`: `HH:MM` local wall time.
- `request_timeout_seconds`: 1–120 seconds.
- `max_stale_hours`: maximum permitted stale-data window, 1–720 hours.

The checked-in GitHub workflow runs at minute 17 of UTC hours 00–22 and at
23:00 UTC (07:00 Asia/Kuala_Lumpur). GitHub cron is UTC and may start late
under load. Change the workflow itself to change deployment cadence.

### `news`

- `max_age_hours` discards old items.
- `headline_limit` is bounded to 1–50; the design target is 10–15.
- `category_weights` influences deterministic ranking.

Category names must match the feed registry. The current registry uses
`malaysia`, `ai_tech`, `apple_dev`, `business`, `insurance`, `science`, `f1`,
and `travel`; not every category currently has a reliable source.

### `ai`

`provider` is one of `fallback`, `none`, `gemini`, `openrouter`, `groq`,
`openai`, or `openai_compatible`. Omit or leave `model` empty to use that
provider's coded default, or set a non-empty explicit model. `max_stories` is
1–20. Provider keys are read only from environment variables; see
[AI providers](ai-providers.md).

`openai_compatible` is reserved by the schema but intentionally rejected by
the current CLI because configuration has no reviewed base-URL field. Use one
of the four explicit remote providers or the local fallback.

### `f1` and `pages`

F1 can be disabled at the data layer and standing counts are bounded to 1–10.
The page flags are reserved for a future release profile with variable page
sets. Version 1 rejects a disabled flag because its updater and touch runtime
intentionally require the complete, ordered five-page release. This makes a
configuration change fail clearly instead of silently publishing the wrong
page set.

## Feed registry

Each `config/feeds.yaml` entry contains a unique ID, display name, HTTPS URL,
category, attribution, and enabled state. Optional compatibility flags control
missing dates and feeds that expose a usable link only through their GUID.

Check the registry over the network without publishing:

```sh
PYTHONPATH=backend .venv/bin/python -m kindle_brief.cli feeds-check \
  --feeds config/feeds.yaml --timeout 20
```

A failed feed check is not proof that a source is permanently broken; it may
reflect rate limits, bot filtering, or a transient outage. Changes to feed URLs
should be verified against the publisher's official site.

## Device profile

The KT5 profile fixes width, height, orientation, DPI, and grayscale depth.
Raw touch limits are intentionally unset until read from the actual device.
The installed controller queries the Linux input device ranges at runtime, so
do not guess or copy limits from a different Kindle model.

## Local overrides

Both preview and build accept `--profile PATH` to select an explicit profile.
Live operations accept `--cache PATH` for the last-success cache. Keep local
caches and `.env` files out of version control. Do not place API keys in the
configuration or in a public GitHub Pages artifact.
