"""Gateway security policy — who may talk to the lab bench, and from where.

The gateway drives real hardware (PSUs, debug probes, CAN, cameras) and can
run FlowLab workflows, so a request is a physical action.  Policy:

1. **No cross-site requests.**  A web page on another site must not be able
   to trigger or read anything here (the classic "drive-by request to
   localhost").  Browsers label requests with ``Sec-Fetch-Site`` / ``Origin``;
   cross-site ones are refused except plain top-level navigations (clicking
   a link to the gateway).  Extra origins may be allowed explicitly via
   ``PYONTRUST_ALLOWED_ORIGINS`` (comma-separated).
2. **Remote clients need the station token.**  Requests from loopback are
   trusted (single-user lab PC).  Anything else must present the token as
   ``Authorization: Bearer <token>``, the ``pyontrust_token`` cookie, or once
   as ``?token=<token>`` (which sets the cookie).  Token source:
   ``PYONTRUST_TOKEN`` or ``~/.pyontrust/gateway_token`` (created on demand,
   mode 0600).  ``PYONTRUST_REMOTE_NO_AUTH=1`` disables this (not advised).
3. **Defensive headers** on every response.
"""
from __future__ import annotations

import hmac
import ipaddress
import logging
import os
import secrets
from pathlib import Path
from urllib.parse import urlencode, urlsplit

from flask import Flask, Response, jsonify, redirect, request

logger = logging.getLogger("pyontrust.gateway.security")

COOKIE = "pyontrust_token"
_UNSAFE = {"POST", "PUT", "PATCH", "DELETE"}


def token_path() -> Path:
    return Path.home() / ".pyontrust" / "gateway_token"


def load_token(create: bool = True) -> str | None:
    """The station token (env var wins; otherwise the token file)."""
    env = os.environ.get("PYONTRUST_TOKEN", "").strip()
    if env:
        return env
    path = token_path()
    try:
        tok = path.read_text(encoding="utf-8").strip()
        if tok:
            return tok
    except OSError:
        pass
    if not create:
        return None
    tok = secrets.token_urlsafe(24)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        fh.write(tok + "\n")
    logger.warning("Created station token in %s", path)
    return tok


def _is_loopback(addr: str | None) -> bool:
    try:
        return ipaddress.ip_address((addr or "").split("%")[0]).is_loopback
    except ValueError:
        return False


def _origin_of(url: str | None) -> str | None:
    if not url:
        return None
    parts = urlsplit(url)
    return f"{parts.scheme}://{parts.netloc}".lower() if parts.scheme and parts.netloc else None


def register_security(app: Flask) -> None:
    allowed = {o.strip().lower().rstrip("/") for o in
               os.environ.get("PYONTRUST_ALLOWED_ORIGINS", "").split(",") if o.strip()}
    remote_auth = os.environ.get("PYONTRUST_REMOTE_NO_AUTH") != "1"
    app.extensions["security"] = {"allowed_origins": sorted(allowed), "remote_auth": remote_auth}

    def same_origin(origin: str) -> bool:
        return origin == request.host_url.rstrip("/").lower() or origin in allowed

    def deny(status: int, message: str) -> Response:
        logger.warning("Blocked %s %s from %s: %s", request.method, request.path,
                       request.remote_addr, message)
        resp = jsonify({"ok": False, "error": message})
        resp.status_code = status
        return resp

    @app.before_request
    def _policy() -> Response | None:
        # ── 1. cross-site protection ───────────────────────────────────
        site = request.headers.get("Sec-Fetch-Site", "").lower()
        origin = (request.headers.get("Origin") or "").lower().rstrip("/") or None
        if origin == "null":
            return deny(403, "Cross-origin request blocked (opaque origin)")
        if origin and not same_origin(origin):
            if request.method == "OPTIONS" and origin in allowed:
                return None  # preflight for an allowed origin — answered below
            return deny(403, f"Cross-origin request from {origin} blocked")
        if site == "cross-site" and request.headers.get("Sec-Fetch-Mode") != "navigate" and not origin:
            return deny(403, "Cross-site request blocked")
        if request.method in _UNSAFE and not origin:
            ref = _origin_of(request.headers.get("Referer"))
            if ref and not same_origin(ref):
                return deny(403, f"Cross-origin request from {ref} blocked")

        # ── 2. station token for non-loopback clients ──────────────────
        if not remote_auth or _is_loopback(request.remote_addr):
            return None
        token = load_token()
        given = request.cookies.get(COOKIE, "")
        auth = request.headers.get("Authorization", "")
        if auth.lower().startswith("bearer "):
            given = auth[7:].strip()
        query_token = request.args.get("token")
        if query_token and hmac.compare_digest(query_token, token or ""):
            # one-time link login: set the cookie and drop the token from the URL
            args = request.args.to_dict(flat=False)
            args.pop("token", None)
            target = request.path + ("?" + urlencode(args, doseq=True) if args else "")
            resp = redirect(target)
            resp.set_cookie(COOKIE, query_token, httponly=True, samesite="Strict",
                            secure=request.is_secure, max_age=30 * 86400)
            return resp
        if given and token and hmac.compare_digest(given, token):
            return None
        if request.path.startswith("/api") or "/api/" in request.path:
            return deny(401, "Station token required (Authorization: Bearer <token>)")
        return Response(_LOGIN_PAGE, status=401, mimetype="text/html")

    @app.after_request
    def _headers(resp: Response) -> Response:
        origin = (request.headers.get("Origin") or "").lower().rstrip("/")
        if origin and origin in allowed:
            resp.headers["Access-Control-Allow-Origin"] = origin
            resp.headers["Vary"] = "Origin"
            resp.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, PATCH, DELETE, OPTIONS"
            resp.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization"
            resp.headers["Access-Control-Allow-Credentials"] = "true"
            if request.method == "OPTIONS":
                resp.status_code = 204
        resp.headers.setdefault("X-Content-Type-Options", "nosniff")
        resp.headers.setdefault("X-Frame-Options", "SAMEORIGIN")
        resp.headers.setdefault("Content-Security-Policy", "frame-ancestors 'self'")
        resp.headers.setdefault("Referrer-Policy", "same-origin")
        return resp


_LOGIN_PAGE = """<!DOCTYPE html><html lang="en"><head><meta charset="utf-8">
<title>pyontrust — station token</title><style>body{font-family:system-ui;background:#1e1e2e;color:#cdd6f4;
display:grid;place-items:center;height:100vh;margin:0}form{background:#252538;padding:24px;border-radius:8px;
border:1px solid #585b70;width:min(420px,90vw)}input{width:100%;padding:8px;margin:10px 0;background:#2d2d44;
color:#cdd6f4;border:1px solid #585b70;border-radius:5px}button{padding:8px 16px;background:#89b4fa;border:0;
border-radius:5px;font-weight:600}</style></head><body><main><form method="get"><h1 style="font-size:18px">
Station token required</h1><p>This gateway controls lab hardware. Enter the station token (shown in the
gateway's log at start-up, or in <code>~/.pyontrust/gateway_token</code> on the lab PC).</p>
<label>Token<input name="token" type="password" autocomplete="off" autofocus></label>
<button type="submit">Continue</button></form></main></body></html>"""
