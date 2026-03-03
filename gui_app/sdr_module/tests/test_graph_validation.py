import unittest

from pyontrust_sdr.models import BlockSpec, EdgeSpec, GraphSpec
from pyontrust_sdr.runtime.graph_validate import validate_graph
from pyontrust_sdr.errors import GraphValidationError


class TestGraphValidation(unittest.TestCase):
    def test_rejects_unknown_block(self) -> None:
        g = GraphSpec(blocks=[BlockSpec(id="a", type="nope")])
        with self.assertRaises(GraphValidationError):
            validate_graph(g)

    def test_rejects_type_mismatch(self) -> None:
        g = GraphSpec(
            blocks=[
                BlockSpec(id="src", type="sim_iq_source"),
                BlockSpec(id="fm", type="fm_demod"),
            ],
            edges=[EdgeSpec(src_block="src", src_port="iq", dst_block="fm", dst_port="iq")],
        )
        validate_graph(g)  # ok

        g2 = GraphSpec(
            blocks=[
                BlockSpec(id="src", type="sim_iq_source"),
                BlockSpec(id="fft", type="fft_sink"),
                BlockSpec(id="fm", type="fm_demod"),
            ],
            edges=[
                EdgeSpec(src_block="src", src_port="iq", dst_block="fm", dst_port="iq"),
                EdgeSpec(src_block="fm", src_port="audio", dst_block="fft", dst_port="iq"),
            ],
        )
        with self.assertRaises(GraphValidationError):
            validate_graph(g2)

    def test_rejects_cycle(self) -> None:
        g = GraphSpec(
            blocks=[
                BlockSpec(id="a", type="sim_iq_source"),
                BlockSpec(id="b", type="dc_blocker"),
            ],
            edges=[
                EdgeSpec(src_block="a", src_port="iq", dst_block="b", dst_port="iq"),
                EdgeSpec(src_block="b", src_port="iq", dst_block="a", dst_port="iq"),
            ],
        )
        with self.assertRaises(GraphValidationError):
            validate_graph(g)

    def test_requires_exactly_one_source(self) -> None:
        g0 = GraphSpec(blocks=[BlockSpec(id="a", type="dc_blocker")])
        with self.assertRaises(GraphValidationError):
            validate_graph(g0)

        g2 = GraphSpec(
            blocks=[
                BlockSpec(id="s1", type="sim_iq_source"),
                BlockSpec(id="s2", type="sim_iq_source"),
            ]
        )
        with self.assertRaises(GraphValidationError):
            validate_graph(g2)


if __name__ == "__main__":
    unittest.main()
