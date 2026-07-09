import pytest

from datasaudi_mcp.errors import DataSaudiError


def test_catalog_indexes_all_277_cubes(catalog):
    # R12: catalog cached + indexed by name
    assert len(catalog.names()) == 277
    assert "gastat_real_estate" in catalog.names()


def test_levels_of_returns_all_levels_not_just_leaf(catalog):
    # R7: every drillable level, across all hierarchies (Nation AND Province, Year AND Quarter)
    levels = catalog.levels_of("gastat_real_estate")
    assert set(levels) == {"Nation", "Province", "Year", "Quarter"}


def test_measures_of(catalog):
    assert catalog.measures_of("gastat_real_estate") == ["Price Index", "Growth"]


def test_get_unknown_cube_raises(catalog):
    with pytest.raises(DataSaudiError):
        catalog.get("gastat_does_not_exist")


def test_search_catalog_returns_compact_hits(catalog):
    # R10: compact {name, caption, domain}, never the raw cube tree
    hits = catalog.search("real", scope="catalog")
    assert any(h["name"] == "gastat_real_estate" for h in hits)
    hit = next(h for h in hits if h["name"] == "gastat_real_estate")
    assert set(hit.keys()) == {"name", "caption", "domain"}
    assert "dimensions" not in hit  # not the fat tree


def test_search_scope_measures_looks_inside_cube(catalog):
    # R11: scope='measures' searches measure names across cubes
    hits = catalog.search("Price Index", scope="measures")
    assert any(h["name"] == "gastat_real_estate" for h in hits)


def test_search_scope_levels_searches_level_names(catalog):
    # scope='levels' searches drillable LEVEL names (Province is a level of real_estate)
    hits = catalog.search("Province", scope="levels")
    assert any(h["name"] == "gastat_real_estate" for h in hits)


def test_search_scope_members_alias_equals_levels(catalog):
    # 'members' is kept as a backward-compatible alias for 'levels'
    assert catalog.search("Province", scope="members") == catalog.search("Province", scope="levels")


def test_search_locale_ar_matches_arabic_annotations(catalog):
    # locale='ar' searches the Arabic catalog annotations (topic_ar etc.) which the
    # /cubes payload carries; "المؤشرات الاجتماعية" is real_estate's topic_ar.
    ar_hits = catalog.search("المؤشرات الاجتماعية", scope="catalog", locale="ar")
    en_hits = catalog.search("المؤشرات الاجتماعية", scope="catalog", locale="en")
    assert any(h["name"] == "gastat_real_estate" for h in ar_hits)  # found via Arabic
    assert en_hits == []  # the same Arabic term finds nothing in the English fields


def test_did_you_mean_suggests_near_match(catalog):
    # R8: a misspelling gets the real cube suggested
    suggestions = catalog.did_you_mean("gastat_realestate")  # missing underscore
    assert "gastat_real_estate" in suggestions


def test_has_level(catalog):
    assert catalog.has_level("gastat_real_estate", "Province") is True
    assert catalog.has_level("gastat_real_estate", "Banana") is False
