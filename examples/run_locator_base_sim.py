"""Example: Running Locator Base Simulation

This example demonstrates how to:
1. Run the locator_base in simulation using ProtoSim/Renode
2. Log measured data to VCD, CSV, and JSON formats
3. Use the unified HIL interface for testing

Run this example:
    python examples/run_locator_base_sim.py
    
Or with specific options:
    python examples/run_locator_base_sim.py --duration 5.0 --output sim_data
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

# Add parent to path for development
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from pyontrust.simulation import (
    BackendType,
    LocatorBaseSimulator,
    ScenarioRunner,
    SimulationConfig,
    UnifiedHIL,
)


def run_basic_simulation(
    firmware_path: str,
    duration_s: float = 2.0,
    output_dir: str = "sim_output",
) -> None:
    """Run basic simulation and log data."""
    
    print(f"\n{'='*60}")
    print("Locator Base Simulation Example")
    print(f"{'='*60}")
    
    # Create simulation config
    config = SimulationConfig(
        project_name="locator_base_demo",
        firmware_path=firmware_path,
        duration_s=duration_s,
        sync_interval_s=100e-6,  # 100µs sync interval
        enable_vcd=True,
        enable_csv=True,
        enable_json=True,
    )
    
    print(f"\nConfiguration:")
    print(f"  Firmware: {firmware_path}")
    print(f"  Duration: {duration_s}s")
    print(f"  Output:   {output_dir}")
    
    # Create simulator
    simulator = LocatorBaseSimulator(config)
    
    print("\nRunning simulation...")
    
    try:
        # Run the simulation
        results = simulator.run(output_dir=output_dir)
        
        print(f"\n{'='*60}")
        print("Simulation Results")
        print(f"{'='*60}")
        print(f"  Elapsed time: {results.elapsed_time:.3f}s")
        print(f"  Simulated time: {results.sim_time:.6f}s")
        print(f"  Samples collected: {results.sample_count}")
        
        print(f"\nOutput files:")
        for path in results.output_files:
            print(f"  - {path}")
        
        if results.errors:
            print(f"\nErrors:")
            for error in results.errors:
                print(f"  - {error}")
        
    except Exception as e:
        print(f"\nSimulation failed: {e}")
        raise


def run_unified_hil_demo() -> None:
    """Demo the unified HIL interface."""
    
    print(f"\n{'='*60}")
    print("Unified HIL Demo (Mock Backend)")
    print(f"{'='*60}")
    
    # Use mock backend for demo (works without hardware/ProtoSim)
    with UnifiedHIL(backend_type=BackendType.MOCK) as hil:
        print(f"\nBackend: {'Simulation' if hil.is_simulation else 'Hardware'}")
        
        # Digital I/O demo
        print("\nDigital I/O:")
        hil.digital_write("PA0", True)
        print(f"  Write PA0 = HIGH")
        
        value = hil.digital_read("PA0")
        print(f"  Read PA0 = {'HIGH' if value else 'LOW'}")
        
        hil.digital_toggle("PA0")
        value = hil.digital_read("PA0")
        print(f"  Toggle PA0 -> {'HIGH' if value else 'LOW'}")
        
        # Analog I/O demo
        print("\nAnalog I/O:")
        hil.analog_write("PA15", 1.65)
        print(f"  Write PA15 = 1.65V")
        
        voltage = hil.analog_read("PA15")
        print(f"  Read PA15 = {voltage:.3f}V")
        
        # Pin state
        print("\nPin States:")
        state = hil.get_pin_state("PA0")
        print(f"  PA0: value={state.value}, digital={state.is_digital}")
        
        state = hil.get_pin_state("PA15")
        print(f"  PA15: value={state.value:.3f}, digital={state.is_digital}")
    
    print("\n✓ Unified HIL demo complete")


def run_scenario_demo(scenario_path: Path, output_dir: Path) -> None:
    """Demo running a test scenario from YAML."""
    
    print(f"\n{'='*60}")
    print("Scenario Runner Demo")
    print(f"{'='*60}")
    
    if not scenario_path.exists():
        print(f"  Scenario file not found: {scenario_path}")
        print("  Skipping scenario demo...")
        return
    
    runner = ScenarioRunner(
        scenario_path=scenario_path,
        output_dir=output_dir,
        backend_override=BackendType.MOCK,  # Use mock for demo
    )
    
    try:
        runner.load()
        runner.setup()
        result = runner.run()
        
        print(f"\nScenario: {result.name}")
        print(f"Duration: {result.duration_s:.2f}s")
        print(f"Results: {result.passed}/{result.total} passed")
        
        for test in result.tests:
            status = "✓" if test.result.value == "passed" else "✗"
            print(f"  {status} {test.name}")
        
    finally:
        runner.teardown()
    
    print("\n✓ Scenario demo complete")


def main():
    parser = argparse.ArgumentParser(
        description="Run Locator Base simulation examples"
    )
    parser.add_argument(
        "--firmware",
        type=Path,
        help="Path to firmware ELF file",
    )
    parser.add_argument(
        "--duration",
        type=float,
        default=2.0,
        help="Simulation duration in seconds",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("sim_output"),
        help="Output directory",
    )
    parser.add_argument(
        "--scenario",
        type=Path,
        help="Path to scenario YAML file",
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Verbose output",
    )
    
    args = parser.parse_args()
    
    # Setup logging
    log_level = logging.DEBUG if args.verbose else logging.WARNING
    logging.basicConfig(level=log_level)
    
    # Always run the unified HIL demo (works without dependencies)
    run_unified_hil_demo()
    
    # Run simulation if firmware provided
    if args.firmware:
        run_basic_simulation(
            firmware_path=str(args.firmware),
            duration_s=args.duration,
            output_dir=str(args.output),
        )
    else:
        print("\n[Note: Skipping full simulation (no --firmware provided)]")
    
    # Run scenario if provided
    if args.scenario:
        run_scenario_demo(args.scenario, args.output)
    else:
        # Try default scenario path
        default_scenario = Path(__file__).parent.parent / "scenarios" / "locator_base_blink_test.yaml"
        if default_scenario.exists():
            run_scenario_demo(default_scenario, args.output)
    
    print(f"\n{'='*60}")
    print("Demo Complete!")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
