# Multi-Phone Acoustic Noise-Source Localization (`mobile_acoustics`)

A matrix of Android phones acts as a distributed microphone array. Each phone
records the same noise source; host-side time-difference-of-arrival (TDOA) and
delay-and-sum beamforming then locate the emitter in 3-D — the same approach
family as the [nGene Beamforming Toolkit](https://www.ngene.co/beamforming-toolkit)
(delay-and-sum power maps + adaptive beamformers), adapted to a phone array.

## Package layout (`src/mobile_acoustics/`)

| module | role |
|---|---|
| `capture.py` | `MicStream` (one phone channel: grabber, sample rate, 3-D mic position) and `MultiMicCapture` (fire all phones, host timestamps) |

`mic_stream_from_termux(bridge, ...)` builds a `MicStream` whose grabber records via `TermuxBridge.record_audio` and decodes the pulled WAV to float64 mono (stdlib `wave`, no extra deps).
| `localization/tdoa.py` | `TDOAEstimator` — GCC-PHAT pairwise TDOA (`pair_tdoa_s`, full `(M,M)` matrix). Verified sample-accurate on broadband bursts; sign convention: `t[i][j] = arrival_i - arrival_j` |
| `localization/localizer.py` | `SourceLocalizer` — solves `c·t[i][j] = \|p-m_i\| - \|p-m_j\|` by damped Gauss-Newton with **multi-start + step capping** (TDOA least-squares has spurious far-field minima; naive GN walks off to km-scale points) |
| `beamforming/beamformer.py` | `DelayAndSumBeamformer` — coherent power map over an `AcousticGrid`; peak cell ≈ source. nGene-style D&S, numpy-only (no scipy) |
| `beamforming/mvdr.py` | `MVDRBeamformer` — adaptive Capon beamformer: per-bin cross-spectral matrix R with diagonal loading, power P(p)=1/(aᴴR⁻¹a). Nulls strong interferers (beats D&S by ~3.6 dB contrast in the two-tone test) |
| `calibration/clock_skew.py` | `ClockSkewCalibrator` — shared-beep per-phone clock-offset calibration (cross-correlation lags minus geometric path difference); `apply_skew_correction` removes offsets from TDOA matrices; `beep_template` generates the calibration tone |

## Verified behaviour (synthetic round-trips, 4-phone array, ~2 m range)

* GCC-PHAT pairwise TDOA: **≤ ±0.6 samples** error per pair on broadband bursts
  (stationary tones/chirps are inherently ambiguous for PHAT — use real machine noise).
* `SourceLocalizer`: converges to the true emitter; residuals ≈ measurement noise.
* Beamformer power-map peak within grid resolution of the source.

## Tests (`tests/mobile_acoustics_tests/`, 27 tests)

| file | coverage |
|---|---|
| test_tdoa.py | sign/magnitude vs known delay, matrix antisymmetry, geometry match, short-input rejection |
| test_source_localizer.py | position tolerance, constraint residuals, bearing accuracy, single-mic rejection |
| test_beamforming.py | peak near source, power-map shape/finite, single-mic rejection |
| test_mvdr.py | fine-grid localization (<0.3 m), interferer contrast beats D&S by ≥1 dB (observed ~3.6 dB) |
| test_clock_skew.py | lag sign convention, beep tone purity, skew recovery to <5e-5 s (~2 samples @48 kHz), TDOA correction antisymmetry |
| test_capture.py | capture dict contract, <2-channel rejection |

Run: `python -m pytest tests/mobile_acoustics_tests/` (extra: `pip install -e ".[acoustics]"`).

## Gotchas learned the hard way

* **GCC-PHAT FFT length**: `irfft(Rxy_phat, n=2n)` silently *doubles* peak lags
  (frequency-domain truncation). Use `n=n` and map circular indices properly.
* **TDOA far-field minima**: cap GN steps + multi-start; otherwise the solver
  converges to a point kilometres away with "small" residuals.
* **Test signals**: pure tones/chirps give ambiguous PHAT peaks — broadband noise
  bursts are the gold standard (and match real machine-noise use cases).

## Next steps

Done in this pass:

1. ~~Wire capture to Termux~~ — `mic_stream_from_termux(bridge, ...)` + WAV decode (`capture.py`).
2. ~~MVDR adaptive beamformer~~ — `beamforming/mvdr.py` (Capon, diagonal loading 0.1 default).
4. ~~Clock-skew calibration~~ — `calibration/clock_skew.py` (shared beep → per-channel offsets → TDOA correction).

Still open:

3. Time-varying tracking: slide a window over continuous recordings, feed per-frame
   localizations into the existing `Tracker3D`.
5. LCMV / robust-CMVDR variants and real-device skew measurements (needs 2+ phones + shared beep playback via Termux).
