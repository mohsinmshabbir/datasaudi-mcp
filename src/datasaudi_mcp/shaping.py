"""Pure result-shaping functions. Compact columnar output (R16), query echo +
row_count (R6b), and failure-type-specific steers (R5/R15/R20). No I/O."""

from __future__ import annotations

import json as _json


def to_compact(rows: list[dict]) -> dict:
    """R16: columnar {columns, rows}. Column order = union of keys in first-seen
    order; missing keys become None so the shape is stable across rows.
    Tolerates None / empty / non-ASCII values unchanged (R9/R17)."""
    columns: list[str] = []
    seen = set()
    for row in rows:
        for key in row:
            if key not in seen:
                seen.add(key)
                columns.append(key)
    table = [[row.get(col) for col in columns] for row in rows]
    return {"columns": columns, "rows": table}


# R22: the client discards any tool result over ~1MB. We cap on BYTES (not rows), because
# the same row count is far larger in Arabic (multi-byte) or on a wide/many-measure cube.
# 800 KB leaves comfortable margin under the ~1MB wall for the surrounding envelope text.
_MAX_RESULT_BYTES = 800_000


def _fit_to_byte_budget(rows: list[dict], budget: int = _MAX_RESULT_BYTES) -> tuple[list[dict], bool]:
    """R22: trim rows until the serialized compact data fits under `budget` bytes.
    Returns (kept_rows, trimmed) where trimmed=True means rows were dropped for size.
    Byte-based so it is correct across every cube width and locale (en vs ar)."""
    if not rows:
        return rows, False
    kept = rows
    trimmed = False
    while kept:
        size = len(_json.dumps(to_compact(kept)).encode("utf-8"))
        if size <= budget:
            break
        # drop ~the proportional overflow (at least one row) and re-measure
        drop = max(1, int(len(kept) * (1 - budget / size)) + 1)
        kept = kept[:-drop]
        trimmed = True
    return kept, trimmed


def build_result(cube, drilldowns, measures, cut, rows, more, offset=0, clamped=False):
    """R6b: wrap rows with the resolved query + row_count so an empty or partial
    result is never ambiguous. R5/R22: report the window (offset/returned/complete)
    and steer when truncated. `clamped` means the caller's limit was reduced to the
    server ceiling (R22). R22 also caps the payload by BYTES so it never exceeds the
    client's ~1MB result wall regardless of cube width or locale (Arabic is multi-byte)."""
    resolved = {"cube": cube, "drilldowns": drilldowns, "measures": measures, "cut": cut}
    had_rows = bool(rows)
    rows, trimmed = _fit_to_byte_budget(rows)
    if trimmed:
        more = True   # we dropped rows for size -> there is definitely more
        clamped = True
    n = len(rows)
    # A single row can exceed the whole byte budget, so trimming drops EVERYTHING.
    # That is not "no data" and it is not pageable (the same fat row would return):
    # tell the model the truth - the row was too large - and steer to narrowing.
    oversized_wipeout = trimmed and n == 0 and had_rows
    complete = not more
    nxt = offset + n
    if oversized_wipeout:
        more = False          # paging won't help; do not claim a next page exists
        complete = False      # but the caller did NOT get the data either
        note = ("A single row exceeded the result size budget, so no rows could be "
                "returned. This is NOT 'no data' - the slice HAS data, it's just too "
                "large for one result. Narrow it: request fewer measures, drop a "
                "drilldown, or add a cut (e.g. one year / one province).")
    elif not rows:
        note = "0 rows - query valid, no matching data (this series may not cover that slice)."
    elif more and clamped:
        # R22: the caller asked for more than the hard row ceiling. Lead with the cap fact.
        note = (f"Showing rows {offset + 1}-{nxt} (a bounded page, NOT the full set). Your "
                f"requested limit was capped to the server's row ceiling that keeps one result "
                f"under the client's size wall. Pass offset={nxt} for the next page (repeat until "
                f"complete). Do NOT infer a total from returned - read `more`/`complete`. To shrink "
                f"instead of paging, add a cut (e.g. one year) or drop a drilldown. Combine only "
                f"additive measures (counts/sums) across pages - never an index, average, or ratio.")
    elif more:
        note = (f"Showing rows {offset + 1}-{nxt} (more available). Pass offset={nxt} for the next "
                f"page, or narrow with a cut / fewer drilldowns.")
    else:
        note = f"{n} rows (complete)."
    return {
        "resolved": resolved, "offset": offset, "returned": n, "row_count": n,
        "more": more, "complete": complete, "data": to_compact(rows), "note": note,
    }


def build_catalog_result(query, scope, matches, offset, cap, catalog_size):
    """R21: honest catalog-search envelope, mirroring build_result. Fixes the
    'silent truncation' class (the model must never infer a cap from len(results)).
    `matches` is the FULL match set from catalog.search; we slice [offset:offset+cap]
    and report total_matches / complete so the model always knows what it has."""
    total = len(matches)
    page = matches[offset:offset + cap]
    complete = offset + len(page) >= total
    if complete and offset == 0:
        note = (f"{total} of {total} matches (complete). {catalog_size} cubes total in the "
                f"catalog. Refine the query to narrow.")
    elif complete:
        note = (f"Showing matches {offset + 1}-{offset + len(page)} of {total} (end of results). "
                f"{catalog_size} cubes total in the catalog.")
    else:
        nxt = offset + len(page)
        note = (f"Showing {offset + 1}-{nxt} of {total} matches (more available). Refine the query "
                f"to narrow, or pass offset={nxt} to page through the rest. "
                f"Do NOT infer a cap from the result length - read total_matches and complete. "
                f"{catalog_size} cubes total in the catalog.")
    return {
        "query": query, "scope": scope,
        "total_matches": total, "returned": len(page), "catalog_size": catalog_size,
        "complete": complete, "results": page, "note": note,
    }


def steer_for(kind: str) -> str:
    """R5/R15/R20: the recovery advice DIFFERS by failure type (verified Probe 5).
    - oversize/timeout: adding a cut rescues huge-but-valid queries (~75x smaller).
    - server500: a cut does NOT help; only reducing the number of drilldowns does."""
    if kind in ("oversize", "timeout"):
        return ("Query too broad. Add a cut to one dimension (e.g. one country/province), "
                "or request a lower-dimensional projection, or page with offset. If you need "
                "the whole picture, run it once per value and combine yourself - but only "
                "combine additive measures (counts/sums), never an index, average, or ratio.")
    if kind == "server500":
        return ("That many drilldowns overwhelmed the server (it returned HTTP 500). "
                "Reduce the number of drilldowns - a cut does NOT help here; drop a dimension.")
    return "Query could not be completed; narrow it and retry."


def steer_result(cube, drilldowns, measures, cut, kind: str) -> dict:
    """R15/R20: build the empty-result-with-steer envelope once (DRY), shared by
    query_cube's failure branches. Same envelope shape as build_result (R6b/R16)."""
    return {
        "resolved": {"cube": cube, "drilldowns": drilldowns, "measures": measures, "cut": cut},
        "row_count": 0,
        "data": {"columns": [], "rows": []},
        "note": steer_for(kind),
    }
