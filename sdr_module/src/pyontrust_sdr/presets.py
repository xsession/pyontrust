from __future__ import annotations

from .models import BlockSpec, EdgeSpec, GraphSpec


def default_graph() -> GraphSpec:
    return GraphSpec(
        name="default",
        blocks=[
            BlockSpec(id="src", type="sim_iq_source", params={"tone_hz": 100e3, "amp": 0.7, "noise": 0.02}),
            BlockSpec(id="dc", type="dc_blocker", params={"alpha": 0.995}),
            BlockSpec(id="agc", type="agc", params={"target": 0.5, "rate": 1e-3}),
            BlockSpec(id="fft", type="fft_sink", params={"bins": 1024}),
            BlockSpec(id="wf", type="waterfall_sink", params={"bins": 256, "rows": 200}),
            BlockSpec(id="scope", type="iq_scope_sink", params={"max_points": 1024}),
        ],
        edges=[
            EdgeSpec(src_block="src", src_port="iq", dst_block="dc", dst_port="iq"),
            EdgeSpec(src_block="dc", src_port="iq", dst_block="agc", dst_port="iq"),
            EdgeSpec(src_block="agc", src_port="iq", dst_block="fft", dst_port="iq"),
            EdgeSpec(src_block="agc", src_port="iq", dst_block="wf", dst_port="iq"),
            EdgeSpec(src_block="agc", src_port="iq", dst_block="scope", dst_port="iq"),
        ],
    )
