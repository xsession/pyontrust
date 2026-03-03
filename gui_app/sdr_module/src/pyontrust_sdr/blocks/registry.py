from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Dict, List

from .base import Block
from .sources import HalRxSource, SimIqSource, SdrSource, SignalGeneratorSource, FileIqSource
from .processing import DcBlocker, Agc, FrequencyTranslate, FirLowpass, Decimator, AmDemod, FmDemod
from .sinks import FftSink, WaterfallSink, IqScopeSink
from .zmq_bridge import ZmqIqPubSink, ZmqIqSubSource


BlockFactory = Callable[[], Block]


@dataclass
class BlockRegistry:
    _blocks: Dict[str, BlockFactory]

    def list_blocks(self) -> List[str]:
        return sorted(self._blocks.keys())

    def get(self, name: str) -> BlockFactory:
        return self._blocks[name]


def default_block_registry() -> BlockRegistry:
    return BlockRegistry(
        _blocks={
            # sources
            "hal_rx_source": HalRxSource,
            "sim_iq_source": SimIqSource,
            "file_iq_source": FileIqSource,
            "zmq_iq_sub_source": ZmqIqSubSource,
            # v0.1 compatibility
            "sdr_source": SdrSource,
            "signal_generator": SignalGeneratorSource,
            # processing
            "dc_blocker": DcBlocker,
            "agc": Agc,
            "freq_translate": FrequencyTranslate,
            "fir_lowpass": FirLowpass,
            "decimator": Decimator,
            "am_demod": AmDemod,
            "fm_demod": FmDemod,
            # sinks
            "fft_sink": FftSink,
            "waterfall_sink": WaterfallSink,
            "iq_scope_sink": IqScopeSink,
            "zmq_iq_pub_sink": ZmqIqPubSink,
        }
    )
