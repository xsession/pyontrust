from __future__ import annotations

import time
from typing import Dict

import numpy as np

from .base import Block
from ..runtime.pubsub import PubSub


def _require_zmq():
    try:
        import zmq  # type: ignore

        return zmq
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(
            "pyzmq is required for ZMQ bridge blocks. Install with: pip install -e sdr_module[zmq]"
        ) from exc


class ZmqIqSubSource(Block):
    """ZMQ SUB source for complex64 IQ.

    Params:
    - address: e.g. tcp://127.0.0.1:5555
    - bind: bool (default False)
    - topic: bytes prefix (default b"")
    - timeout_ms: int (default 250)

    Payload format: raw bytes of complex64 samples.
    """

    is_source = True

    def __init__(self) -> None:
        self._ctx = None
        self._sock = None

    def output_ports(self) -> Dict[str, str]:
        return {"iq": "complex64"}

    def start(self, *, sample_rate_hz: float, pubsub: PubSub) -> None:
        zmq = _require_zmq()
        self._ctx = zmq.Context.instance()
        self._sock = self._ctx.socket(zmq.SUB)

        address = str(self._params.get("address", "tcp://127.0.0.1:5555"))
        bind = bool(self._params.get("bind", False))
        topic = self._params.get("topic", b"")
        if isinstance(topic, str):
            topic = topic.encode("utf-8")
        self._sock.setsockopt(zmq.SUBSCRIBE, topic)

        if bind:
            self._sock.bind(address)
        else:
            self._sock.connect(address)

    def stop(self) -> None:
        if self._sock is not None:
            try:
                self._sock.close(0)
            except Exception:
                pass
        self._sock = None

    def produce(self, *, chunk_size: int, sample_rate_hz: float, pubsub: PubSub) -> Dict[str, np.ndarray]:
        if self._sock is None:
            return {}

        zmq = _require_zmq()
        timeout_ms = int(self._params.get("timeout_ms", 250))
        poller = zmq.Poller()
        poller.register(self._sock, zmq.POLLIN)
        ev = dict(poller.poll(timeout_ms))
        if self._sock not in ev:
            return {}

        msg = self._sock.recv()
        iq = np.frombuffer(msg, dtype=np.complex64)
        if iq.size == 0:
            return {}

        # Normalize to chunk_size
        n = int(chunk_size)
        if iq.size > n:
            iq = iq[:n]
        elif iq.size < n:
            # pad to keep downstream blocks stable
            pad = np.zeros(n - iq.size, dtype=np.complex64)
            iq = np.concatenate([iq, pad])

        return {"iq": iq}


class ZmqIqPubSink(Block):
    """ZMQ PUB sink for complex64 IQ.

    Params:
    - address: e.g. tcp://*:5555
    - bind: bool (default True)
    - topic: bytes prefix (default b"")

    Payload format: topic + raw bytes of complex64 samples.
    """

    def __init__(self) -> None:
        self._ctx = None
        self._sock = None

    def input_ports(self) -> Dict[str, str]:
        return {"iq": "complex64"}

    def start(self, *, sample_rate_hz: float, pubsub: PubSub) -> None:
        zmq = _require_zmq()
        self._ctx = zmq.Context.instance()
        self._sock = self._ctx.socket(zmq.PUB)

        address = str(self._params.get("address", "tcp://*:5555"))
        bind = bool(self._params.get("bind", True))
        if bind:
            self._sock.bind(address)
        else:
            self._sock.connect(address)

        # Give subscribers a moment to connect.
        time.sleep(0.05)

    def stop(self) -> None:
        if self._sock is not None:
            try:
                self._sock.close(0)
            except Exception:
                pass
        self._sock = None

    def process(self, inputs: Dict[str, np.ndarray], *, sample_rate_hz: float, pubsub: PubSub) -> Dict[str, np.ndarray]:
        if self._sock is None:
            return {}
        iq = inputs.get("iq")
        if iq is None:
            return {}

        topic = self._params.get("topic", b"")
        if isinstance(topic, str):
            topic = topic.encode("utf-8")

        payload = iq.astype(np.complex64, copy=False).tobytes(order="C")
        if topic:
            self._sock.send(topic + payload)
        else:
            self._sock.send(payload)
        return {}
