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


def _drain(k, quiet_s: float = 0.3, max_s: float = 3.0) -> None:
    """Stop any running measurement and read until the port goes quiet.

    After a stop the PPK2 still delivers the samples already in flight; a single
    buffer reset is not enough and the leftovers corrupt the next metadata read."""
    try:
        k.stop_measuring()
    except Exception:
        pass
    old = k.ser.timeout
    k.ser.timeout = quiet_s
    try:
        end = time.perf_counter() + max_s
        while time.perf_counter() < end and k.ser.read(65536):
            pass
    except Exception:
        pass
    finally:
        k.ser.timeout = old


def _pick_data_port(ports: list[str]) -> str:
    """The PPK2 enumerates as two serial ports (same serial number); measurement data
    and commands use the one on the lower USB interface number (…:1.1, not …:1.3).
    Chosen from the USB location only — nothing is sent to the device."""
    import re

    try:
        import serial.tools.list_ports

        iface = {}
        for p in serial.tools.list_ports.comports():
            m = re.search(r":\d+\.(\d+)$", p.location or "")
            if p.device in ports and m:
                iface[p.device] = int(m.group(1))
        if iface:
            return min(ports, key=lambda d: (iface.get(d, 99), d))
    except Exception:
        pass
    return sorted(ports)[0]


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
            try:
                from ppk2_api import PPK2_API
            except ImportError:  # newer ppk2-api keeps the class in a submodule
                from ppk2_api.ppk2_api import PPK2_API
        except ImportError as exc:
            raise ImportError(
                "PPK2 driver requires ppk2-api: pip install ppk2-api"
            ) from exc

        port = self._resolve_port()
        logger.info("Opening PPK2 on %s (mode=%s, voltage=%d mV)", port, self.mode, self.source_voltage_mv)

        try:
            ppk2 = PPK2_API(port)
        except Exception as exc:
            if "Permission denied" in str(exc):
                raise PermissionError(
                    f"PPK2 on {port}: permission denied — add your user to the 'dialout' group "
                    "(sudo usermod -aG dialout $USER, then log out and in) or install a udev rule "
                    "for Nordic devices (VID 1915)"
                ) from exc
            raise
        _drain(ppk2)                    # a previous measurement may still be streaming
        ppk2.get_modifiers()

        if self.mode == "source":
            ppk2.use_source_meter()
            ppk2.set_source_voltage(self.source_voltage_mv)
            ppk2.toggle_DUT_power("ON")
        else:
            ppk2.use_ampere_meter()
            # ppk2-api refuses start_measuring() without a set voltage, also in ampere mode
            # (it is the reference for the logic port); DUT power is never switched on here.
            ppk2.set_source_voltage(self.source_voltage_mv)

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
                if isinstance(samples, tuple):  # newer ppk2-api returns (samples, raw_digital_output)
                    samples = samples[0]
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
            try:
                from ppk2_api import PPK2_API
            except ImportError:  # newer ppk2-api keeps the class in a submodule
                from ppk2_api.ppk2_api import PPK2_API
            ports = sorted({str(p) for p in (PPK2_API.list_devices() or [])})
            if len(ports) == 1:
                logger.info("PPK2 auto-discovered on %s", ports[0])
                return ports[0]
            if ports:
                port = _pick_data_port(ports)
                logger.info("PPK2 auto-discovered on %s (of %s)", port, ", ".join(ports))
                return port
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
