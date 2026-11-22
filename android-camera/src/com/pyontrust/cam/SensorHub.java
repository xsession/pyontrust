package com.pyontrust.cam;

import android.content.Context;
import android.hardware.Sensor;
import android.hardware.SensorEvent;
import android.hardware.SensorEventListener;
import android.hardware.SensorManager;
import android.os.Handler;
import android.os.HandlerThread;
import android.os.SystemClock;

import java.util.ArrayDeque;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;

/**
 * Phone sensors over the same HTTP link as the cameras (no Termux needed).
 *
 * <pre>
 * GET /sensors                       JSON list of the sensors this app can read
 * GET /sensor?type=accelerometer&ms=150
 *     → samples that arrived during the next {@code ms} milliseconds:
 *       {"ok":true,"type":..,"name":..,"samples":[[t_s, v0, v1, ..], ..] (t_s = seconds since app start),"stale":false}
 * </pre>
 *
 * A listener is registered on the first request for a sensor and released
 * after {@link #IDLE_MS} without requests, so nothing runs while nobody looks.
 * On-change sensors (light, proximity) only report when the value changes;
 * if nothing arrived in the window the last known sample is returned with
 * {@code "stale":true}.
 */
final class SensorHub {
    private static final long IDLE_MS = 15000;
    private static final int MAX_BUFFER = 2000;

    /** API name → Android sensor type. */
    static final Map<String, Integer> TYPES = new HashMap<>();
    static {
        TYPES.put("accelerometer", Sensor.TYPE_ACCELEROMETER);
        TYPES.put("gyroscope", Sensor.TYPE_GYROSCOPE);
        TYPES.put("magnetometer", Sensor.TYPE_MAGNETIC_FIELD);
        TYPES.put("light", Sensor.TYPE_LIGHT);
        TYPES.put("proximity", Sensor.TYPE_PROXIMITY);
        TYPES.put("barometer", Sensor.TYPE_PRESSURE);
        TYPES.put("gravity", Sensor.TYPE_GRAVITY);
        TYPES.put("rotation", Sensor.TYPE_ROTATION_VECTOR);
        TYPES.put("linear_acceleration", Sensor.TYPE_LINEAR_ACCELERATION);
        TYPES.put("temperature", Sensor.TYPE_AMBIENT_TEMPERATURE);
        TYPES.put("humidity", Sensor.TYPE_RELATIVE_HUMIDITY);
    }

    private final long t0 = SystemClock.elapsedRealtime();
    private final SensorManager sm;
    private final Handler handler;
    private final Map<String, Feed> feeds = new HashMap<>();

    SensorHub(Context ctx) {
        sm = (SensorManager) ctx.getSystemService(Context.SENSOR_SERVICE);
        HandlerThread t = new HandlerThread("sensors");
        t.start();
        handler = new Handler(t.getLooper());
    }

    /** One registered sensor with a ring buffer of samples. */
    private final class Feed implements SensorEventListener {
        final String type;
        final Sensor sensor;
        final ArrayDeque<float[]> buf = new ArrayDeque<>();   // [t_s, v0, v1, ...]
        float[] last;
        volatile long lastRequest = SystemClock.elapsedRealtime();

        Feed(String type, Sensor sensor) { this.type = type; this.sensor = sensor; }

        @Override
        public void onSensorChanged(SensorEvent e) {
            float[] s = new float[e.values.length + 1];
            s[0] = (SystemClock.elapsedRealtime() - t0) / 1000f;   // seconds since the app started
            System.arraycopy(e.values, 0, s, 1, e.values.length);
            synchronized (this) {
                buf.addLast(s);
                while (buf.size() > MAX_BUFFER) buf.removeFirst();
                last = s;
                notifyAll();
            }
        }

        @Override
        public void onAccuracyChanged(Sensor sensor, int accuracy) { }
    }

    private Sensor find(String type) {
        Integer t = TYPES.get(type);
        return (t == null || sm == null) ? null : sm.getDefaultSensor(t);
    }

    private synchronized Feed feed(String type) {
        Feed f = feeds.get(type);
        if (f != null) return f;
        Sensor s = find(type);
        if (s == null) return null;
        f = new Feed(type, s);
        sm.registerListener(f, s, SensorManager.SENSOR_DELAY_GAME, handler);
        feeds.put(type, f);
        scheduleIdleCheck();
        return f;
    }

    private void scheduleIdleCheck() {
        handler.postDelayed(() -> {
            boolean any;
            synchronized (SensorHub.this) {
                long now = SystemClock.elapsedRealtime();
                for (Feed f : new ArrayList<>(feeds.values())) {
                    if (now - f.lastRequest > IDLE_MS) {
                        sm.unregisterListener(f);
                        feeds.remove(f.type);
                    }
                }
                any = !feeds.isEmpty();
            }
            if (any) scheduleIdleCheck();
        }, IDLE_MS / 3);
    }

    String listJson() {
        StringBuilder sb = new StringBuilder("{\"ok\":true,\"sensors\":[");
        boolean first = true;
        for (Map.Entry<String, Integer> e : TYPES.entrySet()) {
            Sensor s = find(e.getKey());
            if (s == null) continue;
            if (!first) sb.append(',');
            first = false;
            sb.append("{\"type\":").append(Json.str(e.getKey()))
              .append(",\"name\":").append(Json.str(s.getName()))
              .append(",\"vendor\":").append(Json.str(s.getVendor()))
              .append(",\"max_range\":").append(num(s.getMaximumRange()))
              .append(",\"resolution\":").append(num(s.getResolution()))
              .append(",\"min_delay_us\":").append(s.getMinDelay()).append('}');
        }
        return sb.append("]}").toString();
    }

    String readJson(String type, long ms) throws InterruptedException {
        if (type == null || !TYPES.containsKey(type)) {
            return "{\"ok\":false,\"error\":" + Json.str("unknown sensor type: " + type) + "}";
        }
        Feed f = feed(type);
        if (f == null) {
            return "{\"ok\":false,\"error\":" + Json.str("this phone has no " + type + " sensor") + "}";
        }
        f.lastRequest = SystemClock.elapsedRealtime();
        ms = Math.max(20, Math.min(5000, ms));
        List<float[]> got = new ArrayList<>();
        boolean stale = false;
        synchronized (f) {
            f.buf.clear();
            long end = SystemClock.elapsedRealtime() + ms;
            long left;
            while ((left = end - SystemClock.elapsedRealtime()) > 0) f.wait(left);
            got.addAll(f.buf);
            f.buf.clear();
            if (got.isEmpty()) {
                // on-change sensor that did not change (or just registered): wait a little for a first value
                if (f.last == null) f.wait(500);
                if (f.last != null) { got.add(f.last); stale = true; }
            }
        }
        f.lastRequest = SystemClock.elapsedRealtime();
        StringBuilder sb = new StringBuilder("{\"ok\":true,\"type\":").append(Json.str(type))
                .append(",\"name\":").append(Json.str(f.sensor.getName()))
                .append(",\"window_ms\":").append(ms)
                .append(",\"stale\":").append(stale)
                .append(",\"samples\":[");
        for (int i = 0; i < got.size(); i++) {
            if (i > 0) sb.append(',');
            float[] s = got.get(i);
            sb.append('[');
            for (int j = 0; j < s.length; j++) {
                if (j > 0) sb.append(',');
                sb.append(num(s[j]));
            }
            sb.append(']');
        }
        return sb.append("]}").toString();
    }

    synchronized void close() {
        for (Feed f : feeds.values()) sm.unregisterListener(f);
        feeds.clear();
        handler.getLooper().quitSafely();
    }

    private static String num(float v) {
        if (Float.isNaN(v) || Float.isInfinite(v)) return "null";
        return String.format(Locale.US, "%.6g", v);
    }
}
