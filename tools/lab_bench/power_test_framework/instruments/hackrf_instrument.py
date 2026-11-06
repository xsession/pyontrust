"""HackRF One instrument — RF spectrum analyser / IQ recorder.

Wraps ``hackrf_transfer`` and optionally ``hackrf_sweep`` to provide
spectrum-level measurements and raw IQ capture as a *first-class
instrument* (open/close lifecycle) rather than just a recorder.

This is designed around the user's 700 MHz – 11 GHz antenna setup.

Usage in a test profile::

    "instruments": {
      "hackrf": {
        "type": "hackrf",
        "freq_hz": 2402000000,
        "sample_rate_hz": 10000000,
        "lna_gain_db": 16,
        "vga_gain_db": 20,
        "amp_enable": false,
        "device_serial": "auto"
      }
    }

Two operational modes:

1. **IQ capture** — records raw IQ to a file for a given duration.
2. **Sweep** — uses ``hackrf_sweep`` to produce power-vs-frequency data
   over a configurable band (e.g. 700 MHz – 6 GHz).
"""

from __future__ import annotations

import logging
import os
import pathlib
import shutil
import subprocess
import time
from dataclasses import dataclass, field
from typing import Any, Optional

from ..platform import creationflags_no_window

logger = logging.getLogger("pyontrust.instruments.hackrf")


def _find_tool(name: str) -> Optional[str]:
    path = shutil.which(name)
    if path:
        return path
    # Common Windows install
    for p in [
        rf"C:\Program Files\hackrf\bin\{name}.exe",
        rf"C:\hackrf\{name}.exe",
    ]:
        if os.path.isfile(p):
            return p
    return None


@dataclass
class HackRfInstrument:
    """HackRF One as a measurement instrument.

    Parameters
    ----------
    freq_hz : int
        Centre frequency in Hz.
    sample_rate_hz : int
        Sample rate in Hz (max 20 MSPS).
    lna_gain_db : int
        LNA gain 0-40 dB (steps of 8).
    vga_gain_db : int
        VGA gain 0-62 dB (steps of 2).
    amp_enable : bool
        Enable +14 dB RF amplifier.
    device_serial : str
        Device serial, ``"auto"`` for first available.
    hackrf_transfer_path : str
        Path to ``hackrf_transfer`` binary.
    hackrf_sweep_path : str
        Path to ``hackrf_sweep`` binary.
    """

    freq_hz: int = 2_402_000_000
    sample_rate_hz: int = 10_000_000
    lna_gain_db: int = 16
    vga_gain_db: int = 20
    amp_enable: bool = False
    device_serial: str = "auto"

    hackrf_transfer_path: str = "hackrf_transfer"
    hackrf_sweep_path: str = "hackrf_sweep"

    skip_if_missing: bool = True

    _transfer_exe: Optional[str] = field(default=None, init=False, repr=False)
    _sweep_exe: Optional[str] = field(default=None, init=False, repr=False)
    _iq_proc: subprocess.Popen | None = field(default=None, init=False, repr=False)

    def open(self) -> None:
        self._transfer_exe = _find_tool(self.hackrf_transfer_path)
        self._sweep_exe = _find_tool(self.hackrf_sweep_path)
        if self._transfer_exe is None and not self.skip_if_missing:
            raise FileNotFoundError(f"{self.hackrf_transfer_path} not found")
        logger.info(
            "HackRF: transfer=%s sweep=%s freq=%d Hz",
            self._transfer_exe or "MISSING",
            self._sweep_exe or "MISSING",
            self.freq_hz,
        )

    def close(self) -> None:
        self.stop_iq_capture()

    # ---- IQ Capture (background) -----------------------------------------

    def start_iq_capture(self, output_path: str | pathlib.Path) -> bool:
        """Start background IQ capture to a file.

        Returns True if started, False if tool is missing and skip_if_missing.
        """
        if self._transfer_exe is None:
            if self.skip_if_missing:
                logger.warning("hackrf_transfer not found — skipping IQ capture")
                return False
            raise FileNotFoundError("hackrf_transfer not found")

        output_path = pathlib.Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        cmd: list[str] = [
            self._transfer_exe,
            "-r", str(output_path),
            "-f", str(int(self.freq_hz)),
            "-s", str(int(self.sample_rate_hz)),
        ]
        if self.lna_gain_db is not None:
            cmd += ["-l", str(int(self.lna_gain_db))]
        if self.vga_gain_db is not None:
            cmd += ["-g", str(int(self.vga_gain_db))]
        if self.amp_enable:
            cmd += ["-a", "1"]
        if self.device_serial != "auto":
            cmd += ["-d", self.device_serial]

        logger.info("Starting IQ capture: %s", " ".join(cmd))
        self._iq_proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            creationflags=creationflags_no_window(),
        )
        return True

    def stop_iq_capture(self) -> Optional[int]:
        """Stop background IQ capture. Returns exit code or None."""
        if self._iq_proc is None:
            return None
        try:
            self._iq_proc.terminate()
            self._iq_proc.wait(timeout=5)
        except Exception:
            try:
                self._iq_proc.kill()
            except Exception:
                pass
        rc = self._iq_proc.poll()
        self._iq_proc = None
        return rc

    # ---- Sweep (blocking) ------------------------------------------------

    def sweep(
        self,
        output_path: str | pathlib.Path,
        freq_start_mhz: int = 700,
        freq_stop_mhz: int = 6000,
        bin_width_hz: int = 1_000_000,
        num_sweeps: int = 1,
    ) -> bool:
        """Run a frequency sweep and write CSV output.

        Uses ``hackrf_sweep`` which produces CSV rows::

            date, time, freq_low, freq_high, bin_width, num_bins, db1, db2, ...

        Returns True if sweep ran, False if tool missing and skip_if_missing.
        """
        if self._sweep_exe is None:
            if self.skip_if_missing:
                logger.warning("hackrf_sweep not found — skipping")
                return False
            raise FileNotFoundError("hackrf_sweep not found")

        output_path = pathlib.Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        cmd: list[str] = [
            self._sweep_exe,
            "-f", f"{freq_start_mhz}:{freq_stop_mhz}",
            "-w", str(int(bin_width_hz)),
            "-N", str(int(num_sweeps)),
            "-r", str(output_path),
        ]
        if self.lna_gain_db is not None:
            cmd += ["-l", str(int(self.lna_gain_db))]
        if self.vga_gain_db is not None:
            cmd += ["-g", str(int(self.vga_gain_db))]
        if self.amp_enable:
            cmd += ["-a", "1"]
        if self.device_serial != "auto":
            cmd += ["-d", self.device_serial]

        logger.info("Running sweep: %s", " ".join(cmd))
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=120,
            creationflags=creationflags_no_window(),
        )
        if result.returncode != 0:
            logger.warning("hackrf_sweep rc=%d: %s", result.returncode, result.stderr[:500])
        return True

    # ---- Quick power measurement -----------------------------------------

    def measure_power_dbm(
        self,
        freq_mhz: int | None = None,
        bandwidth_mhz: int = 2,
        num_sweeps: int = 3,
    ) -> Optional[float]:
        """Quick single-frequency power measurement via sweep.

        Returns average power in dBm at the specified frequency, or None
        if sweep failed / tool missing.
        """
        import tempfile
        freq_mhz = freq_mhz or int(self.freq_hz / 1_000_000)
        start = max(1, freq_mhz - bandwidth_mhz // 2)
        stop = freq_mhz + bandwidth_mhz // 2

        with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as f:
            tmp = f.name

        try:
            ok = self.sweep(tmp, freq_start_mhz=start, freq_stop_mhz=stop, num_sweeps=num_sweeps)
            if not ok:
                return None
            return self._parse_sweep_avg_power(tmp)
        finally:
            try:
                os.remove(tmp)
            except OSError:
                pass

    @staticmethod
    def _parse_sweep_avg_power(csv_path: str) -> Optional[float]:
        """Parse hackrf_sweep CSV and return average power across all bins."""
        powers: list[float] = []
        try:
            with open(csv_path, "r", encoding="utf-8") as f:
                for line in f:
                    parts = line.strip().split(",")
                    if len(parts) < 7:
                        continue
                    # columns 6+ are dB values
                    for val in parts[6:]:
                        try:
                            powers.append(float(val.strip()))
                        except ValueError:
                            continue
        except Exception:
            return None
        if not powers:
            return None
        return sum(powers) / len(powers)
