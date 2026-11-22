package com.pyontrust.cam;

import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.Service;
import android.content.Intent;
import android.content.pm.ServiceInfo;
import android.os.Build;
import android.os.IBinder;
import android.os.PowerManager;
import android.util.Log;

import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;
import java.net.InetAddress;
import java.net.ServerSocket;
import java.net.Socket;
import java.net.URLDecoder;
import java.nio.charset.StandardCharsets;
import java.util.HashMap;
import java.util.Map;

/**
 * Foreground service: HTTP server on 127.0.0.1:8090 (reached from the PC
 * through {@code adb forward tcp:N tcp:8090}).
 *
 * <pre>
 * GET /status                                  JSON state
 * GET /cameras                                 JSON list of cameras
 * GET /video?camera=0&w=1280&h=720&q=70        MJPEG stream (multipart/x-mixed-replace)
 * GET /frame?camera=0&w=1280&h=720             latest preview frame (JPEG)
 * GET /photo?camera=0                          full-resolution still (JPEG)
 * GET /focus?mode=auto|manual|continuous&d=4.5 focus control (d = diopters)
 * GET /sensors                                JSON list of phone sensors
 * GET /sensor?type=accelerometer&ms=150       samples from one sensor (see SensorHub)
 * </pre>
 */
public class StreamService extends Service {
    static final String TAG = "pyontrust-cam";
    static final int PORT = 8090;
    private static final String CHANNEL = "stream";

    private ServerSocket server;
    private CameraEngine engine;
    private SensorHub sensors;
    private PowerManager.WakeLock wake;
    private volatile boolean running;

    @Override
    public IBinder onBind(Intent intent) { return null; }

    @Override
    public void onCreate() {
        super.onCreate();
        startInForeground();
        engine = new CameraEngine(this);
        sensors = new SensorHub(this);
        PowerManager pm = (PowerManager) getSystemService(POWER_SERVICE);
        wake = pm.newWakeLock(PowerManager.PARTIAL_WAKE_LOCK, "pyontrust:stream");
        wake.acquire();
        running = true;
        new Thread(this::serve, "http-accept").start();
    }

    @Override
    public int onStartCommand(Intent intent, int flags, int startId) {
        return START_STICKY;
    }

    @Override
    public void onDestroy() {
        running = false;
        try { if (server != null) server.close(); } catch (IOException ignored) { }
        engine.close();
        sensors.close();
        if (wake != null && wake.isHeld()) wake.release();
        super.onDestroy();
    }

    private void startInForeground() {
        Notification.Builder b;
        if (Build.VERSION.SDK_INT >= 26) {
            NotificationManager nm = getSystemService(NotificationManager.class);
            nm.createNotificationChannel(new NotificationChannel(CHANNEL, "Camera stream",
                    NotificationManager.IMPORTANCE_LOW));
            b = new Notification.Builder(this, CHANNEL);
        } else {
            b = new Notification.Builder(this);
        }
        Notification n = b.setContentTitle("pyontrust camera")
                .setContentText("Streaming cameras to the lab PC (USB)")
                .setSmallIcon(android.R.drawable.ic_menu_camera)
                .setOngoing(true)
                .build();
        if (Build.VERSION.SDK_INT >= 29) {
            startForeground(1, n, ServiceInfo.FOREGROUND_SERVICE_TYPE_CAMERA);
        } else {
            startForeground(1, n);
        }
    }

    // ── HTTP ─────────────────────────────────────────────────────────────

    private void serve() {
        try {
            server = new ServerSocket(PORT, 16, InetAddress.getByName("127.0.0.1"));
            while (running) {
                Socket s = server.accept();
                new Thread(() -> handle(s), "http-conn").start();
            }
        } catch (IOException e) {
            if (running) Log.e(TAG, "server stopped", e);
        }
    }

    private void handle(Socket s) {
        try (Socket sock = s) {
            sock.setTcpNoDelay(true);
            InputStream in = sock.getInputStream();
            String requestLine = readLine(in);
            if (requestLine == null) return;
            //noinspection StatementWithEmptyBody
            while (readLine(in).length() > 0) { /* skip headers */ }
            String[] parts = requestLine.split(" ");
            if (parts.length < 2) return;
            String target = parts[1];
            String path = target.contains("?") ? target.substring(0, target.indexOf('?')) : target;
            Map<String, String> q = query(target);
            OutputStream out = sock.getOutputStream();
            switch (path) {
                case "/status": json(out, engine.statusJson()); break;
                case "/cameras": json(out, engine.camerasJson()); break;
                case "/video": stream(out, q); break;
                case "/frame": frame(out, q); break;
                case "/photo": photo(out, q); break;
                case "/focus": json(out, engine.focus(q.get("mode"), q.get("d"))); break;
                case "/sensors": json(out, sensors.listJson()); break;
                case "/sensor": json(out, sensors.readJson(q.get("type"), parseInt(q.get("ms"), 150))); break;
                default: send(out, "404 Not Found", "application/json",
                        "{\"ok\":false,\"error\":\"not found\"}".getBytes(StandardCharsets.UTF_8));
            }
        } catch (Exception e) {
            Log.w(TAG, "request failed: " + e);
        }
    }

    private void stream(OutputStream out, Map<String, String> q) throws Exception {
        CameraEngine.Config cfg = config(q);
        engine.ensure(cfg);
        out.write(("HTTP/1.1 200 OK\r\nContent-Type: multipart/x-mixed-replace; boundary=frame\r\n"
                + "Cache-Control: no-store\r\nConnection: close\r\n\r\n").getBytes(StandardCharsets.US_ASCII));
        long last = -1;
        engine.addViewer();
        try {
            while (running) {
                CameraEngine.Frame f = engine.awaitFrame(last, 3000);
                if (f == null) { engine.ensure(cfg); continue; }   // stalled -> reopen
                last = f.seq;
                out.write(("--frame\r\nContent-Type: image/jpeg\r\nContent-Length: " + f.jpeg.length
                        + "\r\nX-Frame-Seq: " + f.seq + "\r\nX-Timestamp-Ns: " + f.timestampNs
                        + "\r\n\r\n").getBytes(StandardCharsets.US_ASCII));
                out.write(f.jpeg);
                out.write("\r\n".getBytes(StandardCharsets.US_ASCII));
                out.flush();
            }
        } finally {
            engine.removeViewer();
        }
    }

    private void frame(OutputStream out, Map<String, String> q) throws Exception {
        engine.ensure(config(q));
        CameraEngine.Frame f = engine.awaitFrame(-1, 5000);
        if (f == null) { send(out, "503 Service Unavailable", "application/json",
                "{\"ok\":false,\"error\":\"no frame\"}".getBytes(StandardCharsets.UTF_8)); return; }
        send(out, "200 OK", "image/jpeg", f.jpeg);
    }

    private void photo(OutputStream out, Map<String, String> q) throws Exception {
        byte[] jpeg = engine.takePhoto(config(q), 10000);
        send(out, "200 OK", "image/jpeg", jpeg);
    }

    private static CameraEngine.Config config(Map<String, String> q) {
        CameraEngine.Config c = new CameraEngine.Config();
        c.cameraId = q.containsKey("camera") ? q.get("camera") : "0";
        c.width = parseInt(q.get("w"), 1280);
        c.height = parseInt(q.get("h"), 720);
        c.quality = Math.max(30, Math.min(95, parseInt(q.get("q"), 70)));
        return c;
    }

    // ── tiny HTTP helpers ────────────────────────────────────────────────

    private static void json(OutputStream out, String body) throws IOException {
        send(out, "200 OK", "application/json", body.getBytes(StandardCharsets.UTF_8));
    }

    private static void send(OutputStream out, String status, String type, byte[] body) throws IOException {
        out.write(("HTTP/1.1 " + status + "\r\nContent-Type: " + type + "\r\nContent-Length: " + body.length
                + "\r\nCache-Control: no-store\r\nConnection: close\r\n\r\n").getBytes(StandardCharsets.US_ASCII));
        out.write(body);
        out.flush();
    }

    private static String readLine(InputStream in) throws IOException {
        StringBuilder sb = new StringBuilder();
        int c;
        while ((c = in.read()) != -1) {
            if (c == '\n') break;
            if (c != '\r') sb.append((char) c);
            if (sb.length() > 8192) break;
        }
        return (c == -1 && sb.length() == 0) ? null : sb.toString();
    }

    private static Map<String, String> query(String target) {
        Map<String, String> m = new HashMap<>();
        int i = target.indexOf('?');
        if (i < 0) return m;
        for (String kv : target.substring(i + 1).split("&")) {
            int e = kv.indexOf('=');
            try {
                if (e > 0) m.put(URLDecoder.decode(kv.substring(0, e), "UTF-8"), URLDecoder.decode(kv.substring(e + 1), "UTF-8"));
            } catch (Exception ignored) { }
        }
        return m;
    }

    private static int parseInt(String s, int def) {
        try { return s == null ? def : Integer.parseInt(s); } catch (NumberFormatException e) { return def; }
    }
}
