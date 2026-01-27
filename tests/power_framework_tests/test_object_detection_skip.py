import pathlib
import tempfile
import unittest

from pyontrust_packages.power_test_framework.vision_object_detector import ObjectDetectConfig, analyze_video_objects


class TestObjectDetectionSkip(unittest.TestCase):
    def test_skips_when_ml_missing_and_no_bootstrap(self):
        with tempfile.TemporaryDirectory() as td:
            root = pathlib.Path(td)
            video = root / "dummy.mp4"
            video.write_bytes(b"not a real video")

            cfg = ObjectDetectConfig(bootstrap_ml=False)
            summary = analyze_video_objects(
                artifacts_root=root,
                video_path=video,
                cfg=cfg,
                _ultralytics_module="definitely_not_a_real_module_name_xyz",
            )

            self.assertTrue(summary.get("ok"))
            self.assertTrue(summary.get("skipped"))
            self.assertIn("reason", summary)
            self.assertTrue((root / "object_summary.json").exists())
            self.assertTrue((root / "object_events.jsonl").exists())


if __name__ == "__main__":
    unittest.main()
