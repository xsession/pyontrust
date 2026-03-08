"""Cross-cutting middleware — CORS, error handlers, request logging."""
from __future__ import annotations

import logging
import time
from typing import Any

from flask import Flask, Response, jsonify, request

logger = logging.getLogger("pyontrust.gateway.middleware")


def register_middleware(app: Flask) -> None:
    """Attach all middleware hooks to *app*."""

    # ── CORS (permissive for local dev) ─────────────────────────────
    @app.after_request
    def _cors(response: Response) -> Response:
        origin = request.headers.get("Origin", "*")
        response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS"
        response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization"
        response.headers["Access-Control-Max-Age"] = "3600"
        return response

    @app.before_request
    def _cors_preflight() -> Response | None:
        if request.method == "OPTIONS":
            resp = Response("", status=204)
            resp.headers["Access-Control-Allow-Origin"] = request.headers.get("Origin", "*")
            resp.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS"
            resp.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization"
            return resp
        return None

    # ── Request timing ──────────────────────────────────────────────
    @app.before_request
    def _start_timer() -> None:
        request._start_time = time.perf_counter()  # type: ignore[attr-defined]

    @app.after_request
    def _log_request(response: Response) -> Response:
        elapsed = time.perf_counter() - getattr(request, "_start_time", time.perf_counter())
        if elapsed > 1.0 or response.status_code >= 400:
            logger.info(
                "%s %s → %s (%.3fs)",
                request.method,
                request.path,
                response.status,
                elapsed,
            )
        return response

    # ── Error handlers ──────────────────────────────────────────────
    @app.errorhandler(404)
    def _not_found(e: Any) -> tuple:
        return jsonify({"error": "Not found", "path": request.path}), 404

    @app.errorhandler(500)
    def _internal_error(e: Any) -> tuple:
        logger.exception("Internal server error on %s %s", request.method, request.path)
        return jsonify({"error": "Internal server error"}), 500
