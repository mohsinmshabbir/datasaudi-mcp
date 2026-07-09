import httpx
import pytest

from datasaudi_mcp.client import DataSaudiClient, DEFAULT_TIMEOUT, DEFAULT_PAGE
from datasaudi_mcp.errors import DataSaudiError, DataSaudiServerError


def make_client(handler) -> DataSaudiClient:
    transport = httpx.MockTransport(handler)
    c = DataSaudiClient()
    c._client = httpx.AsyncClient(transport=transport)  # inject mock transport
    return c


def test_constants_pinned():
    assert DEFAULT_TIMEOUT == 30.0
    assert DEFAULT_PAGE == 100


@pytest.mark.asyncio
async def test_http_500_raises_server_error_for_r20():
    async def handler(request):
        return httpx.Response(500, text="Internal Server Error")
    c = make_client(handler)
    with pytest.raises(DataSaudiServerError):
        await c.query("donor_data", ["a", "b", "c", "d", "e", "f", "g"], ["Value"])
    await c.aclose()


@pytest.mark.asyncio
async def test_http_400_raises_plain_error_with_detail():
    async def handler(request):
        return httpx.Response(400, json={"error": True, "detail": "bad level"})
    c = make_client(handler)
    with pytest.raises(DataSaudiError) as exc:
        await c.query("c", ["Banana"], ["m"])
    assert "bad level" in str(exc.value)
    await c.aclose()


@pytest.mark.asyncio
async def test_utf8_arabic_roundtrip():
    async def handler(request):
        return httpx.Response(200, json={"data": [{"Province": "الرياض"}]})
    c = make_client(handler)
    rows = await c.query("c", ["Province"], [])
    assert rows[0]["Province"] == "الرياض"
    await c.aclose()


@pytest.mark.asyncio
async def test_cut_sent_as_level_equals_member_param():
    # VERIFIED syntax (Probe 6/7): a member filter is `<Level>=<memberID>`, NOT the
    # older `cuts=Level:member` (which this deployment SILENTLY IGNORES).
    seen = {}

    async def handler(request):
        seen["params"] = dict(request.url.params)
        return httpx.Response(200, json={"data": []})
    c = make_client(handler)
    await c.query("foreign_trade", ["Month", "HS2"], ["Million SAR"],
                  cut={"Country": "sau", "Year": "2023"})
    assert seen["params"]["Country"] == "sau"
    assert seen["params"]["Year"] == "2023"
    assert "cuts" not in seen["params"]   # the broken param must NOT be sent
    await c.aclose()


@pytest.mark.asyncio
async def test_cut_absent_when_none():
    # No cut -> no extra level params on the request
    seen = {}

    async def handler(request):
        seen["params"] = dict(request.url.params)
        return httpx.Response(200, json={"data": []})
    c = make_client(handler)
    await c.query("c", ["Province"], ["Price Index"])  # cut defaults to None
    assert set(seen["params"]) == {"cube", "locale", "drilldowns", "measures", "limit"}
    await c.aclose()


@pytest.mark.asyncio
async def test_query_all_stops_on_short_page():
    # R4: full page => maybe more; short page => end. total is never trusted.
    pages = {0: [{"i": n} for n in range(100)], 100: [{"i": n} for n in range(100, 130)]}

    async def handler(request):
        offset = int(dict(request.url.params)["limit"].split(",")[1])
        return httpx.Response(200, json={"data": pages.get(offset, [])})
    c = make_client(handler)
    rows, more = await c.query_all("c", ["Province"], ["m"], page=100, max_rows=10_000)
    assert len(rows) == 130
    assert more is False  # 130 < 10000 and last page was short
    await c.aclose()


@pytest.mark.asyncio
async def test_query_all_reports_more_when_capped():
    async def handler(request):
        return httpx.Response(200, json={"data": [{"i": n} for n in range(100)]})  # always full
    c = make_client(handler)
    rows, more = await c.query_all("c", ["Province"], ["m"], page=100, max_rows=100)
    assert len(rows) == 100
    assert more is True  # a full page came back at the cap => more exist
    await c.aclose()


async def _noop():
    return None


@pytest.mark.asyncio
async def test_retry_recovers_from_transient_503():
    # R14: a transient 503 then 200 should succeed after retry
    calls = {"n": 0}

    async def handler(request):
        calls["n"] += 1
        if calls["n"] == 1:
            return httpx.Response(503, text="temporarily unavailable")
        return httpx.Response(200, json={"data": [{"ok": 1}]})
    c = make_client(handler)
    c._sleep = lambda s: _noop()  # no real waiting
    rows = await c.query("c", ["Province"], ["m"])
    assert rows == [{"ok": 1}]
    assert calls["n"] == 2
    await c.aclose()


@pytest.mark.asyncio
async def test_500_is_not_retried():
    # R14/R20: a deterministic 500 must NOT be retried (it just re-crashes)
    calls = {"n": 0}

    async def handler(request):
        calls["n"] += 1
        return httpx.Response(500, text="Internal Server Error")
    c = make_client(handler)
    c._sleep = lambda s: _noop()
    with pytest.raises(DataSaudiServerError):
        await c.query("c", ["a", "b", "c", "d", "e", "f", "g"], ["m"])
    assert calls["n"] == 1  # exactly one attempt, no retry
    await c.aclose()


@pytest.mark.asyncio
async def test_query_all_rejects_nonpositive_page():
    # Folded from Task 12 review: page<=0 would infinite-loop; guard it
    c = make_client(lambda request: httpx.Response(200, json={"data": []}))
    with pytest.raises(ValueError):
        await c.query_all("c", ["Province"], ["m"], page=0)
    await c.aclose()


@pytest.mark.asyncio
async def test_persistent_503_exhausts_retries_then_raises():
    # R14: a persistent transient error must GIVE UP after 1 + MAX_RETRIES attempts
    # (=3 total) and raise DataSaudiError - it must NOT loop forever.
    calls = {"n": 0}

    async def handler(request):
        calls["n"] += 1
        return httpx.Response(503, text="still unavailable")
    c = make_client(handler)
    c._sleep = lambda s: _noop()
    with pytest.raises(DataSaudiError):
        await c.query("c", ["Province"], ["m"])
    assert calls["n"] == 3  # initial attempt + 2 retries, then raise
    await c.aclose()


@pytest.mark.asyncio
async def test_retry_after_numeric_header_sets_delay():
    # R14: a numeric Retry-After header determines the backoff delay
    delays = []

    async def handler(request):
        if len(delays) == 0 and getattr(handler, "first", True):
            handler.first = False
            return httpx.Response(503, headers={"Retry-After": "3"}, text="wait")
        return httpx.Response(200, json={"data": [{"ok": 1}]})
    handler.first = True

    async def fake_sleep(s):
        delays.append(s)
    c = make_client(handler)
    c._sleep = fake_sleep
    rows = await c.query("c", ["Province"], ["m"])
    assert rows == [{"ok": 1}]
    assert delays == [3.0]  # honored the numeric Retry-After, not exponential
    await c.aclose()
