# Getting Started

## Prerequisites

| Requirement | Version | Notes |
|---|---|---|
| Python | ≥ 3.10 (3.12 recommended) | core is pure Python |
| Git | any | for source checkout |
| ADB | platform-tools | only for mobile-sensor modules |
| Docker + Compose | v2+ | optional, containerised bench |

## Install from source

```bash
git clone <repo-url> pyontrust && cd pyontrust
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -e ".[gui]"            # gateway + web UI (Flask)
# optional extras, as needed:
pip install -e ".[analysis]"       # numpy/pandas/scipy/matplotlib pipelines
pip install -e ".[aoi]"            # OpenCV machine vision
pip install -e ".[thermal]"        # Seek Thermal support
```

The core package has **zero mandatory dependencies**; every instrument
backend is an opt-in extra.

## Run the Lab Bench

Three equivalent launchers are provided in `scripts/`:

| Launcher | Platform | Command |
|---|---|---|
| `start_lab_bench.py` | any | `python scripts/start_lab_bench.py --port 5200` |
| `start_lab_bench.sh` | Linux/macOS | `./scripts/start_lab_bench.sh --port 5200` |
| `start_lab_bench.bat` | Windows | `scripts\start_lab_bench.bat --port 8080` |

Common options: `--host`, `--port`, `--artifacts <dir>`, `--bench <json>`,
`--debug`, `--no-browser`. Environment overrides: `PYONTRUST_HOST`,
`PYONTRUST_PORT`, `PYONTRUST_ARTIFACTS`, `PYONTRUST_BENCH`,
`PYONTRUST_LOG_LEVEL`.

The gateway binds to `127.0.0.1:5200` by default and opens your browser
automatically (disable with `--no-browser`).

## Run with Docker Compose

```bash
docker compose up --build -d
# web UI → http://localhost:5200
docker compose logs -f lab-bench
```

The compose file mounts `./artifacts` for result storage and passes the USB
device bus through so instrument drivers (Digilent, PCAN, Seek Thermal, …)
work inside the container. For cameras add `/dev/video*` to the `devices:`
list in `docker-compose.yml`.

> **USB permissions:** on Linux hosts, grant your user access once:
> ```bash
> sudo usermod -aG plugdev $USER        # or install vendor udev rules
> ```
> Vendor-specific devices (e.g. Seek Thermal) may need a per-VID rule — see
> [Seek Thermal Integration](hardware/seek-thermal-integration.md).

## Smoke test

```bash
python - <<'EOF'
from pyontrust.gateway.app import create_app
app = create_app(artifacts_root="/tmp/pyontrust-artifacts")
print("gateway OK:", app.name)
EOF
```

## Troubleshooting

| Symptom | Fix |
|---|---|
| `Cannot import pyontrust.gateway` | `pip install -e ".[gui]"` in the active venv |
| Port already in use | `--port 8080` or set `PYONTRUST_PORT` |
| USB device: *Access denied* | udev rule / group membership (see hardware docs) |
| Camera black frames | check slit/lens, try manual exposure via V4L2 |
