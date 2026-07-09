from datasaudi_mcp.errors import DataSaudiError, DataSaudiServerError, ValidationError


def test_error_hierarchy():
    # DataSaudiServerError is a DataSaudiError so callers catching the base still catch 500s
    assert issubclass(DataSaudiServerError, DataSaudiError)
    # ValidationError is a ValueError (semantically a bad-argument error)
    assert issubclass(ValidationError, ValueError)


def test_errors_carry_message():
    err = ValidationError("no measure 'GDP'; valid: Real GDP, Nominal GDP")
    assert "valid: Real GDP" in str(err)
