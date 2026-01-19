# pyontrust

## Getting started

## Power consumption test framework

This repo includes a small, hardware-friendly framework to run repeatable power-consumption tests (battery current/voltage over time) and generate artifacts (CSV + JSON summary + Markdown report).

### Quick start (no hardware)

Run the simulated example (creates an `artifacts/` folder):

```powershell
python scripts\power_tests\example_sleep_current.py
```

Run unit tests:

```powershell
python -m unittest discover -s tests -p "test_*.py"
```

### Run profiles (repeatable lab runs)

Profiles are JSON files describing:
- which power meter to use (simulated / CSV file / CSV-producing process)
- which recorders to run (tshark/wireshark, ghidra headless, PCAN, ffmpeg, hackrf, etc.)
- the timed steps and actions (markers, power-mode toggles, one-shot commands)

Example (simulated + dummy recorder):

```powershell
python scripts\power_tests\run_profile.py run scripts\power_tests\example_profile.json --repo-root=.
```

### Minimal GUI

```powershell
python gui_app\power_test_gui\power_test_gui.py
```

### Hardware integration

Adapters are designed to be optional and are safe to import even if the external tools/drivers are not installed.

- PPK2: implemented as a CLI-backed adapter stub (hook up your preferred `nrfutil`/PPK2 tooling).
- AD3: framework provides an AD3/DWF adapter stub (hook up Digilent WaveForms DWF on Windows).
- J-Link: adapter stub (intended to call `JLink.exe` / `JLinkExe`).
- Nordic BLE sniffer: adapter stub (intended to capture to PCAP).
- HackRF: adapter stub (intended to call `hackrf_transfer`).
- Webcam: adapter stub (intended to call `ffmpeg`).

The framework lives in `pyontrust_packages/power_test_framework/`.

Integrations are *optional*:
- Wireshark: use recorder type `wireshark_tshark` (requires `tshark` on PATH)
- Ghidra: use recorder type `ghidra_headless` (requires `analyzeHeadless` on PATH)
- PEAK-CAN: use recorder type `pcan_can` (requires `python-can` + PCAN drivers)

