"""Self-tests — "is this station able to do its job right now?".

Each provider returns a list of checks::

    {"name": "...", "status": "pass" | "warn" | "fail", "detail": "..."}

Providers are referenced from the tool registry (``Tool.selftest``) plus a
``station`` provider for the gateway itself.  :func:`run_all` runs them in
parallel with a per-provider timeout so one hung driver cannot stall the
health page.
"""
from __future__ import annotations

import concurrent.futures as cf
import importlib.util
import os
import shutil
import stat
import time
from typing import Any, Callable

Check = dict[str, str]
TIMEOUT_S = 12.0


def _c(name: str, status: str, detail: str = "") -> Check:
    return {"name": name, "status": status, "detail": detail}


def _has(module: str) -> bool:
    return importlib.util.find_spec(module) is not None


# ── providers ───────────────────────────────────────────────────────────

def station() -> list[Check]:
    from pyontrust.gateway import context
    from pyontrust.gateway.security import token_path

    checks: list[Check] = []
    d = context.data_dir()
    probe = d / ".write_test"
    try:
        probe.write_text("ok"); probe.unlink()
        checks.append(_c("Data directory writable", "pass", str(d)))
    except OSError as exc:
        checks.append(_c("Data directory writable", "fail", f"{d}: {exc}"))
    free_gb = shutil.disk_usage(d).free / 1e9
    checks.append(_c("Free disk space", "fail" if free_gb < 1 else "warn" if free_gb < 5 else "pass",
                     f"{free_gb:.1f} GB free"))
    checks.append(_c("Production web server", "pass" if _has("waitress") else "warn",
                     "waitress installed" if _has("waitress") else "pip install waitress (dev server in use)"))
    tp = token_path()
    if tp.exists():
        loose = tp.stat().st_mode & (stat.S_IRWXG | stat.S_IRWXO)
        checks.append(_c("Station token file permissions", "warn" if loose else "pass",
                         f"{tp} is readable by other users — chmod 600" if loose else "owner-only"))
    if os.environ.get("PYONTRUST_REMOTE_NO_AUTH") == "1":
        checks.append(_c("Remote authentication", "fail", "PYONTRUST_REMOTE_NO_AUTH=1 — network clients are not authenticated"))
    from pyontrust.gateway.blueprints.station import audit_log, instruments

    v = audit_log().verify()
    checks.append(_c("Audit log integrity", "pass" if v["ok"] else "fail",
                     f"{v['entries']} entries, chain intact" if v["ok"] else f"{v.get('error')} (entry {v.get('seq')})"))
    s = instruments().summary()
    if s["overdue"]:
        checks.append(_c("Instrument calibration", "fail", f"{s['overdue']} instrument(s) overdue"))
    elif s["due_soon"]:
        checks.append(_c("Instrument calibration", "warn", f"{s['due_soon']} instrument(s) due within 30 days"))
    else:
        checks.append(_c("Instrument calibration", "pass", f"{s['ok']} in calibration"))
    return checks


def thermal() -> list[Check]:
    checks = [_c("pyusb (libseek driver)", "pass" if _has("usb") else "fail",
                 "" if _has("usb") else "pip install pyusb"),
              _c("OpenCV", "pass" if _has("cv2") else "fail", "" if _has("cv2") else "pip install opencv-python")]
    if _has("usb"):
        from pyontrust.instruments.libseek_driver import default_flat_field_path, detect_camera
        cam = detect_camera()
        checks.append(_c("Seek Thermal camera", "pass" if cam else "warn",
                         f"{cam} detected on USB" if cam else "not connected (USB 289D)"))
        checks.append(_c("Flat-field correction", "pass" if default_flat_field_path(cam or "compact").is_file() else "warn",
                         "captured" if default_flat_field_path(cam or "compact").is_file() else "not captured — image shows a fixed pattern"))
    from pyontrust.instruments import thermal_calibration as tcal
    info = tcal.load_info()
    checks.append(_c("One-point calibration", "pass" if info.get("calibrated") else "warn",
                     f"offset {info.get('offset_c', 0):+.2f} °C" if info.get("calibrated") else "none — absolute °C are estimates"))
    return checks


def micro() -> list[Check]:
    checks = [_c("OpenCV", "pass" if _has("cv2") else "fail", "" if _has("cv2") else "pip install opencv-python")]
    from pyontrust.instruments import phone_camera as pc
    if not shutil.which("adb"):
        checks.append(_c("adb (phone cameras)", "warn", "Android platform-tools not installed"))
        return checks
    phones = pc.list_phones()
    ready = [p for p in phones if p.ready]
    checks.append(_c("Android phones", "pass" if ready else "warn",
                     ", ".join(f"{p.label} ({p.state})" for p in phones) or "none connected"))
    for p in phones:
        if not p.ready:
            checks.append(_c(f"Phone {p.serial}", "warn", p.hint))
    return checks


def can() -> list[Check]:
    if not _has("can"):
        return [_c("python-can", "fail", "pip install python-can")]
    from pyontrust.services.can_service import CanDiagService
    iface, chan = CanDiagService.detect_default()
    return [_c("python-can", "pass"),
            _c("CAN interface", "pass" if iface != "virtual" else "warn",
               f"{iface} / {chan}" if iface != "virtual" else "no hardware adapter — virtual bus only")]


def waveforms() -> list[Check]:
    from pyontrust.instruments.dwf_loader import find_dwf_library
    lib = find_dwf_library()
    return [_c("Digilent WaveForms runtime (libdwf)", "pass" if lib else "fail",
               str(lib) if lib else "install Digilent WaveForms / Adept runtime")]


def flowlab() -> list[Check]:
    from pyontrust.gateway.flowlab_engine import unsafe_blocks_enabled
    return [_c("Shell / HTTP blocks", "warn" if unsafe_blocks_enabled() else "pass",
               "ENABLED (PYONTRUST_FLOWLAB_UNSAFE=1) — diagrams can run commands"
               if unsafe_blocks_enabled() else "disabled (safe default)")]


def hil() -> list[Check]:
    from flask import current_app
    svc = current_app.extensions.get("test_service")
    return [_c("HIL test service", "pass" if svc else "fail", "running" if svc else "not initialised")]


# ── runner ──────────────────────────────────────────────────────────────

def providers() -> dict[str, Callable[[], list[Check]]]:
    from pyontrust.gateway import tools

    out: dict[str, Callable[[], list[Check]]] = {"station": station}
    for t in tools.TOOLS:
        if t.selftest:
            out[t.id] = tools.load(t.selftest)
    return out


def run_all(only: str | None = None) -> dict[str, Any]:
    """Run providers in parallel (each in the caller's app context)."""
    from flask import copy_current_request_context, has_request_context

    selected = {k: v for k, v in providers().items() if only in (None, k)}
    results: dict[str, Any] = {}
    t0 = time.time()

    def wrap(fn: Callable[[], list[Check]]) -> Callable[[], list[Check]]:
        return copy_current_request_context(fn) if has_request_context() else fn

    ex = cf.ThreadPoolExecutor(max_workers=max(1, len(selected)), thread_name_prefix="selftest")
    try:
        futs = {k: ex.submit(wrap(fn)) for k, fn in selected.items()}
        for key, fut in futs.items():
            try:
                checks = fut.result(timeout=max(0.1, TIMEOUT_S - (time.time() - t0)))
            except cf.TimeoutError:
                checks = [_c("Self-test", "fail", f"timed out after {TIMEOUT_S:.0f} s")]
            except Exception as exc:  # a broken provider is itself a finding
                checks = [_c("Self-test", "fail", f"{type(exc).__name__}: {exc}")]
            worst = "fail" if any(c["status"] == "fail" for c in checks) else \
                    "warn" if any(c["status"] == "warn" for c in checks) else "pass"
            results[key] = {"status": worst, "checks": checks}
    finally:
        # Never wait for a hung provider (a `with` block would).
        ex.shutdown(wait=False, cancel_futures=True)
    overall = "fail" if any(r["status"] == "fail" for r in results.values()) else \
              "warn" if any(r["status"] == "warn" for r in results.values()) else "pass"
    return {"status": overall, "elapsed_s": round(time.time() - t0, 2), "results": results}
