"""Tests for AOI models — stdlib only, no optional dependencies required."""

from __future__ import annotations

import unittest

from pyontrust.analysis.aoi.models import (
    AOIVerdict,
    AlignmentResult,
    Defect,
    DefectType,
    InspectionResult,
    SolderJointResult,
    ViaFillResult,
)


class TestDefectType(unittest.TestCase):
    def test_all_values_unique(self):
        values = [dt.value for dt in DefectType]
        self.assertEqual(len(values), len(set(values)))

    def test_missing_component(self):
        self.assertEqual(DefectType.MISSING_COMPONENT.value, "missing_component")

    def test_via_void(self):
        self.assertEqual(DefectType.VIA_VOID.value, "via_void")


class TestAOIVerdict(unittest.TestCase):
    def test_values(self):
        self.assertEqual(AOIVerdict.PASS.value, "PASS")
        self.assertEqual(AOIVerdict.FAIL.value, "FAIL")
        self.assertEqual(AOIVerdict.WARN.value, "WARN")
        self.assertEqual(AOIVerdict.REVIEW.value, "REVIEW")


class TestDefect(unittest.TestCase):
    def test_to_dict(self):
        d = Defect(
            defect_type=DefectType.SOLDER_BRIDGE,
            x=10, y=20, width=30, height=15,
            confidence=0.85,
            description="test defect",
        )
        out = d.to_dict()
        self.assertEqual(out["defect_type"], "solder_bridge")
        self.assertEqual(out["x"], 10)
        self.assertEqual(out["confidence"], 0.85)
        self.assertEqual(out["severity"], "FAIL")

    def test_default_severity_is_fail(self):
        d = Defect(DefectType.TOMBSTONE, 0, 0, 10, 10, 0.5)
        self.assertEqual(d.severity, AOIVerdict.FAIL)

    def test_custom_severity(self):
        d = Defect(DefectType.CONTAMINATION, 0, 0, 10, 10, 0.3, severity=AOIVerdict.WARN)
        self.assertEqual(d.severity, AOIVerdict.WARN)


class TestSolderJointResult(unittest.TestCase):
    def test_to_dict(self):
        r = SolderJointResult(
            x=100, y=200, area_px=150.0, circularity=0.8,
            mean_intensity=180.0, std_intensity=10.0,
            wetting_angle_deg=25.0, grade="GOOD",
        )
        out = r.to_dict()
        self.assertEqual(out["grade"], "GOOD")
        self.assertEqual(out["area_px"], 150.0)


class TestAlignmentResult(unittest.TestCase):
    def test_within_tolerance(self):
        r = AlignmentResult("U1", 0.01, -0.02, 0.1, True)
        self.assertTrue(r.within_tolerance)
        out = r.to_dict()
        self.assertEqual(out["component_id"], "U1")

    def test_out_of_tolerance(self):
        r = AlignmentResult("R5", 0.5, 0.3, 2.0, False)
        self.assertFalse(r.within_tolerance)


class TestViaFillResult(unittest.TestCase):
    def test_full_via(self):
        r = ViaFillResult(0, 50, 60, 20.0, 0.95, 0, "FULL")
        self.assertEqual(r.grade, "FULL")
        self.assertEqual(r.fill_ratio, 0.95)

    def test_void_via(self):
        r = ViaFillResult(1, 100, 100, 18.0, 0.3, 2, "VOID")
        self.assertEqual(r.grade, "VOID")
        out = r.to_dict()
        self.assertEqual(out["void_count"], 2)


class TestInspectionResult(unittest.TestCase):
    def setUp(self):
        self.defects = [
            Defect(DefectType.SOLDER_BRIDGE, 10, 20, 30, 15, 0.9),
            Defect(DefectType.MISSING_COMPONENT, 100, 50, 40, 40, 0.7),
        ]
        self.solder = [
            SolderJointResult(50, 50, 200, 0.8, 180, 10, 25, "GOOD"),
            SolderJointResult(80, 80, 100, 0.3, 120, 55, 65, "COLD"),
        ]
        self.via = [
            ViaFillResult(0, 200, 200, 20, 0.95, 0, "FULL"),
            ViaFillResult(1, 250, 250, 18, 0.4, 3, "VOID"),
        ]

    def test_passed(self):
        result = InspectionResult("SN-001", AOIVerdict.PASS)
        self.assertTrue(result.passed)

    def test_failed(self):
        result = InspectionResult("SN-002", AOIVerdict.FAIL)
        self.assertFalse(result.passed)

    def test_total_defect_count(self):
        result = InspectionResult(
            board_id="SN-003",
            verdict=AOIVerdict.FAIL,
            defects=self.defects,
            solder_results=self.solder,
            via_results=self.via,
        )
        # 2 visual defects + 1 cold joint + 1 void via = 4
        self.assertEqual(result.total_defect_count, 4)

    def test_total_defect_count_all_good(self):
        result = InspectionResult(
            board_id="SN-004",
            verdict=AOIVerdict.PASS,
            solder_results=[SolderJointResult(0, 0, 100, 0.8, 180, 10, 25, "GOOD")],
            via_results=[ViaFillResult(0, 0, 0, 20, 0.95, 0, "FULL")],
        )
        self.assertEqual(result.total_defect_count, 0)

    def test_to_dict(self):
        result = InspectionResult(
            board_id="SN-005",
            verdict=AOIVerdict.WARN,
            defects=self.defects,
            metrics={"time_total_s": 0.5},
        )
        out = result.to_dict()
        self.assertEqual(out["board_id"], "SN-005")
        self.assertEqual(out["verdict"], "WARN")
        self.assertEqual(out["defect_count"], 2)
        self.assertEqual(len(out["defects"]), 2)
        self.assertEqual(out["metrics"]["time_total_s"], 0.5)

    def test_empty_result(self):
        result = InspectionResult("SN-006", AOIVerdict.PASS)
        self.assertEqual(result.total_defect_count, 0)
        out = result.to_dict()
        self.assertEqual(out["defect_count"], 0)
        self.assertEqual(out["defects"], [])


if __name__ == "__main__":
    unittest.main()
