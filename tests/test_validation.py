import pytest
from datasaudi_mcp.validation import normalize, validate_drilldowns, validate_measures
from datasaudi_mcp.errors import ValidationError


def test_normalize_strips_whitespace():
    # R3: ' Province ' must become 'Province' deterministically (do not rely on server trim)
    assert normalize([" Province ", "Quarter"]) == ["Province", "Quarter"]


def test_normalize_drops_empty_after_strip():
    assert normalize(["  ", "Province", ""]) == ["Province"]


REAL_ESTATE_LEVELS = ["Nation", "Province", "Year", "Quarter"]


def test_validate_drilldowns_accepts_valid():
    assert validate_drilldowns(["Province", "Quarter"], REAL_ESTATE_LEVELS) == ["Province", "Quarter"]


def test_validate_drilldowns_rejects_dimension_name_with_valid_list():
    # R2: drilling on the DIMENSION 'Date Quarter' (a level does not exist) fails loud + lists valids
    with pytest.raises(ValidationError) as exc:
        validate_drilldowns(["Date Quarter"], REAL_ESTATE_LEVELS)
    msg = str(exc.value)
    assert "Date Quarter" in msg
    assert "Quarter" in msg  # the valid options are named


def test_validate_drilldowns_rejects_empty_after_normalize():
    # R6: at least one drilldown is required
    with pytest.raises(ValidationError):
        validate_drilldowns(["   "], REAL_ESTATE_LEVELS)


def test_validate_drilldowns_one_bad_in_mix_fails_whole():
    # Even one bad level poisons the query; catch it locally
    with pytest.raises(ValidationError) as exc:
        validate_drilldowns(["Province", "Banana"], REAL_ESTATE_LEVELS)
    assert "Banana" in str(exc.value)


REAL_ESTATE_MEASURES = ["Price Index", "Growth"]


def test_validate_measures_accepts_valid():
    assert validate_measures(["Price Index"], REAL_ESTATE_MEASURES) == ["Price Index"]


def test_validate_measures_rejects_bad_measure_the_server_would_silently_drop():
    # R1 / Probe D: the API returns 200 and silently drops 'Fake'. We must catch it.
    with pytest.raises(ValidationError) as exc:
        validate_measures(["Price Index", "Fake"], REAL_ESTATE_MEASURES)
    msg = str(exc.value)
    assert "Fake" in msg
    assert "Price Index" in msg  # valid options named for self-correction


def test_validate_measures_empty_is_allowed():
    # Probe E: a no-measures query is legal (returns dimension members). Empty is OK here.
    assert validate_measures([], REAL_ESTATE_MEASURES) == []


# --- two coverage tests carried over from the Task 3 review (drilldowns) ---

def test_validate_drilldowns_returns_normalized_for_padded_valid_input():
    # confirms the RETURN value reflects normalization (not just echoing clean input)
    assert validate_drilldowns([" Province "], REAL_ESTATE_LEVELS) == ["Province"]


def test_validate_drilldowns_is_case_sensitive():
    # Probe H: 'province' lowercase must fail against the real level 'Province'
    with pytest.raises(ValidationError):
        validate_drilldowns(["province"], REAL_ESTATE_LEVELS)
