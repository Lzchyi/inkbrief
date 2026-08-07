# GitHub Pages publishing

`.github/workflows/refresh.yml` builds a live static release and deploys it to
GitHub Pages. It runs:

- at minute 17 of every UTC hour;
- at 23:00 UTC every day, which is 07:00 the next day in
  `Asia/Kuala_Lumpur`; and
- on manual `workflow_dispatch`.

Kuala Lumpur does not observe daylight-saving time. GitHub schedules are not a
real-time service and may be delayed, especially near busy schedule boundaries.
The extra 23:00 UTC trigger prioritizes the morning brief even though the
hourly run also covers that hour.

## Enable Pages

1. Push the repository to GitHub with `refresh.yml` on the default branch.
2. Open **Settings → Pages**.
3. Under **Build and deployment**, choose **GitHub Actions** as the source.
4. Run **Refresh dashboard** manually once.
5. Confirm the `github-pages` environment deployment succeeded.

The build job receives only `contents: read`. The separate deploy job receives
only `pages: write` and `id-token: write`, the permissions required by GitHub's
Pages deployment action. The workflow never commits generated files back to
the repository.

## Configure data and AI

Commit a reviewed non-secret configuration and feed registry before enabling
the schedule. The checked-in example uses the deterministic fallback. The
workflow sets the supported `AI_PROVIDER=auto` environment override: it uses
the first configured standard provider key, or the deterministic fallback when
none exists.

To enable remote AI in the supplied workflow, create only one matching
encrypted Actions secret:

- `GEMINI_API_KEY`
- `GROQ_API_KEY`
- `OPENROUTER_API_KEY`
- `OPENAI_API_KEY`

Undefined secrets become empty environment variables and do not break the
fallback. Auto-detection checks Gemini, Groq, OpenRouter, then OpenAI. Never put
a key in YAML or Pages output. The refresh workflow has no pull-request trigger,
which avoids exposing build secrets to untrusted pull-request code.

`AI_PROVIDER=auto` overrides the YAML provider during this workflow. To pin one
provider, replace that workflow value with its explicit provider name; do not
add several keys and rely on their order.

## Last-success behavior

The workflow restores `.cache/kindle-brief` from the newest successful refresh
on the same branch. A unique cache is saved only after a successful live build,
so a failed or partial build cannot replace the last-good cache. GitHub may
evict caches; a cache is resilience, not a permanent backup.

If current providers are unavailable:

- usable bounded cached data may produce a release marked stale;
- a cold build with insufficient data fails;
- the deploy job is skipped on failure; and
- the already deployed Pages version remains available.

This is safer than publishing an empty dashboard. Review failed scheduled runs
instead of adding `continue-on-error` to the build.

## Published URL

For a project Pages site, the release root is normally:

```text
https://OWNER.github.io/REPOSITORY
```

For an account Pages repository it may be `https://OWNER.github.io`. Confirm
the actual environment URL shown by the deployment, then verify:

```sh
curl -fL https://OWNER.github.io/REPOSITORY/profiles/kt5/current.json
```

Use the public root, not the `profiles/kt5` subdirectory, as the Kindle base
URL. Put that single HTTPS URL in the installed project's
`/mnt/us/kindle-brief/current/config/base-url` file. The Kindle never updates
automatically; it reads this endpoint only when **Update Dashboard** is selected
in KUAL.

The endpoint must be reachable over unauthenticated HTTPS by the Kindle. A
private Pages deployment that requires a browser session will not work with the
minimal on-device downloader.

## Validate before enabling the schedule

Run locally:

```sh
PYTHONPATH=backend .venv/bin/python -m kindle_brief.cli validate \
  --config config/config.example.yaml --feeds config/feeds.yaml
PYTHONPATH=backend .venv/bin/python -m kindle_brief.cli build \
  --config config/config.example.yaml --feeds config/feeds.yaml \
  --cache .cache/kindle-brief --output public --live
```

Inspect `public` before publishing. GitHub Pages is public for ordinary public
repositories, and release snapshots can contain the configured location name,
story URLs, headlines, and excerpts.

## Operational notes

- Scheduled workflows run from the default branch.
- GitHub may disable schedules in inactive repositories.
- Protect the default branch and the `github-pages` environment.
- Enable Dependabot or another review process for GitHub Action updates.
- The workflow uses current official action majors, but major tags are mutable;
  a higher-assurance deployment can pin reviewed action commit SHAs.
- Do not configure a custom domain without HTTPS. The Kindle updater refuses a
  non-HTTPS endpoint.
