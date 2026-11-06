"""SEGGER J-Link debug probe controller.

Provides firmware flashing, target reset, RTT logging, and halt/resume
through the J-Link Commander CLI (``JLink.exe`` / ``JLinkExe``).

This is **CLI-first** by design — no native SDK dependency, works on
any machine with J-Link Software installed.

Usage in a test profile::

    "instruments": {
      "jlink": {
        "type": "jlink",
        "device": "nRF9160_xxAA",
        "interface": "swd",
        "speed_khz": 4000,
        "serial": "auto"
      }
    }
"""

from __future__ import annotations

import logging
import os
import pathlib
import shutil
import subprocess
import tempfile
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Optional

logger = logging.getLogger("pyontrust.instruments.jlink")

# Default search order for J-Link CLI
_JLINK_NAMES = ["JLink.exe", "JLinkExe", "JLink"]


def _find_jlink() -> str:
    """Find JLink CLI on PATH or common install locations."""
    for name in _JLINK_NAMES:
        path = shutil.which(name)
        if path:
            return path

    # Windows default install
    common_paths = [
        r"C:\Program Files\SEGGER\JLink\JLink.exe",
        r"C:\Program Files (x86)\SEGGER\JLink\JLink.exe",
    ]
    for p in common_paths:
        if os.path.isfile(p):
            return p

    raise FileNotFoundError(
        "JLink CLI not found. Install SEGGER J-Link Software or add to PATH."
    )


@dataclass
class JLinkController:
    """J-Link debug probe for flashing, reset, and RTT logging.

    Parameters
    ----------
    device : str
        Target MCU name (e.g. ``"nRF9160_xxAA"``, ``"STM32L476RG"``).
    interface : str
        Debug interface: ``"swd"`` (default) or ``"jtag"``.
    speed_khz : int
        Interface clock speed in kHz.
    serial : str
        J-Link serial number. ``"auto"`` uses first available.
    jlink_path : str
        Path to JLink CLI. ``"auto"`` searches PATH + common locations.
    """

    device: str = ""
    interface: str = "swd"
    speed_khz: int = 4000
    serial: str = "auto"
    jlink_path: str = "auto"

    _resolved_path: str = field(default="", init=False, repr=False)
    _rtt_thread: threading.Thread | None = field(default=None, init=False, repr=False)
    _rtt_process: subprocess.Popen | None = field(default=None, init=False, repr=False)
    _rtt_stop: threading.Event = field(default_factory=threading.Event, init=False, repr=False)

    def open(self) -> None:
        if self.jlink_path == "auto":
            self._resolved_path = _find_jlink()
        else:
            self._resolved_path = self.jlink_path
        logger.info("J-Link CLI: %s (device=%s, interface=%s)", self._resolved_path, self.device, self.interface)

    def close(self) -> None:
        self.stop_rtt()

    # ---- High-level operations -------------------------------------------

    def flash(self, firmware_path: str, *, erase: bool = True, reset: bool = True) -> None:
        """Flash a hex/bin file to the target.

        Parameters
        ----------
        firmware_path : str
            Path to ``.hex`` or ``.bin`` firmware file.
        erase : bool
            Erase chip before programming.
        reset : bool
            Reset target after programming.
        """
        cmds = []
        if erase:
            cmds.append("erase")
        cmds.append(f"loadfile {firmware_path}")
        if reset:
            cmds.append("r")  # reset
            cmds.append("g")  # go (run)
        cmds.append("q")      # quit

        logger.info("Flashing %s", firmware_path)
        self._run_commands(cmds)

    def reset(self, *, halt: bool = False) -> None:
        """Reset the target MCU."""
        cmds = ["r"]
        if not halt:
            cmds.append("g")
        cmds.append("q")
        self._run_commands(cmds)
        logger.info("Target reset (halt=%s)", halt)

    def halt(self) -> None:
        """Halt target execution."""
        self._run_commands(["h", "q"])
        logger.info("Target halted")

    def go(self) -> None:
        """Resume target execution."""
        self._run_commands(["g", "q"])
        logger.info("Target running")

    # ---- RTT logging -----------------------------------------------------

    def start_rtt(
        self,
        output_path: str | pathlib.Path,
        *,
        channel: int = 0,
        search_range: str = "0x20000000 0x10000",
    ) -> None:
        """Start background RTT logging to a file.

        Uses ``JLinkRTTLogger`` (ships with J-Link Software).
        """
        rtt_exe = self._find_rtt_logger()
        output_path = pathlib.Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        cmd = [
            rtt_exe,
            "-Device", self.device,
            "-If", self.interface.upper(),
            "-Speed", str(self.speed_khz),
            "-RTTChannel", str(channel),
            output_path.as_posix(),
        ]
        if self.serial != "auto":
            cmd.extend(["-USB", self.serial])

        logger.info("Starting RTT logger: %s", " ".join(cmd))
        self._rtt_stop.clear()
        self._rtt_process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )

    def stop_rtt(self) -> None:
        """Stop background RTT logging."""
        if self._rtt_process is None:
            return
        try:
            self._rtt_process.terminate()
            self._rtt_process.wait(timeout=5)
        except Exception:
            try:
                self._rtt_process.kill()
            except Exception:
                pass
        self._rtt_process = None
        logger.info("RTT logger stopped")

    # ---- Internal --------------------------------------------------------

    def _run_commands(self, commands: list[str]) -> str:
        """Write a J-Link script file and execute it."""
        if not self._resolved_path:
            self.open()

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".jlink", delete=False, encoding="utf-8"
        ) as f:
            for cmd in commands:
                f.write(cmd + "\n")
            script_path = f.name

        try:
            cmd_line = [
                self._resolved_path,
                "-Device", self.device,
                "-If", self.interface.upper(),
                "-Speed", str(self.speed_khz),
                "-AutoConnect", "1",
                "-CommandFile", script_path,
            ]
            if self.serial != "auto":
                cmd_line.extend(["-USB", self.serial])

            result = subprocess.run(
                cmd_line,
                capture_output=True,
                text=True,
                timeout=60,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            if result.returncode != 0:
                logger.warning("J-Link returned rc=%d: %s", result.returncode, result.stderr[:500])
            return result.stdout
        finally:
            try:
                os.remove(script_path)
            except OSError:
                pass

    def _find_rtt_logger(self) -> str:
        """Find JLinkRTTLogger executable."""
        for name in ["JLinkRTTLogger.exe", "JLinkRTTLogger"]:
            path = shutil.which(name)
            if path:
                return path

        # Try same directory as JLink CLI
        if self._resolved_path:
            parent = pathlib.Path(self._resolved_path).parent
            for name in ["JLinkRTTLogger.exe", "JLinkRTTLogger"]:
                candidate = parent / name
                if candidate.is_file():
                    return str(candidate)

        raise FileNotFoundError("JLinkRTTLogger not found. Install SEGGER J-Link Software.")
