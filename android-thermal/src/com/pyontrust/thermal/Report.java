package com.pyontrust.thermal;

import android.graphics.Bitmap;
import android.util.Base64;

import java.io.ByteArrayOutputStream;
import java.io.File;
import java.io.FileWriter;
import java.io.IOException;
import java.text.SimpleDateFormat;
import java.util.Date;
import java.util.List;
import java.util.Locale;

/** Self-contained HTML report of a measurement (same look as pyontrust's thermal report). */
final class Report {
    private static final String CSS = ":root{--bg:#1e1e2e;--bg2:#252538;--bg3:#2d2d44;--fg:#cdd6f4;--dim:#6c7086;"
            + "--accent:#89b4fa;--green:#a6e3a1;--red:#f38ba8;--yellow:#f9e2af;--mauve:#cba6f7;--border:#45475a}"
            + "body{font-family:system-ui,sans-serif;background:var(--bg);color:var(--fg);margin:0;line-height:1.5}"
            + ".r{max-width:1000px;margin:0 auto;padding:24px 16px}h1{color:var(--accent);font-size:24px;margin:0}"
            + "h2{color:var(--mauve);font-size:17px;border-bottom:1px solid var(--border);padding-bottom:4px}"
            + ".sub{color:var(--dim);font-size:13px}.v{padding:14px 20px;border-radius:6px;font-weight:700;margin:20px 0}"
            + ".pass{background:rgba(166,227,161,.12);color:var(--green);border:1px solid var(--green)}"
            + ".fail{background:rgba(243,139,168,.12);color:var(--red);border:1px solid var(--red)}"
            + ".cards{display:grid;grid-template-columns:repeat(auto-fill,minmax(150px,1fr));gap:10px}"
            + ".c{background:var(--bg2);border:1px solid var(--border);border-radius:6px;padding:10px;text-align:center}"
            + ".c b{display:block;font-size:20px;color:var(--accent);font-family:monospace}.c span{font-size:11px;color:var(--dim)}"
            + "table{width:100%;border-collapse:collapse;font-size:13px}th{background:var(--bg3);color:var(--accent);text-align:left;padding:6px 10px}"
            + "td{padding:5px 10px;border-bottom:1px solid var(--border)}img{max-width:100%;border-radius:6px;image-rendering:pixelated}"
            + ".bad{color:var(--red)}.warn{color:var(--yellow)}.ok{color:var(--green)}li{color:var(--red)}";

    static File write(File dir, Measurement m, Settings s, Bitmap snapshot, String source) throws IOException {
        dir.mkdirs();
        String stamp = new SimpleDateFormat("yyyyMMdd_HHmmss", Locale.US).format(new Date(m.startedMs));
        File f = new File(dir, "thermal_" + m.mode + "_" + stamp + ".html");
        StringBuilder h = new StringBuilder("<!DOCTYPE html><html><head><meta charset='utf-8'>"
                + "<meta name='viewport' content='width=device-width,initial-scale=1'><title>Thermal report</title><style>")
                .append(CSS).append("</style></head><body><div class='r'>");
        h.append("<h1>Thermal measurement — ").append(esc(m.mode)).append("</h1><div class='sub'>")
                .append(new SimpleDateFormat("yyyy-MM-dd HH:mm:ss", Locale.US).format(new Date(m.startedMs)))
                .append(" · ").append(esc(source)).append(m.boardId.isEmpty() ? "" : " · board " + esc(m.boardId))
                .append(" · pyontrust Thermal (Android)</div>");
        h.append("<div class='v ").append(m.passed ? "pass'>✔ PASS" : "fail'>✕ FAIL").append("</div>");
        if (!m.failReasons.isEmpty()) {
            h.append("<ul>");
            for (String r : m.failReasons) h.append("<li>").append(esc(r)).append("</li>");
            h.append("</ul>");
        }
        h.append("<h2>Summary</h2><div class='cards'>");
        card(h, s.fmt(m.peak), "frame max");
        card(h, s.fmt(m.low), "frame min");
        card(h, String.format(Locale.US, "%.0f s", m.elapsed()), "duration");
        card(h, String.valueOf(m.series.size()), "samples");
        if (m.grad != null && m.pixelPitch > 0) card(h, String.format(Locale.US, "%.2f °C/mm", m.grad[0] / m.pixelPitch), "max gradient");
        if (m.settledAtS >= 0) card(h, String.format(Locale.US, "%.0f s", m.settledAtS), "settled after");
        h.append("</div>");

        h.append("<h2>Settings</h2><table>");
        row(h, "Mode", m.mode);
        row(h, "Interval", m.interval + " s");
        row(h, "Global max limit", s.fmt(m.globalMax));
        if ("continuous".equals(m.mode)) row(h, "Duration", m.duration + " s");
        if ("soak".equals(m.mode)) row(h, "Stable window / threshold / timeout", m.soakWindow + " s / " + m.soakThreshold + " °C / " + m.soakTimeout + " s");
        if ("delta".equals(m.mode)) row(h, "Baseline / pause / stimulus", m.deltaBaseline + " frames / " + m.deltaPause + " s / " + m.deltaStimulus + " frames");
        if (m.maxGradient > 0) row(h, "Gradient limit", m.maxGradient + " °C/mm (pixel pitch " + m.pixelPitch + " mm)");
        row(h, "Emissivity / reflected", String.format(Locale.US, "%.2f / %s", s.emissivity, s.fmt(s.reflectedC)));
        h.append("</table>");

        if (!m.zones.isEmpty()) {
            h.append("<h2>Zones</h2><table><tr><th>Zone</th><th>Kind</th><th>Min</th><th>Mean</th><th>Max</th><th>Limit</th>");
            if ("delta".equals(m.mode)) h.append("<th>ΔT</th>");
            h.append("</tr>");
            for (int i = 0; i < m.zones.size(); i++) {
                Region z = m.zones.get(i);
                boolean has = m.zoneN[i] > 0;
                float mx = has ? m.zoneMax[i] : Float.NaN;
                String cls = !has ? "" : mx >= z.maxC ? "bad" : mx >= z.warnC ? "warn" : "ok";
                h.append("<tr><td>").append(esc(z.name)).append("</td><td>").append(z.kind).append("</td><td>")
                        .append(has ? s.fmt(m.zoneMin[i]) : "—").append("</td><td>")
                        .append(has ? s.fmt(m.zoneMeanSum[i] / m.zoneN[i]) : "—").append("</td><td class='").append(cls).append("'>")
                        .append(has ? s.fmt(mx) : "—").append("</td><td>").append(s.fmt(z.warnC)).append(" / ").append(s.fmt(z.maxC)).append("</td>");
                if ("delta".equals(m.mode)) h.append("<td>").append(s.fmtDelta(m.deltaOf(i))).append("</td>");
                h.append("</tr>");
            }
            h.append("</table>");
        }
        if (m.series.size() > 1) {
            h.append("<h2>Temperature over time</h2>").append(svg(m, s));
        }
        if (snapshot != null) {
            ByteArrayOutputStream bo = new ByteArrayOutputStream();
            snapshot.compress(Bitmap.CompressFormat.PNG, 100, bo);
            h.append("<h2>Last frame</h2><img src='data:image/png;base64,")
                    .append(Base64.encodeToString(bo.toByteArray(), Base64.NO_WRAP)).append("'>");
        }
        h.append("</div></body></html>");
        try (FileWriter w = new FileWriter(f)) { w.write(h.toString()); }
        return f;
    }

    private static final String[] COLORS = {"#f38ba8", "#89b4fa", "#a6e3a1", "#f9e2af", "#cba6f7", "#94e2d5", "#fab387"};

    private static String svg(Measurement m, Settings s) {
        int W = 900, H = 300, L = 50, B = 30;
        List<float[]> rows = m.series;
        float t1 = Math.max(1e-3f, rows.get(rows.size() - 1)[0]);
        float lo = Float.MAX_VALUE, hi = -Float.MAX_VALUE;
        for (float[] r : rows) for (int i = 1; i < r.length; i++) if (i != 2 && !Float.isNaN(r[i])) { lo = Math.min(lo, r[i]); hi = Math.max(hi, r[i]); }
        if (hi - lo < 1) { hi += 0.5f; lo -= 0.5f; }
        StringBuilder sb = new StringBuilder("<svg viewBox='0 0 " + W + " " + H + "' style='width:100%;background:#252538;border-radius:6px'>");
        for (int g = 0; g <= 4; g++) {
            float v = lo + (hi - lo) * g / 4;
            int y = (int) (H - B - (H - B - 10) * g / 4f);
            sb.append(String.format(Locale.US, "<line x1='%d' x2='%d' y1='%d' y2='%d' stroke='#45475a'/><text x='4' y='%d' fill='#6c7086' font-size='11'>%.1f</text>",
                    L, W - 10, y, y, y + 4, s.disp(v)));
        }
        sb.append(String.format(Locale.US, "<text x='%d' y='%d' fill='#6c7086' font-size='11'>%.0f s</text>", W - 50, H - 8, t1));
        String[] names = new String[rows.get(0).length];
        names[1] = "frame min";
        names[3] = "frame max";
        for (int i = 0; i < m.zones.size(); i++) names[4 + i] = m.zones.get(i).name + " max";
        int ci = 0, ly = 16;
        for (int c = 1; c < names.length; c++) {
            if (c == 2) continue;
            String col = COLORS[ci++ % COLORS.length];
            StringBuilder pts = new StringBuilder();
            for (float[] r : rows) {
                if (Float.isNaN(r[c])) continue;
                pts.append(String.format(Locale.US, "%.1f,%.1f ", L + (W - L - 10) * r[0] / t1, H - B - (H - B - 10) * (r[c] - lo) / (hi - lo)));
            }
            sb.append("<polyline fill='none' stroke-width='1.6' stroke='").append(col).append("' points='").append(pts).append("'/>");
            sb.append(String.format(Locale.US, "<text x='%d' y='%d' fill='%s' font-size='11'>%s</text>", W - 140, ly, col, esc(names[c])));
            ly += 14;
        }
        return sb.append("</svg>").toString();
    }

    private static void card(StringBuilder h, String v, String label) {
        h.append("<div class='c'><b>").append(esc(v)).append("</b><span>").append(esc(label)).append("</span></div>");
    }

    private static void row(StringBuilder h, String k, String v) {
        h.append("<tr><td>").append(esc(k)).append("</td><td>").append(esc(v)).append("</td></tr>");
    }

    static String esc(String s) {
        return String.valueOf(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace("'", "&#39;");
    }
}
