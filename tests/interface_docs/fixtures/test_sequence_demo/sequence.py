from __future__ import annotations

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


class DemoBoardSequence:
    device_label = "Demo Board"
    device_key = "demo_board"
    device_serial_regex = "DEMO_BOARD-(\\d+)"

    def summary(self) -> dict:
        return dict(SUMMARY)

    def metadata(self) -> dict:
        return dict(METADATA)

    def expected_reader_methods(self) -> list[str]:
        return [
  "read_status",
  "read_temperature"
]

    def expected_writer_methods(self) -> list[str]:
        return [
  "write_status"
]

    def driver_class_name(self) -> str:
        return DemoBoardOD.__name__