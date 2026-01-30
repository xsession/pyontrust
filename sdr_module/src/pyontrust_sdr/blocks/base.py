from __future__ import annotations

from typing import Any, Dict

import numpy as np

from ..runtime.pubsub import PubSub


class Block:
    """DSP block base class.

    Blocks are stateless or stateful. They receive named inputs, emit named outputs.
    Dtypes are enforced by graph validation via input_ports()/output_ports().
    """

    def input_ports(self) -> Dict[str, str]:
        return {}

    def output_ports(self) -> Dict[str, str]:
        return {}

    def configure(self, params: dict) -> None:
        self._params = dict(params or {})

    def process(self, inputs: Dict[str, np.ndarray], *, sample_rate_hz: float, pubsub: PubSub) -> Dict[str, np.ndarray]:
        return {}
