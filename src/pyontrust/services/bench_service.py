"""Hardware discovery and lab-bench management service.

Wraps :class:`~pyontrust.core.lab_bench.LabBench` with discovery /
health-check / status APIs that the gateway polls.
"""
from __future__ import annotations

import json
import logging
import os
import pathlib
from typing import Any

from pyontrust.core.lab_bench import InstrumentConfig, LabBench
from pyontrust.instruments import create_instrument, discover_instruments

logger = logging.getLogger("pyontrust.services.bench_service")

_ENV_BENCH = "PYONTRUST_BENCH"
_DEFAULT_BENCH_PATH = "benches/default.json"


class BenchService:
    """Manages the lab-bench configuration and instrument lifecycle.

    Usage::

        svc = BenchService()
        svc.load()                   # load from env / default path
        status = svc.instrument_status()
        meter  = svc.get_instrument("power_meter")
    """

    def __init__(self, bench_path: str | pathlib.Path | None = None) -> None:
        self._bench_path: pathlib.Path | None = None
        if bench_path:
            self._bench_path = pathlib.Path(bench_path)
        self._bench: LabBench | None = None
        self._instruments: dict[str, Any] = {}
        self._instrument_errors: dict[str, str] = {}

    @property
    def bench(self) -> LabBench | None:
        return self._bench

    # ── Loading ─────────────────────────────────────────────────────

    def load(self, path: str | pathlib.Path | None = None) -> dict[str, Any]:
        """Load a lab-bench JSON config.

        Resolution order:

        1. Explicit *path* argument
        2. ``self._bench_path`` (constructor)
        3. ``PYONTRUST_BENCH`` environment variable
        4. ``benches/default.json``
        """
        if path:
            p = pathlib.Path(path)
        elif self._bench_path:
            p = self._bench_path
        else:
            p = pathlib.Path(os.environ.get(_ENV_BENCH, _DEFAULT_BENCH_PATH))

        if not p.is_file():
            logger.warning("Bench config not found: %s", p)
            return {"error": f"Bench file not found: {p}", "loaded": False}

        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            self._bench = LabBench.from_dict(data)
            self._bench_path = p
            logger.info("Loaded bench config: %s", p)
            return {"loaded": True, "path": str(p), "instruments": len(self._bench.instruments)}
        except Exception as exc:
            logger.exception("Failed to load bench config: %s", p)
            return {"error": str(exc), "loaded": False}

    def save(self, path: str | pathlib.Path | None = None) -> dict[str, Any]:
        """Save current bench config to disk."""
        if self._bench is None:
            return {"error": "No bench loaded"}
        p = pathlib.Path(path) if path else self._bench_path
        if p is None:
            return {"error": "No path specified"}
        p.parent.mkdir(parents=True, exist_ok=True)
        try:
            p.write_text(
                json.dumps(self._bench.to_dict(), indent=2),
                encoding="utf-8",
            )
            return {"saved": True, "path": str(p)}
        except Exception as exc:
            return {"error": str(exc)}

    # ── Discovery ───────────────────────────────────────────────────

    def discover_available_types(self) -> dict[str, str]:
        """Return all registered instrument type names."""
        return {name: str(ep) for name, ep in discover_instruments().items()}

    # ── Instrument lifecycle ────────────────────────────────────────

    def instantiate_all(self) -> dict[str, Any]:
        """Instantiate all enabled instruments from the bench config."""
        if self._bench is None:
            return {"error": "No bench loaded"}

        self._instruments.clear()
        self._instrument_errors.clear()
        results: dict[str, str] = {}

        for cfg in self._bench.instruments:
            if not cfg.enabled:
                results[cfg.type] = "disabled"
                continue
            try:
                inst = create_instrument(cfg.type, cfg.params)
                self._instruments[cfg.type] = inst
                results[cfg.type] = "ok"
            except Exception as exc:
                self._instrument_errors[cfg.type] = str(exc)
                results[cfg.type] = f"error: {exc}"
                logger.warning("Failed to instantiate %s: %s", cfg.type, exc)

        return results

    def get_instrument(self, name: str) -> Any | None:
        """Return an instantiated instrument by name/type."""
        return self._instruments.get(name)

    def instrument_status(self) -> list[dict[str, Any]]:
        """Return status of all configured instruments."""
        if self._bench is None:
            return []
        statuses: list[dict[str, Any]] = []
        for cfg in self._bench.instruments:
            entry: dict[str, Any] = {
                "type": cfg.type,
                "enabled": cfg.enabled,
                "params": cfg.params,
            }
            if cfg.type in self._instruments:
                inst = self._instruments[cfg.type]
                entry["status"] = "connected"
                # Probe health if the instrument supports it
                if hasattr(inst, "info"):
                    try:
                        info = inst.info()
                        entry["info"] = str(info)
                    except Exception:
                        entry["info"] = "unavailable"
            elif cfg.type in self._instrument_errors:
                entry["status"] = "error"
                entry["error"] = self._instrument_errors[cfg.type]
            else:
                entry["status"] = "not_instantiated"
            statuses.append(entry)
        return statuses

    def close_all(self) -> None:
        """Close all open instruments."""
        for name, inst in list(self._instruments.items()):
            try:
                if hasattr(inst, "close"):
                    inst.close()
            except Exception:
                logger.debug("Error closing %s", name, exc_info=True)
        self._instruments.clear()

    # ── Config access ───────────────────────────────────────────────

    def bench_summary(self) -> dict[str, Any]:
        """Return a JSON-serialisable summary of the bench config."""
        if self._bench is None:
            return {"loaded": False}
        return {
            "loaded": True,
            "path": str(self._bench_path) if self._bench_path else None,
            "instruments": [
                {"type": c.type, "enabled": c.enabled, "params": c.params}
                for c in self._bench.instruments
            ],
        }
