"""Lab bench configuration and hardware inventory.

A **lab bench** is the persistent description of a physical test setup:
which instruments are connected, how they're wired, and their calibration
data.  It is stored as a YAML or JSON file that can be version-controlled
alongside the DUT firmware repo.

Design principles
-----------------
- **Declarative**: describe *what* is on the bench, not *how* to test.
- **Composable**: a bench config can reference shared calibration profiles.
- **Validatable**: every field has a type and optional range constraint.
- **Hardware-agnostic**: the bench schema is the same whether you have one
  AD3 or a cluster of ten.

Example ``lab_bench.json``::

    {
      "name": "nrf9160_power_bench",
      "instruments": {
        "power_meter": {
          "type": "ad3_cluster",
          "devices": [
            {"serial": "SN:210321A01234", "role": "current"},
            {"serial": "SN:210321A05678", "role": "voltage"}
          ],
          "shunt_ohms": 10.0,
          "sample_rate_hz": 10000
        },
        "ppk2": {
          "type": "ppk2",
          "serial_port": "auto",
          "mode": "source",
          "source_voltage_mv": 3300
        },
        "jlink": {
          "type": "jlink",
          "serial": "auto",
          "interface": "swd",
          "speed_khz": 4000,
          "device": "nRF9160_xxAA"
        },
        "psu": {
          "type": "sk120",
          "port": "COM5",
          "default_voltage_v": 3.3,
          "current_limit_a": 0.5
        },
        "can": {
          "type": "pcan",
          "channel": "PCAN_USBBUS1",
          "bitrate": 500000
        },
        "sdr": {
          "type": "hackrf",
          "antenna": "700MHz-11GHz",
          "center_freq_hz": 868000000,
          "sample_rate_hz": 2000000,
          "lna_gain_db": 32,
          "vga_gain_db": 24
        },
        "camera": {
          "type": "webcam",
          "device_index": 0,
          "resolution": [1920, 1080],
          "fps": 30,
          "ir_filter": false
        }
      },
      "calibration": {
        "power_meter": {
          "current_offset_a": 0.0,
          "voltage_offset_v": 0.0,
          "last_cal_date": "2026-02-15"
        }
      },
      "wiring": {
        "description": "AD3 cluster: CH1 across 10Ω shunt (current), CH2 at DUT VCC (voltage). PPK2 in source mode powering DUT. J-Link SWD to DUT debug header."
      }
    }
"""

from __future__ import annotations

import json
import logging
import pathlib
from dataclasses import dataclass, field
from typing import Any, Optional

logger = logging.getLogger("pyontrust.lab_bench")


@dataclass
class CalibrationData:
    """Calibration offsets and metadata for an instrument."""
    current_offset_a: float = 0.0
    voltage_offset_v: float = 0.0
    gain_correction: float = 1.0
    last_cal_date: str | None = None
    notes: str = ""


@dataclass
class InstrumentConfig:
    """Configuration for a single instrument in the bench."""
    name: str
    type: str
    params: dict[str, Any] = field(default_factory=dict)
    calibration: CalibrationData = field(default_factory=CalibrationData)
    enabled: bool = True

    def get(self, key: str, default: Any = None) -> Any:
        return self.params.get(key, default)


@dataclass
class LabBench:
    """Complete description of a physical test bench.

    Load from JSON/YAML, pass to :class:`TestSession` to instantiate
    all instruments and recorders automatically.
    """
    name: str
    instruments: dict[str, InstrumentConfig] = field(default_factory=dict)
    calibration: dict[str, CalibrationData] = field(default_factory=dict)
    wiring: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    # --------------- serialization ----------------------------------------

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {"name": self.name}
        if self.instruments:
            out["instruments"] = {}
            for k, inst in self.instruments.items():
                d = {"type": inst.type, "enabled": inst.enabled, **inst.params}
                out["instruments"][k] = d
        if self.calibration:
            out["calibration"] = {
                k: {
                    "current_offset_a": c.current_offset_a,
                    "voltage_offset_v": c.voltage_offset_v,
                    "gain_correction": c.gain_correction,
                    "last_cal_date": c.last_cal_date,
                    "notes": c.notes,
                }
                for k, c in self.calibration.items()
            }
        if self.wiring:
            out["wiring"] = self.wiring
        if self.metadata:
            out["metadata"] = self.metadata
        return out

    def save(self, path: str | pathlib.Path) -> None:
        p = pathlib.Path(path)
        p.write_text(json.dumps(self.to_dict(), indent=2), encoding="utf-8")
        logger.info("Saved bench config to %s", p)

    @classmethod
    def load(cls, path: str | pathlib.Path) -> LabBench:
        """Load a bench configuration from a JSON file."""
        p = pathlib.Path(path)
        raw = json.loads(p.read_text(encoding="utf-8"))
        return cls.from_dict(raw)

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> LabBench:
        """Build a LabBench from a plain dict (e.g. parsed JSON)."""
        name = str(raw.get("name", "unnamed_bench"))

        # --- instruments ---
        instruments: dict[str, InstrumentConfig] = {}
        for inst_name, inst_cfg in (raw.get("instruments") or {}).items():
            if not isinstance(inst_cfg, dict):
                continue
            inst_type = str(inst_cfg.pop("type", "unknown"))
            enabled = bool(inst_cfg.pop("enabled", True))
            instruments[inst_name] = InstrumentConfig(
                name=inst_name,
                type=inst_type,
                params=dict(inst_cfg),
                enabled=enabled,
            )

        # --- calibration ---
        calibration: dict[str, CalibrationData] = {}
        for cal_name, cal_cfg in (raw.get("calibration") or {}).items():
            if not isinstance(cal_cfg, dict):
                continue
            calibration[cal_name] = CalibrationData(
                current_offset_a=float(cal_cfg.get("current_offset_a", 0.0)),
                voltage_offset_v=float(cal_cfg.get("voltage_offset_v", 0.0)),
                gain_correction=float(cal_cfg.get("gain_correction", 1.0)),
                last_cal_date=cal_cfg.get("last_cal_date"),
                notes=str(cal_cfg.get("notes", "")),
            )

        # --- apply calibration to matching instruments ---
        for cal_key, cal in calibration.items():
            if cal_key in instruments:
                instruments[cal_key].calibration = cal

        return cls(
            name=name,
            instruments=instruments,
            calibration=calibration,
            wiring=raw.get("wiring") or {},
            metadata=raw.get("metadata") or {},
        )

    # --------------- helpers ----------------------------------------------

    def get_instrument(self, name: str) -> InstrumentConfig:
        if name not in self.instruments:
            raise KeyError(f"Instrument '{name}' not found in bench '{self.name}'. "
                           f"Available: {sorted(self.instruments.keys())}")
        return self.instruments[name]

    def enabled_instruments(self) -> dict[str, InstrumentConfig]:
        return {k: v for k, v in self.instruments.items() if v.enabled}

    def list_types(self) -> dict[str, str]:
        """Return {name: type} for all instruments."""
        return {k: v.type for k, v in self.instruments.items()}
