<!-- mcp-name: io.github.mohsinmshabbir/datasaudi-mcp -->

<div align="center">

# datasaudi-mcp

*Ask Claude, Cursor, or any MCP client about the Saudi economy —*
*in plain English **or Arabic**. No API key. No database.*

[![PyPI](https://img.shields.io/pypi/v/datasaudi-mcp.svg)](https://pypi.org/project/datasaudi-mcp/)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/)
[![CI](https://github.com/mohsinmshabbir/datasaudi-mcp/actions/workflows/ci.yml/badge.svg)](https://github.com/mohsinmshabbir/datasaudi-mcp/actions)

<br/>

**[Ask it](#ask-it-anything)**&nbsp;&nbsp;·&nbsp;&nbsp;**[Coverage](#what-you-can-ask-about)**&nbsp;&nbsp;·&nbsp;&nbsp;**[Install](#install)**&nbsp;&nbsp;·&nbsp;&nbsp;**[العربية](#arabic-support)**&nbsp;&nbsp;·&nbsp;&nbsp;**[Tools](#the-tools)**

</div>

---

GDP, inflation, trade, population, the real‑estate price index — **277 official
[GASTAT](https://www.stats.gov.sa) datasets**, live from [DataSaudi](https://datasaudi.sa),
answered right inside your AI client. You never name a dataset; the model finds it.

Here it is in Claude Desktop — one plain‑English question, and the model finds the dataset,
pulls Riyadh's real‑estate price index against the national trend, and charts it:

https://github.com/user-attachments/assets/99c0433c-91fb-4815-94a5-349c589ad4ec

> [!NOTE]
> The PyPI package is publishing now. Until it lands, install from source (see
> [Contributing](#contributing)). The `uvx` command below works the moment it's live.

---

## Ask it anything

Connect it in about 2 minutes ([Install](#install)), then just ask:

> 💬 &nbsp;*"What was the real‑estate price index in Riyadh by quarter, and how does it
> compare to the national trend?"*

> 💬 &nbsp;*"Who are Saudi Arabia's top trading partners? Break foreign trade down by
> country and exports vs. imports."*

> 🇸🇦 &nbsp;*"اعرض الرقم القياسي لأسعار العقارات في الرياض حسب الربع"*
> &nbsp;&nbsp;— ask in Arabic, get Arabic back (`الرياض`, `مكة المكرمة`). See [Arabic support](#arabic-support).

The model discovers the right dataset, pulls the numbers, and answers. **You don't need to
know any dataset names or query syntax.**

<details>
<summary><b>More example prompts</b></summary>

<br/>

- *"Show me inflation and the CPI by province for the latest year — which regions were highest?"*
- *"How has the real‑estate price index differed between villas and apartments over time?"*
- *"What's the population by province, split by sex and nationality (Saudi vs. non‑Saudi)?"*
- *"Show me real GDP by economic sector, quarter over quarter, with year‑on‑year growth."*
- *"Compare average monthly wages: Saudi vs. non‑Saudi, and men vs. women."*

</details>

---

## What you can ask about

277 curated GASTAT / DataSaudi datasets. Every query hits the **live** API, so the numbers
are as current as GASTAT publishes.

<table>
<tr>
<td width="50%" valign="top">

**📈 Economy**

GDP (sector / expenditure / activity), CPI & inflation (national + by province), the
Producer Price Index, FDI, foreign trade (country / product / flow), the trade balance,
business & consumer confidence.

</td>
<td width="50%" valign="top">

**👥 Society**

Population (province / sex / nationality / age), households & dwellings, wages, employment
& participation rates, education, health, disability.

</td>
</tr>
<tr>
<td width="50%" valign="top">

**🏗️ Real estate**

The price **index** by province and property type (villa / apartment / land), building
permits, the construction cost index, housing tenure & type.

</td>
<td width="50%" valign="top">

**🌍 More**

Tourism & hotel occupancy, energy & water, Hajj & Umrah, SAMA financial series,
internationally‑reported (World Bank / UN) indicators.

</td>
</tr>
</table>

> [!IMPORTANT]
> **Where it stops — on purpose.** A data tool you can trust tells you its edges.
> - Serves the real‑estate **price index** (base‑year 100) — **not per‑deal prices in riyals** (those live in MoJ / Srem).
> - No MoJ transaction volumes, no REGA, no municipal / ZATCA / CMA data, no microdata. This is the ~277‑series *headline‑indicator* layer, not the full national corpus.
> - Geographic detail stops at the **province** level for most series — no city / district breakdown.
>
> Ask for something outside this and the server says so plainly, rather than guessing.

---

## Install

No API key, nothing to configure — DataSaudi is keyless. You'll need
[`uv`](https://docs.astral.sh/uv/getting-started/installation/) installed.

**Claude Code** — one line, no file editing:

```bash
claude mcp add datasaudi -- uvx datasaudi-mcp
```

<details>
<summary><b>Claude Desktop</b></summary>

<br/>

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

</details>

<details>
<summary><b>Cursor</b></summary>

<br/>

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

</details>

Then ask one of the questions above.

---

## Arabic support

Saudi data in Arabic, as a first‑class feature — not an afterthought.

- **Ask in Arabic, get Arabic back.** Member names return in Arabic script: `الرياض` for
  Riyadh, `مكة المكرمة` for Makkah, `المنطقة الشرقية` for the Eastern Region.
- **Catalog search works in Arabic too** — an Arabic term matches the datasets' Arabic
  topic / source annotations.
- **Numbers and structure are identical** across languages — only the human‑readable
  captions change.

---

## The tools

Three tools do the work; the model calls them for you.

| Tool | What it does |
|---|---|
| `list_cubes` | Search the 277‑dataset catalog by keyword (English or Arabic). |
| `describe_cube` | Show one dataset's breakdown dimensions and measures. |
| `query_cube` | Run a validated query and return tidy rows — with the query echoed back and honest paging. |

<details>
<summary><b>Troubleshooting — "datasaudi" doesn't show up</b></summary>

<br/>

- Did you **fully quit and reopen** the app? (Closing the window isn't enough — quit from the tray.)
- Is your config valid JSON? A stray comma breaks the whole file — paste it into a JSON validator.
- Is `uv` installed and on your PATH? Run `uvx --version` in a terminal.
- Check the client's MCP / tools panel for an error message next to `datasaudi`.

</details>

<details>
<summary><b>Data source & freshness</b></summary>

<br/>

Data comes live from `api.datasaudi.sa` (the DataSaudi Tesseract API, operated by the
Ministry of Economy & Planning; data produced by GASTAT). The server holds **no local copy**
— every query is fetched fresh, so results are always as current as DataSaudi itself. Only
the lightweight dataset *catalog* is cached in memory for the session.

DataSaudi's data‑usage terms are set by its operator; this project is an independent
open‑source client and attributes GASTAT / MEP as the source. Please review DataSaudi's
terms for your use case.

</details>

---

## Contributing

Contributions welcome — see [`CONTRIBUTING.md`](CONTRIBUTING.md). To develop locally:

```bash
git clone https://github.com/mohsinmshabbir/datasaudi-mcp
cd datasaudi-mcp
uv sync --all-extras
uv run pytest -m "not live"    # offline test suite
uv run pytest -m live          # optional: hits the real API
```

## License

MIT — see [LICENSE](LICENSE).
