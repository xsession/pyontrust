# SPDX-License-Identifier: Apache-2.0
"""Focused tests for package CAD artifact helpers."""

import pathlib
import sys

_PKG_DIR = pathlib.Path(__file__).resolve().parent.parent
if str(_PKG_DIR) not in sys.path:
    sys.path.insert(0, str(_PKG_DIR))

from package_artifacts import generate_kicad_footprint


def test_generate_kicad_footprint_emits_pinfunction_metadata():
    footprint = generate_kicad_footprint({
        "name": "LGA-8",
        "package_type": "LGA",
        "pin_count": 8,
        "width_mm": 2.0,
        "height_mm": 2.5,
        "pitch_mm": 0.5,
        "thickness_mm": 0.95,
        "pins": [
            {"number": 1, "name": "GND"},
            {"number": 2, "name": "CSB"},
            {"number": 3, "name": "SDI"},
            {"number": 4, "name": "SCK"},
            {"number": 5, "name": "SDO"},
            {"number": 6, "name": "VDDIO"},
            {"number": 7, "name": "GND"},
            {"number": 8, "name": "VDD"},
        ],
    }, "BMP280")

    assert '(pad "1" smd rect' in footprint
    assert '(pinfunction "GND") (pintype "power_in")' in footprint
    assert '(pinfunction "CSB") (pintype "passive")' in footprint
    assert '(pinfunction "VDD") (pintype "power_in")' in footprint