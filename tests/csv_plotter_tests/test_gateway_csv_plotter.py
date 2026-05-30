from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
from flask import Flask


REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_DIR = REPO_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))


from pyontrust.gateway.blueprints import csv_plotter as csv_plotter_bp  # noqa: E402


def _reset_state() -> None:
    csv_plotter_bp._state.clear()
    csv_plotter_bp._state.update(
        {
            "file_path": None,
            "folder_path": None,
            "df": None,
            "columns": [],
            "rows": 0,
            "separator": None,
            "timestamp_scale": 1.0,
            "mtime": None,
            "history": [],
            "history_index": -1,
            "layout": {},
            "subplots": [],
            "active_subplot_id": None,
            "next_subplot_id": 1,
        }
    )
    csv_plotter_bp._state["subplots"] = [csv_plotter_bp._new_subplot()]
    csv_plotter_bp._state["active_subplot_id"] = "subplot-1"


def _make_client(tmp_path: Path):
    _reset_state()
    csv_plotter_bp._LAYOUT_PATH = tmp_path / "layout.json"
    app = Flask(__name__)
    app.register_blueprint(csv_plotter_bp.bp, url_prefix="/csv")
    return app.test_client()


def test_gateway_load_patch_render_and_export(tmp_path: Path) -> None:
    client = _make_client(tmp_path)

    df = pd.DataFrame(
        {
            "Timestamp": [0.0, 0.5, 1.0, 1.5],
            "A": [1.0, 2.0, 3.0, 4.0],
            "B": [4.0, 3.0, 2.0, 1.0],
        }
    )
    csv_path = tmp_path / "demo.csv"
    df.to_csv(csv_path, index=False)

    load_response = client.post("/csv/api/csv/load", json={"path": str(csv_path)})
    assert load_response.status_code == 200
    assert load_response.get_json()["rows"] == 4

    state_response = client.get("/csv/api/app-state")
    state_payload = state_response.get_json()
    subplot_id = state_payload["active_subplot_id"]
    assert subplot_id == "subplot-1"
    assert "A" in state_payload["columns"]

    patch_response = client.patch(
        f"/csv/api/subplots/{subplot_id}",
        json={
            "mode": "Histogram",
            "selected_columns": ["A"],
            "histogram_bins": 6,
            "title": "Histogram view",
        },
    )
    assert patch_response.status_code == 200
    assert patch_response.get_json()["subplot"]["mode"] == "Histogram"

    panel_response = client.get(f"/csv/api/subplots/{subplot_id}/panel")
    panel_payload = panel_response.get_json()["payload"]
    assert panel_payload["kind"] == "histogram"
    assert panel_payload["series"]

    render_response = client.get(f"/csv/api/subplots/{subplot_id}/render?fmt=png")
    assert render_response.status_code == 200
    assert render_response.mimetype == "image/png"
    assert len(render_response.data) > 100

    export_response = client.post(
        f"/csv/api/subplots/{subplot_id}/export-data",
        json={"format": "json"},
    )
    assert export_response.status_code == 200
    assert export_response.mimetype == "application/json"
    assert b'"A"' in export_response.data


def test_gateway_layout_and_combined_export(tmp_path: Path) -> None:
    client = _make_client(tmp_path)

    df = pd.DataFrame(
        {
            "Timestamp": [0.0, 1.0, 2.0],
            "A": [0.0, 1.0, 0.0],
        }
    )
    csv_path = tmp_path / "demo.csv"
    df.to_csv(csv_path, index=False)
    client.post("/csv/api/csv/load", json={"path": str(csv_path)})

    create_response = client.post("/csv/api/subplots", json={"mode": "Statistics"})
    assert create_response.status_code == 200

    layout_response = client.post(
        "/csv/api/layout",
        json={
            "subplots": client.get("/csv/api/subplots").get_json()["subplots"],
            "active_subplot_id": client.get("/csv/api/subplots").get_json()["active_subplot_id"],
        },
    )
    assert layout_response.status_code == 200

    combined_response = client.post("/csv/api/export/combined", json={"format": "png"})
    assert combined_response.status_code == 200
    assert combined_response.mimetype == "image/png"
    assert len(combined_response.data) > 100
