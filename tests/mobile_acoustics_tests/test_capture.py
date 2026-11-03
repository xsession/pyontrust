"""Multi-phone capture orchestration."""
import numpy as np
from mobile_acoustics import MicStream, MultiMicCapture


def test_capture_returns_all_channels(rig):
    streams = [MicStream(source_id=f"p{i}", grabber=lambda: np.ones(10), sample_rate=48000, position=m)
               for i, m in enumerate(rig["mics"])]
    cap = MultiMicCapture(streams)
    shot = cap.capture()
    assert set(shot.keys()) == {f"p{i}" for i in range(len(rig["mics"]))}
    for s in streams:
        entry = shot[s.source_id]
        assert len(entry["waveform"]) == 10
        assert "t_start_ms" in entry and entry["sample_rate"] == 48000


def test_single_stream_rejected():
    try:
        MultiMicCapture([MicStream(source_id="only", grabber=lambda: np.ones(4))])
        raise AssertionError("expected ValueError")
    except ValueError:
        pass


def test_positions_property(rig):
    streams = [MicStream(source_id=f"p{i}", grabber=lambda: np.ones(10), position=m)
               for i, m in enumerate(rig["mics"])]
    cap = MultiMicCapture(streams)
    assert len(cap.positions) == 4 and all(p is not None for p in cap.positions)
