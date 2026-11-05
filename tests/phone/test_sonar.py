"""Tests for pyontrust.phone.sonar (speaker->mic acoustic sonar)."""
from __future__ import annotations

import struct

import numpy as np
import pytest

from pyontrust.phone.sonar import (
    ChirpConfig,
    PhoneSonar,
    SonarError,
    cross_correlate,
    generate_chirp,
    pick_peaks,
    read_wav_pcm,
)


def _write_wav(path: str, pcm_f32: np.ndarray, sample_rate: int = 48000) -> None:
    """16-bit mono WAV in the same layout the device writes."""
    pcm = (np.clip(pcm_f32, -1.0, 1.0) * 32767).astype(np.int16)
    data = pcm.tobytes()
    header = bytearray(44)
    def put_str(off, s): header[off:off+len(s)] = s.encode()
    def put_int(off, v): header[off:off+4] = struct.pack("<I", int(v))
    def put_short(off, v): header[off:off+2] = struct.pack("<H", int(v))
    put_str(0, "RIFF"); put_int(4, 36 + len(data)); put_str(8, "WAVE")
    put_str(12, "fmt "); put_int(16, 16); put_short(20, 1); put_short(22, 1)
    put_int(24, sample_rate); put_int(28, sample_rate * 2); put_short(32, 2); put_short(34, 16)
    put_str(36, "data"); put_int(40, len(data))
    with open(path, "wb") as fh:
        fh.write(bytes(header)); fh.write(data)


class TestChirp:
    def test_length(self):
        ref = generate_chirp(ChirpConfig(duration_ms=50, sample_rate=48000))
        assert len(ref) == 2400

    def test_endpoint_frequencies(self):
        cfg = ChirpConfig(f0_hz=2000.0, f1_hz=8000.0, duration_ms=50, sample_rate=48000)
        ref = generate_chirp(cfg)
        win = 96          # short window so the sweep barely moves inside it

        def zc_freq(x):
            sgn = np.sign(x[1:]) * np.sign(x[:-1])
            crossings = int((sgn < 0).sum())
            return crossings / (len(x) - 1) * cfg.sample_rate / 2.0

        # average instantaneous frequency over the first/last window
        t_win = win / cfg.sample_rate
        f_avg_first = cfg.f0_hz + (cfg.f1_hz - cfg.f0_hz) * t_win / 2 / (cfg.duration_ms / 1000)
        f_avg_last = cfg.f1_hz - (cfg.f1_hz - cfg.f0_hz) * t_win / 2 / (cfg.duration_ms / 1000)
        assert zc_freq(ref[:win]) == pytest.approx(f_avg_first, rel=0.05)
        assert zc_freq(ref[-win:]) == pytest.approx(f_avg_last, rel=0.05)

    def test_bad_config_rejected(self):
        with pytest.raises(ValueError, match="f0"):
            ChirpConfig(f0_hz=9000, f1_hz=2000).validate()


class TestCorrelation:
    def test_matches_direct_correlate(self):
        rng = np.random.default_rng(3)
        ref = rng.standard_normal(512).astype(np.float64)
        rec = rng.standard_normal(2048).astype(np.float64)
        got = cross_correlate(ref, rec)
        m = ref.size
        want = np.correlate(rec, ref, mode="full")[m - 1 : len(rec)]
        assert got.shape == want.shape
        scale = max(float(np.abs(want).max()), 1e-9)
        assert float(np.max(np.abs(got - want)) / scale) < 1e-6

    def test_delay_recovery(self):
        cfg = ChirpConfig(duration_ms=20, sample_rate=48000)
        ref = generate_chirp(cfg)
        delay = 733
        rec = np.zeros(4096); rec[delay:delay + len(ref)] = ref
        prof = cross_correlate(ref, rec)
        assert int(np.argmax(prof)) == delay


class TestPeaksAndWav:
    def test_pick_peaks_finds_known_delays(self):
        sr = 48000
        env = np.zeros(10000)
        for lag, amp in ((1000, 1.0), (2500, 0.4), (6000, 0.2)):
            env[lag - 3:lag + 4] += amp * np.exp(-((np.arange(7) - 3) ** 2))
        peaks = pick_peaks(env, sample_rate=sr, threshold_db=15.0)
        lags = [p["lag_idx"] for p in peaks]
        assert 1000 in lags and 2500 in lags

    def test_wav_roundtrip(self, tmp_path):
        rng = np.random.default_rng(9)
        pcm = (rng.standard_normal(1000).astype(np.float32) * 0.2)
        path = str(tmp_path / "t.wav")
        _write_wav(path, pcm, sample_rate=48000)
        out, sr = read_wav_pcm(path)
        assert sr == 48000 and len(out) == 1000
        assert np.allclose(out, (pcm * 32767).astype(np.int16).astype(np.float32) / 32768.0, atol=1e-6)



class TestPhoneSonar:
    def _fake_link(self, wav_path: str | None = None):
        class FakeLink:
            serial = "FAKE123"
            adb_path = "/usr/bin/adb"

            def _command(self, cmd, **kw):
                assert cmd == "sonar"
                return {"ok": True, "msg": f"saved {wav_path}"}
        return FakeLink()

    def test_ping_recovers_reflection_distance(self, tmp_path):
        cfg = ChirpConfig(duration_ms=50, sample_rate=48000)
        ref = generate_chirp(cfg)
        c, d_true, sr = 343.0, 1.7, 48000
        dt_samples = int(round(2 * d_true / c * sr))          # reflection extra delay
        rec = np.zeros(1200 + len(ref) + dt_samples + len(ref) + 500, dtype=np.float32)
        rec[1200:1200 + len(ref)] += ref * 0.9                # direct speaker->mic path
        lag2 = 1200 + dt_samples
        rec[lag2:lag2 + len(ref)] += ref * 0.35               # reflection off a wall

        wav_local = str(tmp_path / "sonar.wav")
        _write_wav(wav_local, rec)

        res = PhoneSonar(self._fake_link()).ping(local_wav=wav_local, threshold_db=12.0)
        assert len(res.peaks) >= 2
        assert res.sample_rate == 48000
        # first peak is the direct path (distance ~0), second is the reflection
        assert res.peaks[0]["distance_m"] < 0.05
        assert res.peaks[1]["distance_m"] == pytest.approx(d_true, abs=0.05)

    def test_ping_threshold_limits_peaks(self, tmp_path):
        rng = np.random.default_rng(7)
        rec = (rng.standard_normal(4800).astype(np.float32)) * 0.01   # noise only
        wav_local = str(tmp_path / "noise.wav")
        _write_wav(wav_local, rec)

        th_db = 40.0
        res = PhoneSonar(self._fake_link()).ping(local_wav=wav_local, threshold_db=th_db)
        assert len(res.peaks) <= 8          # top_n cap
        prof_max = float(np.max(res.profile))
        for pk in res.peaks:                # contract: within threshold of the max
            assert 20.0 * np.log10(pk["amp"] / prof_max) >= -th_db - 1e-6

    def test_ping_bad_wav_raises(self, tmp_path):
        bad = str(tmp_path / "bad.wav")
        with open(bad, "wb") as f:
            f.write(b"NOTAWAVEFILE")

        with pytest.raises(SonarError):
            PhoneSonar(self._fake_link()).ping(local_wav=bad)

