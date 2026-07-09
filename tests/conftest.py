import json
from pathlib import Path

import pytest

FIXTURE = Path(__file__).parent / "fixtures" / "cubes.json"


def pytest_configure(config):
    config.addinivalue_line("markers", "live: hits the real api.datasaudi.sa (opt-in, needs network)")


@pytest.fixture(scope="session")
def raw_cubes() -> list[dict]:
    with open(FIXTURE, encoding="utf-8") as f:
        return json.load(f)["cubes"]


@pytest.fixture()
def catalog(raw_cubes):
    from datasaudi_mcp.catalog import Catalog
    return Catalog.from_cubes(raw_cubes)
