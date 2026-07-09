import json
import sys
from pathlib import Path

import httpx
import pytest

import datasaudi_mcp.server as server
from datasaudi_mcp.catalog import Catalog
from datasaudi_mcp.client import DataSaudiClient
from datasaudi_mcp.errors import DataSaudiError

FIXTURE = Path(__file__).parent / "fixtures" / "cubes.json"


@pytest.fixture(autouse=True)
def offline_catalog():
    cubes = json.load(open(FIXTURE, encoding="utf-8"))["cubes"]
    server._CATALOG = Catalog.from_cubes(cubes)
    yield
    server._CATALOG = None


@pytest.mark.asyncio
async def test_describe_cube_returns_all_levels_and_measures():
    out = await server.describe_cube("gastat_real_estate")
    assert set(out["levels"]) == {"Nation", "Province", "Year", "Quarter"}  # R7
    assert out["measures"] == ["Price Index", "Growth"]


@pytest.mark.asyncio
async def test_describe_unknown_cube_suggests():
    # R8: unknown cube fails loud with did-you-mean
    with pytest.raises(DataSaudiError) as exc:
        await server.describe_cube("gastat_realestate")  # missing underscore
    assert "gastat_real_estate" in str(exc.value)


@pytest.mark.asyncio
async def test_list_cubes_compact():
    out = await server.list_cubes("real estate")
    hits = out["results"]
    assert any(h["name"] == "gastat_real_estate" for h in hits)
    assert "dimensions" not in hits[0]  # R10 compact


@pytest.mark.asyncio
async def test_list_cubes_envelope_reports_completeness():
    # R21: the envelope tells the model total_matches, catalog_size, and complete -
    # so it can NEVER infer a false cap from len(results). (The live-drive bug.)
    out = await server.list_cubes("real estate")
    assert out["catalog_size"] == 277
    assert out["total_matches"] == out["returned"]  # small match set: all returned
    assert out["complete"] is True
    assert "complete" in out["note"].lower()


@pytest.mark.asyncio
async def test_list_cubes_broad_search_is_complete_not_capped():
    # R21 regression on the EXACT bug: 'gastat' matched 163 and the model wrongly
    # inferred a '~165 cap'. It must now come back complete with the true count.
    out = await server.list_cubes("gastat")
    assert out["total_matches"] > 100          # a big match set
    assert out["total_matches"] == out["returned"]
    assert out["complete"] is True             # ALL matches returned, no hidden cap
    assert str(out["total_matches"]) in out["note"]


@pytest.mark.asyncio
async def test_list_cubes_empty_query_labeled_preview():
    # R10/R21: empty query returns a LABELED preview (25 of 277), not a silent cap
    out = await server.list_cubes("")
    assert out["returned"] <= 25
    assert out["total_matches"] == 277         # the model is told the true universe
    assert out["complete"] is False            # explicitly a preview, not the whole set
    assert "277" in out["note"]


@pytest.mark.asyncio
async def test_list_cubes_offset_pages_through():
    # R21: offset gives a browse-all path; last page flips complete=true
    page1 = await server.list_cubes("", offset=0)
    page2 = await server.list_cubes("", offset=25)
    names1 = {h["name"] for h in page1["results"]}
    names2 = {h["name"] for h in page2["results"]}
    assert names1.isdisjoint(names2)           # disjoint pages
    assert page2["returned"] > 0


def test_logger_uses_stderr_not_stdout():
    # R18: never log to stdout (it is the JSON-RPC channel)
    handlers = server.log.handlers
    streams = [getattr(h, "stream", None) for h in handlers]
    assert sys.stdout not in streams
    assert any(s is sys.stderr for s in streams)


def _fake_client(handler):
    c = DataSaudiClient()
    c._client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    return c


@pytest.mark.asyncio
async def test_describe_cube_level_lists_members_offline():
    # R9: describe_cube(cube, level=) fetches that level's members and tolerates dirty IDs
    async def handler(request):
        return httpx.Response(200, json={"data": [
            {"Province ID": 1, "Province": "Al-Riyadh"},
            {"Province ID": None, "Province": "الرياض"},  # dirty: null id + arabic
        ]})
    server._client_factory = lambda: _fake_client(handler)
    try:
        out = await server.describe_cube("gastat_real_estate", level="Province")
        assert out["level"] == "Province"
        assert "Province" in out["members"]["columns"]
        # dirty null-id row and arabic survived shaping
        assert any(row[out["members"]["columns"].index("Province")] == "الرياض"
                   for row in out["members"]["rows"])
    finally:
        server._client_factory = None


@pytest.mark.asyncio
async def test_describe_cube_forwards_locale_to_member_query():
    # locale='ar' must reach the member query so captions come back in Arabic
    seen = {}

    async def handler(request):
        seen["params"] = dict(request.url.params)
        return httpx.Response(200, json={"data": [{"Province ID": 1, "Province": "الرياض"}]})
    server._client_factory = lambda: _fake_client(handler)
    try:
        out = await server.describe_cube("gastat_real_estate", level="Province", locale="ar")
        assert seen["params"]["locale"] == "ar"   # forwarded to the API
        assert out["locale"] == "ar"              # echoed in the result
    finally:
        server._client_factory = None


@pytest.mark.asyncio
async def test_describe_cube_bad_level_fails_loud():
    # bad level name -> DataSaudiError with valid levels, never hits the API
    with pytest.raises(DataSaudiError) as exc:
        await server.describe_cube("gastat_real_estate", level="Banana")
    assert "Banana" in str(exc.value)


@pytest.mark.asyncio
async def test_list_cubes_no_space_query_zero_hits_returns_empty():
    # the space->underscore fallback should NOT invent matches for a genuinely-absent term
    out = await server.list_cubes("zzznotarealthing")
    assert out["results"] == []
    assert out["total_matches"] == 0
    assert out["complete"] is True  # zero matches IS the complete (empty) set


@pytest.mark.asyncio
async def test_query_cube_happy_path_wraps_result():
    async def handler(request):
        return httpx.Response(200, json={"data": [{"Province": "Al-Riyadh", "Price Index": 74.4}]})
    server._client_factory = lambda: _fake_client(handler)
    try:
        out = await server.query_cube("gastat_real_estate", ["Province"], ["Price Index"])
        assert out["row_count"] == 1                          # R6b
        assert out["resolved"]["cube"] == "gastat_real_estate"
        assert out["data"]["columns"] == ["Province", "Price Index"]
    finally:
        server._client_factory = None


@pytest.mark.asyncio
async def test_query_cube_bad_measure_fails_loud_before_calling():
    # R1: bad measure never even reaches the API
    called = {"n": 0}

    async def handler(request):
        called["n"] += 1
        return httpx.Response(200, json={"data": []})
    server._client_factory = lambda: _fake_client(handler)
    try:
        with pytest.raises(Exception) as exc:
            await server.query_cube("gastat_real_estate", ["Province"], ["Fake Measure"])
        assert "Fake Measure" in str(exc.value)
        assert called["n"] == 0                               # never hit the API
    finally:
        server._client_factory = None


@pytest.mark.asyncio
async def test_query_cube_bad_drilldown_fails_loud_before_calling():
    called = {"n": 0}

    async def handler(request):
        called["n"] += 1
        return httpx.Response(200, json={"data": []})
    server._client_factory = lambda: _fake_client(handler)
    try:
        with pytest.raises(Exception) as exc:
            await server.query_cube("gastat_real_estate", ["Date Quarter"], ["Price Index"])
        assert "Date Quarter" in str(exc.value)
        assert called["n"] == 0
    finally:
        server._client_factory = None


@pytest.mark.asyncio
async def test_query_cube_unknown_cube_suggests():
    with pytest.raises(DataSaudiError) as exc:
        await server.query_cube("gastat_realestate", ["Province"], ["Price Index"])
    assert "gastat_real_estate" in str(exc.value)


@pytest.mark.asyncio
async def test_query_cube_500_returns_drop_drilldown_steer():
    # R20: a 500 comes back with the drop-a-drilldown steer, not add-a-cut
    async def handler(request):
        return httpx.Response(500, text="Internal Server Error")
    server._client_factory = lambda: _fake_client(handler)
    try:
        out = await server.query_cube(
            "donor_data",
            ["Year", "Destination Organization", "Destination Organization Type",
             "Reporting Organization Type", "Sector", "Funding Status", "Source Country"],
            ["Value"],
        )
        assert "drilldown" in out["note"].lower()
    finally:
        server._client_factory = None


@pytest.mark.asyncio
async def test_query_cube_timeout_returns_add_cut_steer():
    # R15: a timeout returns the "add a cut" steer (NOT the drop-drilldown one).
    # Guards against the 500/timeout steer branches being swapped.
    async def handler(request):
        raise httpx.TimeoutException("slow")
    server._client_factory = lambda: _fake_client(handler)
    try:
        out = await server.query_cube("gastat_real_estate", ["Province"], ["Price Index"])
        note = out["note"].lower()
        assert "cut" in note                 # add-a-cut advice
        assert "drilldown" not in note       # must NOT be the server500 steer
    finally:
        server._client_factory = None


@pytest.mark.asyncio
async def test_query_cube_forwards_cut_as_level_param_and_echoes_it():
    # cut ({level: member}) must reach the API as <Level>=<member> AND be echoed in resolved.cut
    seen = {}

    async def handler(request):
        seen["params"] = dict(request.url.params)
        return httpx.Response(200, json={"data": [{"Province": "Al-Riyadh", "Price Index": 74.4}]})
    server._client_factory = lambda: _fake_client(handler)
    try:
        out = await server.query_cube("gastat_real_estate", ["Province"], ["Price Index"],
                                      cut={"Quarter": "20211"})
        assert seen["params"].get("Quarter") == "20211"        # verified filter syntax
        assert out["resolved"]["cut"] == {"Quarter": "20211"}   # echoed back (R6b)
    finally:
        server._client_factory = None


@pytest.mark.asyncio
async def test_query_cube_forwards_locale():
    # locale='ar' must reach the data query so member captions come back in Arabic
    seen = {}

    async def handler(request):
        seen["params"] = dict(request.url.params)
        return httpx.Response(200, json={"data": [{"Province": "الرياض", "Price Index": 74.4}]})
    server._client_factory = lambda: _fake_client(handler)
    try:
        out = await server.query_cube("gastat_real_estate", ["Province"], ["Price Index"],
                                      locale="ar")
        assert seen["params"]["locale"] == "ar"
        # the Arabic caption survived into the compact result
        prov_i = out["data"]["columns"].index("Province")
        assert out["data"]["rows"][0][prov_i] == "الرياض"
    finally:
        server._client_factory = None


@pytest.mark.asyncio
async def test_query_cube_clamps_huge_limit_to_ceiling():
    # R22: the caller's limit is advisory. A limit=1000000 is clamped to the server ceiling,
    # never sent to the API, so the result can NEVER exceed the ~1MB client wall.
    seen = {"limits": []}

    async def handler(request):
        # record the per-page 'limit' rows the server actually requests
        seen["limits"].append(int(dict(request.url.params)["limit"].split(",")[0]))
        # return a FULL page so query_all thinks more may exist and stops at max_rows
        return httpx.Response(200, json={"data": [{"i": n} for n in range(server._HARD_MAX_ROWS)]})
    server._client_factory = lambda: _fake_client(handler)
    try:
        out = await server.query_cube("gastat_real_estate", ["Province"], ["Price Index"],
                                      limit=1_000_000)
        # never requested more than the ceiling per page
        assert all(lim <= server._HARD_MAX_ROWS for lim in seen["limits"])
        assert out["returned"] <= server._HARD_MAX_ROWS
        assert out["more"] is True and out["complete"] is False
        # the note leads with the cap fact and gives a next offset to page
        note = out["note"].lower()
        assert "cap" in note and "offset=" in note
    finally:
        server._client_factory = None


@pytest.mark.asyncio
async def test_query_cube_offset_reaches_the_api_and_is_echoed():
    # R22: offset threads through to the API and is reported back so the model can page
    seen = {}

    async def handler(request):
        seen["params"] = dict(request.url.params)
        return httpx.Response(200, json={"data": [{"Province": "Makkah", "Price Index": 72.2}]})
    server._client_factory = lambda: _fake_client(handler)
    try:
        out = await server.query_cube("gastat_real_estate", ["Province"], ["Price Index"],
                                      offset=100)
        # the API 'limit' param is "rows,offset" - the offset half must be 100
        assert dict(seen["params"])["limit"].split(",")[1] == "100"
        assert out["offset"] == 100
    finally:
        server._client_factory = None


@pytest.mark.asyncio
async def test_query_cube_cut_on_bad_level_fails_loud_before_calling():
    # A cut on an UNKNOWN LEVEL is silently ignored by the API (returns unfiltered =
    # silent mislead). We must reject it locally before any API call.
    called = {"n": 0}

    async def handler(request):
        called["n"] += 1
        return httpx.Response(200, json={"data": []})
    server._client_factory = lambda: _fake_client(handler)
    try:
        with pytest.raises(DataSaudiError) as exc:
            await server.query_cube("gastat_real_estate", ["Province"], ["Price Index"],
                                    cut={"Banana": "1"})
        assert "Banana" in str(exc.value)
        assert called["n"] == 0
    finally:
        server._client_factory = None


@pytest.mark.asyncio
async def test_query_cube_persistent_non500_propagates_as_error():
    # A persistent transient error (retry-exhausted 503 -> plain DataSaudiError, not a 500)
    # propagates as a raised error, NOT a steer envelope. Deliberate fail-loud: we do not
    # dress an unknown failure as a misleading "no data"/steer result.
    async def _noop():
        return None

    async def handler(request):
        return httpx.Response(503, text="still unavailable")
    fake = _fake_client(handler)
    fake._sleep = lambda s: _noop()
    server._client_factory = lambda: fake
    try:
        with pytest.raises(DataSaudiError):
            await server.query_cube("gastat_real_estate", ["Province"], ["Price Index"])
    finally:
        server._client_factory = None


@pytest.mark.asyncio
async def test_all_tool_schemas_nonempty():
    # R19: every registered tool must expose a non-empty input schema
    tools = await server.mcp.list_tools()   # FastMCP 3.x: async, returns list[FunctionTool]
    assert len(tools) == 3                   # list_cubes, describe_cube, query_cube
    for tool in tools:
        assert tool.parameters, f"tool {tool.name} has an empty input schema"


def test_schema_sanity_check_runs_without_error():
    # R19: the startup guard itself does not raise for our valid tools
    server._assert_tool_schemas_nonempty()
