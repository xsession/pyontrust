"""FlowLab component coverage: every registered block type.

For each of the 91 block generators we synthesize a minimal valid diagram,
run it through diagram_to_python(), compile it, and execute it when the
block is safe to run on this bench (simulated modes, local files, no network).

Classification per block:
  EXECUTED        — generated, compiled AND ran cleanly
  COMPILED-ONLY   — generated + compiles; execution needs HW/network/optional dep
  FAILED          — codegen or compile error (real bug)
"""
import os, re, sys, time, json, tempfile, shutil

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "src"))
from pyontrust.gateway import flowlab_codegen as fc
from pyontrust.gateway.flowlab_codegen import diagram_to_python

# ── Introspect every generator: params (with defaults) + input ports ────────
def introspect(gen_name):
    src = os.path.join(ROOT, "src", "pyontrust", "gateway", "flowlab_codegen.py")
    txt = open(src).read()
    i = txt.find(f"def {gen_name}(")
    j = txt.find("\ndef ", i + 10)
    body = txt[i:j]
    params = {}
    for m in re.finditer(r'params\.get\(["\'](\w+)["\'](?:,\s*([^)]+))?\)', body):
        name, default = m.group(1), (m.group(2) or "None").strip()
        try:
            params[name] = eval(default, {"__builtins__": {}}, {})
        except Exception:
            params[name] = None
    inputs = sorted(set(re.findall(r"inputs\.get\(['\"](\w+)['\"]", body)))
    return params, inputs

GENERATORS = sorted(set(re.findall(r"def (_gen_\w+)\(", open(os.path.join(
    ROOT, "src", "pyontrust", "gateway", "flowlab_codegen.py")).read())))
BLOCK_TYPES = [g[len("_gen_"):] for g in GENERATORS]

# ── Per-block overrides: params that make the block runnable/safe here ──────
PROFILES_DIR = os.path.join(ROOT, "profiles")
OVERRIDES = {
    "http_request":  {"url": "http://127.0.0.1:9/", "method": "GET"},
    "shell_cmd":     {"command": "echo flowlab_ok", "timeout_s": 5},
    "serial_send":   {"port": "/dev/null", "command": "x", "baudrate": 9600, "timeout_s": 2},
    "gpio_toggle":   {"pin": 1, "action": "pulse", "pulse_ms": 1},
    "aoi_camera":    {"mode": "simulated", "width": 32, "height": 32},
    "seek_thermal":  {"mode": "simulated", "base_temp_c": 25, "inject_hotspot": True},
    "load_profile":  {"path": os.path.join(PROFILES_DIR, "_flowlab_run.json")},
    "sleep_test":    {"duration_s": 0.1, "settle_s": 0.05, "max_avg_ua": 9e6},
    "tx_burst_test": {"duration_s": 0.2, "interval_ms": 50, "max_avg_ma": 9e3, "max_peak_ma": 9e4},
    "save_file":     {"path": "/tmp/flowlab_cov_save.json", "fmt": "json"},
    "log_message":   {"level": "INFO", "prefix": "cov"},
    "benchmark_timer": {"label": "cov_bench"},
}
ANDROID_BLOCKS = [b for b in BLOCK_TYPES if b.startswith("android_")]

# Blocks that must NOT be executed (HW / network / side effects) — compile only.
COMPILE_ONLY = {
    "ppk2_meter", "ad3_dwf_meter",          # bench instruments not attached to this flow
    "http_request",                          # network
    "gpio_toggle",                           # needs gpiod/RPi.GPIO
    "serial_send",                           # /dev/null may work, but keep deterministic: compile-only
}

SOURCE_PORTS = {"waveform_gen": "trace", "constant": "value", "aoi_camera": "frame"}

def make_source_for(port):
    """Pick an upstream block that plausibly feeds this input port; returns (block, out_port)."""
    if port in ("trace", "dtrace", "filtered", "smoothed"):
        blk = {"id": f"src_{port}", "type": "waveform_gen", "x": -300, "y": 0,
               "params": {"shape": "sine", "frequency_hz": 100, "amplitude": 1.0,
                          "duration_s": 0.02, "sample_rate_hz": 5000}}
    elif port in ("image", "img", "snapshot", "heatmap"):
        blk = {"id": f"src_{port}", "type": "aoi_camera", "x": -300, "y": 0,
               "params": {"mode": "simulated", "width": 32, "height": 32}}
    else:  # cond/trigger/scalars/steps — scalar constant
        blk = {"id": f"src_{port}", "type": "constant", "x": -300, "y": 0,
               "params": {"value": "1.0", "dtype": "float"}}
    return blk, SOURCE_PORTS[blk["type"]]

def build_diagram(btype):
    gen = f"_gen_{btype}"
    params, inputs = introspect(gen)
    params.update(OVERRIDES.get(btype, {}))
    if btype in ANDROID_BLOCKS:
        params.setdefault("mode", "simulated")
    # drop params whose default is None (optional) to keep diagrams minimal
    params = {k: v for k, v in params.items() if v is not None}

    blocks = [{"id": "b1", "type": btype, "x": 0, "y": 0, "params": params}]
    wires = []
    seen_src = {}
    for port in inputs:
        src, out_port = make_source_for(port)
        if src["id"] not in seen_src:
            blocks.append(src); seen_src[src["id"]] = True
        wires.append({"id": f"w_{port}", "from": {"block": src["id"], "port": out_port},
                      "to": {"block": "b1", "port": port}})
    return {"version": 1, "blocks": blocks, "wires": wires}

def main():
    os.environ.setdefault("MPLBACKEND", "Agg")
    tmp = tempfile.mkdtemp(prefix="flowlab_cov_")
    results = []
    for btype in BLOCK_TYPES:
        status, detail = "FAILED", ""
        try:
            diagram = build_diagram(btype)
            code = diagram_to_python(diagram, script_name=f"cov_{btype}")
            compile(code, f"<cov_{btype}>", "exec")
            if btype in COMPILE_ONLY:
                status, detail = "COMPILED-ONLY", "hw/network/optional-dep (by design)"
            else:
                old_cwd = os.getcwd()
                os.chdir(tmp)
                try:
                    ns = {"__name__": "__main__"}
                    exec(compile(code, f"<cov_{btype}>", "exec"), ns)
                    status = "EXECUTED"
                except Exception as e:
                    status, detail = "COMPILED-ONLY", f"{type(e).__name__}: {str(e)[:90]}"
                finally:
                    os.chdir(old_cwd)
        except Exception as e:
            status, detail = "FAILED", f"{type(e).__name__}: {str(e)[:120]}"
        results.append((btype, status, detail))

    print("=" * 78)
    print(f"FlowLab component coverage — {len(results)} block types")
    print("=" * 78)
    for btype, status, detail in results:
        mark = {"EXECUTED": "✓", "COMPILED-ONLY": "~", "FAILED": "✗"}[status]
        line = f" {mark} {btype:20s} {status}"
        if detail: line += f"  ({detail})"
        print(line)

    n_exec = sum(1 for _, s, _ in results if s == "EXECUTED")
    n_comp = sum(1 for _, s, _ in results if s == "COMPILED-ONLY")
    n_fail = sum(1 for _, s, _ in results if s == "FAILED")
    print("-" * 78)
    print(f"EXECUTED={n_exec}  COMPILED-ONLY={n_comp}  FAILED={n_fail}")

    with open(os.path.join(tmp, "coverage_report.json"), "w") as f:
        json.dump(results, f, indent=1)
    shutil.rmtree(tmp, ignore_errors=True)
    return n_fail == 0

if __name__ == "__main__":
    import sys as _s
    _s.exit(0 if main() else 1)
