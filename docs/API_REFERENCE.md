# DataSaudi Tesseract API — verified reference

Everything here was verified on **2026-07-07** by hitting the live API with raw HTTP and parsing
the JSON (not a summarizer — an early WebFetch pass hallucinated the cube count as 67; the real
count is 277). Trust this doc over any web summary.

## Endpoint basics

- **Base URL:** `https://api.datasaudi.sa/tesseract`
- **Auth:** none (keyless).
- **WAF:** none. 3 rapid-fire calls all returned HTTP 200 in ~0.1–0.4s with no cooldown. This is
  the opposite of `open.data.gov.sa`, which is behind an Akamai behavioral WAF requiring ~6s pacing.
- **Engine:** Tesseract OLAP on FastAPI/Starlette, Python 3.10 (confirmed from a 400's own stack
  trace: `tesseract_olap.logiclayer.module`). Same engine Datawheel uses for DataUSA/DataMexico —
  i.e. DataSaudi is an official "Data Commons on Tesseract."
- **Operator:** Ministry of Economy & Planning (MEP); data produced by GASTAT. The website claims
  no public API/download, but the `tesseract/` backend is open.
- **License:** unconfirmed. The site emphasizes interactive visualization. Check before publishing.

## Endpoints used

### `GET /cubes?locale=en`

Returns `{name, locales, default_locale, annotations, cubes: [...]}`. **277 cubes.** ~540 KB.
A snapshot is cached at `tests/fixtures/cubes.json`.

Each cube:
```jsonc
{
  "name": "gastat_real_estate",
  "caption": "gastat_real_estate",
  "annotations": { "source_name": "...", "source_link": "..." },
  "dimensions": [ { "name": "Geography Province", "hierarchies": [ { "levels": [ {"name":"Nation"}, {"name":"Province"} ] } ] }, ... ],
  "measures":   [ { "name": "Price Index" }, { "name": "Growth" } ]
}
```

### `GET /data.jsonrecords`

Query params:
| param | value |
|---|---|
| `cube` | cube `name` |
| `locale` | `en` (or `ar`) |
| `drilldowns` | comma-joined **LEAF LEVEL** names (see gotcha) |
| `measures` | comma-joined measure names |
| `limit` | `"{rows},{offset}"` e.g. `"500,0"` |
| `<Level>` | member filter: the **level name as the param key**, member **ID** as value (see filter gotcha) |

Returns `{data: [ {<Level> ID, <Level>, <Measure>...}, ... ], ...}`.
Note: the `total` field was **null** on some queries — don't rely on it for a row count.

## THE FILTER GOTCHA (verified 2026-07-08): filter with `<Level>=<memberID>`, NOT `cuts=`

To filter to specific members, add a query param **keyed by the level name** whose value is the
member **ID** (the `<Level> ID` field from a drilldown row):

```
# only Al-Riyadh (Province ID 1), by quarter:
GET /data.jsonrecords?cube=gastat_real_estate&drilldowns=Province,Quarter&measures=Price Index&Province=1
  -> 21 rows, all Province="Al-Riyadh"   (vs 294 rows / 14 provinces unfiltered)
```
Multiple filters AND together (`&Province=1&Year=2021`).

**Silent traps found by probing (this is why the MCP validates cut levels locally):**
- `cuts=Level:member` (an older Tesseract convention) is **SILENTLY IGNORED** by this deployment —
  returns the *full unfiltered set* with HTTP 200. Do NOT use it.
- A filter on an **unknown LEVEL** (e.g. `BadLevel=1`) is **silently ignored** → unfiltered data,
  no error. A plausible-but-wrong result. (The `query_cube` tool validates the cut level to prevent this.)
- The value must be the member **ID**, not the caption. A caption (`Province=Al-Riyadh`) is ignored or 500s.
- A valid level with a **nonexistent member** (`Province=99999`) returns **0 rows** (safe — surfaced as
  "valid query, no matching data"), not the full set.

## THE GOTCHA (cost me a 400 in session): drill on LEVEL, not DIMENSION

A dimension contains hierarchies which contain levels. `drilldowns` wants the **leaf level name**.

- Dimension `Date Quarter` → levels `Year`, `Quarter`. Use **`Quarter`** (or `Year`), NOT `Date Quarter`.
- Dimension `Geography Province` → levels `Nation`, `Province`. Use **`Province`** (or `Nation`).

Drilling on the dimension name returns:
```
HTTP 400 {"error":true,"detail":"Query parameter 'drilldowns' set incorrectly:
          Could not find a Level named 'Date Quarter' in the 'gastat_real_estate' cube."}
```
The `describe_cube` tool exists to hand the model the exact level strings and avoid this.

## Worked examples (verified, copy-paste)

```
# Regional real-estate price index, by province × quarter:
GET /tesseract/data.jsonrecords?cube=gastat_real_estate&locale=en&drilldowns=Province,Quarter&measures=Price Index,Growth&limit=8,0
  -> {"Quarter":"2021-Q1","Province":"Al-Riyadh","Price Index":74.4,"Growth":null}, ...

# Real-estate price index by property type:
GET /tesseract/data.jsonrecords?cube=gastat_real_estate_category&locale=en&drilldowns=Quarter,Type&measures=Price Index&limit=6,0
  -> {"Quarter":"2021-Q1","Type":"Villa","Price Index":77.25}, {"...":"Apartment","Price Index":82.74}, ...

# GDP by economic activity (the URL that started this project):
GET /tesseract/data.jsonrecords?cube=gastat_real_gdp_by_economic_activity&locale=en&drilldowns=Quarter,Economic Sectors&measures=Real GDP&limit=100,0
```
(Spaces in level/measure names are URL-encoded as `%20` or `+`; `httpx` handles this when you pass
them as a dict — see `client.py`.)

## Domain map (name-keyword buckets over all 277 cubes)

| domain | ~count | examples |
|---|---|---|
| energy / environment | 134 | `gastat_fuels_consumed`, `gastat_dwelling_electrical_energy_consumption`, air/water/emissions |
| GDP / economy | 49 | `gastat_real_gdp_by_economic_activity`, `producer_price_index_*`, confidence indices, establishments |
| health | 23 | ambulances, first-aid, disability |
| trade / FDI | 21 | `gastat_fdi_*`, `gastat_exports_value_by_isic_country`, `foreign_trade` |
| population / demographics | 18 | `gastat_detailed_population`, `households`, `births_and_newborns` |
| labor / wages | 14 | `avg_monthly_wages_per_paid_employee`, employment ratios |
| tourism | 11 | Ministry of Tourism / Saudi Tourism Authority series |
| real estate / construction | 11 | `gastat_real_estate`, `gastat_real_estate_category`, `dwellings`, `building_permits`, `construction_cost_index_by_sector`, `gastat_housing_tenure/type` |
| education | 6 | education/training survey |
| (uncategorized) | ~77 | SAMA financial, census, humanitarian aid, dimension tables |

**Sources present** (`annotations.source_name`): GASTAT, Saudi Central Bank (SAMA), Ministry of
Finance, Ministry of Health, Ministry of Tourism, Saudi Census 2022/2023, Saudi Exchange, Invest
Saudi, Riyad Bank, + international (OECD, UNCTAD, KNOMAD, UNOCHA).

## What DataSaudi does NOT have (know the ceiling of this project)

- **No Ministry of Justice cubes.** None of the 277 are MoJ/justice/notary/deed. So no real-estate
  **transaction volumes** (those are on `open.data.gov.sa`, 1,291 MoJ datasets).
- **No REGA, no municipalities, no ZATCA/CMA, no microdata.** DataSaudi is a curated headline-
  indicator layer (~277 series), ~2% of the 13,100-dataset national open-data corpus.
- **No deal-level transaction PRICES anywhere** — DataSaudi has the price *index* (normalized,
  base-year 100), not per-deal SAR values. Per-deal prices are on MoJ's live Srem dashboard only.
- **Harmonization is per-cube, not corpus-wide.** 9 distinct geography-dimension names and 11 time-
  dimension names exist across cubes; cross-cube joins still need reconciliation. Only 108/277 cubes
  carry any geography.

## Gotchas for the developer

- **Don't trust WebFetch/summarizers for this API** — validate against raw JSON. (Under-counted 277→67.)
- **Windows console + Arabic** → `UnicodeEncodeError: cp1252`. Set `PYTHONIOENCODING=utf-8` or
  `sys.stdout.reconfigure(encoding="utf-8")`. It's a console bug, not an API failure.
- The catalog is ~540 KB and rarely changes — cache `list_cubes()` in the server rather than
  refetching per tool call.
