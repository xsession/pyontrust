"""Test runner for scenario YAML files.

Executes test scenarios defined in YAML format using the UnifiedHIL
bridge, supporting both real hardware and simulation.

Example usage:
    python -m pyontrust.simulation.scenario_runner scenarios/locator_base_blink_test.yaml
"""

from __future__ import annotations

import argparse
import logging
import re
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

from pyontrust.simulation.hil_bridge import BackendType, UnifiedHIL
from pyontrust.simulation.runner import SimulationDataLogger, SignalSample

logger = logging.getLogger("pyontrust.scenario_runner")


class TestResult(Enum):
    """Test execution result."""
    PASSED = "passed"
    FAILED = "failed"
    SKIPPED = "skipped"
    ERROR = "error"


@dataclass
class StepResult:
    """Result of a single test step."""
    step_type: str
    description: str
    result: TestResult
    duration_s: float = 0.0
    message: str = ""
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class TestCaseResult:
    """Result of a test case."""
    name: str
    description: str
    result: TestResult
    steps: List[StepResult] = field(default_factory=list)
    duration_s: float = 0.0


@dataclass
class ScenarioResult:
    """Result of the entire scenario."""
    name: str
    start_time: datetime
    end_time: Optional[datetime] = None
    tests: List[TestCaseResult] = field(default_factory=list)
    
    @property
    def duration_s(self) -> float:
        if self.end_time:
            return (self.end_time - self.start_time).total_seconds()
        return 0.0
    
    @property
    def passed(self) -> int:
        return sum(1 for t in self.tests if t.result == TestResult.PASSED)
    
    @property
    def failed(self) -> int:
        return sum(1 for t in self.tests if t.result == TestResult.FAILED)
    
    @property
    def total(self) -> int:
        return len(self.tests)


def parse_duration(duration_str: str) -> float:
    """Parse duration string to seconds (e.g., '100ms', '2s', '1.5min')."""
    match = re.match(r"(\d+\.?\d*)\s*(us|µs|ms|s|min|m)?", duration_str.strip().lower())
    if not match:
        raise ValueError(f"Invalid duration: {duration_str}")
    
    value = float(match.group(1))
    unit = match.group(2) or "s"
    
    multipliers = {
        "us": 1e-6, "µs": 1e-6,
        "ms": 1e-3,
        "s": 1.0,
        "min": 60.0, "m": 60.0,
    }
    
    return value * multipliers.get(unit, 1.0)


def expand_variables(value: str, variables: Dict[str, str]) -> str:
    """Expand ${VAR} variables in a string."""
    if not isinstance(value, str):
        return value
    
    def replace_var(match):
        var_name = match.group(1)
        return variables.get(var_name, match.group(0))
    
    return re.sub(r"\$\{(\w+)\}", replace_var, value)


class ScenarioRunner:
    """Runs test scenarios from YAML definitions."""
    
    def __init__(
        self,
        scenario_path: Path,
        output_dir: Optional[Path] = None,
        backend_override: Optional[BackendType] = None,
        firmware_override: Optional[Path] = None,
    ):
        self.scenario_path = Path(scenario_path)
        self.output_dir = output_dir or Path("test_output")
        self.backend_override = backend_override
        self.firmware_override = firmware_override
        
        self.scenario: Dict[str, Any] = {}
        self.variables: Dict[str, str] = {}
        self.hil: Optional[UnifiedHIL] = None
        self.logger: Optional[SimulationDataLogger] = None
        self.pins: Dict[str, Dict[str, Any]] = {}
        
        self.result: Optional[ScenarioResult] = None
    
    def load(self) -> None:
        """Load the scenario YAML file."""
        with open(self.scenario_path) as f:
            self.scenario = yaml.safe_load(f)
        
        # Setup variables
        self.variables = {
            "WORKSPACE": str(self.scenario_path.parent.parent),
            "OUTPUT": str(self.output_dir),
            "SCENARIO_DIR": str(self.scenario_path.parent),
        }
        
        # Parse pin mappings
        pins_config = self.scenario.get("pins", {})
        for name, config in pins_config.items():
            self.pins[name] = {
                "mcu_pin": config.get("mcu_pin"),
                "ad3_dio": config.get("ad3_dio"),
                "direction": config.get("direction", "input"),
            }
        
        logger.info(f"Loaded scenario: {self.scenario.get('scenario', {}).get('name', 'Unknown')}")
    
    def setup(self) -> None:
        """Setup HIL backend and logging."""
        # Determine backend type
        backend_config = self.scenario.get("backend", "auto")
        if self.backend_override:
            backend_type = self.backend_override
        else:
            backend_map = {
                "auto": BackendType.AUTO,
                "hardware": BackendType.HARDWARE,
                "simulation": BackendType.SIMULATION,
                "mock": BackendType.MOCK,
            }
            backend_type = backend_map.get(backend_config, BackendType.AUTO)
        
        # Get firmware path
        firmware_path = None
        if self.firmware_override:
            firmware_path = str(self.firmware_override)
        elif "target" in self.scenario:
            fw = self.scenario["target"].get("firmware")
            if fw:
                firmware_path = expand_variables(fw, self.variables)
        
        # Create HIL interface
        self.hil = UnifiedHIL(
            backend_type=backend_type,
            firmware_path=firmware_path,
        )
        self.hil.open()
        
        # Setup data logger
        self.output_dir.mkdir(parents=True, exist_ok=True)
        log_config = self.scenario.get("logging", {})
        formats = log_config.get("formats", ["csv"])
        
        # Get signals to monitor
        signals = [s.get("name", "") for s in log_config.get("signals", [])]
        if not signals:
            signals = list(self.pins.keys())
        
        self.logger = SimulationDataLogger(
            output_dir=str(self.output_dir),
            prefix=self.scenario.get("scenario", {}).get("name", "test").replace(" ", "_").lower(),
        )
        self.logger.start(signals=signals)
        
        logger.info(f"HIL setup complete (backend: {'simulation' if self.hil.is_simulation else 'hardware'})")
    
    def teardown(self) -> None:
        """Cleanup resources."""
        if self.logger:
            self.logger.stop()
        if self.hil:
            self.hil.close()
    
    def run(self) -> ScenarioResult:
        """Run all tests in the scenario."""
        scenario_info = self.scenario.get("scenario", {})
        self.result = ScenarioResult(
            name=scenario_info.get("name", "Unknown"),
            start_time=datetime.now(),
        )
        
        # Run hooks
        self._run_hooks("before_all")
        
        # Run each test
        tests = self.scenario.get("tests", [])
        for test in tests:
            test_result = self._run_test(test)
            self.result.tests.append(test_result)
            
            # Run after_each hooks
            self._run_hooks("after_each", test_result=test_result)
        
        # Run hooks
        self._run_hooks("after_all")
        
        self.result.end_time = datetime.now()
        return self.result
    
    def _run_test(self, test: Dict[str, Any]) -> TestCaseResult:
        """Run a single test case."""
        test_name = test.get("name", "Unnamed Test")
        test_desc = test.get("description", "")
        
        logger.info(f"Running test: {test_name}")
        
        result = TestCaseResult(
            name=test_name,
            description=test_desc,
            result=TestResult.PASSED,
        )
        
        start_time = time.time()
        
        try:
            steps = test.get("steps", [])
            for step in steps:
                step_result = self._run_step(step)
                result.steps.append(step_result)
                
                if step_result.result == TestResult.FAILED:
                    result.result = TestResult.FAILED
                    break
                    
        except Exception as e:
            logger.exception(f"Error in test {test_name}")
            result.result = TestResult.ERROR
            result.steps.append(StepResult(
                step_type="error",
                description=str(e),
                result=TestResult.ERROR,
            ))
        
        result.duration_s = time.time() - start_time
        
        status = "✓" if result.result == TestResult.PASSED else "✗"
        logger.info(f"  {status} {test_name} ({result.duration_s:.3f}s)")
        
        return result
    
    def _run_step(self, step: Dict[str, Any]) -> StepResult:
        """Run a single test step."""
        start_time = time.time()
        
        # Determine step type
        if "wait" in step:
            return self._step_wait(step, start_time)
        elif "set" in step:
            return self._step_set(step, start_time)
        elif "assert" in step:
            return self._step_assert(step, start_time)
        elif "capture" in step:
            return self._step_capture(step, start_time)
        elif "analyze" in step:
            return self._step_analyze(step, start_time)
        else:
            return StepResult(
                step_type="unknown",
                description=str(step),
                result=TestResult.SKIPPED,
                duration_s=time.time() - start_time,
            )
    
    def _step_wait(self, step: Dict[str, Any], start_time: float) -> StepResult:
        """Execute a wait step."""
        duration = parse_duration(str(step["wait"]))
        
        if self.hil.is_simulation:
            self.hil.advance_simulation(duration)
        else:
            time.sleep(duration)
        
        return StepResult(
            step_type="wait",
            description=f"Wait {step['wait']}",
            result=TestResult.PASSED,
            duration_s=time.time() - start_time,
        )
    
    def _step_set(self, step: Dict[str, Any], start_time: float) -> StepResult:
        """Execute a set (write) step."""
        config = step["set"]
        pin_name = config["pin"]
        state = config["state"]
        
        # Resolve pin to actual pin name
        pin_config = self.pins.get(pin_name, {})
        actual_pin = pin_config.get("mcu_pin", pin_name)
        
        # Write value
        value = state.lower() in ("high", "1", "true")
        self.hil.digital_write(actual_pin, value)
        
        # Log signal
        if self.logger:
            sample = SignalSample(
                timestamp_s=self.hil.sim_time if self.hil.is_simulation else time.time(),
                signal_name=pin_name,
                value=1.0 if value else 0.0,
                domain="digital",
            )
            self.logger.log_sample(sample)
        
        return StepResult(
            step_type="set",
            description=f"Set {pin_name} = {state}",
            result=TestResult.PASSED,
            duration_s=time.time() - start_time,
        )
    
    def _step_assert(self, step: Dict[str, Any], start_time: float) -> StepResult:
        """Execute an assert step."""
        config = step["assert"]
        pin_name = config["pin"]
        expected_state = config["state"]
        message = config.get("message", f"Pin {pin_name} state check")
        
        # Resolve pin
        pin_config = self.pins.get(pin_name, {})
        actual_pin = pin_config.get("mcu_pin", pin_name)
        
        # Read value
        actual_value = self.hil.digital_read(actual_pin)
        expected_value = expected_state.lower() in ("high", "1", "true")
        
        passed = actual_value == expected_value
        
        return StepResult(
            step_type="assert",
            description=f"Assert {pin_name} == {expected_state}",
            result=TestResult.PASSED if passed else TestResult.FAILED,
            duration_s=time.time() - start_time,
            message="" if passed else f"Expected {expected_state}, got {'high' if actual_value else 'low'}",
            details={
                "pin": pin_name,
                "expected": expected_state,
                "actual": "high" if actual_value else "low",
                "message": message,
            },
        )
    
    def _step_capture(self, step: Dict[str, Any], start_time: float) -> StepResult:
        """Execute a capture step (record signal for analysis)."""
        config = step["capture"]
        pin_name = config["pin"]
        duration = parse_duration(config.get("duration", "1s"))
        sample_rate = self._parse_rate(config.get("sample_rate", "10kHz"))
        
        num_samples = int(duration * sample_rate)
        samples = []
        
        # Resolve pin
        pin_config = self.pins.get(pin_name, {})
        actual_pin = pin_config.get("mcu_pin", pin_name)
        
        # Capture samples
        sample_interval = 1.0 / sample_rate
        for i in range(num_samples):
            value = self.hil.digital_read(actual_pin)
            samples.append((i * sample_interval, 1 if value else 0))
            
            if self.hil.is_simulation:
                self.hil.advance_simulation(sample_interval)
            else:
                time.sleep(sample_interval)
            
            # Log to data logger
            if self.logger:
                sample = SignalSample(
                    timestamp_s=i * sample_interval,
                    signal_name=pin_name,
                    value=1.0 if value else 0.0,
                    domain="digital",
                )
                self.logger.log_sample(sample)
        
        # Store capture for analysis
        self._captures = getattr(self, "_captures", {})
        self._captures[pin_name] = samples
        
        return StepResult(
            step_type="capture",
            description=f"Capture {pin_name} for {config.get('duration', '1s')}",
            result=TestResult.PASSED,
            duration_s=time.time() - start_time,
            details={
                "samples": len(samples),
                "duration_s": duration,
                "sample_rate_hz": sample_rate,
            },
        )
    
    def _step_analyze(self, step: Dict[str, Any], start_time: float) -> StepResult:
        """Execute an analysis step on captured data."""
        config = step["analyze"]
        capture_name = config.get("capture", "")
        
        samples = getattr(self, "_captures", {}).get(capture_name, [])
        if not samples:
            return StepResult(
                step_type="analyze",
                description=f"Analyze {capture_name}",
                result=TestResult.SKIPPED,
                message=f"No capture data for {capture_name}",
                duration_s=time.time() - start_time,
            )
        
        checks = config.get("checks", [])
        all_passed = True
        details = {}
        
        for check in checks:
            if "frequency" in check:
                freq_result = self._analyze_frequency(samples, check["frequency"])
                details["frequency"] = freq_result
                if not freq_result.get("passed", False):
                    all_passed = False
                    
            if "duty_cycle" in check:
                dc_result = self._analyze_duty_cycle(samples, check["duty_cycle"])
                details["duty_cycle"] = dc_result
                if not dc_result.get("passed", False):
                    all_passed = False
        
        return StepResult(
            step_type="analyze",
            description=f"Analyze {capture_name}",
            result=TestResult.PASSED if all_passed else TestResult.FAILED,
            duration_s=time.time() - start_time,
            details=details,
        )
    
    def _analyze_frequency(
        self, samples: List[tuple], config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Analyze frequency from captured samples."""
        expected_hz = config.get("expected", 1.0)
        if isinstance(expected_hz, str):
            expected_hz = self._parse_rate(expected_hz)
        tolerance = float(config.get("tolerance", "10%").rstrip("%")) / 100
        
        # Count transitions
        transitions = 0
        last_value = samples[0][1] if samples else 0
        for _, value in samples[1:]:
            if value != last_value:
                transitions += 1
                last_value = value
        
        # Calculate frequency (transitions / 2 = cycles)
        duration = samples[-1][0] if samples else 0
        measured_hz = (transitions / 2) / duration if duration > 0 else 0
        
        error = abs(measured_hz - expected_hz) / expected_hz if expected_hz > 0 else 0
        passed = error <= tolerance
        
        return {
            "expected_hz": expected_hz,
            "measured_hz": measured_hz,
            "error": error,
            "tolerance": tolerance,
            "passed": passed,
        }
    
    def _analyze_duty_cycle(
        self, samples: List[tuple], config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Analyze duty cycle from captured samples."""
        expected_dc = float(config.get("expected", "50%").rstrip("%")) / 100
        tolerance = float(config.get("tolerance", "5%").rstrip("%")) / 100
        
        # Count high samples
        high_count = sum(1 for _, v in samples if v > 0)
        measured_dc = high_count / len(samples) if samples else 0
        
        error = abs(measured_dc - expected_dc)
        passed = error <= tolerance
        
        return {
            "expected": expected_dc,
            "measured": measured_dc,
            "error": error,
            "tolerance": tolerance,
            "passed": passed,
        }
    
    def _parse_rate(self, rate_str: str) -> float:
        """Parse rate string to Hz (e.g., '10kHz', '1MHz')."""
        if isinstance(rate_str, (int, float)):
            return float(rate_str)
            
        match = re.match(r"(\d+\.?\d*)\s*(Hz|kHz|MHz|GHz)?", rate_str, re.I)
        if not match:
            return 10000.0  # Default 10kHz
        
        value = float(match.group(1))
        unit = (match.group(2) or "Hz").lower()
        
        multipliers = {
            "hz": 1.0,
            "khz": 1e3,
            "mhz": 1e6,
            "ghz": 1e9,
        }
        
        return value * multipliers.get(unit, 1.0)
    
    def _run_hooks(self, hook_name: str, **kwargs) -> None:
        """Run scenario hooks."""
        hooks = self.scenario.get("hooks", {}).get(hook_name, [])
        for hook in hooks:
            action = hook.get("action", "")
            
            if action == "log":
                logger.info(hook.get("message", ""))
                
            elif action == "screenshot":
                condition = hook.get("condition", "always")
                if condition == "on_failure":
                    test_result = kwargs.get("test_result")
                    if test_result and test_result.result == TestResult.FAILED:
                        logger.info("Would capture screenshot (not implemented)")
                        
            elif action == "generate_report":
                self._generate_report(hook)
    
    def _generate_report(self, config: Dict[str, Any]) -> None:
        """Generate test report."""
        if not self.result:
            return
            
        report_format = config.get("format", "text")
        output_path = expand_variables(
            config.get("output", "${OUTPUT}/report.txt"),
            self.variables,
        )
        
        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)
        
        if report_format == "html":
            self._generate_html_report(output_file)
        else:
            self._generate_text_report(output_file)
    
    def _generate_text_report(self, output_file: Path) -> None:
        """Generate plain text report."""
        lines = [
            f"Test Report: {self.result.name}",
            "=" * 60,
            f"Start Time: {self.result.start_time}",
            f"Duration: {self.result.duration_s:.2f}s",
            f"Results: {self.result.passed}/{self.result.total} passed",
            "",
            "Tests:",
            "-" * 40,
        ]
        
        for test in self.result.tests:
            status = "PASS" if test.result == TestResult.PASSED else "FAIL"
            lines.append(f"  [{status}] {test.name} ({test.duration_s:.3f}s)")
            
            for step in test.steps:
                if step.result == TestResult.FAILED:
                    lines.append(f"        ✗ {step.description}: {step.message}")
        
        output_file.write_text("\n".join(lines))
        logger.info(f"Report saved to: {output_file}")
    
    def _generate_html_report(self, output_file: Path) -> None:
        """Generate HTML report."""
        # Simple HTML template
        html = f"""<!DOCTYPE html>
<html>
<head>
    <title>Test Report: {self.result.name}</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; }}
        .pass {{ color: green; }}
        .fail {{ color: red; }}
        table {{ border-collapse: collapse; width: 100%; }}
        th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
        th {{ background: #4CAF50; color: white; }}
    </style>
</head>
<body>
    <h1>Test Report: {self.result.name}</h1>
    <p>Duration: {self.result.duration_s:.2f}s</p>
    <p>Results: <span class="pass">{self.result.passed}</span> / {self.result.total} passed</p>
    
    <table>
        <tr><th>Test</th><th>Status</th><th>Duration</th></tr>
"""
        
        for test in self.result.tests:
            status = "PASS" if test.result == TestResult.PASSED else "FAIL"
            css_class = "pass" if test.result == TestResult.PASSED else "fail"
            html += f'        <tr><td>{test.name}</td><td class="{css_class}">{status}</td><td>{test.duration_s:.3f}s</td></tr>\n'
        
        html += """    </table>
</body>
</html>"""
        
        output_file.write_text(html)
        logger.info(f"HTML report saved to: {output_file}")


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Run HIL test scenarios from YAML files"
    )
    parser.add_argument(
        "scenario",
        type=Path,
        help="Path to scenario YAML file",
    )
    parser.add_argument(
        "-o", "--output",
        type=Path,
        default=Path("test_output"),
        help="Output directory for logs and reports",
    )
    parser.add_argument(
        "-b", "--backend",
        choices=["auto", "hardware", "simulation", "mock"],
        default="auto",
        help="HIL backend to use",
    )
    parser.add_argument(
        "-f", "--firmware",
        type=Path,
        help="Override firmware path",
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable verbose logging",
    )
    
    args = parser.parse_args()
    
    # Setup logging
    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    
    # Map backend string to enum
    backend_map = {
        "auto": BackendType.AUTO,
        "hardware": BackendType.HARDWARE,
        "simulation": BackendType.SIMULATION,
        "mock": BackendType.MOCK,
    }
    
    # Run scenario
    runner = ScenarioRunner(
        scenario_path=args.scenario,
        output_dir=args.output,
        backend_override=backend_map.get(args.backend),
        firmware_override=args.firmware,
    )
    
    try:
        runner.load()
        runner.setup()
        result = runner.run()
        
        # Print summary
        print("\n" + "=" * 60)
        print(f"Test Results: {result.passed}/{result.total} passed")
        print("=" * 60)
        
        for test in result.tests:
            status = "✓" if test.result == TestResult.PASSED else "✗"
            print(f"  {status} {test.name}")
        
        sys.exit(0 if result.failed == 0 else 1)
        
    except Exception as e:
        logger.exception(f"Scenario failed: {e}")
        sys.exit(2)
        
    finally:
        runner.teardown()


if __name__ == "__main__":
    main()
