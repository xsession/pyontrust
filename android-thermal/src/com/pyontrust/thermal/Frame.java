package com.pyontrust.thermal;

import java.util.Arrays;

/** One radiometric frame: °C per pixel, row-major, plus where it came from. */
final class Frame {
    final int w, h;
    final float[] t;
    final long timeMs;
    final String source;

    // global statistics, filled by stats()
    float min, max, mean, center;
    int minX, minY, maxX, maxY;

    Frame(int w, int h, float[] t, long timeMs, String source) {
        this.w = w;
        this.h = h;
        this.t = t;
        this.timeMs = timeMs;
        this.source = source;
    }

    Frame copy() {
        Frame f = new Frame(w, h, t.clone(), timeMs, source);
        f.stats();
        return f;
    }

    float at(int x, int y) {
        x = Math.max(0, Math.min(w - 1, x));
        y = Math.max(0, Math.min(h - 1, y));
        return t[y * w + x];
    }

    Frame stats() {
        float lo = Float.MAX_VALUE, hi = -Float.MAX_VALUE;
        double sum = 0;
        int li = 0, hiI = 0;
        for (int i = 0; i < t.length; i++) {
            float v = t[i];
            sum += v;
            if (v < lo) { lo = v; li = i; }
            if (v > hi) { hi = v; hiI = i; }
        }
        min = lo; max = hi; mean = (float) (sum / Math.max(1, t.length));
        minX = li % w; minY = li / w; maxX = hiI % w; maxY = hiI / w;
        center = at(w / 2, h / 2);
        return this;
    }

    /** Median of all pixels (copy + sort; fine at Seek resolutions). */
    float median() {
        float[] c = t.clone();
        Arrays.sort(c);
        return c[c.length / 2];
    }

    /** Value at a percentile 0..100 (from a sorted copy). */
    static float[] percentiles(float[] data, float... p) {
        float[] c = data.clone();
        Arrays.sort(c);
        float[] out = new float[p.length];
        for (int i = 0; i < p.length; i++) {
            int k = Math.round(p[i] / 100f * (c.length - 1));
            out[i] = c[Math.max(0, Math.min(c.length - 1, k))];
        }
        return out;
    }

    /** Flip horizontally / vertically, then rotate (0/90/180/270 clockwise). */
    Frame transformed(int rotation, boolean mirror, boolean flipV) {
        if (rotation == 0 && !mirror && !flipV) return this;
        int nw = (rotation == 90 || rotation == 270) ? h : w;
        int nh = (rotation == 90 || rotation == 270) ? w : h;
        float[] o = new float[t.length];
        for (int y = 0; y < h; y++) {
            for (int x = 0; x < w; x++) {
                int sx = mirror ? w - 1 - x : x;
                int sy = flipV ? h - 1 - y : y;
                int nx, ny;
                switch (rotation) {
                    case 90: nx = h - 1 - sy; ny = sx; break;
                    case 180: nx = w - 1 - sx; ny = h - 1 - sy; break;
                    case 270: nx = sy; ny = w - 1 - sx; break;
                    default: nx = sx; ny = sy;
                }
                o[ny * nw + nx] = t[y * w + x];
            }
        }
        return new Frame(nw, nh, o, timeMs, source);
    }
}
