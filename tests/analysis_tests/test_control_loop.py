"""Tests for pyontrust.analysis.control_loop — ZOH discretization, PID, margins."""

from __future__ import annotations

import math

import numpy as np
import pytest

from pyontrust.analysis.control_loop import (
    DiscretePID,
    TransferFunction,
    bode_response,
    gain_phase_margin,
    relay_test_to_zn,
    simulate_closed_loop,
    step_metrics,
    tune_ziegler_nichols,
    zoh_discretize,
)

DT = 0.01


# ── ZOH discretization ──────────────────────────────────────────────────────

def test_zoh_first_order_matches_analytic():
    """G(s)=2/(0.5s+1): A_d=e^{-dt/tau}, B_d=(1-A_d)/|A|, C=k/tau."""
    plant = TransferFunction(num=(2.0,), den=(0.5, 1.0))
    A_d, B_d, C_d, D_d = zoh_discretize(plant, DT)

    a_exact = math.exp(-DT / 0.5)
    assert float(A_d[0, 0]) == pytest.approx(a_exact, rel=1e-9)
    b_exact = (1.0 - a_exact) * 0.5          # tau*(1-e^{-dt/tau})
    assert float(B_d[0, 0]) == pytest.approx(b_exact, rel=1e-9)
    assert float(C_d[0, 0]) == pytest.approx(2.0 / 0.5, rel=1e-12)   # k/tau
    assert float(D_d[0, 0]) == pytest.approx(0.0, abs=1e-12)

    # DC gain of the discrete realization must equal the continuous one (k=2)
    dc = float((C_d @ np.linalg.inv(np.eye(1) - A_d) @ B_d + D_d)[0, 0])
    assert dc == pytest.approx(2.0, rel=1e-9)


def test_zoh_second_order_dc_gain():
    """G(s)=4/(s^2+2s+4): DC gain 1 — canonical form must preserve it."""
    plant = TransferFunction(num=(4.0,), den=(1.0, 2.0, 4.0))
    A_d, B_d, C_d, D_d = zoh_discretize(plant, DT)
    dc = float((C_d @ np.linalg.inv(np.eye(A_d.shape[0]) - A_d) @ B_d + D_d)[0, 0])
    assert dc == pytest.approx(4.0 / 4.0, rel=1e-9)


def test_zoh_rejects_improper():
    with pytest.raises(ValueError):
        zoh_discretize(TransferFunction(num=(1.0, 2.0), den=(1.0)), DT)


# ── discrete PID ────────────────────────────────────────────────────────────

def test_pid_p_only_step_output():
    pid = DiscretePID(kp=3.0)
    assert pid.step(2.0, DT) == pytest.approx(6.0)


def test_pid_anti_windup_keeps_integral_bounded():
    """Saturated output + constant error: integral must not wind up."""
    pid = DiscretePID(kp=5.0, ki=5.0, output_limits=(-0.5, 0.5))
    for _ in range(2000):                     # 20 s of full-scale error
        u = pid.step(1.0, DT)
    assert u == pytest.approx(0.5)            # clamped at the limit
    assert abs(pid._i) < 10.0           # bounded (would be ~100 without AW)


def _tf_impulse_response(num, den, n):
    """Impulse response of N(z)/D(z) (descending coeffs) via series in q=z^-1."""
    # rewrite both as polynomials in q = z^-1 (ascending), cancelling the common z^2 factor
    # multiply N and D by q^2 to get polynomials in q, then long-divide.
    # Descending-z coefficients are already ascending-q coefficients.
    nq = list(num)
    dq = list(den)
    h = []
    for m in range(n):
        s = (nq[m] if m < len(nq) else 0.0)
        for k in range(1, min(m, len(dq) - 1) + 1):
            s -= dq[k] * h[m - k]
        h.append(s / dq[0])
    return h


def test_pid_to_z_transfer():
    pid = DiscretePID(kp=2.0, ki=4.0, kd=0.5)
    num, den = pid.to_z(DT)
    # C(z) = kp + ki·dt·z/(z-1) + (kd/dt)(z-1)/z over common denominator z(z-1):
    #   num = (kp + ki·dt + kd/dt, -(kp + 2kd/dt), kd/dt);  den = (1, -1, 0)
    assert list(den) == [1.0, -1.0, 0.0]
    assert float(num[0]) == pytest.approx(2.0 + 4.0 * DT + 0.5 / DT)
    assert float(num[1]) == pytest.approx(-(2.0 + 2.0 * 0.5 / DT))
    assert float(num[2]) == pytest.approx(0.5 / DT)

    # ground truth: z-domain model must reproduce step()'s impulse response exactly
    h_tf = _tf_impulse_response(num, den, 12)
    pid.reset()
    h_sim = [pid.step(1.0 if k == 0 else 0.0, DT) for k in range(12)]
    assert h_sim == pytest.approx(h_tf, rel=1e-9)


# ── closed-loop simulation ──────────────────────────────────────────────────

def test_pi_regulates_first_order_plant_to_zero_error():
    plant = TransferFunction(num=(1.0,), den=(1.0, 1.0))   # G=1/(s+1)
    A_d, B_d, C_d, D_d = zoh_discretize(plant, DT)
    pid = DiscretePID(kp=1.0, ki=1.0)

    res = simulate_closed_loop(A_d, B_d, C_d, D_d, pid, DT, int(20.0 / DT), reference=1.0)
    t, y = res["t"], res["output"]
    assert len(t) == len(y)
    assert float(y[-1]) == pytest.approx(1.0, abs=5e-3)     # zero steady-state error
    m = step_metrics(t, y, 1.0)
    assert m["steady_state_error"] < 5e-3


def test_step_metrics_on_analytic_first_order():
    t = np.arange(0.0, 20.0 + DT, DT)
    y = 1.0 - np.exp(-t)                                    # no overshoot
    m = step_metrics(t, y, 1.0)
    assert m["overshoot_pct"] == pytest.approx(0.0, abs=1e-9)
    assert m["steady_state"] == pytest.approx(1.0, abs=1e-3)
    # rise time 10->90 %: ln(9) = 2.197 s for a first-order plant
    assert m["rise_time_10_90_s"] == pytest.approx(math.log(9.0), rel=0.05)
    # settling (2 %): -ln(0.02) = 3.912 s
    assert m["settling_time_2pct_s"] == pytest.approx(-math.log(0.02), rel=0.08)


# ── Bode + margins ─────────────────────────────────────────────────────────

def test_bode_margins_match_analytic_triple_lag():
    """L(s)=2/(s+1)^3 with pure-P loop: PM≈67.5° @ 0.122 Hz; no gain margin
    (phase lag saturates at −90°, so the −180° crossing never occurs)."""
    plant = TransferFunction(num=(1.0,), den=(1.0, 3.0, 3.0, 1.0))
    A_d, B_d, C_d, D_d = zoh_discretize(plant, DT)
    pid = DiscretePID(kp=2.0)

    # loop L(z) = C_PID(z)·P_d(z), swept on the unit circle by the library API
    freqs_hz, mag_db, phase_deg = bode_response(A_d, B_d, C_d, D_d, DT,
                                                f_min_hz=0.01, f_max_hz=2.0, n_points=800, pid=pid)

    m = gain_phase_margin(freqs_hz, mag_db, phase_deg)
    assert m["phase_margin_deg"] == pytest.approx(67.5, abs=2.5)
    assert m["gain_margin_db"] is None          # no −180° crossing for this loop
    assert 0.1 < m["crossover_freq_hz"] < 0.2


def test_bode_response_api_first_order():
    """Sanity: PI on G=1/(s+1) — low-freq phase ≈ -90°, magnitude → ∞."""
    plant = TransferFunction(num=(1.0,), den=(1.0, 1.0))
    A_d, B_d, C_d, D_d = zoh_discretize(plant, DT)
    pid = DiscretePID(kp=1.0, ki=1.0)

    freqs_hz, mag_db, phase_deg = bode_response(A_d, B_d, C_d, D_d, DT,
                                                f_min_hz=0.02, f_max_hz=5.0, n_points=300, pid=pid)
    assert len(freqs_hz) == 300
    # at the lowest frequency the integrator dominates: phase near -90°
    assert phase_deg[0] == pytest.approx(-90.0, abs=8.0)
    assert mag_db[0] > 15.0                     # large loop gain at low freq


# ── tuning helpers ─────────────────────────────────────────────────────────

def test_ziegler_nichols_exact_values():
    zn = tune_ziegler_nichols(k_ultimate=10.0, period_ultimate_s=2.0)
    assert zn["kp"] == pytest.approx(6.0)
    assert zn["ki"] == pytest.approx(6.0)
    assert zn["kd"] == pytest.approx(1.5)


def test_relay_test_conversion():
    # delta/a = 2 → Ku = 4*2/pi; Tu = 1 s
    zn = relay_test_to_zn(amp=2.0, period_s=1.0)
    ku = 8.0 / math.pi
    assert zn["kp"] == pytest.approx(0.6 * ku)


def test_relay_test_rejects_bad_input():
    with pytest.raises(ValueError):
        relay_test_to_zn(amp=-1.0, period_s=1.0)
