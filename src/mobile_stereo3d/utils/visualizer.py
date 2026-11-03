"""Real-time / offline 3-D visualization (matplotlib; Open3D optional)."""

from __future__ import annotations

from pathlib import Path
from typing import Sequence

import numpy as np


class Visualizer3D:
    """Render point clouds + trajectories. Headless-safe (Agg backend)."""

    def __init__(self, figsize: tuple[int, int] = (8, 6)) -> None:
        self.figsize = figsize

    def plot_trajectories(self, tracks: Sequence, title: str = "3D trajectories",
                          save_path: str | Path | None = None) -> None:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        from mpl_toolkits.mplot3d import Axes3D  # noqa: F401

        fig = plt.figure(figsize=self.figsize)
        ax = fig.add_subplot(111, projection="3d")
        for i, tr in enumerate(tracks):
            t = np.asarray(tr.trajectory if hasattr(tr, "trajectory") else tr.positions)
            if len(t) == 0:
                continue
            c = plt.cm.tab10(i % 10)
            ax.plot(t[:, 0], t[:, 1], t[:, 2], "-", color=c, lw=1.5, label=f"track {i}")
            ax.scatter(*t[-1].T if len(t) else [0, 0, 0], color=c, s=40)
        ax.set_xlabel("X"); ax.set_ylabel("Y"); ax.set_zlabel("Z")
        ax.legend(fontsize=7)
        fig.suptitle(title)
        if save_path:
            fig.savefig(save_path, dpi=120, bbox_inches="tight")
        plt.close(fig)

    def plot_point_cloud(self, points: np.ndarray, title: str = "point cloud",
                         save_path: str | Path | None = None) -> None:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        fig = plt.figure(figsize=self.figsize)
        ax = fig.add_subplot(111, projection="3d")
        p = np.asarray(points)
        if len(p):
            ax.scatter(p[:, 0], p[:, 1], p[:, 2], s=6, c=p[:, 0] + p[:, 1], cmap="viridis")
        ax.set_xlabel("X"); ax.set_ylabel("Y"); ax.set_zlabel("Z")
        fig.suptitle(title)
        if save_path:
            fig.savefig(save_path, dpi=120, bbox_inches="tight")
        plt.close(fig)


__all__ = ["Visualizer3D"]
