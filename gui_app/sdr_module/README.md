# pyontrust-sdr-module

Embeddable SDR flowgraph module (GNU Radio–like) with a NiceGUI UI.

## Quick start (Simulated)

```powershell
python -m venv .venv-sdr
.\.venv-sdr\Scripts\python -m pip install -U pip
.\.venv-sdr\Scripts\python -m pip install -e sdr_module
.\.venv-sdr\Scripts\python sdr_module\examples\run_standalone.py
```

## HackRF (via SoapySDR)

This module uses **SoapySDR** as the initial HackRF integration to keep the HAL portable and make future devices (RTL-SDR, etc.) pluggable.

### Windows (notes)
- Install SoapySDR runtime (DLLs) and the HackRF module.
- Ensure SoapySDR DLLs are on `PATH`.
- Then install Python bindings:

```powershell
.\.venv-sdr\Scripts\python -m pip install -e sdr_module
.\.venv-sdr\Scripts\python -m pip install "SoapySDR>=0.8.1"
```

### Linux (notes)
- Install `soapysdr`, `soapysdr-module-hackrf`, and `hackrf` packages via your distro.
- Then `pip install SoapySDR` (or use system python bindings).

## Embedding into an existing NiceGUI app

See `sdr_module/examples/embed_in_existing_app.py`.
