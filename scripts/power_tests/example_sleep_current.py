import pathlib
import sys
import time

# Allow running from repo root without installing as a package.
REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.append(str(REPO_ROOT / "pyontrust_packages"))

from power_test_framework.core import PowerTest, PowerTestRunner, TestStep  # noqa: E402
from power_test_framework.instruments.simulated import SimulatedPowerMeter  # noqa: E402


def main() -> None:
    meter = SimulatedPowerMeter(sample_rate_hz=500.0, voltage_v=3.0)

    def go_active(ctx):
        ctx.instruments["power_meter"].set_mode("active")

    def go_sleep(ctx):
        ctx.instruments["power_meter"].set_mode("sleep")

    # Example: active burst then sleep.
    test = PowerTest(
        name="example_sleep_current",
        description="Simulated test: active burst then sleep.",
        steps=[
            TestStep(name="active", duration_s=1.0, action=go_active),
            TestStep(name="sleep", duration_s=2.0, action=go_sleep),
        ],
    )

    runner = PowerTestRunner(artifacts_root=str(REPO_ROOT / "artifacts"))
    artifacts = runner.run(test=test, instruments={"power_meter": meter}, meta={"note": "simulated"})
    print(f"Artifacts written to: {artifacts.root_dir}")

    # Tiny pause so users see output when double-clicking.
    time.sleep(0.1)


if __name__ == "__main__":
    main()
