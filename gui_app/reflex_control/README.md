# Reflex Instrument Control GUI

Minimal Reflex UI to configure instruments/recorders and run a quick `PowerTestRunner` capture.

## Why a separate venv?

Installing Reflex into the same Python environment as other lab tooling can create dependency conflicts.
In this repo we saw `pip install reflex` upgrade:

- `wrapt` to `2.x` (but `python-can` requires `wrapt~=1.10`)
- `click` to `8.3.x` (but some tooling like `spsdk` may require `click<8.3` on Python 3.10)

To avoid breaking existing instrument stacks, install the GUI dependencies in a dedicated virtual environment.

## Run

From repo root (recommended: create a venv for the GUI):

```powershell
python -m venv .venv-gui
.\.venv-gui\Scripts\python -m pip install -U pip
.\.venv-gui\Scripts\python -m pip install -r scripts\requirements.txt
.\.venv-gui\Scripts\python -m pip install -r gui_app\reflex_control\requirements.txt
cd gui_app\reflex_control
.\.venv-gui\Scripts\reflex run
```

Then open the URL Reflex prints (typically `http://localhost:3000`).

## If you already installed Reflex into your main env

If your existing environment is now reporting dependency conflicts for `python-can` or `spsdk`, you can either:

1) Preferable: stop using that env for the GUI, and use the `.venv-gui` approach above.

2) Or repair the environment by reinstalling compatible versions (adjust if you have different constraints):

```powershell
python -m pip install --upgrade --force-reinstall "wrapt<2,>=1.10" "click<8.3"
```

## Notes

- AD3/DWF: ensure WaveForms is installed (Windows) or `externals/WaveformSDK_linux/usr/lib/libdwf.so` is present (Linux). You can also set `DWF_LIB_PATH`.
- Webcam on Windows requires a DirectShow camera name in **Input device**.
- HackRF/Webcam recorders are optional and will auto-skip if the tool is missing.
