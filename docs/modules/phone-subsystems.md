# Phone Subsystem Access & Automation

Full access to a phone's subsystems over ADB — control **and** measured values,
no extra drivers. Everything lives in `pyontrust.phone` (controllers) and
`pyontrust.analysis.auto_depth` (the automated depth pipeline).

## One object for the whole phone

```python
from pyontrust.phone import PhoneSubsystems

ph = PhoneSubsystems()                 # first adb device
ph = PhoneSubsystems(serial="ABC123")  # or pin a specific device

ph.info()        # {'model': ..., 'brand': ..., 'sdk': ...}
ph.snapshot()    # key measured values from every subsystem (never raises)
```

## Subsystem controllers

| Controller | Control | Measured values |
|---|---|---|
| `ph.bluetooth` | enable / disable | adapter state, paired devices |
| `ph.gsm` | airplane mode, data radio, AT passthrough (`at("CIMI")`) | SIM slot states, multi-RAT signal (NR/LTE/WCDMA/GSM), network registration |
| `ph.nfc` | enable / disable | adapter state |
| `ph.audio` | per-stream volume set, mute | volumes of all streams, active routing devices |
| `ph.vibration` | vibrate(ms) / stop (helper-APK broadcast → shell fallback) | — |
| `ph.cameras` | — (capture via focus-stacking backends) | camera-island enumeration: id + facing per physical camera, device state, supported resolutions |
| `ph.touchscreen` | tap(x,y), swipe(...) | raw touch events (`getevent -l`) as structured `TouchEvent`s for measurement |
| `ph.peripherals` | — | battery (level/status/voltage/temperature), sensor list + reads, storage, network interfaces, USB state, thermal zones |

## Automated depth pipeline

```python
from pyontrust.analysis.auto_depth import AutoDepthPipeline

pipe = AutoDepthPipeline(n_frames=16, step_um=2.0)   # Z-stage step in um
rep = pipe.run()                    # capture (ADB helper APK) -> stack -> depth -> report
# or feed frames from any source:
rep = pipe.run(frames=my_list)

rep.height_um       # metric height map (um)
rep.stacked_image   # sharp composite
rep.report_path     # JSON: stats + export paths
```

The JSON report contains frame count, step size, min/max/mean/std of the
height map, mean confidence and elapsed time — ready for lab_bench.json or a
test-report pipeline.


## Notes & vendor caveats

* `svc` / `cmd` commands are the standard ADB control surface, but some OEM ROMs
  (Huawei/HarmonyOS in particular) restrict parts of it — every controller is
  best-effort and returns raw output so you can adapt.
* AT passthrough (`ph.gsm.at(...)`) needs root on most devices; without root
  use the dumpsys-based measurements instead.
* Vibration uses a helper-APK broadcast first (reliable), then falls back to
  `input vibrate` where the ROM supports it.
* Touchscreen event capture reads `/dev/input/event*` via `getevent -l`;
  permissions are fine over adb shell on virtually all devices.

## Test coverage

The whole layer is tested without hardware: a fake ADB transport feeds
realistic `dumpsys`/`media volume`/`sensors.list` outputs and every parser +
control path is asserted (`tests/phone/test_subsystems.py`, 25 tests). The
automation pipeline is covered by `tests/aoi_tests/test_auto_depth.py`.

