# Changelog

All notable changes to this project are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.0.0/), and this project
adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Fixed

- `query_cube` docstring stated the row cap as 5000 when the real ceiling is 2500,
  which could make a model mis-plan paging. Pinned to the constant with a test so it
  can't drift again.
- `list_cubes` silently swallowed a typo'd `scope` or `locale`, returning an empty
  result the envelope then reported as "complete" — a confident lie. It now fails
  loud and names the valid options, matching the fail-loud philosophy everywhere else.
- When a single row exceeded the result size budget, the envelope simultaneously
  claimed "more available" and "no matching data," hiding that data existed but was
  too large. It now says the row was too big and steers to narrowing the query.

## [0.1.0] — 2026-07-08

First public release.

### Added

- Three MCP tools over the official DataSaudi (GASTAT) statistics API:
  - `list_cubes` — discover the 277 available datasets, with an honest
    completeness envelope so a page is never mistaken for the whole catalog.
  - `describe_cube` — inspect a cube's dimensions, levels, measures, and
    members, in English or Arabic.
  - `query_cube` — drill down, pick measures, and filter by member, with
    results returned in an honesty envelope (row echo + completeness).
- Native Arabic support across all three tools (`locale="ar"`) — ask in Arabic,
  get Arabic back (الرياض, not "Al-Riyadh").
- Local validation of measure, level, and filter names that fails loud with the
  valid options — the upstream API silently drops unknown measures and ignores
  bad filters, and this refuses to pass that silence on to the user.
- Byte-budget result trimming (not a fixed row cap) so responses stay under the
  client wall regardless of width or language.
- Keyless operation — no API key, no database; every query hits the live API.

[0.1.0]: https://github.com/mohsinmshabbir/datasaudi-mcp/releases/tag/v0.1.0
