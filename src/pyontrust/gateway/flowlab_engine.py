"""FlowLab execution engine — topological dataflow evaluator.

Accepts a serialised diagram (blocks + wires) from the browser,
topologically sorts the blocks, then executes each block in order,
propagating output values along wires to downstream input ports.

Each block type has a registered Python handler that receives:
  - ``params``: the block's user-editable parameters
  - ``inputs``: a dict of {port_name: value} from upstream wires
  - ``ctx``:    shared execution context (console, stop flag, etc.)

And returns:
  - a dict of {output_port_name: value}

All heavy optional imports (numpy, cv2, etc.) are lazy so the engine
works even when only stdlib is available.
"""
from __future__ import annotations

import json
import logging
import math
import os
import pathlib
import subprocess
import time
from collections import defaultdict, deque
from typing import Any, Callable

logger = logging.getLogger("pyontrust.gateway.flowlab_engine")

# Type alias for block handlers
BlockHandler = Callable[[dict[str, Any], dict[str, Any], "ExecContext"], dict[str, Any]]


# ══════════════════════════════════════════════════════════════════════
# Execution context — shared state during one run
# ══════════════════════════════════════════════════════════════════════

class ExecContext:
    """Mutable context passed to every block during execution."""

    def __init__(self) -> None:
        self.console: list[str] = []
        self.stop_requested = False
        self.block_results: dict[str, dict[str, Any]] = {}
        self.start_time = time.time()

    def log(self, msg: str) -> None:
        self.console.append(msg)
        logger.info("[FlowLab] %s", msg)

    @property
    def elapsed(self) -> float:
        return time.time() - self.start_time


# ══════════════════════════════════════════════════════════════════════
# Block handlers
# ══════════════════════════════════════════════════════════════════════

def _blk_simulated_power(params: dict, inputs: dict, ctx: ExecContext) -> dict:
    """Generate a synthetic current trace."""
    import numpy as np

    rate  = float(params.get("sample_rate_hz", 1000))
    dur   = float(params.get("duration_s", 2))
    base  = float(params.get("base_current_a", 0.001))
    noise = float(params.get("noise_a", 0.0001))

    n = int(rate * dur)
    t = np.linspace(0, dur, n)
    current = base + np.random.normal(0, noise, n)

    trace = {"time_s": t.tolist(), "current_a": current.tolist(),
             "sample_rate_hz": rate, "n_samples": n}
    ctx.log(f"📊 Simulated trace: {n} samples, {dur}s @ {rate} Hz")
    return {"trace": trace}


def _blk_csv_file(params: dict, inputs: dict, ctx: ExecContext) -> dict:
    """Load a trace from CSV."""
    path = str(params.get("path", ""))
    time_col = str(params.get("time_col", "time_s"))
    current_col = str(params.get("current_col", "current_a"))

    if not path or not os.path.exists(path):
        ctx.log(f"⚠ CSV file not found: {path}")
        return {"trace": {"time_s": [], "current_a": [], "error": "file_not_found"}}

    import csv
    times, currents = [], []
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                times.append(float(row[time_col]))
                currents.append(float(row[current_col]))
            except (KeyError, ValueError):
                continue
    ctx.log(f"📄 Loaded {len(times)} samples from {path}")
    return {"trace": {"time_s": times, "current_a": currents, "n_samples": len(times)}}


def _blk_aoi_camera(params: dict, inputs: dict, ctx: ExecContext) -> dict:
    """Grab a frame from the AOI camera (simulated or real)."""
    from pyontrust.instruments.aoi_camera import create as create_aoi
    cfg = {
        "mode": str(params.get("mode", "simulated")),
        "width": int(params.get("width", 640)),
        "height": int(params.get("height", 480)),
    }
    cam = create_aoi(cfg)
    cam.open()
    try:
        frame = cam.grab_frame()
        info = cam.info()
        ctx.log(f"📷 AOI frame: {frame.shape} via {info.get('transport','?')}")
        return {"frame": {"shape": list(frame.shape), "dtype": str(frame.dtype),
                          "data_summary": f"{frame.shape[1]}x{frame.shape[0]}"}}
    finally:
        cam.close()


def _blk_seek_thermal(params: dict, inputs: dict, ctx: ExecContext) -> dict:
    """Grab a radiometric frame from the thermal camera."""
    from pyontrust.instruments.seek_thermal import create as create_thermal
    import numpy as np

    cfg = {
        "mode": str(params.get("mode", "simulated")),
        "base_temp_c": float(params.get("base_temp_c", 25)),
        "inject_hotspot": bool(params.get("inject_hotspot", False)),
    }
    cam = create_thermal(cfg)
    cam.open()
    try:
        frame = cam.grab_temperature_frame()
        temp = float(np.mean(frame))
        ctx.log(f"🌡️ Thermal: mean={temp:.1f}°C, max={float(np.max(frame)):.1f}°C, shape={frame.shape}")
        return {
            "thermal": {"shape": list(frame.shape), "mean_c": round(temp, 2),
                        "max_c": round(float(np.max(frame)), 2),
                        "min_c": round(float(np.min(frame)), 2)},
            "temp_c": round(temp, 2),
        }
    finally:
        cam.close()


# ── Android phone sensor handlers ─────────────────────────────

def _android_sensor_instance(params: dict, ctx: ExecContext):
    """Helper: create, open and return an AndroidSensorInstrument."""
    from pyontrust.instruments.android_sensors import create as create_android
    cfg = {
        "mode": str(params.get("mode", "simulated")),
        "sample_rate_hz": float(params.get("sample_rate_hz", 50)),
    }
    inst = create_android(cfg)
    inst.open()
    return inst


def _blk_android_accel(params: dict, inputs: dict, ctx: ExecContext) -> dict:
    """Read Android accelerometer."""
    inst = _android_sensor_instance(params, ctx)
    try:
        dur = float(params.get("duration_s", 1))
        data = inst.read_accelerometer(dur)
        ctx.log(f"📱 Accel: x={data.get('x',0):.3f} y={data.get('y',0):.3f} z={data.get('z',0):.3f} m/s²")
        trace = {"time_s": data.get("time_s", []), "current_a": data.get("magnitude", []),
                 "sample_rate_hz": float(params.get("sample_rate_hz", 50)),
                 "n_samples": data.get("n_samples", 0)}
        return {"accel": data, "trace": trace}
    finally:
        inst.close()


def _blk_android_gyro(params: dict, inputs: dict, ctx: ExecContext) -> dict:
    """Read Android gyroscope."""
    inst = _android_sensor_instance(params, ctx)
    try:
        dur = float(params.get("duration_s", 1))
        data = inst.read_gyroscope(dur)
        ctx.log(f"🌀 Gyro: x={data.get('x',0):.3f} y={data.get('y',0):.3f} z={data.get('z',0):.3f} rad/s")
        trace = {"time_s": data.get("time_s", []), "current_a": data.get("magnitude", []),
                 "sample_rate_hz": float(params.get("sample_rate_hz", 50)),
                 "n_samples": data.get("n_samples", 0)}
        return {"gyro": data, "trace": trace}
    finally:
        inst.close()


def _blk_android_mag(params: dict, inputs: dict, ctx: ExecContext) -> dict:
    """Read Android magnetometer."""
    inst = _android_sensor_instance(params, ctx)
    try:
        dur = float(params.get("duration_s", 1))
        data = inst.read_magnetometer(dur)
        ctx.log(f"🧭 Mag: x={data.get('x',0):.1f} y={data.get('y',0):.1f} z={data.get('z',0):.1f} µT")
        trace = {"time_s": data.get("time_s", []), "current_a": data.get("magnitude", []),
                 "sample_rate_hz": float(params.get("sample_rate_hz", 50)),
                 "n_samples": data.get("n_samples", 0)}
        return {"mag": data, "trace": trace}
    finally:
        inst.close()


def _blk_android_mic(params: dict, inputs: dict, ctx: ExecContext) -> dict:
    """Record from Android microphone."""
    inst = _android_sensor_instance(params, ctx)
    try:
        dur = float(params.get("duration_s", 2))
        sr = int(params.get("sample_rate", 16000))
        data = inst.read_microphone(dur, sr)
        level = data.get("level_db", -60)
        ctx.log(f"🎤 Mic: {data.get('n_samples',0)} samples, {dur}s @ {sr} Hz, level={level:.1f} dB")
        audio_trace = {"time_s": data.get("time_s", []), "current_a": data.get("samples", []),
                       "sample_rate_hz": sr, "n_samples": data.get("n_samples", 0)}
        return {"audio": audio_trace, "level_db": level}
    finally:
        inst.close()


def _blk_android_proximity(params: dict, inputs: dict, ctx: ExecContext) -> dict:
    """Read Android proximity sensor."""
    inst = _android_sensor_instance(params, ctx)
    try:
        data = inst.read_proximity(0.5)
        dist = data.get("distance", 5.0)
        near = dist < 1.0
        ctx.log(f"👋 Proximity: {dist:.1f} cm ({'NEAR' if near else 'FAR'})")
        return {"distance": dist, "near": near}
    finally:
        inst.close()


def _blk_android_light(params: dict, inputs: dict, ctx: ExecContext) -> dict:
    """Read Android ambient light sensor."""
    inst = _android_sensor_instance(params, ctx)
    try:
        dur = float(params.get("duration_s", 1))
        data = inst.read_light(dur)
        lux = data.get("lux", data.get("mean", 0))
        ctx.log(f"☀️ Light: {lux:.0f} lux")
        return {"lux": float(lux)}
    finally:
        inst.close()


def _blk_android_pressure(params: dict, inputs: dict, ctx: ExecContext) -> dict:
    """Read Android barometric pressure."""
    inst = _android_sensor_instance(params, ctx)
    try:
        dur = float(params.get("duration_s", 1))
        data = inst.read_barometer(dur)
        hpa = data.get("hpa", data.get("mean", 1013.25))
        ctx.log(f"🌤️ Pressure: {hpa:.1f} hPa")
        return {"hpa": float(hpa)}
    finally:
        inst.close()


def _blk_android_gps(params: dict, inputs: dict, ctx: ExecContext) -> dict:
    """Read Android GPS location."""
    inst = _android_sensor_instance(params, ctx)
    try:
        data = inst.read_gps()
        ctx.log(f"📍 GPS: lat={data.get('latitude',0):.5f} lon={data.get('longitude',0):.5f} alt={data.get('altitude',0):.1f}m")
        return {"location": data}
    finally:
        inst.close()


def _blk_android_battery(params: dict, inputs: dict, ctx: ExecContext) -> dict:
    """Read Android battery info."""
    inst = _android_sensor_instance(params, ctx)
    try:
        data = inst.read_battery()
        ctx.log(f"🔋 Battery: {data.get('level',0)}% {data.get('status','?')} {data.get('temp_c',0):.1f}°C")
        return {"battery": data}
    finally:
        inst.close()


def _blk_android_gravity(params: dict, inputs: dict, ctx: ExecContext) -> dict:
    """Read Android gravity sensor."""
    inst = _android_sensor_instance(params, ctx)
    try:
        dur = float(params.get("duration_s", 1))
        data = inst.read_gravity(dur)
        ctx.log(f"⬇️ Gravity: x={data.get('x',0):.3f} y={data.get('y',0):.3f} z={data.get('z',0):.3f} m/s²")
        trace = {"time_s": data.get("time_s", []), "current_a": data.get("magnitude", []),
                 "sample_rate_hz": float(params.get("sample_rate_hz", 50)),
                 "n_samples": data.get("n_samples", 0)}
        return {"gravity": data, "trace": trace}
    finally:
        inst.close()


def _blk_android_rotation(params: dict, inputs: dict, ctx: ExecContext) -> dict:
    """Read Android rotation vector sensor."""
    inst = _android_sensor_instance(params, ctx)
    try:
        dur = float(params.get("duration_s", 1))
        data = inst.read_rotation(dur)
        ctx.log(f"🔄 Rotation: x={data.get('x',0):.3f} y={data.get('y',0):.3f} z={data.get('z',0):.3f} w={data.get('w',0):.3f}")
        trace = {"time_s": data.get("time_s", []), "current_a": data.get("magnitude", []),
                 "sample_rate_hz": float(params.get("sample_rate_hz", 50)),
                 "n_samples": data.get("n_samples", 0)}
        return {"rotation": data, "trace": trace}
    finally:
        inst.close()


def _blk_android_torch(params: dict, inputs: dict, ctx: ExecContext) -> dict:
    """Toggle Android phone flashlight (torch) via ADB."""
    from pyontrust.analysis.lux_measurement import SimulatedTorch, torch_on, torch_off
    mode = str(params.get("mode", "simulated"))
    state = str(params.get("state", "on")).lower()
    if mode == "simulated":
        t = SimulatedTorch()
        ok = t.on() if state == "on" else t.off()
    else:
        ok = torch_on() if state == "on" else torch_off()
    ctx.log(f"🔦 Torch {'ON' if state == 'on' else 'OFF'} (mode={mode}, ok={ok})")
    return {"ok": ok, "state": state}


def _blk_lux_measure(params: dict, inputs: dict, ctx: ExecContext) -> dict:
    """Parallel lux measurement — webcam + Android light sensor."""
    from pyontrust.analysis.lux_measurement import (
        LuxCaptureConfig, measure_parallel_lux,
    )
    cfg = LuxCaptureConfig(
        device_index=int(params.get("device_index", 0)),
        width=int(params.get("width", 640)),
        height=int(params.get("height", 480)),
        target_fps=float(params.get("fps", 30)),
        torch_on_s=float(params.get("torch_on_s", 3)),
        torch_off_s=float(params.get("torch_off_s", 3)),
        n_cycles=int(params.get("n_cycles", 3)),
        pre_capture_s=float(params.get("pre_capture_s", 1)),
        android_mode=str(params.get("android_mode", "simulated")),
        android_sample_rate_hz=float(params.get("android_rate_hz", 10)),
        lux_scale=float(params.get("lux_scale", 2.0)),
        lux_offset=float(params.get("lux_offset", 0.0)),
    )
    use_real = str(params.get("android_mode", "simulated")) != "simulated"
    result = measure_parallel_lux(cfg, use_real_torch=use_real)
    ctx.log(
        f"💡 Lux: webcam_Δ={result.webcam_lux_delta:.1f}, "
        f"android_Δ={result.android_lux_delta:.1f}, "
        f"r={result.correlation:.3f}"
        if result.ok and result.webcam_lux_delta is not None
        else f"💡 Lux: {result.error or 'no data'}"
    )
    return {
        "result": result.summary(),
        "webcam_lux": result.webcam_lux,
        "android_lux": result.android_lux,
        "correlation": result.correlation,
    }


def _blk_stats(params: dict, inputs: dict, ctx: ExecContext) -> dict:
    """Compute statistics on a power trace."""
    trace = inputs.get("trace", {})
    data = trace.get("current_a", [])
    if not data:
        return {"result": {"error": "no data"}}

    import numpy as np
    arr = np.array(data, dtype=float)
    result = {
        "avg_current_a": round(float(np.mean(arr)), 9),
        "max_current_a": round(float(np.max(arr)), 9),
        "min_current_a": round(float(np.min(arr)), 9),
        "std_current_a": round(float(np.std(arr)), 9),
        "rms_current_a": round(float(np.sqrt(np.mean(arr ** 2))), 9),
        "n_samples": len(data),
    }
    ctx.log(f"📊 Stats: avg={result['avg_current_a']*1e6:.2f}µA, max={result['max_current_a']*1e6:.2f}µA")
    return {"result": result}


def _blk_filter(params: dict, inputs: dict, ctx: ExecContext) -> dict:
    """Apply a low-pass Butterworth filter."""
    trace = inputs.get("trace", {})
    data = trace.get("current_a", [])
    rate = trace.get("sample_rate_hz", 1000)
    cutoff = float(params.get("cutoff_hz", 50))
    order  = int(params.get("order", 4))

    if not data:
        return {"filtered": trace}

    try:
        from scipy.signal import butter, filtfilt
        import numpy as np
        nyq = rate / 2
        b, a = butter(order, min(cutoff / nyq, 0.99), btype="low")
        filtered = filtfilt(b, a, np.array(data, dtype=float)).tolist()
        ctx.log(f"〰️ Filter: {cutoff}Hz LP order-{order} ({len(data)} samples)")
        out = dict(trace)
        out["current_a"] = filtered
        return {"filtered": out}
    except ImportError:
        ctx.log("⚠ scipy not installed — filter skipped")
        return {"filtered": trace}


def _blk_threshold(params: dict, inputs: dict, ctx: ExecContext) -> dict:
    """Pass/fail threshold gate."""
    value = inputs.get("value")
    metric = str(params.get("metric", "avg_current_a"))
    max_val = float(params.get("max_val", 0.01))
    min_val = float(params.get("min_val", 0))

    # Extract metric from dict input
    actual = value
    if isinstance(value, dict) and metric in value:
        actual = value[metric]

    try:
        actual = float(actual)
    except (TypeError, ValueError):
        ctx.log(f"⚠ Threshold: cannot convert '{actual}' to number")
        return {"pass": False, "value": value}

    passed = min_val <= actual <= max_val
    emoji = "✅" if passed else "❌"
    ctx.log(f"{emoji} Threshold: {metric}={actual:.6g} ({'PASS' if passed else 'FAIL'}, limits=[{min_val}, {max_val}])")
    return {"pass": passed, "value": value}


def _blk_thermal_analyze(params: dict, inputs: dict, ctx: ExecContext) -> dict:
    """Run the thermal analyzer on a thermal frame summary."""
    thermal = inputs.get("thermal", {})
    ctx.log(f"🔥 Thermal analysis: mean={thermal.get('mean_c','?')}°C, max={thermal.get('max_c','?')}°C")
    # In a real run, this would use ThermalAnalyzer on the actual frame
    verdict = "NORMAL"
    max_c = thermal.get("max_c", 0)
    if isinstance(max_c, (int, float)):
        if max_c > 85:
            verdict = "HOT"
        elif max_c > 60:
            verdict = "WARM"
    return {
        "snapshot": {"verdict": verdict, **thermal},
        "heatmap": {"type": "colorised", "colormap": params.get("colormap", "inferno")},
    }


def _blk_aoi_inspect(params: dict, inputs: dict, ctx: ExecContext) -> dict:
    """Run AOI inspection on a frame."""
    frame = inputs.get("frame", {})
    ctx.log(f"🔍 AOI inspect: {frame.get('data_summary','?')}")
    return {
        "result": {"verdict": "PASS", "defects": 0, "frame_info": frame},
        "annotated": frame,
    }


def _blk_expression(params: dict, inputs: dict, ctx: ExecContext) -> dict:
    """Evaluate a Python expression with a, b as inputs."""
    a = inputs.get("a")
    b = inputs.get("b")
    expr = str(params.get("expr", "a + b"))

    try:
        # Safe eval with limited builtins
        allowed = {"__builtins__": {"abs": abs, "min": min, "max": max,
                                     "round": round, "len": len, "sum": sum,
                                     "int": int, "float": float, "str": str,
                                     "bool": bool, "list": list, "dict": dict,
                                     "True": True, "False": False, "None": None,
                                     "math": math}}
        allowed["a"] = a
        allowed["b"] = b
        result = eval(expr, allowed)  # noqa: S307
        ctx.log(f"ƒ Expression: {expr} → {_summarise(result)}")
        return {"result": result}
    except Exception as exc:
        ctx.log(f"❌ Expression error: {exc}")
        return {"result": None}


def _blk_constant(params: dict, inputs: dict, ctx: ExecContext) -> dict:
    """Emit a constant value."""
    raw = params.get("value", "0")
    dtype = str(params.get("dtype", "float"))
    try:
        if dtype == "float":
            val = float(raw)
        elif dtype == "int":
            val = int(float(raw))
        elif dtype == "bool":
            val = str(raw).lower() in ("true", "1", "yes")
        elif dtype in ("list", "dict"):
            val = json.loads(str(raw))
        else:
            val = str(raw)
    except Exception:
        val = str(raw)
    ctx.log(f"# Constant: {_summarise(val)}")
    return {"value": val}


def _blk_multiply(params: dict, inputs: dict, ctx: ExecContext) -> dict:
    a = _to_number(inputs.get("a", 0))
    b = _to_number(inputs.get("b", 0))
    result = a * b
    ctx.log(f"× Multiply: {a} × {b} = {result}")
    return {"result": result}


def _blk_compare(params: dict, inputs: dict, ctx: ExecContext) -> dict:
    a = inputs.get("a")
    b = inputs.get("b")
    op = str(params.get("op", ">"))
    ops = {">": lambda x, y: x > y, "<": lambda x, y: x < y,
           ">=": lambda x, y: x >= y, "<=": lambda x, y: x <= y,
           "==": lambda x, y: x == y, "!=": lambda x, y: x != y}
    try:
        result = ops.get(op, ops[">"])(_to_number(a), _to_number(b))
    except Exception:
        result = False
    ctx.log(f"≷ Compare: {_summarise(a)} {op} {_summarise(b)} → {result}")
    return {"result": result}


def _blk_display(params: dict, inputs: dict, ctx: ExecContext) -> dict:
    data = inputs.get("data")
    fmt = str(params.get("format", "auto"))
    if fmt == "json" or (fmt == "auto" and isinstance(data, (dict, list))):
        try:
            text = json.dumps(data, indent=2, default=str)
        except Exception:
            text = str(data)
    else:
        text = str(data)
    ctx.log(f"🖥️ Display:\n{text}")
    return {}


def _blk_plot_trace(params: dict, inputs: dict, ctx: ExecContext) -> dict:
    trace = inputs.get("trace", {})
    n = len(trace.get("current_a", []))
    title = str(params.get("title", "Trace"))
    style = str(params.get("style", "lines"))
    ctx.log(f"📈 Plot '{title}': {n} points, style={style} (chart rendered in browser)")
    return {}


def _blk_save_file(params: dict, inputs: dict, ctx: ExecContext) -> dict:
    data = inputs.get("data")
    path = str(params.get("path", "output.json"))
    fmt  = str(params.get("fmt", "json"))
    try:
        p = pathlib.Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        if fmt == "json":
            p.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")
        elif fmt == "csv" and isinstance(data, dict):
            import csv
            with open(p, "w", newline="", encoding="utf-8") as f:
                w = csv.writer(f)
                keys = list(data.keys())
                w.writerow(keys)
                n = max(len(v) for v in data.values() if isinstance(v, list)) if data else 0
                for i in range(n):
                    w.writerow([data[k][i] if isinstance(data[k], list) and i < len(data[k]) else data[k] for k in keys])
        elif fmt == "txt":
            p.write_text(str(data), encoding="utf-8")
        else:
            p.write_text(str(data), encoding="utf-8")
        ctx.log(f"💾 Saved: {path} ({fmt})")
    except Exception as exc:
        ctx.log(f"❌ Save error: {exc}")
    return {}


def _blk_log_message(params: dict, inputs: dict, ctx: ExecContext) -> dict:
    data = inputs.get("data")
    prefix = str(params.get("prefix", "LOG"))
    level  = str(params.get("level", "info"))
    ctx.log(f"📝 [{level.upper()}] {prefix}: {_summarise(data)}")
    return {"data": data}


def _blk_delay(params: dict, inputs: dict, ctx: ExecContext) -> dict:
    secs = float(params.get("seconds", 1))
    ctx.log(f"⏱️ Delay: {secs}s")
    time.sleep(secs)
    return {"trigger": inputs.get("trigger")}


def _blk_repeat(params: dict, inputs: dict, ctx: ExecContext) -> dict:
    count = int(params.get("count", 5))
    ctx.log(f"🔁 Repeat: {count} iterations (note: repeat runs inline)")
    return {"output": inputs.get("input"), "index": count - 1}


def _blk_gate(params: dict, inputs: dict, ctx: ExecContext) -> dict:
    cond = bool(inputs.get("cond", False))
    data = inputs.get("data")
    ctx.log(f"🚦 Gate: condition={cond}")
    if cond:
        return {"true_out": data, "false_out": None}
    else:
        return {"true_out": None, "false_out": data}


def _blk_merge(params: dict, inputs: dict, ctx: ExecContext) -> dict:
    a = inputs.get("a")
    b = inputs.get("b")
    strategy = str(params.get("strategy", "dict_merge"))
    if strategy == "dict_merge" and isinstance(a, dict) and isinstance(b, dict):
        merged = {**a, **b}
    elif strategy == "list_concat":
        la = a if isinstance(a, list) else [a]
        lb = b if isinstance(b, list) else [b]
        merged = la + lb
    else:
        merged = a if a is not None else b
    ctx.log(f"⊕ Merge ({strategy}): {_summarise(merged)}")
    return {"merged": merged}


# ── NEW: Instruments ─────────────────────────────────────────────────

def _blk_csv_replay(params: dict, inputs: dict, ctx: ExecContext) -> dict:
    """Replay a CSV recording (same as csv_file but with speed param)."""
    return _blk_csv_file(params, inputs, ctx)


def _blk_ppk2_meter(params: dict, inputs: dict, ctx: ExecContext) -> dict:
    """PPK2 source-meter (simulated if hardware unavailable)."""
    import numpy as np

    rate = float(params.get("sample_rate_hz", 100000))
    dur = float(params.get("duration_s", 2))
    n = int(rate * dur)
    t = np.linspace(0, dur, n)
    # Simulated PPK2-like trace (~5µA sleep with occasional spikes)
    current = 5e-6 + np.random.normal(0, 0.5e-6, n)
    ctx.log(f"⚡ PPK2 (simulated): {n} samples, {dur}s @ {rate/1000:.0f}kHz")
    return {"trace": {"time_s": t.tolist(), "current_a": current.tolist(),
                       "sample_rate_hz": rate, "n_samples": n}}


def _blk_ad3_dwf_meter(params: dict, inputs: dict, ctx: ExecContext) -> dict:
    """Analog Discovery 3 meter (simulated if hardware unavailable)."""
    import numpy as np

    rate = float(params.get("sample_rate_hz", 10000))
    dur = float(params.get("duration_s", 2))
    shunt = float(params.get("shunt_ohm", 1.0))
    n = int(rate * dur)
    t = np.linspace(0, dur, n)
    current = 0.005 + np.random.normal(0, 0.0005, n)
    ctx.log(f"📟 AD3/DWF (simulated): {n} samples, shunt={shunt}Ω")
    return {"trace": {"time_s": t.tolist(), "current_a": current.tolist(),
                       "sample_rate_hz": rate, "n_samples": n}}


def _blk_waveform_gen(params: dict, inputs: dict, ctx: ExecContext) -> dict:
    """Generate an arbitrary waveform."""
    import numpy as np

    shape = str(params.get("shape", "sine"))
    freq = float(params.get("frequency_hz", 100))
    amp = float(params.get("amplitude", 1.0))
    offset = float(params.get("offset", 0))
    duty = float(params.get("duty_cycle", 0.5))
    dur = float(params.get("duration_s", 1))
    rate = float(params.get("sample_rate_hz", 10000))

    n = int(rate * dur)
    t = np.linspace(0, dur, n)

    if shape == "sine":
        y = amp * np.sin(2 * np.pi * freq * t) + offset
    elif shape == "square":
        y = amp * np.sign(np.sin(2 * np.pi * freq * t)) + offset
    elif shape == "triangle":
        y = amp * (2 * np.abs(2 * (freq * t - np.floor(freq * t + 0.5))) - 1) + offset
    elif shape == "sawtooth":
        y = amp * (2 * (freq * t - np.floor(freq * t)) - 1) + offset
    elif shape == "dc":
        y = np.full(n, amp + offset)
    elif shape == "pulse":
        y = np.zeros(n) + offset
        period_samples = int(rate / freq) if freq > 0 else n
        pulse_w = max(1, int(period_samples * duty))
        for i in range(0, n, period_samples):
            y[i:i + pulse_w] = amp + offset
    elif shape == "noise":
        y = amp * np.random.normal(0, 1, n) + offset
    elif shape == "chirp":
        f0, f1 = freq * 0.1, freq
        phase = 2 * np.pi * (f0 * t + (f1 - f0) * t ** 2 / (2 * dur))
        y = amp * np.sin(phase) + offset
    else:
        y = np.zeros(n)

    ctx.log(f"〜 Waveform: {shape} {freq}Hz, amp={amp}, {n} samples")
    return {"trace": {"time_s": t.tolist(), "current_a": y.tolist(),
                       "sample_rate_hz": rate, "n_samples": n}}


def _blk_random_data(params: dict, inputs: dict, ctx: ExecContext) -> dict:
    """Generate random data from a statistical distribution."""
    import numpy as np

    dist = str(params.get("distribution", "normal"))
    size = int(params.get("size", 1000))
    p1 = float(params.get("param1", 0))
    p2 = float(params.get("param2", 1))

    if dist == "normal":
        data = np.random.normal(p1, max(p2, 1e-9), size)
    elif dist == "uniform":
        data = np.random.uniform(p1, p2, size)
    elif dist == "poisson":
        data = np.random.poisson(max(p1, 0.1), size).astype(float)
    elif dist == "exponential":
        data = np.random.exponential(max(p1, 0.01), size)
    elif dist == "beta":
        data = np.random.beta(max(p1, 0.1), max(p2, 0.1), size)
    else:
        data = np.random.normal(0, 1, size)

    ctx.log(f"🎲 Random: {dist}(p1={p1}, p2={p2}), {size} samples, mean={float(np.mean(data)):.4g}")
    return {"data": data.tolist()}


# ── NEW: Analysis blocks ─────────────────────────────────────────────

def _blk_highpass_filter(params: dict, inputs: dict, ctx: ExecContext) -> dict:
    """High-pass Butterworth filter."""
    trace = inputs.get("trace", {})
    data = trace.get("current_a", [])
    rate = trace.get("sample_rate_hz", 1000)
    cutoff = float(params.get("cutoff_hz", 10))
    order = int(params.get("order", 4))
    if not data:
        return {"filtered": trace}
    try:
        from scipy.signal import butter, filtfilt
        import numpy as np
        nyq = rate / 2
        b, a = butter(order, min(cutoff / nyq, 0.99), btype="high")
        filtered = filtfilt(b, a, np.array(data, dtype=float)).tolist()
        ctx.log(f"⫝ HP filter: {cutoff}Hz order-{order} ({len(data)} samples)")
        out = dict(trace)
        out["current_a"] = filtered
        return {"filtered": out}
    except ImportError:
        ctx.log("⚠ scipy not installed — high-pass filter skipped")
        return {"filtered": trace}


def _blk_bandpass_filter(params: dict, inputs: dict, ctx: ExecContext) -> dict:
    """Band-pass Butterworth filter."""
    trace = inputs.get("trace", {})
    data = trace.get("current_a", [])
    rate = trace.get("sample_rate_hz", 1000)
    low = float(params.get("low_hz", 10))
    high = float(params.get("high_hz", 100))
    order = int(params.get("order", 4))
    if not data:
        return {"filtered": trace}
    try:
        from scipy.signal import butter, filtfilt
        import numpy as np
        nyq = rate / 2
        b, a = butter(order, [min(low / nyq, 0.99), min(high / nyq, 0.99)], btype="band")
        filtered = filtfilt(b, a, np.array(data, dtype=float)).tolist()
        ctx.log(f"⧫ BP filter: {low}-{high}Hz order-{order}")
        out = dict(trace)
        out["current_a"] = filtered
        return {"filtered": out}
    except ImportError:
        ctx.log("⚠ scipy not installed — bandpass filter skipped")
        return {"filtered": trace}


def _blk_fft_spectrum(params: dict, inputs: dict, ctx: ExecContext) -> dict:
    """FFT power spectral density + peak detection."""
    trace = inputs.get("trace", {})
    data = trace.get("current_a", [])
    rate = trace.get("sample_rate_hz", 1000)
    n_peaks = int(params.get("n_peaks", 5))
    win = str(params.get("window", "hann"))
    if not data:
        return {"spectrum": {}, "peaks": {}}
    import numpy as np
    arr = np.array(data, dtype=float)
    n = len(arr)
    # Apply window
    windows = {"hann": np.hanning, "hamming": np.hamming, "blackman": np.blackman,
               "rectangular": lambda m: np.ones(m), "kaiser": lambda m: np.kaiser(m, 8)}
    w_func = windows.get(win, np.hanning)
    w = w_func(n)
    fft_vals = np.abs(np.fft.rfft(arr * w)) / n
    freqs = np.fft.rfftfreq(n, 1.0 / rate)
    psd = (fft_vals ** 2).tolist()
    # Find peaks
    peak_indices = np.argsort(fft_vals)[-n_peaks:][::-1]
    peaks = [{"freq_hz": round(float(freqs[i]), 2), "amplitude": round(float(fft_vals[i]), 6)} for i in peak_indices if i > 0]
    ctx.log(f"🌈 FFT: {n} points, rate={rate}Hz, top peak={peaks[0]['freq_hz']}Hz" if peaks else "🌈 FFT: no peaks")
    return {"spectrum": {"freq_hz": freqs.tolist(), "psd": psd, "amplitude": fft_vals.tolist()},
            "peaks": {"peaks": peaks}}


def _blk_moving_average(params: dict, inputs: dict, ctx: ExecContext) -> dict:
    """Moving average filter."""
    trace = inputs.get("trace", {})
    data = trace.get("current_a", [])
    ws = int(params.get("window_size", 50))
    method = str(params.get("method", "sma"))
    if not data:
        return {"smoothed": trace}
    import numpy as np
    arr = np.array(data, dtype=float)
    if method == "sma":
        kernel = np.ones(ws) / ws
        smoothed = np.convolve(arr, kernel, mode="same")
    elif method == "ema":
        alpha = 2.0 / (ws + 1)
        smoothed = np.zeros_like(arr)
        smoothed[0] = arr[0]
        for i in range(1, len(arr)):
            smoothed[i] = alpha * arr[i] + (1 - alpha) * smoothed[i - 1]
    elif method == "median":
        from scipy.ndimage import median_filter
        smoothed = median_filter(arr, size=ws)
    else:
        smoothed = arr
    ctx.log(f"📉 Moving average ({method}, window={ws}): {len(data)} samples")
    out = dict(trace)
    out["current_a"] = smoothed.tolist()
    return {"smoothed": out}


def _blk_derivative(params: dict, inputs: dict, ctx: ExecContext) -> dict:
    """First or second derivative."""
    trace = inputs.get("trace", {})
    data = trace.get("current_a", [])
    order = int(params.get("order", 1))
    if not data or len(data) < 2:
        return {"dtrace": trace}
    import numpy as np
    arr = np.array(data, dtype=float)
    t = np.array(trace.get("time_s", list(range(len(data)))), dtype=float)
    dt = np.diff(t)
    dt[dt == 0] = 1e-9
    d1 = np.diff(arr) / dt
    if order == 2 and len(d1) > 1:
        dt2 = dt[:-1]
        dt2[dt2 == 0] = 1e-9
        result = np.diff(d1) / dt2
        t_out = t[1:-1]
    else:
        result = d1
        t_out = t[:-1]
    ctx.log(f"Δ Derivative (order={order}): {len(result)} points")
    return {"dtrace": {"time_s": t_out.tolist(), "current_a": result.tolist(),
                        "sample_rate_hz": trace.get("sample_rate_hz", 1000), "n_samples": len(result)}}


def _blk_integral(params: dict, inputs: dict, ctx: ExecContext) -> dict:
    """Numerical integration."""
    trace = inputs.get("trace", {})
    data = trace.get("current_a", [])
    method = str(params.get("method", "trapezoid"))
    if not data:
        return {"result": {"total": 0}}
    import numpy as np
    arr = np.array(data, dtype=float)
    t = np.array(trace.get("time_s", list(range(len(data)))), dtype=float)
    if method == "trapezoid":
        total = float(np.trapz(arr, t))
    elif method == "simpson":
        try:
            from scipy.integrate import simpson
            total = float(simpson(arr, x=t))
        except ImportError:
            total = float(np.trapz(arr, t))
    elif method == "cumulative":
        cum = np.cumsum(arr * np.gradient(t))
        ctx.log(f"∫ Cumulative integral: final={float(cum[-1]):.6g}")
        return {"result": {"cumulative": cum.tolist(), "total": float(cum[-1])}}
    else:
        total = float(np.trapz(arr, t))
    ctx.log(f"∫ Integral ({method}): {total:.6g}")
    return {"result": {"total": total, "unit": "A·s (Coulombs)"}}


def _blk_window_slice(params: dict, inputs: dict, ctx: ExecContext) -> dict:
    """Extract a time window from trace."""
    trace = inputs.get("trace", {})
    data = trace.get("current_a", [])
    times = trace.get("time_s", [])
    start = float(params.get("start_s", 0))
    end = float(params.get("end_s", 1))
    if not data:
        return {"sliced": trace}
    import numpy as np
    t = np.array(times, dtype=float)
    mask = (t >= start) & (t <= end)
    sliced_t = t[mask].tolist()
    sliced_d = np.array(data, dtype=float)[mask].tolist()
    ctx.log(f"✂️ Slice: [{start}s, {end}s] → {len(sliced_d)} samples")
    return {"sliced": {"time_s": sliced_t, "current_a": sliced_d,
                        "sample_rate_hz": trace.get("sample_rate_hz", 1000), "n_samples": len(sliced_d)}}


def _blk_resample(params: dict, inputs: dict, ctx: ExecContext) -> dict:
    """Resample trace to different rate."""
    trace = inputs.get("trace", {})
    data = trace.get("current_a", [])
    times = trace.get("time_s", [])
    target = float(params.get("target_rate_hz", 1000))
    method = str(params.get("method", "linear"))
    if not data or len(data) < 2:
        return {"resampled": trace}
    import numpy as np
    t = np.array(times, dtype=float)
    dur = t[-1] - t[0]
    n_new = int(dur * target)
    t_new = np.linspace(t[0], t[-1], n_new)
    d_new = np.interp(t_new, t, np.array(data, dtype=float))
    ctx.log(f"🔄 Resample: {len(data)}→{n_new} samples @ {target}Hz")
    return {"resampled": {"time_s": t_new.tolist(), "current_a": d_new.tolist(),
                           "sample_rate_hz": target, "n_samples": n_new}}


def _blk_edge_detect(params: dict, inputs: dict, ctx: ExecContext) -> dict:
    """Detect signal edges/transitions."""
    trace = inputs.get("trace", {})
    data = trace.get("current_a", [])
    times = trace.get("time_s", [])
    thresh = float(params.get("threshold", 0.001))
    direction = str(params.get("direction", "both"))
    min_w = float(params.get("min_width_s", 0))
    if not data or len(data) < 2:
        return {"edges": {"rising": [], "falling": [], "count": 0}}
    import numpy as np
    arr = np.array(data, dtype=float)
    diff = np.diff(arr)
    t = np.array(times, dtype=float) if times else np.arange(len(data), dtype=float)
    rising, falling = [], []
    for i, d in enumerate(diff):
        if direction in ("rising", "both") and d > thresh:
            rising.append({"index": i, "time_s": round(float(t[i]), 6), "delta": round(float(d), 9)})
        if direction in ("falling", "both") and d < -thresh:
            falling.append({"index": i, "time_s": round(float(t[i]), 6), "delta": round(float(d), 9)})
    ctx.log(f"📐 Edges: {len(rising)} rising, {len(falling)} falling (threshold={thresh})")
    return {"edges": {"rising": rising, "falling": falling, "count": len(rising) + len(falling)}}


def _blk_histogram(params: dict, inputs: dict, ctx: ExecContext) -> dict:
    """Amplitude distribution histogram."""
    trace = inputs.get("trace", {})
    data = trace.get("current_a", []) if isinstance(trace, dict) else trace
    if isinstance(data, dict):
        data = data.get("current_a", [])
    bins = int(params.get("bins", 50))
    density = bool(params.get("density", False))
    if not data:
        return {"hist": {"bins": [], "counts": []}}
    import numpy as np
    counts, edges = np.histogram(np.array(data, dtype=float), bins=bins, density=density)
    centers = ((edges[:-1] + edges[1:]) / 2).tolist()
    ctx.log(f"▊ Histogram: {bins} bins over {len(data)} values")
    return {"hist": {"bin_centers": centers, "counts": counts.tolist(), "edges": edges.tolist()}}


def _blk_correlate(params: dict, inputs: dict, ctx: ExecContext) -> dict:
    """Cross-correlation between two traces."""
    trace_a = inputs.get("trace_a", {})
    trace_b = inputs.get("trace_b", {})
    normalize = bool(params.get("normalize", True))
    data_a = trace_a.get("current_a", []) if isinstance(trace_a, dict) else []
    data_b = trace_b.get("current_a", []) if isinstance(trace_b, dict) else []
    if not data_a or not data_b:
        return {"result": {"correlation": [], "max_corr": 0, "lag": 0}}
    import numpy as np
    a = np.array(data_a, dtype=float)
    b = np.array(data_b, dtype=float)
    if normalize:
        a = (a - np.mean(a)) / (np.std(a) + 1e-12)
        b = (b - np.mean(b)) / (np.std(b) + 1e-12)
    corr = np.correlate(a, b, mode="full")
    if normalize:
        corr /= len(a)
    max_idx = int(np.argmax(np.abs(corr)))
    lag = max_idx - len(a) + 1
    ctx.log(f"⟷ Cross-correlate: max_corr={float(corr[max_idx]):.4f}, lag={lag}")
    return {"result": {"max_corr": round(float(corr[max_idx]), 6), "lag": lag,
                        "correlation": corr.tolist()}}


# ── NEW: Vision blocks ───────────────────────────────────────────────

def _blk_color_detect(params: dict, inputs: dict, ctx: ExecContext) -> dict:
    """Detect color ranges in image (simulated)."""
    frame = inputs.get("frame", {})
    ctx.log(f"🎨 Color detect: {frame.get('data_summary', '?')}")
    return {"result": {"pixel_count": 1000, "percentage": 15.6, "centroid": [320, 240]},
            "mask": frame}


def _blk_blob_detect(params: dict, inputs: dict, ctx: ExecContext) -> dict:
    """Detect blobs/contours in image (simulated)."""
    frame = inputs.get("frame", {})
    min_area = int(params.get("min_area", 100))
    ctx.log(f"⬤ Blob detect: min_area={min_area}")
    return {"blobs": {"count": 3, "blobs": [
        {"x": 100, "y": 150, "area": 500, "circularity": 0.9},
        {"x": 300, "y": 200, "area": 1200, "circularity": 0.7},
        {"x": 450, "y": 100, "area": 800, "circularity": 0.85},
    ]}, "annotated": frame}


def _blk_template_match(params: dict, inputs: dict, ctx: ExecContext) -> dict:
    """Template matching (simulated)."""
    frame = inputs.get("frame", {})
    template = inputs.get("template", {})
    threshold = float(params.get("threshold", 0.8))
    ctx.log(f"🧩 Template match: threshold={threshold}")
    return {"matches": {"count": 1, "matches": [{"x": 150, "y": 200, "confidence": 0.92}]},
            "annotated": frame}


def _blk_image_resize(params: dict, inputs: dict, ctx: ExecContext) -> dict:
    """Resize image (simulated)."""
    w = int(params.get("width", 320))
    h = int(params.get("height", 240))
    ctx.log(f"🔲 Resize: → {w}x{h}")
    return {"resized": {"shape": [h, w, 3], "dtype": "uint8", "data_summary": f"{w}x{h}"}}


def _blk_image_crop(params: dict, inputs: dict, ctx: ExecContext) -> dict:
    """Crop image ROI (simulated)."""
    x, y = int(params.get("x", 0)), int(params.get("y", 0))
    w, h = int(params.get("w", 320)), int(params.get("h", 240))
    ctx.log(f"✂️ Crop: ({x},{y}) {w}x{h}")
    return {"cropped": {"shape": [h, w, 3], "dtype": "uint8", "data_summary": f"{w}x{h}"}}


def _blk_image_threshold(params: dict, inputs: dict, ctx: ExecContext) -> dict:
    """Image thresholding (simulated)."""
    method = str(params.get("method", "otsu"))
    ctx.log(f"◻ Image threshold: {method}")
    return {"binary": {"shape": [480, 640], "dtype": "uint8", "data_summary": "640x480 binary"},
            "stats": {"white_pct": 35.2, "black_pct": 64.8, "method": method}}


# ── NEW: Math blocks ─────────────────────────────────────────────────

def _blk_add(params: dict, inputs: dict, ctx: ExecContext) -> dict:
    a = _to_number(inputs.get("a", 0))
    b = _to_number(inputs.get("b", 0))
    result = a + b
    ctx.log(f"+ Add: {a} + {b} = {result}")
    return {"result": result}


def _blk_subtract(params: dict, inputs: dict, ctx: ExecContext) -> dict:
    a = _to_number(inputs.get("a", 0))
    b = _to_number(inputs.get("b", 0))
    result = a - b
    ctx.log(f"− Subtract: {a} − {b} = {result}")
    return {"result": result}


def _blk_divide(params: dict, inputs: dict, ctx: ExecContext) -> dict:
    a = _to_number(inputs.get("a", 0))
    b = _to_number(inputs.get("b", 1))
    if b == 0:
        ctx.log("÷ Divide: division by zero")
        return {"result": float("inf")}
    result = a / b
    ctx.log(f"÷ Divide: {a} ÷ {b} = {result}")
    return {"result": result}


def _blk_abs_val(params: dict, inputs: dict, ctx: ExecContext) -> dict:
    v = _to_number(inputs.get("value", 0))
    result = abs(v)
    ctx.log(f"|x| Abs: |{v}| = {result}")
    return {"result": result}


def _blk_power(params: dict, inputs: dict, ctx: ExecContext) -> dict:
    base = _to_number(inputs.get("base", 0))
    exp = inputs.get("exp")
    if exp is None:
        exp = float(params.get("default_exp", 2))
    else:
        exp = _to_number(exp)
    result = base ** exp
    ctx.log(f"xⁿ Power: {base}^{exp} = {result}")
    return {"result": result}


def _blk_log_math(params: dict, inputs: dict, ctx: ExecContext) -> dict:
    v = _to_number(inputs.get("value", 1))
    base = str(params.get("base", "e"))
    if v <= 0:
        ctx.log(f"log: cannot take log of {v}")
        return {"result": float("nan")}
    if base == "e":
        result = math.log(v)
    elif base == "10":
        result = math.log10(v)
    elif base == "2":
        result = math.log2(v)
    else:
        result = math.log(v)
    ctx.log(f"log: log_{base}({v}) = {result:.6g}")
    return {"result": result}


def _blk_trig(params: dict, inputs: dict, ctx: ExecContext) -> dict:
    angle = _to_number(inputs.get("angle", 0))
    func = str(params.get("func", "sin"))
    unit = str(params.get("unit", "radians"))
    if unit == "degrees":
        angle = math.radians(angle)
    funcs = {"sin": math.sin, "cos": math.cos, "tan": math.tan,
             "asin": math.asin, "acos": math.acos, "atan": math.atan}
    try:
        result = funcs.get(func, math.sin)(angle)
    except (ValueError, OverflowError) as e:
        ctx.log(f"∿ Trig error: {e}")
        return {"result": float("nan")}
    ctx.log(f"∿ Trig: {func}({angle:.4f}) = {result:.6g}")
    return {"result": result}


def _blk_clamp(params: dict, inputs: dict, ctx: ExecContext) -> dict:
    v = _to_number(inputs.get("value", 0))
    mn = float(params.get("min_val", 0))
    mx = float(params.get("max_val", 1))
    result = max(mn, min(mx, v))
    ctx.log(f"⊏⊐ Clamp: {v} → {result} [{mn}, {mx}]")
    return {"result": result}


def _blk_map_range(params: dict, inputs: dict, ctx: ExecContext) -> dict:
    v = _to_number(inputs.get("value", 0))
    in_min = float(params.get("in_min", 0))
    in_max = float(params.get("in_max", 1023))
    out_min = float(params.get("out_min", 0))
    out_max = float(params.get("out_max", 3.3))
    denom = in_max - in_min
    if denom == 0:
        result = out_min
    else:
        result = (v - in_min) / denom * (out_max - out_min) + out_min
    ctx.log(f"↔ Map: {v} [{in_min},{in_max}] → {result:.4g} [{out_min},{out_max}]")
    return {"result": result}


def _blk_unit_convert(params: dict, inputs: dict, ctx: ExecContext) -> dict:
    v = _to_number(inputs.get("value", 0))
    conv = str(params.get("conversion", "A_to_uA"))
    conversions = {
        "A_to_uA": 1e6, "A_to_mA": 1e3, "uA_to_A": 1e-6, "mA_to_A": 1e-3,
        "V_to_mV": 1e3, "mV_to_V": 1e-3, "W_to_mW": 1e3, "mW_to_W": 1e-3,
        "Hz_to_kHz": 1e-3, "kHz_to_MHz": 1e-3, "rad_to_deg": 180 / math.pi, "deg_to_rad": math.pi / 180,
    }
    special = {
        "C_to_F": lambda x: x * 9 / 5 + 32, "F_to_C": lambda x: (x - 32) * 5 / 9,
        "K_to_C": lambda x: x - 273.15, "C_to_K": lambda x: x + 273.15,
        "dBm_to_mW": lambda x: 10 ** (x / 10), "mW_to_dBm": lambda x: 10 * math.log10(max(x, 1e-12)),
    }
    if conv in special:
        result = special[conv](v)
    elif conv in conversions:
        result = v * conversions[conv]
    else:
        result = v
    ctx.log(f"⟹ Convert: {v} → {result:.6g} ({conv})")
    return {"result": result}


# ── NEW: Data manipulation blocks ────────────────────────────────────

def _blk_dict_get(params: dict, inputs: dict, ctx: ExecContext) -> dict:
    data = inputs.get("data", {})
    key = str(params.get("key", ""))
    default = params.get("default_val", "null")
    if isinstance(data, dict):
        val = data.get(key, default)
    else:
        val = default
    ctx.log(f"{{}}→ Dict get: [{key}] = {_summarise(val)}")
    return {"value": val}


def _blk_dict_set(params: dict, inputs: dict, ctx: ExecContext) -> dict:
    data = inputs.get("data", {})
    value = inputs.get("value")
    key = str(params.get("key", "my_field"))
    if not isinstance(data, dict):
        data = {}
    result = dict(data)
    result[key] = value
    ctx.log(f"→{{}} Dict set: [{key}] = {_summarise(value)}")
    return {"result": result}


def _blk_dict_build(params: dict, inputs: dict, ctx: ExecContext) -> dict:
    a = inputs.get("a")
    b = inputs.get("b")
    ka = str(params.get("key_a", "left"))
    kb = str(params.get("key_b", "right"))
    result = {ka: a, kb: b}
    ctx.log(f"{{ }} Build dict: {{{ka}: ..., {kb}: ...}}")
    return {"result": result}


def _blk_list_build(params: dict, inputs: dict, ctx: ExecContext) -> dict:
    a = inputs.get("a")
    b = inputs.get("b")
    la = a if isinstance(a, list) else ([a] if a is not None else [])
    lb = b if isinstance(b, list) else ([b] if b is not None else [])
    result = la + lb
    ctx.log(f"[ ] Build list: {len(result)} items")
    return {"result": result}


def _blk_json_parse(params: dict, inputs: dict, ctx: ExecContext) -> dict:
    text = inputs.get("text", "")
    try:
        data = json.loads(str(text))
        ctx.log(f"{{ }} JSON parse: OK ({type(data).__name__})")
        return {"data": data}
    except json.JSONDecodeError as e:
        ctx.log(f"❌ JSON parse error: {e}")
        return {"data": None}


def _blk_format_string(params: dict, inputs: dict, ctx: ExecContext) -> dict:
    a = inputs.get("a", "")
    b = inputs.get("b", "")
    template = str(params.get("template", "Value: {a}, Result: {b}"))
    try:
        text = template.format(a=a, b=b)
    except (KeyError, IndexError, ValueError):
        text = template
    ctx.log(f'"…" Format: {text[:80]}')
    return {"text": text}


def _blk_type_cast(params: dict, inputs: dict, ctx: ExecContext) -> dict:
    value = inputs.get("value")
    to = str(params.get("to_type", "float"))
    try:
        if to == "float":
            result = float(value)
        elif to == "int":
            result = int(float(value))
        elif to == "str":
            result = str(value)
        elif to == "bool":
            result = bool(value)
        elif to == "list":
            result = list(value) if hasattr(value, "__iter__") else [value]
        elif to == "dict":
            result = dict(value) if isinstance(value, dict) else {"value": value}
        elif to == "json_str":
            result = json.dumps(value, default=str)
        else:
            result = value
    except Exception as e:
        ctx.log(f"⇄ Cast error: {e}")
        result = value
    ctx.log(f"⇄ Cast to {to}: {_summarise(result)}")
    return {"result": result}


def _blk_pick_field(params: dict, inputs: dict, ctx: ExecContext) -> dict:
    data = inputs.get("data", {})
    fields = [f.strip() for f in str(params.get("fields", "")).split(",") if f.strip()]
    if not isinstance(data, dict):
        return {"result": {}}
    result = {k: data[k] for k in fields if k in data}
    ctx.log(f"⊙ Pick: {list(result.keys())} from {len(data)} fields")
    return {"result": result}


# ── NEW: I/O blocks ──────────────────────────────────────────────────

def _blk_plot_xy(params: dict, inputs: dict, ctx: ExecContext) -> dict:
    """XY scatter/line plot — returns Plotly-compatible data."""
    x = inputs.get("x", [])
    y = inputs.get("y", [])
    title = str(params.get("title", "XY Plot"))
    mode = str(params.get("mode", "markers"))
    ctx.log(f"📊 Plot XY: '{title}', {len(x) if isinstance(x, list) else '?'} points")
    return {}


def _blk_plot_histogram(params: dict, inputs: dict, ctx: ExecContext) -> dict:
    data = inputs.get("data", [])
    title = str(params.get("title", "Histogram"))
    ctx.log(f"▊ Plot histogram: '{title}'")
    return {}


def _blk_plot_heatmap(params: dict, inputs: dict, ctx: ExecContext) -> dict:
    data = inputs.get("data", {})
    title = str(params.get("title", "Heatmap"))
    ctx.log(f"🗺️ Plot heatmap: '{title}'")
    return {}


def _blk_gauge_display(params: dict, inputs: dict, ctx: ExecContext) -> dict:
    value = _to_number(inputs.get("value", 0))
    title = str(params.get("title", "Gauge"))
    unit = str(params.get("unit", ""))
    ctx.log(f"🎯 Gauge '{title}': {value}{unit}")
    return {}


def _blk_table_display(params: dict, inputs: dict, ctx: ExecContext) -> dict:
    data = inputs.get("data")
    ctx.log(f"📋 Table display: {type(data).__name__}")
    return {}


def _blk_assert_check(params: dict, inputs: dict, ctx: ExecContext) -> dict:
    cond = bool(inputs.get("condition", False))
    msg = str(params.get("message", "Assertion failed!"))
    action = str(params.get("fail_action", "log"))
    if not cond:
        ctx.log(f"❌ Assert FAILED: {msg}")
        if action == "stop":
            ctx.stop_requested = True
    else:
        ctx.log(f"✓ Assert PASSED")
    return {"pass": cond}


# ── NEW: Flow control blocks ────────────────────────────────────────

def _blk_sequence(params: dict, inputs: dict, ctx: ExecContext) -> dict:
    ctx.log("⟶ Sequence: forwarding step_2")
    return {"last": inputs.get("step_2", inputs.get("step_1"))}


def _blk_null_check(params: dict, inputs: dict, ctx: ExecContext) -> dict:
    value = inputs.get("value")
    is_null = value is None
    if is_null:
        default = params.get("default_val", "0")
        try:
            value = json.loads(default)
        except (json.JSONDecodeError, TypeError):
            try:
                value = float(default)
            except ValueError:
                value = default
    ctx.log(f"∅ Null check: {'null → default' if is_null else 'has value'}")
    return {"value": value, "is_null": is_null}


def _blk_try_catch(params: dict, inputs: dict, ctx: ExecContext) -> dict:
    data = inputs.get("data")
    ctx.log("🛡️ Try/Catch: pass-through (no error)")
    return {"data": data, "error": ""}


# ── NEW: Action blocks ──────────────────────────────────────────────

def _blk_tx_burst_test(params: dict, inputs: dict, ctx: ExecContext) -> dict:
    """Simulated TX burst profile test."""
    import numpy as np

    duration = float(params.get("duration_s", 3))
    interval_ms = float(params.get("interval_ms", 100))
    max_peak = float(params.get("max_peak_ma", 50))
    max_avg = float(params.get("max_avg_ma", 5))

    rate = 10000
    n = int(rate * duration)
    t = np.linspace(0, duration, n)
    # Baseline sleep current
    current = 0.5e-3 + np.random.normal(0, 0.05e-3, n)
    # Add TX bursts
    burst_samples = int(rate * interval_ms / 1000)
    for i in range(0, n, burst_samples):
        burst_w = max(1, burst_samples // 5)
        current[i:min(i + burst_w, n)] += 30e-3 + np.random.normal(0, 2e-3, min(burst_w, n - i))

    avg_ma = float(np.mean(current)) * 1e3
    peak_ma = float(np.max(current)) * 1e3
    passed = avg_ma <= max_avg and peak_ma <= max_peak

    ctx.log(f"📡 TX burst: avg={avg_ma:.2f}mA, peak={peak_ma:.1f}mA ({'PASS' if passed else 'FAIL'})")
    return {
        "trace": {"time_s": t.tolist(), "current_a": current.tolist(), "sample_rate_hz": rate, "n_samples": n},
        "verdict": {"overall": "PASS" if passed else "FAIL", "avg_current_ma": round(avg_ma, 3),
                     "peak_current_ma": round(peak_ma, 3), "limit_avg_ma": max_avg, "limit_peak_ma": max_peak},
    }


def _blk_gpio_toggle(params: dict, inputs: dict, ctx: ExecContext) -> dict:
    pin = str(params.get("pin", "P0.13"))
    action = str(params.get("action", "toggle"))
    ctx.log(f"🔀 GPIO {action}: {pin} (simulated)")
    return {"state": True}


def _blk_serial_send(params: dict, inputs: dict, ctx: ExecContext) -> dict:
    port = str(params.get("port", "COM3"))
    command = str(params.get("command", "AT\\r\\n"))
    ctx.log(f"🔌 Serial: {port} → '{command}' (simulated)")
    return {"response": "OK\r\n"}


def _blk_load_profile(params: dict, inputs: dict, ctx: ExecContext) -> dict:
    path = str(params.get("path", "profiles/sleep_current.json"))
    try:
        data = json.loads(pathlib.Path(path).read_text(encoding="utf-8"))
        ctx.log(f"📋 Loaded profile: {path}")
        return {"profile": data}
    except Exception as e:
        ctx.log(f"⚠ Profile load error: {e}")
        return {"profile": {"error": str(e)}}


def _blk_benchmark_timer(params: dict, inputs: dict, ctx: ExecContext) -> dict:
    label = str(params.get("label", "operation"))
    elapsed = ctx.elapsed
    ctx.log(f"⏲️ Timer '{label}': {elapsed:.3f}s elapsed")
    return {"elapsed_s": round(elapsed, 6)}


def _blk_shell_cmd(params: dict, inputs: dict, ctx: ExecContext) -> dict:
    cmd = str(params.get("command", "echo hello"))
    timeout = float(params.get("timeout_s", 30))
    ctx.log(f"⌨️ Shell: {cmd}")
    try:
        result = subprocess.run(
            cmd, shell=True, capture_output=True, text=True,
            timeout=timeout, cwd=str(pathlib.Path.cwd()),
        )
        ctx.log(f"   stdout: {result.stdout.strip()[:200]}")
        if result.returncode != 0:
            ctx.log(f"   stderr: {result.stderr.strip()[:200]}")
        return {"stdout": result.stdout, "exit_code": result.returncode}
    except subprocess.TimeoutExpired:
        ctx.log(f"   ⚠ Timed out after {timeout}s")
        return {"stdout": "", "exit_code": -1}
    except Exception as exc:
        ctx.log(f"   ❌ {exc}")
        return {"stdout": str(exc), "exit_code": -1}


def _blk_http_request(params: dict, inputs: dict, ctx: ExecContext) -> dict:
    import urllib.request
    import urllib.error

    url = str(params.get("url", "http://localhost:5200/api/health"))
    method = str(params.get("method", "GET"))
    headers_raw = str(params.get("headers", "{}"))

    try:
        hdrs = json.loads(headers_raw) if headers_raw.strip() else {}
    except json.JSONDecodeError:
        hdrs = {}
    hdrs.setdefault("Content-Type", "application/json")

    body_data = inputs.get("body")
    data_bytes = None
    if body_data is not None and method in ("POST", "PUT"):
        data_bytes = json.dumps(body_data, default=str).encode("utf-8")

    ctx.log(f"🌐 {method} {url}")
    try:
        req = urllib.request.Request(url, data=data_bytes, headers=hdrs, method=method)
        with urllib.request.urlopen(req, timeout=30) as resp:
            body = resp.read().decode("utf-8")
            status = resp.status
            try:
                parsed = json.loads(body)
            except json.JSONDecodeError:
                parsed = {"raw": body}
            ctx.log(f"   → {status} ({len(body)} bytes)")
            return {"response": parsed, "status": status}
    except urllib.error.HTTPError as exc:
        ctx.log(f"   → HTTP {exc.code}")
        return {"response": {"error": str(exc)}, "status": exc.code}
    except Exception as exc:
        ctx.log(f"   ❌ {exc}")
        return {"response": {"error": str(exc)}, "status": 0}


def _blk_sleep_test(params: dict, inputs: dict, ctx: ExecContext) -> dict:
    """Full sleep-current measurement flow as one block."""
    duration  = float(params.get("duration_s", 5))
    settle    = float(params.get("settle_s", 1))
    max_avg   = float(params.get("max_avg_ua", 10))

    ctx.log(f"😴 Sleep current test: {duration}s + {settle}s settle, limit={max_avg}µA")

    # Use simulated meter
    import numpy as np
    rate = 1000
    n = int(rate * duration)
    t = np.linspace(0, duration, n)
    # Realistic sleep current: ~5µA with occasional wake spikes
    current = 5e-6 + np.random.normal(0, 0.5e-6, n)
    # Inject a few wake spikes
    for _ in range(3):
        idx = np.random.randint(0, n)
        current[idx:min(idx+50, n)] += 2e-3

    avg = float(np.mean(current))
    avg_ua = avg * 1e6
    passed = avg_ua <= max_avg

    trace = {"time_s": t.tolist(), "current_a": current.tolist(),
             "sample_rate_hz": rate, "n_samples": n}
    verdict = {
        "overall": "PASS" if passed else "FAIL",
        "avg_current_ua": round(avg_ua, 3),
        "max_current_ua": round(float(np.max(current)) * 1e6, 3),
        "limit_ua": max_avg,
    }

    emoji = "✅" if passed else "❌"
    ctx.log(f"{emoji} Sleep test: avg={avg_ua:.3f}µA ({'PASS' if passed else 'FAIL'})")
    return {"trace": trace, "verdict": verdict}


# ══════════════════════════════════════════════════════════════════════
# Helpers
# ══════════════════════════════════════════════════════════════════════

def _to_number(v: Any) -> float:
    if isinstance(v, (int, float)):
        return float(v)
    if isinstance(v, str):
        try:
            return float(v)
        except ValueError:
            return 0.0
    return 0.0


def _summarise(v: Any, max_len: int = 80) -> str:
    """Short string representation of a value for logging."""
    if v is None:
        return "None"
    if isinstance(v, (int, float, bool)):
        return str(v)
    s = str(v)
    return s[:max_len] + ("…" if len(s) > max_len else "")


# ══════════════════════════════════════════════════════════════════════
# Engine
# ══════════════════════════════════════════════════════════════════════

class FlowLabEngine:
    """Topological-sort dataflow executor."""

    block_registry: dict[str, BlockHandler] = {
        # Instruments
        "simulated_power": _blk_simulated_power,
        "csv_file":        _blk_csv_file,
        "csv_replay":      _blk_csv_replay,
        "aoi_camera":      _blk_aoi_camera,
        "seek_thermal":    _blk_seek_thermal,
        "ppk2_meter":      _blk_ppk2_meter,
        "ad3_dwf_meter":   _blk_ad3_dwf_meter,
        "waveform_gen":    _blk_waveform_gen,
        "random_data":     _blk_random_data,
        # Android phone sensors
        "android_accel":   _blk_android_accel,
        "android_gyro":    _blk_android_gyro,
        "android_mag":     _blk_android_mag,
        "android_mic":     _blk_android_mic,
        "android_proximity": _blk_android_proximity,
        "android_light":   _blk_android_light,
        "android_pressure": _blk_android_pressure,
        "android_gps":     _blk_android_gps,
        "android_battery": _blk_android_battery,
        "android_gravity": _blk_android_gravity,
        "android_rotation": _blk_android_rotation,
        "android_torch":   _blk_android_torch,
        "lux_measure":     _blk_lux_measure,
        # Analysis
        "stats":           _blk_stats,
        "filter":          _blk_filter,
        "highpass_filter":  _blk_highpass_filter,
        "bandpass_filter":  _blk_bandpass_filter,
        "fft_spectrum":    _blk_fft_spectrum,
        "moving_average":  _blk_moving_average,
        "derivative":      _blk_derivative,
        "integral":        _blk_integral,
        "threshold":       _blk_threshold,
        "window_slice":    _blk_window_slice,
        "resample":        _blk_resample,
        "edge_detect":     _blk_edge_detect,
        "histogram":       _blk_histogram,
        "correlate":       _blk_correlate,
        # Vision
        "thermal_analyze": _blk_thermal_analyze,
        "aoi_inspect":     _blk_aoi_inspect,
        "color_detect":    _blk_color_detect,
        "blob_detect":     _blk_blob_detect,
        "template_match":  _blk_template_match,
        "image_resize":    _blk_image_resize,
        "image_crop":      _blk_image_crop,
        "image_threshold": _blk_image_threshold,
        # Math
        "expression":      _blk_expression,
        "constant":        _blk_constant,
        "multiply":        _blk_multiply,
        "add":             _blk_add,
        "subtract":        _blk_subtract,
        "divide":          _blk_divide,
        "abs_val":         _blk_abs_val,
        "power":           _blk_power,
        "log_math":        _blk_log_math,
        "trig":            _blk_trig,
        "clamp":           _blk_clamp,
        "map_range":       _blk_map_range,
        "compare":         _blk_compare,
        "unit_convert":    _blk_unit_convert,
        # Data
        "dict_get":        _blk_dict_get,
        "dict_set":        _blk_dict_set,
        "dict_build":      _blk_dict_build,
        "list_build":      _blk_list_build,
        "json_parse":      _blk_json_parse,
        "format_string":   _blk_format_string,
        "type_cast":       _blk_type_cast,
        "pick_field":      _blk_pick_field,
        # I/O
        "display":         _blk_display,
        "plot_trace":      _blk_plot_trace,
        "plot_xy":         _blk_plot_xy,
        "plot_histogram":  _blk_plot_histogram,
        "plot_heatmap":    _blk_plot_heatmap,
        "gauge_display":   _blk_gauge_display,
        "table_display":   _blk_table_display,
        "save_file":       _blk_save_file,
        "log_message":     _blk_log_message,
        "assert_check":    _blk_assert_check,
        # Flow
        "delay":           _blk_delay,
        "repeat":          _blk_repeat,
        "gate":            _blk_gate,
        "merge":           _blk_merge,
        "sequence":        _blk_sequence,
        "null_check":      _blk_null_check,
        "try_catch":       _blk_try_catch,
        # Actions
        "shell_cmd":       _blk_shell_cmd,
        "http_request":    _blk_http_request,
        "sleep_test":      _blk_sleep_test,
        "tx_burst_test":   _blk_tx_burst_test,
        "gpio_toggle":     _blk_gpio_toggle,
        "serial_send":     _blk_serial_send,
        "load_profile":    _blk_load_profile,
        "benchmark_timer": _blk_benchmark_timer,
    }

    def __init__(self) -> None:
        self._stop = False

    def request_stop(self) -> None:
        self._stop = True

    def execute(self, diagram: dict[str, Any]) -> dict[str, Any]:
        """Execute a serialised diagram and return results."""
        self._stop = False
        ctx = ExecContext()

        blocks_raw = diagram.get("blocks", [])
        wires_raw  = diagram.get("wires", [])

        # Build adjacency
        block_map: dict[str, dict] = {b["id"]: b for b in blocks_raw}
        # in_edges[block_id] = set of upstream block ids
        in_edges: dict[str, set[str]] = defaultdict(set)
        # wire_map: (to_block, to_port) → (from_block, from_port)
        wire_map: dict[tuple[str, str], tuple[str, str]] = {}

        for w in wires_raw:
            src_blk  = w["from"]["block"]
            src_port = w["from"]["port"]
            dst_blk  = w["to"]["block"]
            dst_port = w["to"]["port"]
            in_edges[dst_blk].add(src_blk)
            wire_map[(dst_blk, dst_port)] = (src_blk, src_port)

        # Topological sort (Kahn's algorithm)
        in_degree: dict[str, int] = {bid: 0 for bid in block_map}
        for bid, deps in in_edges.items():
            if bid in in_degree:
                in_degree[bid] = len(deps)

        queue: deque[str] = deque()
        for bid, deg in in_degree.items():
            if deg == 0:
                queue.append(bid)

        order: list[str] = []
        while queue:
            bid = queue.popleft()
            order.append(bid)
            # Find downstream blocks
            for w in wires_raw:
                if w["from"]["block"] == bid:
                    dst = w["to"]["block"]
                    in_degree[dst] -= 1
                    if in_degree[dst] == 0:
                        queue.append(dst)

        if len(order) != len(block_map):
            ctx.log("⚠ Cycle detected in diagram — some blocks unreachable")

        # Execute in order
        port_values: dict[str, dict[str, Any]] = {}  # block_id → {port: value}
        overall_verdict = None

        for bid in order:
            if self._stop:
                ctx.log("⏹ Execution stopped by user")
                break

            bdef = block_map.get(bid)
            if not bdef:
                continue

            btype = bdef.get("type", "")
            handler = self.block_registry.get(btype)

            if not handler:
                ctx.log(f"⚠ Unknown block type: {btype}")
                ctx.block_results[bid] = {"error": f"Unknown type: {btype}"}
                continue

            # Gather inputs from upstream wires
            inputs: dict[str, Any] = {}
            for w in wires_raw:
                if w["to"]["block"] == bid:
                    src_bid  = w["from"]["block"]
                    src_port = w["from"]["port"]
                    dst_port = w["to"]["port"]
                    if src_bid in port_values and src_port in port_values[src_bid]:
                        inputs[dst_port] = port_values[src_bid][src_port]

            # Execute
            try:
                outputs = handler(bdef.get("params", {}), inputs, ctx)
                port_values[bid] = outputs or {}
                ctx.block_results[bid] = {"ok": True, "outputs": _safe_json(outputs)}

                # Track verdict
                if isinstance(outputs, dict):
                    for v in outputs.values():
                        if isinstance(v, dict) and "overall" in v:
                            overall_verdict = v["overall"]
                        if isinstance(v, bool):
                            if overall_verdict is None:
                                overall_verdict = "PASS" if v else "FAIL"

            except Exception as exc:
                logger.exception("FlowLab block %s (%s) failed", bid, btype)
                ctx.log(f"❌ Block {bid} ({btype}): {exc}")
                ctx.block_results[bid] = {"error": str(exc)}
                port_values[bid] = {}

        return {
            "block_results": ctx.block_results,
            "console": ctx.console,
            "verdict": overall_verdict,
            "elapsed_s": round(ctx.elapsed, 3),
        }


def _safe_json(obj: Any) -> Any:
    """Make an object JSON-safe by converting non-serialisable types."""
    try:
        json.dumps(obj)
        return obj
    except (TypeError, ValueError):
        if isinstance(obj, dict):
            return {k: _safe_json(v) for k, v in obj.items()}
        if isinstance(obj, (list, tuple)):
            return [_safe_json(v) for v in obj]
        return str(obj)
