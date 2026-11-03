# pyontrust

**Enterprise embedded test & measurement platform.**

pyontrust is a Python-based HIL (hardware-in-the-loop) and instrument
platform for lab benches: power measurement, SDR experiments, AOI machine
vision, spectroscopy, stereo3D tracking, multi-phone acoustic arrays, and
thermal imaging — all driven from one Flask gateway with a web UI.

## Highlights

- **Zero mandatory core dependencies** — the platform core is pure Python;
  instrument backends opt in via extras (`gui`, `analysis`, `aoi`, `sdr`, …).
- **Instrument HAL layer** — USB/serial instruments (Digilent, PCAN, HackRF,
  Seek Thermal, AD3 power bench) behind a uniform driver interface.
- **Mobile as sensors** — Android phones become stereo3D cameras and
  microphone-array nodes over ADB + Termux.
- **FlowLab scenario engine** — declarative test scenarios with codegen for
  HIL targets.

## Documentation map

| Area | Start here |
|---|---|
| Installation & running (incl. Docker) | [Getting Started](getting-started.md) |
| System design | [Enterprise Architecture](architecture/ENTERPRISE_ARCHITECTURE.md) |
| Spectroscopy pipeline | [Mobile Spectroscopy](modules/mobile-spectroscopy.md) |
| Stereo3D phone tracking | [Mobile Stereo3D Tracking](modules/mobile-stereo3d-tracking.md) |
| Acoustic noise localization | [Acoustic Noise Localization](modules/mobile-acoustics-noise-localization.md) |
| AOI / machine vision | [AOI Machine Vision](modules/aoi-machine-vision.md) |
| Local LLM tool bridge | [LM Studio MCP](modules/lm-studio-mcp.md) |
| Bench wiring | [AD3 Wiring Guide](hardware/ad3-wiring-guide.md) |
| Thermal camera driver | [Seek Thermal Integration](hardware/seek-thermal-integration.md) |

## Repository layout

```
pyontrust/
├── src/pyontrust/        # platform core (gateway, HAL, analysis, instruments)
├── src/mobile_*/         # mobile sensor modules (stereo3d, acoustics, spectroscopy)
├── scripts/              # launchers (.py / .sh / .bat) and build tooling
├── docs/                 # MkDocs site source (see mkdocs.yml)
├── tests/                # test suites per module
├── android-app/          # companion Android helper APKs
└── docker-compose.yml    # containerised lab bench
```

## Building the documentation site

```bash
pip install mkdocs
mkdocs serve            # live-reload at http://127.0.0.1:8000
# or
mkdocs build && python -m http.server -d site 8080
```
