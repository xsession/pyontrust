"""SK120 programmable power supply driver.

Controls an SK120 (Manson / RND / Korad-compatible) bench power supply
via serial port using the standard SCPI-like text protocol that these
affordable lab PSUs share.

Common wire protocol (9600 8N1, \\r terminated)::

    VSET1:12.00   → set CH1 voltage to 12.00 V
    ISET1:01.500  → set CH1 current limit to 1.500 A
    VOUT1?        → query actual output voltage
    IOUT1?        → query actual output current
    OUT1          → turn output ON
    OUT0          → turn output OFF
    STATUS?       → query status byte

Some models use slightly different naming (VSET1?, ISET1?); this driver
auto-adapts.

Usage in a test profile::

    "instruments": {
      "psu": {
        "type": "sk120",
        "port": "COM5",
        "baud": 9600,
        "voltage_v": 3.3,
        "current_limit_a": 0.5
      }
    }
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Optional

logger = logging.getLogger("pyontrust.instruments.sk120")


@dataclass
class Sk120PowerSupply:
    """Programmable bench PSU over serial (SK120 / Korad / RND compatible).

    Parameters
    ----------
    port : str
        Serial port (``"COM5"``, ``"/dev/ttyUSB0"``, etc.).
    baud : int
        Baud rate (usually 9600).
    voltage_v : float
        Initial output voltage to set on open().
    current_limit_a : float
        Initial current limit to set on open().
    channel : int
        Output channel (1 for single-channel PSUs).
    output_on : bool
        Whether to enable output on open().
    """

    port: str = ""
    baud: int = 9600
    voltage_v: float = 3.3
    current_limit_a: float = 0.5
    channel: int = 1
    output_on: bool = True
    timeout_s: float = 2.0

    _serial: Any = field(default=None, init=False, repr=False)

    def open(self) -> None:
        """Open serial port and apply initial settings."""
        import serial  # pyserial

        if self._serial is not None:
            return

        self._serial = serial.Serial(
            port=self.port,
            baudrate=self.baud,
            bytesize=serial.EIGHTBITS,
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE,
            timeout=self.timeout_s,
        )
        time.sleep(0.2)  # let PSU wake up

        logger.info("Opened SK120 on %s @ %d baud", self.port, self.baud)

        self.set_voltage(self.voltage_v)
        self.set_current_limit(self.current_limit_a)
        if self.output_on:
            self.enable_output(True)

    def close(self) -> None:
        """Disable output and close serial port."""
        if self._serial is None:
            return
        try:
            self.enable_output(False)
        except Exception:
            pass
        try:
            self._serial.close()
        except Exception:
            pass
        self._serial = None
        logger.info("SK120 closed")

    # ---- Control methods -------------------------------------------------

    def set_voltage(self, voltage_v: float) -> None:
        """Set output voltage (volts)."""
        self._send(f"VSET{self.channel}:{voltage_v:05.2f}")
        logger.info("SK120 CH%d voltage → %.2f V", self.channel, voltage_v)

    def set_current_limit(self, current_a: float) -> None:
        """Set output current limit (amps)."""
        self._send(f"ISET{self.channel}:{current_a:06.3f}")
        logger.info("SK120 CH%d current limit → %.3f A", self.channel, current_a)

    def enable_output(self, on: bool = True) -> None:
        """Turn output ON or OFF."""
        self._send(f"OUT{1 if on else 0}")
        logger.info("SK120 output %s", "ON" if on else "OFF")

    def read_voltage(self) -> float:
        """Read actual output voltage."""
        resp = self._query(f"VOUT{self.channel}?")
        return self._parse_float(resp)

    def read_current(self) -> float:
        """Read actual output current."""
        resp = self._query(f"IOUT{self.channel}?")
        return self._parse_float(resp)

    def read_status(self) -> str:
        """Read status byte (raw string)."""
        return self._query("STATUS?")

    # ---- Low-level serial ------------------------------------------------

    def _send(self, cmd: str) -> None:
        """Send a command (adds \\r)."""
        if self._serial is None:
            raise RuntimeError("SK120 not connected. Call open() first.")
        self._serial.write((cmd + "\r").encode("ascii"))
        time.sleep(0.05)  # small delay between commands

    def _query(self, cmd: str) -> str:
        """Send a query and return the stripped response."""
        self._send(cmd)
        assert self._serial is not None
        raw = self._serial.readline()
        return raw.decode("ascii", errors="replace").strip()

    @staticmethod
    def _parse_float(resp: str) -> float:
        """Extract the numeric value from a response like ``'12.34V'``."""
        # Strip trailing unit letters
        cleaned = ""
        for ch in resp:
            if ch.isdigit() or ch in ".+-eE":
                cleaned += ch
            elif cleaned:
                break
        if not cleaned:
            raise ValueError(f"Cannot parse PSU response: {resp!r}")
        return float(cleaned)
