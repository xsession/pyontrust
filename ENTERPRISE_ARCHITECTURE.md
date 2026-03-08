# Pyontrust — Enterprise Architecture & Restructuring Plan

> **Version:** 1.0 · **Date:** 2026-03-07 · **Status:** Proposal  
> **Audience:** Engineering leadership, platform architects, QA leads  
> **Scope:** Unified platform for automated testing, HIL, multi-domain debugging, and real-time logging

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Current-State Audit](#2-current-state-audit)
3. [Problem Analysis](#3-problem-analysis)
4. [Target Architecture](#4-target-architecture)
5. [Proposed Directory Structure](#5-proposed-directory-structure)
6. [Layer Specification](#6-layer-specification)
7. [Interface Contracts (Protocols)](#7-interface-contracts-protocols)
8. [Multi-Channel Real-Time Logging Architecture](#8-multi-channel-real-time-logging-architecture)
9. [Hardware-in-the-Loop (HIL) Framework](#9-hardware-in-the-loop-hil-framework)
10. [GUI Unification Strategy](#10-gui-unification-strategy)
11. [Plugin / Extension System](#11-plugin--extension-system)
12. [Configuration Management](#12-configuration-management)
13. [Testing Strategy](#13-testing-strategy)
14. [CI/CD & Release Pipeline](#14-cicd--release-pipeline)
15. [Migration Roadmap](#15-migration-roadmap)
16. [Appendices](#appendices)

---

## 1  Executive Summary

Pyontrust today is a working collection of ~15 modules spanning power profiling,
RF capture, oscilloscope emulation, CAN bus logging, firmware flashing, vision
inspection, CSV analysis, pin configuration, and GNU Radio integration. Every
module works, 148+ tests pass, and real hardware is supported.

**The problem is organisational, not functional.** Modules live in inconsistent
locations, use three different GUI stacks (Tkinter, NiceGUI, Flask+JS), define
overlapping driver interfaces, duplicate path-bootstrap code, and lack a
unified way to compose them into end-to-end test campaigns.

This document proposes a **mono-repo restructuring** that:

| Goal | How |
|---|---|
| **One import path** for everything | `pyontrust.*` namespace package |
| **Protocol-first hardware abstraction** | Single `pyontrust.hal` layer shared by all modules |
| **Pluggable instruments & recorders** | Entry-point registry (`pyontrust.instruments`, `pyontrust.recorders`) |
| **Unified web dashboard** | Flask gateway + embeddable SPA micro-frontends |
| **Real-time multi-channel logging** | Central event bus (ZMQ or in-process) with typed channels |
| **HIL orchestration** | Profile-driven test campaigns with lab-bench declarations |
| **Enterprise CI** | Matrix tests, hardware-gated stages, artifact archival |
| **Zero breaking changes** | Incremental migration; old imports shim-redirected |

---

## 2  Current-State Audit

### 2.1  Module Inventory

| Module | Location | Tech Stack | Lines (≈) | Tests | Purpose |
|--------|----------|------------|-----------|-------|---------|
| **Power Test Framework** | `pyontrust_packages/power_test_framework/` | Pure Python (stdlib core) | ~3 500 | 60 | PowerTestRunner, instruments, recorders, limits, reporting |
| **CSV Plotter (web)** | `gui_app/csv_plotter/` | Flask + Plotly.js SPA | ~3 200 | 88 | Multi-channel time-series viewer & analysis |
| **CSV Plotter (legacy)** | `gui_app/csv_plotter/csv_plotter.py` | Tkinter + matplotlib | ~4 600 | — | Original desktop version (being replaced) |
| **Pin Configurator** | `gui_app/pin_configurator/` | Flask + vanilla JS SPA | ~5 500 | 18 | Zephyr DTS overlay generator, MCU datasheet parser |
| **SDR Module** | `gui_app/sdr_module/` (→`sdr_module/`) | NiceGUI + numpy + SoapySDR | ~2 800 | 3 | GNU Radio–like flowgraph for HackRF / SoapySDR |
| **WaveForms Module** | `gui_app/waveforms_module/` (→`waveforms_module/`) | NiceGUI + Rust/maturin DSP | ~1 800 | 1 | Oscilloscope / logic analyzer emulation |
| **GNU Radio Module** | `gui_app/gnuradio_module/` | NiceGUI | ~800 | 1 | External GNU Radio runner integration |
| **Lab-Bench Orchestrator** | `gui_app/labbench_orchestrator/` | NiceGUI | ~1 700 | — | GUI for profile execution & artifact review |
| **Power Test GUI (legacy)** | `gui_app/power_test_gui/` | Tkinter | ~200 | — | Thin launcher (superseded by orchestrator) |
| **NiceGUI Control** | `gui_app/nicegui_control/` | NiceGUI | ~100 | — | Main NiceGUI shell (currently broken/empty) |
| **Drivers** | `pyontrust_packages/drivers/` | Pure Python | ~600 | 2 | AD3 low-level wrapper, nRF dongle |
| **Utils** | `pyontrust_packages/utils/` | Python + scipy | ~800 | — | Signal processor, Log2csv, build helpers |
| **Custom Nodes** | `pyontrust_packages/custom_nodes/` | Node-RED | ~200 | — | Node-RED Python wrapper |
| **BarAM (submodule)** | `gui_app/baram/` | Python + Qt (OpenFOAM) | large | external | CFD mesh editor (vendored submodule) |
| **External SDKs** | `externals/` | C headers + DLLs | — | — | Digilent WaveForms SDK |

**Total: ~25 000 lines of Python · 148+ passing tests · 10 hardware instrument types**

### 2.2  Existing Protocol Interfaces

The codebase already defines several `Protocol` classes — this is a strength:

| Protocol | Location | Methods | Used By |
|----------|----------|---------|---------|
| `PowerMeter` | `power_test_framework/instruments/base.py` | `open()`, `close()`, `capture(duration_s)` | All instrument drivers |
| `Recorder` | `power_test_framework/recorders/base.py` | `start(ctx)`, `stop(ctx)` | PCAN, HackRF IQ, ffmpeg, process |
| `SdrHal` | `sdr_module/src/pyontrust_sdr/hal/protocol.py` | `discover()`, `open()`, `close()`, `set_rx_config()`, `start_stream()`, `read_iq()`, `stop_stream()` | Simulated, SoapyHackRF, FileReplay |

### 2.3  Existing Quality Infrastructure

| Aspect | Status |
|--------|--------|
| `pyproject.toml` (PEP 621) | ✅ Root-level with optional deps, pytest, mypy, ruff config |
| GitHub Actions CI | ✅ Matrix (3.10/3.11/3.12 × Linux/Win), lint, CSV + power tests |
| pytest markers | ✅ `slow`, `integration`, `ad3` for hardware-gated tests |
| Type annotations | Partial — framework core is typed, some modules not |
| Docs (Sphinx) | Stub — conf.py exists but not wired to current packages |

---

## 3  Problem Analysis

### 3.1  Structural Issues

| # | Problem | Impact | Severity |
|---|---------|--------|----------|
| **S1** | Three different GUI stacks (Tkinter, NiceGUI, Flask+JS) | Developers must learn 3 paradigms; no shared auth/nav/theme | 🔴 High |
| **S2** | No unified `pyontrust.*` import namespace | Every app has `sys.path.insert(0, ...)` bootstrap hacks | 🔴 High |
| **S3** | `gui_app/` mixes embeddable NiceGUI plugins with standalone Flask apps | Unclear which modules compose, which run standalone | 🟡 Medium |
| **S4** | SDR/WaveForms/GNURadio each define their own HAL protocol separately | Duplicated interface pattern; can't swap HackRF driver between SDR and power framework | 🟡 Medium |
| **S5** | `pyontrust_packages/` is not an installable package | Can't `pip install -e .` and get `from pyontrust.power_test_framework import ...` | 🔴 High |
| **S6** | Test files scattered (`tests/`, `gui_app/*/tests/`, inline) | CI must know all test paths; no single `pytest` invocation finds everything | 🟡 Medium |
| **S7** | No shared event/logging bus | Power trace, CAN frames, RF IQ, webcam snapshots can't be correlated in real-time | 🔴 High |
| **S8** | Externals shipped as raw DLLs/headers | No version pinning, no platform detection, manual install | 🟡 Medium |

### 3.2  Capability Gaps for Enterprise HIL

| # | Gap | Required For |
|---|-----|-------------|
| **G1** | No multi-instrument synchronised capture | Correlating power + RF + CAN + video in one timeline |
| **G2** | No live dashboard during test execution | Real-time monitoring of power traces, CAN messages, RF spectrum |
| **G3** | No test campaign management | Running sequences of profiles, aggregating verdicts, regression tracking |
| **G4** | No hardware inventory service | Discovering which instruments are plugged in, which bench a DUT is on |
| **G5** | No artifact database / indexing | Searching past test results by DUT, firmware version, date, verdict |
| **G6** | No role-based access or audit trail | Enterprise compliance (who ran what, when, with which firmware) |

---

## 4  Target Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              Web Browser                                    │
│  ┌─────────────┐ ┌──────────────┐ ┌───────────────┐ ┌───────────────────┐ │
│  │  Dashboard   │ │  CSV Plotter │ │ Pin Config    │ │ SDR / Waveforms   │ │
│  │  (live HIL)  │ │  (Plotly.js) │ │ (board cfg)   │ │ (IQ viewer)       │ │
│  └──────┬───────┘ └──────┬───────┘ └──────┬────────┘ └────────┬──────────┘ │
│         │ fetch/WS       │ fetch          │ fetch             │ fetch/WS   │
│ ════════╪════════════════╪════════════════╪═══════════════════╪════════ HTTP│
│         │                │                │                   │             │
│  ┌──────┴────────────────┴────────────────┴───────────────────┴──────────┐  │
│  │                     Flask Gateway  (gateway.py)                       │  │
│  │  • Blueprint-per-module:  /csv/*, /hil/*, /pin/*, /sdr/*, /wfm/*    │  │
│  │  • WebSocket relay for live data channels                            │  │
│  │  • Static file serving from each module's web/ folder                │  │
│  │  • Shared middleware: CORS, error handling, auth (optional)          │  │
│  └──────────────────────────┬───────────────────────────────────────────┘  │
│                             │                                              │
│  ┌──────────────────────────┴───────────────────────────────────────────┐  │
│  │                    Service Layer (pyontrust.services)                │  │
│  │  ┌──────────┐ ┌──────────┐ ┌───────────┐ ┌──────────┐ ┌─────────┐  │  │
│  │  │ TestSvc  │ │ LogSvc   │ │ ArtifactSvc│ │ BenchSvc │ │ CfgSvc  │  │  │
│  │  │(run/stop)│ │(channels)│ │(store/query)│ │(discover)│ │(profiles)│ │  │
│  │  └────┬─────┘ └────┬─────┘ └─────┬──────┘ └────┬─────┘ └────┬────┘  │  │
│  └───────┼────────────┼─────────────┼─────────────┼────────────┼────────┘  │
│          │            │             │             │            │            │
│  ┌───────┴────────────┴─────────────┴─────────────┴────────────┴────────┐  │
│  │                  Domain Core (pyontrust.core)                        │  │
│  │  • PowerSample, PowerTrace, PowerSummary, PowerTest, TestStep       │  │
│  │  • LabBench, InstrumentConfig, CalibrationData                      │  │
│  │  • Profile, Limit, TestSpec, TestVerdict                            │  │
│  │  • EventBus, Channel, TimestampedEvent                              │  │
│  └──────────────────────────┬───────────────────────────────────────────┘  │
│                             │                                              │
│  ┌──────────────────────────┴───────────────────────────────────────────┐  │
│  │              Hardware Abstraction (pyontrust.hal)                    │  │
│  │  ┌──────────────────────────────────────────────────────────────┐   │  │
│  │  │  Protocols: PowerMeter │ Recorder │ SdrHal │ DebugProbe │   │   │  │
│  │  │             Psu │ CanBus │ Camera │ SignalGenerator          │   │  │
│  │  └──────────────────────────────────────────────────────────────┘   │  │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌─────────┐  │  │
│  │  │ AD3/DWF  │ │ PPK2     │ │ HackRF   │ │ J-Link   │ │ PCAN    │  │  │
│  │  │ SK120    │ │ Webcam   │ │ SoapySDR │ │ nRF52840 │ │ Simulated│ │  │
│  │  └──────────┘ └──────────┘ └──────────┘ └──────────┘ └─────────┘  │  │
│  └──────────────────────────────────────────────────────────────────────┘  │
│                                                                            │
│  ┌──────────────────────────────────────────────────────────────────────┐  │
│  │              Analysis & DSP (pyontrust.analysis)                     │  │
│  │  • signal_processor (time/freq domain)  • metrics (power stats)     │  │
│  │  • vision (change detection, object detection)  • rf (spectrum)     │  │
│  └──────────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 4.1  Design Principles

| # | Principle | Implementation |
|---|-----------|----------------|
| **P1** | **Protocol-first** | Every hardware interface is a `typing.Protocol`. Implementations register via entry points. |
| **P2** | **Zero-hardware CI** | Every driver has a `Simulated*` counterpart. CI never requires physical devices. |
| **P3** | **Composable micro-frontends** | Each tool is a self-contained `web/` folder. Gateway serves them under path prefixes. |
| **P4** | **Event-driven logging** | All instruments publish to typed channels on a shared bus. |
| **P5** | **JSON-declarative tests** | Lab bench + profile + limits = complete test definition, version-controllable. |
| **P6** | **Stdlib-only core** | `pyontrust.core` and `pyontrust.hal` have ZERO third-party dependencies. |
| **P7** | **Progressive enhancement** | Works with `pip install pyontrust`. Optional extras: `[sdr]`, `[gui]`, `[analysis]`, `[all]`. |
| **P8** | **Single `pip install -e .`** | The whole repo is one editable install. No more `sys.path` hacks. |

---

## 5  Proposed Directory Structure

```
pyontrust/                          # Repository root
├── src/                            # ── Installable Python source ──
│   └── pyontrust/                  # Top-level namespace package
│       ├── __init__.py             # Version, metadata
│       ├── py.typed                # PEP 561 marker
│       │
│       ├── core/                   # ── Domain models (stdlib only) ──
│       │   ├── __init__.py
│       │   ├── models.py           # PowerSample, PowerTrace, PowerSummary, PowerTest, TestStep
│       │   ├── lab_bench.py        # LabBench, InstrumentConfig, CalibrationData
│       │   ├── profiles.py         # Profile loading, step building, instrument factory
│       │   ├── limits.py           # Limit, TestSpec, TestVerdict, evaluate()
│       │   ├── reporting.py        # CSV/JSON/Markdown artifact writers
│       │   ├── runner.py           # PowerTestRunner (extracted from core.py)
│       │   ├── events.py           # EventBus, Channel, TimestampedEvent
│       │   └── utils.py            # utc_timestamp_id, safe_float, etc.
│       │
│       ├── hal/                    # ── Hardware Abstraction Protocols ──
│       │   ├── __init__.py
│       │   ├── power_meter.py      # Protocol: PowerMeter
│       │   ├── recorder.py         # Protocol: Recorder
│       │   ├── sdr.py              # Protocol: SdrHal
│       │   ├── debug_probe.py      # Protocol: DebugProbe (J-Link, OpenOCD)
│       │   ├── psu.py              # Protocol: PowerSupply
│       │   ├── can_bus.py          # Protocol: CanBusInterface
│       │   ├── camera.py           # Protocol: Camera
│       │   └── signal_gen.py       # Protocol: SignalGenerator
│       │
│       ├── instruments/            # ── Concrete driver implementations ──
│       │   ├── __init__.py         # Registry: discover_instruments(), get_instrument()
│       │   ├── simulated.py        # SimulatedPowerMeter, SimulatedSdr, etc.
│       │   ├── ad3_dwf.py          # AD3 single device (DWF SDK)
│       │   ├── ad3_cluster.py      # Multi-AD3 buffered acquisition
│       │   ├── ppk2.py             # Nordic PPK2 via ppk2-api
│       │   ├── sk120_psu.py        # SK120 / Korad serial PSU
│       │   ├── jlink_ctrl.py       # SEGGER J-Link (flash/reset/RTT)
│       │   ├── hackrf.py           # HackRF One (IQ capture + sweep)
│       │   ├── soapy_sdr.py        # SoapySDR generic (merged from sdr_module)
│       │   ├── webcam.py           # Webcam snapshot/recording via ffmpeg
│       │   ├── pcan.py             # PEAK-CAN via python-can
│       │   ├── nrf52840_dongle.py  # nRF52840 serial recorder
│       │   ├── csv_replay.py       # Replay captured CSV as virtual instrument
│       │   └── dwf_loader.py       # DWF SDK dynamic loader helper
│       │
│       ├── recorders/              # ── Background capture implementations ──
│       │   ├── __init__.py
│       │   ├── process.py          # Shell command recorder
│       │   ├── hackrf_iq.py        # HackRF IQ file recording
│       │   ├── ffmpeg_webcam.py    # Video recording via ffmpeg
│       │   ├── pcan_can.py         # CAN bus logging
│       │   └── nrf52840_dongle.py  # nRF52840 serial logging
│       │
│       ├── analysis/               # ── Post-capture analysis ──
│       │   ├── __init__.py
│       │   ├── metrics.py          # Signal statistics (min/max/rms/fft/crest)
│       │   ├── signal_processor.py # Time/freq domain analysis (from utils/)
│       │   ├── vision_change.py    # LED blink / display change detection
│       │   ├── vision_objects.py   # YOLO-based object detection
│       │   ├── rf_spectrum.py      # RF sweep / waterfall analysis
│       │   └── csv_reader.py       # Multi-backend CSV reader (polars/duckdb/pandas)
│       │
│       ├── services/               # ── Stateful application services ──
│       │   ├── __init__.py
│       │   ├── test_service.py     # Campaign management: run/stop/status/history
│       │   ├── log_service.py      # Multi-channel logging & event bus manager
│       │   ├── artifact_service.py # Artifact storage, indexing, search
│       │   ├── bench_service.py    # Hardware discovery & bench config management
│       │   └── config_service.py   # Profile/limit/layout CRUD
│       │
│       └── gateway/                # ── Web layer (Flask + SPA micro-frontends) ──
│           ├── __init__.py
│           ├── app.py              # Flask app factory, blueprint registration
│           ├── middleware.py        # CORS, error handler, JSON sanitiser
│           ├── ws.py               # WebSocket relay for live data channels
│           │
│           ├── blueprints/         # One Flask Blueprint per tool
│           │   ├── __init__.py
│           │   ├── hil.py          # /hil/* — HIL dashboard, live monitoring
│           │   ├── csv_plotter.py  # /csv/* — CSV plotter endpoints
│           │   ├── pin_config.py   # /pin/* — Pin configurator endpoints
│           │   ├── sdr.py          # /sdr/* — SDR viewer endpoints
│           │   ├── waveforms.py    # /wfm/* — Waveforms viewer endpoints
│           │   ├── bench.py        # /bench/* — Lab bench management
│           │   └── artifacts.py    # /artifacts/* — Test result browser
│           │
│           └── web/                # Static SPA assets per tool
│               ├── shell/          # Shared: nav bar, theme, auth skeleton
│               │   ├── index.html  # App shell with <nav> + <main> mount point
│               │   ├── shell.js    # Client-side router, tab loader, theme
│               │   └── shell.css   # Catppuccin Mocha theme (shared)
│               ├── hil/            # HIL live dashboard
│               │   ├── index.html
│               │   └── main.js
│               ├── csv/            # CSV Plotter SPA (current web/)
│               │   ├── index.html
│               │   └── main.js
│               ├── pin/            # Pin Configurator SPA (current web/)
│               │   ├── index.html
│               │   └── main.js
│               ├── sdr/            # SDR Viewer SPA
│               │   ├── index.html
│               │   └── main.js
│               └── wfm/            # Waveforms Viewer SPA
│                   ├── index.html
│                   └── main.js
│
├── externals/                      # Vendored native SDKs
│   ├── WaveFormsSDK/
│   └── WaveformSDK_linux/
│
├── profiles/                       # ── Test profile library ──
│   ├── example_sleep_current.json
│   ├── example_full_bench.json
│   └── templates/
│       └── blank_profile.json
│
├── benches/                        # ── Lab bench definitions ──
│   ├── example_bench.json
│   └── templates/
│       └── blank_bench.json
│
├── tests/                          # ── All tests in one tree ──
│   ├── conftest.py                 # Shared fixtures: simulated instruments, tmp dirs
│   ├── unit/
│   │   ├── core/
│   │   │   ├── test_models.py
│   │   │   ├── test_runner.py
│   │   │   ├── test_limits.py
│   │   │   ├── test_profiles.py
│   │   │   ├── test_lab_bench.py
│   │   │   └── test_events.py
│   │   ├── instruments/
│   │   │   ├── test_simulated.py
│   │   │   ├── test_ad3_dwf.py
│   │   │   └── test_dwf_loader.py
│   │   ├── analysis/
│   │   │   ├── test_metrics.py
│   │   │   ├── test_csv_reader.py
│   │   │   ├── test_signal_processor.py
│   │   │   └── test_custom_code.py
│   │   └── gateway/
│   │       ├── test_csv_endpoints.py
│   │       ├── test_pin_endpoints.py
│   │       └── test_hil_endpoints.py
│   ├── integration/                # @pytest.mark.integration — needs HW or Docker
│   │   ├── test_ad3_real.py
│   │   ├── test_ppk2_real.py
│   │   └── test_full_profile_run.py
│   └── e2e/                        # Playwright / Selenium browser tests
│       └── test_csv_plotter_ui.py
│
├── docs/                           # ── Sphinx documentation ──
│   ├── conf.py
│   ├── index.rst
│   ├── architecture.rst            # This document, rendered
│   ├── getting_started.rst
│   ├── hal_reference.rst
│   ├── instrument_drivers.rst
│   └── profile_reference.rst
│
├── scripts/                        # ── Developer & CI utilities ──
│   ├── run_gateway.py              # `python -m pyontrust.gateway` alias
│   ├── run_profile.py              # CLI profile runner
│   ├── discover_hardware.py        # Print connected instruments
│   └── build_docs.py
│
├── pyproject.toml                  # PEP 621 — single source of truth
├── README.md
├── LICENSE
├── ENTERPRISE_ARCHITECTURE.md      # This document
├── CHANGELOG.md
└── .github/
    └── workflows/
        ├── ci.yml                  # Unit + lint on every push
        ├── integration.yml         # Hardware-gated (self-hosted runners)
        └── release.yml             # Tag → build → publish to internal PyPI
```

---

## 6  Layer Specification

### 6.1  Core Layer (`pyontrust.core`)

**Dependencies:** Python stdlib only (no pip packages).

| Module | Responsibility | Key Types |
|--------|---------------|-----------|
| `models.py` | Domain value objects | `PowerSample`, `PowerTrace`, `PowerSummary`, `TestStep`, `PowerTest`, `TestArtifacts`, `TestContext` |
| `runner.py` | Test execution engine | `PowerTestRunner.run()` |
| `lab_bench.py` | Bench configuration model | `LabBench`, `InstrumentConfig`, `CalibrationData` |
| `profiles.py` | Profile loading & instrument factory | `Profile`, `load_profile()`, `run_profile()` |
| `limits.py` | Pass/fail evaluation | `Limit`, `TestSpec`, `TestVerdict`, `evaluate()` |
| `reporting.py` | Artifact serialisation | `write_power_trace_csv()`, `write_summary_json()`, `write_report_md()` |
| `events.py` | **NEW** — In-process event bus | `EventBus`, `Channel`, `TimestampedEvent`, `Subscriber` |
| `utils.py` | Shared helpers | `utc_timestamp_id()`, path normalization |

### 6.2  HAL Layer (`pyontrust.hal`)

**Dependencies:** Python stdlib only. Each file defines a single `Protocol`.

```python
# pyontrust/hal/power_meter.py
from typing import Protocol, Iterable, runtime_checkable
from pyontrust.core.models import PowerSample

@runtime_checkable
class PowerMeter(Protocol):
    def open(self) -> None: ...
    def close(self) -> None: ...
    def capture(self, duration_s: float) -> Iterable[PowerSample]: ...

@runtime_checkable
class StreamingPowerMeter(PowerMeter, Protocol):
    """Extension for instruments that support continuous streaming."""
    def start_stream(self) -> None: ...
    def read_samples(self, max_samples: int, timeout_s: float) -> list[PowerSample]: ...
    def stop_stream(self) -> None: ...
```

Planned protocol hierarchy:

```
PowerMeter ─────── StreamingPowerMeter
Recorder
SdrHal ─────────── StreamingSdrHal
DebugProbe ─────── FlashableProbe
PowerSupply
CanBusInterface
Camera ─────────── StreamingCamera
SignalGenerator
```

### 6.3  Instruments Layer (`pyontrust.instruments`)

**Dependencies:** Per-driver (lazy-imported). The module itself stays stdlib-only.

Each driver file:
1. Imports its optional dependency inside `open()` (not at module top)
2. Provides a `create(config: dict) -> <Protocol>` factory function
3. Registers itself via `pyproject.toml` entry points:

```toml
[project.entry-points."pyontrust.instruments"]
simulated   = "pyontrust.instruments.simulated:create"
ad3_dwf     = "pyontrust.instruments.ad3_dwf:create"
ppk2        = "pyontrust.instruments.ppk2:create"
sk120       = "pyontrust.instruments.sk120_psu:create"
jlink       = "pyontrust.instruments.jlink_ctrl:create"
hackrf      = "pyontrust.instruments.hackrf:create"
webcam      = "pyontrust.instruments.webcam:create"
pcan        = "pyontrust.instruments.pcan:create"
soapy       = "pyontrust.instruments.soapy_sdr:create"
csv_replay  = "pyontrust.instruments.csv_replay:create"
```

Discovery at runtime:

```python
from importlib.metadata import entry_points

def discover_instruments():
    eps = entry_points(group="pyontrust.instruments")
    return {ep.name: ep for ep in eps}

def create_instrument(type_name: str, config: dict):
    eps = entry_points(group="pyontrust.instruments")
    ep = eps[type_name]
    factory = ep.load()
    return factory(config)
```

### 6.4  Analysis Layer (`pyontrust.analysis`)

| Module | Source (current) | Dependencies |
|--------|-----------------|-------------|
| `metrics.py` | `csv_plotter/metrics.py` | pandas, numpy |
| `csv_reader.py` | `csv_plotter/data.py` | pandas (+ optional polars/duckdb) |
| `signal_processor.py` | `utils/signal_processor/` | numpy, scipy |
| `vision_change.py` | `power_test_framework/vision_change_logger.py` | stdlib (ffmpeg subprocess) |
| `vision_objects.py` | `power_test_framework/vision_object_detector.py` | ultralytics (optional) |
| `rf_spectrum.py` | **NEW** | numpy |

### 6.5  Services Layer (`pyontrust.services`)

Stateful singletons that compose core + HAL + instruments:

| Service | Responsibility |
|---------|---------------|
| `TestService` | Run/stop/pause test profiles; campaign management; emit events |
| `LogService` | Multi-channel event bus manager; log routing; buffer management |
| `ArtifactService` | Store test artifacts to disk; index metadata; search past results |
| `BenchService` | Load bench configs; discover connected hardware; health checks |
| `ConfigService` | Profile/layout/limit CRUD; schema validation |

### 6.6  Gateway Layer (`pyontrust.gateway`)

Flask application factory + Blueprints:

```python
# pyontrust/gateway/app.py
from flask import Flask
from .middleware import register_error_handlers, SafeJSONProvider
from .blueprints import hil, csv_plotter, pin_config, sdr, waveforms, bench, artifacts

def create_app(config=None):
    app = Flask(__name__, static_folder=None)
    app.json = SafeJSONProvider(app)
    register_error_handlers(app)

    # Mount each tool under its own URL prefix
    app.register_blueprint(hil.bp,         url_prefix="/hil")
    app.register_blueprint(csv_plotter.bp, url_prefix="/csv")
    app.register_blueprint(pin_config.bp,  url_prefix="/pin")
    app.register_blueprint(sdr.bp,         url_prefix="/sdr")
    app.register_blueprint(waveforms.bp,   url_prefix="/wfm")
    app.register_blueprint(bench.bp,       url_prefix="/bench")
    app.register_blueprint(artifacts.bp,   url_prefix="/artifacts")

    # App shell (nav bar, router)
    @app.route("/")
    def index():
        return send_from_directory("web/shell", "index.html")

    return app
```

---

## 7  Interface Contracts (Protocols)

### 7.1  Unified Protocol Catalogue

All protocols live in `pyontrust.hal` and use `typing.Protocol` with `@runtime_checkable`.

```python
# ── Power Domain ──
class PowerMeter(Protocol):
    def open(self) -> None: ...
    def close(self) -> None: ...
    def capture(self, duration_s: float) -> Iterable[PowerSample]: ...

class PowerSupply(Protocol):
    def open(self) -> None: ...
    def close(self) -> None: ...
    def set_voltage(self, volts: float) -> None: ...
    def set_current_limit(self, amps: float) -> None: ...
    def enable_output(self, on: bool) -> None: ...
    def measure(self) -> tuple[float, float]: ...  # (V, A)

# ── RF Domain ──
class SdrHal(Protocol):
    def discover(self) -> list[DeviceInfo]: ...
    def open(self, device_id: str) -> None: ...
    def close(self) -> None: ...
    def set_rx_config(self, cfg: RxConfig) -> None: ...
    def start_stream(self) -> None: ...
    def read_iq(self, num_samples: int, timeout_s: float) -> np.ndarray: ...
    def stop_stream(self) -> None: ...

# ── Debug Domain ──
class DebugProbe(Protocol):
    def open(self) -> None: ...
    def close(self) -> None: ...
    def reset(self) -> None: ...
    def flash(self, firmware_path: str) -> None: ...
    def read_rtt(self, timeout_s: float) -> str: ...

# ── Bus Domain ──
class CanBusInterface(Protocol):
    def open(self) -> None: ...
    def close(self) -> None: ...
    def send(self, arbitration_id: int, data: bytes) -> None: ...
    def recv(self, timeout_s: float) -> CanFrame | None: ...

# ── Vision Domain ──
class Camera(Protocol):
    def open(self) -> None: ...
    def close(self) -> None: ...
    def snapshot(self) -> bytes: ...  # JPEG bytes
    def start_recording(self, output_path: str) -> None: ...
    def stop_recording(self) -> str: ...  # path to recorded file
```

---

## 8  Multi-Channel Real-Time Logging Architecture

### 8.1  Event Bus Design

```
┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐
│ PowerMeter│  │ CAN Bus  │  │ HackRF   │  │ Webcam   │
│ driver    │  │ driver   │  │ driver   │  │ driver   │
└─────┬─────┘  └─────┬─────┘  └─────┬─────┘  └─────┬─────┘
      │              │              │              │
      ▼              ▼              ▼              ▼
┌─────────────────────────────────────────────────────────┐
│                    EventBus                              │
│  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐   │
│  │ power   │  │ can     │  │ rf      │  │ video   │   │
│  │ channel │  │ channel │  │ channel │  │ channel │   │
│  └────┬────┘  └────┬────┘  └────┬────┘  └────┬────┘   │
│       │            │            │            │         │
│  ┌────┴────────────┴────────────┴────────────┴────┐    │
│  │          Subscriber Dispatch                    │    │
│  └────┬────────────┬────────────┬────────────┬────┘    │
└───────┼────────────┼────────────┼────────────┼──────────┘
        ▼            ▼            ▼            ▼
   ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐
   │ CSV     │  │ WebSocket│  │ Artifact│  │ Limit   │
   │ Writer  │  │ Relay   │  │ Store   │  │ Checker │
   └─────────┘  └─────────┘  └─────────┘  └─────────┘
```

### 8.2  Core Event Types

```python
@dataclass(frozen=True)
class TimestampedEvent:
    """Base for all events on the bus."""
    t_s: float          # Monotonic seconds since test start
    wall_time: str      # ISO 8601 wall clock
    source: str         # Instrument name

@dataclass(frozen=True)
class PowerEvent(TimestampedEvent):
    current_a: float
    voltage_v: float

@dataclass(frozen=True)
class CanFrameEvent(TimestampedEvent):
    arbitration_id: int
    data: bytes
    is_extended: bool = False

@dataclass(frozen=True)
class RfSampleEvent(TimestampedEvent):
    iq: np.ndarray      # complex64 chunk
    center_freq_hz: float
    sample_rate_hz: float

@dataclass(frozen=True)
class VisionEvent(TimestampedEvent):
    frame_path: str
    detections: list[dict]

@dataclass(frozen=True)
class MarkerEvent(TimestampedEvent):
    label: str
    fields: dict
```

### 8.3  EventBus Implementation

```python
class Channel:
    """Thread-safe typed publish/subscribe channel."""
    def __init__(self, name: str, event_type: type):
        self.name = name
        self.event_type = event_type
        self._subscribers: list[Callable] = []
        self._buffer: collections.deque = collections.deque(maxlen=100_000)
        self._lock = threading.Lock()

    def publish(self, event):
        with self._lock:
            self._buffer.append(event)
        for sub in self._subscribers:
            sub(event)

    def subscribe(self, callback: Callable) -> None:
        self._subscribers.append(callback)

    def recent(self, n: int = 1000) -> list:
        with self._lock:
            return list(self._buffer)[-n:]

class EventBus:
    def __init__(self):
        self._channels: dict[str, Channel] = {}

    def create_channel(self, name: str, event_type: type) -> Channel:
        ch = Channel(name, event_type)
        self._channels[name] = ch
        return ch

    def get_channel(self, name: str) -> Channel | None:
        return self._channels.get(name)

    def all_channels(self) -> dict[str, Channel]:
        return dict(self._channels)
```

### 8.4  Timeline Correlation

Every event carries `t_s` (monotonic seconds since test start). The gateway's
WebSocket relay fans out events from all channels into a unified JSON stream:

```json
{"ch": "power", "t_s": 1.234, "current_a": 0.000012, "voltage_v": 3.301}
{"ch": "can",   "t_s": 1.235, "id": 1537, "data": "0102030405060708"}
{"ch": "rf",    "t_s": 1.236, "peak_dbm": -42.5, "freq_hz": 2402000000}
{"ch": "marker","t_s": 1.300, "label": "flash_complete"}
```

Frontend plots all channels on a shared time axis (Plotly.js subplots).

---

## 9  Hardware-in-the-Loop (HIL) Framework

### 9.1  HIL Test Campaign Model

```
Campaign
├── bench: lab_bench.json           # Which instruments are available
├── profiles: [                     # Ordered list of test profiles
│   ├── profile_1.json              #   (each profile = one PowerTest)
│   ├── profile_2.json
│   └── ...
│ ]
├── limits: campaign_limits.json    # Aggregate pass/fail criteria
├── firmware:
│   ├── path: build/firmware.hex
│   ├── version: "1.2.3-rc4"
│   └── git_sha: "abc1234"
├── dut:
│   ├── serial: "DUT-00042"
│   ├── board: "nrf9160dk"
│   └── revision: "v3"
└── schedule:
    ├── mode: "sequential" | "parallel_instruments"
    ├── retry_on_fail: 1
    └── stop_on_first_fail: false
```

### 9.2  Campaign Execution Flow

```
                     campaign.json
                          │
                          ▼
                  ┌───────────────┐
                  │ CampaignRunner│
                  └───────┬───────┘
                          │ for each profile:
            ┌─────────────┼─────────────┐
            ▼             ▼             ▼
      ┌──────────┐  ┌──────────┐  ┌──────────┐
      │ Profile 1│  │ Profile 2│  │ Profile 3│
      │ (idle)   │  │ (TX)     │  │ (sleep)  │
      └────┬─────┘  └────┬─────┘  └────┬─────┘
           │              │              │
           ▼              ▼              ▼
      PowerTestRunner.run() for each
           │              │              │
           │  ┌───────────┼──────────┐   │
           │  │     EventBus         │   │
           │  │  power│can│rf│video  │   │
           │  └───────┬──────────────┘   │
           │          │                  │
           ▼          ▼                  ▼
      ┌─────────────────────────────────────┐
      │         Artifact Store              │
      │  artifacts/<campaign>/<profile>/    │
      │    ├── power_trace.csv              │
      │    ├── summary.json                 │
      │    ├── report.md                    │
      │    ├── recorders/                   │
      │    └── verdict.json                 │
      └────────────────┬────────────────────┘
                       │
                       ▼
              ┌─────────────────┐
              │ CampaignVerdict │
              │  PASS / FAIL    │
              │  + per-step     │
              │    verdicts     │
              └─────────────────┘
```

### 9.3  Live Dashboard (HIL Micro-Frontend)

The `/hil/` SPA provides during test execution:

| Panel | Data Source | Update Rate |
|-------|-----------|-------------|
| Power trace (real-time chart) | `power` channel via WebSocket | 10 Hz (decimated) |
| CAN message log | `can` channel via WebSocket | Per-frame |
| RF spectrum waterfall | `rf` channel via WebSocket | 1 Hz |
| Video feed | `video` channel (JPEG frames) | 2 FPS |
| Step progress bar | `marker` channel | Per-step |
| Live verdict indicators | `limits` evaluator | Per-step |
| Instrument status badges | `bench_service` polling | 5s |

---

## 10  GUI Unification Strategy

### 10.1  Decision: Flask Micro-Frontends (not NiceGUI)

| Criterion | NiceGUI | Flask + vanilla JS |
|-----------|---------|-------------------|
| Air-gapped lab PC | Needs `nicegui` (50+ transitive deps) | `flask` (3 deps) |
| Build step | None | None |
| Composability | Each module is a full NiceGUI app | Each module is a Blueprint + static `web/` |
| Real-time | Built-in WebSocket | `flask-sock` or Server-Sent Events |
| Existing modules using it | SDR, WaveForms, GNURadio, Orchestrator | CSV Plotter, Pin Configurator |
| Theme consistency | Quasar (Material) | Catppuccin Mocha (already in 2 tools) |
| Browser testing | Difficult | Standard (Playwright, Selenium) |

**Decision:** Standardise on **Flask + vanilla JS** for all web GUIs. The two
existing Flask tools (CSV Plotter, Pin Configurator) become the template.
NiceGUI modules (SDR, WaveForms, GNURadio) get thin Flask Blueprint wrappers
that serve their existing `web/` UIs — the NiceGUI Python code becomes a
backend service called via internal API.

### 10.2  App Shell Pattern

A single `shell/index.html` provides the navigation chrome:

```html
<nav id="app-nav">
  <a href="/hil/">🔬 HIL Dashboard</a>
  <a href="/csv/">📈 CSV Plotter</a>
  <a href="/pin/">🔧 Pin Config</a>
  <a href="/sdr/">📡 SDR Viewer</a>
  <a href="/wfm/">⚡ Waveforms</a>
  <a href="/bench/">🏗️ Lab Bench</a>
  <a href="/artifacts/">📦 Artifacts</a>
</nav>
<main id="app-content">
  <!-- Each tool loads in an iframe or via client-side include -->
</main>
```

Each tool's `index.html` can run standalone (opens `http://localhost:PORT/csv/`)
or embedded inside the shell (loaded into `<main>`).

### 10.3  Shared Theme

All tools use the same CSS variables (Catppuccin Mocha), extracted into a shared
`shell.css` that each tool imports:

```css
:root {
  --bg:       #1e1e2e;
  --bg2:      #252538;
  --bg3:      #2d2d44;
  --fg:       #cdd6f4;
  --fg-dim:   #6c7086;
  --accent:   #89b4fa;
  --green:    #a6e3a1;
  --red:      #f38ba8;
  --yellow:   #f9e2af;
  --border:   #45475a;
  --radius:   6px;
}
```

---

## 11  Plugin / Extension System

### 11.1  Entry-Point Based Registration

Third-party or internal teams can add new instruments, recorders, or analysis
modules without modifying the core repo:

```toml
# In a separate package's pyproject.toml:
[project.entry-points."pyontrust.instruments"]
my_custom_dmm = "my_company.drivers.custom_dmm:create"

[project.entry-points."pyontrust.recorders"]
my_protocol_logger = "my_company.recorders.protocol_log:create"

[project.entry-points."pyontrust.analysis"]
my_custom_metric = "my_company.analysis.special_metric:compute"
```

### 11.2  Plugin Discovery API

```python
from pyontrust.instruments import discover_instruments, create_instrument

# List all registered instrument types (built-in + plugins)
available = discover_instruments()
# → {'simulated': <EntryPoint>, 'ad3_dwf': <EntryPoint>, 'my_custom_dmm': <EntryPoint>, ...}

# Instantiate from a bench config
meter = create_instrument("my_custom_dmm", {"port": "COM7", "range": "auto"})
```

### 11.3  Blueprint Plugins for GUI

```toml
[project.entry-points."pyontrust.blueprints"]
my_tool = "my_company.web.my_tool:bp"
```

The gateway auto-discovers and mounts additional Blueprints at startup:

```python
for ep in entry_points(group="pyontrust.blueprints"):
    bp = ep.load()
    app.register_blueprint(bp, url_prefix=f"/{ep.name}")
```

---

## 12  Configuration Management

### 12.1  Configuration Hierarchy

```
Defaults (code)  ←  lab_bench.json  ←  profile.json  ←  CLI args  ←  env vars
     (lowest)                                                        (highest)
```

### 12.2  Schema Validation

All JSON configs validated against Pydantic models (or dataclasses with manual
validation for stdlib-only core):

```python
# Already exists in lab_bench.py — extend to all config types:
@dataclass
class InstrumentConfig:
    type: str
    enabled: bool = True
    params: dict[str, Any] = field(default_factory=dict)
    calibration: CalibrationData | None = None
```

### 12.3  Environment Variables

| Variable | Purpose | Default |
|----------|---------|---------|
| `PYONTRUST_BENCH` | Path to default lab bench JSON | `./benches/default.json` |
| `PYONTRUST_ARTIFACTS` | Artifact output directory | `./artifacts` |
| `PYONTRUST_LOG_LEVEL` | Logging verbosity | `INFO` |
| `PYONTRUST_PORT` | Gateway HTTP port | `5200` |
| `PYONTRUST_WS_PORT` | WebSocket port | `5201` |

---

## 13  Testing Strategy

### 13.1  Test Pyramid

```
          ┌─────────┐
          │  E2E    │  5–10 tests  (Playwright, real browser)
          │ browser │
         ┌┴─────────┴┐
         │ Integration│  20–30 tests (real HW, Docker, multi-process)
         │            │  @pytest.mark.integration
        ┌┴────────────┴┐
        │   Unit        │  200+ tests (mocked instruments, pure functions)
        │               │  Fast, no I/O, no network
        └───────────────┘
```

### 13.2  pytest Configuration

```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "-ra --strict-markers -q --tb=short"
markers = [
    "slow: marks tests as slow (>5s)",
    "integration: needs external hardware or Docker",
    "ad3: needs Analog Discovery 3",
    "ppk2: needs Nordic PPK2",
    "jlink: needs SEGGER J-Link",
    "hackrf: needs HackRF One",
    "can: needs PEAK-CAN adapter",
    "e2e: browser-based end-to-end test",
]
filterwarnings = [
    "ignore::pytest.PytestCollectionWarning",
]
```

### 13.3  CI Matrix

| Job | Trigger | Runner | Scope |
|-----|---------|--------|-------|
| `unit` | Every push/PR | GitHub-hosted (Linux + Windows × 3.10/3.11/3.12) | `tests/unit/` |
| `lint` | Every push/PR | GitHub-hosted Ubuntu | ruff + mypy |
| `integration` | Nightly + manual | Self-hosted lab runner | `tests/integration/` with `--mark integration` |
| `e2e` | Pre-release | Self-hosted with browser | `tests/e2e/` via Playwright |
| `release` | Git tag `v*` | GitHub-hosted | Build wheel, publish to internal PyPI, Docker image |

### 13.4  Coverage Targets

| Layer | Target | Current (est.) |
|-------|--------|---------------|
| `core/` | 95% line | ~85% |
| `hal/` | 100% (protocols are trivial) | n/a |
| `instruments/` | 80% (simulated paths) | ~60% |
| `analysis/` | 90% | ~75% |
| `gateway/` | 70% (endpoint smoke tests) | ~40% |
| **Overall** | **80%** | **~55%** |

---

## 14  CI/CD & Release Pipeline

### 14.1  Versioning

**CalVer:** `YYYY.MM.PATCH` (e.g., `2026.03.0`).  
Single version source in `pyproject.toml` → `pyontrust.__version__`.

### 14.2  Release Artifacts

| Artifact | Format | Destination |
|----------|--------|-------------|
| Python wheel | `.whl` | Internal PyPI (Artifactory / GitLab registry) |
| Docker image | `pyontrust/gateway:2026.03.0` | Internal registry |
| Docs | HTML (Sphinx) | GitHub Pages or internal wiki |
| Changelog | `CHANGELOG.md` | Git tag release notes |

### 14.3  Docker Strategy

```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY . .
RUN pip install -e .[gui,analysis]
EXPOSE 5200 5201
CMD ["python", "-m", "pyontrust.gateway", "--host", "0.0.0.0"]
```

---

## 15  Migration Roadmap

### Phase 0 — Preparation (Week 1–2)

| # | Task | Risk | Effort |
|---|------|------|--------|
| 0.1 | Create `src/pyontrust/` directory structure | None | 2h |
| 0.2 | Move `pyontrust_packages/power_test_framework/` → `src/pyontrust/core/` + `instruments/` + `recorders/` | Low — add shim `__init__.py` in old location | 4h |
| 0.3 | Update `pyproject.toml` to use `src` layout with `[tool.setuptools] package-dir = {"" = "src"}` | None | 1h |
| 0.4 | Add `py.typed` marker | None | 5min |
| 0.5 | Verify `pip install -e .` works and all 148 tests pass | Gate | 2h |

### Phase 1 — Unified HAL (Week 2–3)

| # | Task | Risk | Effort |
|---|------|------|--------|
| 1.1 | Create `src/pyontrust/hal/` with all Protocol definitions | None | 4h |
| 1.2 | Refactor existing `instruments/base.py` → import from `pyontrust.hal` | Low | 2h |
| 1.3 | Merge SDR module's `SdrHal` protocol into `pyontrust.hal.sdr` | Medium — different method signatures | 4h |
| 1.4 | Add entry-point registration for all instruments | Low | 3h |
| 1.5 | Write `discover_instruments()` and `create_instrument()` | None | 2h |

### Phase 2 — Event Bus & Real-Time Logging (Week 3–4)

| # | Task | Risk | Effort |
|---|------|------|--------|
| 2.1 | Implement `EventBus`, `Channel`, event types in `src/pyontrust/core/events.py` | None | 6h |
| 2.2 | Instrument `PowerTestRunner` to publish `PowerEvent` on capture | Low | 3h |
| 2.3 | Instrument CAN/HackRF/Webcam recorders to publish events | Medium | 6h |
| 2.4 | Add WebSocket relay in gateway | Low | 4h |
| 2.5 | Write unit tests for event bus (thread safety, backpressure) | None | 4h |

### Phase 3 — Flask Gateway Unification (Week 4–6)

| # | Task | Risk | Effort |
|---|------|------|--------|
| 3.1 | Create `src/pyontrust/gateway/app.py` with Blueprint architecture | None | 4h |
| 3.2 | Migrate CSV Plotter server.py → `blueprints/csv_plotter.py` | Low — mostly re-prefix routes | 4h |
| 3.3 | Migrate Pin Configurator server.py → `blueprints/pin_config.py` | Low | 4h |
| 3.4 | Create `web/shell/` app shell (nav bar, router, shared CSS) | None | 6h |
| 3.5 | Create `/hil/` Blueprint with live dashboard micro-frontend | Medium | 12h |
| 3.6 | Wrap SDR/WaveForms NiceGUI backends as Flask Blueprints | High — biggest refactor | 16h |

### Phase 4 — HIL Campaign Runner (Week 6–8)

| # | Task | Risk | Effort |
|---|------|------|--------|
| 4.1 | Design campaign JSON schema | None | 3h |
| 4.2 | Implement `CampaignRunner` in `src/pyontrust/core/` | Medium | 8h |
| 4.3 | Add firmware version tracking to artifacts | Low | 2h |
| 4.4 | Add regression comparison (current vs baseline verdicts) | Medium | 6h |
| 4.5 | Write integration tests with simulated multi-instrument campaign | None | 6h |

### Phase 5 — Enterprise Hardening (Week 8–10)

| # | Task | Risk | Effort |
|---|------|------|--------|
| 5.1 | Add Sphinx docs with auto-generated API reference | Low | 8h |
| 5.2 | Add Docker build + compose (gateway + optional services) | Low | 4h |
| 5.3 | Add GitHub Actions release pipeline (tag → wheel → Docker) | Low | 4h |
| 5.4 | Add E2E browser tests (Playwright) | Medium | 8h |
| 5.5 | Add health-check endpoints and instrument status API | Low | 3h |
| 5.6 | Reach 80% test coverage target | Medium | 12h |

### Summary Timeline

```
Week  1  2  3  4  5  6  7  8  9  10
      ├──┤                              Phase 0: Preparation
         ├──┤                           Phase 1: Unified HAL
            ├──┤                        Phase 2: Event Bus
               ├─────┤                  Phase 3: Gateway
                        ├──┤            Phase 4: HIL Campaign
                              ├──┤      Phase 5: Hardening
```

**Total estimated effort: ~180 hours (1 senior developer, 10 weeks)**

---

## Appendices

### A  pyproject.toml (Target State)

```toml
[build-system]
requires = ["setuptools>=68.0"]
build-backend = "setuptools.build_meta"

[project]
name = "pyontrust"
version = "2026.3.0"
description = "Enterprise embedded test & measurement platform"
readme = "README.md"
license = {text = "MIT"}
requires-python = ">=3.10"
dependencies = []  # Core has ZERO mandatory dependencies

[project.optional-dependencies]
gui = [
    "flask>=3.0",
    "flask-sock>=0.7",
]
analysis = [
    "pandas>=1.5",
    "numpy>=1.23",
    "matplotlib>=3.6",
]
sdr = [
    "numpy>=1.23",
    "SoapySDR>=0.8.1",
]
power = [
    "docopt>=0.6.2",
]
dev = [
    "pytest>=7.0",
    "pytest-cov>=4.0",
    "mypy>=1.0",
    "ruff>=0.1",
    "playwright>=1.40",
    "sphinx>=7.0",
    "sphinx-rtd-theme>=2.0",
]
all = [
    "pyontrust[gui,analysis,sdr,power,dev]",
]

[project.scripts]
pyontrust = "pyontrust.gateway.app:main"

[project.entry-points."pyontrust.instruments"]
simulated   = "pyontrust.instruments.simulated:create"
ad3_dwf     = "pyontrust.instruments.ad3_dwf:create"
ad3_cluster = "pyontrust.instruments.ad3_cluster:create"
ppk2        = "pyontrust.instruments.ppk2:create"
sk120       = "pyontrust.instruments.sk120_psu:create"
jlink       = "pyontrust.instruments.jlink_ctrl:create"
hackrf      = "pyontrust.instruments.hackrf:create"
webcam      = "pyontrust.instruments.webcam:create"
pcan        = "pyontrust.instruments.pcan:create"
soapy       = "pyontrust.instruments.soapy_sdr:create"
csv_replay  = "pyontrust.instruments.csv_replay:create"

[project.entry-points."pyontrust.recorders"]
process     = "pyontrust.recorders.process:create"
hackrf_iq   = "pyontrust.recorders.hackrf_iq:create"
ffmpeg      = "pyontrust.recorders.ffmpeg_webcam:create"
pcan_can    = "pyontrust.recorders.pcan_can:create"

[tool.setuptools]
package-dir = {"" = "src"}

[tool.setuptools.packages.find]
where = ["src"]
```

### B  Backwards Compatibility Shim

During migration, keep old import paths working:

```python
# pyontrust_packages/power_test_framework/__init__.py  (shim)
import warnings
warnings.warn(
    "Import from 'pyontrust.core' instead of 'power_test_framework'",
    DeprecationWarning, stacklevel=2,
)
from pyontrust.core import *  # noqa: F401,F403
from pyontrust.core.limits import *  # noqa: F401,F403
from pyontrust.core.lab_bench import *  # noqa: F401,F403
```

### C  Hardware Compatibility Matrix

| Instrument | Windows | Linux | macOS | CI (Simulated) |
|------------|---------|-------|-------|----------------|
| AD3 (DWF SDK) | ✅ | ✅ | ✅ | ✅ |
| PPK2 | ✅ | ✅ | ✅ | ✅ |
| SK120 PSU | ✅ | ✅ | ❌ | ✅ |
| J-Link | ✅ | ✅ | ✅ | ✅ |
| HackRF | ✅ | ✅ | ✅ | ✅ |
| Webcam (ffmpeg) | ✅ | ✅ | ✅ | ✅ |
| PEAK-CAN | ✅ | ✅ | ❌ | ✅ |
| SoapySDR | ✅ | ✅ | ✅ | ✅ |
| nRF52840 Dongle | ✅ | ✅ | ✅ | ✅ |

### D  Key Metrics (Current → Target)

| Metric | Current | Target (Phase 5) |
|--------|---------|-------------------|
| Total tests | 148 | 300+ |
| Test coverage | ~55% | 80% |
| Import hacks (`sys.path.insert`) | 8 files | 0 |
| GUI stacks | 3 (Tkinter, NiceGUI, Flask) | 1 (Flask + vanilla JS) |
| Hardware protocols (separate) | 3 | 1 unified HAL |
| CI jobs | 2 (unit + lint) | 5 (unit + lint + integration + e2e + release) |
| Time to `pip install` | N/A (not installable) | `pip install -e .[all]` in <30s |
| Docs pages | 0 (stubs) | 20+ (auto-generated API + guides) |

---

*End of document. This is a living document — update version/date on each revision.*
