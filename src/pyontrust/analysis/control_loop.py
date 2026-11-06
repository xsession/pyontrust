"""Control loop design & closed-loop simulation (numpy-only core).

Tools for designing and verifying digital control loops on lab-bench / HIL
rigs:

* :class:`TransferFunction` — continuous SISO plant models + presets.
* :func:`zoh_discretize` — exact ZOH discretization to state space
  (pure-numpy matrix exponential; no scipy required).
* :class:`DiscretePID` — parallel-form discrete PID with output clamping and
  back-calculation anti-windup; also exports its z-domain transfer function.
* :func:`bode_response` / :func:`gain_phase_margin` — open-loop magnitude &
  phase, gain/phase margins from a frequency sweep.
* :func:`simulate_closed_loop` — discrete time-step simulation of PID + plant.
* :func:`step_metrics` — rise/settling/overshoot/steady-state error.
* :func:`relay_test_to_zn` / :func:`tune_ziegler_nichols` — classic relay
  (ultimate gain) tuning for when you have a measured oscillation.

All functions are JSON-friendly and dependency-light: numpy is required
(``pyontrust[analysis]``), scipy/matplotlib are *not* needed.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Sequence

import numpy as np

__all__ = [
    "TransferFunction",
    "DiscretePID",
    "zoh_discretize",
    "bode_response",
    "gain_phase_margin",
    "simulate_closed_loop",
    "step_metrics",
    "tune_ziegler_nichols",
    "relay_test_to_zn",
]


# ── continuous plant model ──────────────────────────────────────────────────

@dataclass(frozen=True)
class TransferFunction:
    """Continuous-time SISO transfer function ``num(s)/den(s)``.

    Coefficient tuples are in *descending* powers of s (control-toolbox style):
    ``(1, 2, 3)`` → ``s² + 2s + 3``.
    """

    num: tuple[float, ...]
    den: tuple[float, ...]

    def __post_init__(self) -> None:
        def _norm(c: object, what: str) -> tuple[float, ...]:
            if isinstance(c, (int, float)):
                c = (float(c),)
            try:
                out = tuple(float(v) for v in c)  # type: ignore[union-attr]
            except TypeError as exc:
                raise ValueError(f"{what} must be a number or sequence of numbers") from exc
            if not out:
                raise ValueError(f"{what} must be non-empty")
            return out

        object.__setattr__(self, "num", _norm(self.num, "num"))
        object.__setattr__(self, "den", _norm(self.den, "den"))
        if self.den[0] == 0.0:
            raise ValueError("den[0] (leading coefficient) must be non-zero")

    # ── presets ────────────────────────────────────────────────────────
    @classmethod
    def first_order(cls, tau_s: float, k: float = 1.0) -> "TransferFunction":
        """``k / (tau·s + 1)``."""
        if tau_s <= 0:
            raise ValueError("tau_s must be > 0")
        return cls((float(k),), (float(tau_s), 1.0))

    @classmethod
    def second_order(cls, wn_rad_s: float, zeta: float, k: float = 1.0) -> "TransferFunction":
        """``k·wn² / (s² + 2ζwn·s + wn²)``."""
        if wn_rad_s <= 0 or zeta < 0:
            raise ValueError("need wn > 0 and zeta >= 0")
        return cls((float(k) * wn_rad_s ** 2,),
                   (1.0, 2.0 * zeta * wn_rad_s, float(wn_rad_s) ** 2))

    @classmethod
    def integrator(cls, k: float = 1.0) -> "TransferFunction":
        """``k / s``."""
        return cls((float(k),), (1.0, 0.0))


# ── matrix exponential (scaling & squaring + Taylor) ───────────────────────

def _mat_exp(A: np.ndarray, t: float) -> np.ndarray:
    """expm(A·t) for small real matrices — scaling & squaring with a Taylor
    series on the scaled argument. Accurate to ~1e-12 for ||A·t|| ≲ 50."""
    n = A.shape[0]
    M = np.asarray(A, dtype=float) * t
    norm = float(np.max(np.abs(M))) if M.size else 0.0
    s = max(0, int(math.ceil(math.log2(max(norm, 1e-300) / 0.5))))
    S = M / (2 ** s)

    term = np.eye(n)
    total = np.eye(n)
    for k in range(1, 40):
        term = term @ S / k
        new_total = total + term
        if float(np.max(np.abs(term))) < 1e-16 * max(1.0, float(np.max(np.abs(total)))):
            total = new_total
            break
        total = new_total

    for _ in range(s):
        total = total @ total
    return total


# ── ZOH discretization ──────────────────────────────────────────────────────

def zoh_discretize(tf: TransferFunction, dt_s: float) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Discretize ``num(s)/den(s)`` with a zero-order hold at period ``dt_s``.

    Returns state-space ``(A_d, B_d, C_d, D_d)`` in controllable canonical form:
        x[k+1] = A_d·x[k] + B_d·u[k]
        y[k]   = C_d·x[k] + D_d·u[k]

    Uses the exact block-matrix exponential (no scipy needed).
    """
    if dt_s <= 0:
        raise ValueError("dt_s must be > 0")

    num = np.asarray(tf.num, dtype=float) / tf.den[0]
    den = np.asarray(tf.den, dtype=float) / tf.den[0]
    n = len(den) - 1
    if len(num) > n + 1:
        raise ValueError("improper transfer function (num order must be <= den order)")

    if n == 0:
        # pure gain — zero-state realization: y[k] = k·u[k]
        return (np.zeros((0, 0)), np.zeros((0, 1)),
                np.zeros((1, 0)), np.array([[float(num[0])]]))

    # split off any direct feedthrough term; the remainder is strictly proper
    d_feed = float(num[0]) if len(num) == n + 1 else 0.0
    sp_num = num[1:] if len(num) == n + 1 else num   # descending, order <= n-1

    A = np.zeros((n, n))
    for i in range(n - 1):
        A[i, i + 1] = 1.0
    A[n - 1, :] = -den[1:n + 1][::-1]           # companion (controllable canonical)

    Bv = np.zeros((n, 1))
    Bv[-1, 0] = 1.0                            # e_n — controllable canonical form
    C_d = np.zeros(n)
    for i in range(min(n, len(sp_num))):
        C_d[i] = sp_num[len(sp_num) - 1 - i]   # coefficient of s^i (ascending)

    # exact ZOH via the block exponential [[A,B],[0,0]]:
    #   expm([[A B],[0 0]]·dt) = [[e^{Adt}, ∫₀^dt e^{Aσ}dσ·B], [0, 1]]
    M = np.zeros((n + 1, n + 1))
    M[:n, :n] = A
    M[:n, n] = Bv[:, 0]
    E = _mat_exp(M, dt_s)
    A_d = E[:n, :n].copy()
    B_d = E[:n, n:].copy()

    D_d = np.array([[d_feed]])
    return A_d, B_d, C_d.reshape(1, -1), D_d


# ── discrete PID ────────────────────────────────────────────────────────────

@dataclass
class DiscretePID:
    """Parallel-form discrete PID with anti-windup.

    u[k] = kp·e[k] + i[k] + kd·(e[k] − e[k−1])/dt,   i[k+1] = i[k] + ki·e[k]·dt

    Anti-windup: output is clamped to ``output_limits``; when clamping occurs
    the integrator state is pulled back by ``back_calc_gain · (u_clamped − u_raw)``
    (set ``back_calc_gain=0`` for plain clamp-only behaviour).
    """

    kp: float = 1.0
    ki: float = 0.0
    kd: float = 0.0
    output_limits: tuple[float, float] | None = None
    back_calc_gain: float = 1.0

    _i: float = field(default=0.0, init=False, repr=False)
    _prev_err: float = field(default=0.0, init=False, repr=False)

    def __post_init__(self) -> None:
        if self.output_limits is not None:
            lo, hi = self.output_limits
            if lo > hi:
                raise ValueError("output_limits must be (low, high) with low <= high")

    def reset(self) -> None:
        self._i = 0.0
        self._prev_err = 0.0

    def step(self, error: float, dt_s: float) -> float:
        """Advance one sample; returns the control output."""
        if dt_s <= 0:
            raise ValueError("dt_s must be > 0")
        p = self.kp * error
        i_new = self._i + self.ki * error * dt_s
        d = self.kd * (error - self._prev_err) / dt_s
        u_raw = p + i_new + d

        lo, hi = self.output_limits if self.output_limits is not None else (-math.inf, math.inf)
        u = min(max(u_raw, lo), hi)

        if u != u_raw and self.back_calc_gain > 0.0:
            i_new += self.back_calc_gain * (u - u_raw)
        self._i = i_new
        self._prev_err = error
        return float(u)

    def to_z(self, dt_s: float) -> tuple[tuple[float, ...], tuple[float, ...]]:
        """z-domain transfer function of this PID (ideal derivative).

        C(z) = [a·z² + b·z + c] / [z² − z] with
            a = kp + ki·dt + kd/dt,  b = −kp − 2kd/dt,  c = kd/dt
        (parallel form: P + forward-Euler integrator + backward-difference
        derivative; pure-P reduces exactly to C(z) = kp).
        """
        num = (self.kp + self.ki * dt_s + self.kd / dt_s,
               -self.kp - 2.0 * self.kd / dt_s,
               self.kd / dt_s)
        den = (1.0, -1.0, 0.0)
        return num, den


# ── frequency response & margins ───────────────────────────────────────────

def _ss_freq_response(A_d: np.ndarray, B_d: np.ndarray, C_d: np.ndarray, D_d: np.ndarray,
                      z: complex) -> complex:
    """G(z) at a single point: C·(zI−A)⁻¹B + D."""
    n = A_d.shape[0]
    if n == 0:
        return complex(D_d[0, 0])
    try:
        X = np.linalg.solve(z * np.eye(n) - A_d, B_d)
    except np.linalg.LinAlgError:
        X = np.linalg.pinv(z * np.eye(n) - A_d) @ B_d
    return complex((C_d @ X + D_d)[0, 0])


def bode_response(A_d: np.ndarray, B_d: np.ndarray, C_d: np.ndarray, D_d: np.ndarray,
                  dt_s: float, f_min_hz: float = 1e-3, f_max_hz: float | None = None,
                  n_points: int = 400, pid: "DiscretePID | None" = None) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Open-loop Bode data on the unit circle.

    Returns ``(freqs_hz, mag_db, phase_deg)`` with phase unwrapped to (−360, 360).
    ``f_max_hz`` defaults to just below the Nyquist frequency. When ``pid`` is
    given, the loop gain L(z) = C_PID(z)·P_d(z) is swept instead of the plant
    alone — that is what gain/phase margins are defined for.
    """
    if dt_s <= 0:
        raise ValueError("dt_s must be > 0")
    f_nyq = 1.0 / (2.0 * dt_s)
    f_max = min(f_max_hz or 0.98 * f_nyq, 0.99 * f_nyq)
    if f_min_hz <= 0 or f_min_hz >= f_max:
        raise ValueError("need 0 < f_min_hz < f_max")

    c_num: tuple[float, ...] | None = None
    c_den: tuple[float, ...] | None = None
    if pid is not None:
        c_num, c_den = pid.to_z(dt_s)

    freqs = np.geomspace(f_min_hz, f_max, n_points)
    mag_db = np.empty_like(freqs)
    phase_deg = np.empty_like(freqs)
    for i, f in enumerate(freqs):
        z = complex(math.cos(2 * math.pi * f * dt_s), math.sin(2 * math.pi * f * dt_s))
        g = _ss_freq_response(A_d, B_d, C_d, D_d, z)
        if c_num is not None:
            cz = z * z
            g *= (c_num[0] * cz + c_num[1] * z + c_num[2]) / \
                 (c_den[0] * cz + c_den[1] * z + c_den[2])
        mag_db[i] = 20.0 * math.log10(max(abs(g), 1e-300))
        phase_deg[i] = math.degrees(math.atan2(g.imag, g.real))

    # unwrap to a continuous branch around the low-frequency value
    wrapped = np.mod(phase_deg + 180.0, 360.0) - 180.0
    dphi = np.diff(wrapped, prepend=wrapped[0])
    dphi[np.abs(dphi) > 180.0] += (np.sign(-dphi[np.abs(dphi) > 180.0])) * 360.0
    phase_deg = wrapped[0] + np.concatenate(([0.0], np.cumsum(dphi[1:])))
    return freqs, mag_db, phase_deg


def gain_phase_margin(freqs_hz: np.ndarray, mag_db: np.ndarray,
                      phase_deg: np.ndarray) -> dict[str, float | None]:
    """Gain/phase margins from Bode data (linear interpolation at crossings).

    Returns ``{"gain_margin_db": ..., "phase_margin_deg": ...,
    "crossover_freq_hz": ...}``; values are ``None`` when the crossing does not
    exist in the swept range.
    """
    out: dict[str, float | None] = {"gain_margin_db": None,
                                    "phase_margin_deg": None,
                                    "crossover_freq_hz": None}

    # phase crosses -180 → gain margin
    p = np.where(phase_deg < 0.0, phase_deg, phase_deg - 360.0) if False else phase_deg
    cross_idx = np.where(np.diff(np.sign(p + 180.0)) != 0)[0]
    for i in cross_idx:
        f0, f1 = freqs_hz[i], freqs_hz[i + 1]
        p0, p1 = phase_deg[i], phase_deg[i + 1]
        t = (p0 + 180.0) / ((p0 + 180.0) - (p1 + 180.0)) if p1 != p0 else 0.5
        fc = f0 * (f1 / f0) ** t
        m0, m1 = mag_db[i], mag_db[i + 1]
        mc = math.exp(math.log(m0) + t * (math.log(m1) - math.log(m0))) if m0 > 0 and m1 > 0 else None
        if out["gain_margin_db"] is None or fc < (out.get("_gm_fc") or math.inf):
            out["gain_margin_db"] = -mc if mc is not None else None
            out["_gm_fc"] = fc

    # |L| crosses 0 dB → phase margin + crossover frequency
    cross_idx = np.where(np.diff(np.sign(mag_db)) != 0)[0]
    for i in cross_idx:
        f0, f1 = freqs_hz[i], freqs_hz[i + 1]
        m0, m1 = mag_db[i], mag_db[i + 1]
        t = (0.0 - m0) / (m1 - m0) if m1 != m0 else 0.5
        fc = f0 * (f1 / f0) ** t
        p0, p1 = phase_deg[i], phase_deg[i + 1]
        pc = p0 + t * (p1 - p0)
        pm = 180.0 + pc if pc < 0 else pc - 180.0
        if out["phase_margin_deg"] is None or fc < (out.get("_pm_fc") or math.inf):
            out["phase_margin_deg"] = float(pm)
            out["crossover_freq_hz"] = float(fc)
            out["_pm_fc"] = fc

    out.pop("_gm_fc", None)
    out.pop("_pm_fc", None)
    return out


# ── closed-loop simulation ──────────────────────────────────────────────────

def simulate_closed_loop(A_d: np.ndarray, B_d: np.ndarray, C_d: np.ndarray, D_d: np.ndarray,
                         pid: DiscretePID, dt_s: float, n_steps: int,
                         reference: Sequence[float] | float = 1.0,
                         disturbance: Sequence[float] | None = None) -> dict[str, Any]:
    """Simulate ``y[k+1]`` of PID + discretized plant for ``n_steps`` samples.

    The controller sees the measured output (no sensor noise model); an optional
    additive output disturbance sequence is applied after the plant update.
    Returns ``{"t": ..., "reference": ..., "output": ..., "control": ...}``.
    """
    if n_steps <= 0:
        raise ValueError("n_steps must be > 0")
    ref = np.full(n_steps, float(reference)) if isinstance(reference, (int, float)) \
        else np.asarray(reference, dtype=float)
    if len(ref) != n_steps:
        raise ValueError("reference length must equal n_steps")

    x = np.zeros(A_d.shape[0])
    y_out = np.empty(n_steps)
    u_out = np.empty(n_steps)
    pid.reset()
    for k in range(n_steps):
        r_k = float(ref[k])
        e_k = r_k - (float(y_out[k - 1]) if k > 0 else 0.0)
        u_k = pid.step(e_k, dt_s)
        x = A_d @ x + B_d[:, 0] * u_k
        y_k = float(np.ravel(C_d @ x)[0] + np.ravel(D_d)[0] * u_k)
        if disturbance is not None:
            d_seq = np.asarray(disturbance, dtype=float)
            if len(d_seq) == n_steps:
                y_k += float(d_seq[k])
        y_out[k] = y_k
        u_out[k] = u_k

    return {"t": np.arange(n_steps) * dt_s, "reference": ref,
            "output": y_out, "control": u_out}


def step_metrics(t: np.ndarray, output: np.ndarray, reference: float = 1.0,
                 settle_band_pct: float = 2.0) -> dict[str, float | None]:
    """Classic step-response metrics (all times in seconds)."""
    t = np.asarray(t, dtype=float)
    y = np.asarray(output, dtype=float)
    if len(t) != len(y) or len(t) < 3:
        raise ValueError("need at least 3 aligned samples")

    r = float(reference)
    band = settle_band_pct / 100.0 * abs(r)
    y_ss = float(np.mean(y[-max(5, len(y) // 20):]))
    overshoot = None
    if r > 0:
        peak = float(np.max(y))
        overshoot = max(0.0, (peak - r) / abs(r) * 100.0)

    rise_10 = _first_crossing(t, y, 0.1 * r) if r > 0 else None
    rise_90 = _first_crossing(t, y, 0.9 * r) if r > 0 else None
    t_rise = (rise_90 - rise_10) if (rise_10 is not None and rise_90 is not None) else None

    # settling time: first sample after which the signal stays within ±band of r
    in_band = np.abs(y - r) <= band
    n_s = len(y)
    last_violation = max([k for k in range(n_s) if not bool(in_band[k])] + [-1])
    t_settle = float(t[last_violation + 1]) if last_violation < n_s - 1 else None

    return {
        "steady_state": y_ss,
        "steady_state_error": abs(r - y_ss),
        "overshoot_pct": overshoot,
        "rise_time_10_90_s": t_rise,
        "settling_time_2pct_s": t_settle,
    }


def _first_crossing(t: np.ndarray, y: np.ndarray, level: float) -> float | None:
    idx = np.where(y >= level)[0]
    return float(t[idx[0]]) if len(idx) else None


def _stays_in_band(t: np.ndarray, y: np.ndarray, r: float, band: float, start_idx: int) -> bool:
    """True when the signal stays within ±band of r from ``start_idx`` onward."""
    return bool(np.all(np.abs(y[start_idx:] - r) <= band))


# ── tuning helpers ─────────────────────────────────────────────────────────

def tune_ziegler_nichols(k_ultimate: float, period_ultimate_s: float) -> dict[str, float]:
    """Classic Ziegler–Nichols PID from the ultimate gain/period.

    ``k_ultimate`` is the gain at which sustained oscillation appears and
    ``period_ultimate_s`` that oscillation's period (e.g. from a relay test).
    """
    if k_ultimate <= 0 or period_ultimate_s <= 0:
        raise ValueError("need positive ultimate gain and period")
    return {
        "kp": 0.6 * k_ultimate,
        "ki": 2.0 * (0.6 * k_ultimate) / period_ultimate_s,
        "kd": (0.6 * k_ultimate) * period_ultimate_s / 8.0,
    }


def relay_test_to_zn(amp: float, period_s: float) -> dict[str, float]:
    """Convert a measured relay oscillation to Ziegler–Nichols gains.

    ``k_ultimate ≈ 4·δ/(π·a)`` where δ is the relay half-amplitude and a the
    process oscillation amplitude — pass ``amp=2δ/a`` (i.e. δ divided by a,
    times 2) or simply supply the ratio δ/a as ``amp``; this helper treats
    ``amp`` as δ/a directly: Ku = 4·(δ/a)/π.
    """
    if amp <= 0 or period_s <= 0:
        raise ValueError("need positive relay amplitude ratio and period")
    k_ultimate = 4.0 * amp / math.pi
    return tune_ziegler_nichols(k_ultimate, period_s)
