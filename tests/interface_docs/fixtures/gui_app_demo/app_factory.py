from __future__ import annotations

from flask import Blueprint, jsonify, send_from_directory

from pyontrust.gateway.app import create_app as create_gateway_app

from driver import DemoBoardOD


SUMMARY = {
  "field_count": 2,
  "group_count": 1,
  "title": "Demo Interface",
  "transport": "canopen"
}
METADATA = {
  "groups": {
    "sensors": {
      "status": {
        "doc": "Device status",
        "flags": [
          "read",
          "write"
        ],
        "mlx": 3211266,
        "unit": null
      },
      "temperature": {
        "doc": "Board temperature",
        "flags": [
          "read"
        ],
        "mlx": 3211265,
        "unit": "C"
      }
    }
  }
}
READ_METHODS = [
  "read_status",
  "read_temperature"
]
WRITE_METHODS = [
  "write_status"
]


def create_blueprint() -> Blueprint:
    bp = Blueprint("demo-dashboard_generated", __name__, static_folder="web")

    @bp.get("/")
    def index():
        return send_from_directory(bp.static_folder, "index.html")

    @bp.get("/api/health")
    def health():
        return {"status": "ok", "title": SUMMARY["title"]}

    @bp.get("/api/summary")
    def summary():
        return jsonify(SUMMARY)

    @bp.get("/api/metadata")
    def metadata():
        return jsonify(METADATA)

    @bp.get("/api/methods")
    def methods():
        return jsonify(
            {
                "driver_class": "DemoBoardOD",
                "available_readers": READ_METHODS,
                "available_writers": WRITE_METHODS,
                "generated_class_name": DemoBoardOD.__name__,
            }
        )

    return bp


def create_app():
    app = create_gateway_app()
    app.register_blueprint(create_blueprint(), url_prefix="/demo-dashboard")
    return app