package com.pyontrust.thermal;

import org.json.JSONArray;
import org.json.JSONObject;

import java.util.ArrayList;
import java.util.List;

/**
 * A measurement region, the same model as pyontrust's Thermal workspace
 * (point = 3×3 neighbourhood, rect), plus lines with a temperature profile.
 * Coordinates are native sensor pixels of the displayed (rotated) frame.
 */
final class Region {
    static final int POINT_HALF = 1;
    static final String[] KINDS = {"point", "rect", "line"};

    String id, name, kind;
    int x, y, w = 1, h = 1;       // line: (x, y) → (x + w, y + h)
    float warnC = 60f, maxC = 85f;
    boolean alarm = true;

    // live reading
    float rMin = Float.NaN, rMean = Float.NaN, rMax = Float.NaN;
    int level;                    // 0 ok, 1 warn, 2 max
    float[] profile;              // lines only

    Region(String kind, int x, int y, int w, int h) {
        this.id = Long.toHexString(System.nanoTime());
        this.kind = kind;
        this.x = x;
        this.y = y;
        this.w = w;
        this.h = h;
    }

    boolean isPoint() { return "point".equals(kind); }
    boolean isLine() { return "line".equals(kind); }

    /** Measure this region in a frame; returns false when it lies outside. */
    boolean measure(Frame f) {
        float lo = Float.MAX_VALUE, hi = -Float.MAX_VALUE;
        double sum = 0;
        int n = 0;
        if (isLine()) {
            int steps = Math.max(Math.abs(w), Math.abs(h));
            float[] prof = new float[steps + 1];
            for (int i = 0; i <= steps; i++) {
                float tt = steps == 0 ? 0 : i / (float) steps;
                int px = Math.round(x + w * tt), py = Math.round(y + h * tt);
                float v = f.at(px, py);
                prof[i] = v;
                lo = Math.min(lo, v);
                hi = Math.max(hi, v);
                sum += v;
                n++;
            }
            profile = prof;
        } else {
            int x0 = isPoint() ? x - POINT_HALF : x, y0 = isPoint() ? y - POINT_HALF : y;
            int x1 = isPoint() ? x + POINT_HALF + 1 : x + w, y1 = isPoint() ? y + POINT_HALF + 1 : y + h;
            x0 = Math.max(0, x0); y0 = Math.max(0, y0);
            x1 = Math.min(f.w, x1); y1 = Math.min(f.h, y1);
            for (int yy = y0; yy < y1; yy++) {
                for (int xx = x0; xx < x1; xx++) {
                    float v = f.t[yy * f.w + xx];
                    lo = Math.min(lo, v);
                    hi = Math.max(hi, v);
                    sum += v;
                    n++;
                }
            }
        }
        if (n == 0) {
            rMin = rMean = rMax = Float.NaN;
            level = 0;
            return false;
        }
        rMin = lo;
        rMax = hi;
        rMean = (float) (sum / n);
        // limits judge the max (pyontrust region_readings); a point *reads* its 3×3 mean
        level = rMax >= maxC ? 2 : rMax >= warnC ? 1 : 0;
        return true;
    }

    /** The value a point reports / an area's headline value. */
    float value() { return isPoint() ? rMean : rMax; }

    JSONObject toJson() throws Exception {
        return new JSONObject().put("id", id).put("name", name).put("kind", kind).put("x", x).put("y", y)
                .put("w", w).put("h", h).put("warn_c", warnC).put("max_c", maxC).put("alarm", alarm);
    }

    static Region fromJson(JSONObject o) {
        Region r = new Region(o.optString("kind", "point"), o.optInt("x"), o.optInt("y"), o.optInt("w", 1), o.optInt("h", 1));
        r.id = o.optString("id", r.id);
        r.name = o.optString("name", "?");
        r.warnC = (float) o.optDouble("warn_c", 60);
        r.maxC = (float) o.optDouble("max_c", 85);
        r.alarm = o.optBoolean("alarm", true);
        return r;
    }

    static String toJson(List<Region> list) {
        JSONArray a = new JSONArray();
        try {
            for (Region r : list) a.put(r.toJson());
        } catch (Exception ignored) { }
        return a.toString();
    }

    static List<Region> listFromJson(String json) {
        List<Region> out = new ArrayList<>();
        try {
            JSONArray a = new JSONArray(json);
            for (int i = 0; i < a.length(); i++) out.add(fromJson(a.getJSONObject(i)));
        } catch (Exception ignored) { }
        return out;
    }

    static String nextName(List<Region> list, String kind) {
        String prefix = "point".equals(kind) ? "P" : "line".equals(kind) ? "L" : "R";
        for (int i = 1; ; i++) {
            boolean used = false;
            for (Region r : list) if ((prefix + i).equals(r.name)) used = true;
            if (!used) return prefix + i;
        }
    }
}
