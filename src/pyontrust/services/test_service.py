"""Test campaign management service.

Wraps :class:`~pyontrust.core.runner.PowerTestRunner` and the profile
system with a stateful campaign model that the gateway can query for
run/stop/status/history.
"""
from __future__ import annotations

import enum
import json
import logging
import pathlib
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Callable

from pyontrust.core.models import PowerTest, TestArtifacts
from pyontrust.core.runner import PowerTestRunner
from pyontrust.core.profiles import Profile, load_profile, run_profile

logger = logging.getLogger("pyontrust.services.test_service")


class RunState(enum.Enum):
    IDLE = "idle"
    RUNNING = "running"
    STOPPING = "stopping"
    FINISHED = "finished"
    ERROR = "error"


@dataclass
class RunRecord:
    """Immutable snapshot of a completed (or failed) test run."""

    run_id: str
    profile_name: str
    state: RunState
    started_at: float
    finished_at: float | None = None
    artifacts_dir: str | None = None
    error: str | None = None
    meta: dict[str, Any] = field(default_factory=dict)


class TestService:
    """Manages test campaigns — start / stop / status / history.

    Thread-safe: runs execute on a background thread; the gateway can
    poll ``status()`` or ``history()`` concurrently.
    """

    def __init__(
        self,
        artifacts_root: str | pathlib.Path = "artifacts",
        max_history: int = 200,
    ) -> None:
        self._artifacts_root = pathlib.Path(artifacts_root)
        self._max_history = max_history

        self._lock = threading.Lock()
        self._state = RunState.IDLE
        self._current_thread: threading.Thread | None = None
        self._current_profile: str | None = None
        self._stop_requested = threading.Event()

        self._history: list[RunRecord] = []
        self._on_state_change: list[Callable[[RunState, dict[str, Any]], None]] = []

    # ── Public API ──────────────────────────────────────────────────

    def status(self) -> dict[str, Any]:
        """Return current run status (thread-safe)."""
        with self._lock:
            return {
                "state": self._state.value,
                "profile": self._current_profile,
                "history_count": len(self._history),
            }

    def history(self, limit: int = 50) -> list[dict[str, Any]]:
        """Return recent run history (newest first)."""
        with self._lock:
            records = list(reversed(self._history[-limit:]))
        return [
            {
                "run_id": r.run_id,
                "profile": r.profile_name,
                "state": r.state.value,
                "started_at": r.started_at,
                "finished_at": r.finished_at,
                "artifacts_dir": r.artifacts_dir,
                "error": r.error,
            }
            for r in records
        ]

    def start_profile(
        self,
        profile_path: str,
        *,
        bench_overrides: dict[str, Any] | None = None,
        meta: dict[str, Any] | None = None,
    ) -> dict[str, str]:
        """Start a test profile on a background thread.

        Returns ``{"run_id": ..., "state": "running"}`` immediately.
        """
        with self._lock:
            if self._state == RunState.RUNNING:
                return {"error": "A test is already running", "state": self._state.value}
            self._state = RunState.RUNNING
            self._stop_requested.clear()
            self._current_profile = profile_path

        run_id = f"{int(time.time())}_{pathlib.Path(profile_path).stem}"

        def _worker() -> None:
            record = RunRecord(
                run_id=run_id,
                profile_name=profile_path,
                state=RunState.RUNNING,
                started_at=time.time(),
                meta=meta or {},
            )
            try:
                result = run_profile(
                    profile_path,
                    artifacts_root=str(self._artifacts_root),
                )
                record.artifacts_dir = str(result) if result else None
                record.state = RunState.FINISHED
            except Exception as exc:
                logger.exception("Profile run failed: %s", exc)
                record.state = RunState.ERROR
                record.error = str(exc)
            finally:
                record.finished_at = time.time()
                with self._lock:
                    self._state = record.state
                    self._history.append(record)
                    if len(self._history) > self._max_history:
                        self._history = self._history[-self._max_history:]
                    self._current_profile = None
                self._fire_state_change(record.state, {"run_id": run_id})

        t = threading.Thread(target=_worker, name=f"test-{run_id}", daemon=True)
        t.start()
        with self._lock:
            self._current_thread = t

        self._fire_state_change(RunState.RUNNING, {"run_id": run_id})
        return {"run_id": run_id, "state": RunState.RUNNING.value}

    def start_test(
        self,
        test: PowerTest,
        instruments: dict[str, Any],
        *,
        recorders: list[Any] | None = None,
        meta: dict[str, Any] | None = None,
    ) -> dict[str, str]:
        """Start a PowerTest directly (non-profile path)."""
        with self._lock:
            if self._state == RunState.RUNNING:
                return {"error": "A test is already running", "state": self._state.value}
            self._state = RunState.RUNNING
            self._stop_requested.clear()
            self._current_profile = test.name

        run_id = f"{int(time.time())}_{test.name}"
        runner = PowerTestRunner(artifacts_root=str(self._artifacts_root))

        def _worker() -> None:
            record = RunRecord(
                run_id=run_id,
                profile_name=test.name,
                state=RunState.RUNNING,
                started_at=time.time(),
                meta=meta or {},
            )
            try:
                artifacts = runner.run(
                    test, instruments,
                    recorders=recorders, meta=meta,
                )
                record.artifacts_dir = str(artifacts.root_dir)
                record.state = RunState.FINISHED
            except Exception as exc:
                logger.exception("Test run failed: %s", exc)
                record.state = RunState.ERROR
                record.error = str(exc)
            finally:
                record.finished_at = time.time()
                with self._lock:
                    self._state = record.state
                    self._history.append(record)
                    self._current_profile = None
                self._fire_state_change(record.state, {"run_id": run_id})

        t = threading.Thread(target=_worker, name=f"test-{run_id}", daemon=True)
        t.start()
        with self._lock:
            self._current_thread = t
        return {"run_id": run_id, "state": RunState.RUNNING.value}

    def request_stop(self) -> dict[str, str]:
        """Request that the current run stop gracefully."""
        with self._lock:
            if self._state != RunState.RUNNING:
                return {"state": self._state.value, "message": "Not running"}
            self._state = RunState.STOPPING
        self._stop_requested.set()
        return {"state": RunState.STOPPING.value, "message": "Stop requested"}

    def on_state_change(self, cb: Callable[[RunState, dict[str, Any]], None]) -> None:
        """Register a callback for state transitions."""
        self._on_state_change.append(cb)

    # ── Internals ───────────────────────────────────────────────────

    def _fire_state_change(self, state: RunState, info: dict[str, Any]) -> None:
        for cb in self._on_state_change:
            try:
                cb(state, info)
            except Exception:
                logger.debug("State change callback error", exc_info=True)
