Hardware Diagnostic System
==========================

.. contents:: Table of Contents
   :depth: 3
   :local:

Overview
--------

The hardware diagnostic system provides automated discovery, testing,
and reporting for all physical instruments connected to the lab bench.
It is composed of three layers:

1. **Hardware Discovery Service** — parallel probing of all hardware
   interfaces (serial, USB, ADB, webcam, DWF, Seek Thermal, J-Link,
   HackRF, PPK2, nRF52840, network)
2. **Diagnostic Blueprint** — Flask REST API with a web SPA dashboard
3. **Test Report Generator** — enterprise-grade HTML reports with
   SVG charts and embedded JSON data


Diagnostic Landing Page
-----------------------

The diagnostic SPA is served at ``/diag/`` and provides:

- **Hardware scan** with parallel probing (< 30 seconds)
- **Category grouping** — Android, serial, camera, instruments,
  thermal, debug, SDR, BLE, network
- **Quick tests** — per-device functional tests
- **Test-all** — batch testing of all connected hardware
- **LED blink measurement** — webcam-based LED frequency analysis
- **Report generation** — detailed HTML reports for each measurement
- **Report browsing** — list and view historical reports


Hardware Discovery
------------------

Supported Interfaces
~~~~~~~~~~~~~~~~~~~~

.. list-table::
   :header-rows: 1
   :widths: 20 15 65

   * - Interface
     - Icon
     - Detection Method
   * - Serial Ports
     - 🔌
     - ``serial.tools.list_ports.comports()``
   * - ADB Devices
     - 📱
     - ``adb devices`` with Popen timeout (10s)
   * - Webcams
     - 📷
     - ``cv2.VideoCapture(idx, CAP_DSHOW)``
   * - Analog Discovery
     - 📊
     - DWF SDK ``FDwfEnum`` via ctypes
   * - Seek Thermal
     - 🌡️
     - ``seekcamera`` / USB VID check
   * - J-Link
     - 🐛
     - ``JLink.exe`` or ``pylink``
   * - HackRF
     - 📡
     - ``hackrf_info`` or SoapySDR
   * - PPK2
     - ⚡
     - Serial VID:PID (1915:C00A)
   * - nRF52840 Dongle
     - 📻
     - Serial VID:PID (1915:521F, 1915:C00A)
   * - Network
     - 🌐
     - ``socket.gethostname()``

Discovery runs all probes in parallel using ``ThreadPoolExecutor``
with a configurable timeout (default 30 seconds).


REST API Reference
------------------

.. list-table::
   :header-rows: 1
   :widths: 10 35 55

   * - Method
     - Endpoint
     - Description
   * - GET
     - ``/diag/``
     - Diagnostic SPA landing page
   * - GET
     - ``/diag/api/scan``
     - Parallel hardware scan
   * - POST
     - ``/diag/api/test``
     - Quick test on a single device
   * - POST
     - ``/diag/api/test_all``
     - Scan + test all hardware
   * - POST
     - ``/diag/api/led_blink``
     - LED blink measurement + report
   * - GET
     - ``/diag/api/reports``
     - List all HTML test reports
   * - GET
     - ``/diag/api/reports/<name>``
     - Serve a specific report
   * - GET
     - ``/diag/api/system``
     - System and package info


Test Reports
------------

Report Storage
~~~~~~~~~~~~~~

Reports are stored in the ``test_reports/`` directory at the project
root.  Each report is a self-contained HTML file named with a
timestamp:

.. code-block:: text

   test_reports/
   ├── led_blink_20260309_120000.html
   ├── led_blink_20260309_143000.html
   └── led_blink_20260310_091500.html

Report Lifecycle
~~~~~~~~~~~~~~~~

1. **Generation** — via ``build_led_blink_report()`` or the
   ``POST /diag/api/led_blink`` endpoint
2. **Storage** — written to ``test_reports/`` with auto-created
   parent directories
3. **Browsing** — via ``GET /diag/api/reports`` (list) and
   ``GET /diag/api/reports/<name>`` (serve)
4. **Archival** — collect ``test_reports/*.html`` as CI artifacts
5. **Comparison** — embedded JSON enables automated trend analysis


Security
--------

- **Path traversal** — report serving uses ``pathlib.Path.name`` to
  strip directory components; only files in ``test_reports/`` are served
- **XSS protection** — all user-supplied strings are escaped via
  ``html.escape()``
- **No external resources** — reports are fully self-contained,
  preventing SSRF via injected URLs


Testing
-------

.. code-block:: bash

   # Full diagnostic test suite
   python -m pytest tests/power_framework_tests/test_diagnostic.py \
                     tests/power_framework_tests/test_report_generator.py \
                     tests/power_framework_tests/test_led_blink.py \
                     -v -k "not RealWebcam"

   # Hardware integration (requires connected devices)
   python -m pytest tests/power_framework_tests/test_led_blink.py \
                     -v -k "RealWebcam" -s

Test coverage:

.. list-table::
   :header-rows: 1
   :widths: 40 12 48

   * - Test File
     - Count
     - Scope
   * - ``test_diagnostic.py``
     - 19
     - Hardware discovery, blueprint routes, navigation
   * - ``test_led_blink.py``
     - 28
     - LED analysis (26 synthetic + 2 hardware + report)
   * - ``test_report_generator.py``
     - 30+
     - Report builder, SVG charts, blueprint report routes
   * - **Total**
     - **77+**
     - Full coverage of diagnostic + analysis + reporting


Changelog
---------

.. list-table::
   :header-rows: 1
   :widths: 15 85

   * - Version
     - Changes
   * - 2026.3.0
     - Hardware discovery service, diagnostic SPA, LED blink analysis,
       HTML report generator, enterprise documentation
