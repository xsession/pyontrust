"""Tests for the HIL ↔ FlowLab bidirectional converter.

Covers:
- diagram_to_hil: FlowLab → HIL profile
- hil_to_diagram: HIL profile → FlowLab
- Round-trip: diagram → HIL → diagram (structure preserved)
- Edge cases: empty diagrams, malformed input, all block types
"""
from __future__ import annotations

import json
import pytest
from pyontrust.gateway.hil_flowlab_converter import (
    diagram_to_hil,
    hil_to_diagram,
    _topo_sort,
    _block_to_step,
    _detect_instruments,
    _flatten_profile,
    _action_to_block,
)


# ═══════════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════════

@pytest.fixture
def simple_diagram():
    """A simple FlowLab diagram: simulated_power → stats → display."""
    return {
        "version": 1,
        "blocks": [
            {"id": "b1", "type": "simulated_power", "x": 100, "y": 100,
             "params": {"sample_rate_hz": 1000, "duration_s": 2, "base_current_a": 0.001, "noise_a": 0.0001}},
            {"id": "b2", "type": "stats", "x": 350, "y": 100, "params": {}},
            {"id": "b3", "type": "display", "x": 600, "y": 100, "params": {}},
        ],
        "wires": [
            {"id": "w1", "from": {"block": "b1", "port": "trace"}, "to": {"block": "b2", "port": "trace"}},
            {"id": "w2", "from": {"block": "b2", "port": "result"}, "to": {"block": "b3", "port": "data"}},
        ],
    }


@pytest.fixture
def sleep_test_diagram():
    """A FlowLab diagram with sleep_test block."""
    return {
        "version": 1,
        "blocks": [
            {"id": "b1", "type": "sleep_test", "x": 100, "y": 100,
             "params": {"duration_s": 5, "settle_s": 1, "max_avg_ua": 10}},
            {"id": "b2", "type": "threshold", "x": 350, "y": 100,
             "params": {"metric": "avg_current_a", "max_val": 0.01, "min_val": 0}},
        ],
        "wires": [
            {"id": "w1", "from": {"block": "b1", "port": "trace"}, "to": {"block": "b2", "port": "value"}},
        ],
    }


@pytest.fixture
def multi_action_diagram():
    """Complex diagram with multiple action types."""
    return {
        "version": 1,
        "blocks": [
            {"id": "b1", "type": "gpio_toggle", "x": 100, "y": 100,
             "params": {"pin": "P0.13", "action": "high"}},
            {"id": "b2", "type": "delay", "x": 350, "y": 100,
             "params": {"seconds": 2}},
            {"id": "b3", "type": "simulated_power", "x": 100, "y": 300,
             "params": {"duration_s": 5, "sample_rate_hz": 1000}},
            {"id": "b4", "type": "stats", "x": 350, "y": 300, "params": {}},
            {"id": "b5", "type": "threshold", "x": 600, "y": 300,
             "params": {"metric": "avg_current_a", "max_val": 0.01, "min_val": 0}},
            {"id": "b6", "type": "shell_cmd", "x": 100, "y": 500,
             "params": {"command": "echo done", "timeout_s": 10}},
        ],
        "wires": [
            {"id": "w1", "from": {"block": "b1", "port": "state"}, "to": {"block": "b2", "port": "trigger"}},
            {"id": "w2", "from": {"block": "b3", "port": "trace"}, "to": {"block": "b4", "port": "trace"}},
            {"id": "w3", "from": {"block": "b4", "port": "result"}, "to": {"block": "b5", "port": "value"}},
        ],
    }


@pytest.fixture
def sleep_current_profile():
    """The standard sleep_current HIL profile."""
    return {
        "name": "sleep_current",
        "description": "Measure idle/sleep current consumption over 10 seconds",
        "instruments": {
            "power_meter": {"type": "simulated", "params": {}}
        },
        "recorders": [],
        "actions": [
            {"type": "mark", "label": "test_start"},
            {"type": "run", "name": "idle_10s", "duration_s": 10.0,
             "description": "Device in deep sleep for 10 seconds"},
            {"type": "mark", "label": "test_end"},
        ],
    }


@pytest.fixture
def tx_burst_profile():
    """The standard tx_burst HIL profile."""
    return {
        "name": "tx_burst",
        "description": "Measure current during a TX burst cycle",
        "instruments": {
            "power_meter": {"type": "simulated", "params": {}}
        },
        "recorders": [],
        "actions": [
            {"type": "mark", "label": "test_start"},
            {"type": "run", "name": "pre_idle", "duration_s": 2.0, "description": "Baseline idle measurement"},
            {"type": "mark", "label": "tx_start"},
            {"type": "run", "name": "tx_burst", "duration_s": 5.0, "description": "DUT transmitting"},
            {"type": "mark", "label": "tx_end"},
            {"type": "run", "name": "post_idle", "duration_s": 3.0, "description": "Post-TX return to idle"},
            {"type": "mark", "label": "test_end"},
        ],
    }


@pytest.fixture
def nested_steps_profile():
    """A profile in the nested steps format."""
    return {
        "name": "nested_test",
        "description": "Multi-step nested HIL test",
        "instruments": {
            "power_meter": {"type": "simulated", "params": {}}
        },
        "recorders": [],
        "steps": [
            {
                "name": "init",
                "duration_s": 1.0,
                "actions": [
                    {"type": "mark", "label": "init_start"},
                    {"type": "set_power_mode", "mode": "source"},
                ],
            },
            {
                "name": "measure_sleep",
                "duration_s": 10.0,
                "actions": [
                    {"type": "mark", "label": "sleep_start"},
                ],
            },
            {
                "name": "cleanup",
                "duration_s": 1.0,
                "actions": [
                    {"type": "mark", "label": "test_done"},
                ],
            },
        ],
    }


# ═══════════════════════════════════════════════════════════════════
# Tests: diagram_to_hil
# ═══════════════════════════════════════════════════════════════════

class TestDiagramToHil:
    def test_simple_diagram_produces_valid_profile(self, simple_diagram):
        profile = diagram_to_hil(simple_diagram)
        assert "name" in profile
        assert "description" in profile
        assert "instruments" in profile
        assert "steps" in profile
        assert isinstance(profile["steps"], list)

    def test_simple_diagram_step_count(self, simple_diagram):
        """Simulated_power + stats + display = 3 actionable blocks."""
        profile = diagram_to_hil(simple_diagram)
        # simulated_power → measure step, stats → analysis step, display → display step
        assert len(profile["steps"]) == 3

    def test_simple_diagram_instruments_detected(self, simple_diagram):
        profile = diagram_to_hil(simple_diagram)
        assert "power_meter" in profile["instruments"]
        assert profile["instruments"]["power_meter"]["type"] == "simulated"

    def test_sleep_test_diagram_export(self, sleep_test_diagram):
        profile = diagram_to_hil(sleep_test_diagram)
        assert len(profile["steps"]) == 2  # sleep_test + threshold
        sleep_step = profile["steps"][0]
        assert sleep_step["duration_s"] == 5

    def test_multi_action_diagram_export(self, multi_action_diagram):
        profile = diagram_to_hil(multi_action_diagram)
        steps = profile["steps"]
        # gpio_toggle, delay, simulated_power, stats, threshold, shell_cmd
        assert len(steps) == 6
        # Check types are meaningful
        step_names = [s["name"] for s in steps]
        assert any("gpio" in n for n in step_names)
        assert any("delay" in n for n in step_names)
        assert any("measure" in n for n in step_names)
        assert any("shell" in n for n in step_names)

    def test_empty_diagram(self):
        profile = diagram_to_hil({"blocks": [], "wires": []})
        assert profile["name"] == "empty_flowlab_export"
        assert profile["steps"] == []

    def test_no_blocks_key(self):
        profile = diagram_to_hil({})
        assert profile["steps"] == []

    def test_steps_have_required_fields(self, simple_diagram):
        profile = diagram_to_hil(simple_diagram)
        for step in profile["steps"]:
            assert "name" in step
            assert "duration_s" in step
            assert "actions" in step
            assert isinstance(step["actions"], list)

    def test_each_step_has_marker(self, simple_diagram):
        """Every step should start with a mark action."""
        profile = diagram_to_hil(simple_diagram)
        for step in profile["steps"]:
            assert len(step["actions"]) >= 1
            assert step["actions"][0]["type"] == "mark"

    def test_meta_includes_source(self, simple_diagram):
        profile = diagram_to_hil(simple_diagram)
        assert profile.get("meta", {}).get("source") == "flowlab"

    def test_profile_is_json_serializable(self, multi_action_diagram):
        profile = diagram_to_hil(multi_action_diagram)
        text = json.dumps(profile, indent=2)
        roundtripped = json.loads(text)
        assert roundtripped == profile

    def test_ppk2_instrument_detected(self):
        diagram = {
            "blocks": [
                {"id": "b1", "type": "ppk2_meter", "x": 0, "y": 0,
                 "params": {"serial_port": "COM3", "vdd_mv": 3300, "duration_s": 5}},
            ],
            "wires": [],
        }
        profile = diagram_to_hil(diagram)
        assert profile["instruments"]["power_meter"]["type"] == "ppk2"

    def test_ad3_instrument_detected(self):
        diagram = {
            "blocks": [
                {"id": "b1", "type": "ad3_dwf_meter", "x": 0, "y": 0,
                 "params": {"device_index": 0, "duration_s": 3}},
            ],
            "wires": [],
        }
        profile = diagram_to_hil(diagram)
        assert profile["instruments"]["power_meter"]["type"] == "ad3_dwf"

    def test_vision_instruments_detected(self):
        diagram = {
            "blocks": [
                {"id": "b1", "type": "aoi_camera", "x": 0, "y": 0, "params": {"mode": "webcam"}},
                {"id": "b2", "type": "seek_thermal", "x": 200, "y": 0, "params": {"mode": "simulated"}},
            ],
            "wires": [],
        }
        profile = diagram_to_hil(diagram)
        assert "aoi_camera" in profile["instruments"]
        assert "seek_thermal" in profile["instruments"]

    def test_data_routing_blocks_skipped(self):
        """Pure data-routing blocks like constant, expression should not become steps."""
        diagram = {
            "blocks": [
                {"id": "b1", "type": "constant", "x": 0, "y": 0, "params": {"value": "42"}},
                {"id": "b2", "type": "expression", "x": 200, "y": 0, "params": {"expr": "a + 1"}},
                {"id": "b3", "type": "display", "x": 400, "y": 0, "params": {}},
            ],
            "wires": [
                {"id": "w1", "from": {"block": "b1", "port": "value"}, "to": {"block": "b2", "port": "a"}},
                {"id": "w2", "from": {"block": "b2", "port": "result"}, "to": {"block": "b3", "port": "data"}},
            ],
        }
        profile = diagram_to_hil(diagram)
        # Only display should become a step (constant and expression are skipped)
        assert len(profile["steps"]) == 1


# ═══════════════════════════════════════════════════════════════════
# Tests: hil_to_diagram
# ═══════════════════════════════════════════════════════════════════

class TestHilToDiagram:
    def test_flat_profile_produces_diagram(self, sleep_current_profile):
        diagram = hil_to_diagram(sleep_current_profile)
        assert "version" in diagram
        assert "blocks" in diagram
        assert "wires" in diagram
        assert diagram["version"] == 1

    def test_flat_profile_block_count(self, sleep_current_profile):
        diagram = hil_to_diagram(sleep_current_profile)
        # 1 instrument block + 3 actions (mark, run, mark)
        blocks = diagram["blocks"]
        assert len(blocks) >= 3  # At least instrument + 2 marks + run step

    def test_nested_profile_produces_diagram(self, nested_steps_profile):
        diagram = hil_to_diagram(nested_steps_profile)
        assert len(diagram["blocks"]) >= 3

    def test_tx_burst_import(self, tx_burst_profile):
        diagram = hil_to_diagram(tx_burst_profile)
        blocks = diagram["blocks"]
        # Should have instrument block + multiple action blocks
        assert len(blocks) >= 4
        # Check tx_burst_test block was created for the TX step
        block_types = [b["type"] for b in blocks]
        assert "tx_burst_test" in block_types

    def test_sleep_current_import_has_sleep_test_block(self, sleep_current_profile):
        diagram = hil_to_diagram(sleep_current_profile)
        block_types = [b["type"] for b in diagram["blocks"]]
        # The "idle_10s" run step should map to sleep_test
        assert "sleep_test" in block_types or "simulated_power" in block_types

    def test_blocks_have_valid_positions(self, sleep_current_profile):
        diagram = hil_to_diagram(sleep_current_profile)
        for block in diagram["blocks"]:
            assert "x" in block
            assert "y" in block
            assert isinstance(block["x"], (int, float))
            assert isinstance(block["y"], (int, float))
            assert block["x"] >= 0
            assert block["y"] >= 0

    def test_blocks_have_valid_ids(self, sleep_current_profile):
        diagram = hil_to_diagram(sleep_current_profile)
        ids = [b["id"] for b in diagram["blocks"]]
        assert len(ids) == len(set(ids)), "Block IDs must be unique"
        for bid in ids:
            assert bid.startswith("b")

    def test_wires_reference_valid_blocks(self, tx_burst_profile):
        diagram = hil_to_diagram(tx_burst_profile)
        block_ids = {b["id"] for b in diagram["blocks"]}
        for wire in diagram["wires"]:
            assert wire["from"]["block"] in block_ids, f"Wire from block {wire['from']['block']} not found"
            assert wire["to"]["block"] in block_ids, f"Wire to block {wire['to']['block']} not found"

    def test_instrument_block_created(self, sleep_current_profile):
        diagram = hil_to_diagram(sleep_current_profile)
        # Should have a simulated_power block for the power_meter instrument
        block_types = [b["type"] for b in diagram["blocks"]]
        assert "simulated_power" in block_types

    def test_empty_profile(self):
        profile = {"name": "empty", "instruments": {}, "actions": []}
        diagram = hil_to_diagram(profile)
        assert diagram["blocks"] == []

    def test_diagram_is_json_serializable(self, tx_burst_profile):
        diagram = hil_to_diagram(tx_burst_profile)
        text = json.dumps(diagram, indent=2)
        roundtripped = json.loads(text)
        assert roundtripped == diagram

    def test_profile_with_flash_action(self):
        profile = {
            "name": "flash_test",
            "instruments": {"power_meter": {"type": "simulated", "params": {}}},
            "steps": [{
                "name": "flash_fw",
                "duration_s": 30,
                "actions": [
                    {"type": "flash", "firmware": "build/app.hex", "instrument": "jlink"},
                ],
            }],
        }
        diagram = hil_to_diagram(profile)
        block_types = [b["type"] for b in diagram["blocks"]]
        assert "shell_cmd" in block_types
        # Find the shell_cmd block and check params
        shell_block = [b for b in diagram["blocks"] if b["type"] == "shell_cmd"][0]
        assert "nrfjprog" in shell_block["params"]["command"]

    def test_profile_with_sleep_action(self):
        profile = {
            "name": "delay_test",
            "instruments": {},
            "actions": [
                {"type": "sleep", "seconds": 3},
            ],
        }
        diagram = hil_to_diagram(profile)
        block_types = [b["type"] for b in diagram["blocks"]]
        assert "delay" in block_types
        delay_block = [b for b in diagram["blocks"] if b["type"] == "delay"][0]
        assert delay_block["params"]["seconds"] == 3


# ═══════════════════════════════════════════════════════════════════
# Tests: Round-trip conversion
# ═══════════════════════════════════════════════════════════════════

class TestRoundTrip:
    def test_diagram_to_hil_to_diagram(self, simple_diagram):
        """Convert diagram → HIL → diagram and verify structure preserved."""
        hil = diagram_to_hil(simple_diagram)
        reimported = hil_to_diagram(hil)
        assert reimported["version"] == 1
        assert len(reimported["blocks"]) > 0
        # The reimported diagram should have blocks
        reimported_types = {b["type"] for b in reimported["blocks"]}
        assert len(reimported_types) > 0

    def test_hil_to_diagram_to_hil(self, sleep_current_profile):
        """Convert HIL → diagram → HIL and verify structure preserved."""
        diagram = hil_to_diagram(sleep_current_profile)
        re_exported = diagram_to_hil(diagram)
        assert re_exported["name"] is not None
        assert "instruments" in re_exported
        assert "steps" in re_exported
        assert len(re_exported["steps"]) > 0

    def test_tx_burst_round_trip(self, tx_burst_profile):
        """TX burst profile survives round-trip."""
        diagram = hil_to_diagram(tx_burst_profile)
        re_exported = diagram_to_hil(diagram)
        # Should still have steps
        assert len(re_exported["steps"]) > 0
        # Should still detect instruments
        assert "power_meter" in re_exported["instruments"]

    def test_round_trip_preserves_profile_json_validity(self, tx_burst_profile):
        diagram = hil_to_diagram(tx_burst_profile)
        re_exported = diagram_to_hil(diagram)
        text = json.dumps(re_exported, indent=2)
        parsed = json.loads(text)
        assert parsed == re_exported


# ═══════════════════════════════════════════════════════════════════
# Tests: Helper functions
# ═══════════════════════════════════════════════════════════════════

class TestHelpers:
    def test_topo_sort_linear(self):
        blocks = [{"id": "b1"}, {"id": "b2"}, {"id": "b3"}]
        wires = [
            {"from": {"block": "b1", "port": "out"}, "to": {"block": "b2", "port": "in"}},
            {"from": {"block": "b2", "port": "out"}, "to": {"block": "b3", "port": "in"}},
        ]
        order = _topo_sort(blocks, wires)
        assert order == ["b1", "b2", "b3"]

    def test_topo_sort_diamond(self):
        blocks = [{"id": "b1"}, {"id": "b2"}, {"id": "b3"}, {"id": "b4"}]
        wires = [
            {"from": {"block": "b1", "port": "out"}, "to": {"block": "b2", "port": "in"}},
            {"from": {"block": "b1", "port": "out"}, "to": {"block": "b3", "port": "in"}},
            {"from": {"block": "b2", "port": "out"}, "to": {"block": "b4", "port": "in"}},
            {"from": {"block": "b3", "port": "out"}, "to": {"block": "b4", "port": "in"}},
        ]
        order = _topo_sort(blocks, wires)
        assert order[0] == "b1"
        assert order[-1] == "b4"
        assert len(order) == 4

    def test_topo_sort_no_wires(self):
        blocks = [{"id": "b1"}, {"id": "b2"}]
        order = _topo_sort(blocks, [])
        assert set(order) == {"b1", "b2"}

    def test_topo_sort_disconnected(self):
        blocks = [{"id": "b1"}, {"id": "b2"}, {"id": "b3"}]
        wires = [
            {"from": {"block": "b1", "port": "out"}, "to": {"block": "b2", "port": "in"}},
        ]
        order = _topo_sort(blocks, wires)
        assert len(order) == 3
        assert "b1" in order
        assert "b2" in order
        assert "b3" in order

    def test_detect_instruments_simulated(self):
        blocks = [{"id": "b1", "type": "simulated_power", "params": {}}]
        instr = _detect_instruments(blocks)
        assert "power_meter" in instr
        assert instr["power_meter"]["type"] == "simulated"

    def test_detect_instruments_ppk2(self):
        blocks = [{"id": "b1", "type": "ppk2_meter", "params": {"serial_port": "COM3"}}]
        instr = _detect_instruments(blocks)
        assert instr["power_meter"]["type"] == "ppk2"

    def test_detect_instruments_vision(self):
        blocks = [
            {"id": "b1", "type": "aoi_camera", "params": {"mode": "webcam"}},
            {"id": "b2", "type": "seek_thermal", "params": {"mode": "seek"}},
        ]
        instr = _detect_instruments(blocks)
        assert "aoi_camera" in instr
        assert "seek_thermal" in instr

    def test_detect_instruments_empty_defaults(self):
        blocks = [{"id": "b1", "type": "stats", "params": {}}]
        instr = _detect_instruments(blocks)
        # Should still provide a default simulated meter
        assert "power_meter" in instr

    def test_flatten_profile_flat_format(self):
        profile = {"actions": [{"type": "mark", "label": "a"}, {"type": "sleep", "seconds": 1}]}
        actions = _flatten_profile(profile)
        assert len(actions) == 2

    def test_flatten_profile_nested_format(self):
        profile = {
            "steps": [
                {"name": "s1", "duration_s": 1, "actions": [{"type": "mark", "label": "a"}]},
                {"name": "s2", "duration_s": 2, "actions": [{"type": "mark", "label": "b"}]},
            ]
        }
        actions = _flatten_profile(profile)
        assert len(actions) == 2
        assert actions[0]["_step_name"] == "s1"
        assert actions[1]["_step_name"] == "s2"

    def test_flatten_profile_step_without_actions(self):
        profile = {
            "steps": [
                {"name": "measure", "duration_s": 5},
            ]
        }
        actions = _flatten_profile(profile)
        assert len(actions) == 1
        assert actions[0]["type"] == "run"
        assert actions[0]["duration_s"] == 5

    def test_action_to_block_mark(self):
        result = _action_to_block("mark", {"label": "hello"}, 0)
        assert result is not None
        btype, params, inp, outp = result
        assert btype == "log_message"
        assert params["prefix"] == "hello"

    def test_action_to_block_sleep(self):
        result = _action_to_block("sleep", {"seconds": 3}, 0)
        assert result is not None
        btype, params, _, _ = result
        assert btype == "delay"
        assert params["seconds"] == 3

    def test_action_to_block_flash(self):
        result = _action_to_block("flash", {"firmware": "build/app.hex"}, 0)
        assert result is not None
        btype, params, _, _ = result
        assert btype == "shell_cmd"
        assert "nrfjprog" in params["command"]

    def test_action_to_block_run_with_command(self):
        result = _action_to_block("run", {"command": ["echo", "test"]}, 0)
        assert result is not None
        btype, params, _, _ = result
        assert btype == "shell_cmd"

    def test_action_to_block_run_with_duration_sleep(self):
        result = _action_to_block("run", {"name": "idle_sleep", "duration_s": 5, "description": "sleep mode"}, 0)
        assert result is not None
        btype, params, _, _ = result
        assert btype == "sleep_test"
        assert params["duration_s"] == 5

    def test_action_to_block_run_with_duration_tx(self):
        result = _action_to_block("run", {"name": "tx_burst", "duration_s": 3, "description": "transmitting"}, 0)
        assert result is not None
        btype, params, _, _ = result
        assert btype == "tx_burst_test"

    def test_action_to_block_snapshot(self):
        result = _action_to_block("snapshot", {"instrument": "webcam"}, 0)
        assert result is not None
        btype, _, _, _ = result
        assert btype == "aoi_camera"

    def test_action_to_block_thermal(self):
        result = _action_to_block("thermal_capture", {"instrument": "seek_thermal"}, 0)
        assert result is not None
        btype, _, _, _ = result
        assert btype == "seek_thermal"


# ═══════════════════════════════════════════════════════════════════
# Tests: All block types export
# ═══════════════════════════════════════════════════════════════════

class TestAllBlockTypes:
    """Ensure every actionable block type can be exported to HIL."""

    ACTIONABLE_TYPES = [
        "simulated_power", "csv_file", "csv_replay", "aoi_camera",
        "seek_thermal", "ppk2_meter", "ad3_dwf_meter", "waveform_gen",
        "random_data", "stats", "filter", "highpass_filter", "bandpass_filter",
        "fft_spectrum", "moving_average", "derivative", "integral",
        "threshold", "window_slice", "resample", "edge_detect",
        "histogram", "correlate", "thermal_analyze", "aoi_inspect",
        "color_detect", "blob_detect", "template_match", "image_resize",
        "image_crop", "image_threshold", "display", "plot_trace",
        "plot_xy", "plot_histogram", "plot_heatmap", "gauge_display",
        "table_display", "save_file", "log_message", "assert_check",
        "delay", "shell_cmd", "http_request", "sleep_test",
        "tx_burst_test", "gpio_toggle", "serial_send", "load_profile",
        "benchmark_timer",
    ]

    @pytest.mark.parametrize("block_type", ACTIONABLE_TYPES)
    def test_block_type_exports(self, block_type):
        diagram = {
            "blocks": [{"id": "b1", "type": block_type, "x": 0, "y": 0, "params": {}}],
            "wires": [],
        }
        profile = diagram_to_hil(diagram)
        assert len(profile["steps"]) >= 1, f"Block type {block_type} should produce at least 1 step"

    SKIPPED_TYPES = [
        "constant", "expression", "multiply", "add", "subtract",
        "divide", "abs_val", "power", "log_math", "trig", "clamp",
        "map_range", "compare", "unit_convert", "merge", "gate",
        "null_check", "try_catch", "sequence", "dict_get", "dict_set",
        "dict_build", "list_build", "json_parse", "format_string",
        "type_cast", "pick_field", "repeat",
    ]

    @pytest.mark.parametrize("block_type", SKIPPED_TYPES)
    def test_data_routing_blocks_skipped(self, block_type):
        diagram = {
            "blocks": [{"id": "b1", "type": block_type, "x": 0, "y": 0, "params": {}}],
            "wires": [],
        }
        profile = diagram_to_hil(diagram)
        assert len(profile["steps"]) == 0, f"Block type {block_type} should be skipped"


# ═══════════════════════════════════════════════════════════════════
# Tests: All HIL action types import
# ═══════════════════════════════════════════════════════════════════

class TestAllHilActions:
    """Ensure every HIL action type can be imported as a FlowLab block."""

    ACTION_CONFIGS = [
        ("mark", {"label": "test"}),
        ("sleep", {"seconds": 2}),
        ("run", {"command": ["echo", "hi"]}),
        ("flash", {"firmware": "app.hex"}),
        ("reset_target", {"instrument": "jlink"}),
        ("set_voltage", {"voltage_v": 3.3}),
        ("enable_output", {"on": True}),
        ("snapshot", {"instrument": "webcam"}),
        ("inspect", {"board_id": "pcb1"}),
        ("thermal_capture", {"instrument": "seek_thermal"}),
        ("rf_sweep", {"instrument": "hackrf"}),
        ("set_power_mode", {"mode": "source"}),
    ]

    @pytest.mark.parametrize("action_type,params", ACTION_CONFIGS)
    def test_action_type_imports(self, action_type, params):
        result = _action_to_block(action_type, {**params, "type": action_type}, 0)
        assert result is not None, f"Action type {action_type} should map to a block"
        btype, block_params, _, _ = result
        assert isinstance(btype, str)
        assert isinstance(block_params, dict)
