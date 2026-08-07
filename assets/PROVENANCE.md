# Raster asset provenance

This record covers the project-authorized raster derivatives used by Kindle
Brief. It records file identity and processing history; it is not evidence of
third-party ownership or licensing.

## Supplied inputs

| Supplied file | Dimensions | SHA-256 | Use |
| --- | ---: | --- | --- |
| `Weather Icons.png` | 1122×1402 | `5c0c2de2ce4ebb7e3ade628db2445ad21e9092a3696087312ad03d67a3ef02be` | Source sheet for weather symbols |
| `Moonphase.png` | 1122×1402 | `8dab4e1539c32b0c27128c6bdc691669be5fd357e3f2422d46e3431467370fa4` | Source sheet for moon phases |
| `F1.png` | 1122×1402 | `4560bfea6e01e25c85b02d39c587f36dab03d9f40e8ad4120742a0f49832d5aa` | Source sheet for generic motorsport symbols only |
| `codex-clipboard-e15bbc4e-af28-43e6-906f-24956e80d943.png` | 854×1146 | `a750dc3a23c3a9c64dfefa4b18c5a601d64754856f60a2cd7cb982ad167c5ff7` | Branded 2026 calendar reference; excluded from production |
| `clipart3297922.png` | 415×340 | `8a209cc0317b8d4c24c0fc738e519963fe24ff4a0ae64b8d8a0091e0e4c59554` | Reference only; not shipped as a production asset |

The project owner supplied these files and authorized their use for this
project. Text embedded in a sheet, including claims such as “MIT License” or
“Open Source,” is descriptive artwork and is not treated as licence evidence.

## Processing and outputs

The weather, moon, and generic motorsport motifs were isolated from the three
source sheets with the built-in image-generation workflow. Local processing
then removed the chroma-key/background and cropped, converted, padded, and
normalized the transparent grayscale assets. The deterministic split/crop
stage is implemented by `scripts/split_icon_atlases.py`. Its optional
`--f1-sheet` input crops the simple alternate helmet and car at documented
source-sheet coordinates for legibility in the 54-pixel standings rows.

| Production master | Dimensions | SHA-256 | Production output |
| --- | ---: | --- | --- |
| `assets/weather/atlas.png` | 1536×1024 | `42e9f9a07c255b158d19d6e4b5dcde0f94dba631f47118c559b189ecb4e72291` | `assets/weather/icons/` |
| `assets/moon/phase-atlas.png` | 1254×1254 | `0296e99c824a263755cfb61cf524121466fe7aa48ff367703dfec5a551c11c56` | `assets/moon/phases/` |
| `assets/icons/motorsport-atlas.png` | 1254×1254 | `fa677f3ca1b84380b01ca3c126c49b9af395076fdb8c402934b092979b50241c` | `assets/icons/motorsport/` |
| `assets/icons/track-symbol.png` | 1536×1024 | `3858bcede4bf1461ed75e7d91ea40597f0cabc6f520091a78aad9f375da1841b` | `assets/icons/motorsport/track.png` |

No Formula 1 logo or full calendar poster is a production asset. The
motorsport outputs are generic dashboard symbols; circuit data under
`assets/tracks/` has separate provenance and terms.

## Image-generation record

Mode: reference-image editing/extraction with a deliberately removable chroma
background, followed by deterministic local cleanup. Prompt directions were:

- Weather: preserve the 18 supplied black line motifs, arrange them in a
  strict 6×3 grid, remove every label and header, and use a flat green field.
- Moon: preserve the eight grayscale lunar textures in phase order on a strict
  4×2 grid, with no labels, ornaments, or typography, on a flat green field.
- Motorsport: preserve only generic helmet, race car, flag, calendar,
  countdown, trophy, and podium motifs; exclude all logos and words; arrange a
  clean atlas on a flat green field.
- Track symbol: isolate a generic circuit-outline category symbol, not any real
  venue, logo, or wordmark, on a flat green field.

The green field was removed locally. Exact real circuit geometry is loaded
from the separately licensed GeoJSON dataset and was never image-generated.

## Original SVGs

`assets/icons/car.svg`, `cloud.svg`, `helmet.svg`, `home.svg`, and `news.svg`
are existing project-original SVGs. They are not derivatives of the supplied
raster sheets and remain covered by `assets/icons/LICENSE.md`.
