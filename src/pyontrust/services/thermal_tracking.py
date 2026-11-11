"""Long-term thermal tracking session — click-selected points & patches.

Designed for electronics-prototype inspection: select interesting pixels or
regions on a live Seek Thermal frame, then record their temperatures over
time (failure detection, component thermal-fluctuation logging).

A :class:`TrackingSession` holds the camera open and samples at a fixed
interval in a background thread.  Each sample computes per-selection stats:

* point -> mean of a small 3x3 neighbourhood around the pixel
* patch -> min / mean / max inside the rectangle

Rows are kept in memory (for plotting) and appended to a CSV file as they
arrive, so a crash mid-session never loses already-recorded data.
"""

from __future__ import annotations

import csv
import logging
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger("pyontrust.services.thermal_tracking")

# Serialises all camera grabs (sampling loop + display grabs) — the libseek
# driver is not thread-safe, so only one grab may be in flight at a time.
_CAMERA_LOCK = threading.Lock()

# Where CSV logs are written (repo-relative when running from the checkout).
_DEFAULT_LOG_DIR = Path(__file__).resolve().parents[3] / "tracking_logs"


@dataclass
class Selection:
    """A user-selected point or rectangular patch on the thermal frame."""

    name: str
    type: str  # "point" | "patch"
    x: int
    y: int
    w: int = 1
    h: int = 1

    def to_dict(self) -> dict[str, Any]:
        return {"name": self.name, "type": self.type,
                "x": self.x, "y": self.y, "w": self.w, "h": self.h}


@dataclass
class TrackingSession:
    """One long-term tracking run over a set of user selections."""

    selections: list[Selection] = field(default_factory=list)
    interval_s: float = 1.0
    running: bool = False
    started_at: float | None = None
    samples: int = 0
    csv_path: Path | None = None
    _thread: threading.Thread | None = None
    _stop_event: threading.Event = field(default_factory=threading.Event)
    _lock: threading.Lock = field(default_factory=threading.Lock)
    # rows: [t_s, <one value per selection column>, frame_min, frame_max]
    _rows: list[list[float]] = field(default_factory=list)
    _camera: Any = None

    # ── lifecycle ────────────────────────────────────────────────────────

    def start(self, selections: list[dict[str, Any]], interval_s: float = 1.0,
              camera_cfg: dict[str, Any] | None = None) -> dict[str, Any]:
        """Open the camera and begin sampling."""
        with self._lock:
            if self.running:
                raise RuntimeError("Tracking session already running")

            sels = [Selection(
                name=str(s.get("name", f"P{i + 1}")),
                type="patch" if str(s.get("type", "point")) == "patch" else "point",
                x=int(s["x"]), y=int(s["y"]),
                w=max(1, int(s.get("w", 1))), h=max(1, int(s.get("h", 1))),
            ) for i, s in enumerate(selections)]
            if not sels:
                raise ValueError("At least one selection is required")

            self.selections = sels
            self.interval_s = max(0.2, float(interval_s))
            self._rows = []
            self.samples = 0
            self.started_at = time.time()
            self._stop_event.clear()

            # Open the camera (real hardware by default).
            from pyontrust.instruments.seek_thermal import create as create_thermal
            cfg = dict(camera_cfg or {})
            cfg.setdefault("mode", "seek")
            cam = create_thermal(cfg)
            cam.open()
            self._camera = cam

            # Prepare the CSV file.
            log_dir = _DEFAULT_LOG_DIR
            log_dir.mkdir(parents=True, exist_ok=True)
            stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            self.csv_path = log_dir / f"thermal_tracking_{stamp}.csv"
            with open(self.csv_path, "w", newline="", encoding="utf-8") as fh:
                writer = csv.writer(fh)
                header = ["timestamp_iso", "t_s"]
                for s in sels:
                    if s.type == "patch":
                        header += [f"{s.name}_min_c", f"{s.name}_mean_c", f"{s.name}_max_c"]
                    else:
                        header.append(f"{s.name}_c")
                header += ["frame_min_c", "frame_max_c"]
                writer.writerow(header)

            self.running = True
            self._thread = threading.Thread(
                target=self._sample_loop, name="thermal-tracking", daemon=True)
            self._thread.start()
            logger.info("Tracking started: %d selections @ %.1fs -> %s",
                        len(sels), self.interval_s, self.csv_path)

        return {"ok": True, "samples": 0, "csv_path": str(self.csv_path)}

    def stop(self) -> dict[str, Any]:
        """Stop sampling and release the camera."""
        with self._lock:
            if not self.running:
                return {"ok": True, "samples": self.samples,
                        "csv_path": str(self.csv_path) if self.csv_path else None}
            self.running = False
            self._stop_event.set()

        thread = self._thread
        if thread is not None and thread.is_alive():
            thread.join(timeout=10.0)
        self._thread = None

        cam = self._camera
        self._camera = None
        if cam is not None:
            try:
                cam.close()
            except Exception as exc:  # pragma: no cover - best effort
                logger.warning("Camera close failed: %s", exc)
        logger.info("Tracking stopped after %d samples -> %s", self.samples, self.csv_path)
        return {"ok": True, "samples": self.samples,
                "csv_path": str(self.csv_path) if self.csv_path else None}

    def grab_for_display(self) -> Any:
        """Grab one frame for the live view, serialized with sampling.

        Only valid while a session is running (camera held open).
        """
        cam = self._camera
        if cam is None:
            raise RuntimeError("No tracking session active")
        with _CAMERA_LOCK:
            return cam.grab_temperature_frame()

    # ── sampling loop ────────────────────────────────────────────────────

    def _sample_loop(self) -> None:
        import numpy as np

        cam = self._camera
        if cam is None:
            return
        while not self._stop_event.is_set():
            t0 = time.time()
            try:
                with _CAMERA_LOCK:
                    frame = cam.grab_temperature_frame()  # deg C, calibration applied
            except Exception as exc:
                logger.warning("Tracking grab failed: %s", exc)
                self._stop_event.wait(2.0)
                continue

            row: list[float] = [round(time.time() - (self.started_at or t0), 3)]
            for s in self.selections:
                if s.type == "patch":
                    y0, x0 = max(0, s.y), max(0, s.x)
                    y1 = min(frame.shape[0], s.y + s.h)
                    x1 = min(frame.shape[1], s.x + s.w)
                    region = frame[y0:y1, x0:x1]
                    if region.size == 0:
                        row += [float("nan")] * 3
                        continue
                    row += [round(float(np.min(region)), 2),
                            round(float(np.mean(region)), 2),
                            round(float(np.max(region)), 2)]
                else:
                    # point -> mean of a small neighbourhood (robust to noise)
                    y0, x0 = max(0, s.y - 1), max(0, s.x - 1)
                    region = frame[y0:min(frame.shape[0], s.y + 2),
                                   x0:min(frame.shape[1], s.x + 2)]
                    row.append(round(float(np.mean(region)), 2))

            row += [round(float(np.min(frame)), 2), round(float(np.max(frame)), 2)]

            with self._lock:
                self._rows.append(row)
                self.samples = len(self._rows)
                # Keep memory bounded for very long runs (plots downsample anyway).
                if len(self._rows) > 200_000:
                    del self._rows[:100_000]

            self._append_csv(row)

            elapsed = time.time() - t0
            wait = max(0.0, self.interval_s - elapsed)
            if wait > 0:
                # Sleep in small slices so stop() stays responsive.
                end = time.time() + wait
                while time.time() < end and not self._stop_event.is_set():
                    time.sleep(min(0.1, max(0.0, end - time.time())))

    def _append_csv(self, row: list[float]) -> None:
        if self.csv_path is None:
            return
        try:
            with open(self.csv_path, "a", newline="", encoding="utf-8") as fh:
                writer = csv.writer(fh)
                ts = datetime.now().isoformat(timespec="milliseconds")
                writer.writerow([ts] + row)
        except OSError as exc:  # pragma: no cover - disk issues
            logger.warning("CSV append failed: %s", exc)

    # ── queries ──────────────────────────────────────────────────────────

    def status(self, max_points: int = 600) -> dict[str, Any]:
        """Running state + latest values + (downsampled) series for plotting."""
        with self._lock:
            rows = list(self._rows)
            sels = [s.to_dict() for s in self.selections]
            running = self.running
            samples = self.samples
            started_at = self.started_at
            csv_path = str(self.csv_path) if self.csv_path else None

        latest: dict[str, Any] = {}
        series: list[list[float]] = []

        if rows:
            last = rows[-1]
            col = 1  # skip t_s
            for s in sels:
                if s["type"] == "patch":
                    latest[s["name"]] = {
                        "min_c": last[col], "mean_c": last[col + 1], "max_c": last[col + 2]}
                    col += 3
                else:
                    latest[s["name"]] = {"c": last[col]}
                    col += 1

            # Downsample to max_points by stride (preserves order & endpoints).
            if len(rows) > max_points:
                stride = -(-len(rows) // max_points)  # ceil division
                rows = rows[::stride]
                if rows[-1] is not self._rows[-1]:
                    rows.append(self._rows[-1])

            for r in rows:
                col = 1
                point_row = [r[0]]
                for s in sels:
                    if s["type"] == "patch":
                        point_row.append(r[col + 1])  # mean line per patch
                        col += 3
                    else:
                        point_row.append(r[col])
                        col += 1
                series.append(point_row)

        return {
            "running": running,
            "samples": samples,
            "elapsed_s": round(time.time() - started_at, 1) if (running and started_at) else None,
            "selections": sels,
            "latest": latest,
            "series": series,
            "csv_path": csv_path,
        }
