# Mobile Stereo 3-D Tracking (`mobile_stereo3d`)

Multi-phone stereo rig: two (or more) Android phones act as calibrated cameras,
streaming frames over ADB/Termux to a PC where epipolar geometry recovers 3-D
points and time-series tracking builds trajectories.

Status: **implemented + tested** (29/29 tests green, real device `MWS7N17623000254` verified).

## Package layout

```
src/mobile_stereo3d/
├── controller/          # PC → phone control plane
│   ├── adb_manager.py   # ADBManager: discovery, TCP/IP connect, push/pull, port forward, shell
│   └── termux_bridge.py # TermuxBridge: camera stills (termux-api), audio record, config
├── sync/                # capture alignment
│   ├── frame_stream.py  # Frame / FrameStream (timestamped grabs)
│   └── synchronizer.py  # StreamSynchronizer: timestamp matching w/ tolerance + drift tracking
├── calibration/         # camera model
│   ├── stereo_calib.py  # StereoCalibration dataclass; StereoCalibrator (checkerboard or baseline)
│   └── rectify.py       # StereoRectifier: cv2.stereoRectify maps, Z = Q·1/disp depth
├── reconstruction/      # 2-D → 3-D
│   ├── localization.py  # FeatureLocalizer: ORB extract + ratio-test matching (or marker mode)
│   └── triangulation.py # Triangulator: DLT via cv2.triangulatePoints; disparity depth shortcut
├── tracking/            # time series
│   └── tracker_3d.py    # Tracker3D: NN association + velocity prediction, CSV/JSON/PLY export
└── utils/
    └── visualizer.py    # Visualizer3D: headless matplotlib 3-D plots (PNG)
```

## Data flow

```
phone A ──ADB/Termux──► FrameStream(L) ─┐
                                        ├─ StreamSynchronizer.match() → aligned pairs
phone B ──ADB/Termux──► FrameStream(R) ─┘        (tolerance_ms gate, per-pair delta_ms)
                                                        │
                              FeatureLocalizer.match()  ▼  (ORB + knn ratio test)
                                              pts_left / pts_right
                                                        │
                              Triangulator.triangulate()▼  (DLT, K/R/T from calibration)
                                                  (N,3) world points
                                                        │
                                       Tracker3D.update(pts, t_ms) per frame
                                                        │
                                    CSV / JSON / PLY + Visualizer3D PNG
```

## Calibration strategies

1. **`from_baseline(K_left, D_left, K_right, D_right, baseline_px)`** — phone rigs:
   both phones share (near-)identical intrinsics; extrinsics = right camera offset by
   `baseline_px` along +X of the left frame (R=I). Fast path for a fixed stand.
2. **`calibrate_from_checkerboard(left_views, right_views)`** — full per-camera
   `cv2.calibrateCamera` from checkerboard images; relative pose via solvePnP when both
   cameras see the same board, else baseline fallback.

`StereoCalibration.save()/load()` round-trips everything as JSON (K/D/R/T/image_size).

## Synchronization model

Host-side timestamps at grab completion (`Frame.timestamp_ms`). `match()` pairs each left
frame with its nearest right frame within `tolerance_ms`; per-pair `delta_ms` is exposed so
downstream code can correct residual skew. Drift shows up as growing deltas — assert on it.

## Reconstruction notes

* Triangulation uses full projective matrices: `P1 = [K|0]`, `P2 = K·R | K·T`.
  Correspondence length mismatch → `ValueError`; empty input → `(0,3)`.
* Rectified path: `StereoRectifier` builds `stereoRectify` maps (OpenCV 5.0 requires T as
  3×1 — verified empirically) and depth via the standard `Q` matrix relation.
* Feature matching: ORB + BFMatcher knn with Lowe's ratio test (0.75). Query/train index
  orientation is a classic bug source — fixed & regression-tested.

## Tracking model

Nearest-neighbour association against last position **and** constant-velocity prediction,
gated by `max_link_m`; unassigned points open new tracks; `Track` keeps `(3,)` positions +
timestamps. Exports: CSV (`track_id,t_ms,x,y,z`), JSON (per-track), PLY point cloud
(coloured per track id).

## Tests — `tests/mobile_stereo3d_tests/` (29 tests)

| file | coverage |
|---|---|
| test_calibration.py | from_baseline invariants, save/load round-trip, checkerboard fallback K≈0.9·w, empty-view rejection |
| test_rectify.py | rectified shapes, depth monotonicity, zero-disparity → NaN |
| test_localization.py | ORB extraction on synthetic pattern, correspondence matching (shifted views) |
| test_triangulation.py | single + multi-point round-trip (<1e-4 err), mismatch rejection, empty input |
| test_tracker.py | continuity, two-object separation, gap re-open, CSV/JSON/PLY export |
| test_stream_sync.py | timestamp alignment, out-of-skew rejection, drift deltas, empty inputs |
| test_adb_bridge.py | **real device**: discovery, shell round-trip, push/pull file transfer, Termux probe |

Run: `python -m pytest tests/mobile_stereo3d_tests/` (needs the `stereo3d` extra:
`pip install -e ".[stereo3d]"`).

## Environment gotchas (learned the hard way)

* **OpenCV 5.0**: `cv2.stereoRectify` rejects a flat `(3,)` translation — pass `(3,1)`.
* **PYTHONPATH shadowing**: Hermes kernel injects a foreign site-packages dir whose Pillow
  is broken (`_imaging` missing). Run tests with `PYTHONPATH=` cleared so the venv's own
  PIL/matplotlib win.
* ADB shell returns combined stdout+stderr as one string; failures raise `RuntimeError`.

## Next steps (not yet built)

1. **Multi-phone (>2)**: generalise triangulation to N views (current API is pairwise).
2. **Live streaming**: raw MJPEG over `adb forward` instead of per-still Termux calls
   (latency ~10× better); FrameStream already abstracts the grabber.
3. **ArUco marker mode** in FeatureLocalizer for sub-pixel target centres (`mode="marker"`).
4. Bundle a phone-side helper APK so no Termux:API install is needed on-device.
