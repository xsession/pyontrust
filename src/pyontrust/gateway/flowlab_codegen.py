"""FlowLab → standalone Python code generator.

Converts a serialised FlowLab diagram (blocks + wires) into a self-contained
Python script that reproduces the same dataflow without requiring the FlowLab
UI or the gateway server.

The generated script:
- Uses only stdlib + numpy + scipy (optional) + requests (optional)
- Follows the same topological execution order as FlowLabEngine
- Preserves all block parameters as inline constants
- Prints results / writes files exactly as the engine would
- Embeds the original diagram JSON (base64) for re-import into FlowLab
"""
from __future__ import annotations

import base64
import json
import textwrap
from collections import defaultdict, deque
from typing import Any

# ═══════════════════════════════════════════════════════════════════════
# Diagram extraction from exported Python scripts
# ═══════════════════════════════════════════════════════════════════════

_FLOWLAB_MARKER = "# FLOWLAB_DIAGRAM: "


def extract_diagram_from_python(source: str) -> dict[str, Any] | None:
    """Extract the embedded FlowLab diagram from an exported Python script.

    The diagram is stored as a base64-encoded JSON string in a comment line
    starting with ``# FLOWLAB_DIAGRAM: ``.

    Parameters
    ----------
    source : str
        The Python source code to scan.

    Returns
    -------
    dict or None
        The deserialised diagram, or *None* if no embedded diagram was found.
    """
    for line in source.splitlines():
        stripped = line.strip()
        if stripped.startswith(_FLOWLAB_MARKER):
            b64_data = stripped[len(_FLOWLAB_MARKER):]
            try:
                raw = base64.b64decode(b64_data)
                return json.loads(raw)
            except Exception:
                return None
    return None


# ═══════════════════════════════════════════════════════════════════════
# Per-block code templates
# ═══════════════════════════════════════════════════════════════════════
# Each template receives:
#   bid       – sanitised variable prefix e.g. "blk_1"
#   params    – dict of parameter values
#   inputs    – dict  port_name → "variable_expression"
#   outputs   – list of (port_name, var_name)  that the caller expects
#
# Templates must assign all output variables.

_IMPORTS: dict[str, set[str]] = {}  # populated per-diagram


def _py(val: Any) -> str:
    """Render a Python literal."""
    if isinstance(val, bool):
        return "True" if val else "False"
    if isinstance(val, str):
        return repr(val)
    if isinstance(val, (int, float)):
        return repr(val)
    return repr(val)


# ── Instruments ──────────────────────────────────────────────────────

def _gen_simulated_power(bid, params, inputs, outs):
    rate = params.get("sample_rate_hz", 1000)
    dur = params.get("duration_s", 2)
    base = params.get("base_current_a", 0.001)
    noise = params.get("noise_a", 0.0001)
    return [
        f"# ── Simulated Power Meter ──",
        f"_rate = {_py(rate)}",
        f"_dur  = {_py(dur)}",
        f"_n    = int(_rate * _dur)",
        f"_t    = np.linspace(0, _dur, _n)",
        f"_curr = {_py(base)} + np.random.normal(0, {_py(noise)}, _n)",
        f"{outs['trace']} = {{'time_s': _t.tolist(), 'current_a': _curr.tolist(), 'sample_rate_hz': _rate, 'n_samples': _n}}",
        f'print(f"[simulated_power] {{_n}} samples, {{_dur}}s @ {{_rate}} Hz")',
    ], {"numpy"}


def _gen_csv_file(bid, params, inputs, outs):
    path = params.get("path", "artifacts/trace.csv")
    tc = params.get("time_col", "time_s")
    cc = params.get("current_col", "current_a")
    return [
        f"# ── CSV File Reader ──",
        f"_times, _currents = [], []",
        f"with open({_py(path)}, newline='', encoding='utf-8') as _f:",
        f"    _reader = csv.DictReader(_f)",
        f"    for _row in _reader:",
        f"        try:",
        f"            _times.append(float(_row[{_py(tc)}]))",
        f"            _currents.append(float(_row[{_py(cc)}]))",
        f"        except (KeyError, ValueError):",
        f"            continue",
        f"{outs['trace']} = {{'time_s': _times, 'current_a': _currents, 'n_samples': len(_times)}}",
        f'print(f"[csv_file] Loaded {{len(_times)}} samples from {path}")',
    ], {"csv"}


def _gen_csv_replay(bid, params, inputs, outs):
    # Delegates to csv_file logic
    return _gen_csv_file(bid, params, inputs, outs)


def _gen_aoi_camera(bid, params, inputs, outs):
    mode = params.get("mode", "simulated")
    w = params.get("width", 640)
    h = params.get("height", 480)
    return [
        f"# ── AOI Camera ──",
        f"from pyontrust.instruments.aoi_camera import create as _create_aoi",
        f"_cam = _create_aoi({{'mode': {_py(mode)}, 'width': {_py(w)}, 'height': {_py(h)}}})",
        f"_cam.open()",
        f"try:",
        f"    _frame = _cam.grab_frame()",
        f"    {outs['frame']} = {{'shape': list(_frame.shape), 'dtype': str(_frame.dtype), 'data': _frame}}",
        f'    print(f"[aoi_camera] Frame: {{_frame.shape}}")',
        f"finally:",
        f"    _cam.close()",
    ], set()


def _gen_seek_thermal(bid, params, inputs, outs):
    mode = params.get("mode", "simulated")
    base = params.get("base_temp_c", 25)
    hotspot = params.get("inject_hotspot", False)
    return [
        f"# ── Seek Thermal Camera ──",
        f"from pyontrust.instruments.seek_thermal import create as _create_thermal",
        f"_cam = _create_thermal({{'mode': {_py(mode)}, 'base_temp_c': {_py(base)}, 'inject_hotspot': {_py(hotspot)}}})",
        f"_cam.open()",
        f"try:",
        f"    _thframe = _cam.grab_temperature_frame()",
        f"    _mean_t = float(np.mean(_thframe))",
        f"    {outs['thermal']} = {{'shape': list(_thframe.shape), 'mean_c': round(_mean_t, 2), 'max_c': round(float(np.max(_thframe)), 2), 'min_c': round(float(np.min(_thframe)), 2)}}",
        f"    {outs['temp_c']} = round(_mean_t, 2)",
        f'    print(f"[seek_thermal] mean={{_mean_t:.1f}}C")',
        f"finally:",
        f"    _cam.close()",
    ], {"numpy"}


def _gen_ppk2_meter(bid, params, inputs, outs):
    port = params.get("serial_port", "")
    vdd = params.get("vdd_mv", 3300)
    rate = params.get("sample_rate_hz", 100000)
    dur = params.get("duration_s", 2)
    return [
        f"# ── PPK2 Meter ──",
        f"from pyontrust.instruments.ppk2 import PPK2",
        f"_ppk = PPK2(port={_py(port)}, vdd_mv={_py(vdd)})",
        f"_ppk.open()",
        f"try:",
        f"    _trace = _ppk.measure(sample_rate_hz={_py(rate)}, duration_s={_py(dur)})",
        f"    {outs['trace']} = _trace",
        f'    print(f"[ppk2_meter] Captured trace")',
        f"finally:",
        f"    _ppk.close()",
    ], set()


def _gen_ad3_dwf_meter(bid, params, inputs, outs):
    di = params.get("device_index", 0)
    ch = params.get("channel", 0)
    shunt = params.get("shunt_ohm", 1.0)
    rate = params.get("sample_rate_hz", 10000)
    dur = params.get("duration_s", 2)
    vdd = params.get("vdd_v", 3.3)
    return [
        f"# ── AD3 / DWF Power Meter ──",
        f"from pyontrust.instruments.ad3_dwf_power_meter import AD3DWFPowerMeter",
        f"_meter = AD3DWFPowerMeter(device_index={_py(di)}, channel={_py(ch)}, shunt_ohm={_py(shunt)}, vdd_v={_py(vdd)})",
        f"_meter.open()",
        f"try:",
        f"    _trace = _meter.measure(sample_rate_hz={_py(rate)}, duration_s={_py(dur)})",
        f"    {outs['trace']} = _trace",
        f'    print(f"[ad3_dwf_meter] Captured trace")',
        f"finally:",
        f"    _meter.close()",
    ], set()


def _gen_waveform_gen(bid, params, inputs, outs):
    shape = params.get("shape", "sine")
    freq = params.get("frequency_hz", 100)
    amp = params.get("amplitude", 1.0)
    off = params.get("offset", 0)
    duty = params.get("duty_cycle", 0.5)
    dur = params.get("duration_s", 1)
    rate = params.get("sample_rate_hz", 10000)
    return [
        f"# ── Waveform Generator ──",
        f"_n = int({_py(rate)} * {_py(dur)})",
        f"_t = np.linspace(0, {_py(dur)}, _n)",
        f"_ft = {_py(freq)} * _t",
        f"if {_py(shape)} == 'sine':",
        f"    _y = np.sin(2 * np.pi * _ft)",
        f"elif {_py(shape)} == 'square':",
        f"    _y = np.sign(np.sin(2 * np.pi * _ft))",
        f"elif {_py(shape)} == 'triangle':",
        f"    _y = 2 * np.abs(2 * (_ft - np.floor(_ft + 0.5))) - 1",
        f"elif {_py(shape)} == 'sawtooth':",
        f"    _y = 2 * (_ft - np.floor(_ft)) - 1",
        f"elif {_py(shape)} == 'dc':",
        f"    _y = np.ones(_n)",
        f"elif {_py(shape)} == 'noise':",
        f"    _y = np.random.normal(0, 1, _n)",
        f"elif {_py(shape)} == 'chirp':",
        f"    _y = np.sin(2 * np.pi * _ft * _t / {_py(dur)})",
        f"else:",
        f"    _y = np.zeros(_n)",
        f"_current = {_py(amp)} * _y + {_py(off)}",
        f"{outs['trace']} = {{'time_s': _t.tolist(), 'current_a': _current.tolist(), 'sample_rate_hz': {_py(rate)}, 'n_samples': _n}}",
        f'print(f"[waveform_gen] {shape} — {{_n}} samples")',
    ], {"numpy"}


def _gen_random_data(bid, params, inputs, outs):
    dist = params.get("distribution", "normal")
    size = params.get("size", 1000)
    p1 = params.get("param1", 0)
    p2 = params.get("param2", 1)
    return [
        f"# ── Random Data ──",
        f"if {_py(dist)} == 'normal':",
        f"    {outs['data']} = np.random.normal({_py(p1)}, {_py(p2)}, {_py(size)}).tolist()",
        f"elif {_py(dist)} == 'uniform':",
        f"    {outs['data']} = np.random.uniform({_py(p1)}, {_py(p2)}, {_py(size)}).tolist()",
        f"elif {_py(dist)} == 'poisson':",
        f"    {outs['data']} = np.random.poisson({_py(p1)}, {_py(size)}).tolist()",
        f"elif {_py(dist)} == 'exponential':",
        f"    {outs['data']} = np.random.exponential({_py(p1)} if {_py(p1)} > 0 else 1, {_py(size)}).tolist()",
        f"else:",
        f"    {outs['data']} = np.random.beta(max(0.1, {_py(p1)}), max(0.1, {_py(p2)}), {_py(size)}).tolist()",
        f'print(f"[random_data] {dist} — {size} samples")',
    ], {"numpy"}


# ── Android Phone Sensors ────────────────────────────────────────────

def _gen_android_sensor_setup(mode):
    """Common setup lines for Android sensors."""
    return [
        f"from pyontrust.instruments.android_sensors import create as _create_android",
        f"_android = _create_android({{'mode': {_py(mode)}}})",
        f"_android.open()",
    ]


def _gen_android_accel(bid, params, inputs, outs):
    mode = params.get("mode", "simulated")
    dur = params.get("duration_s", 1)
    rate = params.get("sample_rate_hz", 50)
    lines = _gen_android_sensor_setup(mode) + [
        f"try:",
        f"    _data = _android.read_accelerometer({_py(dur)})",
        f"    {outs['accel']} = _data",
        f"    {outs['trace']} = {{'time_s': _data.get('time_s', []), 'current_a': _data.get('magnitude', []), 'sample_rate_hz': {_py(rate)}, 'n_samples': _data.get('n_samples', 0)}}",
        "    print(f\"[android_accel] x={_data.get('x',0):.3f} y={_data.get('y',0):.3f} z={_data.get('z',0):.3f} m/s²\")",
        f"finally:",
        f"    _android.close()",
    ]
    return lines, set()


def _gen_android_gyro(bid, params, inputs, outs):
    mode = params.get("mode", "simulated")
    dur = params.get("duration_s", 1)
    rate = params.get("sample_rate_hz", 50)
    lines = _gen_android_sensor_setup(mode) + [
        f"try:",
        f"    _data = _android.read_gyroscope({_py(dur)})",
        f"    {outs['gyro']} = _data",
        f"    {outs['trace']} = {{'time_s': _data.get('time_s', []), 'current_a': _data.get('magnitude', []), 'sample_rate_hz': {_py(rate)}, 'n_samples': _data.get('n_samples', 0)}}",
        "    print(f\"[android_gyro] x={_data.get('x',0):.3f} y={_data.get('y',0):.3f} z={_data.get('z',0):.3f} rad/s\")",
        f"finally:",
        f"    _android.close()",
    ]
    return lines, set()


def _gen_android_mag(bid, params, inputs, outs):
    mode = params.get("mode", "simulated")
    dur = params.get("duration_s", 1)
    rate = params.get("sample_rate_hz", 50)
    lines = _gen_android_sensor_setup(mode) + [
        f"try:",
        f"    _data = _android.read_magnetometer({_py(dur)})",
        f"    {outs['mag']} = _data",
        f"    {outs['trace']} = {{'time_s': _data.get('time_s', []), 'current_a': _data.get('magnitude', []), 'sample_rate_hz': {_py(rate)}, 'n_samples': _data.get('n_samples', 0)}}",
        "    print(f\"[android_mag] x={_data.get('x',0):.1f} y={_data.get('y',0):.1f} z={_data.get('z',0):.1f} µT\")",
        f"finally:",
        f"    _android.close()",
    ]
    return lines, set()


def _gen_android_mic(bid, params, inputs, outs):
    mode = params.get("mode", "simulated")
    dur = params.get("duration_s", 2)
    sr = params.get("sample_rate", 16000)
    lv = outs["level_db"]
    lines = _gen_android_sensor_setup(mode) + [
        f"try:",
        f"    _data = _android.read_microphone({_py(dur)}, {_py(int(sr))})",
        f"    {outs['audio']} = {{'time_s': _data.get('time_s', []), 'current_a': _data.get('samples', []), 'sample_rate_hz': {_py(int(sr))}, 'n_samples': _data.get('n_samples', 0)}}",
        f"    {lv} = _data.get('level_db', -60)",
        "    print(f\"[android_mic] {_data.get('n_samples',0)} samples, level={" + lv + ":.1f} dB\")",
        f"finally:",
        f"    _android.close()",
    ]
    return lines, set()


def _gen_android_proximity(bid, params, inputs, outs):
    mode = params.get("mode", "simulated")
    dv = outs["distance"]
    nv = outs["near"]
    lines = _gen_android_sensor_setup(mode) + [
        f"try:",
        f"    _data = _android.read_proximity(0.5)",
        f"    {dv} = _data.get('distance', 5.0)",
        f"    {nv} = {dv} < 1.0",
        "    print(f\"[android_proximity] {" + dv + ":.1f} cm ({'NEAR' if " + nv + " else 'FAR'})\")",
        f"finally:",
        f"    _android.close()",
    ]
    return lines, set()


def _gen_android_light(bid, params, inputs, outs):
    mode = params.get("mode", "simulated")
    dur = params.get("duration_s", 1)
    lv = outs["lux"]
    lines = _gen_android_sensor_setup(mode) + [
        f"try:",
        f"    _data = _android.read_light({_py(dur)})",
        f"    {lv} = float(_data.get('lux', _data.get('mean', 0)))",
        "    print(f\"[android_light] {" + lv + ":.0f} lux\")",
        f"finally:",
        f"    _android.close()",
    ]
    return lines, set()


def _gen_android_pressure(bid, params, inputs, outs):
    mode = params.get("mode", "simulated")
    dur = params.get("duration_s", 1)
    hv = outs["hpa"]
    lines = _gen_android_sensor_setup(mode) + [
        f"try:",
        f"    _data = _android.read_barometer({_py(dur)})",
        f"    {hv} = float(_data.get('hpa', _data.get('mean', 1013.25)))",
        "    print(f\"[android_pressure] {" + hv + ":.1f} hPa\")",
        f"finally:",
        f"    _android.close()",
    ]
    return lines, set()


def _gen_android_gps(bid, params, inputs, outs):
    mode = params.get("mode", "simulated")
    loc = outs["location"]
    lines = _gen_android_sensor_setup(mode) + [
        f"try:",
        f"    {loc} = _android.read_gps()",
        "    print(f\"[android_gps] lat={" + loc + ".get('latitude',0):.5f} lon={" + loc + ".get('longitude',0):.5f}\")",
        f"finally:",
        f"    _android.close()",
    ]
    return lines, set()


def _gen_android_battery(bid, params, inputs, outs):
    mode = params.get("mode", "simulated")
    bv = outs["battery"]
    lines = _gen_android_sensor_setup(mode) + [
        f"try:",
        f"    {bv} = _android.read_battery()",
        "    print(f\"[android_battery] {" + bv + ".get('level',0)}% {" + bv + ".get('status','?')}\")",
        f"finally:",
        f"    _android.close()",
    ]
    return lines, set()


def _gen_android_gravity(bid, params, inputs, outs):
    mode = params.get("mode", "simulated")
    dur = params.get("duration_s", 1)
    rate = params.get("sample_rate_hz", 50)
    lines = _gen_android_sensor_setup(mode) + [
        f"try:",
        f"    _data = _android.read_gravity({_py(dur)})",
        f"    {outs['gravity']} = _data",
        f"    {outs['trace']} = {{'time_s': _data.get('time_s', []), 'current_a': _data.get('magnitude', []), 'sample_rate_hz': {_py(rate)}, 'n_samples': _data.get('n_samples', 0)}}",
        "    print(f\"[android_gravity] x={_data.get('x',0):.3f} y={_data.get('y',0):.3f} z={_data.get('z',0):.3f} m/s²\")",
        f"finally:",
        f"    _android.close()",
    ]
    return lines, set()


def _gen_android_rotation(bid, params, inputs, outs):
    mode = params.get("mode", "simulated")
    dur = params.get("duration_s", 1)
    rate = params.get("sample_rate_hz", 50)
    lines = _gen_android_sensor_setup(mode) + [
        f"try:",
        f"    _data = _android.read_rotation({_py(dur)})",
        f"    {outs['rotation']} = _data",
        f"    {outs['trace']} = {{'time_s': _data.get('time_s', []), 'current_a': _data.get('magnitude', []), 'sample_rate_hz': {_py(rate)}, 'n_samples': _data.get('n_samples', 0)}}",
        "    print(f\"[android_rotation] x={_data.get('x',0):.3f} y={_data.get('y',0):.3f} z={_data.get('z',0):.3f} w={_data.get('w',0):.3f}\")",
        f"finally:",
        f"    _android.close()",
    ]
    return lines, set()


def _gen_android_torch(bid, params, inputs, outs):
    mode = params.get("mode", "simulated")
    state = params.get("state", "on")
    ov = outs["ok"]
    sv = outs["state"]
    lines = [
        f"# ── Android Torch ──",
        f"from pyontrust.analysis.lux_measurement import SimulatedTorch, torch_on, torch_off",
    ]
    if mode == "simulated":
        lines += [
            f"_torch = SimulatedTorch()",
            f"{ov} = _torch.on()" if state == "on" else f"{ov} = _torch.off()",
        ]
    else:
        lines += [
            f"{ov} = torch_on()" if state == "on" else f"{ov} = torch_off()",
        ]
    lines += [
        f"{sv} = {_py(state)}",
        f'print(f"[android_torch] {{{sv}}} ok={{{ov}}}")',
    ]
    return lines, set()


def _gen_lux_measure(bid, params, inputs, outs):
    n_cycles = params.get("n_cycles", 3)
    torch_on_s = params.get("torch_on_s", 3)
    torch_off_s = params.get("torch_off_s", 3)
    android_mode = params.get("android_mode", "simulated")
    rv = outs["result"]
    wv = outs["webcam_lux"]
    av = outs["android_lux"]
    cv = outs["correlation"]
    lines = [
        f"# ── Parallel Lux Measurement ──",
        f"from pyontrust.analysis.lux_measurement import LuxCaptureConfig, measure_parallel_lux",
        f"_lux_cfg = LuxCaptureConfig(",
        f"    n_cycles={_py(n_cycles)},",
        f"    torch_on_s={_py(torch_on_s)},",
        f"    torch_off_s={_py(torch_off_s)},",
        f"    android_mode={_py(android_mode)},",
        f")",
        f"_use_real = {_py(android_mode)} != 'simulated'",
        f"_lux_result = measure_parallel_lux(_lux_cfg, use_real_torch=_use_real)",
        f"{rv} = _lux_result.summary()",
        f"{wv} = _lux_result.webcam_lux",
        f"{av} = _lux_result.android_lux",
        f"{cv} = _lux_result.correlation",
        f'print(f"[lux_measure] ok={{_lux_result.ok}} corr={{{cv}}}")',
    ]
    return lines, set()


# ── Analysis ─────────────────────────────────────────────────────────

def _gen_stats(bid, params, inputs, outs):
    return [
        f"# ── Statistics ──",
        f"_data = {inputs.get('trace', '{}')}.get('current_a', [])",
        f"if _data:",
        f"    _arr = np.array(_data, dtype=float)",
        f"    {outs['result']} = {{'avg_current_a': round(float(np.mean(_arr)), 9), 'max_current_a': round(float(np.max(_arr)), 9), 'min_current_a': round(float(np.min(_arr)), 9), 'std_current_a': round(float(np.std(_arr)), 9), 'rms_current_a': round(float(np.sqrt(np.mean(_arr**2))), 9), 'n_samples': len(_data)}}",
        f"else:",
        f"    {outs['result']} = {{'error': 'no data'}}",
        f'print(f"[stats] {{len(_data)}} samples analysed")',
    ], {"numpy"}


def _gen_filter(bid, params, inputs, outs):
    cutoff = params.get("cutoff_hz", 50)
    order = params.get("order", 4)
    return [
        f"# ── Low-Pass Filter ──",
        f"_trace = {inputs.get('trace', '{}')}",
        f"_data = _trace.get('current_a', [])",
        f"_rate = _trace.get('sample_rate_hz', 1000)",
        f"if _data and _rate > 0:",
        f"    from scipy.signal import butter, sosfilt",
        f"    _nyq = _rate / 2",
        f"    _co = min({_py(cutoff)}, _nyq * 0.99)",
        f"    _sos = butter({_py(order)}, _co / _nyq, btype='low', output='sos')",
        f"    _filtered = sosfilt(_sos, np.array(_data)).tolist()",
        f"    {outs['filtered']} = {{**_trace, 'current_a': _filtered}}",
        f"else:",
        f"    {outs['filtered']} = _trace",
        f'print(f"[filter] LP {{_co if _data else 0:.0f}} Hz, order {order}")',
    ], {"numpy", "scipy"}


def _gen_highpass_filter(bid, params, inputs, outs):
    cutoff = params.get("cutoff_hz", 10)
    order = params.get("order", 4)
    return [
        f"# ── High-Pass Filter ──",
        f"_trace = {inputs.get('trace', '{}')}",
        f"_data = _trace.get('current_a', [])",
        f"_rate = _trace.get('sample_rate_hz', 1000)",
        f"if _data and _rate > 0:",
        f"    from scipy.signal import butter, sosfilt",
        f"    _nyq = _rate / 2",
        f"    _co = min({_py(cutoff)}, _nyq * 0.99)",
        f"    _sos = butter({_py(order)}, _co / _nyq, btype='high', output='sos')",
        f"    _filtered = sosfilt(_sos, np.array(_data)).tolist()",
        f"    {outs['filtered']} = {{**_trace, 'current_a': _filtered}}",
        f"else:",
        f"    {outs['filtered']} = _trace",
        f'print(f"[highpass_filter] HP {cutoff} Hz, order {order}")',
    ], {"numpy", "scipy"}


def _gen_bandpass_filter(bid, params, inputs, outs):
    low = params.get("low_hz", 10)
    high = params.get("high_hz", 100)
    order = params.get("order", 4)
    return [
        f"# ── Band-Pass Filter ──",
        f"_trace = {inputs.get('trace', '{}')}",
        f"_data = _trace.get('current_a', [])",
        f"_rate = _trace.get('sample_rate_hz', 1000)",
        f"if _data and _rate > 0:",
        f"    from scipy.signal import butter, sosfilt",
        f"    _nyq = _rate / 2",
        f"    _lo = min({_py(low)}, _nyq * 0.99)",
        f"    _hi = min({_py(high)}, _nyq * 0.99)",
        f"    _sos = butter({_py(order)}, [_lo / _nyq, _hi / _nyq], btype='band', output='sos')",
        f"    _filtered = sosfilt(_sos, np.array(_data)).tolist()",
        f"    {outs['filtered']} = {{**_trace, 'current_a': _filtered}}",
        f"else:",
        f"    {outs['filtered']} = _trace",
        f'print(f"[bandpass_filter] BP {low}-{high} Hz, order {order}")',
    ], {"numpy", "scipy"}


def _gen_fft_spectrum(bid, params, inputs, outs):
    window = params.get("window", "hann")
    n_peaks = params.get("n_peaks", 5)
    return [
        f"# ── FFT Spectrum ──",
        f"_trace = {inputs.get('trace', '{}')}",
        f"_data = np.array(_trace.get('current_a', []), dtype=float)",
        f"_rate = _trace.get('sample_rate_hz', 1000)",
        f"if len(_data) > 0:",
        f"    from scipy.signal import get_window",
        f"    _win = get_window({_py(window)}, len(_data))",
        f"    _fft = np.fft.rfft(_data * _win)",
        f"    _psd = (np.abs(_fft) ** 2) / len(_data)",
        f"    _freqs = np.fft.rfftfreq(len(_data), 1.0 / _rate)",
        f"    _peak_idx = np.argsort(_psd)[-{_py(n_peaks)}:][::-1]",
        f"    {outs['spectrum']} = {{'frequencies': _freqs.tolist(), 'psd': _psd.tolist()}}",
        f"    {outs['peaks']} = {{'peak_freqs': _freqs[_peak_idx].tolist(), 'peak_powers': _psd[_peak_idx].tolist()}}",
        f"else:",
        f"    {outs['spectrum']} = {{'frequencies': [], 'psd': []}}",
        f"    {outs['peaks']} = {{'peak_freqs': [], 'peak_powers': []}}",
        f'print(f"[fft_spectrum] {{len(_data)}} points, window={window}")',
    ], {"numpy", "scipy"}


def _gen_moving_average(bid, params, inputs, outs):
    ws = params.get("window_size", 50)
    method = params.get("method", "sma")
    return [
        f"# ── Moving Average ──",
        f"_trace = {inputs.get('trace', '{}')}",
        f"_data = np.array(_trace.get('current_a', []), dtype=float)",
        f"if len(_data) > 0:",
        f"    if {_py(method)} == 'ema':",
        f"        import pandas as pd",
        f"        _smoothed = pd.Series(_data).ewm(span={_py(ws)}).mean().values.tolist()",
        f"    elif {_py(method)} == 'median':",
        f"        from scipy.ndimage import median_filter",
        f"        _smoothed = median_filter(_data, size={_py(ws)}).tolist()",
        f"    else:",
        f"        _kernel = np.ones({_py(ws)}) / {_py(ws)}",
        f"        _smoothed = np.convolve(_data, _kernel, mode='same').tolist()",
        f"    {outs['smoothed']} = {{**_trace, 'current_a': _smoothed}}",
        f"else:",
        f"    {outs['smoothed']} = _trace",
        f'print(f"[moving_average] {method}, window={ws}")',
    ], {"numpy"}


def _gen_derivative(bid, params, inputs, outs):
    order = params.get("order", "1")
    return [
        f"# ── Derivative ──",
        f"_trace = {inputs.get('trace', '{}')}",
        f"_data = np.array(_trace.get('current_a', []), dtype=float)",
        f"_dt = _trace.get('time_s', [])",
        f"if len(_data) > 1:",
        f"    _d1 = np.gradient(_data, _dt if len(_dt) == len(_data) else 1).tolist()",
        f"    if {_py(order)} == '2' and len(_d1) > 1:",
        f"        _d1 = np.gradient(np.array(_d1), _dt if len(_dt) == len(_d1) else 1).tolist()",
        f"    {outs['dtrace']} = {{**_trace, 'current_a': _d1}}",
        f"else:",
        f"    {outs['dtrace']} = _trace",
        f'print(f"[derivative] order={order}")',
    ], {"numpy"}


def _gen_integral(bid, params, inputs, outs):
    method = params.get("method", "trapezoid")
    return [
        f"# ── Integral ──",
        f"_trace = {inputs.get('trace', '{}')}",
        f"_data = np.array(_trace.get('current_a', []), dtype=float)",
        f"_t = np.array(_trace.get('time_s', list(range(len(_data)))), dtype=float)",
        f"if len(_data) > 0:",
        f"    if {_py(method)} == 'cumulative':",
        f"        {outs['result']} = {{'cumulative': np.cumsum(_data * np.gradient(_t)).tolist()}}",
        f"    else:",
        f"        {outs['result']} = {{'total': float(np.trapz(_data, _t))}}",
        f"else:",
        f"    {outs['result']} = {{'total': 0}}",
        f'print(f"[integral] method={method}")',
    ], {"numpy"}


def _gen_threshold(bid, params, inputs, outs):
    metric = params.get("metric", "avg_current_a")
    max_v = params.get("max_val", 0.01)
    min_v = params.get("min_val", 0)
    return [
        f"# ── Threshold Check ──",
        f"_val = {inputs.get('value', 'None')}",
        f"if isinstance(_val, dict):",
        f"    _val = _val.get({_py(metric)}, _val)",
        f"_fval = float(_val) if _val is not None else 0",
        f"_pass = {_py(min_v)} <= _fval <= {_py(max_v)}",
        f"{outs['pass']} = _pass",
        f"{outs['value']} = _fval",
        f"print(f\"[threshold] {{_fval}} in [{min_v}, {max_v}] \\u2192 {{'PASS' if _pass else 'FAIL'}}\")",
    ], set()


def _gen_window_slice(bid, params, inputs, outs):
    s = params.get("start_s", 0)
    e = params.get("end_s", 1)
    return [
        f"# ── Window / Slice ──",
        f"_trace = {inputs.get('trace', '{}')}",
        f"_t = _trace.get('time_s', [])",
        f"_d = _trace.get('current_a', [])",
        f"_mask = [(i, tv, dv) for i, (tv, dv) in enumerate(zip(_t, _d)) if {_py(s)} <= tv <= {_py(e)}]",
        f"{outs['sliced']} = {{**_trace, 'time_s': [m[1] for m in _mask], 'current_a': [m[2] for m in _mask], 'n_samples': len(_mask)}}",
        f'print(f"[window_slice] {{len(_mask)}} samples in [{s}, {e}]s")',
    ], set()


def _gen_resample(bid, params, inputs, outs):
    target = params.get("target_rate_hz", 1000)
    method = params.get("method", "linear")
    return [
        f"# ── Resample ──",
        f"_trace = {inputs.get('trace', '{}')}",
        f"_t = np.array(_trace.get('time_s', []), dtype=float)",
        f"_d = np.array(_trace.get('current_a', []), dtype=float)",
        f"if len(_t) > 1:",
        f"    _t_new = np.arange(_t[0], _t[-1], 1.0 / {_py(target)})",
        f"    _d_new = np.interp(_t_new, _t, _d).tolist()",
        f"    {outs['resampled']} = {{**_trace, 'time_s': _t_new.tolist(), 'current_a': _d_new, 'sample_rate_hz': {_py(target)}, 'n_samples': len(_d_new)}}",
        f"else:",
        f"    {outs['resampled']} = _trace",
        f'print(f"[resample] → {target} Hz")',
    ], {"numpy"}


def _gen_edge_detect(bid, params, inputs, outs):
    thr = params.get("threshold", 0.001)
    direction = params.get("direction", "both")
    min_w = params.get("min_width_s", 0)
    return [
        f"# ── Edge Detect ──",
        f"_trace = {inputs.get('trace', '{}')}",
        f"_data = np.array(_trace.get('current_a', []), dtype=float)",
        f"_t = np.array(_trace.get('time_s', list(range(len(_data)))), dtype=float)",
        f"_diff = np.diff(_data)",
        f"_edges = []",
        f"for _i, _dv in enumerate(_diff):",
        f"    if {_py(direction)} in ('rising', 'both') and _dv > {_py(thr)}:",
        f"        _edges.append({{'index': _i, 'time_s': float(_t[_i]), 'direction': 'rising', 'magnitude': float(_dv)}})",
        f"    elif {_py(direction)} in ('falling', 'both') and _dv < -{_py(thr)}:",
        f"        _edges.append({{'index': _i, 'time_s': float(_t[_i]), 'direction': 'falling', 'magnitude': float(_dv)}})",
        f"{outs['edges']} = {{'edges': _edges, 'count': len(_edges)}}",
        f'print(f"[edge_detect] {{len(_edges)}} edges found")',
    ], {"numpy"}


def _gen_histogram(bid, params, inputs, outs):
    bins = params.get("bins", 50)
    density = params.get("density", False)
    return [
        f"# ── Histogram ──",
        f"_data = np.array({inputs.get('trace', '{}')}.get('current_a', []), dtype=float)",
        f"if len(_data) > 0:",
        f"    _counts, _bin_edges = np.histogram(_data, bins={_py(bins)}, density={_py(density)})",
        f"    {outs['hist']} = {{'counts': _counts.tolist(), 'bin_edges': _bin_edges.tolist()}}",
        f"else:",
        f"    {outs['hist']} = {{'counts': [], 'bin_edges': []}}",
        f'print(f"[histogram] {bins} bins")',
    ], {"numpy"}


def _gen_correlate(bid, params, inputs, outs):
    norm = params.get("normalize", True)
    return [
        f"# ── Cross-Correlate ──",
        f"_a = np.array({inputs.get('trace_a', '{}')}.get('current_a', []), dtype=float)",
        f"_b = np.array({inputs.get('trace_b', '{}')}.get('current_a', []), dtype=float)",
        f"if len(_a) > 0 and len(_b) > 0:",
        f"    _corr = np.correlate(_a - np.mean(_a), _b - np.mean(_b), mode='full')",
        f"    if {_py(norm)}:",
        f"        _corr = _corr / (np.std(_a) * np.std(_b) * len(_a))",
        f"    {outs['result']} = {{'correlation': _corr.tolist(), 'max_corr': float(np.max(_corr)), 'lag': int(np.argmax(_corr) - len(_a) + 1)}}",
        f"else:",
        f"    {outs['result']} = {{'correlation': [], 'max_corr': 0, 'lag': 0}}",
        f'print(f"[correlate] done")',
    ], {"numpy"}


# ── Vision ───────────────────────────────────────────────────────────

def _gen_thermal_analyze(bid, params, inputs, outs):
    cmap = params.get("colormap", "inferno")
    zones_raw = params.get("zones", "[]")
    return [
        f"# ── Thermal Analyzer ──",
        f"import cv2 as _cv2",
        f"import matplotlib.cm as _cm",
        f"_thermal = {inputs.get('thermal', '{}')}",
        f"_tdata = _thermal.get('data', _thermal) if isinstance(_thermal, dict) else _thermal",
        f"if hasattr(_tdata, 'shape'):",
        f"    _tarr = np.array(_tdata, dtype=float)",
        f"    _snap = {{'mean_c': round(float(np.mean(_tarr)), 2), 'max_c': round(float(np.max(_tarr)), 2), 'min_c': round(float(np.min(_tarr)), 2), 'std_c': round(float(np.std(_tarr)), 2)}}",
        f"    # Zone analysis",
        f"    _zones = {_py(zones_raw)}",
        f"    if isinstance(_zones, str):",
        f"        import json as _j; _zones = _j.loads(_zones) if _zones.strip() else []",
        f"    for _zi, _z in enumerate(_zones):",
        f"        _zx, _zy, _zw, _zh = _z.get('x',0), _z.get('y',0), _z.get('w',50), _z.get('h',50)",
        f"        _zroi = _tarr[_zy:_zy+_zh, _zx:_zx+_zw]",
        f"        if _zroi.size > 0:",
        f"            _snap[f'zone_{{_zi}}_mean_c'] = round(float(np.mean(_zroi)), 2)",
        f"            _snap[f'zone_{{_zi}}_max_c'] = round(float(np.max(_zroi)), 2)",
        f"    # Generate heatmap image",
        f"    _norm = (_tarr - np.min(_tarr)) / (np.ptp(_tarr) + 1e-9)",
        f"    _cmap_fn = getattr(_cm, {_py(cmap)}, _cm.inferno)",
        f"    _hmap = (_cmap_fn(_norm)[:, :, :3] * 255).astype(np.uint8)",
        f"    {outs['snapshot']} = _snap",
        f"    {outs['heatmap']} = {{'shape': list(_hmap.shape), 'data': _hmap}}",
        f"    print(f\"[thermal_analyze] mean={{_snap['mean_c']}}C max={{_snap['max_c']}}C\")",
        f"else:",
        f"    {outs['snapshot']} = _thermal",
        f"    {outs['heatmap']} = {{'colormap': {_py(cmap)}, 'data': _thermal}}",
        f"    print('[thermal_analyze] passthrough (no ndarray)')",
    ], {"numpy"}


def _gen_aoi_inspect(bid, params, inputs, outs):
    tol = params.get("tolerance", 30)
    ref = params.get("reference", "")
    return [
        f"# ── AOI Inspector ──",
        f"import cv2 as _cv2",
        f"_frame_in = {inputs.get('frame', '{}')}",
        f"_img = _frame_in.get('data', _frame_in) if isinstance(_frame_in, dict) else _frame_in",
        f"if hasattr(_img, 'shape'):",
        f"    _gray = _cv2.cvtColor(_img, _cv2.COLOR_BGR2GRAY) if len(_img.shape) == 3 else _img",
        f"    _ref_path = {_py(ref)}",
        f"    _defects = 0",
        f"    _annotated = _img.copy()",
        f"    if _ref_path:",
        f"        _ref_img = _cv2.imread(_ref_path, _cv2.IMREAD_GRAYSCALE)",
        f"        if _ref_img is not None:",
        f"            _ref_img = _cv2.resize(_ref_img, (_gray.shape[1], _gray.shape[0]))",
        f"            _diff = _cv2.absdiff(_gray, _ref_img)",
        f"            _, _thresh = _cv2.threshold(_diff, {_py(tol)}, 255, _cv2.THRESH_BINARY)",
        f"            _contours, _ = _cv2.findContours(_thresh, _cv2.RETR_EXTERNAL, _cv2.CHAIN_APPROX_SIMPLE)",
        f"            _defects = len(_contours)",
        f"            _cv2.drawContours(_annotated, _contours, -1, (0, 0, 255), 2)",
        f"    else:",
        f"        # No reference: edge-based anomaly detection",
        f"        _edges = _cv2.Canny(_gray, 50, 150)",
        f"        _contours, _ = _cv2.findContours(_edges, _cv2.RETR_EXTERNAL, _cv2.CHAIN_APPROX_SIMPLE)",
        f"        _defects = len([c for c in _contours if _cv2.contourArea(c) > 50])",
        f"        _cv2.drawContours(_annotated, _contours, -1, (0, 255, 0), 1)",
        f"    _status = 'PASS' if _defects == 0 else 'FAIL'",
        f"    {outs['result']} = {{'tolerance': {_py(tol)}, 'defects': _defects, 'status': _status}}",
        f"    {outs['annotated']} = {{'shape': list(_annotated.shape), 'data': _annotated}}",
        f"    print(f'[aoi_inspect] {{_defects}} defects — {{_status}}')",
        f"else:",
        f"    {outs['result']} = {{'tolerance': {_py(tol)}, 'defects': 0, 'status': 'SKIP', 'reason': 'no image data'}}",
        f"    {outs['annotated']} = _frame_in",
        f"    print('[aoi_inspect] no image data — skipped')",
    ], set()


def _gen_color_detect(bid, params, inputs, outs):
    cs = params.get("color_space", "hsv")
    low_h = params.get("low_h", 0)
    high_h = params.get("high_h", 180)
    low_s = params.get("low_s", 50)
    high_s = params.get("high_s", 255)
    low_v = params.get("low_v", 50)
    high_v = params.get("high_v", 255)
    return [
        f"# ── Color Detect ──",
        f"import cv2 as _cv2",
        f"_frame_in = {inputs.get('frame', '{}')}",
        f"_img = _frame_in.get('data', _frame_in) if isinstance(_frame_in, dict) else _frame_in",
        f"if hasattr(_img, 'shape') and len(_img.shape) >= 2:",
        f"    if {_py(cs)} == 'hsv':",
        f"        _conv = _cv2.cvtColor(_img, _cv2.COLOR_BGR2HSV) if len(_img.shape) == 3 else _img",
        f"        _lower = np.array([{_py(low_h)}, {_py(low_s)}, {_py(low_v)}])",
        f"        _upper = np.array([{_py(high_h)}, {_py(high_s)}, {_py(high_v)}])",
        f"    elif {_py(cs)} == 'lab':",
        f"        _conv = _cv2.cvtColor(_img, _cv2.COLOR_BGR2LAB) if len(_img.shape) == 3 else _img",
        f"        _lower = np.array([{_py(low_h)}, {_py(low_s)}, {_py(low_v)}])",
        f"        _upper = np.array([{_py(high_h)}, {_py(high_s)}, {_py(high_v)}])",
        f"    else:",
        f"        _conv = _img",
        f"        _lower = np.array([{_py(low_h)}, {_py(low_s)}, {_py(low_v)}])",
        f"        _upper = np.array([{_py(high_h)}, {_py(high_s)}, {_py(high_v)}])",
        f"    _mask_arr = _cv2.inRange(_conv, _lower, _upper)",
        f"    _px_matched = int(np.count_nonzero(_mask_arr))",
        f"    _total_px = _mask_arr.shape[0] * _mask_arr.shape[1]",
        f"    _pct = round(_px_matched / _total_px * 100, 2) if _total_px > 0 else 0",
        f"    {outs['result']} = {{'color_space': {_py(cs)}, 'pixels_matched': _px_matched, 'total_pixels': _total_px, 'match_pct': _pct}}",
        f"    {outs['mask']} = {{'shape': list(_mask_arr.shape), 'data': _mask_arr}}",
        f"    print(f'[color_detect] {{_px_matched}} pixels matched ({{_pct}}%)')",
        f"else:",
        f"    {outs['result']} = {{'color_space': {_py(cs)}, 'pixels_matched': 0, 'reason': 'no image'}}",
        f"    {outs['mask']} = _frame_in",
        f"    print('[color_detect] no image data')",
    ], {"numpy"}


def _gen_blob_detect(bid, params, inputs, outs):
    min_area = params.get("min_area", 100)
    max_area = params.get("max_area", 10000)
    circ = params.get("circularity", 0.5)
    return [
        f"# ── Blob Detect ──",
        f"import cv2 as _cv2",
        f"_frame_in = {inputs.get('frame', '{}')}",
        f"_img = _frame_in.get('data', _frame_in) if isinstance(_frame_in, dict) else _frame_in",
        f"if hasattr(_img, 'shape'):",
        f"    _gray = _cv2.cvtColor(_img, _cv2.COLOR_BGR2GRAY) if len(_img.shape) == 3 else _img",
        f"    _, _bin = _cv2.threshold(_gray, 0, 255, _cv2.THRESH_BINARY + _cv2.THRESH_OTSU)",
        f"    _contours, _ = _cv2.findContours(_bin, _cv2.RETR_EXTERNAL, _cv2.CHAIN_APPROX_SIMPLE)",
        f"    _blobs_list = []",
        f"    _annotated_img = _img.copy() if len(_img.shape) == 3 else _cv2.cvtColor(_img, _cv2.COLOR_GRAY2BGR)",
        f"    for _c in _contours:",
        f"        _area = _cv2.contourArea(_c)",
        f"        if _area < {_py(min_area)} or _area > {_py(max_area)}:",
        f"            continue",
        f"        _perim = _cv2.arcLength(_c, True)",
        f"        _cir = 4 * 3.14159 * _area / (_perim * _perim + 1e-9) if _perim > 0 else 0",
        f"        if _cir < {_py(circ)}:",
        f"            continue",
        f"        _M = _cv2.moments(_c)",
        f"        _cx = int(_M['m10'] / (_M['m00'] + 1e-9))",
        f"        _cy = int(_M['m01'] / (_M['m00'] + 1e-9))",
        f"        _blobs_list.append({{'area': round(_area, 1), 'centroid': [_cx, _cy], 'circularity': round(_cir, 3)}})",
        f"        _cv2.drawContours(_annotated_img, [_c], -1, (0, 255, 0), 2)",
        f"        _cv2.circle(_annotated_img, (_cx, _cy), 4, (0, 0, 255), -1)",
        f"    {outs['blobs']} = {{'count': len(_blobs_list), 'blobs': _blobs_list}}",
        f"    {outs['annotated']} = {{'shape': list(_annotated_img.shape), 'data': _annotated_img}}",
        f"    print(f'[blob_detect] {{len(_blobs_list)}} blobs found')",
        f"else:",
        f"    {outs['blobs']} = {{'count': 0, 'blobs': []}}",
        f"    {outs['annotated']} = _frame_in",
        f"    print('[blob_detect] no image data')",
    ], set()


def _gen_template_match(bid, params, inputs, outs):
    method = params.get("method", "ccoeff_normed")
    thr = params.get("threshold", 0.8)
    method_map = {
        "ccoeff_normed": "cv2.TM_CCOEFF_NORMED",
        "ccorr_normed": "cv2.TM_CCORR_NORMED",
        "sqdiff_normed": "cv2.TM_SQDIFF_NORMED",
    }
    cv_method = method_map.get(method, "cv2.TM_CCOEFF_NORMED")
    return [
        f"# ── Template Match ──",
        f"import cv2 as _cv2",
        f"_frame_in = {inputs.get('frame', '{}')}",
        f"_tmpl_in = {inputs.get('template', '{}')}",
        f"_img = _frame_in.get('data', _frame_in) if isinstance(_frame_in, dict) else _frame_in",
        f"_tmpl = _tmpl_in.get('data', _tmpl_in) if isinstance(_tmpl_in, dict) else _tmpl_in",
        f"if hasattr(_img, 'shape') and hasattr(_tmpl, 'shape'):",
        f"    _gray_i = _cv2.cvtColor(_img, _cv2.COLOR_BGR2GRAY) if len(_img.shape) == 3 else _img",
        f"    _gray_t = _cv2.cvtColor(_tmpl, _cv2.COLOR_BGR2GRAY) if len(_tmpl.shape) == 3 else _tmpl",
        f"    _res = _cv2.matchTemplate(_gray_i, _gray_t, {cv_method})",
        f"    _th, _tw = _gray_t.shape[:2]",
        f"    _locs = []",
        f"    _annotated_img = _img.copy() if len(_img.shape) == 3 else _cv2.cvtColor(_img, _cv2.COLOR_GRAY2BGR)",
        f"    if 'SQDIFF' in {_py(cv_method)}:",
        f"        _match_pts = np.where(_res <= (1 - {_py(thr)}))",
        f"    else:",
        f"        _match_pts = np.where(_res >= {_py(thr)})",
        f"    for _pt in zip(*_match_pts[::-1]):",
        f"        _locs.append({{'x': int(_pt[0]), 'y': int(_pt[1]), 'score': round(float(_res[_pt[1], _pt[0]]), 4)}})",
        f"        _cv2.rectangle(_annotated_img, _pt, (_pt[0]+_tw, _pt[1]+_th), (0, 255, 0), 2)",
        f"    {outs['matches']} = {{'count': len(_locs), 'threshold': {_py(thr)}, 'locations': _locs[:100]}}",
        f"    {outs['annotated']} = {{'shape': list(_annotated_img.shape), 'data': _annotated_img}}",
        f"    print(f'[template_match] {{len(_locs)}} matches (>={thr})')",
        f"else:",
        f"    {outs['matches']} = {{'count': 0, 'threshold': {_py(thr)}, 'reason': 'missing image or template'}}",
        f"    {outs['annotated']} = _frame_in",
        f"    print('[template_match] missing image or template')",
    ], {"numpy"}


def _gen_image_resize(bid, params, inputs, outs):
    w = params.get("width", 320)
    h = params.get("height", 240)
    interp = params.get("interpolation", "linear")
    interp_map = {
        "nearest": "cv2.INTER_NEAREST",
        "linear": "cv2.INTER_LINEAR",
        "cubic": "cv2.INTER_CUBIC",
        "area": "cv2.INTER_AREA",
        "lanczos": "cv2.INTER_LANCZOS4",
    }
    cv_interp = interp_map.get(interp, "cv2.INTER_LINEAR")
    return [
        f"# ── Resize Image ──",
        f"import cv2 as _cv2",
        f"_frame_in = {inputs.get('frame', '{}')}",
        f"_img = _frame_in.get('data', _frame_in) if isinstance(_frame_in, dict) else _frame_in",
        f"if hasattr(_img, 'shape'):",
        f"    _resized_img = _cv2.resize(_img, ({_py(w)}, {_py(h)}), interpolation={cv_interp})",
        f"    {outs['resized']} = {{'shape': list(_resized_img.shape), 'data': _resized_img}}",
        f"    print(f'[image_resize] {{_img.shape}} → {{_resized_img.shape}}')",
        f"else:",
        f"    {outs['resized']} = {{**(_frame_in if isinstance(_frame_in, dict) else {{}}), 'target_size': ({_py(w)}, {_py(h)})}}",
        f"    print(f'[image_resize] passthrough (no ndarray)')",
    ], set()


def _gen_image_crop(bid, params, inputs, outs):
    x = params.get("x", 0)
    y = params.get("y", 0)
    w = params.get("w", 320)
    h = params.get("h", 240)
    return [
        f"# ── Crop Image ──",
        f"_frame_in = {inputs.get('frame', '{}')}",
        f"_img = _frame_in.get('data', _frame_in) if isinstance(_frame_in, dict) else _frame_in",
        f"if hasattr(_img, 'shape'):",
        f"    _cropped_img = _img[{_py(y)}:{_py(y)}+{_py(h)}, {_py(x)}:{_py(x)}+{_py(w)}]",
        f"    {outs['cropped']} = {{'shape': list(_cropped_img.shape), 'data': _cropped_img, 'roi': ({_py(x)}, {_py(y)}, {_py(w)}, {_py(h)})}}",
        f"    print(f'[image_crop] ROI ({x},{y}) {w}x{h} → {{_cropped_img.shape}}')",
        f"else:",
        f"    {outs['cropped']} = {{**(_frame_in if isinstance(_frame_in, dict) else {{}}), 'roi': ({_py(x)}, {_py(y)}, {_py(w)}, {_py(h)})}}",
        f"    print(f'[image_crop] passthrough (no ndarray)')",
    ], set()


def _gen_image_threshold(bid, params, inputs, outs):
    method = params.get("method", "otsu")
    thr = params.get("threshold", 127)
    invert = params.get("invert", False)
    return [
        f"# ── Image Threshold ──",
        f"import cv2 as _cv2",
        f"_frame_in = {inputs.get('frame', '{}')}",
        f"_img = _frame_in.get('data', _frame_in) if isinstance(_frame_in, dict) else _frame_in",
        f"if hasattr(_img, 'shape'):",
        f"    _gray = _cv2.cvtColor(_img, _cv2.COLOR_BGR2GRAY) if len(_img.shape) == 3 else _img",
        f"    _thr_type = _cv2.THRESH_BINARY_INV if {_py(invert)} else _cv2.THRESH_BINARY",
        f"    if {_py(method)} == 'otsu':",
        f"        _tv, _bin = _cv2.threshold(_gray, 0, 255, _thr_type + _cv2.THRESH_OTSU)",
        f"    elif {_py(method)} == 'adaptive':",
        f"        _bin = _cv2.adaptiveThreshold(_gray, 255, _cv2.ADAPTIVE_THRESH_GAUSSIAN_C, _thr_type, 11, 2)",
        f"        _tv = -1",
        f"    elif {_py(method)} == 'triangle':",
        f"        _tv, _bin = _cv2.threshold(_gray, 0, 255, _thr_type + _cv2.THRESH_TRIANGLE)",
        f"    else:",
        f"        _tv, _bin = _cv2.threshold(_gray, {_py(thr)}, 255, _thr_type)",
        f"    _white = int(np.count_nonzero(_bin))",
        f"    _total = _bin.shape[0] * _bin.shape[1]",
        f"    {outs['binary']} = {{'shape': list(_bin.shape), 'data': _bin}}",
        f"    {outs['stats']} = {{'method': {_py(method)}, 'threshold_used': float(_tv), 'white_pixels': _white, 'total_pixels': _total, 'white_pct': round(_white / _total * 100, 2) if _total else 0}}",
        f"    print(f'[image_threshold] {{_white}}/{{_total}} white pixels ({{round(_white/_total*100,1) if _total else 0}}%)')",
        f"else:",
        f"    {outs['binary']} = _frame_in",
        f"    {outs['stats']} = {{'method': {_py(method)}, 'threshold': {_py(thr)}, 'reason': 'no image'}}",
        f"    print('[image_threshold] no image data')",
    ], {"numpy"}


# ── Math ─────────────────────────────────────────────────────────────

def _gen_expression(bid, params, inputs, outs):
    expr = params.get("expr", "a + b")
    return [
        f"# ── Expression: {expr} ──",
        f"_a = {inputs.get('a', 'None')}",
        f"_b = {inputs.get('b', 'None')}",
        f"try:",
        f"    {outs['result']} = eval({_py(expr)}, {{'__builtins__': {{'abs': abs, 'round': round, 'min': min, 'max': max, 'sum': sum, 'len': len, 'int': int, 'float': float, 'str': str, 'bool': bool, 'list': list, 'dict': dict, 'True': True, 'False': False, 'None': None}}}}, {{'a': _a, 'b': _b}})",
        f"except Exception as _e:",
        f"    {outs['result']} = {{'error': str(_e)}}",
        f'print(f"[expression] {expr} → {{{outs["result"]}}}")',
    ], set()


def _gen_constant(bid, params, inputs, outs):
    val = params.get("value", "0")
    dtype = params.get("dtype", "float")
    return [
        f"# ── Constant ──",
        f"if {_py(dtype)} == 'float':",
        f"    {outs['value']} = float({_py(val)})",
        f"elif {_py(dtype)} == 'int':",
        f"    {outs['value']} = int(float({_py(val)}))",
        f"elif {_py(dtype)} == 'bool':",
        f"    {outs['value']} = {_py(val)}.lower() in ('true', '1', 'yes')" if isinstance(val, str) else f"    {outs['value']} = bool({_py(val)})",
        f"elif {_py(dtype)} in ('list', 'dict'):",
        f"    import json as _json",
        f"    {outs['value']} = _json.loads({_py(val)})",
        f"else:",
        f"    {outs['value']} = {_py(val)}",
        f'print(f"[constant] {val} ({dtype})")',
    ], set()


def _gen_multiply(bid, params, inputs, outs):
    return [
        f"_a = float({inputs.get('a', '0')})",
        f"_b = float({inputs.get('b', '0')})",
        f"{outs['result']} = _a * _b",
        f"print(f'[multiply] {{_a}} × {{_b}} = {{{outs['result']}}}')",
    ], set()


def _gen_add(bid, params, inputs, outs):
    return [
        f"_a = float({inputs.get('a', '0')})",
        f"_b = float({inputs.get('b', '0')})",
        f"{outs['result']} = _a + _b",
        f"print(f'[add] {{_a}} + {{_b}} = {{{outs['result']}}}')",
    ], set()


def _gen_subtract(bid, params, inputs, outs):
    return [
        f"_a = float({inputs.get('a', '0')})",
        f"_b = float({inputs.get('b', '0')})",
        f"{outs['result']} = _a - _b",
        f"print(f'[subtract] {{_a}} − {{_b}} = {{{outs['result']}}}')",
    ], set()


def _gen_divide(bid, params, inputs, outs):
    return [
        f"_a = float({inputs.get('a', '0')})",
        f"_b = float({inputs.get('b', '1')})",
        f"{outs['result']} = _a / _b if _b != 0 else float('inf')",
        f"print(f'[divide] {{_a}} ÷ {{_b}} = {{{outs['result']}}}')",
    ], set()


def _gen_abs_val(bid, params, inputs, outs):
    return [
        f"{outs['result']} = abs(float({inputs.get('value', '0')}))  # Absolute value",
    ], set()


def _gen_power(bid, params, inputs, outs):
    exp = params.get("default_exp", 2)
    return [
        f"_base = float({inputs.get('base', '0')})",
        f"_exp = float({inputs.get('exp', _py(exp))})",
        f"{outs['result']} = _base ** _exp  # Power",
    ], set()


def _gen_log_math(bid, params, inputs, outs):
    base = params.get("base", "e")
    return [
        f"# ── Logarithm ──",
        f"_v = float({inputs.get('value', '1')})",
        f"if _v > 0:",
        f"    if {_py(base)} == 'e':",
        f"        {outs['result']} = math.log(_v)",
        f"    elif {_py(base)} == '10':",
        f"        {outs['result']} = math.log10(_v)",
        f"    else:",
        f"        {outs['result']} = math.log2(_v)",
        f"else:",
        f"    {outs['result']} = float('nan')",
    ], {"math"}


def _gen_trig(bid, params, inputs, outs):
    func = params.get("func", "sin")
    unit = params.get("unit", "radians")
    return [
        f"# ── Trigonometry ──",
        f"_angle = float({inputs.get('angle', '0')})",
        f"if {_py(unit)} == 'degrees':",
        f"    _angle = math.radians(_angle)",
        f"{outs['result']} = getattr(math, {_py(func)})(_angle)",
    ], {"math"}


def _gen_clamp(bid, params, inputs, outs):
    mn = params.get("min_val", 0)
    mx = params.get("max_val", 1)
    return [
        f"{outs['result']} = max({_py(mn)}, min({_py(mx)}, float({inputs.get('value', '0')})))  # Clamp",
    ], set()


def _gen_map_range(bid, params, inputs, outs):
    imn = params.get("in_min", 0)
    imx = params.get("in_max", 1023)
    omn = params.get("out_min", 0)
    omx = params.get("out_max", 3.3)
    return [
        f"# ── Map Range ──",
        f"_v = float({inputs.get('value', '0')})",
        f"_span_in = {_py(imx)} - {_py(imn)}",
        f"_span_out = {_py(omx)} - {_py(omn)}",
        f"{outs['result']} = {_py(omn)} + (_v - {_py(imn)}) * _span_out / _span_in if _span_in != 0 else {_py(omn)}",
    ], set()


def _gen_compare(bid, params, inputs, outs):
    op = params.get("op", ">")
    return [
        f"# ── Compare ──",
        f"_a = {inputs.get('a', '0')}",
        f"_b = {inputs.get('b', '0')}",
        f"try:",
        f"    _a, _b = float(_a), float(_b)",
        f"except (TypeError, ValueError):",
        f"    pass",
        f"{outs['result']} = _a {op} _b",
    ], set()


def _gen_unit_convert(bid, params, inputs, outs):
    conv = params.get("conversion", "A_to_uA")
    factors = {
        "A_to_uA": 1e6, "A_to_mA": 1e3, "uA_to_A": 1e-6, "mA_to_A": 1e-3,
        "V_to_mV": 1e3, "mV_to_V": 1e-3, "W_to_mW": 1e3, "mW_to_W": 1e-3,
        "Hz_to_kHz": 1e-3, "kHz_to_MHz": 1e-3,
    }
    if conv in factors:
        return [
            f"{outs['result']} = float({inputs.get('value', '0')}) * {factors[conv]}  # {conv}",
        ], set()
    elif conv in ("C_to_F", "F_to_C", "K_to_C", "C_to_K", "rad_to_deg", "deg_to_rad", "dBm_to_mW", "mW_to_dBm"):
        return [
            f"# ── Unit Convert: {conv} ──",
            f"_v = float({inputs.get('value', '0')})",
            f"_conversions = {{",
            f"    'C_to_F': lambda x: x * 9/5 + 32,",
            f"    'F_to_C': lambda x: (x - 32) * 5/9,",
            f"    'K_to_C': lambda x: x - 273.15,",
            f"    'C_to_K': lambda x: x + 273.15,",
            f"    'rad_to_deg': lambda x: math.degrees(x),",
            f"    'deg_to_rad': lambda x: math.radians(x),",
            f"    'dBm_to_mW': lambda x: 10 ** (x / 10),",
            f"    'mW_to_dBm': lambda x: 10 * math.log10(x) if x > 0 else float('-inf'),",
            f"}}",
            f"{outs['result']} = _conversions[{_py(conv)}](_v)",
        ], {"math"}
    return [f"{outs['result']} = float({inputs.get('value', '0')})  # Unknown conversion: {conv}"], set()


# ── Data ─────────────────────────────────────────────────────────────

def _gen_dict_get(bid, params, inputs, outs):
    key = params.get("key", "avg_current_a")
    dv = params.get("default_val", "null")
    return [
        f"{outs['value']} = {inputs.get('data', '{}')}.get({_py(key)}, {_py(dv)})  # Dict Get",
    ], set()


def _gen_dict_set(bid, params, inputs, outs):
    key = params.get("key", "my_field")
    return [
        f"_d = dict({inputs.get('data', '{}')}) if isinstance({inputs.get('data', '{}')}, dict) else {{}}",
        f"_d[{_py(key)}] = {inputs.get('value', 'None')}",
        f"{outs['result']} = _d  # Dict Set",
    ], set()


def _gen_dict_build(bid, params, inputs, outs):
    ka = params.get("key_a", "left")
    kb = params.get("key_b", "right")
    return [
        f"{outs['result']} = {{{_py(ka)}: {inputs.get('a', 'None')}, {_py(kb)}: {inputs.get('b', 'None')}}}  # Build Dict",
    ], set()


def _gen_list_build(bid, params, inputs, outs):
    return [
        f"{outs['result']} = [{inputs.get('a', 'None')}, {inputs.get('b', 'None')}]  # Build List",
    ], set()


def _gen_json_parse(bid, params, inputs, outs):
    _default_text = '"{}"'
    _src = inputs.get('text', _default_text)
    return [
        f"{outs['data']} = json.loads({_src})  # JSON Parse",
    ], {"json"}


def _gen_format_string(bid, params, inputs, outs):
    tpl = params.get("template", "Value: {a}, Result: {b}")
    return [
        f"{outs['text']} = {_py(tpl)}.format(a={inputs.get('a', 'None')}, b={inputs.get('b', 'None')})  # Format String",
    ], set()


def _gen_type_cast(bid, params, inputs, outs):
    to = params.get("to_type", "float")
    return [
        f"# ── Type Cast → {to} ──",
        f"_v = {inputs.get('value', 'None')}",
        f"if {_py(to)} == 'float': {outs['result']} = float(_v)",
        f"elif {_py(to)} == 'int': {outs['result']} = int(float(_v))",
        f"elif {_py(to)} == 'str': {outs['result']} = str(_v)",
        f"elif {_py(to)} == 'bool': {outs['result']} = bool(_v)",
        f"elif {_py(to)} == 'json_str': {outs['result']} = json.dumps(_v)",
        f"else: {outs['result']} = _v",
    ], {"json"}


def _gen_pick_field(bid, params, inputs, outs):
    fields = params.get("fields", "avg_current_a,max_current_a")
    return [
        f"_d = {inputs.get('data', '{}')}",
        f"_keys = [k.strip() for k in {_py(fields)}.split(',')]",
        f"{outs['result']} = {{k: _d.get(k) for k in _keys if k in _d}}  # Pick Fields",
    ], set()


# ── I/O ──────────────────────────────────────────────────────────────

def _gen_display(bid, params, inputs, outs):
    fmt = params.get("format", "auto")
    # Accept both 'data' and 'value' input ports for compatibility
    inp = inputs.get('data', inputs.get('value', 'None'))
    return [
        f"# ── Display ──",
        f"_val = {inp}",
        f"if isinstance(_val, dict) or isinstance(_val, list):",
        f"    print(json.dumps(_val, indent=2, default=str))",
        f"else:",
        f"    print(_val)",
    ], {"json"}


def _gen_plot_trace(bid, params, inputs, outs):
    title = params.get("title", "Power Trace")
    y_label = params.get("y_label", "Current (A)")
    style = params.get("style", "lines")
    return [
        f"# ── Plot Trace: {title} ──",
        f"_trace = {inputs.get('trace', '{}')}",
        f"try:",
        f"    import matplotlib.pyplot as plt",
        f"    _t = _trace.get('time_s', list(range(len(_trace.get('current_a', [])))))",
        f"    _y = _trace.get('current_a', [])",
        f"    plt.figure(figsize=(10, 4))",
        "    plt.plot(_t, _y" + (", marker='o', markersize=2)" if style in ('markers', 'lines+markers') else ")"),
        f"    plt.title({_py(title)})",
        f"    plt.xlabel('Time (s)')",
        f"    plt.ylabel({_py(y_label)})",
        f"    plt.grid(True, alpha=0.3)",
        f"    plt.tight_layout()",
        f"    plt.savefig({_py(title.replace(' ', '_').lower() + '.png')}, dpi=150)",
        f"    plt.show()",
        f"    print(f'[plot_trace] {title} — {{len(_y)}} points')",
        f"except ImportError:",
        f"    print(f'[plot_trace] matplotlib not available — skipping plot')",
    ], set()


def _gen_plot_xy(bid, params, inputs, outs):
    title = params.get("title", "XY Plot")
    x_label = params.get("x_label", "X")
    y_label = params.get("y_label", "Y")
    mode = params.get("mode", "markers")
    return [
        f"# ── Plot XY: {title} ──",
        f"try:",
        f"    import matplotlib.pyplot as plt",
        f"    _x = {inputs.get('x', '[]')}",
        f"    _y = {inputs.get('y', '[]')}",
        f"    plt.figure(figsize=(8, 6))",
        "    plt." + ('scatter' if mode == 'markers' else 'plot') + "(_x, _y" + (", marker='o')" if mode == 'lines+markers' else ")"),
        f"    plt.title({_py(title)}); plt.xlabel({_py(x_label)}); plt.ylabel({_py(y_label)})",
        f"    plt.grid(True, alpha=0.3); plt.tight_layout()",
        f"    plt.savefig({_py(title.replace(' ', '_').lower() + '.png')}, dpi=150)",
        f"    plt.show()",
        f"except ImportError:",
        f"    print('[plot_xy] matplotlib not available')",
    ], set()


def _gen_plot_histogram(bid, params, inputs, outs):
    title = params.get("title", "Histogram")
    bins = params.get("bins", 50)
    color = params.get("color", "#89b4fa")
    return [
        f"# ── Plot Histogram: {title} ──",
        f"try:",
        f"    import matplotlib.pyplot as plt",
        f"    _data_in = {inputs.get('data', '[]')}",
        f"    _arr = _data_in.get('current_a', _data_in) if isinstance(_data_in, dict) else _data_in",
        f"    plt.figure(figsize=(8, 4))",
        f"    plt.hist(_arr, bins={_py(bins)}, color={_py(color)}, edgecolor='black', alpha=0.8)",
        f"    plt.title({_py(title)}); plt.grid(True, alpha=0.3); plt.tight_layout()",
        f"    plt.savefig({_py(title.replace(' ', '_').lower() + '.png')}, dpi=150)",
        f"    plt.show()",
        f"except ImportError:",
        f"    print('[plot_histogram] matplotlib not available')",
    ], set()


def _gen_plot_heatmap(bid, params, inputs, outs):
    title = params.get("title", "Heatmap")
    cs = params.get("colorscale", "Inferno")
    return [
        f"# ── Plot Heatmap: {title} ──",
        f"try:",
        f"    import matplotlib.pyplot as plt",
        f"    _data_in = {inputs.get('data', '[]')}",
        f"    plt.figure(figsize=(8, 6))",
        f"    plt.imshow(_data_in if not isinstance(_data_in, dict) else [[0]], cmap={_py(cs.lower())})",
        f"    plt.colorbar(); plt.title({_py(title)}); plt.tight_layout()",
        f"    plt.savefig({_py(title.replace(' ', '_').lower() + '.png')}, dpi=150)",
        f"    plt.show()",
        f"except ImportError:",
        f"    print('[plot_heatmap] matplotlib not available')",
    ], set()


def _gen_gauge_display(bid, params, inputs, outs):
    title = params.get("title", "Gauge")
    unit = params.get("unit", "")
    mn = params.get("min_val", 0)
    mx = params.get("max_val", 100)
    return [
        f"# ── Gauge: {title} ──",
        f"_v = {inputs.get('value', '0')}",
        f'print(f"[gauge] {title}: {{_v}} {unit} (range {mn}-{mx})")',
    ], set()


def _gen_table_display(bid, params, inputs, outs):
    max_rows = params.get("max_rows", 100)
    return [
        f"# ── Table Display ──",
        f"_data = {inputs.get('data', '{}')}",
        f"if isinstance(_data, dict):",
        f"    for _k, _v in list(_data.items())[:{_py(max_rows)}]:",
        f"        print(f'  {{_k:>20s}}: {{_v}}')",
        f"elif isinstance(_data, list):",
        f"    for _row in _data[:{_py(max_rows)}]:",
        f"        print(f'  {{_row}}')",
        f"else:",
        f"    print(_data)",
    ], set()


def _gen_save_file(bid, params, inputs, outs):
    path = params.get("path", "output.json")
    fmt = params.get("fmt", "json")
    return [
        f"# ── Save to File: {path} ──",
        f"_data = {inputs.get('data', '{}')}",
        f"os.makedirs(os.path.dirname({_py(path)}) or '.', exist_ok=True)",
        f"if {_py(fmt)} == 'json':",
        f"    with open({_py(path)}, 'w', encoding='utf-8') as _f:",
        f"        json.dump(_data, _f, indent=2, default=str)",
        f"elif {_py(fmt)} == 'csv':",
        f"    import csv as _csv",
        f"    with open({_py(path)}, 'w', newline='', encoding='utf-8') as _f:",
        f"        if isinstance(_data, dict):",
        f"            _w = _csv.writer(_f); _w.writerow(_data.keys())",
        f"            _rows = zip(*[v if isinstance(v, list) else [v] for v in _data.values()])",
        f"            _w.writerows(_rows)",
        f"else:",
        f"    with open({_py(path)}, 'w', encoding='utf-8') as _f:",
        f"        _f.write(str(_data))",
        f'print(f"[save_file] Saved to {path}")',
    ], {"json", "os"}


def _gen_log_message(bid, params, inputs, outs):
    prefix = params.get("prefix", "LOG")
    level = params.get("level", "info")
    return [
        f"# ── Log Message ──",
        f"_data = {inputs.get('data', 'None')}",
        f'print(f"[{prefix}] ({level}) {{_data}}")',
        f"{outs['data']} = _data  # pass-through",
    ], set()


def _gen_assert_check(bid, params, inputs, outs):
    msg = params.get("message", "Assertion failed!")
    action = params.get("fail_action", "log")
    return [
        f"# ── Assert ──",
        f"_cond = bool({inputs.get('condition', 'False')})",
        f"if not _cond:",
        f'    print(f"ASSERT FAIL: {msg}")',
        f"    if {_py(action)} == 'stop':",
        f"        raise RuntimeError({_py(msg)})",
        f"{outs['pass']} = _cond",
    ], set()


# ── Flow ─────────────────────────────────────────────────────────────

def _gen_delay(bid, params, inputs, outs):
    sec = params.get("seconds", 1)
    return [
        f"time.sleep({_py(sec)})  # Delay",
        f"{outs['trigger']} = {inputs.get('trigger', 'None')}",
    ], {"time"}


def _gen_repeat(bid, params, inputs, outs):
    count = params.get("count", 5)
    return [
        f"# ── Repeat ({count}x) ──",
        f"for _i in range({_py(count)}):",
        f"    {outs['output']} = {inputs.get('input', 'None')}",
        f"    {outs['index']} = _i",
        f'    print(f"[repeat] iteration {{_i + 1}}/{count}")',
    ], set()


def _gen_gate(bid, params, inputs, outs):
    return [
        f"# ── Gate (If) ──",
        f"_cond = {inputs.get('cond', 'False')}",
        f"_data = {inputs.get('data', 'None')}",
        f"if _cond:",
        f"    {outs['true_out']} = _data",
        f"    {outs['false_out']} = None",
        f"else:",
        f"    {outs['true_out']} = None",
        f"    {outs['false_out']} = _data",
    ], set()


def _gen_merge(bid, params, inputs, outs):
    strat = params.get("strategy", "dict_merge")
    return [
        f"# ── Merge ({strat}) ──",
        f"_a = {inputs.get('a', 'None')}",
        f"_b = {inputs.get('b', 'None')}",
        f"if {_py(strat)} == 'dict_merge' and isinstance(_a, dict) and isinstance(_b, dict):",
        f"    {outs['merged']} = {{**_a, **_b}}",
        f"elif {_py(strat)} == 'list_concat':",
        f"    {outs['merged']} = (list(_a) if isinstance(_a, list) else [_a]) + (list(_b) if isinstance(_b, list) else [_b])",
        f"else:",
        f"    {outs['merged']} = _a if _a is not None else _b",
    ], set()


def _gen_sequence(bid, params, inputs, outs):
    return [
        f"# ── Sequence (step_1 → step_2) ──",
        f"_ = {inputs.get('step_1', 'None')}  # ensure step_1 executed first",
        f"{outs['last']} = {inputs.get('step_2', 'None')}",
    ], set()


def _gen_null_check(bid, params, inputs, outs):
    dv = params.get("default_val", "0")
    return [
        f"# ── Null Check ──",
        f"_v = {inputs.get('value', 'None')}",
        f"{outs['is_null']} = _v is None",
        f"{outs['value']} = _v if _v is not None else {_py(dv)}",
    ], set()


def _gen_try_catch(bid, params, inputs, outs):
    return [
        f"# ── Try/Catch ──",
        f"try:",
        f"    {outs['data']} = {inputs.get('data', 'None')}",
        f"    {outs['error']} = ''",
        f"except Exception as _e:",
        f"    {outs['data']} = None",
        f"    {outs['error']} = str(_e)",
    ], set()


# ── Actions ──────────────────────────────────────────────────────────

def _gen_shell_cmd(bid, params, inputs, outs):
    cmd = params.get("command", "echo hello")
    timeout = params.get("timeout_s", 30)
    return [
        f"# ── Shell Command ──",
        f"try:",
        f"    _proc = subprocess.run({_py(cmd)}, shell=True, capture_output=True, text=True, timeout={_py(timeout)})",
        f"    {outs['stdout']} = _proc.stdout",
        f"    {outs['exit_code']} = _proc.returncode",
        f"    print(f'[shell] exit={{_proc.returncode}}: {{_proc.stdout[:200]}}')",
        f"except subprocess.TimeoutExpired:",
        f"    {outs['stdout']} = 'TIMEOUT'",
        f"    {outs['exit_code']} = -1",
        f"except Exception as _e:",
        f"    {outs['stdout']} = str(_e)",
        f"    {outs['exit_code']} = -1",
    ], {"subprocess"}


def _gen_http_request(bid, params, inputs, outs):
    url = params.get("url", "http://localhost:5200/api/health")
    method = params.get("method", "GET")
    headers = params.get("headers", "{}")
    return [
        f"# ── HTTP Request ──",
        f"import requests as _requests",
        f"try:",
        f"    _hdrs = json.loads({_py(headers)})",
        f"    _body = {inputs.get('body', 'None')}",
        f"    _resp = _requests.request({_py(method)}, {_py(url)}, headers=_hdrs{', json=_body' if method in ('POST', 'PUT') else ''})",
        f"    try:",
        f"        {outs['response']} = _resp.json()",
        f"    except ValueError:",
        f"        {outs['response']} = {{'text': _resp.text}}",
        f"    {outs['status']} = _resp.status_code",
        f"    print(f'[http] {method} {url} → {{_resp.status_code}}')",
        f"except Exception as _e:",
        f"    {outs['response']} = {{'error': str(_e)}}",
        f"    {outs['status']} = 0",
    ], {"json"}


def _gen_sleep_test(bid, params, inputs, outs):
    dur = params.get("duration_s", 5)
    settle = params.get("settle_s", 1)
    max_ua = params.get("max_avg_ua", 10)
    return [
        f"# ── Sleep Current Test ──",
        f'print(f"[sleep_test] Settle {settle}s then measure {dur}s...")',
        f"time.sleep({_py(settle)})",
        f"# Simulated measurement for standalone script",
        f"_n = int(1000 * {_py(dur)})",
        f"_t = np.linspace(0, {_py(dur)}, _n)",
        f"_curr = np.random.normal(5e-6, 1e-6, _n)  # ~5uA sleep current",
        f"{outs['trace']} = {{'time_s': _t.tolist(), 'current_a': _curr.tolist(), 'sample_rate_hz': 1000, 'n_samples': _n}}",
        f"_avg_ua = float(np.mean(_curr)) * 1e6",
        f"_pass = _avg_ua <= {_py(max_ua)}",
        f"{outs['verdict']} = {{'overall': ('PASS' if _pass else 'FAIL'), 'avg_current_ua': round(_avg_ua, 3), 'limit_ua': {_py(max_ua)}}}",
        f"print(f\"[sleep_test] avg={{_avg_ua:.3f}} uA \\u2014 {{'PASS' if _pass else 'FAIL'}}\")",
    ], {"numpy", "time"}


def _gen_tx_burst_test(bid, params, inputs, outs):
    dur = params.get("duration_s", 3)
    interval = params.get("interval_ms", 100)
    max_peak = params.get("max_peak_ma", 50)
    max_avg = params.get("max_avg_ma", 5)
    return [
        f"# ── TX Burst Test ──",
        f'print(f"[tx_burst_test] Measuring {dur}s...")',
        f"_n = int(10000 * {_py(dur)})",
        f"_t = np.linspace(0, {_py(dur)}, _n)",
        f"_curr = np.random.normal(0.002, 0.0005, _n)",
        f"# Inject bursts",
        f"_interval_samples = int(10000 * {_py(interval)} / 1000)",
        f"for _bi in range(0, _n, max(1, _interval_samples)):",
        f"    _curr[_bi:min(_bi+100, _n)] += 0.03  # ~30mA burst",
        f"{outs['trace']} = {{'time_s': _t.tolist(), 'current_a': _curr.tolist(), 'sample_rate_hz': 10000, 'n_samples': _n}}",
        f"_peak_ma = float(np.max(_curr)) * 1000",
        f"_avg_ma = float(np.mean(_curr)) * 1000",
        f"_pass = _peak_ma <= {_py(max_peak)} and _avg_ma <= {_py(max_avg)}",
        f"{outs['verdict']} = {{'overall': ('PASS' if _pass else 'FAIL'), 'peak_ma': round(_peak_ma, 3), 'avg_ma': round(_avg_ma, 3)}}",
        f"print(f\"[tx_burst_test] peak={{_peak_ma:.1f}}mA avg={{_avg_ma:.1f}}mA \\u2014 {{'PASS' if _pass else 'FAIL'}}\")",
    ], {"numpy"}


def _gen_gpio_toggle(bid, params, inputs, outs):
    pin = params.get("pin", "P0.13")
    action = params.get("action", "toggle")
    pulse_ms = params.get("pulse_ms", 100)
    return [
        f"# ── GPIO Toggle: {pin} ({action}) ──",
        f"_ = {inputs.get('trigger', 'None')}  # wait for trigger",
        f"try:",
        f"    from pyontrust.instruments.gpio_probe import GPIOProbe",
        f"    _gpio = GPIOProbe()",
        f"    _gpio.open()",
        f"    if {_py(action)} == 'toggle':",
        f"        _state = _gpio.toggle({_py(pin)})",
        f"    elif {_py(action)} == 'high':",
        f"        _gpio.set_high({_py(pin)}); _state = True",
        f"    elif {_py(action)} == 'low':",
        f"        _gpio.set_low({_py(pin)}); _state = False",
        f"    elif {_py(action)} == 'pulse':",
        f"        _gpio.pulse({_py(pin)}, ms={_py(pulse_ms)}); _state = True",
        f"    else:",
        f"        _state = False",
        f"    _gpio.close()",
        f"    {outs['state']} = _state",
        f"    print(f'[gpio] {action} {pin} → {{_state}}')",
        f"except ImportError:",
        f"    print('[gpio] GPIOProbe not available — simulating')",
        f"    {outs['state']} = True",
    ], set()


def _gen_serial_send(bid, params, inputs, outs):
    port = params.get("port", "COM3")
    baud = params.get("baudrate", 115200)
    cmd = params.get("command", "AT\\r\\n")
    timeout = params.get("timeout_s", 2)
    return [
        f"# ── Serial Send ──",
        f"import serial as _serial",
        f"_ser = _serial.Serial({_py(port)}, {_py(baud)}, timeout={_py(timeout)})",
        f"try:",
        f"    _ser.write({_py(cmd)}.encode())",
        f"    time.sleep(0.1)",
        f"    {outs['response']} = _ser.read(_ser.in_waiting or 256).decode(errors='replace')",
        "    print(f'[serial] {_ser.port} \u2192 {" + outs['response'] + "[:80]}')",
        f"finally:",
        f"    _ser.close()",
    ], {"time"}


def _gen_load_profile(bid, params, inputs, outs):
    path = params.get("path", "profiles/sleep_current.json")
    return [
        f"# ── Load Profile ──",
        f"with open({_py(path)}, 'r', encoding='utf-8') as _f:",
        f"    {outs['profile']} = json.load(_f)",
        f'print(f"[load_profile] Loaded {path}")',
    ], {"json"}


def _gen_benchmark_timer(bid, params, inputs, outs):
    label = params.get("label", "operation")
    return [
        f"# ── Benchmark Timer: {label} ──",
        f"_ = {inputs.get('trigger', 'None')}  # wait for trigger",
        f"{outs['elapsed_s']} = time.time() - _start_time",
        "print(f\"[benchmark] " + label + ": {" + outs['elapsed_s'] + ":.3f}s\")",
    ], {"time"}


# ═══════════════════════════════════════════════════════════════════════
# Generator registry
# ═══════════════════════════════════════════════════════════════════════

GENERATORS: dict[str, Any] = {
    # Instruments
    "simulated_power": _gen_simulated_power,
    "csv_file":        _gen_csv_file,
    "csv_replay":      _gen_csv_replay,
    "aoi_camera":      _gen_aoi_camera,
    "seek_thermal":    _gen_seek_thermal,
    "ppk2_meter":      _gen_ppk2_meter,
    "ad3_dwf_meter":   _gen_ad3_dwf_meter,
    "waveform_gen":    _gen_waveform_gen,
    "random_data":     _gen_random_data,
    # Android phone sensors
    "android_accel":   _gen_android_accel,
    "android_gyro":    _gen_android_gyro,
    "android_mag":     _gen_android_mag,
    "android_mic":     _gen_android_mic,
    "android_proximity": _gen_android_proximity,
    "android_light":   _gen_android_light,
    "android_pressure": _gen_android_pressure,
    "android_gps":     _gen_android_gps,
    "android_battery": _gen_android_battery,
    "android_gravity": _gen_android_gravity,
    "android_rotation": _gen_android_rotation,
    "android_torch":   _gen_android_torch,
    "lux_measure":     _gen_lux_measure,
    # Analysis
    "stats":           _gen_stats,
    "filter":          _gen_filter,
    "highpass_filter":  _gen_highpass_filter,
    "bandpass_filter":  _gen_bandpass_filter,
    "fft_spectrum":    _gen_fft_spectrum,
    "moving_average":  _gen_moving_average,
    "derivative":      _gen_derivative,
    "integral":        _gen_integral,
    "threshold":       _gen_threshold,
    "window_slice":    _gen_window_slice,
    "resample":        _gen_resample,
    "edge_detect":     _gen_edge_detect,
    "histogram":       _gen_histogram,
    "correlate":       _gen_correlate,
    # Vision
    "thermal_analyze": _gen_thermal_analyze,
    "aoi_inspect":     _gen_aoi_inspect,
    "color_detect":    _gen_color_detect,
    "blob_detect":     _gen_blob_detect,
    "template_match":  _gen_template_match,
    "image_resize":    _gen_image_resize,
    "image_crop":      _gen_image_crop,
    "image_threshold": _gen_image_threshold,
    # Math
    "expression":      _gen_expression,
    "constant":        _gen_constant,
    "multiply":        _gen_multiply,
    "add":             _gen_add,
    "subtract":        _gen_subtract,
    "divide":          _gen_divide,
    "abs_val":         _gen_abs_val,
    "power":           _gen_power,
    "log_math":        _gen_log_math,
    "trig":            _gen_trig,
    "clamp":           _gen_clamp,
    "map_range":       _gen_map_range,
    "compare":         _gen_compare,
    "unit_convert":    _gen_unit_convert,
    # Data
    "dict_get":        _gen_dict_get,
    "dict_set":        _gen_dict_set,
    "dict_build":      _gen_dict_build,
    "list_build":      _gen_list_build,
    "json_parse":      _gen_json_parse,
    "format_string":   _gen_format_string,
    "type_cast":       _gen_type_cast,
    "pick_field":      _gen_pick_field,
    # I/O
    "display":         _gen_display,
    "plot_trace":      _gen_plot_trace,
    "plot_xy":         _gen_plot_xy,
    "plot_histogram":  _gen_plot_histogram,
    "plot_heatmap":    _gen_plot_heatmap,
    "gauge_display":   _gen_gauge_display,
    "table_display":   _gen_table_display,
    "save_file":       _gen_save_file,
    "log_message":     _gen_log_message,
    "assert_check":    _gen_assert_check,
    # Flow
    "delay":           _gen_delay,
    "repeat":          _gen_repeat,
    "gate":            _gen_gate,
    "merge":           _gen_merge,
    "sequence":        _gen_sequence,
    "null_check":      _gen_null_check,
    "try_catch":       _gen_try_catch,
    # Actions
    "shell_cmd":       _gen_shell_cmd,
    "http_request":    _gen_http_request,
    "sleep_test":      _gen_sleep_test,
    "tx_burst_test":   _gen_tx_burst_test,
    "gpio_toggle":     _gen_gpio_toggle,
    "serial_send":     _gen_serial_send,
    "load_profile":    _gen_load_profile,
    "benchmark_timer": _gen_benchmark_timer,
}


# ═══════════════════════════════════════════════════════════════════════
# Main codegen function
# ═══════════════════════════════════════════════════════════════════════

def _sanitise_id(bid: str) -> str:
    """Convert block id like 'b3' to a valid Python variable prefix."""
    return bid.replace("-", "_").replace(".", "_")


def diagram_to_python(diagram: dict[str, Any], *, script_name: str = "flowlab_export") -> str:
    """Convert a serialised FlowLab diagram to a standalone Python script.

    Parameters
    ----------
    diagram : dict
        The serialised diagram with ``blocks`` and ``wires`` lists.
    script_name : str
        Name used in the script header.

    Returns
    -------
    str
        Complete, runnable Python source code.
    """
    blocks_raw = diagram.get("blocks", [])
    wires_raw = diagram.get("wires", [])

    if not blocks_raw:
        return "# Empty diagram — nothing to export.\n"

    # ── Build block map and adjacency ──
    block_map: dict[str, dict] = {b["id"]: b for b in blocks_raw}
    in_edges: dict[str, set[str]] = defaultdict(set)

    # wire_map: (dst_block, dst_port) → (src_block, src_port)
    wire_map: dict[tuple[str, str], tuple[str, str]] = {}

    for w in wires_raw:
        src_blk = w["from"]["block"]
        dst_blk = w["to"]["block"]
        dst_port = w["to"]["port"]
        src_port = w["from"]["port"]
        in_edges[dst_blk].add(src_blk)
        wire_map[(dst_blk, dst_port)] = (src_blk, src_port)

    # ── Topological sort (Kahn's) ──
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
        for w in wires_raw:
            if w["from"]["block"] == bid:
                dst = w["to"]["block"]
                in_degree[dst] -= 1
                if in_degree[dst] == 0:
                    queue.append(dst)

    # ── Generate variable names for each block's output ports ──
    # e.g. block "b3" output port "trace" → "b3_trace"
    def out_var(bid: str, port: str) -> str:
        return f"{_sanitise_id(bid)}_{port}"

    # For each block, map its output port names to variable names
    def block_output_vars(bid: str, btype: str) -> dict[str, str]:
        """Build output_port → variable_name mapping."""
        # Look up known outputs from the BLOCK_CATALOGUE data in the diagram
        # or from the generator
        gen = GENERATORS.get(btype)
        if not gen:
            return {}

        # We need to know the output ports — derive from diagram block definitions
        # or use a default set based on what the generator accesses
        # We'll use a helper: call the generator with dummy data to see what 'outs' keys it expects
        # Instead, use a static map from the JS BLOCK_CATALOGUE knowledge:
        return _output_ports_for_type(btype, bid)

    # ── Static output port mapping (mirrors JS BLOCK_CATALOGUE) ──
    def _output_ports_for_type(btype: str, bid: str) -> dict[str, str]:
        _OUTPUTS: dict[str, list[str]] = {
            "simulated_power": ["trace"], "csv_file": ["trace"], "csv_replay": ["trace"],
            "aoi_camera": ["frame"], "seek_thermal": ["thermal", "temp_c"],
            "ppk2_meter": ["trace"], "ad3_dwf_meter": ["trace"],
            "waveform_gen": ["trace"], "random_data": ["data"],
            "android_accel": ["accel", "trace"], "android_gyro": ["gyro", "trace"],
            "android_mag": ["mag", "trace"], "android_mic": ["audio", "level_db"],
            "android_proximity": ["distance", "near"],
            "android_light": ["lux"], "android_pressure": ["hpa"],
            "android_gps": ["location"], "android_battery": ["battery"],
            "android_gravity": ["gravity", "trace"], "android_rotation": ["rotation", "trace"],
            "stats": ["result"], "filter": ["filtered"], "highpass_filter": ["filtered"],
            "bandpass_filter": ["filtered"], "fft_spectrum": ["spectrum", "peaks"],
            "moving_average": ["smoothed"], "derivative": ["dtrace"],
            "integral": ["result"], "threshold": ["pass", "value"],
            "window_slice": ["sliced"], "resample": ["resampled"],
            "edge_detect": ["edges"], "histogram": ["hist"], "correlate": ["result"],
            "thermal_analyze": ["snapshot", "heatmap"], "aoi_inspect": ["result", "annotated"],
            "color_detect": ["result", "mask"], "blob_detect": ["blobs", "annotated"],
            "template_match": ["matches", "annotated"],
            "image_resize": ["resized"], "image_crop": ["cropped"],
            "image_threshold": ["binary", "stats"],
            "expression": ["result"], "constant": ["value"],
            "multiply": ["result"], "add": ["result"], "subtract": ["result"],
            "divide": ["result"], "abs_val": ["result"], "power": ["result"],
            "log_math": ["result"], "trig": ["result"], "clamp": ["result"],
            "map_range": ["result"], "compare": ["result"], "unit_convert": ["result"],
            "dict_get": ["value"], "dict_set": ["result"], "dict_build": ["result"],
            "list_build": ["result"], "json_parse": ["data"], "format_string": ["text"],
            "type_cast": ["result"], "pick_field": ["result"],
            "display": [], "plot_trace": [], "plot_xy": [],
            "plot_histogram": [], "plot_heatmap": [],
            "gauge_display": [], "table_display": [], "save_file": [],
            "log_message": ["data"], "assert_check": ["pass"],
            "delay": ["trigger"], "repeat": ["output", "index"],
            "gate": ["true_out", "false_out"], "merge": ["merged"],
            "sequence": ["last"], "null_check": ["value", "is_null"],
            "try_catch": ["data", "error"],
            "shell_cmd": ["stdout", "exit_code"],
            "http_request": ["response", "status"],
            "sleep_test": ["trace", "verdict"], "tx_burst_test": ["trace", "verdict"],
            "gpio_toggle": ["state"], "serial_send": ["response"],
            "load_profile": ["profile"], "benchmark_timer": ["elapsed_s"],
        }
        ports = _OUTPUTS.get(btype, [])
        return {p: out_var(bid, p) for p in ports}

    # ── Generate code for each block ──
    all_imports: set[str] = set()
    code_sections: list[str] = []

    for bid in order:
        bdef = block_map.get(bid)
        if not bdef:
            continue

        btype = bdef.get("type", "")
        params = bdef.get("params", {})
        gen = GENERATORS.get(btype)

        # Build output var map
        outs = _output_ports_for_type(btype, bid)

        # Build input map: port_name → "variable_expression"
        inp_vars: dict[str, str] = {}
        for w in wires_raw:
            if w["to"]["block"] == bid:
                src_bid = w["from"]["block"]
                src_port = w["from"]["port"]
                dst_port = w["to"]["port"]
                inp_vars[dst_port] = out_var(src_bid, src_port)

        if gen:
            lines, imports = gen(bid, params, inp_vars, outs)
            all_imports |= imports
            section = f"\n# ━━━ Block {bid}: {btype} ━━━"
            section += "\n" + "\n".join(lines)
            code_sections.append(section)
        else:
            code_sections.append(f"\n# ━━━ Block {bid}: {btype} (no code generator) ━━━")
            code_sections.append(f"# TODO: Implement {btype} handler")

    # ── Assemble the full script ──
    # Embed the diagram JSON as base64 for re-import into FlowLab
    diagram_json = json.dumps(diagram, separators=(",", ":"), default=str)
    diagram_b64 = base64.b64encode(diagram_json.encode("utf-8")).decode("ascii")

    # Build import block
    import_lines = [
        '#!/usr/bin/env python3',
        f'# FLOWLAB_DIAGRAM: {diagram_b64}',
        f'"""Auto-generated FlowLab test script: {script_name}',
        f'',
        f'Generated from a FlowLab visual diagram.',
        f'Blocks: {len(blocks_raw)}, Wires: {len(wires_raw)}',
        f'"""',
        '',
    ]

    # Standard library imports
    stdlib = {"json", "os", "csv", "math", "time", "subprocess"} & all_imports
    if stdlib:
        import_lines.append(f"import {', '.join(sorted(stdlib))}")

    # Third-party imports
    if "numpy" in all_imports:
        import_lines.append("import numpy as np")
    if "scipy" in all_imports:
        import_lines.append("# scipy is used for signal processing (pip install scipy)")

    import_lines.append("")
    import_lines.append("")

    # Main function
    main_lines = [
        f"def main():",
        f'    """Execute the FlowLab dataflow pipeline."""',
        f"    _start_time = __import__('time').time()",
        f"    print('=' * 60)",
        f"    print(f'FlowLab: {script_name}')",
        f"    print('=' * 60)",
        f"    print()",
    ]

    # Indent all code sections into main()
    for section in code_sections:
        for line in section.split("\n"):
            main_lines.append(f"    {line}" if line.strip() else "")

    # Footer
    main_lines.append("")
    main_lines.append("    print()")
    main_lines.append("    print('=' * 60)")
    main_lines.append("    _elapsed = __import__('time').time() - _start_time")
    main_lines.append("    print(f'Completed in {_elapsed:.3f}s')")
    main_lines.append("    print('=' * 60)")

    # Final result summary — collect all verdict-like outputs
    verdict_vars = []
    for bid in order:
        bdef = block_map.get(bid, {})
        outs = _output_ports_for_type(bdef.get("type", ""), bid)
        if "verdict" in outs:
            verdict_vars.append(outs["verdict"])
        if "pass" in outs:
            verdict_vars.append(outs["pass"])

    if verdict_vars:
        main_lines.append("")
        main_lines.append("    # ── Final Verdict ──")
        for vv in verdict_vars:
            main_lines.append(f"    print(f'  Verdict ({vv}): {{{vv}}}')")

    main_lines.append("")
    main_lines.append("")
    main_lines.append("if __name__ == '__main__':")
    main_lines.append("    main()")
    main_lines.append("")

    return "\n".join(import_lines + main_lines)
