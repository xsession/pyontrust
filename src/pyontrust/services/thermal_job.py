"""Background thermal measurement job (continuous / soak / delta / gradient).

Wraps :func:`pyontrust.analysis.thermal.measurement.run_thermal_measurement`
in a worker thread with progress reporting, abort and a persisted HTML report.
"""
from __future__ import annotations

import logging
import threading
import time
from typing import Any, Callable

logger = logging.getLogger("pyontrust.services.thermal_job")


class MeasurementJob:
    """At most one measurement at a time; progress / result readable any time."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._abort = threading.Event()
        self._thread: threading.Thread | None = None
        self.running = False
        self.result: dict[str, Any] | None = None
        self._progress: dict[str, Any] = self._fresh_progress()

    @staticmethod
    def _fresh_progress(mode: str = "continuous") -> dict[str, Any]:
        return {"frame": 0, "total": 0, "latest_snapshot": None,
                "elapsed_s": 0.0, "mode": mode, "start_time": time.time()}

    # ── control ─────────────────────────────────────────────────────────

    def start(self, config: dict[str, Any],
              before_launch: Callable[[], None] | None = None) -> None:
        """Start a measurement in the background.

        ``running`` flips to True *before* ``before_launch`` runs (e.g. to
        release the live camera), so no other user grabs the device in
        between.  Raises RuntimeError when a measurement is already running.
        """
        with self._lock:
            if self.running:
                raise RuntimeError("Measurement already running")
            self.running = True
        try:
            self._abort.clear()
            self._progress = self._fresh_progress(str(config.get("mode", "continuous")))
            self.result = None
            if before_launch is not None:
                before_launch()
            self._thread = threading.Thread(target=self._run, args=(config,),
                                            name="thermal-measurement", daemon=True)
            self._thread.start()
        except BaseException:
            self.running = False
            raise

    def stop(self) -> bool:
        """Request abort; returns False when nothing is running."""
        if not self.running:
            return False
        self._abort.set()
        return True

    def progress(self) -> dict[str, Any]:
        p = self._progress
        return {
            "running": self.running,
            "frame": p["frame"],
            "total": p["total"],
            "elapsed_s": round(p.get("elapsed_s", 0.0), 1),
            "latest_snapshot": p.get("latest_snapshot"),
        }

    # ── worker ──────────────────────────────────────────────────────────

    def _run(self, config: dict[str, Any]) -> None:
        try:
            from pyontrust.analysis.thermal.measurement import run_thermal_measurement

            def _on_progress(frame_idx: int, total: int, snapshot: dict[str, Any]) -> None:
                p = self._progress
                p.update(frame=frame_idx, total=total, latest_snapshot=snapshot,
                         elapsed_s=time.time() - p["start_time"])
                if self._abort.is_set():
                    raise KeyboardInterrupt("Measurement aborted by user")

            res = run_thermal_measurement(config, progress_cb=_on_progress)
            report_path = res.write_report()
            out = res.to_dict()
            out["report_path"] = str(report_path)
            self.result = out
            logger.info("Thermal measurement complete: %s", "PASS" if res.passed else "FAIL")
        except KeyboardInterrupt:
            logger.info("Thermal measurement aborted by user")
            self.result = {"aborted": True, "message": "Measurement aborted by user"}
        except Exception as exc:
            logger.exception("Thermal measurement failed")
            self.result = {"error": str(exc)}
        finally:
            self.running = False
