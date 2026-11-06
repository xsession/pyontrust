"""Triangulation round-trip: project known 3-D points, recover them."""
import numpy as np
import pytest
from pyontrust.mobile.stereo3d import Triangulator


def test_single_point_recovery(rig):
    K, R, T = rig["K"], rig["R"], rig["T"]
    P = np.array([10., 8., 150.])
    p1 = (lambda v: v[:2] / v[2])(K @ P)
    p2 = (lambda v: v[:2] / v[2])(K @ (R @ P + T))
    tri = Triangulator(rig["calib"])
    rec = tri.triangulate(p1.reshape(1, 2), p2.reshape(1, 2))
    assert np.linalg.norm(rec[0] - P) < 1e-6


def test_multiple_points_recovery(rig):
    K, R, T = rig["K"], rig["R"], rig["T"]
    rng = np.random.default_rng(7)
    xy = rng.uniform(-30, 30, size=(8, 2))
    z = rng.uniform(50., 400., size=8)
    P = np.hstack([xy, z[:, None]])
    p1 = np.array([(K @ p)[:2] / (K @ p)[2] for p in P])
    p2 = np.array([(K @ (R @ p + T))[:2] / (K @ (R @ p + T))[2] for p in P])
    tri = Triangulator(rig["calib"])
    rec = tri.triangulate(p1, p2)
    assert len(rec) == 8
    assert np.linalg.norm(rec - P, axis=1).max() < 1e-4


def test_rejects_mismatched_lengths(rig):
    tri = Triangulator(rig["calib"])
    with pytest.raises(ValueError):
        tri.triangulate(np.zeros((3, 2)), np.zeros((2, 2)))


def test_empty_returns_empty(rig):
    tri = Triangulator(rig["calib"])
    out = tri.triangulate(np.zeros((0, 2)), np.zeros((0, 2)))
    assert len(out) == 0
