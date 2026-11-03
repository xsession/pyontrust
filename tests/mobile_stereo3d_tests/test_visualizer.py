"""Headless 3-D visualization (PNG output)."""
import numpy as np
from mobile_stereo3d import Tracker3D, Visualizer3D


def test_plot_trajectories(tmp_path):
    trk = Tracker3D()
    P = np.array([1., 2., 3.])
    for t in range(5):
        trk.update((P + [t, 0, 0]).reshape(1, 3), time_ms=t * 50)
    out = tmp_path / "traj.png"
    Visualizer3D().plot_trajectories(list(trk.tracks.values()), save_path=out)
    assert out.exists() and out.stat().st_size > 1000


def test_plot_point_cloud(tmp_path):
    rng = np.random.default_rng(1)
    pts = rng.uniform(-5, 5, size=(20, 3))
    out = tmp_path / "cloud.png"
    Visualizer3D().plot_point_cloud(pts, save_path=out)
    assert out.exists() and out.stat().st_size > 1000
