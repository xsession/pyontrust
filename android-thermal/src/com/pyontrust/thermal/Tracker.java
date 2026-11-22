package com.pyontrust.thermal;

import java.io.File;
import java.io.FileWriter;
import java.io.IOException;
import java.text.SimpleDateFormat;
import java.util.ArrayList;
import java.util.Date;
import java.util.List;
import java.util.Locale;

/**
 * Long-term tracking (pyontrust TrackingSession): every interval, each region's
 * reading plus the frame min / max goes to a CSV and the trend chart.
 * Columns match the PC: points → mean, rect / line → min, mean, max.
 */
final class Tracker {
    final List<String> columns = new ArrayList<>();
    final List<float[]> rows = new ArrayList<>();
    File csv;
    long startedMs;
    float intervalS;
    private long lastSampleMs;
    private List<Region> regions;
    private boolean running;

    boolean running() { return running; }

    void start(List<Region> regs, float intervalS, File dir) throws IOException {
        regions = new ArrayList<>(regs);
        this.intervalS = Math.max(0.1f, intervalS);
        columns.clear();
        rows.clear();
        columns.add("t_s");
        for (Region r : regions) {
            if (r.isPoint()) columns.add(r.name);
            else { columns.add(r.name + "_min"); columns.add(r.name + "_mean"); columns.add(r.name + "_max"); }
        }
        columns.add("frame_min");
        columns.add("frame_max");
        dir.mkdirs();
        csv = new File(dir, "thermal_tracking_" + new SimpleDateFormat("yyyyMMdd_HHmmss", Locale.US).format(new Date()) + ".csv");
        try (FileWriter fw = new FileWriter(csv)) {
            fw.write("timestamp," + join(columns) + "\n");
        }
        startedMs = System.currentTimeMillis();
        lastSampleMs = 0;
        running = true;
    }

    /** Called with every processed frame; samples when the interval has passed. */
    boolean offer(Frame f) {
        if (!running) return false;
        long now = System.currentTimeMillis();
        if (lastSampleMs != 0 && now - lastSampleMs < intervalS * 1000 - 20) return false;
        lastSampleMs = now;
        float[] row = new float[columns.size()];
        int k = 0;
        row[k++] = (now - startedMs) / 1000f;
        for (Region r : regions) {
            r.measure(f);
            if (r.isPoint()) row[k++] = r.rMean;
            else { row[k++] = r.rMin; row[k++] = r.rMean; row[k++] = r.rMax; }
        }
        row[k++] = f.min;
        row[k] = f.max;
        synchronized (rows) {
            rows.add(row);
            if (rows.size() > 50000) rows.subList(0, 25000).clear();
        }
        StringBuilder sb = new StringBuilder(new SimpleDateFormat("yyyy-MM-dd'T'HH:mm:ss.SSS", Locale.US).format(new Date(now)));
        for (float v : row) sb.append(',').append(Float.isNaN(v) ? "" : String.format(Locale.US, "%.2f", v));
        try (FileWriter fw = new FileWriter(csv, true)) {
            fw.write(sb.append('\n').toString());
        } catch (IOException ignored) { }
        return true;
    }

    void stop() { running = false; }

    int samples() { synchronized (rows) { return rows.size(); } }

    private static String join(List<String> l) {
        StringBuilder sb = new StringBuilder();
        for (String s : l) sb.append(sb.length() == 0 ? "" : ",").append(s);
        return sb.toString();
    }
}
