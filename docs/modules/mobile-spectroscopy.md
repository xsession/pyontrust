# Multi-Phone Spectroscopy (`mobile_spectroscopy`)

A phone camera + diffraction grating slit acts as a bench spectrometer. Each
image column is one wavelength bin; the host-side pipeline extracts, corrects,
smooths, calibrates and peak-detects — an independent Python port of the
**Theremino Spectrometer V5.0** processing chain (VB.NET WinForms, used as the
design reference).

## Attribution

Algorithmic design follows Theremino Spectrometer V5.0 (© Theremino project;
upstream is GPL-3.0 open source — see https://www.theremino.com and the
`Theremino_Spectrometer_V5.0_WithSources.zip` distribution). This package is an
independent reimplementation of the documented pipeline in numpy; no VB.NET
code was copied. Keep this attribution when redistributing.

## Package layout (`src/mobile_spectroscopy/`)

| module | role (Theremino source it ports) |
|---|---|
| `pipeline.py :: extract_column_samples` | `Bitmap_To_ReceivedSamples` — per-column RGB-weighted row sums → one raw sample/bin |
| `pipeline.py :: correct_for_irradiance` | `Module_IrradianceCoeffs.vb :: CorrectForIrradiance` — interpolated (nm→coeff) response flattening |
| `pipeline.py` scaling + dark level | `Spectrometer_ProcessReceivedSamples` (`ScaleCoeff_to65536`, `ValueMinSubtractor`) |
| `pipeline.py` averaging | `Array_AverageFiltered` / `Spectrometer_AverageCounter` — N-frame accumulation with running average |
| `pipeline.py :: spatial_filter` | `Add_SpatialFilter` — two-pass symmetric exponential smoothing (KFilter) |
| `pipeline.py :: resample_to_nm_grid` | `Array_UpDownFiltered_To_Array_Calibrated` + `Calib_NmToBin` — uniform nm grid via piecewise-linear calibration |
| `calibration.py` | `Module_Calibrations.vb` — `Interpolate`, Calib_BIN/Calib_NM, AddTrimmingPoint/RemoveTrimmingPoint, ArrayToString/ArrayFromString (pipe-separated persistence) |
| `pipeline.py :: subtract_background` | `AddBackground` — background subtraction clipped at 0 |
| `peaks.py` | `MarkAllPeaks` + dip marking — local extrema with >1%-of-max prominence and ±delta dominance window |
| `known_lines.py` | NIST reference emission lines (Hg/Ar/Ne/Na/He) for calibration matching |

## Verified behaviour (`tests/mobile_spectroscopy_tests/`, 21 tests, all green)

* Column extraction matches hand-computed RGB-weighted sums.
* Spatial filter: white-noise std reduced ~46% (0.99→0.54), constants pass
  through exactly, step response interior exact at 0.5.
* Calibration: piecewise-linear both directions, clamped out-of-range,
  add/remove points keep bins sorted, string round-trip lossless.
* Irradiance correction matches `np.interp` on the (nm→coeff) table.
* **Round trip**: synthetic 8-bit slit image with two emission lines → full
  pipeline → both lines detected within ±3 nm of their true wavelengths.

## Usage

```python
import numpy as np
from mobile_spectroscopy import WavelengthCalibration, SpectrometerPipeline, find_peaks, nearest_line

# calibration: mark known lines on the raw spectrum (e.g. Hg 435.83 / 546.07 nm)
calib = WavelengthCalibration(bins=[120.0, 340.0], nms=[435.83, 546.07])

pipe = SpectrometerPipeline(calib, nm_min=380, nm_max=750, n_bins=512, average_n=10)
spec = pipe.process_image(slit_img)          # (H,W,3) uint8 from TermuxBridge.capture_still
nm_axis = np.linspace(380, 750, 512)

for i, v in find_peaks(spec, delta=4):
    nm = float(nm_axis[i])
    line, dist = nearest_line(nm, lamp="mercury")
    print(f"{nm:7.2f} nm  (nearest Hg {line:.2f}, Δ{dist:.2f})")
```

Capture path on Android: `mobile_stereo3d.controller.TermuxBridge.capture_still`
→ pull the slit image → feed to `SpectrometerPipeline.process_image`.

## Gotchas / notes

* **8-bit quantization** creates shoulder ripples on sharp lines; use a wider
  peak-detection window (`delta`) or higher bit-depth capture.
* The spatial filter seeds each pass with the first sample (no startup
  transient) — constants pass through exactly, unlike a zero-seeded IIR.
* `find_peaks` prominence is relative to the spectrum max (>1%), matching
  Theremino; sub-1% features are intentionally ignored.

## Next steps

1. Real-device slit capture: grating + slit rig on the phone camera, dark-frame
   and background subtraction from live captures.
2. Irradiance response table from a calibrated reference lamp (per-nm coeffs).
3. Multi-phone spectral averaging / cross-checking for stability.
