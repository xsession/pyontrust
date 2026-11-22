package com.pyontrust.thermal;

import android.content.Context;
import android.graphics.Canvas;
import android.graphics.Color;
import android.graphics.Paint;
import android.graphics.Path;
import android.view.View;

import java.util.ArrayList;
import java.util.List;
import java.util.Locale;

/** Small line / bar chart: tracking trend, line profile, histogram. */
final class ChartView extends View {
    static final int[] COLORS = {0xfff38ba8, 0xff89b4fa, 0xffa6e3a1, 0xfff9e2af, 0xffcba6f7, 0xff94e2d5,
            0xfffab387, 0xffeba0ac, 0xff74c7ec, 0xffb4befe};

    private final Settings s;
    private String title = "";
    private List<String> names = new ArrayList<>();
    private List<float[]> series = new ArrayList<>();   // each: y values
    private float[] xs;                                 // shared x (null = index)
    private boolean bars;
    private String xUnit = "";
    private final Paint p = new Paint(Paint.ANTI_ALIAS_FLAG);
    private final Paint t = new Paint(Paint.ANTI_ALIAS_FLAG);

    ChartView(Context c, Settings s) {
        super(c);
        this.s = s;
        setBackgroundColor(0xff181825);
        t.setTextSize(11 * getResources().getDisplayMetrics().scaledDensity);
        t.setColor(0xffa6adc8);
    }

    /** Tracking rows: column 0 = t (s), the others = temperatures. */
    void showTrend(String title, List<String> cols, List<float[]> rows) {
        this.title = title;
        bars = false;
        xUnit = "s";
        names = new ArrayList<>();
        series = new ArrayList<>();
        int n;
        synchronized (rows) {
            n = rows.size();
            int step = Math.max(1, n / 600);           // downsample for drawing
            int m = (n + step - 1) / step;
            xs = new float[m];
            for (int c = 1; c < cols.size(); c++) {
                names.add(cols.get(c));
                series.add(new float[m]);
            }
            for (int i = 0, k = 0; i < n && k < m; i += step, k++) {
                float[] r = rows.get(i);
                xs[k] = r[0];
                for (int c = 1; c < cols.size(); c++) series.get(c - 1)[k] = r[c];
            }
        }
        invalidate();
    }

    void showProfile(String title, float[] profile) {
        this.title = title;
        bars = false;
        xUnit = "px";
        xs = null;
        names = new ArrayList<>();
        series = new ArrayList<>();
        if (profile != null) { names.add("°"); series.add(profile.clone()); }
        invalidate();
    }

    void showHistogram(Frame f) {
        title = "Histogram";
        bars = true;
        xUnit = "";
        names = new ArrayList<>();
        series = new ArrayList<>();
        if (f != null) {
            int[] h = Processor.histogram(f, 64);
            float[] v = new float[h.length];
            xs = new float[h.length];
            for (int i = 0; i < h.length; i++) { v[i] = h[i]; xs[i] = s.disp(f.min + (f.max - f.min) * i / 63f); }
            names.add("pixels");
            series.add(v);
        }
        invalidate();
    }

    @Override
    protected void onDraw(Canvas c) {
        float dp = getResources().getDisplayMetrics().density;
        float L = 42 * dp, R = 8 * dp, T = 18 * dp, B = 18 * dp;
        float W = getWidth() - L - R, H = getHeight() - T - B;
        t.setColor(Color.WHITE);
        c.drawText(title, L, 13 * dp, t);
        if (series.isEmpty() || series.get(0).length < 1 || W <= 0 || H <= 0) {
            t.setColor(0xffa6adc8);
            c.drawText("no data yet", L, T + H / 2, t);
            return;
        }
        float lo = Float.MAX_VALUE, hi = -Float.MAX_VALUE;
        for (float[] sr : series) for (float v : sr) if (!Float.isNaN(v)) { float d = bars ? v : s.disp(v); lo = Math.min(lo, d); hi = Math.max(hi, d); }
        if (bars) lo = 0;
        if (hi - lo < 0.5f) { hi += 0.25f; lo -= 0.25f; }
        int len = series.get(0).length;
        float x0 = xs != null ? xs[0] : 0, x1 = xs != null ? xs[len - 1] : len - 1;
        if (x1 <= x0) x1 = x0 + 1;
        p.setStrokeWidth(1);
        p.setStyle(Paint.Style.STROKE);
        t.setColor(0xffa6adc8);
        for (int g = 0; g <= 3; g++) {
            float y = T + H - H * g / 3f;
            p.setColor(0xff313244);
            c.drawLine(L, y, L + W, y, p);
            float v = lo + (hi - lo) * g / 3f;
            c.drawText(bars ? String.valueOf((int) v) : String.format(Locale.US, "%.1f", v), 2 * dp, y + 4 * dp, t);
        }
        c.drawText(String.format(Locale.US, "%.1f", x0), L, getHeight() - 4 * dp, t);
        String xe = String.format(Locale.US, "%.1f %s", x1, bars ? s.unit() : xUnit);
        c.drawText(xe, L + W - t.measureText(xe), getHeight() - 4 * dp, t);
        float legendX = L + 8 * dp;
        for (int si = 0; si < series.size(); si++) {
            float[] sr = series.get(si);
            int col = COLORS[si % COLORS.length];
            p.setColor(col);
            if (bars) {
                p.setStyle(Paint.Style.FILL);
                float bw = W / sr.length;
                for (int i = 0; i < sr.length; i++) {
                    float y = T + H - H * (sr[i] - lo) / (hi - lo);
                    c.drawRect(L + i * bw, y, L + (i + 1) * bw - 1, T + H, p);
                }
                p.setStyle(Paint.Style.STROKE);
                continue;
            }
            p.setStrokeWidth(1.6f * dp);
            Path path = new Path();
            boolean started = false;
            for (int i = 0; i < sr.length; i++) {
                if (Float.isNaN(sr[i])) { started = false; continue; }
                float xv = xs != null ? xs[i] : i;
                float x = L + W * (xv - x0) / (x1 - x0), y = T + H - H * (s.disp(sr[i]) - lo) / (hi - lo);
                if (!started) { path.moveTo(x, y); started = true; } else path.lineTo(x, y);
            }
            c.drawPath(path, p);
            if (series.size() > 1 && legendX < L + W - 30 * dp) {
                t.setColor(col);
                String nm = names.get(si);
                c.drawText(nm, legendX, T + 10 * dp, t);
                legendX += t.measureText(nm) + 10 * dp;
            }
        }
    }
}
