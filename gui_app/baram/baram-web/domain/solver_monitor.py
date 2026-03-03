#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Solver process monitor — replaces CaseManager + Qt signal-based monitoring.

Tracks the solver subprocess via PID + create_time (same pattern as
``baramFlow.solver_status.SolverProcess``) and provides a thread-safe log
queue that the WebSocket endpoint can drain.
"""

import logging
import queue
import re
import subprocess
import threading
import time
from enum import Enum
from typing import Optional

log = logging.getLogger(__name__)


class SolverState(str, Enum):
    IDLE = "idle"
    RUNNING = "running"
    FINISHED = "finished"
    ERROR = "error"


# Regex to extract OpenFOAM residual lines like:
#   smoothSolver:  Solving for Ux, Initial residual = 0.123, Final residual = 0.001, No Iterations 5
_RESIDUAL_RE = re.compile(
    r"Solving for (\w+),\s+Initial residual = ([0-9.eE+-]+),\s+"
    r"Final residual = ([0-9.eE+-]+),\s+No Iterations (\d+)"
)

# Regex to extract iteration number:
#   Time = 100   (transient)  or  Iteration = 100  (steady)
_ITERATION_RE = re.compile(r"(?:Time|Iteration)\s*=\s*([0-9.eE+-]+)")


class SolverMonitor:
    """Non-Qt replacement for CaseManager's solver lifecycle tracking.

    Thread-safe:  Flask request threads write via ``attach()`` / ``stop()``,
    the WebSocket thread reads via ``read_next_log_line()``.
    """

    def __init__(self):
        self._state = SolverState.IDLE
        self._pid: Optional[int] = None
        self._create_time: Optional[float] = None
        self._case_dir: Optional[str] = None
        self._log_queue: queue.Queue = queue.Queue(maxsize=50_000)
        self._lock = threading.Lock()

        # Residual history for the chart  { field: [(iter, value), ...] }
        self._residual_history: dict[str, list] = {}
        self._current_iteration: float = 0

        self._reader_thread: Optional[threading.Thread] = None
        self._log_path: Optional[str] = None

    # ── attach / stop ─────────────────────────────────────────────────────

    def attach(self, pid: int, create_time: float, case_dir: str):
        """Attach to a solver process already launched by the backend."""
        with self._lock:
            self._pid = pid
            self._create_time = create_time
            self._case_dir = case_dir
            self._state = SolverState.RUNNING
            self._residual_history.clear()
            self._current_iteration = 0
            # Clear queue
            while not self._log_queue.empty():
                try:
                    self._log_queue.get_nowait()
                except queue.Empty:
                    break

        # Start a thread that tails the solver log file
        self._reader_thread = threading.Thread(
            target=self._tail_log, daemon=True, name="solver-log-tail",
        )
        self._reader_thread.start()
        log.info("Attached to solver PID=%d in %s", pid, case_dir)

    def stop(self):
        """Kill the solver process."""
        with self._lock:
            if self._pid is not None:
                try:
                    import psutil
                    proc = psutil.Process(self._pid)
                    proc.terminate()
                    log.info("Terminated solver PID=%d", self._pid)
                except Exception as exc:
                    log.warning("Could not terminate PID=%d: %s", self._pid, exc)
            self._state = SolverState.IDLE
            self._pid = None

    # ── log reading ───────────────────────────────────────────────────────

    def read_next_log_line(self, timeout: float = 1.0) -> Optional[str]:
        try:
            return self._log_queue.get(timeout=timeout)
        except queue.Empty:
            return None

    # ── status ────────────────────────────────────────────────────────────

    def get_status(self) -> dict:
        return {
            "state": self._state.value,
            "pid": self._pid,
            "iteration": self._current_iteration,
        }

    @property
    def residual_history(self) -> dict:
        """{ field_name: [ [iter, initial_residual, final_residual], ... ] }"""
        return dict(self._residual_history)

    # ── internal log tailer ───────────────────────────────────────────────

    def _tail_log(self):
        """Tail the OpenFOAM log file, pushing lines into the queue and
        parsing residuals for the chart."""
        import psutil
        from pathlib import Path

        # OpenFOAM writes logs to <case>/log or stdout captured by MPI.
        # Common locations:
        log_candidates = [
            Path(self._case_dir) / "log",
            Path(self._case_dir) / "log.simpleFoam",
            Path(self._case_dir) / "log.pimpleFoam",
        ]

        # Wait for log file to appear (solver may take a moment to start)
        log_file = None
        for _ in range(30):  # up to 30 seconds
            for candidate in log_candidates:
                if candidate.exists():
                    log_file = candidate
                    break
            # Also try any log.* file
            if log_file is None:
                for f in Path(self._case_dir).glob("log.*"):
                    log_file = f
                    break
            if log_file:
                break
            time.sleep(1.0)

        if log_file is None:
            # Fallback: just monitor process status without log
            self._monitor_pid_only()
            return

        log.info("Tailing log file: %s", log_file)
        with open(log_file, "r") as fh:
            while True:
                line = fh.readline()
                if line:
                    line = line.rstrip("\n\r")
                    self._process_log_line(line)
                    try:
                        self._log_queue.put_nowait(line)
                    except queue.Full:
                        pass  # drop oldest silently
                else:
                    # No new data — check if process is still alive
                    if not self._is_pid_alive():
                        self._finalise()
                        break
                    time.sleep(0.2)

    def _monitor_pid_only(self):
        """If no log file found, just wait for the process to exit."""
        while self._is_pid_alive():
            time.sleep(1.0)
        self._finalise()

    def _is_pid_alive(self) -> bool:
        if self._pid is None:
            return False
        try:
            import psutil
            proc = psutil.Process(self._pid)
            return proc.is_running() and proc.create_time() == self._create_time
        except Exception:
            return False

    def _finalise(self):
        with self._lock:
            if self._state == SolverState.RUNNING:
                self._state = SolverState.FINISHED
                log.info("Solver finished (PID=%s)", self._pid)

    def _process_log_line(self, line: str):
        """Parse a single solver output line for iteration/residual data."""
        # Check for iteration marker
        m = _ITERATION_RE.search(line)
        if m:
            self._current_iteration = float(m.group(1))

        # Check for residual data
        m = _RESIDUAL_RE.search(line)
        if m:
            field = m.group(1)
            initial_res = float(m.group(2))
            final_res = float(m.group(3))
            if field not in self._residual_history:
                self._residual_history[field] = []
            self._residual_history[field].append([
                self._current_iteration, initial_res, final_res,
            ])
