import pathlib
import sys
import tempfile
import unittest

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.append(str(REPO_ROOT / "pyontrust_packages"))

from power_test_framework.core import PowerTest, PowerTestRunner, TestStep  # noqa: E402
from power_test_framework.instruments.simulated import SimulatedPowerMeter  # noqa: E402


class TestSimulatedPowerFramework(unittest.TestCase):
    def test_runner_produces_artifacts(self):
        meter = SimulatedPowerMeter(sample_rate_hz=200.0, voltage_v=3.0)

        def active(ctx):
            ctx.instruments["power_meter"].set_mode("active")

        def sleep(ctx):
            ctx.instruments["power_meter"].set_mode("sleep")

        test = PowerTest(
            name="unit_simulated",
            description="Unit test simulated run",
            steps=[
                TestStep(name="active", duration_s=0.2, action=active),
                TestStep(name="sleep", duration_s=0.2, action=sleep),
            ],
        )

        with tempfile.TemporaryDirectory() as tmp:
            runner = PowerTestRunner(artifacts_root=tmp)
            artifacts = runner.run(test=test, instruments={"power_meter": meter})

            self.assertTrue(artifacts.meta_path.exists())
            self.assertTrue(artifacts.trace_csv_path.exists())
            self.assertTrue(artifacts.summary_json_path.exists())
            self.assertTrue(artifacts.report_md_path.exists())


if __name__ == "__main__":
    unittest.main()
