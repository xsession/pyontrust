"""Cross-cutting middleware — security policy, error handlers, request logging."""
from __future__ import annotations

import logging
import time
import uuid
from typing import Any

from flask import Flask, Response, jsonify, request
from werkzeug.exceptions import HTTPException

logger = logging.getLogger("pyontrust.gateway.middleware")

AUDITED_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
# Read-only endpoints that happen to use POST (bodies are queries, not actions).
AUDIT_SKIP = {"/thermal/api/zone_readings", "/micro/api/release"}


def register_middleware(app: Flask) -> None:
    """Attach all middleware hooks to *app*."""

    # Security (cross-site blocking, CORS allowlist, station token, headers)
    # comes first: see pyontrust.gateway.security.
    from pyontrust.gateway.security import register_security

    register_security(app)

    # ── Request id + timing ─────────────────────────────────────────
    @app.before_request
    def _start_timer() -> None:
        request._start_time = time.perf_counter()  # type: ignore[attr-defined]
        incoming = request.headers.get("X-Request-ID", "")
        request.request_id = incoming[:64] if incoming.isalnum() else uuid.uuid4().hex[:12]  # type: ignore[attr-defined]

    @app.after_request
    def _log_request(response: Response) -> Response:
        elapsed = time.perf_counter() - getattr(request, "_start_time", time.perf_counter())
        response.headers["X-Request-ID"] = getattr(request, "request_id", "")
        if elapsed > 1.0 or response.status_code >= 400:
            logger.info("%s %s → %s (%.3fs) [%s]", request.method, request.path,
                        response.status, elapsed, getattr(request, "request_id", ""))
        _audit(response, elapsed)
        return response

    # ── Audit trail: every state-changing request ───────────────────
    def _audit(response: Response, elapsed: float) -> None:
        if request.method not in AUDITED_METHODS or request.path in AUDIT_SKIP:
            return
        try:
            from pyontrust.gateway import context
            from pyontrust.gateway.blueprints.station import audit_log
            from pyontrust.services.audit import redact

            body = request.get_json(silent=True) if request.is_json else None
            if body is None and request.form:
                body = {k: v for k, v in request.form.items()}
            if request.files:
                body = {**(body or {}), "_files": [f.filename for f in request.files.values()]}
            audit_log().append({
                **context.actor(),
                "action": f"{request.method} {request.path}",
                "tool": request.path.strip("/").split("/")[0] or "shell",
                "status": response.status_code,
                "duration_ms": round(elapsed * 1000),
                "request_id": getattr(request, "request_id", ""),
                "body": redact(body) if body is not None else None,
            })
        except Exception:  # the audit trail must never break the action itself
            logger.exception("audit append failed for %s %s", request.method, request.path)

    # ── Error handlers: one envelope for every API error ────────────
    def _envelope(status: int, message: str) -> tuple:
        return jsonify({"ok": False, "error": message, "status": status,
                        "request_id": getattr(request, "request_id", "")}), status

    @app.errorhandler(HTTPException)
    def _http_error(e: HTTPException) -> Any:
        if not (request.path.startswith("/api") or "/api/" in request.path) and e.code != 404:
            return e
        message = "Not found" if e.code == 404 else (e.description or e.name)
        return _envelope(e.code or 500, message)

    @app.errorhandler(Exception)
    def _internal_error(e: Exception) -> tuple:
        if isinstance(e, HTTPException):
            return _http_error(e)
        logger.exception("Unhandled error on %s %s [%s]", request.method, request.path,
                         getattr(request, "request_id", ""))
        return _envelope(500, f"Internal error ({type(e).__name__}) — quote request id "
                              f"{getattr(request, 'request_id', '')} when reporting")
