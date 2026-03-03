"""Nordic PPK2 power meter via ``ppk2-api`` Python library.

The PPK2 (Power Profiler Kit II) is a Nordic Semiconductor tool for
measuring power consumption of embedded devices at µA resolution.

This adapter wraps the ``ppk2-api`` package (``pip install ppk2-api``)
and exposes it through the :class:`~..instruments.base.PowerMeter` protocol.

Modes
-----
- **Source mode**: PPK2 powers the DUT directly (0–5000 mV).
- **Ampere meter mode**: PPK2 is in-line with an external supply.

The driver auto-discovers the PPK2 serial port when ``serial_port="auto"``.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Iterable, Optional

from ..core import PowerSample

logger = logging.getLogger("pyontrust.instruments.ppk2")


@dataclass
class Ppk2PowerMeter:
    """PPK2 power meter adapter.

    Parameters
    ----------
    serial_port : str
        Serial port (e.g. ``"COM6"``). Use ``"auto"`` for auto-discovery.
    mode : str
        ``"source"`` or ``"ampere"`` (in-line with external PSU).
    source_voltage_mv : int
        Output voltage in millivolts (source mode only, 800–5000).
    sample_rate_hz : float
        Desired sample rate.  PPK2 native rate is 100 kHz; we decimate.
    """

    serial_port: str = "auto"
    mode: str = "source"
    source_voltage_mv: int = 3300
    sample_rate_hz: float = 100_000.0

    _ppk2: Any = field(default=None, init=False, repr=False)
    _t0: float = field(default=0.0, init=False, repr=False)

    def open(self) -> None:
        try:
            from ppk2_api import PPK2_API
        except ImportError as exc:
            raise ImportError(
                "PPK2 driver requires ppk2-api: pip install ppk2-api"
            ) from exc

        port = self._resolve_port()
        logger.info("Opening PPK2 on %s (mode=%s, voltage=%d mV)", port, self.mode, self.source_voltage_mv)

        ppk2 = PPK2_API(port)
        ppk2.get_modifiers()

        if self.mode == "source":
            ppk2.use_source_meter()
            ppk2.set_source_voltage(self.source_voltage_mv)
            ppk2.toggle_DUT_power("ON")
        else:
            ppk2.use_ampere_meter()

        self._ppk2 = ppk2
        self._t0 = time.perf_counter()
        logger.info("PPK2 opened successfully")

    def close(self) -> None:
        if self._ppk2 is None:
            return
        try:
            self._ppk2.toggle_DUT_power("OFF")
        except Exception:
            pass
        self._ppk2 = None
        logger.info("PPK2 closed")

    def capture(self, duration_s: float) -> Iterable[PowerSample]:
        if self._ppk2 is None:
            self.open()
        assert self._ppk2 is not None

        self._ppk2.start_measuring()
        start = time.perf_counter()

        try:
            while (time.perf_counter() - start) < duration_s:
                read_data = self._ppk2.get_data()
                if read_data is None or len(read_data) == 0:
                    time.sleep(0.001)
                    continue

                samples = self._ppk2.get_samples(read_data)
                if not samples:
                    continue

                now = time.perf_counter()
                n = len(samples)
                dt = 1.0 / self.sample_rate_hz
                # Distribute timestamps evenly over the batch
                t_base = now - self._t0 - (n * dt)

                for i, current_ua in enumerate(samples):
                    t_s = t_base + (i * dt)
                    current_a = float(current_ua) * 1e-6
                    voltage_v = float(self.source_voltage_mv) * 1e-3
                    yield PowerSample(
                        t_s=max(0.0, t_s),
                        current_a=current_a,
                        voltage_v=voltage_v,
                    )
        finally:
            try:
                self._ppk2.stop_measuring()
            except Exception:
                pass

    def set_voltage(self, voltage_mv: int) -> None:
        """Change source voltage live (source mode only)."""
        if self._ppk2 is None:
            raise RuntimeError("PPK2 not open")
        self._ppk2.set_source_voltage(voltage_mv)
        self.source_voltage_mv = voltage_mv
        logger.info("PPK2 voltage set to %d mV", voltage_mv)

    def _resolve_port(self) -> str:
        if self.serial_port != "auto":
            return self.serial_port

        try:
            from ppk2_api import PPK2_API
            ppk2_port = PPK2_API.list_devices()
            if ppk2_port:
                port = ppk2_port[0]
                logger.info("PPK2 auto-discovered on %s", port)
                return str(port)
        except Exception:
            pass

        # Fallback: scan serial ports for Nordic VID/PID
        try:
            import serial.tools.list_ports
            NORDIC_VID = 0x1915
            for p in serial.tools.list_ports.comports():
                if p.vid == NORDIC_VID:
                    logger.info("PPK2 found via VID scan: %s", p.device)
                    return p.device
        except ImportError:
            pass

        raise RuntimeError(
            "Could not auto-discover PPK2. "
            "Set serial_port explicitly or install pyserial."
        )
