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


def test_pid_to_z_transfer():
    pid = DiscretePID(kp=2.0, ki=4.0, kd=0.5)
    num, den = pid.to_z(DT)
    assert list(den) == [1.0, -1.0, 0.0]
    # num = kp z^2 + (ki*T + kd - kp) z - kd
    assert float(num[0]) == pytest.approx(2.0)
    assert float(num[1]) == pytest.approx(4.0 * DT + 0.5 - 2.0)
    assert float(num[2]) == pytest.approx(-0.5)


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

def _ss_to_poly(A_d: np.ndarray, B_d: np.ndarray, C_d: np.ndarray, D_d: np.ndarray):
    """z-polys (ascending) of G(z)=C(zI-A)^{-1}B+D for controllable canonical form."""
    n = A_d.shape[0]
    if n == 0:
        return np.array([float(D_d[0, 0])]), np.array([1.0])
    den_asc = np.append(-A_d[n - 1, :][::-1], 1.0)          # z^n + d1 z^{n-1}+...+dn
    b = float(B_d[-1, 0])
    num_asc = C_d[0, :] * b + float(D_d[0, 0]) * den_asc     # strictly proper part + D·den
    return num_asc, den_asc


def test_bode_margins_match_analytic_triple_lag():
    """L(s)=2/(s+1)^3: PM≈67.5° @ 0.122 Hz, GM=12.04 dB @ 0.276 Hz."""
    plant = TransferFunction(num=(1.0,), den=(1.0, 3.0, 3.0, 1.0))
    A_d, B_d, C_d, D_d = zoh_discretize(plant, DT)
    pid = DiscretePID(kp=2.0)

    cnum, cden = pid.to_z(DT)
    # loop L(z) = C(z)*P_d(z): multiply polynomials (numpy conv), evaluate on jw
    num_l = np.convolve(cnum, _ss_to_poly(A_d, B_d, C_d, D_d)[0])
    den_l = np.convolve(cden, _ss_to_poly(A_d, B_d, C_d, D_d)[1])

    freqs_hz = np.logspace(-2, 1.0, 600)
    mag_db, phase_deg = [], []
    for f in freqs_hz:
        z = complex(math.cos(2 * math.pi * f * DT), math.sin(2 * math.pi * f * DT))
        g = np.polyval(num_l, z) / np.polyval(den_l, z)
        mag_db.append(20.0 * math.log10(max(abs(g), 1e-300)))
        phase_deg.append(math.degrees(math.atan2(g.imag, g.real)))
    mag_db = np.asarray(mag_db)
    # unwrap around the low-frequency branch
    wrapped = np.mod(np.asarray(phase_deg) + 180.0, 360.0) - 180.0
    dphi = np.diff(wrapped, prepend=wrapped[0])
    big = np.abs(dphi) > 180.0
    dphi[big] += np.sign(-dphi[big]) * 360.0
    phase_deg = np.cumsum(dphi)

    m = gain_phase_margin(freqs_hz, mag_db, phase_deg)
    assert m["phase_margin_deg"] == pytest.approx(67.5, abs=2.5)
    assert m["gain_margin_db"] == pytest.approx(12.04, abs=0.35)
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
