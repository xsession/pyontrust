"""Simulation package for pyontrust.

Provides integration with ProtoSim for MCU simulation and
hardware-in-the-loop testing of Zephyr drivers.
"""

from pyontrust.simulation.runner import (
    LocatorBaseSimulator,
    SimulationConfig,
    SimulationResults,
    SimulationDataLogger,
    SignalSample,
)

from pyontrust.simulation.hil_bridge import (
    AD3Backend,
    BackendType,
    DigitalValue,
    HILBackend,
    MockBackend,
    PinState,
    SimulationBackend,
    UnifiedHIL,
    create_hil_fixtures,
)

from pyontrust.simulation.scenario_runner import (
    ScenarioRunner,
    ScenarioResult,
    TestResult,
    TestCaseResult,
    StepResult,
)

__all__ = [
    # Runner
    "LocatorBaseSimulator",
    "SimulationConfig",
    "SimulationResults",
    "SimulationDataLogger",
    "SignalSample",
    # HIL Bridge
    "AD3Backend",
    "BackendType",
    "DigitalValue",
    "HILBackend",
    "MockBackend",
    "PinState",
    "SimulationBackend",
    "UnifiedHIL",
    "create_hil_fixtures",
    # Scenario Runner
    "ScenarioRunner",
    "ScenarioResult",
    "TestResult",
    "TestCaseResult",
    "StepResult",
]
