HTML Test Report Generator
===========================

.. contents:: Table of Contents
   :depth: 3
   :local:

Overview
--------

The ``pyontrust.analysis.test_report`` module provides an enterprise-grade
HTML report generator for automated test results.  Reports are self-contained,
print-ready, and use the Catppuccin Mocha dark theme consistent with the
pyontrust gateway web interface.

Key features:

- **Self-contained HTML** — no external CSS, JS, or font dependencies
- **SVG line charts** — stdlib-only renderer, no matplotlib required
- **Catppuccin Mocha theme** — dark mode with print-optimised fallback
- **Embedded JSON data** — machine-readable ``<script>`` block for
  downstream tooling (CI dashboards, trend analysis)
- **Fluent API** — chainable builder methods for easy report composition
- **Enterprise metadata** — DUT, operator, test ID, environment, timestamp


Module Reference
----------------

.. automodule:: pyontrust.analysis.test_report
   :members:
   :undoc-members:
   :show-inheritance:


ReportBuilder API
-----------------

Construction
~~~~~~~~~~~~

.. code-block:: python

   from pyontrust.analysis.test_report import ReportBuilder

   rb = ReportBuilder(
       title="Power Consumption Test",
       dut="nRF9160-DK SN:12345",
       operator="Jane Smith",
       test_id="PWR-SLEEP-042",
       environment="Lab A — Station 3",
   )

All parameters are optional.  The report header will display whatever
metadata is provided.

Adding Sections
~~~~~~~~~~~~~~~

All ``add_*`` methods return ``self`` for fluent chaining.

.. list-table:: Section Methods
   :header-rows: 1
   :widths: 35 65

   * - Method
     - Description
   * - ``add_section_text(title, text)``
     - Free-text paragraph(s).  Double newlines create ``<p>`` breaks.
   * - ``add_section_kv(title, data)``
     - Key-value grid.  ``data`` is a ``dict[str, Any]``.
   * - ``add_section_table(title, headers, rows, ...)``
     - Data table with optional numeric alignment and pass/fail colouring.
   * - ``add_section_chart(title, x, y, ...)``
     - SVG line chart.  Supports threshold line and secondary Y series.
   * - ``add_section_html(title, raw_html)``
     - Raw HTML for custom sections.

Verdict
~~~~~~~

.. code-block:: python

   rb.set_verdict(
       passed=True,
       message="All measurements within specification",
       details="Sleep current: 2.3 µA (limit: < 5 µA)",
   )

Creates a prominent PASS ✅ or FAIL ❌ banner at the top of the report.

Metadata & Raw Data
~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   rb.add_meta("Firmware", "v2.1.0-rc3")
   rb.add_meta("Build", "CI #4521")
   rb.attach_raw_data("measurements", {"samples": [...], "stats": {...}})

Extra metadata appears in the header.  Raw data is embedded in a
``<script type="application/json" id="report-data">`` tag for
programmatic extraction.

Rendering & Writing
~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   # Get HTML string
   html_string = rb.render()

   # Write to file (creates directories)
   path = rb.write("test_reports/my_report.html")
   print(f"Report: {path}")


SVG Chart Renderer
------------------

The ``_render_svg_line_chart()`` function generates inline SVG charts
without any external dependencies.

Features:

- Auto-scaled axes with grid lines
- Axis labels and title
- Optional horizontal threshold line (dashed yellow)
- Optional secondary Y-series overlay
- Responsive ``viewBox`` for scaling
- Catppuccin colour palette

Limitations:

- Line charts only (no bar, scatter, histogram)
- No interactive zoom/pan (static SVG)
- Up to ~5000 data points before the SVG string becomes large


Convenience Functions
---------------------

``build_led_blink_report()``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

One-call convenience that builds a complete LED blink test report:

.. code-block:: python

   from pyontrust.analysis.test_report import build_led_blink_report
   from pyontrust.analysis.led_blink import measure_led_blink_rate

   result = measure_led_blink_rate()
   path = build_led_blink_report(
       result,
       dut="Arduino Uno — Pin 13 LED",
       output_dir="test_reports",
   )

The report includes:

1. Verdict banner
2. Test description
3. Measurement results (frequency, period, duty cycle)
4. Capture and mask configuration
5. Brightness time-series SVG chart
6. Red pixel count SVG chart
7. Signal statistics table
8. Embedded JSON raw data


Integration with CI/CD
----------------------

Reports can be collected as CI artifacts:

.. code-block:: yaml

   # GitHub Actions example
   - name: Run LED blink test
     run: |
       python -m pytest tests/power_framework_tests/test_led_blink.py \
         -v -k RealWebcam -s

   - name: Upload test reports
     uses: actions/upload-artifact@v4
     if: always()
     with:
       name: led-blink-reports
       path: test_reports/*.html

For Jenkins, archive the ``test_reports/`` directory as post-build
artifacts.


Extending the Report System
----------------------------

Custom Test Reports
~~~~~~~~~~~~~~~~~~~

The ``ReportBuilder`` is generic and can be used for any test type:

.. code-block:: python

   from pyontrust.analysis.test_report import ReportBuilder

   rb = ReportBuilder(title="RF Spectrum Analysis")
   rb.add_section_text("Summary", "Measured TX power at 868 MHz…")
   rb.add_section_chart("Spectrum", freq_mhz, power_dbm,
                        x_label="Frequency (MHz)",
                        y_label="Power (dBm)",
                        threshold_y=-20.0)
   rb.add_section_table("Band Compliance",
                        ["Band", "Limit (dBm)", "Measured (dBm)", "Result"],
                        rows, pass_fail_col=3)
   rb.set_verdict(passed=all_ok, message="RF compliance check")
   rb.write("test_reports/rf_spectrum.html")

Custom Section HTML
~~~~~~~~~~~~~~~~~~~

For complex visualisations, inject raw HTML:

.. code-block:: python

   rb.add_section_html("Custom View", '''
       <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 12px;">
           <div class="card">Left panel</div>
           <div class="card">Right panel</div>
       </div>
   ''')


Testing
-------

.. code-block:: bash

   python -m pytest tests/power_framework_tests/test_report_generator.py -v

The test suite covers:

- ``ReportBuilder`` API (all section types, metadata, chaining)
- SVG chart edge cases (empty data, constant Y, large datasets)
- ``build_led_blink_report()`` pass/fail scenarios
- Diagnostic blueprint report routes (list, serve, path traversal)
- End-to-end synthetic pipeline (blink → analysis → report)
- HTML validity (balanced tags, proper escaping, XSS protection)


Changelog
---------

.. list-table::
   :header-rows: 1
   :widths: 15 85

   * - Version
     - Changes
   * - 2026.3.0
     - Initial implementation: ReportBuilder, SVG charts, LED blink reports
