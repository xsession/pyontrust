package com.pyontrust.thermal;

import java.util.ArrayList;
import java.util.List;
import java.util.Locale;

/**
 * pyontrust's thermal measurement modes, fed frame by frame from the live loop:
 *  - continuous: capture for a duration, statistics + limits
 *  - soak:       wait until the hottest reading is stable (window / threshold) or time out
 *  - delta:      baseline frames → pause (apply the stimulus) → stimulus frames → ΔT per zone
 *  - gradient:   one frame, max spatial gradient in °C/mm
 * Pass/fail: global max limit, per-zone max limits, optional gradient limit.
 */
final class Measurement {
    static final String[] MODES = {"continuous", "soak", "delta", "gradient"};

    final String mode, boardId;
    final float duration, interval, globalMax, maxGradient, pixelPitch, soakWindow, soakThreshold, soakTimeout, deltaPause;
    final int deltaBaseline, deltaStimulus;
    final List<Region> zones = new ArrayList<>();
    final long startedMs = System.currentTimeMillis();

    // results
    final List<float[]> series = new ArrayList<>();    // t, global min, mean, max, zone max…
    final List<String> failReasons = new ArrayList<>();
    float[] zoneMin, zoneMax, zoneMeanSum;
    int[] zoneN;
    float peak = -Float.MAX_VALUE, low = Float.MAX_VALUE;
    float[] grad;                                        // gradient mode result
    float[] baseline, stimulus;                          // delta mode: per-zone mean (+ global mean last)
    int baselineN, stimulusN;
    float settledAtS = -1;
    Frame lastFrame;
    String phase = "starting";
    boolean done, passed;

    private long lastSampleMs, pauseUntilMs;

    Measurement(Settings s, List<Region> regions) {
        mode = s.measMode;
        boardId = s.boardId;
        duration = s.measDuration;
        interval = Math.max(0.05f, s.measInterval);
        globalMax = s.measGlobalMax;
        maxGradient = s.measMaxGradient;
        pixelPitch = s.measPixelPitch;
        soakWindow = s.soakWindow;
        soakThreshold = s.soakThreshold;
        soakTimeout = s.soakTimeout;
        deltaPause = s.deltaPause;
        deltaBaseline = Math.max(1, s.deltaBaseline);
        deltaStimulus = Math.max(1, s.deltaStimulus);
        zones.addAll(regions);
        int n = zones.size();
        zoneMin = new float[n];
        zoneMax = new float[n];
        zoneMeanSum = new float[n];
        zoneN = new int[n];
        for (int i = 0; i < n; i++) { zoneMin[i] = Float.MAX_VALUE; zoneMax[i] = -Float.MAX_VALUE; }
        baseline = new float[n + 1];
        stimulus = new float[n + 1];
    }

    float elapsed() { return (System.currentTimeMillis() - startedMs) / 1000f; }

    /** 0..1 for the progress bar. */
    float progress() {
        switch (mode) {
            case "gradient": return done ? 1 : 0;
            case "delta": return Math.min(1f, (baselineN + stimulusN) / (float) (deltaBaseline + deltaStimulus));
            case "soak": return Math.min(1f, elapsed() / soakTimeout);
            default: return Math.min(1f, elapsed() / duration);
        }
    }

    /** Feed a processed frame; returns true when the measurement just finished. */
    boolean offer(Frame f) {
        if (done) return false;
        long now = System.currentTimeMillis();
        if (now < pauseUntilMs) {
            phase = String.format(Locale.US, "apply the stimulus — capturing in %.0f s", (pauseUntilMs - now) / 1000f);
            return false;
        }
        if (lastSampleMs != 0 && now - lastSampleMs < interval * 1000 - 20) return false;
        lastSampleMs = now;
        lastFrame = f;
        sample(f);
        switch (mode) {
            case "gradient":
                grad = Processor.gradient(f);
                phase = "gradient analysed";
                return finish();
            case "delta":
                float[] m = means(f);
                if (baselineN < deltaBaseline) {
                    add(baseline, m);
                    baselineN++;
                    phase = "baseline " + baselineN + "/" + deltaBaseline;
                    if (baselineN == deltaBaseline) pauseUntilMs = now + (long) (deltaPause * 1000);
                    return false;
                }
                add(stimulus, m);
                stimulusN++;
                phase = "stimulus " + stimulusN + "/" + deltaStimulus;
                return stimulusN >= deltaStimulus && finish();
            case "soak":
                phase = String.format(Locale.US, "soaking — max %.1f °C", f.max);
                float t = elapsed();
                if (t >= soakWindow) {
                    float lo = Float.MAX_VALUE, hi = -Float.MAX_VALUE;
                    for (float[] row : series) {
                        if (row[0] >= t - soakWindow) { lo = Math.min(lo, row[3]); hi = Math.max(hi, row[3]); }
                    }
                    if (hi - lo <= soakThreshold) { settledAtS = t; return finish(); }
                }
                if (t >= soakTimeout) { failReasons.add(String.format(Locale.US, "did not settle within %.0f s", soakTimeout)); return finish(); }
                return false;
            default:
                phase = String.format(Locale.US, "capturing %.0f / %.0f s", elapsed(), duration);
                return elapsed() >= duration && finish();
        }
    }

    private void sample(Frame f) {
        float[] row = new float[4 + zones.size()];
        row[0] = elapsed();
        row[1] = f.min;
        row[2] = f.mean;
        row[3] = f.max;
        peak = Math.max(peak, f.max);
        low = Math.min(low, f.min);
        for (int i = 0; i < zones.size(); i++) {
            Region z = zones.get(i);
            if (!z.measure(f)) { row[4 + i] = Float.NaN; continue; }
            row[4 + i] = z.rMax;
            zoneMin[i] = Math.min(zoneMin[i], z.rMin);
            zoneMax[i] = Math.max(zoneMax[i], z.rMax);
            zoneMeanSum[i] += z.rMean;
            zoneN[i]++;
        }
        series.add(row);
    }

    private float[] means(Frame f) {
        float[] m = new float[zones.size() + 1];
        for (int i = 0; i < zones.size(); i++) { zones.get(i).measure(f); m[i] = zones.get(i).rMean; }
        m[zones.size()] = f.mean;
        return m;
    }

    private static void add(float[] acc, float[] v) { for (int i = 0; i < acc.length; i++) acc[i] += v[i]; }

    private boolean finish() {
        done = true;
        if (peak > globalMax) failReasons.add(String.format(Locale.US, "global max %.1f °C > limit %.1f °C", peak, globalMax));
        for (int i = 0; i < zones.size(); i++) {
            Region z = zones.get(i);
            if (zoneN[i] > 0 && zoneMax[i] >= z.maxC) {
                failReasons.add(String.format(Locale.US, "%s max %.1f °C ≥ limit %.1f °C", z.name, zoneMax[i], z.maxC));
            }
        }
        if (grad == null && lastFrame != null) grad = Processor.gradient(lastFrame);
        if (maxGradient > 0 && grad != null && pixelPitch > 0 && grad[0] / pixelPitch > maxGradient) {
            failReasons.add(String.format(Locale.US, "gradient %.2f °C/mm > limit %.2f °C/mm", grad[0] / pixelPitch, maxGradient));
        }
        passed = failReasons.isEmpty();
        phase = passed ? "PASS" : "FAIL";
        return true;
    }

    void abort() {
        if (done) return;
        failReasons.add("stopped by the user");
        finish();
    }

    float deltaOf(int i) {
        if (baselineN == 0 || stimulusN == 0) return Float.NaN;
        return stimulus[i] / stimulusN - baseline[i] / baselineN;
    }

    String summary(Settings s) {
        StringBuilder sb = new StringBuilder();
        sb.append(passed ? "PASS" : "FAIL").append(" — ").append(mode).append(String.format(Locale.US, ", %.0f s, %d samples\n", elapsed(), series.size()));
        sb.append("frame min ").append(s.fmt(low)).append(", max ").append(s.fmt(peak)).append('\n');
        if (settledAtS >= 0) sb.append(String.format(Locale.US, "settled after %.0f s\n", settledAtS));
        if ("delta".equals(mode)) {
            for (int i = 0; i < zones.size(); i++) sb.append("Δ ").append(zones.get(i).name).append(' ').append(s.fmtDelta(deltaOf(i))).append('\n');
            sb.append("Δ frame mean ").append(s.fmtDelta(deltaOf(zones.size()))).append('\n');
        }
        if (grad != null && pixelPitch > 0) sb.append(String.format(Locale.US, "max gradient %.2f °C/mm at (%d, %d)\n", grad[0] / pixelPitch, (int) grad[1], (int) grad[2]));
        for (String r : failReasons) sb.append("✕ ").append(r).append('\n');
        return sb.toString().trim();
    }
}
