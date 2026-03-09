Parallel Lux Measurement
========================

.. module:: pyontrust.analysis.lux_measurement
   :synopsis: Parallel lux measurement — webcam + Android light sensor.

.. versionadded:: 2026.3.0

Overview
--------

The **parallel lux measurement** module provides a complete pipeline for
simultaneously measuring ambient illuminance from two independent sources:

1. **USB Webcam** — estimates lux from V-channel (HSV) brightness using
   a linear calibration model.
2. **Android Light Sensor** — reads the hardware ambient-light sensor
   (TYPE_LIGHT) via ADB or the simulated driver.

A controlled step-change is created by cycling the Android phone's
flashlight (torch) ON and OFF, allowing cross-validation between the
two sensors via Pearson correlation and cross-correlation lag estimation.

Architecture
~~~~~~~~~~~~

.. code-block:: text

   ┌────────────────┐       ┌──────────────┐
   │  Android Phone │       │  USB Webcam  │
   │  ┌───────────┐ │       │              │
   │  │  Torch    │ │       │  V-channel   │
   │  │  (Flash)  │ ├──LED──│  brightness  │
   │  └───────────┘ │       │  → lux est.  │
   │  ┌───────────┐ │       └──────┬───────┘
   │  │  Light    │ │              │
   │  │  Sensor   │ │        webcam_lux[]
   │  └─────┬─────┘ │              │
   │        │       │              │
   └────────┼───────┘              │
            │                      │
     android_lux[]                 │
            │                      │
            ▼                      ▼
   ┌──────────────────────────────────────┐
   │  analyse_parallel_lux()              │
   │  · ON/OFF classification             │
   │  · Per-source Δlux                   │
   │  · Pearson correlation               │
   │  · Cross-correlation lag             │
   └──────────────────────────────────────┘
            │
            ▼
        LuxResult


Algorithm
---------

The measurement proceeds in five stages:

1. **Open Devices** — Webcam via ``cv2.VideoCapture`` (DSHOW on Windows),
   Android sensors via ``AndroidSensorInstrument``.

2. **Parallel Capture** — Two ``threading.Thread``\s run concurrently:

   - **Webcam thread**: grabs frames at ``target_fps``, computes mean
     V-channel brightness via ``frame_to_brightness()``.
   - **Android thread**: reads ``read_light()`` at ``android_sample_rate_hz``.

   Both threads record timestamps relative to a shared ``time.perf_counter()``
   origin.

3. **Torch Cycling** — The main thread controls the torch:

   - Wait ``pre_capture_s`` for baseline.
   - For each cycle: toggle ON → wait ``torch_on_s`` → toggle OFF →
     wait ``torch_off_s``.
   - All transitions are logged with timestamps.

4. **Stop & Collect** — ``threading.Event.set()`` signals both threads to
   exit. Lists are collected from thread-local buffers.

5. **Analyse** — ``analyse_parallel_lux()`` performs:

   a. Convert webcam brightness to lux via ``brightness_to_lux()``.
   b. Classify every sample as ON or OFF using ``classify_on_off_regions()``.
   c. Compute per-source statistics: mean ON, mean OFF, Δlux.
   d. Resample both series to a uniform 10 Hz grid.
   e. Compute Pearson correlation coefficient.
   f. Compute cross-correlation lag (peak of ``np.correlate``).


Data Classes
------------

LuxCaptureConfig
~~~~~~~~~~~~~~~~

.. autoclass:: pyontrust.analysis.lux_measurement.LuxCaptureConfig
   :members:

+---------------------------+--------+----------+------------------------------------------+
| Field                     | Type   | Default  | Description                              |
+===========================+========+==========+==========================================+
| ``device_index``          | int    | 0        | Webcam index (0 = default)               |
+---------------------------+--------+----------+------------------------------------------+
| ``width`` / ``height``    | int    | 640/480  | Capture resolution                       |
+---------------------------+--------+----------+------------------------------------------+
| ``target_fps``            | float  | 30.0     | Frame rate target                        |
+---------------------------+--------+----------+------------------------------------------+
| ``warmup_frames``         | int    | 10       | Frames to discard (auto-exposure)        |
+---------------------------+--------+----------+------------------------------------------+
| ``roi``                   | tuple  | None     | (x, y, w, h) crop or full frame          |
+---------------------------+--------+----------+------------------------------------------+
| ``torch_on_s``            | float  | 3.0      | Seconds torch stays ON per cycle         |
+---------------------------+--------+----------+------------------------------------------+
| ``torch_off_s``           | float  | 3.0      | Seconds torch stays OFF per cycle        |
+---------------------------+--------+----------+------------------------------------------+
| ``n_cycles``              | int    | 3        | Number of ON/OFF cycles                  |
+---------------------------+--------+----------+------------------------------------------+
| ``pre_capture_s``         | float  | 1.0      | Baseline capture before first toggle     |
+---------------------------+--------+----------+------------------------------------------+
| ``android_mode``          | str    | simulated| ``simulated``, ``adb``, ``adb_bridge``   |
+---------------------------+--------+----------+------------------------------------------+
| ``android_sample_rate_hz``| float  | 10.0     | Phone sensor polling rate                |
+---------------------------+--------+----------+------------------------------------------+
| ``lux_scale``             | float  | 2.0      | Brightness → lux linear scale            |
+---------------------------+--------+----------+------------------------------------------+
| ``lux_offset``            | float  | 0.0      | Brightness → lux linear offset           |
+---------------------------+--------+----------+------------------------------------------+

LuxResult
~~~~~~~~~

.. autoclass:: pyontrust.analysis.lux_measurement.LuxResult
   :members:

+--------------------------+-----------------+-----------------------------------------+
| Field                    | Type            | Description                             |
+==========================+=================+=========================================+
| ``ok``                   | bool            | Whether measurement succeeded           |
+--------------------------+-----------------+-----------------------------------------+
| ``error``                | str | None      | Error message if ``ok=False``           |
+--------------------------+-----------------+-----------------------------------------+
| ``webcam_timestamps``    | list[float]     | Webcam frame timestamps (s)             |
+--------------------------+-----------------+-----------------------------------------+
| ``webcam_lux``           | list[float]     | Estimated lux from webcam               |
+--------------------------+-----------------+-----------------------------------------+
| ``webcam_brightness``    | list[float]     | Raw V-channel brightness (0–255)        |
+--------------------------+-----------------+-----------------------------------------+
| ``android_timestamps``   | list[float]     | Phone sensor timestamps (s)             |
+--------------------------+-----------------+-----------------------------------------+
| ``android_lux``          | list[float]     | Phone sensor lux readings               |
+--------------------------+-----------------+-----------------------------------------+
| ``torch_events``         | list[dict]      | ``[{"t": float, "state": "ON"/"OFF"}]`` |
+--------------------------+-----------------+-----------------------------------------+
| ``webcam_lux_mean_on``   | float | None    | Mean webcam lux during torch ON         |
+--------------------------+-----------------+-----------------------------------------+
| ``webcam_lux_mean_off``  | float | None    | Mean webcam lux during torch OFF        |
+--------------------------+-----------------+-----------------------------------------+
| ``webcam_lux_delta``     | float | None    | ON − OFF difference (webcam)            |
+--------------------------+-----------------+-----------------------------------------+
| ``android_lux_mean_on``  | float | None    | Mean phone lux during torch ON          |
+--------------------------+-----------------+-----------------------------------------+
| ``android_lux_mean_off`` | float | None    | Mean phone lux during torch OFF         |
+--------------------------+-----------------+-----------------------------------------+
| ``android_lux_delta``    | float | None    | ON − OFF difference (phone)             |
+--------------------------+-----------------+-----------------------------------------+
| ``correlation``          | float | None    | Pearson correlation between series      |
+--------------------------+-----------------+-----------------------------------------+
| ``lag_ms``               | float | None    | Cross-correlation lag (ms)              |
+--------------------------+-----------------+-----------------------------------------+


REST API
--------

``POST /diag/api/lux_measure``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Start a parallel lux measurement. The endpoint spawns webcam and Android
sensor threads, cycles the torch, analyses the data, and generates an
HTML report.

**Request Body** (JSON):

.. code-block:: json

   {
     "device_index": 0,
     "width": 640,
     "height": 480,
     "fps": 30.0,
     "torch_on_s": 3.0,
     "torch_off_s": 3.0,
     "n_cycles": 3,
     "pre_capture_s": 1.0,
     "android_mode": "simulated",
     "android_rate_hz": 10.0,
     "lux_scale": 2.0,
     "lux_offset": 0.0
   }

**Response** (JSON):

.. code-block:: json

   {
     "result": {
       "ok": true,
       "webcam_lux_delta": 345.2,
       "android_lux_delta": 720.5,
       "correlation": 0.9823,
       "lag_ms": 12.3,
       "..."
     },
     "report_file": "C:\\GIT\\pyontrust\\test_reports\\lux_parallel_20260309_120000.html",
     "report_url": "/diag/api/reports/lux_parallel_20260309_120000.html"
   }


FlowLab Blocks
--------------

Two new blocks are added to the FlowLab visual dataflow editor:

``android_torch``
~~~~~~~~~~~~~~~~~

Toggles the Android phone's flashlight on or off.

+----------+---------+------+----------------------------------------------+
| Port     | Dir     | Type | Description                                  |
+==========+=========+======+==============================================+
| ok       | output  | bool | ``True`` if command succeeded                |
+----------+---------+------+----------------------------------------------+
| state    | output  | str  | ``"on"`` or ``"off"``                        |
+----------+---------+------+----------------------------------------------+

Parameters: ``mode`` (simulated/adb), ``state`` (on/off).

``lux_measure``
~~~~~~~~~~~~~~~

Runs the full parallel lux measurement pipeline.

+---------------+---------+------+------------------------------------------+
| Port          | Dir     | Type | Description                              |
+===============+=========+======+==========================================+
| result        | output  | dict | Full ``LuxResult.summary()``             |
+---------------+---------+------+------------------------------------------+
| webcam_lux    | output  | list | Webcam estimated lux time-series         |
+---------------+---------+------+------------------------------------------+
| android_lux   | output  | list | Phone sensor lux time-series             |
+---------------+---------+------+------------------------------------------+
| correlation   | output  | num  | Pearson correlation coefficient          |
+---------------+---------+------+------------------------------------------+

Parameters: ``android_mode``, ``n_cycles``, ``torch_on_s``, ``torch_off_s``.


Calibration
-----------

The webcam-to-lux mapping uses a simple linear model:

.. math::

   \text{lux} = \text{brightness} \times \text{scale} + \text{offset}

where *brightness* is the mean V-channel value (0–255) of the captured
frame. For accurate absolute lux values, calibrate ``lux_scale`` and
``lux_offset`` against a reference lux meter:

1. Place the webcam in a known illuminance environment.
2. Capture frames and note the mean brightness.
3. Fit a linear model to at least 3 brightness–lux pairs.

The default ``scale=2.0, offset=0.0`` maps 0–255 → 0–510 lux, which
is a reasonable indoor range.


Performance
-----------

+---------------------+--------+------------------------------------------+
| Metric              | Value  | Notes                                    |
+=====================+========+==========================================+
| Webcam capture      | 25–30  | With DSHOW backend (Windows)             |
| FPS                 | fps    |                                          |
+---------------------+--------+------------------------------------------+
| Android sensor      | 10 Hz  | Configurable, phone-dependent            |
| rate                |        |                                          |
+---------------------+--------+------------------------------------------+
| Typical measurement | 20 s   | 3 cycles × (3s ON + 3s OFF) + 1s pre    |
| duration            |        |                                          |
+---------------------+--------+------------------------------------------+
| Report size         | 20–35  | Self-contained HTML with SVG charts      |
|                     | KB     |                                          |
+---------------------+--------+------------------------------------------+
| Correlation compute | < 10   | Resampled to 10 Hz, ``numpy.corrcoef``   |
|                     | ms     |                                          |
+---------------------+--------+------------------------------------------+


Limitations
-----------

* Webcam-to-lux calibration is approximate — the linear model does not
  account for non-linear camera response curves or auto-exposure.
* Torch control via ADB is device-dependent. Some phones require a
  helper APK or Termux for reliable flashlight control.
* Android light sensor accuracy varies between devices (≈ ±15%).
* The cross-correlation lag estimate assumes both sensors observe the
  same light event — directional placement matters.


Test Coverage
-------------

The module has **40+** unit tests across 8 test classes:

- ``TestFrameToBrightness`` — V-channel extraction, ROI crop, gradient
- ``TestBrightnessToLux`` — linear scaling, clamping, edge cases
- ``TestSimulatedTorch`` — state tracking, event logging
- ``TestClassifyOnOff`` — region classification with multiple cycles
- ``TestAnalyseParallelLux`` — ON/OFF delta, correlation, lag, errors
- ``TestLuxCaptureConfig`` — frozen dataclass, custom values
- ``TestLuxResult`` — summary serialisation, error handling
- ``TestLuxReport`` — HTML report generation, charts, embedded JSON
- ``TestDiagnosticLuxRoutes`` — Flask endpoint integration
- ``TestEndToEndSynthetic`` — full pipeline synthetic test
- ``TestRealHardwareLuxMeasure`` — live webcam + simulated phone (guarded)


Changelog
---------

.. list-table::
   :header-rows: 1

   * - Version
     - Change
   * - 2026.3.0
     - Initial implementation — parallel webcam + Android lux measurement
       with torch cycling, correlation analysis, HTML reports, FlowLab
       blocks (``android_torch``, ``lux_measure``), and REST API.
