# Privacy and security

Kindle Brief has no account system and does not read the Kindle library. It
still handles network data, location configuration, optional AI credentials,
and a public static release, so its trust boundaries should be explicit.

## Data flow

During a live host build:

- Open-Meteo receives latitude/longitude and forecast parameters.
- Jolpica receives ordinary F1 endpoint requests.
- Each enabled RSS publisher receives the runner IP, TLS metadata, and the
  Kindle Brief user agent.
- An enabled AI provider receives selected article IDs, headlines, bounded
  excerpts, categories, source names, and publication times.
- Astronomy and Chinese lunar date calculations remain local.

When the user taps a news row on the Kindle, its stock browser contacts that
publisher directly. The publisher can then observe the Kindle's IP address,
TLS/browser metadata, cookies, and any interaction performed on the article.
Article launching is disabled by default. Its firmware-internal Chromium path
uses Amazon's single-process and no-sandbox flags inside the Kindle chroot, so a
browser vulnerability in an untrusted publisher page could have greater impact
than ordinary host browsing. Enable it only through the explicitly risk-labeled
KUAL action, and disable it again when not needed.

The backend never reads connected Kindle books, annotations, reading history,
Calibre metadata, account data, or the device serial number. The detector uses
only the non-unique model portion of the USB serial and does not print the full
value.

## Public artifacts

Treat `public/` as public information. Depending on the release schema it can
contain:

- the configured location display name and timezone;
- generated weather and sky data;
- F1 schedule and standings;
- source names, article URLs, headlines, and feed excerpts;
- generated summaries and category preferences; and
- generation timestamps and device-profile metadata.

Use a city-level location name and coordinates if publishing exact whereabouts
would be sensitive. Inspect the complete directory before enabling GitHub
Pages. Do not use private feeds whose titles or URLs would disclose confidential
information.

## Secrets

- Keep `.env` local and untracked.
- Use environment variables or GitHub encrypted secrets only.
- Never put credentials in YAML, feed URLs, base URLs, logs, snapshots, page
  text, or Kindle storage.
- Give the refresh workflow only the one AI key it needs.
- Rotate a key immediately if it appears in Actions logs or a Pages artifact.

The application configuration rejects secret-like fields. AI responses and
transport errors should not include the key, but provider error text can still
reveal request context; review logs before sharing them.

## Untrusted content

RSS entries, API JSON, and model output are untrusted. Kindle Brief:

- uses safe YAML loading and strict known-key configuration;
- parses remote content into bounded immutable models;
- strips feed markup and does not render remote HTML;
- never runs article text as a command or template;
- publishes only bounded, credential-free HTTPS article hitboxes, which the
  device revalidates and passes as one quoted browser argument without `eval`;
- accepts only schema-valid AI output referencing known article IDs;
- uses safe relative paths and fixed page IDs in releases; and
- stages and verifies downloads before cache promotion.

These controls do not validate the truth of a news report. Open consequential
items at the original publisher.

## Static release integrity

The Kindle updater requires HTTPS, known KT5 metadata, fixed page names, and
SHA-256 checksums. This protects against truncated or mismatched downloads. It
does not provide independent publisher authenticity because an attacker who
controls the Pages origin could replace both files and hashes.

Protect the GitHub account with strong multi-factor authentication, protect the
default branch and `github-pages` environment, review workflow changes, and
keep Actions permissions minimal. For a higher-assurance deployment, pin
reviewed GitHub Actions to full commit SHAs and add a separately managed signed
release pointer.

## Cache handling

Host cache files contain public provider responses and normalized article
content, not credentials. Files are permission-restricted and atomically
replaced. GitHub Actions restores cache only for scheduled/manual trusted-branch
builds and saves it only after success. Do not place private feed data in a
shared Actions cache.

Kindle-side page downloads are stored only under the project-owned directory.
No page is converted into an EPUB/AZW document or inserted into the Library.

## Jailbreak risk

SpringBreak is not part of the Kindle Brief codebase. Although the v1.2 ZIP is
pinned and hash-checked, its injected page downloads a mutable `jb.sh` and runs
it as root. The ZIP hash does not cover that live script. Review the current
official flow immediately before use and keep the device in Airplane Mode
except for the explicitly required short network step.

hdnext, KPM, KUAL, and FBInk have their own update and supply chains. Do not
install duplicate legacy hotfixes or a fabricated Kindle Brief KPM package.

## Device write boundary

Rendering, validation, tests, feed checks, and GitHub deployment never write to
a Kindle. The host installer requires an explicit mount argument and completes
all mount/model/firmware/package/ownership/capacity checks before writing. The
uninstaller refuses anything without project ownership markers. Neither script
changes boot configuration or silently deletes user files.
