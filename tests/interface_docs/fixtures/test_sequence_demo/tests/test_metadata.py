from __future__ import annotations

from sequence import DemoBoardSequence


def test_sequence_summary_includes_transport() -> None:
    sequence = DemoBoardSequence()
    summary = sequence.summary()

    assert summary["title"] == "Demo Interface"
    assert summary["transport"] == "canopen"


def test_sequence_exposes_metadata_and_driver_name() -> None:
    sequence = DemoBoardSequence()

    assert sequence.metadata() == {
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
    assert sequence.driver_class_name() == "DemoBoardOD"