"""Tests for the Baram-Web Flask application."""
import sys
import os
import json
import pytest

# ── Make the baram-web package importable ─────────────────────────────────
_HERE = os.path.dirname(os.path.abspath(__file__))
_WEB_ROOT = os.path.dirname(_HERE)
if _WEB_ROOT not in sys.path:
    sys.path.insert(0, _WEB_ROOT)


@pytest.fixture
def app():
    """Create a Flask test app."""
    from server import app as flask_app
    flask_app.config["TESTING"] = True
    return flask_app


@pytest.fixture
def client(app):
    """Flask test client."""
    return app.test_client()
