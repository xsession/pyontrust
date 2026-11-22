package com.pyontrust.thermal;

import org.json.JSONArray;
import org.json.JSONObject;

import java.io.ByteArrayOutputStream;
import java.io.InputStream;
import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.nio.ByteBuffer;
import java.nio.ByteOrder;
import java.nio.charset.StandardCharsets;

/**
 * The Seek camera attached to the lab PC, read through the pyontrust gateway's
 * {@code /thermal/api/frame_raw} (float32 °C, the gateway's calibration applied).
 * Over USB: {@code adb reverse tcp:5210 tcp:5210}, then http://127.0.0.1:5210.
 */
final class GatewaySource implements FrameSource {
    private final String base;
    private long lastMs;

    GatewaySource(String baseUrl) {
        String b = baseUrl.trim();
        while (b.endsWith("/")) b = b.substring(0, b.length() - 1);
        if (!b.startsWith("http")) b = "http://" + b;
        this.base = b;
    }

    @Override public String name() { return "pyontrust gateway (" + base.replaceFirst("^https?://", "") + ")"; }
    @Override public String calibrationKey() { return "gateway"; }
    @Override public boolean isPlayback() { return false; }
    @Override public boolean supportsFlatField() { return true; }

    @Override
    public void open() throws Exception {
        grab();   // fail early with the gateway's own message
    }

    @Override
    public Frame grab() throws Exception {
        // the camera paces itself at ~9 Hz; don't hammer the gateway faster than that
        long wait = 100 - (System.currentTimeMillis() - lastMs);
        if (wait > 0) Thread.sleep(wait);
        lastMs = System.currentTimeMillis();
        HttpURLConnection c = (HttpURLConnection) new URL(base + "/thermal/api/frame_raw?mode=seek").openConnection();
        c.setConnectTimeout(3000);
        c.setReadTimeout(8000);
        try {
            int code;
            try {
                code = c.getResponseCode();
            } catch (java.io.IOException e) {
                throw new IllegalStateException("cannot reach the pyontrust gateway at " + base
                        + "\nIs it running? Over USB the PC needs: adb reverse tcp:5210 tcp:5210");
            }
            if (code != 200) throw new IllegalStateException(errorText(c, code));
            if ("1".equals(c.getHeaderField("X-Simulated"))) {
                throw new IllegalStateException("the gateway only has a simulated camera");
            }
            int w = Integer.parseInt(c.getHeaderField("X-Width"));
            int h = Integer.parseInt(c.getHeaderField("X-Height"));
            byte[] body = readAll(c.getInputStream());
            if (body.length != w * h * 4) throw new IllegalStateException("short frame from gateway");
            float[] t = new float[w * h];
            ByteBuffer.wrap(body).order(ByteOrder.LITTLE_ENDIAN).asFloatBuffer().get(t);
            return new Frame(w, h, t, System.currentTimeMillis(), name());
        } finally {
            c.disconnect();
        }
    }

    @Override public void close() { }

    @Override
    public String captureFlatField(int frames) throws Exception {
        JSONObject r = post("/thermal/api/flat_field", new JSONObject().put("frames", frames));
        return "gateway flat-field: residual " + r.optDouble("residual_std_counts") + " counts rms";
    }

    @Override
    public void clearFlatField() {
        try { post("/thermal/api/flat_field", new JSONObject().put("clear", true)); } catch (Exception ignored) { }
    }

    /** Regions defined in the pyontrust Thermal workspace. */
    JSONArray regions() throws Exception {
        return new JSONObject(request("GET", "/thermal/api/regions", null)).getJSONArray("regions");
    }

    JSONObject post(String path, JSONObject body) throws Exception {
        return new JSONObject(request("POST", path, body.toString()));
    }

    String request(String method, String path, String body) throws Exception {
        HttpURLConnection c = (HttpURLConnection) new URL(base + path).openConnection();
        c.setConnectTimeout(3000);
        c.setReadTimeout(60000);
        c.setRequestMethod(method);
        try {
            if (body != null) {
                c.setDoOutput(true);
                c.setRequestProperty("Content-Type", "application/json");
                try (OutputStream o = c.getOutputStream()) { o.write(body.getBytes(StandardCharsets.UTF_8)); }
            }
            int code = c.getResponseCode();
            if (code / 100 != 2) throw new IllegalStateException(errorText(c, code));
            return new String(readAll(c.getInputStream()), StandardCharsets.UTF_8);
        } finally {
            c.disconnect();
        }
    }

    private static String errorText(HttpURLConnection c, int code) {
        try {
            InputStream es = c.getErrorStream();
            String s = es == null ? "" : new String(readAll(es), StandardCharsets.UTF_8);
            String msg = new JSONObject(s).optString("error", s);
            return "gateway: " + (msg.isEmpty() ? "HTTP " + code : msg);
        } catch (Exception e) {
            return "gateway: HTTP " + code;
        }
    }

    static byte[] readAll(InputStream in) throws java.io.IOException {
        ByteArrayOutputStream bo = new ByteArrayOutputStream();
        byte[] b = new byte[16384];
        int n;
        while ((n = in.read(b)) > 0) bo.write(b, 0, n);
        in.close();
        return bo.toByteArray();
    }
}
