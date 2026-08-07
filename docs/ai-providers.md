# AI providers

AI is optional. `provider: fallback` performs deterministic category ranking
and extractive summarization locally, uses no key, and is the recommended
baseline. Weather, F1, astronomy, lunar calculations, rendering, and Kindle
navigation never depend on AI.

For automation, the environment override `AI_PROVIDER=auto` checks the standard
key variables in this order: Gemini, Groq, OpenRouter, then OpenAI. With no key
it selects the same deterministic fallback. `auto` is an environment-only mode,
not a YAML provider value.

## Supported providers

| Provider | Environment variable | Coded default when `model` is empty | Notes |
| --- | --- | --- | --- |
| `fallback` or `none` | None | Local deterministic implementation | No remote request. |
| `gemini` | `GEMINI_API_KEY` | `gemini-3.5-flash-lite` | Uses Gemini `generateContent` structured output. Availability and free-tier limits depend on account and region. |
| `groq` | `GROQ_API_KEY` | `openai/gpt-oss-20b` | Uses the provider's OpenAI-compatible chat endpoint. |
| `openrouter` | `OPENROUTER_API_KEY` | `openai/gpt-oss-20b:free` | Free-route availability and limits can change. |
| `openai` | `OPENAI_API_KEY` | `gpt-5.4-nano` | Do not assume a free API tier. |
| `openai_compatible` | None | None | Reserved; validation rejects it until an explicit reviewed base-URL mechanism exists. |

Model names and prices change. The table describes current code defaults, not
a promise of continued availability or cost. For Gemini model capabilities,
structured output, and pricing, consult the current official documentation:

- [Gemini model documentation](https://ai.google.dev/gemini-api/docs/latest-model)
- [Gemini structured output](https://ai.google.dev/gemini-api/docs/generate-content/structured-output)
- [Gemini API pricing](https://ai.google.dev/gemini-api/docs/pricing)
- [OpenAI GPT-5.4 nano](https://developers.openai.com/api/docs/models/gpt-5.4-nano)
- [OpenRouter structured outputs](https://openrouter.ai/docs/guides/features/structured-outputs)

The Gemini 3.5 Flash-Lite adapter uses the current
`generationConfig.responseFormat.text` JSON schema envelope. Sampling controls
deprecated for that model family are intentionally not sent.

## Configure a provider

Select the provider and optionally a non-empty model in YAML:

```yaml
ai:
  provider: gemini
  model: gemini-3.5-flash-lite
  max_stories: 8
```

Set the corresponding environment variable only for the build process:

```sh
export GEMINI_API_KEY='...'
PYTHONPATH=backend .venv/bin/python -m kindle_brief.cli build \
  --config config/config.example.yaml --feeds config/feeds.yaml \
  --cache .cache/kindle-brief --output public --live
```

Do not put a key in YAML, `.env.example`, a command committed to shell history,
a static artifact, or a Kindle file. For GitHub Actions, use an encrypted
repository or environment secret with the exact environment-variable name.
Scheduled workflows never run on pull requests, so untrusted pull-request code
cannot receive these secrets through `refresh.yml`.

`AI_PROVIDER` and `AI_MODEL` environment values override their YAML
counterparts. A configured `credential_env` is honored only for an explicit
remote provider; combining a custom credential name with `auto` is rejected so
provider selection cannot be ambiguous.

The supplied GitHub workflow sets `AI_PROVIDER=auto`, so its environment value
overrides the YAML example. Replace that workflow value with one explicit name
if provider pinning is preferred.

## Data sent to AI

Only already-selected feed records are sent: article ID, headline, a bounded
excerpt, category, source names, and publication time. Coordinates, weather,
F1 standings, Kindle identifiers, books, and Calibre data are not included.
The provider still receives potentially personal interests and the runner's IP
address. Review its retention and training policy before enabling it.

## Output controls and fallback

The system prompt instructs the model to use only supplied records, keep a
neutral factual tone, and return schema-valid JSON. Application validation then
enforces:

- only supplied article IDs;
- no article assigned to multiple summaries;
- bounded story count and field lengths;
- non-empty headline, summary, and relevance text; and
- strict JSON object shape.

These controls reduce hallucination and prompt-injection impact but do not make
model output authoritative. Feed text is untrusted, and important claims should
still be opened at the original source.

The pipeline grounds each brief against validated article IDs and stores the
resulting publisher names with the daily cache. The renderer retains a compact
visible `Source` or `Sources` line even after hourly headlines rotate.
Model-written text does not replace publisher attribution.

Any transport, authentication, quota, JSON, unknown-ID, or schema error causes
that operation to use the deterministic local provider. The dashboard remains
useful without AI rather than publishing a blank morning brief solely because
a model is unavailable.
