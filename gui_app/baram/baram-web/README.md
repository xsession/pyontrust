# Baram-Web

A modern web-based frontend for BaramFlow CFD simulation, replacing the PySide6/Qt desktop UI with a Flask + Vanilla JS stack.

## Architecture

```
baram-web/
├── run.py                 # CLI entry point (--port, --host, --open)
├── server.py              # Flask backend with REST + WebSocket endpoints
├── domain/
│   ├── project_manager.py # Project lifecycle (replaces App singleton)
│   ├── solver_monitor.py  # Solver log tailing + residual parsing
│   └── cfd_schema.py      # CoreDB → JSON serialization
├── web/
│   ├── index.html         # SPA shell (Catppuccin Mocha theme)
│   └── main.js            # All frontend logic (~600 lines, no build step)
├── tests/
│   ├── conftest.py        # pytest fixtures
│   └── test_api.py        # API smoke tests
├── requirements.txt       # Python dependencies
├── start.bat              # Windows quick-launch
├── Dockerfile             # Container deployment
└── VERSION                # Semver
```

## Quick Start

### Windows
```batch
start.bat
```

### Manual
```bash
python -m venv .venv
.venv\Scripts\activate    # or: source .venv/bin/activate
pip install -r requirements.txt
python run.py --open
```

### Docker
```bash
docker build -t baram-web .
docker run -p 5000:5000 -v /path/to/projects:/projects baram-web
```

## Key Design Decisions

| Desktop (Qt)               | Web (Flask+JS)              |
|----------------------------|-----------------------------|
| PySide6 widgets + .ui      | Vanilla HTML + CSS          |
| Qt signals                 | REST polling + WebSocket    |
| pyqtgraph residual plots   | Chart.js (log scale)        |
| VTK 3D viewport            | Three.js placeholder        |
| `coredb.CoreDB()` singleton| Reused as-is (server-side)  |
| `CaseGenerator` async      | Wrapped in `asyncio.run()`  |
| `Solver` + MPI launch      | Reused as-is                |

## API Reference

See `REFACTOR_STACK_TEMPLATE.md §7` for the full 40+ endpoint reference.

Core endpoints:
- `GET  /api/project`          — current project summary
- `POST /api/project/open`     — open existing project
- `GET  /api/pages/general`    — general settings
- `PUT  /api/pages/general`    — save general settings
- `POST /api/solver/start`     — launch OpenFOAM solver
- `WS   /ws/solver-log`        — live log streaming

## Testing
```bash
pytest tests/ -v
```

## License

Same as the parent Baram project.
