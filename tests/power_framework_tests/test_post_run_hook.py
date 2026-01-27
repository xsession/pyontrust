import pathlib
import tempfile
import unittest

from pyontrust_packages.power_test_framework.core import PowerTest, PowerTestRunner, TestStep
from pyontrust_packages.power_test_framework.instruments.simulated import SimulatedPowerMeter


class TestPostRunHook(unittest.TestCase):
    def test_post_run_called_and_can_add_marker(self):
        with tempfile.TemporaryDirectory() as td:
            artifacts_root = pathlib.Path(td)

            test = PowerTest(
                name="post_run_hook",
                description="",
                steps=[TestStep(name="noop", duration_s=0.01, action=lambda ctx: None)],
            )

            runner = PowerTestRunner(artifacts_root=artifacts_root)

            def post_run(ctx):
                ctx.mark("post_run_marker", x=1)

            artifacts = runner.run(
                test=test,
                instruments={"power_meter": SimulatedPowerMeter(sample_rate_hz=50.0, voltage_v=3.3)},
                post_run=post_run,
            )

            markers = (pathlib.Path(artifacts.markers_json_path)).read_text(encoding="utf-8")
            self.assertIn("post_run_marker", markers)


if __name__ == "__main__":
    unittest.main()
