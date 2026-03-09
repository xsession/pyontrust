"""End-to-end test of FlowLab Python code generation.

Uses the correct block type names from BLOCK_CATALOGUE.
"""
import json, sys, textwrap, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))

from pyontrust.gateway.flowlab_codegen import diagram_to_python

PASS = 0
FAIL = 0

def test(name, diagram, *, execute=False):
    """Generate, compile, and optionally execute a diagram."""
    global PASS, FAIL
    try:
        code = diagram_to_python(diagram, script_name=name)
        compile(code, f"<{name}>", "exec")
        if execute:
            exec(code, {"__name__": "__main__"})
        print(f"  ✓ {name}  ({len(code.splitlines())} lines, {'executed' if execute else 'compiled'})")
        PASS += 1
    except Exception as e:
        print(f"  ✗ {name}  ── {e}")
        FAIL += 1


print("=" * 60)
print("FlowLab Codegen - End-to-End Tests")
print("=" * 60)

# 1. Single constant
test("single_constant", {
    "version": 1,
    "blocks": [
        {"id": "b1", "type": "constant", "x": 0, "y": 0,
         "params": {"value": "42", "dtype": "float"}},
    ],
    "wires": [],
}, execute=True)

# 2. Constant -> Threshold
test("const_threshold", {
    "version": 1,
    "blocks": [
        {"id": "b1", "type": "constant", "x": 0, "y": 0,
         "params": {"value": "5.0", "dtype": "float"}},
        {"id": "b2", "type": "threshold", "x": 200, "y": 0,
         "params": {"min_val": 0, "max_val": 10}},
    ],
    "wires": [
        {"id": "w1",
         "from": {"block": "b1", "port": "value"},
         "to": {"block": "b2", "port": "value"}},
    ],
}, execute=True)

# 3. Two constants -> multiply -> display
test("math_chain", {
    "version": 1,
    "blocks": [
        {"id": "a", "type": "constant", "x": 0, "y": 0,
         "params": {"value": "3.14", "dtype": "float"}},
        {"id": "b", "type": "constant", "x": 0, "y": 100,
         "params": {"value": "2.0", "dtype": "float"}},
        {"id": "m", "type": "multiply", "x": 200, "y": 50, "params": {}},
        {"id": "d", "type": "display", "x": 400, "y": 50,
         "params": {"label": "Result"}},
    ],
    "wires": [
        {"id": "w1", "from": {"block": "a", "port": "value"},
                      "to": {"block": "m", "port": "a"}},
        {"id": "w2", "from": {"block": "b", "port": "value"},
                      "to": {"block": "m", "port": "b"}},
        {"id": "w3", "from": {"block": "m", "port": "result"},
                      "to": {"block": "d", "port": "value"}},
    ],
}, execute=True)

# 4. Expression block
test("expression", {
    "version": 1,
    "blocks": [
        {"id": "c1", "type": "constant", "x": 0, "y": 0,
         "params": {"value": "10", "dtype": "float"}},
        {"id": "e1", "type": "expression", "x": 200, "y": 0,
         "params": {"expr": "a ** 2 + 1"}},
    ],
    "wires": [
        {"id": "w1", "from": {"block": "c1", "port": "value"},
                      "to": {"block": "e1", "port": "a"}},
    ],
}, execute=True)

# 5. Delay block
test("delay_block", {
    "version": 1,
    "blocks": [
        {"id": "d1", "type": "delay", "x": 0, "y": 0,
         "params": {"seconds": 0.01}},
    ],
    "wires": [],
}, execute=True)

# 6. Add / Subtract / Divide / Abs / Power
test("math_ops", {
    "version": 1,
    "blocks": [
        {"id": "c1", "type": "constant", "x": 0, "y": 0,
         "params": {"value": "-8", "dtype": "float"}},
        {"id": "c2", "type": "constant", "x": 0, "y": 100,
         "params": {"value": "3", "dtype": "float"}},
        {"id": "add1", "type": "add", "x": 200, "y": 0, "params": {}},
        {"id": "sub1", "type": "subtract", "x": 200, "y": 100, "params": {}},
        {"id": "div1", "type": "divide", "x": 200, "y": 200, "params": {}},
        {"id": "abs1", "type": "abs_val", "x": 400, "y": 0, "params": {}},
        {"id": "pow1", "type": "power", "x": 400, "y": 100, "params": {}},
    ],
    "wires": [
        {"id": "w1", "from": {"block": "c1", "port": "value"}, "to": {"block": "add1", "port": "a"}},
        {"id": "w2", "from": {"block": "c2", "port": "value"}, "to": {"block": "add1", "port": "b"}},
        {"id": "w3", "from": {"block": "c1", "port": "value"}, "to": {"block": "sub1", "port": "a"}},
        {"id": "w4", "from": {"block": "c2", "port": "value"}, "to": {"block": "sub1", "port": "b"}},
        {"id": "w5", "from": {"block": "c1", "port": "value"}, "to": {"block": "div1", "port": "a"}},
        {"id": "w6", "from": {"block": "c2", "port": "value"}, "to": {"block": "div1", "port": "b"}},
        {"id": "w7", "from": {"block": "c1", "port": "value"}, "to": {"block": "abs1", "port": "value"}},
        {"id": "w8", "from": {"block": "c1", "port": "value"}, "to": {"block": "pow1", "port": "base"}},
        {"id": "w9", "from": {"block": "c2", "port": "value"}, "to": {"block": "pow1", "port": "exp"}},
    ],
}, execute=True)

# 7. Log, Trig, Clamp, MapRange, Compare, UnitConvert
test("math_funcs", {
    "version": 1,
    "blocks": [
        {"id": "c1", "type": "constant", "x": 0, "y": 0,
         "params": {"value": "100", "dtype": "float"}},
        {"id": "lg1", "type": "log_math", "x": 200, "y": 0,
         "params": {"base": "e"}},
        {"id": "tg1", "type": "trig", "x": 200, "y": 100,
         "params": {"function": "sin"}},
        {"id": "cl1", "type": "clamp", "x": 200, "y": 200,
         "params": {"min_val": 0, "max_val": 50}},
        {"id": "mr1", "type": "map_range", "x": 200, "y": 300,
         "params": {"in_min": 0, "in_max": 100, "out_min": 0, "out_max": 1}},
        {"id": "cmp", "type": "compare", "x": 200, "y": 400,
         "params": {"operator": ">", "threshold": 50}},
        {"id": "uc1", "type": "unit_convert", "x": 200, "y": 500,
         "params": {"from_unit": "mA", "to_unit": "A"}},
    ],
    "wires": [
        {"id": "w1", "from": {"block": "c1", "port": "value"}, "to": {"block": "lg1", "port": "value"}},
        {"id": "w2", "from": {"block": "c1", "port": "value"}, "to": {"block": "tg1", "port": "value"}},
        {"id": "w3", "from": {"block": "c1", "port": "value"}, "to": {"block": "cl1", "port": "value"}},
        {"id": "w4", "from": {"block": "c1", "port": "value"}, "to": {"block": "mr1", "port": "value"}},
        {"id": "w5", "from": {"block": "c1", "port": "value"}, "to": {"block": "cmp", "port": "value"}},
        {"id": "w6", "from": {"block": "c1", "port": "value"}, "to": {"block": "uc1", "port": "value"}},
    ],
}, execute=True)

# 8. Data blocks
test("data_blocks", {
    "version": 1,
    "blocks": [
        {"id": "db", "type": "dict_build", "x": 0, "y": 0,
         "params": {"keys": "a,b,c"}},
        {"id": "dg", "type": "dict_get", "x": 200, "y": 0,
         "params": {"key": "a"}},
        {"id": "ds", "type": "dict_set", "x": 200, "y": 100,
         "params": {"key": "d", "value": "99"}},
        {"id": "lb", "type": "list_build", "x": 0, "y": 200,
         "params": {"size": 3}},
        {"id": "jp", "type": "json_parse", "x": 0, "y": 300, "params": {}},
        {"id": "fs", "type": "format_string", "x": 0, "y": 400,
         "params": {"template": "Hello {a}"}},
        {"id": "tc", "type": "type_cast", "x": 0, "y": 500,
         "params": {"to_type": "str"}},
        {"id": "pf", "type": "pick_field", "x": 0, "y": 600,
         "params": {"field": "name"}},
    ],
    "wires": [],
}, execute=True)

# 9. I/O blocks (compile only)
test("io_blocks", {
    "version": 1,
    "blocks": [
        {"id": "d1", "type": "display", "x": 0, "y": 0,
         "params": {"label": "test"}},
        {"id": "lm", "type": "log_message", "x": 200, "y": 0,
         "params": {"level": "info", "prefix": "TEST"}},
        {"id": "ac", "type": "assert_check", "x": 400, "y": 0,
         "params": {"message": "should be true"}},
        {"id": "gd", "type": "gauge_display", "x": 0, "y": 100,
         "params": {"label": "Current", "unit": "mA", "min_val": 0, "max_val": 100}},
        {"id": "td", "type": "table_display", "x": 200, "y": 100,
         "params": {"title": "Results"}},
    ],
    "wires": [],
})

# 10. Flow blocks
test("flow_blocks", {
    "version": 1,
    "blocks": [
        {"id": "r1", "type": "repeat", "x": 0, "y": 0,
         "params": {"count": 3}},
        {"id": "g1", "type": "gate", "x": 200, "y": 0,
         "params": {"mode": "pass_if_true"}},
        {"id": "mg", "type": "merge", "x": 200, "y": 100, "params": {}},
        {"id": "sq", "type": "sequence", "x": 200, "y": 200, "params": {}},
        {"id": "nc", "type": "null_check", "x": 200, "y": 300,
         "params": {"default": "N/A"}},
        {"id": "tc", "type": "try_catch", "x": 200, "y": 400, "params": {}},
    ],
    "wires": [],
})

# 11. Simulated power -> stats -> threshold -> display chain
test("power_pipeline", {
    "version": 1,
    "blocks": [
        {"id": "src", "type": "simulated_power", "x": 0, "y": 0,
         "params": {"sample_rate_hz": 1000, "duration_s": 1,
                    "base_current_a": 0.005, "noise_a": 0.001}},
        {"id": "st", "type": "stats", "x": 250, "y": 0, "params": {}},
        {"id": "th", "type": "threshold", "x": 500, "y": 0,
         "params": {"min_val": 0, "max_val": 0.01}},
        {"id": "dsp", "type": "display", "x": 750, "y": 0,
         "params": {"label": "Pass?"}},
    ],
    "wires": [
        {"id": "w1", "from": {"block": "src", "port": "trace"},
                      "to": {"block": "st", "port": "trace"}},
        {"id": "w2", "from": {"block": "st", "port": "result"},
                      "to": {"block": "th", "port": "value"}},
        {"id": "w3", "from": {"block": "th", "port": "pass"},
                      "to": {"block": "dsp", "port": "value"}},
    ],
})

# 12. Waveform gen
test("waveform", {
    "version": 1,
    "blocks": [
        {"id": "wg", "type": "waveform_gen", "x": 0, "y": 0,
         "params": {"shape": "sine", "frequency_hz": 100,
                    "amplitude": 1.0, "duration_s": 0.1,
                    "sample_rate_hz": 10000}},
    ],
    "wires": [],
})

# 13. Random data -> histogram
test("random_hist", {
    "version": 1,
    "blocks": [
        {"id": "rd", "type": "random_data", "x": 0, "y": 0,
         "params": {"distribution": "normal", "size": 100}},
        {"id": "h1", "type": "histogram", "x": 200, "y": 0,
         "params": {"bins": 20}},
    ],
    "wires": [
        {"id": "w1", "from": {"block": "rd", "port": "data"},
                      "to": {"block": "h1", "port": "trace"}},
    ],
})

# 14. Shell command + HTTP request
test("actions", {
    "version": 1,
    "blocks": [
        {"id": "sh", "type": "shell_cmd", "x": 0, "y": 0,
         "params": {"command": "echo hello", "timeout_s": 5}},
        {"id": "hr", "type": "http_request", "x": 200, "y": 0,
         "params": {"url": "https://httpbin.org/get", "method": "GET"}},
    ],
    "wires": [],
})

# 15. Sleep test + tx_burst_test
test("hw_tests", {
    "version": 1,
    "blocks": [
        {"id": "s1", "type": "sleep_test", "x": 0, "y": 0,
         "params": {"duration_s": 1, "max_current_ua": 10}},
        {"id": "t1", "type": "tx_burst_test", "x": 300, "y": 0,
         "params": {"duration_s": 1, "interval_ms": 100,
                    "max_peak_ma": 50, "max_avg_ma": 20}},
    ],
    "wires": [],
})

# 16. Load profile + benchmark timer
test("profile_bench", {
    "version": 1,
    "blocks": [
        {"id": "lp", "type": "load_profile", "x": 0, "y": 0,
         "params": {"path": "profiles/sleep_current.json"}},
        {"id": "bt", "type": "benchmark_timer", "x": 200, "y": 0,
         "params": {"label": "test_op"}},
    ],
    "wires": [],
})

# 17. GPIO toggle + serial send
test("gpio_serial", {
    "version": 1,
    "blocks": [
        {"id": "g1", "type": "gpio_toggle", "x": 0, "y": 0,
         "params": {"pin": "P0.13", "action": "toggle"}},
        {"id": "s1", "type": "serial_send", "x": 200, "y": 0,
         "params": {"port": "COM3", "baud": 115200,
                    "command": "AT\\r\\n"}},
    ],
    "wires": [],
})

# 18. All vision blocks
test("vision_blocks", {
    "version": 1,
    "blocks": [
        {"id": "cam", "type": "aoi_camera", "x": 0, "y": 0,
         "params": {"mode": "simulated"}},
        {"id": "ta", "type": "thermal_analyze", "x": 200, "y": 0, "params": {}},
        {"id": "ai", "type": "aoi_inspect", "x": 200, "y": 100, "params": {}},
        {"id": "cd", "type": "color_detect", "x": 200, "y": 200, "params": {}},
        {"id": "bd", "type": "blob_detect", "x": 200, "y": 300, "params": {}},
        {"id": "tm", "type": "template_match", "x": 200, "y": 400, "params": {}},
        {"id": "ir", "type": "image_resize", "x": 200, "y": 500, "params": {}},
        {"id": "ic", "type": "image_crop", "x": 200, "y": 600, "params": {}},
        {"id": "it", "type": "image_threshold", "x": 200, "y": 700, "params": {}},
    ],
    "wires": [],
})

# 19. Filter chain
test("filter_chain", {
    "version": 1,
    "blocks": [
        {"id": "src", "type": "simulated_power", "x": 0, "y": 0, "params": {}},
        {"id": "lp", "type": "filter", "x": 200, "y": 0,
         "params": {"cutoff_hz": 50}},
        {"id": "hp", "type": "highpass_filter", "x": 200, "y": 100,
         "params": {"cutoff_hz": 10}},
        {"id": "bp", "type": "bandpass_filter", "x": 200, "y": 200,
         "params": {"low_hz": 10, "high_hz": 100}},
        {"id": "ma", "type": "moving_average", "x": 200, "y": 300,
         "params": {"window_size": 20}},
        {"id": "dv", "type": "derivative", "x": 200, "y": 400, "params": {}},
        {"id": "ig", "type": "integral", "x": 200, "y": 500, "params": {}},
        {"id": "ff", "type": "fft_spectrum", "x": 200, "y": 600, "params": {}},
        {"id": "ws", "type": "window_slice", "x": 200, "y": 700, "params": {}},
        {"id": "rs", "type": "resample", "x": 200, "y": 800, "params": {}},
        {"id": "ed", "type": "edge_detect", "x": 200, "y": 900, "params": {}},
        {"id": "cr", "type": "correlate", "x": 200, "y": 1000, "params": {}},
    ],
    "wires": [
        {"id": "w1", "from": {"block": "src", "port": "trace"}, "to": {"block": "lp", "port": "trace"}},
        {"id": "w2", "from": {"block": "src", "port": "trace"}, "to": {"block": "hp", "port": "trace"}},
        {"id": "w3", "from": {"block": "src", "port": "trace"}, "to": {"block": "bp", "port": "trace"}},
        {"id": "w4", "from": {"block": "src", "port": "trace"}, "to": {"block": "ma", "port": "trace"}},
        {"id": "w5", "from": {"block": "src", "port": "trace"}, "to": {"block": "dv", "port": "trace"}},
        {"id": "w6", "from": {"block": "src", "port": "trace"}, "to": {"block": "ig", "port": "trace"}},
        {"id": "w7", "from": {"block": "src", "port": "trace"}, "to": {"block": "ff", "port": "trace"}},
        {"id": "w8", "from": {"block": "src", "port": "trace"}, "to": {"block": "ws", "port": "trace"}},
        {"id": "w9", "from": {"block": "src", "port": "trace"}, "to": {"block": "rs", "port": "trace"}},
        {"id": "w10", "from": {"block": "src", "port": "trace"}, "to": {"block": "ed", "port": "trace"}},
    ],
})

# 20. Plot blocks
test("plot_blocks", {
    "version": 1,
    "blocks": [
        {"id": "pt", "type": "plot_trace", "x": 0, "y": 0,
         "params": {"title": "Current", "y_label": "A"}},
        {"id": "pxy", "type": "plot_xy", "x": 200, "y": 0,
         "params": {"title": "XY", "mode": "markers"}},
        {"id": "ph", "type": "plot_histogram", "x": 400, "y": 0,
         "params": {"title": "Hist"}},
        {"id": "phm", "type": "plot_heatmap", "x": 600, "y": 0,
         "params": {"title": "Heat"}},
    ],
    "wires": [],
})

# ══════════════════════════════════════════════════════════════
# Import round-trip tests
# ══════════════════════════════════════════════════════════════
print()
print("=" * 60)
print("Import Round-Trip Tests")
print("=" * 60)

from pyontrust.gateway.flowlab_codegen import extract_diagram_from_python

# 21. Round-trip: export → extract
def test_roundtrip(name, diagram):
    global PASS, FAIL
    try:
        source = diagram_to_python(diagram, script_name=name)
        extracted = extract_diagram_from_python(source)
        assert extracted is not None, "extraction returned None"
        assert len(extracted["blocks"]) == len(diagram["blocks"]), \
            f"block count mismatch: {len(extracted['blocks'])} vs {len(diagram['blocks'])}"
        assert len(extracted["wires"]) == len(diagram["wires"]), \
            f"wire count mismatch: {len(extracted['wires'])} vs {len(diagram['wires'])}"
        print(f"  ✓ {name}  (round-trip OK, {len(extracted['blocks'])} blocks)")
        PASS += 1
    except Exception as e:
        print(f"  ✗ {name}  ── {e}")
        FAIL += 1


test_roundtrip("rt_single_block", {
    "version": 1,
    "blocks": [{"id": "b1", "type": "constant", "x": 0, "y": 0, "params": {"value": "42"}}],
    "wires": [],
})

test_roundtrip("rt_complex_pipeline", {
    "version": 1,
    "blocks": [
        {"id": "b1", "type": "waveform_gen", "x": 0, "y": 0,
         "params": {"shape": "sine", "frequency_hz": 100}},
        {"id": "b2", "type": "stats", "x": 200, "y": 0, "params": {}},
        {"id": "b3", "type": "display", "x": 400, "y": 0, "params": {"format": "auto"}},
    ],
    "wires": [
        {"id": "w1", "from": {"block": "b1", "port": "trace"},
                      "to": {"block": "b2", "port": "trace"}},
        {"id": "w2", "from": {"block": "b2", "port": "result"},
                      "to": {"block": "b3", "port": "data"}},
    ],
})

# 22. No marker → returns None
def test_no_marker():
    global PASS, FAIL
    result = extract_diagram_from_python("# just a regular script\nprint('hello')")
    if result is None:
        print("  ✓ no_marker  (correctly returned None)")
        PASS += 1
    else:
        print("  ✗ no_marker  ── expected None, got dict")
        FAIL += 1

test_no_marker()

# 23. Display block accepts 'value' port (wire to 'value' instead of 'data')
test("display_value_port", {
    "version": 1,
    "blocks": [
        {"id": "c1", "type": "constant", "x": 0, "y": 0,
         "params": {"value": "99", "dtype": "float"}},
        {"id": "d1", "type": "display", "x": 200, "y": 0,
         "params": {"format": "auto"}},
    ],
    "wires": [
        {"id": "w1", "from": {"block": "c1", "port": "value"},
                      "to": {"block": "d1", "port": "value"}},
    ],
}, execute=True)

# 24. Vision blocks produce real code (compile check with all params)
test("vision_full_params", {
    "version": 1,
    "blocks": [
        {"id": "cam", "type": "aoi_camera", "x": 0, "y": 0,
         "params": {"mode": "simulated", "width": 640, "height": 480}},
        {"id": "cd", "type": "color_detect", "x": 200, "y": 0,
         "params": {"color_space": "hsv", "low_h": 10, "high_h": 170, "low_s": 50, "high_s": 255, "low_v": 50, "high_v": 255}},
        {"id": "bd", "type": "blob_detect", "x": 400, "y": 0,
         "params": {"min_area": 50, "max_area": 5000, "circularity": 0.3}},
        {"id": "ir", "type": "image_resize", "x": 200, "y": 100,
         "params": {"width": 160, "height": 120, "interpolation": "cubic"}},
        {"id": "ic", "type": "image_crop", "x": 400, "y": 100,
         "params": {"x": 10, "y": 10, "w": 100, "h": 100}},
        {"id": "it", "type": "image_threshold", "x": 600, "y": 0,
         "params": {"method": "otsu", "threshold": 127, "invert": False}},
        {"id": "ai", "type": "aoi_inspect", "x": 600, "y": 100,
         "params": {"reference": "", "tolerance": 30}},
        {"id": "tm", "type": "template_match", "x": 800, "y": 0,
         "params": {"method": "ccoeff_normed", "threshold": 0.8}},
    ],
    "wires": [
        {"id": "w1", "from": {"block": "cam", "port": "frame"},
                      "to": {"block": "cd", "port": "frame"}},
        {"id": "w2", "from": {"block": "cam", "port": "frame"},
                      "to": {"block": "bd", "port": "frame"}},
        {"id": "w3", "from": {"block": "cam", "port": "frame"},
                      "to": {"block": "ir", "port": "frame"}},
        {"id": "w4", "from": {"block": "ir", "port": "resized"},
                      "to": {"block": "ic", "port": "frame"}},
        {"id": "w5", "from": {"block": "cam", "port": "frame"},
                      "to": {"block": "it", "port": "frame"}},
        {"id": "w6", "from": {"block": "cam", "port": "frame"},
                      "to": {"block": "ai", "port": "frame"}},
    ],
})

# 25. Thermal analysis with zones
test("thermal_full", {
    "version": 1,
    "blocks": [
        {"id": "st", "type": "seek_thermal", "x": 0, "y": 0,
         "params": {"mode": "simulated", "base_temp_c": 25}},
        {"id": "ta", "type": "thermal_analyze", "x": 200, "y": 0,
         "params": {"zones": "[]", "colormap": "inferno"}},
    ],
    "wires": [
        {"id": "w1", "from": {"block": "st", "port": "thermal"},
                      "to": {"block": "ta", "port": "thermal"}},
    ],
})

# 26. Math blocks print output
test("math_verbose", {
    "version": 1,
    "blocks": [
        {"id": "c1", "type": "constant", "x": 0, "y": 0,
         "params": {"value": "7", "dtype": "float"}},
        {"id": "c2", "type": "constant", "x": 0, "y": 80,
         "params": {"value": "3", "dtype": "float"}},
        {"id": "mul", "type": "multiply", "x": 200, "y": 0, "params": {}},
        {"id": "add", "type": "add", "x": 200, "y": 80, "params": {}},
        {"id": "sub", "type": "subtract", "x": 200, "y": 160, "params": {}},
        {"id": "div", "type": "divide", "x": 200, "y": 240, "params": {}},
    ],
    "wires": [
        {"id": "w1", "from": {"block": "c1", "port": "value"}, "to": {"block": "mul", "port": "a"}},
        {"id": "w2", "from": {"block": "c2", "port": "value"}, "to": {"block": "mul", "port": "b"}},
        {"id": "w3", "from": {"block": "c1", "port": "value"}, "to": {"block": "add", "port": "a"}},
        {"id": "w4", "from": {"block": "c2", "port": "value"}, "to": {"block": "add", "port": "b"}},
        {"id": "w5", "from": {"block": "c1", "port": "value"}, "to": {"block": "sub", "port": "a"}},
        {"id": "w6", "from": {"block": "c2", "port": "value"}, "to": {"block": "sub", "port": "b"}},
        {"id": "w7", "from": {"block": "c1", "port": "value"}, "to": {"block": "div", "port": "a"}},
        {"id": "w8", "from": {"block": "c2", "port": "value"}, "to": {"block": "div", "port": "b"}},
    ],
}, execute=True)

# ── Android Phone Sensor Tests ───────────────────────────────

# 27. Android Accelerometer → Stats
test("android_accel_stats", {
    "version": 1,
    "blocks": [
        {"id": "acc", "type": "android_accel", "x": 0, "y": 0,
         "params": {"mode": "simulated", "duration_s": 1, "sample_rate_hz": 50}},
        {"id": "st", "type": "stats", "x": 200, "y": 0, "params": {}},
        {"id": "d", "type": "display", "x": 400, "y": 0,
         "params": {"format": "auto"}},
    ],
    "wires": [
        {"id": "w1", "from": {"block": "acc", "port": "trace"},
                      "to": {"block": "st", "port": "trace"}},
        {"id": "w2", "from": {"block": "st", "port": "result"},
                      "to": {"block": "d", "port": "data"}},
    ],
})

# 28. Android Gyroscope standalone
test("android_gyro", {
    "version": 1,
    "blocks": [
        {"id": "gy", "type": "android_gyro", "x": 0, "y": 0,
         "params": {"mode": "simulated", "duration_s": 0.5, "sample_rate_hz": 100}},
    ],
    "wires": [],
})

# 29. Android Magnetometer standalone
test("android_mag", {
    "version": 1,
    "blocks": [
        {"id": "mg", "type": "android_mag", "x": 0, "y": 0,
         "params": {"mode": "simulated", "duration_s": 1, "sample_rate_hz": 50}},
    ],
    "wires": [],
})

# 30. Android Microphone → Display
test("android_mic", {
    "version": 1,
    "blocks": [
        {"id": "mic", "type": "android_mic", "x": 0, "y": 0,
         "params": {"mode": "simulated", "duration_s": 2, "sample_rate": 16000}},
        {"id": "d", "type": "display", "x": 200, "y": 0,
         "params": {"format": "auto"}},
    ],
    "wires": [
        {"id": "w1", "from": {"block": "mic", "port": "level_db"},
                      "to": {"block": "d", "port": "data"}},
    ],
})

# 31. Android Proximity + Light + Pressure
test("android_env_sensors", {
    "version": 1,
    "blocks": [
        {"id": "px", "type": "android_proximity", "x": 0, "y": 0,
         "params": {"mode": "simulated"}},
        {"id": "lt", "type": "android_light", "x": 0, "y": 80,
         "params": {"mode": "simulated", "duration_s": 1}},
        {"id": "pr", "type": "android_pressure", "x": 0, "y": 160,
         "params": {"mode": "simulated", "duration_s": 1}},
    ],
    "wires": [],
})

# 32. Android GPS + Battery
test("android_gps_battery", {
    "version": 1,
    "blocks": [
        {"id": "gps", "type": "android_gps", "x": 0, "y": 0,
         "params": {"mode": "simulated"}},
        {"id": "bat", "type": "android_battery", "x": 0, "y": 80,
         "params": {"mode": "simulated"}},
    ],
    "wires": [],
})

# 33. Android Gravity + Rotation
test("android_gravity_rotation", {
    "version": 1,
    "blocks": [
        {"id": "gv", "type": "android_gravity", "x": 0, "y": 0,
         "params": {"mode": "simulated", "duration_s": 1, "sample_rate_hz": 50}},
        {"id": "rot", "type": "android_rotation", "x": 0, "y": 80,
         "params": {"mode": "simulated", "duration_s": 1, "sample_rate_hz": 50}},
    ],
    "wires": [],
})

# 34. Full Android multi-sensor pipeline: Accel → Filter → Stats → Threshold → Display
test("android_full_pipeline", {
    "version": 1,
    "blocks": [
        {"id": "acc", "type": "android_accel", "x": 0, "y": 0,
         "params": {"mode": "simulated", "duration_s": 2, "sample_rate_hz": 100}},
        {"id": "flt", "type": "filter", "x": 200, "y": 0,
         "params": {"cutoff_hz": 10, "order": 4}},
        {"id": "st", "type": "stats", "x": 400, "y": 0, "params": {}},
        {"id": "th", "type": "threshold", "x": 600, "y": 0,
         "params": {"metric": "avg_current_a", "max_val": 100, "min_val": 0}},
        {"id": "d", "type": "display", "x": 800, "y": 0,
         "params": {"format": "auto"}},
    ],
    "wires": [
        {"id": "w1", "from": {"block": "acc", "port": "trace"},
                      "to": {"block": "flt", "port": "trace"}},
        {"id": "w2", "from": {"block": "flt", "port": "filtered"},
                      "to": {"block": "st", "port": "trace"}},
        {"id": "w3", "from": {"block": "st", "port": "result"},
                      "to": {"block": "th", "port": "value"}},
        {"id": "w4", "from": {"block": "th", "port": "value"},
                      "to": {"block": "d", "port": "data"}},
    ],
})

# Summary
print()
print("=" * 60)
total = PASS + FAIL
print(f"RESULTS: {PASS}/{total} passed, {FAIL} failed")
if FAIL:
    print("SOME TESTS FAILED")
    sys.exit(1)
else:
    print("ALL TESTS PASSED")
print("=" * 60)
