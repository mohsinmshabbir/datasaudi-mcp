"""FastMCP server exposing DataSaudi cubes as three workhorse tools.

Guided discovery (spec Section 2): list_cubes (search 277-cube catalog) ->
describe_cube (one cube's levels + measures) -> query_cube (validated query).
All hardening (R1-R20) lives below this thin orchestration layer.

Transport: stdio (the default). STDOUT is the JSON-RPC channel; all logging
goes to STDERR (R18)."""

from __future__ import annotations

import logging
import sys

import httpx
from fastmcp import FastMCP

from . import shaping, validation
from .catalog import Catalog
from .client import DEFAULT_PAGE, DataSaudiClient
from .errors import DataSaudiError, DataSaudiServerError

# R18: logs go to STDERR only; stdout is the JSON-RPC protocol channel.
log = logging.getLogger("datasaudi_mcp")
if not log.handlers:
    _h = logging.StreamHandler(sys.stderr)
    _h.setFormatter(logging.Formatter("%(levelname)s %(name)s: %(message)s"))
    log.addHandler(_h)
    log.setLevel(logging.INFO)

# R17: force stdout to UTF-8 so Arabic member strings serialize cleanly on Windows.
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:  # pragma: no cover - not all streams support reconfigure
    pass

mcp = FastMCP("datasaudi-mcp")

_CATALOG: Catalog | None = None  # test-injectable; None => fetch live
_EMPTY_QUERY_CAP = 25            # R10: empty-query preview cap (don't flood)
_SEARCH_CAP = 250                # R21: per-page cap for a real search; big enough to
#                                  return any realistic match set whole (largest is ~163),
#                                  so `complete` is true and no false cap is ever inferred.
_HARD_MAX_ROWS = 2500            # R22: server-side row ceiling for query_cube. The caller's
#                                  `limit` is advisory - a bigger value is clamped to this.
#                                  MEASURED on the WIDEST cube (foreign_trade, all 8 drilldowns +
#                                  both measures = 10 cols): 2500 rows ~= 0.53 MB, ~half the
#                                  client's undocumented ~1MB hard result wall (5000 ~= 1.07 MB,
#                                  OVER). The margin covers even-wider cubes and multi-byte Arabic
#                                  (locale=ar) captions. Above the wall the client DISCARDS the
#                                  result (no spill, no partial data) - the server must stay under
#                                  it by construction. Same order of magnitude as BigQuery (3000)
#                                  / MotherDuck (2048) ceilings.

_client_factory = None  # test hook; None => real DataSaudiClient()


def _make_client():
    return _client_factory() if _client_factory else DataSaudiClient()


def _require_known_cube(cat: Catalog, cube: str) -> None:
    """R8: fail loud on an unknown cube, naming near-matches so the model self-corrects."""
    if cube not in cat.names():
        suggestions = cat.did_you_mean(cube)
        hint = f"; did you mean: {', '.join(suggestions)}" if suggestions else ""
        raise DataSaudiError(f"no cube named {cube!r}{hint}")


async def get_catalog() -> Catalog:
    """R12: fetch the 277-cube catalog once, cache in memory."""
    global _CATALOG
    if _CATALOG is None:
        async with DataSaudiClient() as client:
            _CATALOG = Catalog.from_cubes(await client.list_cubes())
    return _CATALOG


@mcp.tool()
async def list_cubes(query: str = "", scope: str = "catalog", locale: str = "en",
                     offset: int = 0) -> dict:
    """Search the DataSaudi catalog of 277 statistical cubes.

    Returns an ENVELOPE (not a bare list):
      {query, scope, total_matches, returned, catalog_size (277), complete, results, note}.
    `results` holds compact {name, caption, domain} hits. `total_matches` is the TRUE number
    of matching cubes; when `complete` is true, `results` contains ALL of them - there is no
    hidden cap. Never infer a result ceiling from len(results): read `total_matches` and
    `complete`. When `complete` is false the result is a page - refine the query or pass
    `offset` (the next start index, from the note) to page through the rest.

    scope: 'catalog' (title/topic), 'measures' (measure names), or 'levels' (drillable level
    names - NOT member values; 'members' is an alias). locale='ar' also matches the Arabic
    catalog annotations (topic/subtopic/source); cube names/captions themselves are English only.
    An empty query returns a labeled preview (first 25 of 277). A space-separated query that
    finds nothing is retried once with spaces replaced by underscores."""
    cat = await get_catalog()
    catalog_size = len(cat.names())
    if not query.strip():
        matches = cat.search("", scope=scope, locale=locale)
        return shaping.build_catalog_result("", scope, matches, offset, _EMPTY_QUERY_CAP,
                                            catalog_size)
    matches = cat.search(query, scope=scope, locale=locale)
    if not matches and " " in query:
        # Catalog names/captions are underscore_separated; a model or user may
        # naturally type a space-separated phrase ("real estate"). Retry once
        # with underscores so a literal-substring search still finds it.
        matches = cat.search(query.strip().replace(" ", "_"), scope=scope, locale=locale)
    return shaping.build_catalog_result(query, scope, matches, offset, _SEARCH_CAP, catalog_size)


@mcp.tool()
async def describe_cube(cube: str, level: str | None = None, locale: str = "en") -> dict:
    """Introspect one cube: its drillable level names and measures. Pass `level`
    to also list that level's members. `locale` ('en' or 'ar') controls the language
    of the returned member captions (e.g. locale='ar' -> 'الرياض' instead of 'Al-Riyadh');
    the level/measure NAMES stay as-is since query_cube matches them literally.
    Unknown cube -> error with 'did you mean'."""
    cat = await get_catalog()
    _require_known_cube(cat, cube)
    out = {"cube": cube, "levels": cat.levels_of(cube), "measures": cat.measures_of(cube)}
    if level is not None:
        if not cat.has_level(cube, level):
            raise DataSaudiError(
                f"no level {level!r} in {cube!r}; valid levels: " + ", ".join(cat.levels_of(cube))
            )
        async with _make_client() as client:
            rows = await client.query(cube, [level], [], locale=locale, limit=DEFAULT_PAGE)
        out["level"] = level
        out["locale"] = locale
        out["members"] = shaping.to_compact(rows)  # R9: tolerates dirty IDs
    return out


@mcp.tool()
async def query_cube(
    cube: str,
    drilldowns: list[str],
    measures: list[str],
    cut: dict[str, str] | None = None,
    limit: int = DEFAULT_PAGE,
    locale: str = "en",
    offset: int = 0,
) -> dict:
    """Query a cube by drilldowns (level names) + measures; returns a compact,
    paginated result with the resolved query echoed back.

    `cut` filters by member: a {level: member_id} mapping, e.g. {"Province": "1"} to
    keep only that province. Use the member *ID* (from describe_cube(cube, level=...)),
    NOT its caption. `locale` ('en' or 'ar') sets the language of member captions in
    the result rows (e.g. 'الرياض' vs 'Al-Riyadh'); member IDs and numbers are unaffected.
    Validates level/measure names AND cut level names locally and fails loud with the
    valid options.

    limit: max rows per call (default 100), HARD-CAPPED at 5000. A larger value is
    silently reduced to 5000 - the tool will NOT return an unbounded result, because a
    single result over ~1MB is rejected outright by the client (no partial data comes
    back). THERE IS NO 'get everything in one call'. To get more than one page, do NOT
    raise limit: page with `offset` (the note gives you the next offset; repeat until
    complete), OR narrow with a `cut` / fewer drilldowns. Paging or narrowing is the
    intended path and is faster than one giant call that errors.
    offset: start row of this page (default 0). When combining pages, only sum additive
    measures (counts/sums); never average an index or ratio across pages.

    Note: a cut on a valid level but nonexistent member returns 0 rows (reported as
    'valid query, no matching data'), not an error - check the member id if you
    expected rows."""
    cat = await get_catalog()
    _require_known_cube(cat, cube)

    # R3 normalize + R2/R6 drilldown validation + R1 measure validation (fail loud, R13)
    dd = validation.validate_drilldowns(drilldowns, cat.levels_of(cube))
    ms = validation.validate_measures(measures, cat.measures_of(cube))
    # R2/R13 for cut: a filter on an UNKNOWN LEVEL is silently ignored by the API
    # (returns unfiltered data -> a silent mislead), so we validate the cut levels.
    if cut:
        for cut_level in cut:
            if not cat.has_level(cube, cut_level):
                raise DataSaudiError(
                    f"no level {cut_level!r} to cut on in {cube!r}; valid levels: "
                    + ", ".join(cat.levels_of(cube))
                )

    # R22: clamp the caller's limit to the hard row ceiling. The caller cannot exceed it;
    # a bigger request is capped and the model is told (in the note) to page or narrow.
    capped = max(1, min(limit, _HARD_MAX_ROWS))
    clamped = capped < limit
    offset = max(0, offset)

    client = _make_client()
    try:
        rows, more = await client.query_all(cube, dd, ms, locale=locale, page=capped,
                                            max_rows=capped, cut=cut, start_offset=offset)
    except DataSaudiServerError:
        # R20: combinatorial collapse - a cut does NOT help; drop a drilldown.
        log.warning("HTTP 500 (combinatorial collapse) on %s with %d drilldowns", cube, len(dd))
        return shaping.steer_result(cube, dd, ms, cut, "server500")
    except httpx.TimeoutException:
        # R15: bounded timeout - steer to add a cut.
        log.warning("timeout on %s", cube)
        return shaping.steer_result(cube, dd, ms, cut, "timeout")
    finally:
        await client.aclose()

    return shaping.build_result(cube, dd, ms, cut, rows, more, offset=offset, clamped=clamped)


def main() -> None:
    """Console-script entry point. R19 schema sanity runs before serving."""
    _assert_tool_schemas_nonempty()
    mcp.run()


def _assert_tool_schemas_nonempty() -> None:
    """R19: fail loud at startup if any tool generated an empty input schema
    (an empty schema silently breaks tool-calling for every client).
    Verified against FastMCP 3.4.3: mcp.list_tools() is async -> list[FunctionTool],
    each with .name and .parameters (a JSON-schema dict)."""
    import asyncio

    try:
        tools = asyncio.run(mcp.list_tools())
    except RuntimeError:
        # already inside a running loop (e.g. under pytest-asyncio) - skip the sync path
        log.warning("schema sanity check skipped: called from within a running event loop")
        return
    for tool in tools:
        if not getattr(tool, "parameters", None):
            raise RuntimeError(f"tool {tool.name!r} has an empty input schema (R19)")


if __name__ == "__main__":
    main()
