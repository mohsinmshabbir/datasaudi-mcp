<!-- mcp-name: io.github.mohsinmshabbir/datasaudi-mcp -->

# datasaudi-mcp

**Ask Claude, Cursor, or any MCP client about the Saudi economy — GDP, inflation, trade,
population, the real‑estate price index — in plain English *or Arabic*, straight from
official [GASTAT](https://www.stats.gov.sa) data via [DataSaudi](https://datasaudi.sa).
No API key. No database.**

[![PyPI](https://img.shields.io/pypi/v/datasaudi-mcp.svg)](https://pypi.org/project/datasaudi-mcp/)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/)
[![CI](https://github.com/mohsinmshabbir/datasaudi-mcp/actions/workflows/ci.yml/badge.svg)](https://github.com/mohsinmshabbir/datasaudi-mcp/actions)

It connects your AI client to **277 official Saudi statistical datasets** — the same headline
indicators GASTAT and the Ministry of Economy & Planning publish — and lets you just *ask*.

### ▶ [Watch the 60‑second demo](https://github.com/mohsinmshabbir/datasaudi-mcp/raw/main/docs/demo.mp4)

A real question in Claude Desktop — the model finds the right dataset, pulls Riyadh's
real‑estate price index and the national trend, and charts them.

<!-- To get an INLINE autoplaying player (better than this link): open a new GitHub Issue on
this repo, drag docs/demo.mp4 into the comment box, copy the generated
https://github.com/user-attachments/assets/... URL, and paste it on its own line here in
place of the heading above. GitHub only auto-embeds video from that upload URL, not from a
raw/ repo path. -->

> **Note:** the PyPI package is being published — until it lands, install from source (see
> [Contributing](#contributing)). The `uvx` command below works once it's on PyPI.

---

## Try asking

Once it's connected (2 minutes — see [Install](#install)), just ask your AI client things like:

1. *"What was Saudi Arabia's real‑estate price index in Riyadh by quarter, and how does it
   compare to the national trend?"*
2. *"Show me inflation and the Consumer Price Index by province for the latest year — which
   regions had the highest inflation?"*
3. *"Who are Saudi Arabia's top trading partners by value? Break foreign trade down by country
   and exports vs. imports."*
4. *"How has the real‑estate price index differed between villas and apartments over time?"*
5. *"What's Saudi Arabia's population by province, split by sex and nationality (Saudi vs.
   non‑Saudi)?"*
6. *"Show me real GDP by economic sector, quarter over quarter, with year‑on‑year growth."*
7. *"Compare average monthly wages for Saudi vs. non‑Saudi workers, and men vs. women."*
8. **بالعربية:** *"اعرض الرقم القياسي لأسعار العقارات في الرياض حسب الربع بالعربية"*
   — ask in Arabic, get Arabic (`الرياض`, `مكة المكرمة`, …). See [Arabic support](#arabic-support).

The model discovers the right dataset, pulls the numbers, and answers — you don't need to know
any dataset names or query syntax.

---

## What it covers

277 curated GASTAT / DataSaudi "cubes" across, among others:

- **Economy** — GDP (by sector / expenditure / activity), the Consumer Price Index & inflation
  (national and by province), the Producer Price Index, FDI, foreign trade (by country / product /
  flow), the trade balance, business & consumer confidence.
- **Society** — population (by province / sex / nationality / age), households & dwellings, wages,
  employment & participation rates, education, health, disability.
- **Real estate** — the real‑estate **price index** by province and by property type (villa /
  apartment / land), building permits, construction cost index, housing tenure & type.
- **More** — tourism & hotel occupancy, energy & water, Hajj & Umrah, SAMA financial series,
  internationally‑reported (World Bank / UN) indicators.

Every query hits the **live** DataSaudi API, so the numbers are as current as GASTAT publishes.

## What it does *not* do

Being honest about the edges is the point — a data tool you can trust is one that tells you where
it stops:

- It serves the real‑estate **price index** (normalized, base‑year 100) — **not per‑deal prices
  in riyals.** Actual transaction prices live in the Ministry of Justice / Srem systems, which
  DataSaudi does not carry.
- **No Ministry of Justice transaction volumes**, no REGA, no municipal data, no ZATCA/CMA, no
  microdata. DataSaudi is the curated ~277‑series *headline‑indicator* layer, not the full national
  open‑data corpus.
- Geographic detail stops at the **province** level for most series — no city/district breakdown.

If you ask for something outside this, the server says so plainly rather than guessing.

---

## Install

Works the same in most MCP clients — pick yours below. You'll need
[`uv`](https://docs.astral.sh/uv/getting-started/installation/) installed (it runs the server with
no separate install step). There is **no API key and nothing to configure** — DataSaudi is keyless.

### Claude Desktop

`Settings → Developer → Edit Config`, add the block below, then **completely quit and reopen**
Claude Desktop (fully quit from the tray — not just close the window):

```json
{
  "mcpServers": {
    "datasaudi": {
      "command": "uvx",
      "args": ["datasaudi-mcp"]
    }
  }
}
```

### Cursor

`Settings → Tools & MCP → New MCP Server` (or edit `~/.cursor/mcp.json`), same block:

```json
{
  "mcpServers": {
    "datasaudi": {
      "command": "uvx",
      "args": ["datasaudi-mcp"]
    }
  }
}
```

### Claude Code (one line, no file editing)

```bash
claude mcp add datasaudi -- uvx datasaudi-mcp
```

Then ask one of the questions above.

---

## Arabic support

Saudi data in Arabic, as a first‑class feature — not an afterthought:

- **Ask in Arabic**, get Arabic back. Set `locale=ar` (the model does this for you when you ask in
  Arabic) and member names return in Arabic script: `الرياض` for Riyadh, `مكة المكرمة` for Makkah,
  `المنطقة الشرقية` for the Eastern Region.
- **Catalog search works in Arabic too** — an Arabic search term matches the datasets' Arabic
  topic / subtopic / source annotations.
- Numbers, IDs, and structure are identical across languages — only the human‑readable captions
  change.

---

## The tools

Three tools do the work; the model calls them for you (you never need to invoke them directly):

| Tool | What it does |
|---|---|
| `list_cubes` | Search the 277‑dataset catalog by keyword (English or Arabic) to find the right dataset. |
| `describe_cube` | Show one dataset's breakdown dimensions and measures (and, on request, its members). |
| `query_cube` | Run a validated query and return tidy rows — with the query echoed back and honest paging. |

## Troubleshooting

**"datasaudi" doesn't show up in my client:**
- Did you **fully quit and reopen** the app? (Closing the window isn't enough — quit from the tray.)
- Is your config valid JSON? A stray comma breaks the whole file — paste it into a JSON validator.
- Is `uv` installed and on your PATH? Run `uvx --version` in a terminal.
- Check the client's MCP/tools panel for an error message next to `datasaudi`.

## Data source & freshness

Data comes live from `api.datasaudi.sa` (the DataSaudi Tesseract API, operated by the Ministry of
Economy & Planning; data produced by GASTAT). The server holds **no local copy** of the data — every
query is fetched fresh, so results are always as current as DataSaudi itself. It caches only the
lightweight dataset *catalog* in memory for the session.

DataSaudi's data‑usage terms are set by its operator; this project is an independent open‑source
client and attributes GASTAT / MEP as the source. Please review DataSaudi's terms for your use case.

## Contributing

Contributions welcome — see [`CONTRIBUTING.md`](CONTRIBUTING.md). To develop locally:

```bash
git clone https://github.com/mohsinmshabbir/datasaudi-mcp
cd datasaudi-mcp
uv venv && uv pip install -e ".[dev]"
pytest -m "not live"          # offline test suite
pytest -m live                # optional: hits the real API
```

## License

MIT — see [LICENSE](LICENSE).
