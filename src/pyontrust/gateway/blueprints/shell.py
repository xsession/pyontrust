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
    """Serve the app-shell ``index.html``."""
    return send_from_directory(str(_WEB_DIR), "index.html")


@bp.route("/favicon.ico")
def favicon():
    return send_from_directory(str(_WEB_DIR), "favicon.ico", mimetype="image/x-icon")
