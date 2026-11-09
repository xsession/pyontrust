"""Waveforms GUI backend — Digilent WaveForms clone (scope + spectrum + gen).

Wraps :class:`pyontrust.instruments.dwf_waveforms.WaveformDevice` behind a
small JSON API for the ``/waveforms`` web tab:

- ``GET  /api/devices``            enumerate DWF devices (USB/network)
- ``POST /api/scope/capture``      one-shot scope capture, decimated + stats
- ``POST /api/scope/spectrum``     FFT spectrum of a capture (peaks included)
- ``POST /api/gen/configure|start|stop``  signal generator (devices with analog out)

Device handles are kept open in a small session registry (open-on-first-use,
closed after an idle timeout) so repeated captures don't re-open the USB
device. Devices without analog outputs (e.g. Analog Discovery 3) report a
clean "not available" on generator endpoints — never simulated output.
"""
from __future__ import annotations

import logging
import threading
import time
from pathlib import Path
from typing import Any, Optional

import numpy as np
from flask import Blueprint, Response, jsonify, request, send_from_directory

logger = logging.getLogger("pyontrust.gateway.waveforms")

_WEB_DIR = Path(__file__).resolve().parent.parent / "web" / "waveforms"
bp = Blueprint(
    "waveforms", __name__, static_folder=str(_WEB_DIR), static_url_path="/static",
)

# ── Limits ─────────────────────────────────────────────────────────────
MAX_POINTS_PER_CHANNEL = 2048      # decimation target for the web plot
MAX_RATE_HZ = 5_000_000.0          # AD3 max analog-in rate
MIN_RECORD_S = 0.001
MAX_RECORD_S = 60.0
IDLE_CLOSE_S = 300.0               # close unused device handles after 5 min

# ── Device session registry ────────────────────────────────────────────


class _Session:
    __slots__ = ("device", "lock", "last_used")

    def __init__(self, device: Any) -> None:
        self.device = device
        self.lock = threading.Lock()   # serialize configure→read per handle
        self.last_used = time.monotonic()


_REGISTRY: dict[int, _Session] = {}
_REGISTRY_LOCK = threading.Lock()


def _resolve_index(device_index: int) -> int:
    """Map -1 (first device) to a concrete index; validate the rest."""
    if device_index == -1:
        from pyontrust.instruments.dwf_waveforms import enumerate_devices

        devs = enumerate_devices()
        if not devs:
            raise _NoDeviceError("no DWF devices found")
        return int(devs[0].index)
    return int(device_index)


class _NoDeviceError(RuntimeError):
    pass


def _get_session(device_index: int) -> _Session:
    from pyontrust.instruments.dwf_waveforms import WaveformDevice

    with _REGISTRY_LOCK:
        # reap idle sessions first (cheap; keeps the registry bounded)
        now = time.monotonic()
        for idx in [i for i, s in _REGISTRY.items() if now - s.last_used > IDLE_CLOSE_S]:
            try:
                _REGISTRY[idx].device.close()
            except Exception:  # noqa: BLE001 — best-effort close
                logger.warning("waveforms: idle close failed for device %s", idx)
            del _REGISTRY[idx]

        sess = _REGISTRY.get(device_index)
        if sess is None:
            dev = WaveformDevice(index=device_index)
            dev.open()  # raises DwfError with the SDK's message on failure
            sess = _Session(dev)
            _REGISTRY[device_index] = sess
            logger.info("waveforms: opened device index=%d", device_index)
        sess.last_used = time.monotonic()
        return sess


def _touch(sess: _Session) -> None:
    with _REGISTRY_LOCK:
        sess.last_used = time.monotonic()


# ── Helpers ────────────────────────────────────────────────────────────


def _json_body() -> dict[str, Any]:
    return request.get_json(silent=True) or {}


def _clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


def _decimate(samples: list[float], max_points: int = MAX_POINTS_PER_CHANNEL) -> list[float]:
    """Min/max bucket decimation — preserves peaks the way a scope does."""
    n = len(samples)
    if n <= max_points:
        return samples
    arr = np.asarray(samples, dtype=np.float64)
    nbuckets = max(1, max_points // 2)   # each bucket emits one min+max pair
    nb = int(np.ceil(n / nbuckets))
    out: list[float] = []
    for start in range(0, n, nb):
        chunk = arr[start:start + nb]
        out.append(float(chunk.min()))
        out.append(float(chunk.max()))
    return out[:max_points]


def _channel_stats(samples: np.ndarray, rate_hz: float) -> dict[str, Any]:
    """Per-channel measurements incl. a dominant-frequency estimate."""
    n = int(samples.size)
    if n == 0:
        return {"n": 0}
    mean = float(np.mean(samples))
    rms = float(np.sqrt(np.mean((samples - mean) ** 2)))
    vpp = float(np.max(samples) - np.min(samples))

    # Dominant frequency via FFT peak (skip DC bin).
    freq_hz: Optional[float] = None
    if n >= 16 and rate_hz > 0:
        windowed = samples * np.hanning(n)
        spec = np.abs(np.fft.rfft(windowed))
        k = int(np.argmax(spec[1:]) + 1)
        freq_hz = float(k * rate_hz / n)

    return {
        "n": n,
        "min_v": round(float(np.min(samples)), 6),
        "max_v": round(float(np.max(samples)), 6),
        "mean_v": round(mean, 6),
        "rms_v": round(rms, 6),
        "vpp_v": round(vpp, 6),
        "freq_hz": round(freq_hz, 3) if freq_hz is not None else None,
    }


def _capture(
    sess: _Session,
    channels: list[int],
    rate_hz: float,
    record_s: float,
    range_v: dict[str, float],
    trigger_source: str,
    trigger_level_v: float,
) -> tuple[dict[str, Any], dict[int, np.ndarray]]:
    """Configure → start → wait → read. Returns (capture_meta, {ch: samples})."""
    dev = sess.device
    t0 = time.monotonic()

    with sess.lock:
        dev.scope_configure(
            channels=tuple(channels),
            rate_hz=rate_hz,
            record_s=record_s,
            range_v={int(k): float(v) for k, v in range_v.items()},
            trigger_source=trigger_source,
            trigger_level_v=trigger_level_v,
        )
        time.sleep(0.15)  # front-end settle (per official DWF sample)
        dev.scope_start()
        done = dev.scope_wait_done(timeout_s=max(3.0, record_s * 4 + 2.0))
        if not done:
            raise RuntimeError(f"capture did not finish (state={dev.scope_state()})")

        data: dict[int, np.ndarray] = {}
        for ch in channels:
            raw = dev.scope_read(channel=ch)
            if not raw:
                raise RuntimeError(f"device returned no samples on channel {ch}")
            data[ch] = np.asarray(raw, dtype=np.float64)

    elapsed_ms = round((time.monotonic() - t0) * 1000.0, 1)
    meta = {
        "rate_hz": rate_hz,
        "record_s": record_s,
        "samples_total": int(sum(len(v) for v in data.values())),
        "elapsed_ms": elapsed_ms,
    }
    return meta, data


# ── Routes ─────────────────────────────────────────────────────────────


@bp.route("/")
def index() -> Response:
    return send_from_directory(str(_WEB_DIR), "index.html")


@bp.route("/api/devices")
def devices() -> Response:
    from pyontrust.instruments.dwf_waveforms import DwfError, enumerate_devices

    try:
        devs = enumerate_devices()
    except DwfError as exc:
        return jsonify({"ok": False, "error": str(exc), "devices": []}), 503

    out = [d.to_dict() for d in devs]
    # expose generator availability explicitly so the UI can gate on it
    for d in out:
        d["has_analog_out"] = int(d.get("analog_out_channels", 0)) > 0
    return jsonify({"ok": True, "devices": out})


@bp.route("/api/scope/capture", methods=["POST"])
def scope_capture() -> Response:
    from pyontrust.instruments.dwf_waveforms import DwfError

    body = _json_body()
    try:
        device_index = int(body.get("device_index", -1))
        channels = [int(c) for c in (body.get("channels") or [0])]
        rate_hz = _clamp(float(body.get("rate_hz", 250_000.0)), 1e3, MAX_RATE_HZ)
        record_s = _clamp(float(body.get("record_s", 0.04)), MIN_RECORD_S, MAX_RECORD_S)
        range_v = {str(k): float(v) for k, v in (body.get("range_v") or {}).items()}
        trigger_source = str(body.get("trigger_source", "none"))
        trigger_level_v = float(body.get("trigger_level_v", 0.0))
    except (TypeError, ValueError) as exc:
        return jsonify({"ok": False, "error": f"bad request body: {exc}"}), 400

    if not channels:
        return jsonify({"ok": False, "error": "channels must be a non-empty list"}), 400

    try:
        idx = _resolve_index(device_index)
        sess = _get_session(idx)
        meta, data = _capture(
            sess, channels, rate_hz, record_s, range_v, trigger_source, trigger_level_v,
        )
    except (_NoDeviceError, DwfError) as exc:
        return jsonify({"ok": False, "error": str(exc)}), 503
    except RuntimeError as exc:
        return jsonify({"ok": False, "error": str(exc)}), 502

    _touch(sess)
    ch_out = []
    for ch in channels:
        arr = data[ch]
        dec = _decimate(arr.tolist())
        ch_out.append({
            "channel": int(ch),
            "points": len(dec),
            "data": [round(v, 6) for v in dec],
            "stats": _channel_stats(arr, rate_hz),
        })

    logger.info(
        "waveforms capture: dev=%d ch=%s %.0fHz x%.3fs -> %d pts (%.1fms)",
        idx, channels, rate_hz, record_s, meta["samples_total"], meta["elapsed_ms"],
    )
    return jsonify({"ok": True, "device_index": idx, "capture": meta, "channels": ch_out})


@bp.route("/api/scope/spectrum", methods=["POST"])
def scope_spectrum() -> Response:
    from pyontrust.instruments.dwf_waveforms import DwfError

    body = _json_body()
    try:
        device_index = int(body.get("device_index", -1))
        channel = int(body.get("channel", 0))
        rate_hz = _clamp(float(body.get("rate_hz", 250_000.0)), 1e3, MAX_RATE_HZ)
        record_s = _clamp(float(body.get("record_s", 0.04)), MIN_RECORD_S, MAX_RECORD_S)
    except (TypeError, ValueError) as exc:
        return jsonify({"ok": False, "error": f"bad request body: {exc}"}), 400

    try:
        idx = _resolve_index(device_index)
        sess = _get_session(idx)
        _, data = _capture(sess, [channel], rate_hz, record_s, {}, "none", 0.0)
    except (_NoDeviceError, DwfError) as exc:
        return jsonify({"ok": False, "error": str(exc)}), 503
    except RuntimeError as exc:
        return jsonify({"ok": False, "error": str(exc)}), 502

    _touch(sess)
    samples = data[channel] - float(np.mean(data[channel]))  # remove DC for the spectrum
    n = int(samples.size)
    windowed = samples * np.hanning(n)
    spec = np.abs(np.fft.rfft(windowed)) / (n / 2.0)          # V amplitude per bin
    freqs = np.fft.rfftfreq(n, d=1.0 / rate_hz)

    # top peaks: local maxima above 5% of the strongest, min 3 bins apart
    order = np.argsort(spec)[::-1]
    peaks: list[dict[str, Any]] = []
    used = set()
    for k in order[:64]:
        if spec[k] < 0.05 * spec.max():
            break
        if any(abs(int(k) - u) < 3 for u in used):
            continue
        used.add(int(k))
        peaks.append({"freq_hz": round(float(freqs[k]), 2), "amp_v": round(float(spec[k]), 6)})
    peaks.sort(key=lambda p: p["freq_hz"])

    # downsample the grid to <=1024 points for transport
    step = max(1, int(np.ceil(len(freqs) / 1024)))
    return jsonify({
        "ok": True,
        "device_index": idx,
        "channel": channel,
        "rate_hz": rate_hz,
        "record_s": record_s,
        "n_samples": n,
        "freqs": [round(float(v), 3) for v in freqs[::step]],
        "magnitudes": [round(float(v), 6) for v in spec[::step]],
        "peaks": peaks[:12],
    })


def _gen_available(sess: _Session, device_index: int) -> tuple[bool, str]:
    from pyontrust.instruments.dwf_waveforms import DwfError, enumerate_devices

    try:
        devs = {d.index: d for d in enumerate_devices()}
    except DwfError as exc:
        return False, str(exc)
    dev = devs.get(device_index)
    if dev is None:
        return False, f"device index {device_index} not found"
    if int(dev.analog_out_channels or 0) == 0:
        return False, (
            f"{dev.name} has no analog outputs — signal generation is not "
            "available on this device"
        )
    return True, ""


@bp.route("/api/gen/configure", methods=["POST"])
def gen_configure() -> Response:
    from pyontrust.instruments.dwf_waveforms import DwfError

    body = _json_body()
    try:
        device_index = int(body.get("device_index", -1))
        channel = int(body.get("channel", 0))
        function = str(body.get("function", "sine"))
        freq_hz = float(body.get("freq_hz", 1_000.0))
        amplitude_v = float(body.get("amplitude_v", 1.41))
        offset_v = float(body.get("offset_v", 0.0))
    except (TypeError, ValueError) as exc:
        return jsonify({"ok": False, "error": f"bad request body: {exc}"}), 400

    try:
        idx = _resolve_index(device_index)
        sess = _get_session(idx)
    except (_NoDeviceError, DwfError) as exc:
        return jsonify({"ok": False, "error": str(exc)}), 503

    ok, why = _gen_available(sess, idx)
    if not ok:
        return jsonify({"ok": False, "error": why}), 409

    with sess.lock:
        try:
            sess.device.gen_set(
                channel=channel, function=function, freq_hz=freq_hz,
                amplitude_v=amplitude_v, offset_v=offset_v,
            )
        except DwfError as exc:
            return jsonify({"ok": False, "error": str(exc)}), 502
    _touch(sess)
    logger.info("waveforms gen configure: dev=%d ch=%d %s %.1fHz", idx, channel, function, freq_hz)
    return jsonify({
        "ok": True, "device_index": idx, "channel": channel,
        "function": function, "freq_hz": freq_hz,
        "amplitude_v": amplitude_v, "offset_v": offset_v, "started": False,
    })


@bp.route("/api/gen/start", methods=["POST"])
def gen_start() -> Response:
    from pyontrust.instruments.dwf_waveforms import DwfError

    body = _json_body()
    try:
        device_index = int(body.get("device_index", -1))
        channels = [int(c) for c in (body.get("channels") or [0])]
    except (TypeError, ValueError) as exc:
        return jsonify({"ok": False, "error": f"bad request body: {exc}"}), 400

    try:
        idx = _resolve_index(device_index)
        sess = _get_session(idx)
    except (_NoDeviceError, DwfError) as exc:
        return jsonify({"ok": False, "error": str(exc)}), 503

    ok, why = _gen_available(sess, idx)
    if not ok:
        return jsonify({"ok": False, "error": why}), 409

    with sess.lock:
        try:
            sess.device.gen_start(channels=tuple(channels))
        except DwfError as exc:
            return jsonify({"ok": False, "error": str(exc)}), 502
    _touch(sess)
    logger.info("waveforms gen start: dev=%d ch=%s", idx, channels)
    return jsonify({"ok": True, "device_index": idx, "channels": channels, "started": True})


@bp.route("/api/gen/stop", methods=["POST"])
def gen_stop() -> Response:
    from pyontrust.instruments.dwf_waveforms import DwfError

    body = _json_body()
    try:
        device_index = int(body.get("device_index", -1))
        channels = [int(c) for c in (body.get("channels") or [0])]
    except (TypeError, ValueError) as exc:
        return jsonify({"ok": False, "error": f"bad request body: {exc}"}), 400

    try:
        idx = _resolve_index(device_index)
        sess = _get_session(idx)
    except (_NoDeviceError, DwfError) as exc:
        return jsonify({"ok": False, "error": str(exc)}), 503

    ok, why = _gen_available(sess, idx)
    if not ok:
        return jsonify({"ok": False, "error": why}), 409

    with sess.lock:
        try:
            sess.device.gen_stop(channels=tuple(channels))
        except DwfError as exc:
            return jsonify({"ok": False, "error": str(exc)}), 502
    _touch(sess)
    logger.info("waveforms gen stop: dev=%d ch=%s", idx, channels)
    return jsonify({"ok": True, "device_index": idx, "channels": channels, "started": False})


@bp.route("/api/state")
def state() -> Response:
    with _REGISTRY_LOCK:
        open_devs = sorted(_REGISTRY.keys())
    return jsonify({
        "ok": True,
        "open_devices": open_devs,
        "idle_close_s": IDLE_CLOSE_S,
        "max_points_per_channel": MAX_POINTS_PER_CHANNEL,
    })
