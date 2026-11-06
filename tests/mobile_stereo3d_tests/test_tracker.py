"""3-D trajectory tracking + CSV/JSON/PLY export."""
import numpy as np
from pyontrust.mobile.stereo3d import Tracker3D


def test_single_track_continuity():
    trk = Tracker3D(max_link_m=5.0)
    P = np.array([1., 2., 3.])
    for t in range(6):
        trk.update((P + [t * 2.0, 0., 0.]).reshape(1, 3), time_ms=t * 100)
    assert len(trk.tracks) == 1
    tr = next(iter(trk.tracks.values()))
    assert len(tr.positions) == 6


def test_two_objects_separated():
    trk = Tracker3D(max_link_m=5.0)
    A, B = np.array([0., 0., 10.]), np.array([20., 0., 10.])
    for t in range(4):
        trk.update(np.vstack([A + [t, 0, 0], B - [t, 0, 0]]), time_ms=t * 50)
    assert len(trk.tracks) == 2


def test_gap_reopens_track():
    trk = Tracker3D(max_link_m=1.0)
    P = np.array([0., 0., 10.])
    for t in range(3):
        trk.update((P + [t * 0.5, 0., 0.]).reshape(1, 3), time_ms=t * 100)
    assert len(trk.tracks) == 1
    # jump beyond the association gate → a new track starts
    for t in range(3):
        trk.update((P + [10. + t * 0.5, 0., 0.]).reshape(1, 3), time_ms=(t + 30) * 100)
    assert len(trk.tracks) == 2


def test_export_ply(tmp_path):
    trk = Tracker3D()
    P = np.array([1., 2., 3.])
    for t in range(4):
        trk.update((P + [t, 0, 0]).reshape(1, 3), time_ms=t * 50)
    out = tmp_path / "cloud.ply"
    n = trk.to_ply(out)
    assert n == 4 and out.exists()
    text = out.read_text()
    assert text.startswith("ply") and "element vertex 4" in text


def test_export_csv(tmp_path):
    trk = Tracker3D()
    P = np.array([1., 2., 3.])
    for t in range(4):
        trk.update((P + [t, 0, 0]).reshape(1, 3), time_ms=t * 50)
    out = tmp_path / "traj.csv"
    n = trk.to_csv(out)
    assert n == 4 and out.exists()
    header = out.read_text().splitlines()[0]
    assert header.split(",")[:2] == ["track_id", "t_ms"]


def test_export_json(tmp_path):
    import json
    trk = Tracker3D(max_link_m=2.0)  # gate wide enough to link the 1.0-unit steps
    P = np.array([1., 2., 3.])
    for t in range(4):
        trk.update((P + [t, 0, 0]).reshape(1, 3), time_ms=t * 50)
    out = tmp_path / "traj.json"
    trk.to_json(out)
    data = json.loads(out.read_text())
    assert len(data) == 1
    entry = next(iter(data.values()))
    assert len(entry["positions"]) == 4
