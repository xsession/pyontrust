from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd


REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_DIR = REPO_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))


from pyontrust.analysis.metrics import compute_signal_spectrum  # noqa: E402
from pyontrust.csv_plotter import (  # noqa: E402
    PanelFileEntry,
    build_browser_plot_model,
    build_histogram_panel_payload,
    build_plot_scene,
    build_spectrum_panel_payload,
)


def test_build_plot_scene_and_browser_model() -> None:
    df = pd.DataFrame(
        {
            "Timestamp": [0.0, 0.5, 1.0, 1.5],
            "A": [1.0, 2.0, 3.0, 4.0],
            "B": [4.0, 3.0, 2.0, 1.0],
        }
    )

    scene = build_plot_scene(df, ["A", "B"], title_prefix="Demo")
    model = build_browser_plot_model(scene, x_window=(0.25, 1.25))

    assert scene.title == "Demo"
    assert len(scene.series) == 2
    assert model["domain"] == [0.0, 1.5]
    assert model["xWindow"] == [0.25, 1.25]


def test_histogram_and_spectrum_payloads() -> None:
    samples = 256
    df = pd.DataFrame(
        {
            "Timestamp": [index * 0.01 for index in range(samples)],
            "A": [__import__("math").sin(2.0 * __import__("math").pi * 2.0 * (index * 0.01)) for index in range(samples)],
        }
    )
    entry = PanelFileEntry(path="demo.csv", label="demo", df=df)

    histogram = build_histogram_panel_payload([entry], ["A"], bins=4)
    spectrum = build_spectrum_panel_payload([entry], ["A"])

    assert histogram["kind"] == "histogram"
    assert histogram["series"]
    assert spectrum["kind"] == "spectrum"
    assert spectrum["series"]


def test_compute_signal_spectrum_detects_bins() -> None:
    x = pd.Series([index * 0.01 for index in range(256)])
    y = pd.Series([0.0 if index % 2 == 0 else 1.0 for index in range(256)])
    freqs, magnitudes, baseline = compute_signal_spectrum(x, y)

    assert baseline is not None
    assert len(freqs) == len(magnitudes)
    assert len(freqs) > 1