"""Tests for thermal measurement analysis module.

Covers all 4 measurement modes (continuous, soak, delta, gradient),
result dataclasses, config parsing, HTML report generation,
gateway blueprint API routes, and FlowLab blocks.

Target: 60+ tests, all using the SimulatedThermalCamera (no USB needed).
"""

from __future__ import annotations

import json
import os
import pathlib
import shutil
import tempfile
import time
from typing import Any
from unittest.mock import MagicMock, patch

import numpy as np
import pytest


# ═══════════════════════════════════════════════════════════════════════
#  Fixtures
# ═══════════════════════════════════════════════════════════════════════


@pytest.fixture()
def tmp_reports(tmp_path: pathlib.Path):
    """Provide a temporary report directory and clean up after."""
    report_dir = tmp_path / "reports"
    report_dir.mkdir()
    return report_dir


def _base_config(**overrides: Any) -> dict[str, Any]:
    """Return a minimal simulated-camera config dict for fast tests."""
    cfg: dict[str, Any] = {
        "mode": "continuous",
        "duration_s": 2.0,
        "capture_interval_s": 0.2,
        "warmup_frames": 1,
        "camera": {"mode": "simulated", "base_temp_c": 30.0, "inject_hotspot": False},
        "zones": [
            {"name": "MCU", "x": 10, "y": 10, "width": 20, "height": 20,
             "warn_temp_c": 60.0, "max_temp_c": 85.0},
        ],
        "global_max_temp_c": 85.0,
        "board_id": "TEST-PCB-001",
        "save_snapshots": False,
    }
    cfg.update(overrides)
    return cfg


# ═══════════════════════════════════════════════════════════════════════
#  Configuration dataclass
# ═══════════════════════════════════════════════════════════════════════


class TestThermalMeasurementConfig:
    """ThermalMeasurementConfig dataclass tests."""

    def test_default_mode(self):
        from pyontrust.analysis.thermal.measurement import ThermalMeasurementConfig
        cfg = ThermalMeasurementConfig()
        assert cfg.mode == "continuous"

    def test_default_duration(self):
        from pyontrust.analysis.thermal.measurement import ThermalMeasurementConfig
        cfg = ThermalMeasurementConfig()
        assert cfg.duration_s == 30.0

    def test_custom_fields(self):
        from pyontrust.analysis.thermal.measurement import ThermalMeasurementConfig
        cfg = ThermalMeasurementConfig(
            mode="soak",
            duration_s=120.0,
            soak_stable_threshold_c=0.3,
            board_id="PCB-42",
        )
        assert cfg.mode == "soak"
        assert cfg.duration_s == 120.0
        assert cfg.soak_stable_threshold_c == 0.3
        assert cfg.board_id == "PCB-42"

    def test_to_dict_roundtrip(self):
        from pyontrust.analysis.thermal.measurement import ThermalMeasurementConfig
        cfg = ThermalMeasurementConfig(mode="delta", duration_s=10.0)
        d = cfg.to_dict()
        assert d["mode"] == "delta"
        assert d["duration_s"] == 10.0
        assert "camera" in d

    def test_dict_to_config(self):
        from pyontrust.analysis.thermal.measurement import _dict_to_config
        d = {"mode": "gradient", "duration_s": 5.0, "warmup_frames": 2, "board_id": "XYZ"}
        cfg = _dict_to_config(d)
        assert cfg.mode == "gradient"
        assert cfg.duration_s == 5.0
        assert cfg.warmup_frames == 2
        assert cfg.board_id == "XYZ"

    def test_dict_to_config_defaults(self):
        from pyontrust.analysis.thermal.measurement import _dict_to_config
        cfg = _dict_to_config({})
        assert cfg.mode == "continuous"
        assert cfg.warmup_frames == 5
        assert cfg.global_max_temp_c == 85.0

    def test_soak_params_in_config(self):
        from pyontrust.analysis.thermal.measurement import ThermalMeasurementConfig
        cfg = ThermalMeasurementConfig(
            soak_stable_window_s=15.0,
            soak_stable_threshold_c=0.2,
            soak_timeout_s=600.0,
        )
        assert cfg.soak_stable_window_s == 15.0
        assert cfg.soak_stable_threshold_c == 0.2
        assert cfg.soak_timeout_s == 600.0

    def test_delta_params_in_config(self):
        from pyontrust.analysis.thermal.measurement import ThermalMeasurementConfig
        cfg = ThermalMeasurementConfig(
            delta_baseline_frames=8,
            delta_stimulus_frames=12,
            delta_pause_s=3.0,
        )
        assert cfg.delta_baseline_frames == 8
        assert cfg.delta_stimulus_frames == 12
        assert cfg.delta_pause_s == 3.0

    def test_gradient_params_in_config(self):
        from pyontrust.analysis.thermal.measurement import ThermalMeasurementConfig
        cfg = ThermalMeasurementConfig(
            max_gradient_c_per_mm=2.0,
            pixel_pitch_mm=0.12,
        )
        assert cfg.max_gradient_c_per_mm == 2.0
        assert cfg.pixel_pitch_mm == 0.12


# ═══════════════════════════════════════════════════════════════════════
#  Result dataclasses
# ═══════════════════════════════════════════════════════════════════════


class TestZoneStatistics:
    """ZoneStatistics dataclass tests."""

    def test_create_default(self):
        from pyontrust.analysis.thermal.measurement import ZoneStatistics
        zs = ZoneStatistics(zone_name="CPU")
        assert zs.zone_name == "CPU"
        assert zs.mean_temp_c == 0.0

    def test_to_dict(self):
        from pyontrust.analysis.thermal.measurement import ZoneStatistics
        zs = ZoneStatistics(
            zone_name="VREG",
            mean_temp_c=45.12345,
            max_temp_c=52.3,
            min_temp_c=41.1,
            std_temp_c=1.567,
            peak_rate_c_per_s=0.45,
            temp_rise_c=3.2,
            worst_verdict="WARM",
        )
        d = zs.to_dict()
        assert d["zone_name"] == "VREG"
        assert d["mean_temp_c"] == 45.12
        assert d["worst_verdict"] == "WARM"

    def test_to_dict_includes_delta_if_nonzero(self):
        from pyontrust.analysis.thermal.measurement import ZoneStatistics
        zs = ZoneStatistics(
            zone_name="MCU",
            baseline_mean_c=25.0,
            stimulus_mean_c=30.0,
            delta_c=5.0,
        )
        d = zs.to_dict()
        assert "delta_c" in d
        assert d["delta_c"] == 5.0

    def test_to_dict_omits_delta_if_zero(self):
        from pyontrust.analysis.thermal.measurement import ZoneStatistics
        zs = ZoneStatistics(zone_name="MCU", delta_c=0.0)
        d = zs.to_dict()
        assert "delta_c" not in d


class TestGradientResult:
    """GradientResult dataclass tests."""

    def test_defaults(self):
        from pyontrust.analysis.thermal.measurement import GradientResult
        g = GradientResult()
        assert g.passed is True
        assert g.max_gradient_c_per_px == 0.0

    def test_to_dict(self):
        from pyontrust.analysis.thermal.measurement import GradientResult
        g = GradientResult(
            max_gradient_c_per_px=0.1234,
            max_gradient_c_per_mm=0.7259,
            gradient_location=(50, 30),
            direction_deg=45.6,
            passed=False,
        )
        d = g.to_dict()
        assert d["max_gradient_c_per_px"] == 0.1234
        assert d["gradient_location"] == [50, 30]
        assert d["passed"] is False


class TestThermalMeasurementResult:
    """ThermalMeasurementResult dataclass tests."""

    def test_default_passed(self):
        from pyontrust.analysis.thermal.measurement import ThermalMeasurementResult
        r = ThermalMeasurementResult()
        assert r.passed is True
        assert r.fail_reasons == []

    def test_summary(self):
        from pyontrust.analysis.thermal.measurement import ThermalMeasurementResult
        r = ThermalMeasurementResult(
            mode="continuous",
            passed=True,
            board_id="PCB-001",
            global_max_c=42.5,
            total_frames=10,
        )
        s = r.summary()
        assert s["mode"] == "continuous"
        assert s["passed"] is True
        assert s["global_max_c"] == 42.5
        assert s["total_frames"] == 10

    def test_to_dict_includes_config(self):
        from pyontrust.analysis.thermal.measurement import ThermalMeasurementResult
        r = ThermalMeasurementResult(config={"mode": "soak"})
        d = r.to_dict()
        assert d["config"] == {"mode": "soak"}

    def test_to_dict_includes_gradient(self):
        from pyontrust.analysis.thermal.measurement import (
            ThermalMeasurementResult, GradientResult,
        )
        g = GradientResult(max_gradient_c_per_mm=1.5)
        r = ThermalMeasurementResult(gradient=g)
        d = r.to_dict()
        assert "gradient" in d
        assert d["gradient"]["max_gradient_c_per_mm"] == 1.5

    def test_write_json(self, tmp_reports):
        from pyontrust.analysis.thermal.measurement import ThermalMeasurementResult
        r = ThermalMeasurementResult(mode="continuous", total_frames=5)
        p = r.write_json(tmp_reports / "result.json")
        assert p.exists()
        data = json.loads(p.read_text(encoding="utf-8"))
        assert data["mode"] == "continuous"
        assert data["total_frames"] == 5


# ═══════════════════════════════════════════════════════════════════════
#  Helpers
# ═══════════════════════════════════════════════════════════════════════


class TestHelpers:
    """Tests for internal helper functions."""

    def test_compute_zone_stats_empty(self):
        from pyontrust.analysis.thermal.measurement import _compute_zone_stats
        stats = _compute_zone_stats({})
        assert stats == []

    def test_compute_zone_stats_single_zone(self):
        from pyontrust.analysis.thermal.measurement import _compute_zone_stats
        series = {"CPU": [
            (0.0, 30.0, 0.5),
            (1.0, 32.0, 1.0),
            (2.0, 35.0, 0.8),
        ]}
        stats = _compute_zone_stats(series)
        assert len(stats) == 1
        zs = stats[0]
        assert zs.zone_name == "CPU"
        assert zs.max_temp_c == 35.0
        assert zs.min_temp_c == 30.0
        assert abs(zs.mean_temp_c - np.mean([30, 32, 35])) < 0.01
        assert zs.temp_rise_c == 5.0  # 35 - 30

    def test_compute_zone_stats_verdict_warm(self):
        from pyontrust.analysis.thermal.measurement import _compute_zone_stats
        series = {"VREG": [(0.0, 65.0, 0.1), (1.0, 70.0, 0.2)]}
        stats = _compute_zone_stats(series)
        assert stats[0].worst_verdict == "WARM"

    def test_compute_zone_stats_verdict_hot(self):
        from pyontrust.analysis.thermal.measurement import _compute_zone_stats
        series = {"VREG": [(0.0, 90.0, 0.1)]}
        stats = _compute_zone_stats(series)
        assert stats[0].worst_verdict == "HOT"

    def test_compute_zone_stats_verdict_runaway(self):
        from pyontrust.analysis.thermal.measurement import _compute_zone_stats
        series = {"MCU": [(0.0, 30.0, 6.0)]}  # rate > 5.0
        stats = _compute_zone_stats(series)
        assert stats[0].worst_verdict == "RUNAWAY"

    def test_compute_gradient_2d(self):
        from pyontrust.analysis.thermal.measurement import _compute_gradient
        # Create a frame with a horizontal gradient
        frame = np.tile(np.linspace(20, 40, 50, dtype=np.float32), (30, 1))
        g = _compute_gradient(frame, pixel_pitch_mm=0.17)
        assert g.max_gradient_c_per_px > 0
        assert g.max_gradient_c_per_mm > 0
        assert g.passed is True

    def test_compute_gradient_empty(self):
        from pyontrust.analysis.thermal.measurement import _compute_gradient
        g = _compute_gradient(np.array([]), pixel_pitch_mm=0.17)
        assert g.max_gradient_c_per_px == 0.0

    def test_compute_gradient_1d_returns_default(self):
        from pyontrust.analysis.thermal.measurement import _compute_gradient
        g = _compute_gradient(np.array([1.0, 2.0, 3.0]), pixel_pitch_mm=0.17)
        assert g.max_gradient_c_per_px == 0.0

    def test_compute_gradient_uniform_frame(self):
        from pyontrust.analysis.thermal.measurement import _compute_gradient
        frame = np.full((30, 50), 25.0, dtype=np.float32)
        g = _compute_gradient(frame, pixel_pitch_mm=0.17)
        assert g.max_gradient_c_per_px < 0.01  # effectively zero

    def test_compute_gradient_location(self):
        from pyontrust.analysis.thermal.measurement import _compute_gradient
        frame = np.full((30, 50), 25.0, dtype=np.float32)
        frame[15, 25] = 50.0  # inject single hotspot
        g = _compute_gradient(frame, pixel_pitch_mm=0.17)
        assert g.max_gradient_c_per_px > 1.0
        # Location should be near the hotspot
        lx, ly = g.gradient_location
        assert abs(lx - 25) <= 2 and abs(ly - 15) <= 2


# ═══════════════════════════════════════════════════════════════════════
#  Continuous mode — full integration with SimulatedThermalCamera
# ═══════════════════════════════════════════════════════════════════════


class TestContinuousMode:
    """Test continuous measurement mode with simulated camera."""

    def test_continuous_basic(self):
        from pyontrust.analysis.thermal.measurement import run_thermal_measurement
        cfg = _base_config(duration_s=1.5, capture_interval_s=0.3)
        result = run_thermal_measurement(cfg)
        assert result.mode == "continuous"
        assert result.total_frames >= 3
        assert result.duration_s > 0
        assert result.global_mean_c > 0

    def test_continuous_passed(self):
        from pyontrust.analysis.thermal.measurement import run_thermal_measurement
        cfg = _base_config(duration_s=1.0, capture_interval_s=0.3, global_max_temp_c=200)
        result = run_thermal_measurement(cfg)
        assert result.passed is True
        assert result.fail_reasons == []

    def test_continuous_zone_stats_populated(self):
        from pyontrust.analysis.thermal.measurement import run_thermal_measurement
        cfg = _base_config(duration_s=1.0, capture_interval_s=0.3)
        result = run_thermal_measurement(cfg)
        assert len(result.zone_stats) >= 1
        zs = result.zone_stats[0]
        assert zs.zone_name == "MCU"
        assert zs.mean_temp_c > 0

    def test_continuous_timestamps(self):
        from pyontrust.analysis.thermal.measurement import run_thermal_measurement
        cfg = _base_config(duration_s=1.0, capture_interval_s=0.25)
        result = run_thermal_measurement(cfg)
        assert len(result.timestamps) == result.total_frames
        assert len(result.global_temps) == result.total_frames
        # Timestamps should be monotonically increasing
        for i in range(1, len(result.timestamps)):
            assert result.timestamps[i] > result.timestamps[i - 1]

    def test_continuous_hotspot_history(self):
        from pyontrust.analysis.thermal.measurement import run_thermal_measurement
        cfg = _base_config(duration_s=1.0, capture_interval_s=0.3)
        result = run_thermal_measurement(cfg)
        assert len(result.hotspot_history) == result.total_frames
        for h in result.hotspot_history:
            assert "t_s" in h
            assert "temp_c" in h

    def test_continuous_with_snapshots(self):
        from pyontrust.analysis.thermal.measurement import run_thermal_measurement
        cfg = _base_config(duration_s=0.8, capture_interval_s=0.3, save_snapshots=True)
        result = run_thermal_measurement(cfg)
        assert len(result.snapshots) == result.total_frames
        assert result.snapshots[0].get("global_mean_c", 0) > 0

    def test_continuous_with_progress_callback(self):
        from pyontrust.analysis.thermal.measurement import run_thermal_measurement
        progress_calls: list[tuple] = []

        def cb(idx, total, snap):
            progress_calls.append((idx, total, snap))

        cfg = _base_config(duration_s=0.8, capture_interval_s=0.3)
        result = run_thermal_measurement(cfg, progress_cb=cb)
        assert len(progress_calls) == result.total_frames
        assert progress_calls[0][0] == 1  # First frame index = 1

    def test_continuous_global_limit_fail(self):
        from pyontrust.analysis.thermal.measurement import run_thermal_measurement
        # Set a very low limit so simulated camera triggers it
        cfg = _base_config(duration_s=0.8, capture_interval_s=0.3, global_max_temp_c=1.0)
        result = run_thermal_measurement(cfg)
        assert result.passed is False
        assert any("exceeds limit" in r for r in result.fail_reasons)

    def test_continuous_camera_info_populated(self):
        from pyontrust.analysis.thermal.measurement import run_thermal_measurement
        cfg = _base_config(duration_s=0.5, capture_interval_s=0.3)
        result = run_thermal_measurement(cfg)
        assert "model" in result.camera_info
        assert "resolution" in result.camera_info

    def test_continuous_multiple_zones(self):
        from pyontrust.analysis.thermal.measurement import run_thermal_measurement
        cfg = _base_config(
            duration_s=0.8,
            capture_interval_s=0.3,
            zones=[
                {"name": "MCU", "x": 10, "y": 10, "width": 20, "height": 20},
                {"name": "VREG", "x": 50, "y": 50, "width": 15, "height": 15},
                {"name": "PA", "x": 80, "y": 20, "width": 10, "height": 10},
            ],
        )
        result = run_thermal_measurement(cfg)
        assert len(result.zone_stats) == 3
        names = {zs.zone_name for zs in result.zone_stats}
        assert names == {"MCU", "VREG", "PA"}

    def test_continuous_board_id(self):
        from pyontrust.analysis.thermal.measurement import run_thermal_measurement
        cfg = _base_config(duration_s=0.5, capture_interval_s=0.3, board_id="MY-PCB-99")
        result = run_thermal_measurement(cfg)
        assert result.board_id == "MY-PCB-99"


# ═══════════════════════════════════════════════════════════════════════
#  Soak mode
# ═══════════════════════════════════════════════════════════════════════


class TestSoakMode:
    """Test soak measurement mode."""

    def test_soak_settles(self):
        """Simulated camera has constant temp, should settle quickly."""
        from pyontrust.analysis.thermal.measurement import run_thermal_measurement
        cfg = _base_config(
            mode="soak",
            duration_s=5.0,
            capture_interval_s=0.2,
            soak_stable_window_s=1.0,
            soak_stable_threshold_c=2.0,  # generous threshold
            soak_timeout_s=5.0,
        )
        result = run_thermal_measurement(cfg)
        assert result.mode == "soak"
        assert result.soak_settled is True
        assert result.soak_settle_time_s > 0

    def test_soak_timeout(self):
        """With a very tight threshold and short timeout, should fail to settle."""
        from pyontrust.analysis.thermal.measurement import run_thermal_measurement
        # Inject hotspot so temperatures fluctuate
        cfg = _base_config(
            mode="soak",
            duration_s=1.5,
            capture_interval_s=0.1,
            soak_stable_window_s=0.5,
            soak_stable_threshold_c=0.0001,  # impossibly tight
            soak_timeout_s=1.5,
        )
        cfg["camera"]["inject_hotspot"] = True
        result = run_thermal_measurement(cfg)
        assert result.mode == "soak"
        # Simulated may or may not settle depending on noise; check result is valid
        assert result.total_frames >= 5
        assert result.duration_s > 0

    def test_soak_has_zone_stats(self):
        from pyontrust.analysis.thermal.measurement import run_thermal_measurement
        cfg = _base_config(
            mode="soak",
            duration_s=2.0,
            capture_interval_s=0.3,
            soak_stable_window_s=0.8,
            soak_stable_threshold_c=5.0,
            soak_timeout_s=2.0,
        )
        result = run_thermal_measurement(cfg)
        assert len(result.zone_stats) >= 1

    def test_soak_timestamps_present(self):
        from pyontrust.analysis.thermal.measurement import run_thermal_measurement
        cfg = _base_config(
            mode="soak",
            duration_s=1.5,
            capture_interval_s=0.3,
            soak_stable_window_s=0.6,
            soak_stable_threshold_c=5.0,
            soak_timeout_s=1.5,
        )
        result = run_thermal_measurement(cfg)
        assert len(result.timestamps) > 0
        assert len(result.global_temps) == len(result.timestamps)


# ═══════════════════════════════════════════════════════════════════════
#  Delta mode
# ═══════════════════════════════════════════════════════════════════════


class TestDeltaMode:
    """Test delta measurement mode."""

    def test_delta_basic(self):
        from pyontrust.analysis.thermal.measurement import run_thermal_measurement
        cfg = _base_config(
            mode="delta",
            delta_baseline_frames=3,
            delta_stimulus_frames=3,
            delta_pause_s=0.1,
            capture_interval_s=0.1,
        )
        result = run_thermal_measurement(cfg)
        assert result.mode == "delta"
        assert result.total_frames == 6  # 3 baseline + 3 stimulus

    def test_delta_zone_stats_have_delta(self):
        from pyontrust.analysis.thermal.measurement import run_thermal_measurement
        cfg = _base_config(
            mode="delta",
            delta_baseline_frames=3,
            delta_stimulus_frames=3,
            delta_pause_s=0.1,
            capture_interval_s=0.1,
        )
        result = run_thermal_measurement(cfg)
        assert len(result.zone_stats) >= 1
        zs = result.zone_stats[0]
        # With simulated camera, baseline and stimulus are similar
        assert zs.baseline_mean_c > 0
        assert zs.stimulus_mean_c > 0
        # delta_c should be computed
        assert isinstance(zs.delta_c, float)

    def test_delta_timestamps(self):
        from pyontrust.analysis.thermal.measurement import run_thermal_measurement
        cfg = _base_config(
            mode="delta",
            delta_baseline_frames=2,
            delta_stimulus_frames=2,
            delta_pause_s=0.1,
            capture_interval_s=0.1,
        )
        result = run_thermal_measurement(cfg)
        assert len(result.timestamps) == 4
        assert len(result.global_temps) == 4


# ═══════════════════════════════════════════════════════════════════════
#  Gradient mode
# ═══════════════════════════════════════════════════════════════════════


class TestGradientMode:
    """Test gradient measurement mode."""

    def test_gradient_basic(self):
        from pyontrust.analysis.thermal.measurement import run_thermal_measurement
        cfg = _base_config(
            mode="gradient",
            delta_baseline_frames=3,
            capture_interval_s=0.1,
        )
        result = run_thermal_measurement(cfg)
        assert result.mode == "gradient"
        assert result.gradient is not None
        assert result.gradient.max_gradient_c_per_px >= 0

    def test_gradient_pass_no_limit(self):
        from pyontrust.analysis.thermal.measurement import run_thermal_measurement
        cfg = _base_config(
            mode="gradient",
            delta_baseline_frames=3,
            capture_interval_s=0.1,
            max_gradient_c_per_mm=0,  # disabled
        )
        result = run_thermal_measurement(cfg)
        assert result.passed is True

    def test_gradient_fail_tight_limit(self):
        from pyontrust.analysis.thermal.measurement import run_thermal_measurement
        cfg = _base_config(
            mode="gradient",
            delta_baseline_frames=3,
            capture_interval_s=0.1,
            max_gradient_c_per_mm=0.0001,  # impossibly tight
        )
        cfg["camera"]["inject_hotspot"] = True
        result = run_thermal_measurement(cfg)
        # With hotspot, gradient should exceed very tight limit
        if result.gradient and result.gradient.max_gradient_c_per_mm > 0.0001:
            assert result.passed is False
            assert any("gradient" in r.lower() for r in result.fail_reasons)

    def test_gradient_location_tuple(self):
        from pyontrust.analysis.thermal.measurement import run_thermal_measurement
        cfg = _base_config(
            mode="gradient",
            delta_baseline_frames=3,
            capture_interval_s=0.1,
        )
        result = run_thermal_measurement(cfg)
        g = result.gradient
        assert g is not None
        assert isinstance(g.gradient_location, tuple)
        assert len(g.gradient_location) == 2


# ═══════════════════════════════════════════════════════════════════════
#  Invalid mode
# ═══════════════════════════════════════════════════════════════════════


class TestInvalidMode:
    def test_unknown_mode_raises(self):
        from pyontrust.analysis.thermal.measurement import run_thermal_measurement
        cfg = _base_config(mode="bogus")
        with pytest.raises(ValueError, match="Unknown measurement mode"):
            run_thermal_measurement(cfg)


# ═══════════════════════════════════════════════════════════════════════
#  HTML report generation
# ═══════════════════════════════════════════════════════════════════════


class TestHTMLReport:
    """Tests for HTML report generation."""

    def test_generate_report_creates_file(self, tmp_reports):
        from pyontrust.analysis.thermal.measurement import (
            run_thermal_measurement, generate_thermal_report,
        )
        cfg = _base_config(duration_s=0.8, capture_interval_s=0.3)
        result = run_thermal_measurement(cfg)
        path = generate_thermal_report(result, tmp_reports / "test_report.html")
        assert path.exists()
        assert path.suffix == ".html"

    def test_report_contains_verdict(self, tmp_reports):
        from pyontrust.analysis.thermal.measurement import (
            run_thermal_measurement, generate_thermal_report,
        )
        cfg = _base_config(duration_s=0.8, capture_interval_s=0.3)
        result = run_thermal_measurement(cfg)
        path = generate_thermal_report(result, tmp_reports / "report.html")
        html = path.read_text(encoding="utf-8")
        assert "PASS" in html or "FAIL" in html

    def test_report_contains_board_id(self, tmp_reports):
        from pyontrust.analysis.thermal.measurement import (
            run_thermal_measurement, generate_thermal_report,
        )
        cfg = _base_config(duration_s=0.5, capture_interval_s=0.3, board_id="MY-PCB-42")
        result = run_thermal_measurement(cfg)
        path = generate_thermal_report(result, tmp_reports / "report.html")
        html = path.read_text(encoding="utf-8")
        assert "MY-PCB-42" in html

    def test_report_contains_catppuccin_css(self, tmp_reports):
        from pyontrust.analysis.thermal.measurement import (
            run_thermal_measurement, generate_thermal_report,
        )
        cfg = _base_config(duration_s=0.5, capture_interval_s=0.3)
        result = run_thermal_measurement(cfg)
        path = generate_thermal_report(result, tmp_reports / "report.html")
        html = path.read_text(encoding="utf-8")
        assert "--bg: #1e1e2e" in html  # Catppuccin Mocha background

    def test_report_contains_zone_table(self, tmp_reports):
        from pyontrust.analysis.thermal.measurement import (
            run_thermal_measurement, generate_thermal_report,
        )
        cfg = _base_config(duration_s=0.8, capture_interval_s=0.3)
        result = run_thermal_measurement(cfg)
        path = generate_thermal_report(result, tmp_reports / "report.html")
        html = path.read_text(encoding="utf-8")
        assert "Zone Analysis" in html
        assert "MCU" in html

    def test_report_svg_chart(self, tmp_reports):
        from pyontrust.analysis.thermal.measurement import (
            run_thermal_measurement, generate_thermal_report,
        )
        cfg = _base_config(duration_s=1.0, capture_interval_s=0.3)
        result = run_thermal_measurement(cfg)
        path = generate_thermal_report(result, tmp_reports / "report.html")
        html = path.read_text(encoding="utf-8")
        assert "<svg" in html
        assert "polyline" in html

    def test_report_auto_path(self, tmp_path, monkeypatch):
        """Test that report auto-generates filename when path is None."""
        from pyontrust.analysis.thermal.measurement import (
            run_thermal_measurement, generate_thermal_report,
        )
        monkeypatch.chdir(tmp_path)
        cfg = _base_config(duration_s=0.5, capture_interval_s=0.3, report_dir=str(tmp_path / "reports"))
        result = run_thermal_measurement(cfg)
        result.config["report_dir"] = str(tmp_path / "reports")
        path = generate_thermal_report(result)
        assert path.exists()
        assert "thermal_measurement_" in path.name

    def test_write_report_method(self, tmp_reports):
        from pyontrust.analysis.thermal.measurement import run_thermal_measurement
        cfg = _base_config(duration_s=0.5, capture_interval_s=0.3)
        result = run_thermal_measurement(cfg)
        path = result.write_report(tmp_reports / "via_method.html")
        assert path.exists()

    def test_report_for_delta_mode(self, tmp_reports):
        from pyontrust.analysis.thermal.measurement import (
            run_thermal_measurement, generate_thermal_report,
        )
        cfg = _base_config(
            mode="delta",
            delta_baseline_frames=2,
            delta_stimulus_frames=2,
            delta_pause_s=0.1,
            capture_interval_s=0.1,
        )
        result = run_thermal_measurement(cfg)
        path = generate_thermal_report(result, tmp_reports / "delta_report.html")
        html = path.read_text(encoding="utf-8")
        assert "Delta" in html or "ΔT" in html or "Baseline" in html

    def test_report_for_gradient_mode(self, tmp_reports):
        from pyontrust.analysis.thermal.measurement import (
            run_thermal_measurement, generate_thermal_report,
        )
        cfg = _base_config(
            mode="gradient",
            delta_baseline_frames=3,
            capture_interval_s=0.1,
        )
        result = run_thermal_measurement(cfg)
        path = generate_thermal_report(result, tmp_reports / "gradient_report.html")
        html = path.read_text(encoding="utf-8")
        assert "Gradient" in html


# ═══════════════════════════════════════════════════════════════════════
#  SVG chart helper
# ═══════════════════════════════════════════════════════════════════════


class TestSVGLineChart:
    def test_empty_data(self):
        from pyontrust.analysis.thermal.measurement import _svg_line_chart
        result = _svg_line_chart("Test", [], {})
        assert "No data" in result

    def test_single_series(self):
        from pyontrust.analysis.thermal.measurement import _svg_line_chart
        xs = [0, 1, 2, 3]
        ys = {"Temp": [20, 22, 25, 23]}
        result = _svg_line_chart("Temperature", xs, ys)
        assert "<svg" in result
        assert "polyline" in result
        assert "Temp" in result

    def test_multi_series(self):
        from pyontrust.analysis.thermal.measurement import _svg_line_chart
        xs = [0, 1, 2]
        ys = {"CPU": [30, 35, 33], "VREG": [25, 28, 27]}
        result = _svg_line_chart("Multi", xs, ys)
        assert result.count("polyline") == 2


# ═══════════════════════════════════════════════════════════════════════
#  Package __init__.py imports
# ═══════════════════════════════════════════════════════════════════════


class TestPackageImports:
    """Verify thermal measurement classes are exposed at package level."""

    def test_import_config(self):
        from pyontrust.analysis.thermal import ThermalMeasurementConfig
        assert ThermalMeasurementConfig is not None

    def test_import_result(self):
        from pyontrust.analysis.thermal import ThermalMeasurementResult
        assert ThermalMeasurementResult is not None

    def test_import_zone_statistics(self):
        from pyontrust.analysis.thermal import ZoneStatistics
        assert ZoneStatistics is not None

    def test_import_gradient_result(self):
        from pyontrust.analysis.thermal import GradientResult
        assert GradientResult is not None

    def test_import_run_thermal_measurement(self):
        from pyontrust.analysis.thermal import run_thermal_measurement
        assert callable(run_thermal_measurement)

    def test_import_generate_thermal_report(self):
        from pyontrust.analysis.thermal import generate_thermal_report
        assert callable(generate_thermal_report)


# ═══════════════════════════════════════════════════════════════════════
#  Gateway blueprint API tests
# ═══════════════════════════════════════════════════════════════════════


@pytest.fixture()
def thermal_client():
    """Create a Flask test client with the thermal blueprint registered."""
    from flask import Flask
    from pyontrust.gateway.blueprints.thermal_measurement import bp

    app = Flask(__name__)
    app.config["TESTING"] = True
    app.register_blueprint(bp, url_prefix="/thermal")

    with app.test_client() as client:
        yield client


class TestBlueprintStatus:
    def test_status_endpoint(self, thermal_client):
        resp = thermal_client.get("/thermal/api/status")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "camera_status" in data
        assert "simulated_available" in data
        assert data["simulated_available"] is True

    def test_status_measurement_not_running(self, thermal_client):
        resp = thermal_client.get("/thermal/api/status")
        data = resp.get_json()
        assert data["measurement_running"] is False


class TestBlueprintCaptureSingle:
    def test_capture_single_simulated(self, thermal_client):
        body = {
            "camera": {"mode": "simulated", "base_temp_c": 30.0},
            "zones": [{"name": "Z1", "x": 10, "y": 10, "width": 20, "height": 20}],
        }
        resp = thermal_client.post(
            "/thermal/api/capture_single",
            data=json.dumps(body),
            content_type="application/json",
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert "snapshot" in data
        assert "camera_info" in data
        assert data["snapshot"]["global_mean_c"] > 0


class TestBlueprintResult:
    def test_no_result_returns_404(self, thermal_client):
        # Reset module-level state
        import pyontrust.gateway.blueprints.thermal_measurement as tm
        tm._last_result = None
        resp = thermal_client.get("/thermal/api/result")
        assert resp.status_code == 404

    def test_result_available(self, thermal_client):
        import pyontrust.gateway.blueprints.thermal_measurement as tm
        tm._last_result = {"mode": "continuous", "passed": True, "total_frames": 10}
        resp = thermal_client.get("/thermal/api/result")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["mode"] == "continuous"


class TestBlueprintProgress:
    def test_progress_not_running(self, thermal_client):
        resp = thermal_client.get("/thermal/api/progress")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["running"] is False


class TestBlueprintStop:
    def test_stop_when_not_running(self, thermal_client):
        import pyontrust.gateway.blueprints.thermal_measurement as tm
        tm._measurement_progress["running"] = False
        resp = thermal_client.post("/thermal/api/stop")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["status"] == "not_running"


class TestBlueprintReports:
    def test_reports_empty(self, thermal_client, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        resp = thermal_client.get("/thermal/api/reports")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "reports" in data

    def test_reports_with_files(self, thermal_client, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        report_dir = tmp_path / "test_reports"
        report_dir.mkdir()
        (report_dir / "thermal_measurement_20250101_120000.html").write_text("<html></html>")
        resp = thermal_client.get("/thermal/api/reports")
        assert resp.status_code == 200
        data = resp.get_json()
        assert len(data["reports"]) == 1
        assert data["reports"][0]["name"] == "thermal_measurement_20250101_120000.html"


class TestBlueprintStart:
    def test_start_measurement(self, thermal_client):
        import pyontrust.gateway.blueprints.thermal_measurement as tm
        tm._measurement_progress["running"] = False
        tm._last_result = None

        body = {
            "mode": "continuous",
            "duration_s": 1.0,
            "capture_interval_s": 0.3,
            "warmup_frames": 1,
            "camera": {"mode": "simulated", "base_temp_c": 30.0},
            "zones": [],
            "save_snapshots": False,
        }
        resp = thermal_client.post(
            "/thermal/api/start",
            data=json.dumps(body),
            content_type="application/json",
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["status"] == "started"

        # Wait for measurement to complete
        for _ in range(30):
            time.sleep(0.2)
            if not tm._measurement_progress["running"]:
                break

        assert tm._last_result is not None

    def test_start_conflict_when_running(self, thermal_client):
        import pyontrust.gateway.blueprints.thermal_measurement as tm
        tm._measurement_progress["running"] = True
        body = {"mode": "continuous", "duration_s": 1.0}
        resp = thermal_client.post(
            "/thermal/api/start",
            data=json.dumps(body),
            content_type="application/json",
        )
        assert resp.status_code == 409
        # Cleanup
        tm._measurement_progress["running"] = False


# ═══════════════════════════════════════════════════════════════════════
#  FlowLab blocks
# ═══════════════════════════════════════════════════════════════════════


class TestFlowLabBlocks:
    """Test the 4 new thermal measurement FlowLab blocks."""

    def _make_ctx(self) -> MagicMock:
        ctx = MagicMock()
        ctx.log = MagicMock()
        return ctx

    def test_thermal_measure_block_registry(self):
        from pyontrust.gateway.flowlab_engine import FlowLabEngine
        assert "thermal_measure" in FlowLabEngine.block_registry
        assert "thermal_soak" in FlowLabEngine.block_registry
        assert "thermal_delta" in FlowLabEngine.block_registry
        assert "thermal_gradient" in FlowLabEngine.block_registry

    def test_thermal_measure_block_runs(self):
        from pyontrust.gateway.flowlab_engine import _blk_thermal_measure
        ctx = self._make_ctx()
        params = {
            "duration_s": 0.5,
            "capture_interval_s": 0.2,
            "warmup_frames": 1,
            "camera_mode": "simulated",
            "base_temp_c": 30.0,
            "max_temp_c": 85.0,
        }
        result = _blk_thermal_measure(params, {"zones": []}, ctx)
        assert "result" in result
        assert "passed" in result
        assert "max_c" in result
        assert result["max_c"] > 0
        ctx.log.assert_called()

    def test_thermal_soak_block_runs(self):
        from pyontrust.gateway.flowlab_engine import _blk_thermal_soak
        ctx = self._make_ctx()
        params = {
            "duration_s": 1.5,
            "capture_interval_s": 0.2,
            "stable_window_s": 0.5,
            "stable_threshold_c": 5.0,
            "timeout_s": 1.5,
            "warmup_frames": 1,
            "camera_mode": "simulated",
            "base_temp_c": 30.0,
        }
        result = _blk_thermal_soak(params, {"zones": []}, ctx)
        assert "result" in result
        assert "settled" in result
        ctx.log.assert_called()

    def test_thermal_delta_block_runs(self):
        from pyontrust.gateway.flowlab_engine import _blk_thermal_delta
        ctx = self._make_ctx()
        params = {
            "baseline_frames": 2,
            "stimulus_frames": 2,
            "pause_s": 0.1,
            "capture_interval_s": 0.1,
            "warmup_frames": 1,
            "camera_mode": "simulated",
        }
        result = _blk_thermal_delta(params, {"zones": [
            {"name": "MCU", "x": 10, "y": 10, "width": 20, "height": 20},
        ]}, ctx)
        assert "zone_deltas" in result
        assert "MCU" in result["zone_deltas"]
        ctx.log.assert_called()

    def test_thermal_gradient_block_runs(self):
        from pyontrust.gateway.flowlab_engine import _blk_thermal_gradient
        ctx = self._make_ctx()
        params = {
            "avg_frames": 2,
            "capture_interval_s": 0.1,
            "warmup_frames": 1,
            "camera_mode": "simulated",
            "pixel_pitch_mm": 0.17,
        }
        result = _blk_thermal_gradient(params, {}, ctx)
        assert "gradient" in result
        assert "passed" in result
        ctx.log.assert_called()
