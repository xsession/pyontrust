# Focus Stacking & Depth Recovery (native)

Pure-software multi-focus imaging for high-resolution depth of field — no
external programs. Built on OpenCV + NumPy only, so it runs anywhere pyontrust
runs (this Linux lab host included).

## What you get

| Module | Capability |
|---|---|
| `pyontrust.analysis.focus_stacking` | capture schedule, ORB registration, sharpness-weighted composite (`stack_images`, `FocusStacker`) |
| `pyontrust.analysis.focus_depth` | per-pixel best-focus index → **metric height map (µm)** + 16-bit PNG + binary STL mesh |
| `pyontrust.analysis.stereo` | stereo pair → SGBM disparity → **metric depth (m) + 3-D point cloud** |

## Depth from focus (microscopy / macro AOI / small-part scanning)

The stacker already composites a sharp image; the depth module recovers *which*
frame was sharpest at each pixel and turns that index into physical height:

```python
from pyontrust.analysis.focus_depth import FocusDepthAnalyzer

analyzer = FocusDepthAnalyzer(step_um=2.0, z0_um=100.0)   # Z-stage step + start height
res = analyzer.run(frames, out_dir="out", export=("png", "stl"))

res.height_um            # float32 (H, W) surface height in micrometres
res.focus_index_map      # which frame won at each pixel
res.confidence_map       # 0..1 selection margin (low = ambiguous depth)
res.exports              # {"heightmap_png": ..., "mesh_stl": ...}
```

Requirements for metric accuracy: constant stage step between frames, constant
exposure/gain, and the object moving with the stage (or a fixed Z-axis). The STL
is spec-compliant binary (50-byte records) and opens in any CAD/3-D viewer.

## Stereo camera analysis

For two calibrated cameras (or an already-rectified pair):

```python
from pyontrust.analysis.stereo import StereoAnalyzer, StereoConfig

cfg = StereoConfig(fx=800, fy=800, cx=320, cy=240, baseline_m=0.12)  # metres
res = StereoAnalyzer(cfg).run(left_bgr, right_bgr)
# or with calibration: .run(l, r, K1=K1, K2=K2, R=R, T=T)

float(np.nanmedian(res.depth_m))   # scene depth in metres
res.points[120, 320]               # (x, y, z) camera-frame point cloud
```

Depth follows the pinhole model `Z = fx · baseline / disparity`. Set
`num_disp` above your closest expected object (in pixels).

## Choosing between them

* **Single camera + Z-stage** → focus stacking/depth: finest detail, µm-level.
* **Two cameras, no stage** → stereo: fast whole-scene shape, mm-level.
* Both can feed the same AOI checks — depth maps are just (H, W) float arrays.


## lab_bench.json / profile config

```json
{
  "focus_stack": {
    "n_frames": 16,
    "window": 9,
    "gamma": 2.0,
    "depth": { "step_um": 2.0, "z0_um": 0.0 },
    "stereo": {
      "fx": 800, "fy": 800, "cx": 320, "cy": 240,
      "baseline_m": 0.12, "num_disp": 64, "block_size": 7
    }
  }
}
```

## Notes & limitations

* Sharpness-weighted compositing assumes roughly constant illumination between
  frames — keep exposure/gain locked (the capture path already does this).
* Stereo accuracy is limited by texture: matte/featureless surfaces need a
  speckle pattern or structured light. SGBM is fast but not as robust as
  learned methods; for production gauging, validate against a known artefact.
* Depth-from-focus needs at least ~5–10 frames across the tolerance band for
  smooth height maps; more frames = finer depth resolution.

