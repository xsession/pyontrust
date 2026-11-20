# pyontrust

A flexible, hardware-agnostic **embedded test & measurement system** for automated power profiling, RF testing, flash programming, CAN bus capture, and visual inspection of embedded hardware designs.

## Architecture

```
lab_bench/power_test_framework/
├── core.py              # PowerSample, PowerTrace, PowerTestRunner
├── profiles.py          # JSON-driven test profiles + instrument factory
├── lab_bench.py         # Lab bench hardware inventory (JSON)
├── limits.py            # Pass/fail criteria + Verdict system
├── reporting.py         # CSV, JSON, Markdown artifact writers
├── instruments/
│   ├── base.py          # PowerMeter Protocol
│   ├── simulated.py     # Simulated meter (test double only)
│   ├── ad3_dwf.py       # Single Analog Discovery 3 (polling)
│   ├── ad3_cluster.py   # Multi-AD3 cluster (buffered acquisition)
│   ├── ppk2.py          # Nordic PPK2 (ppk2-api)
│   ├── sk120_psu.py     # SK120 programmable power supply (serial)
│   ├── jlink_ctrl.py    # SEGGER J-Link (flash/reset/RTT)
│   ├── hackrf_instrument.py  # HackRF One (IQ capture + sweep)
│   ├── webcam_instrument.py  # Webcam (snapshot + recording + vision)
│   ├── aoi_camera.py        # Industrial AOI camera (GenICam / webcam)
│   └── seek_thermal.py      # Seek Thermal USB camera (radiometric)
└── recorders/
    ├── base.py          # Recorder Protocol
    ├── pcan_can.py      # PEAK-CAN bus (python-can)
    ├── hackrf_iq.py     # HackRF IQ recording
    ├── ffmpeg_webcam.py # Video recording
    ├── aoi.py           # AOI background capture
    ├── thermal.py       # Thermal background capture + zone analysis
    └── ...
```

## Getting started

### Real hardware only

pyontrust measures real devices.  Every tool, API, FlowLab block and profile
uses the real drivers, and a missing device is reported as missing — it is
never silently replaced by synthetic data.  The simulator classes
(`SimulatedPowerMeter`, `SimulatedThermalCamera`, the virtual CAN bus, …) are
**test doubles only**: constructing one raises `SimulationDisabled` unless
`PYONTRUST_ALLOW_SIMULATION=1`, which the test suite sets in
`tests/conftest.py`.

Run the tests:

```bash
python -m pytest tests/ -q
```

Hardware access on Linux:

- **PPK2 / serial devices** — add yourself to `dialout` (`sudo usermod -aG dialout $USER`, then log in again).
- **PEAK PCAN-USB** (kernel `peak_usb`) — bring the link up once: `sudo ip link set can0 up type can bitrate 500000`.
- **Android phones** — enable USB debugging and tap *Allow USB debugging* on the phone.

### Lab bench configuration

Define your physical hardware setup once in `lab_bench.json`:

```json
{
  "name": "my_lab_bench",
  "instruments": {
    "power_meter": {"type": "ppk2", "serial_port": "auto", "mode": "source", "source_voltage_mv": 3300},
    "psu":         {"type": "sk120", "port": "COM5", "voltage_v": 3.3, "current_limit_a": 0.5},
    "jlink":       {"type": "jlink", "device": "nRF9160_xxAA", "interface": "swd"},
    "hackrf":      {"type": "hackrf", "freq_hz": 2402000000},
    "webcam":      {"type": "webcam", "input_device": "HD USB Camera"}
  }
}
```

### Test profiles (repeatable lab runs)

Profiles are JSON files describing timed steps with actions:

```powershell
python scripts\power_tests\run_profile.py run scripts\power_tests\example_full_bench.json --repo-root=.
```

Available action types:
- `flash` — program firmware via J-Link
- `reset_target` — reset DUT via J-Link
- `set_voltage` — change PSU output voltage
- `enable_output` — turn PSU on/off
- `snapshot` — capture webcam frame
- `inspect` — AOI board inspection (grab frame + defect detection)
- `thermal_capture` — grab thermal frame, analyse zones, save heatmap
- `rf_sweep` — HackRF frequency sweep
- `run` — execute any shell command
- `mark` — insert a timestamp marker
- `sleep` — wait a duration
- `set_power_mode` — switch power meter mode

### Pass/fail limits

Add limits to your profile to get automatic PASS/FAIL/WARN verdicts:

```json
{
  "limits": {
    "steps": {
      "idle_sleep": {
        "avg_current_a": {"max": 10e-6, "warn_max": 7e-6},
        "max_current_a": {"max": 50e-6}
      }
    }
  }
}
```

## Automated Optical Inspection (AOI)

Full machine vision pipeline documentation for PCB inspection is available in
[`docs/modules/aoi-machine-vision.md`](docs/modules/aoi-machine-vision.md), covering:

- **Pipeline architecture** — camera → frame grabber → image processing → decision engine
- **Hardware** — camera interface comparison (GigE / USB3 / CoaXPress), lighting systems (ring, dome, dark field, backlight, structured light)
- **Software stack** — GenICam / Harvesters acquisition, OpenCV defect detection, scikit-image solder & via analysis
- **System integration** — complete inspector with SQLite storage, JSON config, image archiving
- **BOM** — example hardware bill of materials with estimated costs

## Thermal Monitoring (Seek Thermal)

Board-level temperature monitoring during test runs using Seek Thermal USB cameras
(Compact, CompactPRO, CompactXR). Provides:

- **Zone-based ROI tracking** — define named regions (MCU, regulator, antenna) with per-zone warn/max thresholds
- **Rate-of-rise detection** — RUNAWAY verdict when temperature climbs faster than a configurable °C/s limit
- **Radiometric frames** — float32 °C-per-pixel for quantitative analysis
- **Colourised heatmaps** — inferno/jet/hot/rainbow/turbo palettes with zone overlays
- **Background recorder** — `thermal` recorder captures + analyses at configurable intervals
- **Service façade** — `ThermalService` for gateway / CLI integration

The AOI camera also supports a **webcam mode** (`mode="webcam"`) using OpenCV `VideoCapture`
for visual inspection without a GenICam industrial camera.

## Supported hardware

| Instrument | Type | Driver | Optional Dependency |
|------------|------|--------|-------------------|
| Analog Discovery 3 (single) | Power meter | `ad3_dwf` | DWF SDK (Digilent WaveForms) |
| Analog Discovery 3 (cluster) | Power meter | `ad3_cluster` | DWF SDK |
| Nordic PPK2 | Power meter | `ppk2` | `ppk2-api` |
| SK120 / Korad PSU | Power supply | `sk120` | `pyserial` |
| SEGGER J-Link | Debug probe | `jlink` | J-Link Software |
| HackRF One | RF analyzer | `hackrf` | `hackrf_transfer` / `hackrf_sweep` |
| Webcam (no IR filter) | Visual inspection | `webcam` | `ffmpeg` |
| PEAK-CAN | CAN bus recorder | `pcan_can` | `python-can` |
| nRF52840 Dongle | Serial recorder | `nrf52840_dongle` | `pyserial` |
| Industrial Camera (GenICam) | AOI inspection | `aoi_camera` | `opencv-python`, `harvesters` |
| USB Webcam (OpenCV) | AOI inspection | `aoi_camera` (webcam mode) | `opencv-python` |
| Seek Thermal Compact/Pro/XR | Thermal imaging | `seek_thermal` | `seekcamera-python` or `seek_thermal` |
| AOI Recorder | Background capture | `aoi` recorder | `numpy` |
| Thermal Recorder | Background thermal logging | `thermal` recorder | `numpy`, `opencv-python` (optional) |
| Android phone back cameras | Microscopy, 3D scan, spectroscopy | `phone_camera` (pyontrust camera app, ADB) | Android SDK build-tools (to build the app) |

## Cameras: Android phones and USB microscopes

Microscopy, 3D Scan and Spectroscopy use any mix of cameras **at the same
time**, each with a live feed: every back camera of every connected Android
phone (`phone:<serial>:<camera id>`) and USB/UVC cameras (`usb:<index>`).

Phones stream through the **pyontrust camera app** (`android-camera/`, plain
Java, Camera2): MJPEG preview at ~25 fps, full-resolution stills and manual
lens focus over HTTP on the phone, reached through `adb forward`.  The gateway
installs and starts the app automatically on every authorised phone; to build
it (needs the Android SDK `build-tools` and `platforms;android-34`):

```bash
cd android-camera && ./build.sh            # → build/pyontrust-camera.apk
./build.sh install                         # install on every authorised phone
```

- **Microscopy** — tick several cameras; *Capture* takes one still from each
  simultaneously into per-camera stacks.  *Focus sweep* drives each phone's
  lens from far to near (diopters = 1000 / mm) for a metric height map.
- **3D Scan** — left/right cameras (two phones by default), both live, plus a
  live SGBM depth map; capture a synchronised live pair or full-res stills.
  fx is derived from the phone's lens and sensor size.

## Lab Bench gateway (web UI)

All tools (Diagnostic, HIL, Lab Bench, CAN, Thermal, Microscopy, 3D Scan,
Spectroscopy, Waveforms, CSV Plotter, FlowLab, Interfaces, Artifacts,
Configuration, Station) run in one web app:

```bash
pip install -e ".[gui]"
./start_lab_bench.sh            # or: python -m pyontrust.gateway.app --port 5200
```

Open <http://127.0.0.1:5200>.  The gateway is served by **waitress**
(production WSGI server); `--debug` uses Flask's development server.

### Security model

The gateway drives real hardware, so every request is a physical action.

| Protection | Behaviour |
|---|---|
| Cross-site requests | Refused (`Sec-Fetch-Site` / `Origin` checks). A web page on another site cannot trigger or read anything. Extra origins: `PYONTRUST_ALLOWED_ORIGINS=https://a,https://b`. |
| Remote clients | Loopback is trusted. Any other client needs the **station token** — `Authorization: Bearer <token>`, or open `http://<pc>:5200/?token=<token>` once (sets an HttpOnly cookie). Token: `PYONTRUST_TOKEN` or `~/.pyontrust/gateway_token` (created on first non-loopback start and logged). |
| FlowLab | Expressions use an AST-checked evaluator (no `eval`). **Shell** and **HTTP** blocks are disabled unless `PYONTRUST_FLOWLAB_UNSAFE=1`. Diagram / profile names cannot contain paths. |
| Headers | `nosniff`, `SAMEORIGIN` framing, same-origin referrer. |
| Errors | One JSON envelope `{ok:false, error, status, request_id}`; `X-Request-ID` on every response. |

Binding to the network (`--host 0.0.0.0`, the Docker image) therefore
requires the token; read it from the container log or set `PYONTRUST_TOKEN`.

### Station: traceability and readiness

The **Station** tool (and the shell header chip) holds the session:
**operator** and **device under test**.  Every state-changing request is
appended to a **hash-chained audit log** (`~/.pyontrust/audit/`; any edit or
deletion is detected by *Verify chain*), and every run — thermal measurement
and tracking, microscopy stack, FlowLab diagram, HIL profile — is recorded in
the **run registry** (`~/.pyontrust/runs.sqlite`) with operator, DUT,
station, outcome, summary and artifacts, exportable as CSV, with first-pass
yield per tool.

Station also keeps the **instrument register** with calibration due dates
(overdue → station *not ready*, red dot in the navigation) and runs the
**self-tests** of every tool (drivers, attached hardware, configuration
risks).  Data location: `PYONTRUST_DATA_DIR` (default `~/.pyontrust`).

### Adding a tool

Tools are declared once in `src/pyontrust/gateway/tools.py` (title, icon,
group, blueprint, page folder, optional activity and self-test providers).
The app registers the blueprint, the shell renders the navigation, and the UI
contract tests check the page from that single entry.  Pages use the shared
design system: `/static/shell/tokens.css` + `components.css`.

## CSV Plotter

Interactive time-series viewer for power measurement CSV data:

```powershell
python gui_app\csv_plotter\csv_plotter.py
```

## MCP server

This repository includes a local MCP server for LM Studio and other tool-using agents. Install the optional dependency and run it from the repository root:

```powershell
python -m pip install -e .[mcp]
python scripts/mcp_server.py
```

Setup details and example LM Studio configuration are in [docs/modules/lm-studio-mcp.md](docs/modules/lm-studio-mcp.md).

## Project structure

The framework lives in `lab_bench/power_test_framework/`.

Core design principles:
- **Stdlib-only core** — no mandatory third-party dependencies
- **Protocol-based** — instruments and recorders are duck-typed protocols
- **JSON-driven** — lab bench + test profiles are plain JSON files
- **Artifact-centric** — every run produces CSV trace, JSON summary, and Markdown report
- **Hardware-optional** — all drivers skip gracefully when tools aren't installed