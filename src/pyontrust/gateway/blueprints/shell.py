"""App-shell blueprint — serves the navigation chrome and root routes."""
from __future__ import annotations

import pathlib

from flask import Blueprint, send_from_directory

_WEB_DIR = pathlib.Path(__file__).resolve().parent.parent / "web" / "shell"

bp = Blueprint(
    "shell",
    __name__,
    static_folder=str(_WEB_DIR),
    static_url_path="/static/shell",
)


@bp.route("/")
def index():
    """App shell; navigation rendered from the tool registry."""
    from flask import Response

    from pyontrust.gateway.tools import render_shell

    page = render_shell((_WEB_DIR / "index.html").read_text(encoding="utf-8"))
    return Response(page, mimetype="text/html")


@bp.route("/favicon.ico")
def favicon():
    return send_from_directory(str(_WEB_DIR), "favicon.ico", mimetype="image/x-icon")
