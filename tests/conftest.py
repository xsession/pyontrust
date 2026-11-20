"""Suite-wide isolation: never touch the real station data while testing.

The gateway records every action (audit trail) and run (run registry) under
``PYONTRUST_DATA_DIR`` (default ``~/.pyontrust``).  Point it — and the other
station files — at a per-test temporary directory.
"""
from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _isolated_station_data(tmp_path, monkeypatch):
    data = tmp_path / "station-data"
    monkeypatch.setenv("PYONTRUST_DATA_DIR", str(data))
    monkeypatch.setenv("PYONTRUST_THERMAL_REGIONS", str(data / "thermal_regions.json"))
    monkeypatch.setenv("PYONTRUST_THERMAL_CAL_FILE", str(data / "thermal_calibration.json"))
    yield data
