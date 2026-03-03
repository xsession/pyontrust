"""
Zephyr Pin Configurator – Flask backend.

Serves the web UI and provides REST endpoints for:
  GET  /api/boards              – list available boards
  GET  /api/board/<name>        – full board definition (pins, peripherals)
  POST /api/generate            – generate DTS overlay + prj.conf from state
  POST /api/save-project        – save the pin config state to a project dir
"""

from __future__ import annotations

import json
import os
import pathlib
import sys

from flask import Flask, jsonify, request, send_from_directory

# Ensure package is importable when run directly
_HERE = pathlib.Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

from board_schema import board_to_frontend
from boards import BOARDS
from dts_generator import PinAssignment, PeripheralConfig, generate


app = Flask(
    __name__,
    static_folder=str(_HERE / "web"),
    static_url_path="",
)

# ── Board registry ────────────────────────────────────────────────────

_BOARD_CACHE: dict = {}


def _get_board(name: str):
    if name not in _BOARD_CACHE:
        builder = BOARDS.get(name)
        if builder is None:
            return None
        _BOARD_CACHE[name] = builder()
    return _BOARD_CACHE[name]


# ── Routes ────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return send_from_directory(app.static_folder, "index.html")


@app.route("/api/boards")
def list_boards():
    return jsonify([
        {"id": k, "name": _get_board(k).soc, "board": _get_board(k).board}
        for k in BOARDS
    ])


@app.route("/api/board/<name>")
def get_board(name: str):
    brd = _get_board(name)
    if brd is None:
        return jsonify({"error": f"Board '{name}' not found"}), 404
    return jsonify(board_to_frontend(brd))


@app.route("/api/generate", methods=["POST"])
def generate_overlay():
    """
    Expects JSON body:
    {
      "board": "mspm0g3507",
      "assignments": [ { pin_name, pincm, function_id, af_name,
                          peripheral, signal, direction,
                          bias_pull_up, bias_pull_down,
                          drive_open_drain, input_enable } ... ],
      "peripherals": [ { name, dts_node, compatible, enabled } ... ]
    }
    """
    body = request.get_json(force=True)

    assignments = [
        PinAssignment(
            pin_name=a["pin_name"],
            pincm=a["pincm"],
            function_id=a["function_id"],
            af_name=a.get("af_name", ""),
            peripheral=a["peripheral"],
            signal=a["signal"],
            direction=a.get("direction", "io"),
            bias_pull_up=a.get("bias_pull_up", False),
            bias_pull_down=a.get("bias_pull_down", False),
            drive_open_drain=a.get("drive_open_drain", False),
            input_enable=a.get("input_enable", False),
        )
        for a in body.get("assignments", [])
    ]

    periphs = [
        PeripheralConfig(
            name=p["name"],
            dts_node=p.get("dts_node", ""),
            compatible=p.get("compatible", ""),
            enabled=p.get("enabled", False),
        )
        for p in body.get("peripherals", [])
    ]

    result = generate(assignments, periphs, board_name=body.get("board", "custom"))

    return jsonify({
        "overlay": result.overlay,
        "prj_conf": result.prj_conf,
    })


@app.route("/api/save-project", methods=["POST"])
def save_project():
    """
    Write generated files directly into a Zephyr project directory.

    Body:
    {
      "project_path": "C:/path/to/app",
      "overlay": "...",
      "prj_conf": "...",
      "board": "mspm0g3507"
    }
    """
    body = request.get_json(force=True)
    project = pathlib.Path(body["project_path"])

    if not project.is_dir():
        return jsonify({"error": f"Directory does not exist: {project}"}), 400

    board = body.get("board", "custom_board")

    overlay_path = project / f"{board}.overlay"
    conf_path = project / "prj.conf"

    overlay_path.write_text(body["overlay"], encoding="utf-8")

    # Merge into existing prj.conf if present
    existing = ""
    if conf_path.exists():
        existing = conf_path.read_text(encoding="utf-8")
    
    new_lines = body["prj_conf"].strip().split("\n")
    for line in new_lines:
        line = line.strip()
        if line and not line.startswith("#"):
            key = line.split("=")[0]
            if key not in existing:
                existing += "\n" + line
    
    conf_path.write_text(existing.strip() + "\n", encoding="utf-8")

    return jsonify({
        "saved": True,
        "overlay_path": str(overlay_path),
        "conf_path": str(conf_path),
    })


# ── Entry point ──────────────────────────────────────────────────────

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Zephyr Pin Configurator")
    parser.add_argument("--port", type=int, default=5100)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--debug", action="store_true")
    args = parser.parse_args()

    print(f"\n  Zephyr Pin Configurator")
    print(f"  http://{args.host}:{args.port}\n")
    app.run(host=args.host, port=args.port, debug=args.debug)


if __name__ == "__main__":
    main()
