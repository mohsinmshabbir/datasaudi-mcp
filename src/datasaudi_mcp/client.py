"""Thin async client for the DataSaudi Tesseract OLAP API. The ONLY module that
speaks HTTP to api.datasaudi.sa. See docs/API_REFERENCE.md for the verified grammar.

Ground truth (verified live): keyless, no WAF; drill on LEAF *LEVEL* names not
dimension names; `total` is always null (paginate by full-page heuristic, R4);
unknown measures are SILENTLY dropped server-side (validated upstream, R1); too many
high-cardinality drilldowns return HTTP 500 (R20).

Member filtering (verified live 2026-07-08): the working syntax is a query param
keyed by the LEVEL name with the member ID as its value, e.g. `Province=1` -> only
Al-Riyadh. A `cuts=Level:member` param (an older Tesseract convention) is SILENTLY
IGNORED by this deployment, and a caption instead of an ID is ignored or 500s. A
filter on an unknown LEVEL is silently ignored (returns unfiltered -> validate the
level upstream, R2-style); a filter on a valid level with an unknown MEMBER returns
0 rows (safe -> R6b signals it)."""

from __future__ import annotations

import asyncio

import httpx

from .errors import DataSaudiError, DataSaudiServerError

BASE_URL = "https://api.datasaudi.sa/tesseract"
DEFAULT_TIMEOUT = 30.0   # R15: fast queries <1s, the cliff is 21-44s, so 30s sits on it
DEFAULT_PAGE = 100       # R5: pinned page size; the API has NO server-side cap

MAX_RETRIES = 2
_TRANSIENT = {429, 502, 503}


class DataSaudiClient:
    def __init__(self, base_url: str = BASE_URL, timeout: float = DEFAULT_TIMEOUT) -> None:
        self._base_url = base_url.rstrip("/")
        self._client = httpx.AsyncClient(timeout=timeout)
        self._sleep = asyncio.sleep

    async def __aenter__(self) -> "DataSaudiClient":
        return self

    async def __aexit__(self, *exc: object) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        await self._client.aclose()

    async def list_cubes(self) -> list[dict]:
        resp = await self._client.get(f"{self._base_url}/cubes", params={"locale": "en"})
        _raise_for_status(resp)
        return resp.json().get("cubes", [])

    async def query(
        self,
        cube: str,
        drilldowns: list[str],
        measures: list[str],
        *,
        locale: str = "en",
        limit: int = DEFAULT_PAGE,
        offset: int = 0,
        cut: dict[str, str] | None = None,
    ) -> list[dict]:
        """Run one page of a data.jsonrecords query. `cut` filters by member: a
        {level: member_id} mapping sent as `<Level>=<member_id>` query params (the
        verified working syntax, Probe 6/7 - `cuts=Level:member` is silently ignored).
        Returns the tidy `data` rows."""
        params = {
            "cube": cube,
            "locale": locale,
            "drilldowns": ",".join(drilldowns),
            "measures": ",".join(measures),
            "limit": f"{limit},{offset}",
        }
        if cut:
            reserved = {"cube", "locale", "drilldowns", "measures", "limit"}
            for level, member in cut.items():
                if level in reserved:
                    # A level whose name collides with a core query param would silently
                    # corrupt the request. No real DataSaudi level does this today, but
                    # fail loud rather than send a malformed query.
                    raise DataSaudiError(f"cannot cut on reserved param name {level!r}")
                params[level] = str(member)
        attempt = 0
        while True:
            resp = await self._client.get(f"{self._base_url}/data.jsonrecords", params=params)
            if resp.status_code in _TRANSIENT and attempt < MAX_RETRIES:
                retry_after = resp.headers.get("Retry-After")
                delay = float(retry_after) if (retry_after or "").isdigit() else 0.5 * (2 ** attempt)
                await self._sleep(delay)
                attempt += 1
                continue
            _raise_for_status(resp)   # 500 -> DataSaudiServerError (not retried), 4xx -> DataSaudiError
            return resp.json().get("data", [])

    async def query_all(
        self,
        cube: str,
        drilldowns: list[str],
        measures: list[str],
        *,
        locale: str = "en",
        page: int = DEFAULT_PAGE,
        max_rows: int = DEFAULT_PAGE,
        cut: dict[str, str] | None = None,
        start_offset: int = 0,
    ) -> tuple[list[dict], bool]:
        """R4: paginate by the full-page heuristic (never trust `total`, which is
        always null). Collect up to max_rows starting at `start_offset`. `cut` is a
        {level: member_id} filter. Returns (rows, more) where `more` means rows exist
        beyond what we returned (i.e. the last fetched page was full at the cap)."""
        if page <= 0:
            raise ValueError(f"page must be positive, got {page}")
        rows: list[dict] = []
        offset = start_offset
        while len(rows) < max_rows:
            batch = await self.query(cube, drilldowns, measures, locale=locale,
                                     limit=page, offset=offset, cut=cut)
            rows.extend(batch)
            if len(batch) < page:      # short page => that was the end
                return rows[:max_rows], False
            offset += page
        # we hit max_rows on full pages => more remain
        return rows[:max_rows], True


def _raise_for_status(resp: httpx.Response) -> None:
    """R13/R20: surface Tesseract's own `detail` on 4xx; a 500 becomes a distinct
    DataSaudiServerError so callers know NOT to retry it (combinatorial collapse)."""
    if resp.is_success:
        return
    detail = resp.text
    try:
        detail = resp.json().get("detail", detail)
    except Exception:
        pass
    if resp.status_code == 500:
        raise DataSaudiServerError(f"HTTP 500: {detail}")
    raise DataSaudiError(f"HTTP {resp.status_code}: {detail}")
