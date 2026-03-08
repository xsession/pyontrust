"""Artifacts blueprint — browse, download, and manage test artifacts.

Mounts at ``/artifacts/`` and provides:

- ``GET  /artifacts/``                      → artifact browser SPA
- ``GET  /artifacts/api/list``              → list artifact entries
- ``GET  /artifacts/api/<run_id>``          → single entry detail
- ``GET  /artifacts/api/<run_id>/files``    → file listing
- ``GET  /artifacts/api/<run_id>/file/<name>`` → download file
- ``POST /artifacts/api/scan``              → re-index artifacts
- ``DELETE /artifacts/api/<run_id>``        → delete a run
"""
from __future__ import annotations

import pathlib

from flask import Blueprint, Response, current_app, jsonify, request, send_from_directory

_WEB_DIR = pathlib.Path(__file__).resolve().parent.parent / "web" / "artifacts"

bp = Blueprint(
    "artifacts",
    __name__,
    static_folder=str(_WEB_DIR),
    static_url_path="/artifacts/static",
)


@bp.route("/")
def index():
    return send_from_directory(str(_WEB_DIR), "index.html")


@bp.route("/api/list")
def list_artifacts():
    svc = current_app.extensions.get("artifact_service")
    if svc is None:
        return jsonify({"error": "Artifact service not available"}), 503
    limit = request.args.get("limit", 100, type=int)
    name_filter = request.args.get("q")
    return jsonify(svc.list_entries(limit=limit, name_filter=name_filter))


@bp.route("/api/scan", methods=["POST"])
def scan():
    svc = current_app.extensions.get("artifact_service")
    if svc is None:
        return jsonify({"error": "Artifact service not available"}), 503
    entries = svc.scan()
    return jsonify({"count": len(entries)})


@bp.route("/api/<run_id>")
def get_artifact(run_id: str):
    svc = current_app.extensions.get("artifact_service")
    if svc is None:
        return jsonify({"error": "Artifact service not available"}), 503
    entry = svc.get(run_id)
    if entry is None:
        return jsonify({"error": "Not found"}), 404
    return jsonify({
        "run_id": entry.run_id,
        "test_name": entry.test_name,
        "created": entry.created,
        "has_trace": entry.has_trace,
        "has_summary": entry.has_summary,
        "has_report": entry.has_report,
        "has_verdict": entry.has_verdict,
        "meta": entry.meta,
    })


@bp.route("/api/<run_id>/files")
def list_files(run_id: str):
    svc = current_app.extensions.get("artifact_service")
    if svc is None:
        return jsonify({"error": "Artifact service not available"}), 503
    return jsonify(svc.list_files(run_id))


@bp.route("/api/<run_id>/file/<path:filename>")
def download_file(run_id: str, filename: str):
    svc = current_app.extensions.get("artifact_service")
    if svc is None:
        return jsonify({"error": "Artifact service not available"}), 503

    # Determine content type
    ext = pathlib.Path(filename).suffix.lower()
    mime_map = {
        ".json": "application/json",
        ".csv": "text/csv",
        ".md": "text/markdown",
        ".txt": "text/plain",
        ".png": "image/png",
        ".svg": "image/svg+xml",
        ".html": "text/html",
    }
    mime = mime_map.get(ext, "application/octet-stream")

    if mime.startswith("text") or ext in (".json", ".csv", ".md"):
        content = svc.read_file(run_id, filename)
        if content is None:
            return jsonify({"error": "File not found"}), 404
        return Response(content, mimetype=mime)
    else:
        data = svc.read_binary(run_id, filename)
        if data is None:
            return jsonify({"error": "File not found"}), 404
        return Response(data, mimetype=mime)


@bp.route("/api/<run_id>", methods=["DELETE"])
def delete_artifact(run_id: str):
    svc = current_app.extensions.get("artifact_service")
    if svc is None:
        return jsonify({"error": "Artifact service not available"}), 503
    ok = svc.delete(run_id)
    return jsonify({"deleted": ok})
