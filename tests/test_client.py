"""Smoke tests for DataSaudiClient against the live API.

These hit the real api.datasaudi.sa (keyless, no WAF). If they fail offline, that's expected —
mark with a network marker or mock later. Kept as live tests here because the whole point of this
project is that the API is reachable without ceremony.
"""

import pytest

from datasaudi_mcp.client import DataSaudiClient, DataSaudiError


@pytest.mark.live
@pytest.mark.asyncio
async def test_list_cubes_returns_many():
    async with DataSaudiClient() as c:
        cubes = await c.list_cubes()
    assert len(cubes) > 200  # verified 277 on 2026-07-07
    assert all("name" in cube for cube in cubes)


@pytest.mark.live
@pytest.mark.asyncio
async def test_query_real_estate_price_index():
    async with DataSaudiClient() as c:
        rows = await c.query(
            cube="gastat_real_estate",
            drilldowns=["Province", "Quarter"],  # LEVEL names, not dimension names
            measures=["Price Index"],
            limit=5,
        )
    assert rows
    assert "Price Index" in rows[0]
    assert "Province" in rows[0]


@pytest.mark.live
@pytest.mark.asyncio
async def test_bad_drilldown_surfaces_api_detail():
    """Drilling on a DIMENSION name instead of a LEVEL name must raise with the API's message."""
    async with DataSaudiClient() as c:
        with pytest.raises(DataSaudiError, match="Level"):
            await c.query(
                cube="gastat_real_estate",
                drilldowns=["Date Quarter"],  # dimension name — invalid; leaf level is "Quarter"
                measures=["Price Index"],
            )


def _has_arabic(s: str) -> bool:
    # Arabic + Arabic Supplement blocks (U+0600..U+06FF, U+0750..U+077F)
    return any("؀" <= ch <= "ۿ" or "ݐ" <= ch <= "ݿ" for ch in s)


@pytest.mark.live
@pytest.mark.asyncio
async def test_arabic_member_roundtrip_live():
    # R17: a REAL Arabic caption survives the full HTTP -> decode path uncorrupted.
    # Query with locale='ar' so province captions come back in Arabic script.
    async with DataSaudiClient() as c:
        rows = await c.query("gastat_real_estate", ["Province"], ["Price Index"],
                             locale="ar", limit=20)
    provinces = [r.get("Province", "") for r in rows]
    assert rows
    assert any(_has_arabic(p) for p in provinces), (
        "expected at least one Arabic province caption; got: " + repr(provinces[:5])
    )
    assert all("�" not in p for p in provinces)  # no U+FFFD replacement char


@pytest.mark.live
@pytest.mark.asyncio
async def test_bad_measure_silently_dropped_live():
    # Regression guard on the API contract behind R1 (Probe D): a bad measure => 200, no column
    from datasaudi_mcp.shaping import to_compact
    async with DataSaudiClient() as c:
        rows = await c.query("gastat_real_estate", ["Province"], ["Definitely Not A Measure"], limit=3)
    assert rows
    # the server SILENTLY drops the bad measure - the column is absent (this is why R1 validates locally)
    assert "Definitely Not A Measure" not in to_compact(rows)["columns"]


@pytest.mark.live
@pytest.mark.asyncio
async def test_cut_by_level_member_filters_live():
    # Verified cut contract (Probe 6/7): {Level: memberID} genuinely filters the result.
    # gastat_real_estate has 14 provinces; cutting to Province=1 (Al-Riyadh) must yield 1.
    async with DataSaudiClient() as c:
        full = await c.query("gastat_real_estate", ["Province"], ["Price Index"], limit=500)
        cut = await c.query("gastat_real_estate", ["Province"], ["Price Index"],
                            limit=500, cut={"Province": "1"})
    assert len({r.get("Province") for r in full}) > 1          # baseline: many provinces
    assert len({r.get("Province") for r in cut}) == 1          # the cut actually filtered


@pytest.mark.live
@pytest.mark.asyncio
async def test_cut_bad_member_returns_zero_rows_live():
    # A cut on a valid level but nonexistent MEMBER returns 0 rows (safe - R6b signals it),
    # NOT the full unfiltered set. Documents why a bad member is not a silent-mislead.
    async with DataSaudiClient() as c:
        rows = await c.query("gastat_real_estate", ["Province"], ["Price Index"],
                            limit=500, cut={"Province": "99999"})
    assert rows == []


@pytest.mark.live
@pytest.mark.asyncio
async def test_describe_cube_arabic_members_live():
    # End-to-end: describe_cube(level=, locale='ar') returns AUTHORITATIVE Arabic member
    # captions from GASTAT (not a model guess). This is the gap the live test drive found.
    import datasaudi_mcp.server as server
    server._CATALOG = None  # force a live catalog fetch
    try:
        out = await server.describe_cube("gastat_real_estate", level="Province", locale="ar")
        captions = [row[out["members"]["columns"].index("Province")]
                    for row in out["members"]["rows"]]
        assert out["locale"] == "ar"
        assert any(_has_arabic(cap) for cap in captions), f"got: {captions[:5]}"
        assert all("�" not in cap for cap in captions if cap)
    finally:
        server._CATALOG = None
