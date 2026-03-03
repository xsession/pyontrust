"""Tests for limits.py — Verdict, Limit checking, TestSpec, evaluate()."""

from __future__ import annotations

import unittest

from pyontrust_packages.power_test_framework.limits import (
    Limit,
    LimitResult,
    StepLimits,
    TestSpec,
    TestVerdict,
    Verdict,
    evaluate,
)
from pyontrust_packages.power_test_framework.core import PowerSummary


class TestVerdictEnum(unittest.TestCase):
    def test_values_exist(self):
        self.assertEqual(Verdict.PASS.value, "PASS")
        self.assertEqual(Verdict.FAIL.value, "FAIL")
        self.assertEqual(Verdict.WARN.value, "WARN")
        self.assertEqual(Verdict.SKIP.value, "SKIP")
        self.assertEqual(Verdict.ERROR.value, "ERROR")


class TestLimit(unittest.TestCase):
    def test_pass_within_range(self):
        lim = Limit(min=0.0, max=10.0)
        v = lim.check(5.0)
        self.assertEqual(v, Verdict.PASS)

    def test_fail_above_max(self):
        lim = Limit(max=10.0)
        v = lim.check(15.0)
        self.assertEqual(v, Verdict.FAIL)

    def test_fail_below_min(self):
        lim = Limit(min=1.0)
        v = lim.check(0.5)
        self.assertEqual(v, Verdict.FAIL)

    def test_warn_above_warn_max(self):
        lim = Limit(max=10.0, warn_max=8.0)
        v = lim.check(9.0)
        self.assertEqual(v, Verdict.WARN)

    def test_warn_below_warn_min(self):
        lim = Limit(min=1.0, warn_min=2.0)
        v = lim.check(1.5)
        self.assertEqual(v, Verdict.WARN)

    def test_pass_no_limits(self):
        lim = Limit()
        v = lim.check(999.0)
        self.assertEqual(v, Verdict.PASS)

    def test_exact_boundary_pass(self):
        lim = Limit(max=10.0)
        v = lim.check(10.0)
        # 10.0 is not > 10.0, so PASS
        self.assertEqual(v, Verdict.PASS)

    def test_from_dict(self):
        d = {"min": 0.0, "max": 10.0, "warn_max": 8.0}
        lim = Limit(**d)
        self.assertEqual(lim.min, 0.0)
        self.assertEqual(lim.max, 10.0)
        self.assertEqual(lim.warn_max, 8.0)

    def test_describe(self):
        lim = Limit(min=1.0, max=10.0, unit="A")
        desc = lim.describe()
        self.assertIn("min=", desc)
        self.assertIn("max=", desc)
        self.assertIn("[A]", desc)


class TestStepLimits(unittest.TestCase):
    def test_check_all_pass(self):
        sl = StepLimits(limits={
            "avg_current_a": Limit(max=10e-6),
            "max_current_a": Limit(max=50e-6),
        })
        measurements = {"avg_current_a": 5e-6, "max_current_a": 20e-6}
        results = sl.check("sleep", measurements)
        self.assertEqual(len(results), 2)
        for r in results:
            self.assertEqual(r.verdict, Verdict.PASS)
            self.assertEqual(r.step_name, "sleep")

    def test_check_fail(self):
        sl = StepLimits(limits={"avg_current_a": Limit(max=1e-6)})
        measurements = {"avg_current_a": 5e-6}
        results = sl.check("step1", measurements)
        self.assertEqual(results[0].verdict, Verdict.FAIL)

    def test_missing_metric_error(self):
        sl = StepLimits(limits={"avg_current_a": Limit(max=10e-6)})
        results = sl.check("step1", {})  # no measurements
        self.assertEqual(results[0].verdict, Verdict.ERROR)


class TestSpecFromDict(unittest.TestCase):
    """Test TestSpec.from_dict parsing."""

    def test_from_dict(self):
        d = {
            "steps": {
                "idle_sleep": {
                    "avg_current_a": {"max": 10e-6, "warn_max": 7e-6},
                    "max_current_a": {"max": 50e-6},
                },
                "active": {
                    "avg_current_a": {"max": 50e-3},
                },
            }
        }
        spec = TestSpec.from_dict(d)
        self.assertIn("idle_sleep", spec.step_limits)
        self.assertIn("active", spec.step_limits)
        self.assertEqual(len(spec.step_limits["idle_sleep"].limits), 2)

    def test_from_dict_with_overall(self):
        d = {
            "steps": {},
            "overall": {
                "energy_j": {"max": 0.1},
            },
        }
        spec = TestSpec.from_dict(d)
        self.assertIn("energy_j", spec.overall_limits.limits)

    def test_empty(self):
        spec = TestSpec.from_dict({})
        self.assertEqual(len(spec.step_limits), 0)


def _make_measurements(avg_i: float = 5e-6, max_i: float = 20e-6) -> dict[str, float]:
    return {
        "duration_s": 10.0,
        "samples": 1000,
        "avg_current_a": avg_i,
        "max_current_a": max_i,
        "avg_voltage_v": 3.3,
        "charge_c": avg_i * 10.0,
        "energy_j": avg_i * 3.3 * 10.0,
        "avg_power_w": avg_i * 3.3,
    }


class TestEvaluate(unittest.TestCase):
    def test_all_pass(self):
        spec = TestSpec.from_dict({
            "steps": {
                "sleep": {"avg_current_a": {"max": 10e-6}},
            }
        })
        step_summaries = {"sleep": _make_measurements(avg_i=5e-6)}
        verdict = evaluate(spec, overall_summary={}, step_summaries=step_summaries)
        self.assertEqual(verdict.overall, Verdict.PASS)

    def test_one_fail(self):
        spec = TestSpec.from_dict({
            "steps": {
                "sleep": {"avg_current_a": {"max": 1e-6}},
            }
        })
        step_summaries = {"sleep": _make_measurements(avg_i=5e-6)}
        verdict = evaluate(spec, overall_summary={}, step_summaries=step_summaries)
        self.assertEqual(verdict.overall, Verdict.FAIL)

    def test_missing_step_error(self):
        spec = TestSpec.from_dict({
            "steps": {
                "sleep": {"avg_current_a": {"max": 10e-6}},
                "active": {"avg_current_a": {"max": 50e-3}},
            }
        })
        # Only provide 'sleep'; 'active' has no data → ERROR for missing metrics
        step_summaries = {"sleep": _make_measurements(avg_i=5e-6)}
        verdict = evaluate(spec, overall_summary={}, step_summaries=step_summaries)
        self.assertEqual(verdict.overall, Verdict.ERROR)

    def test_warn_verdict(self):
        spec = TestSpec.from_dict({
            "steps": {
                "sleep": {"avg_current_a": {"max": 10e-6, "warn_max": 4e-6}},
            }
        })
        step_summaries = {"sleep": _make_measurements(avg_i=5e-6)}
        verdict = evaluate(spec, overall_summary={}, step_summaries=step_summaries)
        self.assertEqual(verdict.overall, Verdict.WARN)

    def test_empty_spec_skip(self):
        spec = TestSpec()
        verdict = evaluate(spec, overall_summary={})
        self.assertEqual(verdict.overall, Verdict.SKIP)

    def test_verdict_results_populated(self):
        spec = TestSpec.from_dict({
            "steps": {
                "s1": {"avg_current_a": {"max": 10e-6}},
            }
        })
        step_summaries = {"s1": _make_measurements()}
        verdict = evaluate(spec, overall_summary={}, step_summaries=step_summaries)
        self.assertGreater(len(verdict.results), 0)

    def test_overall_limits(self):
        spec = TestSpec.from_dict({
            "overall": {"energy_j": {"max": 0.001}},
        })
        overall = _make_measurements(avg_i=5e-6)
        verdict = evaluate(spec, overall_summary=overall)
        self.assertEqual(verdict.overall, Verdict.PASS)

    def test_verdict_to_dict(self):
        verdict = TestVerdict(overall=Verdict.PASS, results=[])
        d = verdict.to_dict()
        self.assertEqual(d["verdict"], "PASS")
        self.assertTrue(d["passed"])

    def test_verdict_passed_property(self):
        self.assertTrue(TestVerdict(overall=Verdict.PASS).passed)
        self.assertFalse(TestVerdict(overall=Verdict.FAIL).passed)


if __name__ == "__main__":
    unittest.main()
