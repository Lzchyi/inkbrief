# Circuit outline attribution

`f1-circuits.geojson` is an unmodified copy of the circuit-coordinate dataset from
[bacinger/f1-circuits](https://github.com/bacinger/f1-circuits), pinned to commit
`432a253890199d0908e7f82044c52de8268cc056` ([source commit][commit]).

- Author: Tomislav Bacinger
- Licence: MIT; see `LICENSE.f1-circuits.md`
- Source file: `f1-circuits.geojson`
- Source SHA-256: `a0c8dfb3109a9181d096985eaa30bd692595eae9125b5b8686744600b24621b5`
- Retrieved: 2026-08-07

The renderer uses only geographic line coordinates and circuit names. It does not include Formula
1, team, sponsor, or championship logos, nor any proprietary broadcast artwork. Formula 1 and
related marks belong to their respective owners; this project is unofficial and is not endorsed by
Formula One Licensing B.V.

The Jolpica-to-source mapping lives in `backend/kindle_brief/renderer/tracks.py`. Its current-season
set was checked against Jolpica's documented
[`/ergast/f1/2026/circuits.json`](https://api.jolpi.ca/ergast/f1/2026/circuits.json?limit=100)
response on 2026-08-07. Unknown IDs use a deliberately generic, original closed-loop outline rather
than another party's artwork.

[commit]: https://github.com/bacinger/f1-circuits/commit/432a253890199d0908e7f82044c52de8268cc056
