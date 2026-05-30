# Demo Dashboard

Generated from `Demo Interface` using the `gui-app` scaffold.

This scaffold embeds the generated Python driver and exposes a small pyontrust-native Flask dashboard.

## Run

```bash
python main.py --port 5410
```

Then open `http://127.0.0.1:5410/demo-dashboard`.

## Build

Install the optional build tools in the pyontrust environment, then run:

```bash
python build_install.py
```

Set `BUILD_BACKEND=nuitka` if you want a Nuitka onefile build instead of the default PyInstaller path.

## API

- `GET /demo-dashboard/api/health`
- `GET /demo-dashboard/api/summary`
- `GET /demo-dashboard/api/metadata`
- `GET /demo-dashboard/api/methods`