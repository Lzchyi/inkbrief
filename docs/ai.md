# AI quick guide

Kindle Brief does not require AI. The default `fallback` provider ranks stories
deterministically and produces short extractive summaries locally. This is the
recommended first deployment because it needs no credential and keeps article
text on the build host.

## Local default

```yaml
ai:
  provider: fallback
  model: ""
  max_stories: 8
```

Run a live build normally; no key is read:

```sh
PYTHONPATH=backend .venv/bin/python -m kindle_brief.cli build \
  --config config/config.example.yaml --feeds config/feeds.yaml \
  --cache .cache/kindle-brief --output public --live
```

## Optional remote provider

Supported explicit providers are Gemini, Groq, OpenRouter, and OpenAI. Select
one provider and expose only its key as an environment variable. Never place a
key in YAML, Pages output, a Kindle file, or source control.

The supplied refresh workflow uses `AI_PROVIDER=auto`. It checks standard key
variables in the order Gemini, Groq, OpenRouter, OpenAI, and falls back locally
when none is present. Add only one provider secret if deterministic selection
of the remote service matters.

Remote AI receives only selected article IDs, headlines, bounded excerpts,
categories, source names, and publication times. Structured responses must
reference known article IDs and pass strict count and length validation. Any
transport, quota, parse, or schema error uses the local fallback.

## Visible Morning Brief sources

Each normally source-backed Morning Brief card retains a compact visible
`Source` or `Sources` line. The pipeline derives those names from validated
article IDs and stores them with the daily brief, so attribution survives
hourly headline rotation. AI or extractive summaries do not replace publisher
attribution. The bitmap cannot make those names clickable; source URLs remain
in the feed cache or the originating publisher records.

See [AI providers](ai-providers.md) for current model defaults, official model
links, custom credential rules, privacy, and output validation.
