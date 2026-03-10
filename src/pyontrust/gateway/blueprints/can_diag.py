"""CAN Diagnostic blueprint — live CAN bus monitoring, CANopen, reverse-engineering.

Mounts at ``/can/`` and provides:

- ``GET  /can/``                       → CAN diagnostic SPA
- ``POST /can/api/start``              → start CAN capture (interface, channel, bitrate)
- ``POST /can/api/stop``               → stop CAN capture
- ``GET  /can/api/snapshot``           → get current traffic + stats
- ``GET  /can/api/stats``              → per-ID statistics table
- ``POST /can/api/send``               → send a CAN frame
- ``POST /can/api/filter``             → set ID filters
- ``GET  /can/api/analyze/<id>``       → deep RE analysis of a message ID
- ``GET  /can/api/dbc``                → generate DBC file stub
- ``GET  /can/api/export/<fmt>``       → export log as ASC/CSV/BLF
- ``GET  /can/api/stream``             → SSE live traffic stream
- ``POST /can/api/clear``              → clear all data
- ``GET  /can/api/status``             → connection status
"""
from __future__ import annotations

import json
import pathlib
import time

from flask import Blueprint, Response, jsonify, request, send_from_directory

_WEB_DIR = pathlib.Path(__file__).resolve().parent.parent / "web" / "can"

bp = Blueprint(
    "can_diag",
    __name__,
    static_folder=str(_WEB_DIR),
    static_url_path="/static",
)

# Lazy singleton — created on first use
_service = None


def _get_service():
    global _service
    if _service is None:
        from pyontrust.services.can_service import CanDiagService
        _service = CanDiagService()
    return _service


# ── Pages ────────────────────────────────────────────────────────────

@bp.route("/")
def index():
    return send_from_directory(str(_WEB_DIR), "index.html")


# ── Connection management ────────────────────────────────────────────

@bp.route("/api/start", methods=["POST"])
def start_capture():
    """Start CAN bus capture.

    JSON body::

        {"interface": "pcan", "channel": "PCAN_USBBUS1",
         "bitrate": 500000, "fd": false}
    """
    svc = _get_service()
    body = request.get_json(silent=True) or {}
    result = svc.start(
        interface=body.get("interface", "pcan"),
        channel=body.get("channel", "PCAN_USBBUS1"),
        bitrate=int(body.get("bitrate", 500000)),
        fd=bool(body.get("fd", False)),
    )
    return jsonify(result)


@bp.route("/api/stop", methods=["POST"])
def stop_capture():
    """Stop CAN bus capture."""
    return jsonify(_get_service().stop())


@bp.route("/api/clear", methods=["POST"])
def clear_data():
    """Clear all captured data."""
    _get_service().clear()
    return jsonify({"ok": True})


@bp.route("/api/status")
def status():
    """Connection status."""
    svc = _get_service()
    return jsonify({
        "running": svc.is_running,
        "interface": svc._interface,
        "channel": svc._channel,
        "bitrate": svc._bitrate,
        "total_frames": svc._total_frames,
        "error_count": svc._error_count,
    })


# ── Data queries ─────────────────────────────────────────────────────

@bp.route("/api/snapshot")
def snapshot():
    """Get current traffic snapshot."""
    last_n = int(request.args.get("n", 200))
    return jsonify(_get_service().get_snapshot(last_n=last_n))


@bp.route("/api/stats")
def stats_table():
    """Get per-ID statistics table."""
    return jsonify({"stats": _get_service().get_stats_table()})


# ── Send ─────────────────────────────────────────────────────────────

@bp.route("/api/send", methods=["POST"])
def send_frame():
    """Send a CAN frame.

    JSON body::

        {"arb_id": "0x123", "data": "01 02 03 04", "extended": false}
    """
    body = request.get_json(silent=True) or {}
    arb_id_str = str(body.get("arb_id", "0"))
    arb_id = int(arb_id_str, 16) if arb_id_str.startswith("0x") else int(arb_id_str)
    data_str = str(body.get("data", "")).strip()
    data = bytes.fromhex(data_str.replace(" ", "")) if data_str else b""
    extended = bool(body.get("extended", False))
    return jsonify(_get_service().send_frame(arb_id, data, extended))


# ── Filters ──────────────────────────────────────────────────────────

@bp.route("/api/filter", methods=["POST"])
def set_filter():
    """Set capture filter.

    JSON body (one of)::

        {"ids": [0x100, 0x200, 0x300]}        # specific IDs
        {"id": "0x600", "mask": "0x7F0"}       # mask filter
        {"clear": true}                        # clear all filters
    """
    svc = _get_service()
    body = request.get_json(silent=True) or {}

    if body.get("clear"):
        svc.clear_filters()
        return jsonify({"ok": True, "filter": "none"})

    ids = body.get("ids")
    if ids:
        parsed = []
        for v in ids:
            parsed.append(int(str(v), 16) if str(v).startswith("0x") else int(v))
        svc.set_id_filter(parsed)
        return jsonify({"ok": True, "filter": "id_list", "count": len(parsed)})

    fid = body.get("id")
    fmask = body.get("mask")
    if fid is not None and fmask is not None:
        fid_int = int(str(fid), 16) if str(fid).startswith("0x") else int(fid)
        fmask_int = int(str(fmask), 16) if str(fmask).startswith("0x") else int(fmask)
        svc.set_mask_filter(fid_int, fmask_int)
        return jsonify({"ok": True, "filter": "mask",
                        "id": f"0x{fid_int:03X}", "mask": f"0x{fmask_int:03X}"})

    return jsonify({"ok": False, "error": "Provide ids, id+mask, or clear"})


# ── Reverse-engineering ──────────────────────────────────────────────

@bp.route("/api/analyze/<arb_id_str>")
def analyze_message(arb_id_str: str):
    """Deep analysis of a single message ID."""
    arb_id = int(arb_id_str, 16) if arb_id_str.startswith("0x") else int(arb_id_str)
    return jsonify(_get_service().analyze_message(arb_id))


@bp.route("/api/dbc")
def generate_dbc():
    """Generate DBC file stub from observed traffic."""
    dbc_text = _get_service().generate_dbc()
    if request.args.get("download"):
        return Response(dbc_text, mimetype="application/octet-stream",
                        headers={"Content-Disposition": "attachment; filename=observed.dbc"})
    return jsonify({"dbc": dbc_text})


# ── Export ───────────────────────────────────────────────────────────

@bp.route("/api/export/<fmt>")
def export_log(fmt: str):
    """Export captured log. Formats: asc, csv, blf."""
    svc = _get_service()
    if fmt == "blf":
        try:
            data = svc.export_blf()
            return Response(data, mimetype="application/octet-stream",
                            headers={"Content-Disposition": "attachment; filename=capture.blf"})
        except RuntimeError as exc:
            return jsonify({"error": str(exc)}), 500

    text = svc.export_log(fmt=fmt)
    if request.args.get("download"):
        ext = "asc" if fmt == "asc" else "csv"
        return Response(text, mimetype="text/plain",
                        headers={"Content-Disposition": f"attachment; filename=capture.{ext}"})
    return Response(text, mimetype="text/plain")


# ── SSE live stream ──────────────────────────────────────────────────

@bp.route("/api/stream")
def live_stream():
    """Server-Sent Events stream of live CAN traffic."""
    def generate():
        svc = _get_service()
        last_count = svc._total_frames
        while True:
            time.sleep(0.1)  # 10 Hz update rate
            if not svc.is_running:
                yield f"data: {json.dumps({'event': 'stopped'})}\n\n"
                break
            current = svc._total_frames
            if current == last_count:
                continue
            snap = svc.get_snapshot(last_n=50)
            snap["event"] = "update"
            yield f"data: {json.dumps(snap, default=str)}\n\n"
            last_count = current

    return Response(generate(), mimetype="text/event-stream",
                    headers={"Cache-Control": "no-cache",
                             "X-Accel-Buffering": "no"})
