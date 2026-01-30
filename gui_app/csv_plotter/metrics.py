import pandas as pd


def compute_signal_metrics(x: pd.Series, y: pd.Series) -> tuple[str, str, str, str, str, str, str]:
    """Return (min, max, avg, med, p2p, freq, period) as strings for display.
    """
    ys = pd.to_numeric(y, errors="coerce").dropna()
    if len(ys) == 0:
        return ("n/a", "n/a", "n/a", "n/a", "n/a", "n/a", "n/a")

    try:
        mn = float(ys.min())
        mx = float(ys.max())
        avg = float(ys.mean())
        med = float(ys.median())
        p2p = float(ys.max() - ys.min())
    except Exception:
        return ("n/a", "n/a", "n/a", "n/a", "n/a", "n/a", "n/a")

    freq_s = "n/a"
    period_s = "n/a"

    # Frequency estimation: best-effort. Works best for roughly periodic signals.
    try:
        xs_raw = pd.to_numeric(x, errors="coerce")
        ys_raw = pd.to_numeric(y, errors="coerce")
        d = pd.DataFrame({"x": xs_raw, "y": ys_raw}).dropna()
        if len(d) >= 8:
            # Sort by time (some sources are not strictly ordered after masking)
            try:
                d = d.sort_values("x")
            except Exception:
                pass

            xs = d["x"].astype(float)
            ys2 = d["y"].astype(float)

            dx = xs.diff().dropna()
            try:
                dx = dx[dx > 0]
            except Exception:
                pass

            dt = float(dx.median()) if len(dx) else 0.0
            duration = float(xs.iloc[-1] - xs.iloc[0]) if len(xs) else 0.0

            if dt > 0 and duration > 0 and len(ys2) >= 8:
                try:
                    import numpy as np

                    x_np = xs.to_numpy(dtype=float)
                    y_np = ys2.to_numpy(dtype=float)

                    # Interpolate to a uniform grid for FFT.
                    t0 = float(x_np[0])
                    t1 = float(x_np[-1])
                    t_uniform = np.arange(t0, t1, dt, dtype=float)
                    if t_uniform.size >= 8:
                        y_uniform = np.interp(t_uniform, x_np, y_np)
                        y_uniform = y_uniform - float(np.nanmean(y_uniform))

                        # Keep FFT cost bounded for very long traces.
                        # Decimate to ~20k samples max; adjust effective dt accordingly.
                        try:
                            max_n = 20000
                            n_u = int(t_uniform.size)
                            if n_u > max_n:
                                step = int(np.ceil(n_u / max_n))
                                if step > 1:
                                    y_uniform = y_uniform[::step]
                                    dt = float(dt) * float(step)
                        except Exception:
                            pass

                        yf = np.fft.rfft(y_uniform)
                        freqs = np.fft.rfftfreq(len(y_uniform), d=dt)
                        if freqs.size > 1:
                            mag = np.abs(yf)
                            mag[0] = 0.0  # ignore DC
                            k = int(np.argmax(mag))
                            f = float(freqs[k])
                            if f > 0:
                                freq_s = f"{f:.3f}"
                                period_s = f"{(1.0 / f):.3f}"
                except Exception:
                    # Fallback: zero-crossing based estimate on raw samples
                    try:
                        yv = ys2.to_numpy(dtype=float)
                        if len(yv) >= 8 and duration > 0:
                            signs = (yv >= 0).astype(int)
                            crossings = int((signs[1:] != signs[:-1]).sum())
                            f = (crossings / 2.0) / duration
                            if f > 0:
                                freq_s = f"{f:.3f}"
                                period_s = f"{(1.0 / f):.3f}"
                    except Exception:
                        pass
    except Exception:
        pass

    return (
        f"{mn:.3f}",
        f"{mx:.3f}",
        f"{avg:.3f}",
        f"{med:.3f}",
        f"{p2p:.3f}",
        freq_s,
        period_s,
    )
