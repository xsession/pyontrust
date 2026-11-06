"""Timestamp alignment of two frame streams (synthetic, no device needed)."""
import numpy as np
from pyontrust.mobile.stereo3d import StreamSynchronizer
from pyontrust.mobile.stereo3d.sync.frame_stream import Frame


def _frames(ts_list, src):
    return [Frame(image=np.zeros((4, 4), np.uint8), timestamp_ms=t, source_id=src) for t in ts_list]


def _sync(tolerance_ms: float) -> StreamSynchronizer:
    """Synchronizer with two dummy streams (constructor requires >= 2)."""
    from pyontrust.mobile.stereo3d import FrameStream
    return StreamSynchronizer(
        streams=[FrameStream(lambda: None, source_id="L"),
                 FrameStream(lambda: None, source_id="R")],
        tolerance_ms=tolerance_ms)


def test_aligns_by_timestamp():
    sync = _sync(80.0)
    left = _frames([0., 100., 200.], "L")
    right = _frames([50., 150., 250.], "R")
    pairs = sync.match(left, right)
    assert len(pairs) == 3
    assert all(abs(p.delta_ms - 50.) < 1e-6 for p in pairs)


def test_rejects_out_of_skew():
    sync = _sync(80.0)
    left = _frames([0., 100.], "L")
    right = _frames([500., 600.], "R")
    assert sync.match(left, right) == []


def test_drift_correction():
    """Right stream drifts +10/+20 ms — still paired, deltas grow."""
    sync = _sync(60.0)
    left = _frames([0., 100., 200.], "L")
    right = _frames([0., 110., 230.], "R")
    pairs = sync.match(left, right)
    assert len(pairs) == 3
    deltas = [p.delta_ms for p in pairs]
    assert deltas[0] < deltas[-1]


def test_empty_inputs():
    sync = _sync(50.0)
    assert sync.match([], []) == []
