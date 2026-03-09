"""Flask gateway — unified application factory.

Assembles all Blueprints (HIL, CSV Plotter, Pin Config, SDR, Waveforms,
Lab-Bench, Artifacts) under one Flask app with a shared app-shell.

Run standalone::

    python -m pyontrust.gateway.app          # default port 5200
    python -m pyontrust.gateway.app --port 8080
"""
from __future__ import annotations

import json
import logging
import math
import os
import pathlib
from importlib.metadata import entry_points
from typing import Any

from flask import Flask
from flask.json.provider import DefaultJSONProvider

logger = logging.getLogger("pyontrust.gateway")

_HERE = pathlib.Path(__file__).resolve().parent


# ── Safe JSON provider (NaN / Infinity → null) ─────────────────────────

class SafeJSONProvider(DefaultJSONProvider):
    """Replace NaN / Infinity with ``null`` so browsers can parse it."""

    def dumps(self, obj: Any, **kwargs: Any) -> str:
        kwargs.setdefault("allow_nan", False)
        kwargs.setdefault("default", self._default)
        try:
            return json.dumps(obj, **kwargs)
        except ValueError:
            return json.dumps(self._sanitise(obj), **kwargs)

    @staticmethod
    def _default(o: Any) -> Any:
        try:
            import numpy as np

            if isinstance(o, np.integer):
                return int(o)
            if isinstance(o, np.floating):
                v = float(o)
                return None if (math.isnan(v) or math.isinf(v)) else v
            if isinstance(o, np.ndarray):
                return [
                    None if (isinstance(x, float) and (math.isnan(x) or math.isinf(x))) else x
                    for x in o.tolist()
                ]
        except ImportError:
            pass
        raise TypeError(f"Object of type {type(o)} is not JSON serializable")

    @classmethod
    def _sanitise(cls, obj: Any) -> Any:
        if isinstance(obj, dict):
            return {k: cls._sanitise(v) for k, v in obj.items()}
        if isinstance(obj, (list, tuple)):
            return [cls._sanitise(v) for v in obj]
        if isinstance(obj, float) and (math.isnan(obj) or math.isinf(obj)):
            return None
        return obj


# ── Application factory ─────────────────────────────────────────────────

def create_app(
    *,
    artifacts_root: str = "artifacts",
    bench_path: str | None = None,
    extra_config: dict[str, Any] | None = None,
) -> Flask:
    """Create and configure the unified Flask application.

    Parameters
    ----------
    artifacts_root : str
        Path to the artifacts storage directory.
    bench_path : str | None
        Path to the default lab-bench JSON config.
    extra_config : dict | None
        Additional Flask config overrides.
    """
    app = Flask(
        __name__,
        static_folder=str(_HERE / "web" / "shell"),
        static_url_path="/static",
    )
    app.json_provider_class = SafeJSONProvider
    app.json = SafeJSONProvider(app)
    app.config["MAX_CONTENT_LENGTH"] = 500 * 1024 * 1024  # 500 MB

    if extra_config:
        app.config.update(extra_config)

    # ── Initialise services and store on app ────────────────────────
    from pyontrust.services import (
        ArtifactService,
        BenchService,
        ConfigService,
        LogService,
        TestService,
    )

    app.extensions["test_service"] = TestService(artifacts_root=artifacts_root)
    app.extensions["log_service"] = LogService()
    app.extensions["artifact_service"] = ArtifactService(root=artifacts_root)
    app.extensions["bench_service"] = BenchService(bench_path=bench_path)
    app.extensions["config_service"] = ConfigService(base_dir=".")

    # Ensure default event channels exist
    app.extensions["log_service"].ensure_channels()

    # ── Register built-in Blueprints ────────────────────────────────
    from pyontrust.gateway.blueprints.shell import bp as shell_bp
    from pyontrust.gateway.blueprints.hil import bp as hil_bp
    from pyontrust.gateway.blueprints.csv_plotter import bp as csv_bp
    from pyontrust.gateway.blueprints.bench import bp as bench_bp
    from pyontrust.gateway.blueprints.artifacts import bp as artifacts_bp
    from pyontrust.gateway.blueprints.config import bp as config_bp
    from pyontrust.gateway.blueprints.flowlab import bp as flowlab_bp
    from pyontrust.gateway.blueprints.diagnostic import bp as diag_bp

    app.register_blueprint(shell_bp)  # serves / and /static/shell/
    app.register_blueprint(diag_bp, url_prefix="/diag")
    app.register_blueprint(hil_bp, url_prefix="/hil")
    app.register_blueprint(csv_bp, url_prefix="/csv")
    app.register_blueprint(bench_bp, url_prefix="/bench")
    app.register_blueprint(artifacts_bp, url_prefix="/artifacts")
    app.register_blueprint(config_bp, url_prefix="/config")
    app.register_blueprint(flowlab_bp, url_prefix="/flowlab")

    # ── Auto-discover plugin Blueprints ─────────────────────────────
    try:
        eps = entry_points(group="pyontrust.blueprints")
        for ep in eps:
            try:
                plugin_bp = ep.load()
                app.register_blueprint(plugin_bp, url_prefix=f"/{ep.name}")
                logger.info("Registered plugin blueprint: /%s", ep.name)
            except Exception:
                logger.warning("Failed to load blueprint plugin %s", ep.name, exc_info=True)
    except Exception:
        pass

    # ── Register middleware ──────────────────────────────────────────
    from pyontrust.gateway.middleware import register_middleware
    register_middleware(app)

    # ── Health-check endpoint ───────────────────────────────────────
    @app.route("/api/health")
    def health():
        return {"status": "ok", "version": _get_version()}

    logger.info("Gateway app created — %d blueprints registered", len(app.blueprints))
    return app


def _get_version() -> str:
    try:
        from pyontrust import __version__
        return __version__
    except Exception:
        return "dev"


# ── CLI entry point ─────────────────────────────────────────────────────

def main() -> None:
    """CLI entry point: ``python -m pyontrust.gateway.app``."""
    import argparse

    parser = argparse.ArgumentParser(description="pyontrust gateway server")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=int(os.environ.get("PYONTRUST_PORT", "5200")))
    parser.add_argument("--artifacts", default=os.environ.get("PYONTRUST_ARTIFACTS", "artifacts"))
    parser.add_argument("--bench", default=os.environ.get("PYONTRUST_BENCH"))
    parser.add_argument("--debug", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(
        level=os.environ.get("PYONTRUST_LOG_LEVEL", "INFO").upper(),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    app = create_app(
        artifacts_root=args.artifacts,
        bench_path=args.bench,
    )
    app.run(host=args.host, port=args.port, debug=args.debug)


if __name__ == "__main__":
    main()
