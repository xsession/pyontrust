import json
import pathlib
import sys
import tempfile
import unittest


REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.append(str(REPO_ROOT / "pyontrust_packages"))

from power_test_framework.profiles import load_profile, run_profile  # noqa: E402


class TestProfileRunner(unittest.TestCase):
    def test_profile_runs_and_writes_artifacts(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = pathlib.Path(tmp)
            profile_path = tmp_path / "profile.json"
            artifacts_root = tmp_path / "artifacts"
            profile = {
                "name": "unit_profile",
                "description": "unit",
                "artifacts_root": str(artifacts_root),
                "instruments": {"power_meter": {"type": "simulated", "sample_rate_hz": 50, "voltage_v": 3.0}},
                "recorders": [
                    {
                        "type": "process",
                        "name": "dummy",
                        "command": [
                            sys.executable,
                            "-c",
                            "import time; print('hello'); time.sleep(0.2); print('bye')",
                        ],
                        "skip_if_missing": False,
                    }
                ],
                "steps": [
                    {"name": "active", "duration_s": 0.2, "actions": [{"type": "set_power_mode", "mode": "active"}]},
                    {"name": "sleep", "duration_s": 0.2, "actions": [{"type": "set_power_mode", "mode": "sleep"}]},
                ],
            }
            profile_path.write_text(json.dumps(profile), encoding="utf-8")

            p = load_profile(profile_path)
            out_dir = run_profile(p, repo_root=REPO_ROOT)

            out = pathlib.Path(out_dir)
            self.assertTrue((out / "meta.json").exists())
            self.assertTrue((out / "markers.json").exists())
            self.assertTrue((out / "power_trace.csv").exists())
            self.assertTrue((out / "summary.json").exists())
            self.assertTrue((out / "report.md").exists())
            self.assertTrue((out / "recorders" / "dummy.log").exists())


if __name__ == "__main__":
    unittest.main()
