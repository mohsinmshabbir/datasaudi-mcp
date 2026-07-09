from datasaudi_mcp.shaping import build_result, steer_for, to_compact


def test_to_compact_columnar_shape():
    # R16: columnar {columns, rows} - keys named once, not per row (token economy)
    rows = [
        {"Province": "Al-Riyadh", "Price Index": 74.4},
        {"Province": "Makkah", "Price Index": 72.2},
    ]
    out = to_compact(rows)
    assert out == {
        "columns": ["Province", "Price Index"],
        "rows": [["Al-Riyadh", 74.4], ["Makkah", 72.2]],
    }


def test_to_compact_stable_columns_when_row_missing_a_key():
    # R16: shape is stable - a row missing a column gets None, columns never shrink
    rows = [{"Province": "Al-Riyadh", "Growth": 1.2}, {"Province": "Makkah"}]
    out = to_compact(rows)
    assert out["columns"] == ["Province", "Growth"]
    assert out["rows"] == [["Al-Riyadh", 1.2], ["Makkah", None]]


def test_to_compact_tolerates_null_member():
    # R9/R17: dirty member IDs (None) and Arabic captions must not crash and survive intact
    rows = [{"Country ID": None, "Country": "", "Value": 5},
            {"Country ID": "sau", "Country": "الرياض", "Value": 9}]
    out = to_compact(rows)
    assert out["rows"][0] == [None, "", 5]
    assert out["rows"][1][1] == "الرياض"  # Arabic survives


def test_to_compact_empty():
    assert to_compact([]) == {"columns": [], "rows": []}


def test_to_compact_backfills_new_column_from_later_row():
    # R16 stability: a LATER row introducing a new column backfills earlier rows with None
    out = to_compact([{"a": 1}, {"a": 2, "b": 99}])
    assert out["columns"] == ["a", "b"]
    assert out["rows"] == [[1, None], [2, 99]]


def test_build_result_echoes_query_and_row_count():
    # R6b: the result carries its own resolved query + count so the model can trust it
    out = build_result(
        cube="gastat_real_estate", drilldowns=["Province"], measures=["Price Index"],
        cut=None, rows=[{"Province": "Al-Riyadh", "Price Index": 74.4}], more=False,
    )
    assert out["resolved"] == {
        "cube": "gastat_real_estate", "drilldowns": ["Province"],
        "measures": ["Price Index"], "cut": None,
    }
    assert out["row_count"] == 1
    assert out["data"]["columns"] == ["Province", "Price Index"]


def test_build_result_empty_is_explicit_not_ambiguous():
    # R6b: empty must say "valid, no data" so the model does not hallucinate over []
    out = build_result("c", ["Province"], ["Price Index"], None, [], more=False)
    assert out["row_count"] == 0
    assert "no matching data" in out["note"].lower()


def test_build_result_more_appends_steer():
    # R5: truncated page appends a steer to narrow
    out = build_result("c", ["Province"], ["Price Index"], None,
                       [{"Province": "x", "Price Index": 1}], more=True)
    assert "narrow" in out["note"].lower() or "cut" in out["note"].lower()


def test_build_result_reports_window():
    # R22: the envelope reports offset/returned/more/complete so the model can page
    rows = [{"i": n} for n in range(10)]
    out = build_result("c", ["Province"], ["m"], None, rows, more=True, offset=20)
    assert out["offset"] == 20
    assert out["returned"] == 10
    assert out["more"] is True
    assert out["complete"] is False
    assert "offset=30" in out["note"]      # next page = offset + returned


def test_build_result_clamped_page_leads_with_cap_fact():
    # R22: when the caller's limit was clamped, the note leads with the cap + how to page
    rows = [{"i": n} for n in range(5000)]
    out = build_result("c", ["Province"], ["m"], None, rows, more=True, offset=0, clamped=True)
    note = out["note"].lower()
    assert "cap" in note
    assert "offset=5000" in note
    assert "additive" in note              # the marginals/combine warning is carried


def test_build_result_complete_flag():
    out = build_result("c", ["Province"], ["m"], None, [{"i": 1}], more=False)
    assert out["complete"] is True
    assert out["more"] is False


def test_build_result_byte_budget_trims_oversized_payload():
    # R22: cap on BYTES, not rows. A payload over the byte budget is trimmed and
    # flagged more=True - correct across cube width and locale (Arabic is multi-byte).
    import json as _json
    from datasaudi_mcp.shaping import _MAX_RESULT_BYTES
    # fat rows: each ~1KB; 2000 of them (~2MB) must be trimmed under the budget
    rows = [{"a": "x" * 500, "b": "y" * 500, "i": n} for n in range(2000)]
    out = build_result("c", ["a", "b"], ["m"], None, rows, more=False)
    size = len(_json.dumps(out["data"]).encode("utf-8"))
    assert size <= _MAX_RESULT_BYTES        # fits the byte budget
    assert out["returned"] < 2000           # rows were dropped
    assert out["more"] is True              # trimming means more exist
    assert out["complete"] is False


def test_build_result_byte_budget_leaves_small_results_untouched():
    # a small payload is not trimmed and stays complete
    rows = [{"Province": "Al-Riyadh", "Price Index": 74.4}]
    out = build_result("c", ["Province"], ["m"], None, rows, more=False)
    assert out["returned"] == 1
    assert out["complete"] is True


def test_build_result_single_oversized_row_is_not_reported_as_no_data():
    # BUG: when ONE row alone exceeds the byte budget, every row is dropped and the
    # envelope wrongly said both more=True AND "no matching data" - hiding that data
    # existed but was too big. The note must say the row was too large, not "no data".
    from datasaudi_mcp.shaping import _MAX_RESULT_BYTES
    huge = "z" * (_MAX_RESULT_BYTES + 50_000)      # one row bigger than the whole budget
    rows = [{"blob": huge}]
    out = build_result("c", ["x"], ["m"], None, rows, more=False)
    assert out["returned"] == 0                    # nothing could fit
    note = out["note"].lower()
    assert "no matching data" not in note          # must NOT claim the query was empty
    assert "size" in note or "too large" in note or "budget" in note  # explains why
    # and it must not simultaneously claim more-available: nothing here is pageable
    assert out["complete"] is True or "size" in note


def test_steer_oversize_says_add_a_cut():
    # R15/Probe5: huge-but-valid -> a cut rescues it (measured 75x)
    s = steer_for("oversize")
    assert "cut" in s.lower()


def test_steer_timeout_says_add_a_cut():
    s = steer_for("timeout")
    assert "cut" in s.lower()


def test_steer_server500_says_drop_a_drilldown_not_cut():
    # R20: a cut does NOT rescue a 500; only dropping a drilldown does
    s = steer_for("server500").lower()
    assert "drilldown" in s
    assert "drop" in s or "reduce" in s or "fewer" in s


def test_steer_result_envelope_shape():
    # DRY helper: same envelope as build_result (resolved/row_count/data/note)
    from datasaudi_mcp.shaping import steer_result
    out = steer_result("c", ["Month", "Country", "HS2"], ["v"], None, "server500")
    assert out["row_count"] == 0
    assert out["data"] == {"columns": [], "rows": []}
    assert out["resolved"]["drilldowns"] == ["Month", "Country", "HS2"]
    assert "drilldown" in out["note"].lower()


def test_build_catalog_result_complete_set():
    # R21: a match set smaller than the cap comes back complete, with the true count
    from datasaudi_mcp.shaping import build_catalog_result
    matches = [{"name": f"c{i}", "caption": f"c{i}", "domain": "d"} for i in range(163)]
    out = build_catalog_result("gastat", "catalog", matches, offset=0, cap=250, catalog_size=277)
    assert out["total_matches"] == 163
    assert out["returned"] == 163
    assert out["catalog_size"] == 277
    assert out["complete"] is True
    assert "163" in out["note"] and "277" in out["note"]


def test_build_catalog_result_truncated_preview_steers():
    # R21: a capped result is labeled incomplete + steers to refine/offset (never silent)
    from datasaudi_mcp.shaping import build_catalog_result
    matches = [{"name": f"c{i}", "caption": f"c{i}", "domain": "d"} for i in range(277)]
    out = build_catalog_result("", "catalog", matches, offset=0, cap=25, catalog_size=277)
    assert out["returned"] == 25
    assert out["total_matches"] == 277
    assert out["complete"] is False
    assert "offset=25" in out["note"]      # tells the model how to page
    assert "do not infer a cap" in out["note"].lower()


def test_build_catalog_result_last_page_is_complete():
    from datasaudi_mcp.shaping import build_catalog_result
    matches = [{"name": f"c{i}", "caption": f"c{i}", "domain": "d"} for i in range(30)]
    out = build_catalog_result("", "catalog", matches, offset=25, cap=25, catalog_size=277)
    assert out["returned"] == 5
    assert out["complete"] is True          # offset+returned >= total
