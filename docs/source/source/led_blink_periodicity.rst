LED Blink Periodicity Measurement
===================================

.. contents:: Table of Contents
   :depth: 3
   :local:

Overview
--------

The LED blink periodicity measurement subsystem enables automated
verification of LED blink rates on embedded devices under test (DUT).
A USB webcam captures video of the target LED, the red channel is
isolated via HSV colour masking, and the blink frequency is computed
using spectral analysis.

This capability is part of the **pyontrust** enterprise test platform
and integrates with:

- **Hardware Discovery** — automatic webcam detection
- **Diagnostic Blueprint** — REST API for on-demand measurements
- **HTML Report Generator** — enterprise-grade, self-contained reports
- **FlowLab** — visual dataflow block for LED blink analysis

Architecture
~~~~~~~~~~~~

.. code-block:: text

   ┌──────────────┐    ┌───────────────────┐    ┌───────────────────┐
   │  USB Webcam  │───▶│  capture_led_     │───▶│  analyse_         │
   │  (cv2 DSHOW) │    │  frames()         │    │  brightness_      │
   └──────────────┘    │                   │    │  series()         │
                       │  • HSV masking    │    │                   │
                       │  • Red isolation  │    │  • FFT            │
                       │  • Brightness     │    │  • Zero-crossing  │
                       │    extraction     │    │  • Peak-interval  │
                       └───────────────────┘    └───────┬───────────┘
                                                        │
                       ┌───────────────────┐            ▼
                       │  build_led_blink_ │◀── BlinkResult
                       │  report()         │
                       │                   │
                       │  • Catppuccin HTML│
                       │  • SVG charts     │
                       │  • Embedded JSON  │
                       └───────┬───────────┘
                               │
                               ▼
                       test_reports/*.html


Modules
-------

``pyontrust.analysis.led_blink``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Pure-compute analysis module with webcam I/O helpers.

.. automodule:: pyontrust.analysis.led_blink
   :members:
   :undoc-members:
   :show-inheritance:

``pyontrust.analysis.test_report``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

HTML test-report generator with Catppuccin Mocha theme and SVG charts.

.. automodule:: pyontrust.analysis.test_report
   :members:
   :undoc-members:
   :show-inheritance:


Data Classes
------------

BlinkResult
~~~~~~~~~~~

The primary output of every LED blink measurement.

.. list-table:: BlinkResult Fields
   :header-rows: 1
   :widths: 20 15 65

   * - Field
     - Type
     - Description
   * - ``ok``
     - ``bool``
     - ``True`` if a valid blink frequency was detected
   * - ``frequency_hz``
     - ``float | None``
     - Measured blink frequency in Hertz
   * - ``period_s``
     - ``float | None``
     - Blink period in seconds (1 / frequency)
   * - ``duty_cycle``
     - ``float | None``
     - Fraction of time LED is ON (0.0 – 1.0)
   * - ``method``
     - ``str``
     - Detection method used: ``"fft"``, ``"zero_crossing"``, or ``"peak_interval"``
   * - ``blink_count``
     - ``int``
     - Number of complete blink cycles observed
   * - ``capture_duration_s``
     - ``float``
     - Total capture window in seconds
   * - ``frame_count``
     - ``int``
     - Number of video frames analysed
   * - ``actual_fps``
     - ``float``
     - Achieved capture frame rate
   * - ``timestamps``
     - ``list[float]``
     - Per-frame timestamps (seconds from capture start)
   * - ``brightness``
     - ``list[float]``
     - Per-frame mean red-LED brightness (V-channel)
   * - ``red_pixel_counts``
     - ``list[int]``
     - Per-frame count of pixels passing the red mask
   * - ``error``
     - ``str | None``
     - Error message if ``ok=False``

CaptureConfig
~~~~~~~~~~~~~

.. list-table:: CaptureConfig Fields
   :header-rows: 1
   :widths: 25 12 10 53

   * - Field
     - Type
     - Default
     - Description
   * - ``device_index``
     - ``int``
     - ``0``
     - OpenCV ``VideoCapture`` device index
   * - ``width``
     - ``int``
     - ``640``
     - Requested frame width in pixels
   * - ``height``
     - ``int``
     - ``480``
     - Requested frame height in pixels
   * - ``capture_duration_s``
     - ``float``
     - ``5.0``
     - Total capture window (seconds)
   * - ``target_fps``
     - ``float``
     - ``30.0``
     - Target frame rate (paced via ``time.sleep``)
   * - ``warmup_frames``
     - ``int``
     - ``10``
     - Frames to discard for auto-exposure settling
   * - ``roi``
     - ``tuple | None``
     - ``None``
     - Region of interest ``(x, y, w, h)`` or ``None`` for full frame

RedLEDMaskConfig
~~~~~~~~~~~~~~~~

HSV thresholds for isolating red LEDs.  Red wraps around in HSV
(H ≈ 0° and H ≈ 180°), so two ranges are applied and OR-combined.

.. list-table:: RedLEDMaskConfig Fields
   :header-rows: 1
   :widths: 20 12 10 58

   * - Field
     - Type
     - Default
     - Description
   * - ``low_h1`` / ``high_h1``
     - ``int``
     - ``0`` / ``10``
     - First hue range (near 0°)
   * - ``low_h2`` / ``high_h2``
     - ``int``
     - ``160`` / ``180``
     - Second hue range (near 360°)
   * - ``low_s`` / ``high_s``
     - ``int``
     - ``80`` / ``255``
     - Saturation range
   * - ``low_v`` / ``high_v``
     - ``int``
     - ``80`` / ``255``
     - Value (brightness) range
   * - ``min_pixel_count``
     - ``int``
     - ``5``
     - Minimum masked pixels to consider valid


Algorithm Detail
----------------

Step 1 — Frame Acquisition
~~~~~~~~~~~~~~~~~~~~~~~~~~

Frames are captured from a USB webcam using OpenCV's ``VideoCapture``
with the DirectShow (``CAP_DSHOW``) backend on Windows for lower
latency.  A configurable warmup phase discards initial frames while
auto-exposure settles.

.. code-block:: python

   cap = cv2.VideoCapture(device_index, cv2.CAP_DSHOW)
   for _ in range(warmup_frames):
       cap.read()  # discard

Step 2 — Red LED Isolation (HSV Masking)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Each BGR frame is converted to HSV colour space.  Two inRange masks
isolate the red hue wrap-around:

.. code-block:: python

   hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
   mask1 = cv2.inRange(hsv, [0, 80, 80], [10, 255, 255])
   mask2 = cv2.inRange(hsv, [160, 80, 80], [180, 255, 255])
   mask  = mask1 | mask2

The mean V-channel value within the mask gives the LED brightness
for that frame.

Step 3 — Time-Series Construction
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

A brightness time-series ``b[t]`` is built from all captured frames.
The ``perf_counter`` timestamps provide sub-millisecond resolution.

Step 4 — Frequency Estimation
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Three independent methods are applied in priority order:

**FFT (primary)**

1. Re-sample brightness to uniform time grid.
2. Subtract DC offset (AC-couple).
3. Apply Hann window to reduce spectral leakage.
4. Compute ``rfft`` and find the dominant peak in ``[min_hz, max_hz]``.
5. SNR gate: peak magnitude must be ≥ 3× the mean magnitude.

.. math::

   f_{\text{blink}} = \arg\max_{f \in [f_{\min}, f_{\max}]} |Y(f)|

**Zero-Crossing (fallback)**

Count sign changes in the AC-coupled signal and divide by duration:

.. math::

   f_{\text{zc}} = \frac{N_{\text{crossings}}}{2 \cdot T}

**Peak-Interval (validation)**

Detect rising edges (OFF→ON transitions) using a midpoint threshold.
Measure intervals between consecutive rising edges:

.. math::

   T_{\text{blink}} = \frac{1}{N-1} \sum_{i=1}^{N-1} (t_{r_i} - t_{r_{i-1}})

This method also yields the **duty cycle** as the fraction of samples
above threshold.


Step 5 — Report Generation
~~~~~~~~~~~~~~~~~~~~~~~~~~

The ``build_led_blink_report()`` function produces a self-contained
HTML report with:

- **Verdict banner** — PASS/FAIL with frequency and method
- **Measurement results** — key-value summary
- **Configuration** — capture and mask parameters
- **SVG charts** — brightness vs time, red pixel count vs time
- **Signal statistics** — min/max/mean/std/amplitude table
- **Embedded JSON** — machine-readable raw data in a ``<script>`` tag


REST API
--------

The diagnostic blueprint exposes LED blink measurement and report
management endpoints:

``POST /diag/api/led_blink``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Run a live LED blink measurement and generate an HTML report.

**Request body (JSON):**

.. code-block:: json

   {
     "device_index": 0,
     "width": 640,
     "height": 480,
     "duration_s": 8.0,
     "fps": 30.0,
     "warmup": 15
   }

**Response:**

.. code-block:: json

   {
     "result": {
       "ok": true,
       "frequency_hz": 1.001,
       "period_s": 0.999,
       "duty_cycle": 0.52,
       "method": "fft",
       "blink_count": 8,
       "capture_duration_s": 7.95,
       "frame_count": 200,
       "actual_fps": 25.1
     },
     "report_file": "C:\\...\\test_reports\\led_blink_20260309_120000.html",
     "report_url": "/diag/api/reports/led_blink_20260309_120000.html"
   }

``GET /diag/api/reports``
~~~~~~~~~~~~~~~~~~~~~~~~~

List all generated HTML test reports.

**Response:**

.. code-block:: json

   [
     {
       "name": "led_blink_20260309_120000.html",
       "size_kb": 42.3,
       "created": 1741500000.0,
       "url": "/diag/api/reports/led_blink_20260309_120000.html"
     }
   ]

``GET /diag/api/reports/<filename>``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Serve a specific HTML report. Returns ``text/html`` content type.
Path traversal is blocked — only filenames within ``test_reports/``
are served.


HTML Report Structure
---------------------

Reports are self-contained HTML files with:

1. **Catppuccin Mocha theme** — consistent with the pyontrust gateway UI
2. **No external dependencies** — all CSS is inline, charts are SVG
3. **Print-ready** — ``@media print`` styles for paper output
4. **Machine-readable** — embedded ``<script type="application/json">``
   block with full time-series data for downstream tooling
5. **Responsive layout** — adapts to narrow screens and PDF export

Report sections:

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Section
     - Content
   * - **Header**
     - Title, DUT, operator, test ID, timestamp, platform version
   * - **Verdict**
     - PASS ✅ / FAIL ❌ banner with frequency and method
   * - **Test Description**
     - Free-text explaining the measurement purpose
   * - **Measurement Results**
     - Key-value grid (frequency, period, duty cycle, FPS, …)
   * - **Capture Configuration**
     - Device index, resolution, FPS, warmup, ROI
   * - **HSV Mask Configuration**
     - Red hue ranges, saturation, value thresholds
   * - **Brightness Time-Series**
     - SVG line chart of red LED brightness vs time
   * - **Red Pixel Count**
     - SVG line chart of masked pixel count vs time
   * - **Signal Statistics**
     - Table: min, max, mean, std, amplitude, pixel counts
   * - **Embedded Data**
     - Hidden JSON with ``blink_result`` and ``time_series``

Using the ``ReportBuilder`` API:

.. code-block:: python

   from pyontrust.analysis.test_report import ReportBuilder

   rb = ReportBuilder(
       title="My Custom Test",
       dut="nRF9160-DK",
       operator="Lab Technician",
       test_id="CUSTOM-001",
   )
   rb.add_section_text("Overview", "Description of the test…")
   rb.add_section_kv("Results", {"Freq": "2.0 Hz", "Pass": "Yes"})
   rb.add_section_chart("Signal", timestamps, values)
   rb.add_section_table("Summary", ["Metric", "Value"], rows)
   rb.set_verdict(passed=True, message="All checks passed")
   rb.write("test_reports/my_custom_test.html")


Testing
-------

Test Strategy
~~~~~~~~~~~~~

.. list-table::
   :header-rows: 1
   :widths: 35 15 50

   * - Test File
     - Count
     - Scope
   * - ``test_led_blink.py``
     - 28
     - LED analysis (26 synthetic + 2 hardware)
   * - ``test_report_generator.py``
     - 30+
     - Report builder, SVG charts, blueprint routes
   * - **Total**
     - **58+**
     - Full coverage of analysis + reporting

Running Tests
~~~~~~~~~~~~~

.. code-block:: bash

   # All tests (CI-safe, no hardware)
   python -m pytest tests/power_framework_tests/test_led_blink.py \
                     tests/power_framework_tests/test_report_generator.py \
                     -v -k "not RealWebcam"

   # Hardware integration (requires webcam + red LED)
   python -m pytest tests/power_framework_tests/test_led_blink.py \
                     -v -k "RealWebcam" -s

   # Generate report from command line
   python -c "
   from pyontrust.analysis.led_blink import measure_led_blink_rate, CaptureConfig
   from pyontrust.analysis.test_report import build_led_blink_report
   result = measure_led_blink_rate(CaptureConfig(capture_duration_s=10))
   path = build_led_blink_report(result)
   print(f'Report: {path}')
   "


Performance Considerations
--------------------------

.. list-table::
   :header-rows: 1
   :widths: 30 25 45

   * - Operation
     - Typical Time
     - Notes
   * - Webcam open (DSHOW)
     - 0.3 – 1.0 s
     - First open slower; DSHOW avoids MSMF lag
   * - Frame capture (30 fps)
     - 33 ms / frame
     - Limited by USB bandwidth and auto-exposure
   * - HSV masking
     - < 1 ms / frame
     - OpenCV optimised; 640×480 trivial
   * - FFT analysis
     - < 5 ms
     - For 300 samples; ``numpy.fft.rfft``
   * - Report generation
     - < 50 ms
     - SVG rendering is string-based, no matplotlib
   * - **8 s capture + report**
     - **~9 s total**
     - Dominated by capture duration


Limitations
-----------

- **Nyquist limit**: Maximum detectable frequency is ``target_fps / 2``.
  At 30 fps, blinks above 15 Hz may alias.
- **Auto-exposure**: Some webcams adjust exposure between frames,
  causing brightness drift.  The warmup phase mitigates this.
- **Ambient light**: Strong ambient light or reflections can saturate
  the red mask.  Use ``roi`` to restrict analysis to the LED region.
- **Multiple LEDs**: If multiple red LEDs are visible, the mask
  averages their brightness, which may confuse the analysis.
  Use ``roi`` to isolate a single LED.
- **Non-red LEDs**: Currently only red LEDs are supported.  Green
  and blue LED support requires additional mask configurations.


Changelog
---------

.. list-table::
   :header-rows: 1
   :widths: 15 85

   * - Version
     - Changes
   * - 2026.3.0
     - Initial implementation: LED blink analysis, HTML reports, diagnostic API
