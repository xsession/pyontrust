"""Acoustic sonar with the phone's own speaker (TX) and microphone (RX).

The device plays a linear FM chirp while its mic records (all timing is
device-side, see the ``sonar`` command in FastTelemetryService). The PC then
cross-correlates the recording against the locally generated reference chirp:

* first strong peak  = direct speaker->mic path (absorbs every clock/latency offset)
* later peaks        = reflections off objects at distance d = c * (lag - lag_direct) / 2

No external hardware, no clock sync — pure software on the fast link.

    from pyontrust.phone import FastLink
    from pyontrust.phone.sonar import PhoneSonar
    with FastLink() as link:
        res = PhoneSonar(link).ping(f0=2000, f1=8000)
        for p in res.peaks[1:]:          # skip the direct path
            print(p["distance_m"], "m")
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
import os
from typing import Any, Callable, Sequence

import numpy as np

SOUND_SPEED_M_S = 343.0


@dataclass(frozen=True)
class ChirpConfig:
    """Linear FM chirp parameters (must match the device's ``sonar_tx``/``sonar``)."""

    f0_hz: float = 2000.0
    f1_hz: float = 8000.0
    duration_ms: int = 50
    sample_rate: int = 48000

    def validate(self) -> None:
        if self.f0_hz <= 0 or self.f1_hz <= self.f0_hz:
            raise ValueError("need 0 < f0_hz < f1_hz")
        if self.duration_ms <= 0:
            raise ValueError("duration_ms must be > 0")
        if self.sample_rate <= 0:
            raise ValueError("sample_rate must be > 0")

    @property
    def n_samples(self) -> int:
        return int(self.sample_rate * self.duration_ms / 1000.0)


def generate_chirp(cfg: ChirpConfig | None = None, **kw: Any) -> np.ndarray:
    """Reference chirp waveform (unit amplitude), identical to the device's playback."""
    cfg = cfg or ChirpConfig(**kw)
    cfg.validate()
    n = cfg.n_samples
    i = np.arange(n, dtype=np.float64)
    inst_f = cfg.f0_hz + (cfg.f1_hz - cfg.f0_hz) * i / float(n)
    phase = 2.0 * math.pi * np.cumsum(inst_f) / float(cfg.sample_rate)
    return np.sin(phase).astype(np.float32)


def cross_correlate(reference: np.ndarray, recording: np.ndarray) -> np.ndarray:
    """Full linear cross-correlation (FFT-based): out[k] = sum_i rec[i+k] * ref[i].

    ``out`` has length len(recording); index k is the lag at which the reference
    starts inside the recording.
    """
    ref = np.asarray(reference, dtype=np.float64)
    rec = np.asarray(recording, dtype=np.float64)
    if ref.size == 0 or rec.size == 0:
        raise ValueError("reference and recording must be non-empty")
    n = ref.size + rec.size - 1
    N = 1 << int(math.ceil(math.log2(n)))
    F_ref = np.fft.fft(ref, N)
    F_rec = np.fft.fft(rec, N)
    xcorr = np.fft.ifft(np.conj(F_ref) * F_rec).real
    # p[k] = sum_i ref[i] * rec[i+k]; valid lags 0 .. len(rec)-len(ref)
    return xcorr[: rec.size - ref.size + 1]


def read_wav_pcm(path: str) -> tuple[np.ndarray, int]:
    """Read a 16-bit mono WAV (as written by the device) -> (float32 samples, sample_rate)."""
    with open(path, "rb") as fh:
        head = fh.read(44)
        if len(head) < 44 or head[0:4] != b"RIFF" or head[8:12] != b"WAVE":
            raise ValueError(f"{path} is not a RIFF/WAVE file")
        # locate the data chunk (robust to extra chunks)
        pos = 12
        sample_rate = None
        data_off = None
        while pos + 8 <= len(head):
            cid = head[pos:pos + 4]
            csize = int.from_bytes(head[pos + 4:pos + 8], "little")
            if cid == b"fmt ":
                sample_rate = int.from_bytes(head[pos + 12:pos + 16], "little")
            elif cid == b"data":
                data_off = pos + 8
            pos += 8 + csize + (csize & 1)
        if sample_rate is None or data_off is None:
            raise ValueError(f"{path} missing fmt/data chunks")
        fh.seek(data_off)
        raw = fh.read()
    pcm = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
    return pcm, int(sample_rate)



class SonarError(RuntimeError):
    """Sonar ping failed (no ack, bad WAV, no detectable peaks)."""


def pick_peaks(
    profile: np.ndarray,
    sample_rate: int,
    threshold_db: float = 30.0,
    min_sep_s: float = 0.001,
    top_n: int = 8,
) -> list[dict[str, Any]]:
    """Local maxima of |profile| above ``threshold_db`` below the strongest peak."""
    env = np.abs(np.asarray(profile, dtype=np.float64))
    if env.size < 3 or float(env.max()) <= 0.0:
        return []
    thr = float(env.max()) * (10.0 ** (-float(threshold_db) / 20.0))
    min_sep = max(1, int(min_sep_s * sample_rate))

    cand: list[tuple[int, float]] = []
    for i in range(1, env.size - 1):
        if env[i] >= thr and env[i] >= env[i - 1] and env[i] > env[i + 1]:
            cand.append((i, float(env[i])))
    # greedy: strongest first, enforce minimum separation
    cand.sort(key=lambda t: -t[1])
    kept: list[tuple[int, float]] = []
    for idx, amp in cand:
        if all(abs(idx - k) >= min_sep for k, _ in kept):
            kept.append((idx, amp))
    kept.sort()
    return [
        {"lag_idx": int(i), "lag_s": i / float(sample_rate), "amp": a}
        for i, a in kept[:top_n]
    ]


@dataclass(frozen=True)
class SonarPingResult:
    """One sonar ping: delay profile + detected peaks with distances."""

    f0_hz: float
    f1_hz: float
    tx_ms: int
    sample_rate: int
    direct_lag_s: float | None      # speaker->mic path (calibration reference)
    peaks: list[dict[str, Any]]     # [{lag_s, distance_m, amp}] — first entry is the direct path
    profile: np.ndarray             # full cross-correlation envelope region
    recording_path: str


class PhoneSonar:
    """Speaker->mic sonar over a FastLink (device-timed ping + PC-side correlation)."""

    def __init__(self, link, sound_speed_m_s: float = SOUND_SPEED_M_S) -> None:
        self.link = link
        self.c = float(sound_speed_m_s)

    def ping(
        self,
        f0_hz: float = 2000.0,
        f1_hz: float = 8000.0,
        tx_ms: int = 50,
        rec_ms: int = 400,
        delay_ms: int = 80,
        threshold_db: float = 30.0,
        top_n: int = 8,
        local_wav: str | None = None,
    ) -> SonarPingResult:
        """Run one ping and return the peak/distance profile.

        ``local_wav`` lets tests (or offline analysis) skip the device entirely.
        """
        cfg = ChirpConfig(f0_hz=f0_hz, f1_hz=f1_hz, duration_ms=tx_ms)
        wav_path = local_wav
        if wav_path is None:
            ack = self.link._command(
                "sonar", f0=float(f0_hz), f1=float(f1_hz),
                tx_ms=int(tx_ms), rec_ms=int(rec_ms), delay_ms=int(delay_ms),
            )
            msg = str(ack.get("msg", ""))
            remote = msg.split()[-1] if msg else None
            if not ack.get("ok") or not remote:
                raise SonarError(f"sonar command failed on device: {ack}")
            import tempfile

            local = os.path.join(tempfile.gettempdir(), "pyontrust_sonar.wav")
            _adb_pull(self.link, remote, local)
            wav_path = local

        try:
            rec_pcm, sr = read_wav_pcm(wav_path)
        except ValueError as e:
            raise SonarError(f"cannot parse recording WAV: {e}") from e
        ref = generate_chirp(cfg)
        profile = cross_correlate(ref, rec_pcm)
        peaks = pick_peaks(profile, sample_rate=sr, threshold_db=threshold_db, top_n=top_n)
        if not peaks:
            raise SonarError("no detectable chirp in recording (too quiet? wrong band?)")

        peaks.sort(key=lambda p: p["lag_idx"])          # earliest arrival = direct path
        direct_lag_s = float(peaks[0]["lag_s"])
        out_peaks = []
        for pk in peaks:
            lag_s = float(pk["lag_s"])
            d = self.c * max(lag_s - direct_lag_s, 0.0) / 2.0
            out_peaks.append({**pk, "distance_m": round(d, 4)})

        return SonarPingResult(
            f0_hz=f0_hz, f1_hz=f1_hz, tx_ms=tx_ms, sample_rate=sr,
            direct_lag_s=direct_lag_s, peaks=out_peaks, profile=np.abs(profile),
            recording_path=str(wav_path),
        )


def _adb_pull(link, remote: str, local: str) -> None:
    """Pull the device WAV over adb (uses the link's serial/adb path)."""
    import subprocess

    adb = [link.adb_path] + (["-s", link.serial] if link.serial else [])
    r = subprocess.run(adb + ["pull", remote, local], capture_output=True, text=True, timeout=60)
    if r.returncode != 0:
        raise SonarError(f"adb pull failed: {r.stderr.strip()}")


__all__ = [
    "ChirpConfig",
    "SonarPingResult",
    "SonarError",
    "PhoneSonar",
    "generate_chirp",
    "cross_correlate",
    "pick_peaks",
    "read_wav_pcm",
    "SOUND_SPEED_M_S",
]

