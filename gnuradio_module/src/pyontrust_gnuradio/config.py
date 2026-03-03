from __future__ import annotations

from dataclasses import dataclass


@dataclass
class GnuradioConfig:
    default_python: str = "python"
    default_conda_env: str = "gnuradio"
