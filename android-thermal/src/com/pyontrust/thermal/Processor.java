package com.pyontrust.thermal;

import android.graphics.Bitmap;

import java.util.Arrays;

/**
 * Raw source frame → measured frame → colour image.
 *
 * Measuring chain: calibration offset → flip / rotation → temporal noise
 * reduction → (that is the "apparent" frame that gets recorded) → emissivity /
 * reflected-temperature correction → statistics.
 * Display chain (pyontrust render_frame): edge-preserving smoothing, robust
 * 1 … 99.7 % stretch with a minimum span, palette, isotherm.
 */
final class Processor {
    private final Settings s;
    private float[] avg;           // temporal average state
    private int avgW, avgH;

    Frame apparent;                // last frame before emissivity correction (what recordings store)
    float rangeLo, rangeHi;        // colour scale used for the last image

    Processor(Settings s) { this.s = s; }

    void reset() { avg = null; }

    Frame process(Frame raw, FrameSource src, float calOffset) {
        Frame f = raw;
        if (!src.isPlayback()) {
            if (calOffset != 0f) {
                float[] t = f.t;
                for (int i = 0; i < t.length; i++) t[i] += calOffset;
            }
            f = f.transformed(s.rotation, s.mirror, s.flipV);
        }
        // temporal noise reduction (exponential average; reset on size change)
        float alpha = s.noiseReduction == 2 ? 0.25f : s.noiseReduction == 1 ? 0.5f : 1f;
        if (alpha < 1f && avg != null && avgW == f.w && avgH == f.h) {
            float[] o = new float[f.t.length];
            for (int i = 0; i < o.length; i++) {
                float d = f.t[i] - avg[i];
                // big changes (> 2 °C) pass straight through: motion must not smear
                o[i] = Math.abs(d) > 2f ? f.t[i] : avg[i] + alpha * d;
            }
            avg = o;
            f = new Frame(f.w, f.h, o.clone(), f.timeMs, f.source);
        } else {
            avg = f.t.clone();
            avgW = f.w;
            avgH = f.h;
        }
        apparent = f;
        Frame out = emissivity(f, s.emissivity, s.reflectedC);
        return out.stats();
    }

    /** Stefan–Boltzmann grey-body correction: T_obj⁴ = (T_app⁴ − (1−ε)·T_refl⁴) / ε  (Kelvin). */
    static Frame emissivity(Frame f, float eps, float reflC) {
        if (eps >= 0.999f || eps <= 0.01f) return new Frame(f.w, f.h, f.t.clone(), f.timeMs, f.source);
        double tr4 = Math.pow(reflC + 273.15, 4) * (1 - eps);
        float[] o = new float[f.t.length];
        for (int i = 0; i < o.length; i++) {
            double ta = f.t[i] + 273.15;
            double v = (ta * ta * ta * ta - tr4) / eps;
            o[i] = v > 0 ? (float) (Math.sqrt(Math.sqrt(v)) - 273.15) : -273.15f;
        }
        return new Frame(f.w, f.h, o, f.timeMs, f.source);
    }

    // ── display ──────────────────────────────────────────────────────

    private static final float[] RANGE_W = new float[256];   // exp(-d²/2σ²), σ = 1 °C, d in 0.02 °C steps
    private static final float[] SPACE_W = new float[25];

    static {
        for (int i = 0; i < 256; i++) {
            float d = i * 0.02f;
            RANGE_W[i] = (float) Math.exp(-d * d / 2.0);
        }
        for (int dy = -2; dy <= 2; dy++)
            for (int dx = -2; dx <= 2; dx++)
                SPACE_W[(dy + 2) * 5 + dx + 2] = (float) Math.exp(-(dx * dx + dy * dy) / (2.0 * 2.0 * 2.0));
    }

    /** 5×5 bilateral filter: hides sub-degree speckle, keeps real edges. */
    static float[] bilateral(Frame f) {
        int w = f.w, h = f.h;
        float[] t = f.t, o = new float[t.length];
        for (int y = 0; y < h; y++) {
            for (int x = 0; x < w; x++) {
                float c = t[y * w + x], sum = 0, ws = 0;
                for (int dy = -2; dy <= 2; dy++) {
                    int yy = y + dy;
                    if (yy < 0 || yy >= h) continue;
                    for (int dx = -2; dx <= 2; dx++) {
                        int xx = x + dx;
                        if (xx < 0 || xx >= w) continue;
                        float v = t[yy * w + xx];
                        int k = (int) (Math.abs(v - c) * 50f);
                        if (k >= 256) continue;
                        float wt = SPACE_W[(dy + 2) * 5 + dx + 2] * RANGE_W[k];
                        sum += wt * v;
                        ws += wt;
                    }
                }
                o[y * w + x] = sum / ws;
            }
        }
        return o;
    }

    Bitmap render(Frame f) {
        float[] d = s.smoothing ? bilateral(f) : f.t;
        float lo, hi;
        if (s.autoRange) {
            float[] p = Frame.percentiles(d, 1f, 99.7f);
            lo = p[0];
            hi = p[1];
            if (hi - lo < s.minSpan) {
                float mid = (hi + lo) / 2;
                lo = mid - s.minSpan / 2;
                hi = mid + s.minSpan / 2;
            }
        } else {
            lo = Math.min(s.manualLo, s.manualHi - 0.1f);
            hi = Math.max(s.manualHi, lo + 0.1f);
        }
        rangeLo = lo;
        rangeHi = hi;
        int[] lut = Palette.lut(s.palette);
        int[] px = new int[d.length];
        float k = 255f / (hi - lo);
        boolean iso = s.isoMode != 0;
        for (int i = 0; i < d.length; i++) {
            int idx = (int) ((d[i] - lo) * k);
            idx = idx < 0 ? 0 : idx > 255 ? 255 : idx;
            int c = lut[idx];
            if (iso) {
                float v = f.t[i];
                boolean in = s.isoMode == 1 ? v >= s.isoLo : s.isoMode == 2 ? v <= s.isoLo
                        : v >= s.isoLo && v <= s.isoHi;
                if (!in) {   // outside the isotherm band: greyscale
                    int r = (c >> 16) & 255, g = (c >> 8) & 255, b = c & 255;
                    int yv = (r * 77 + g * 150 + b * 29) >> 8;
                    c = 0xff000000 | (yv << 16) | (yv << 8) | yv;
                } else if (s.isoMode != 3) {
                    c = s.isoMode == 1 ? 0xffff2a2a : 0xff2aa8ff;
                } else {
                    c = 0xff39ff14;
                }
            }
            px[i] = c;
        }
        return Bitmap.createBitmap(px, f.w, f.h, Bitmap.Config.ARGB_8888);
    }

    /** Histogram of the frame in n bins between its min and max. */
    static int[] histogram(Frame f, int n) {
        int[] hgm = new int[n];
        float span = Math.max(1e-3f, f.max - f.min);
        for (float v : f.t) {
            int b = (int) ((v - f.min) / span * (n - 1));
            hgm[Math.max(0, Math.min(n - 1, b))]++;
        }
        return hgm;
    }

    /** Max spatial gradient (°C/px) and where — numpy.gradient central differences. */
    static float[] gradient(Frame f) {
        int w = f.w, h = f.h;
        float best = 0;
        int bx = 0, by = 0;
        float bgx = 0, bgy = 0;
        for (int y = 0; y < h; y++) {
            for (int x = 0; x < w; x++) {
                float gx = x == 0 ? f.t[y * w + 1] - f.t[y * w] : x == w - 1 ? f.t[y * w + x] - f.t[y * w + x - 1]
                        : (f.t[y * w + x + 1] - f.t[y * w + x - 1]) / 2f;
                float gy = y == 0 ? f.t[w + x] - f.t[x] : y == h - 1 ? f.t[y * w + x] - f.t[(y - 1) * w + x]
                        : (f.t[(y + 1) * w + x] - f.t[(y - 1) * w + x]) / 2f;
                float m = (float) Math.sqrt(gx * gx + gy * gy);
                if (m > best) { best = m; bx = x; by = y; bgx = gx; bgy = gy; }
            }
        }
        return new float[]{best, bx, by, (float) Math.toDegrees(Math.atan2(bgy, bgx))};
    }

    static float median(float[] v) {
        float[] c = v.clone();
        Arrays.sort(c);
        return c[c.length / 2];
    }
}
