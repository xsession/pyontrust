package com.pyontrust.cam;

import android.content.Context;
import android.graphics.ImageFormat;
import android.graphics.Rect;
import android.graphics.YuvImage;
import android.hardware.camera2.CameraAccessException;
import android.hardware.camera2.CameraCaptureSession;
import android.hardware.camera2.CameraCharacteristics;
import android.hardware.camera2.CameraDevice;
import android.hardware.camera2.CameraManager;
import android.hardware.camera2.CaptureRequest;
import android.hardware.camera2.params.StreamConfigurationMap;
import android.media.Image;
import android.media.ImageReader;
import android.os.Handler;
import android.os.HandlerThread;
import android.util.Log;
import android.util.Size;
import android.view.Surface;

import java.io.ByteArrayOutputStream;
import java.nio.ByteBuffer;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.List;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicReference;

/**
 * One open camera at a time (phones generally can't run two of their own
 * cameras concurrently).  Session = YUV preview reader (→ JPEG frames for
 * the MJPEG stream) + full-size JPEG reader (stills on demand).
 */
final class CameraEngine {
    static final class Config {
        String cameraId = "0";
        int width = 1280, height = 720, quality = 70;

        boolean sameAs(Config o) {
            return o != null && cameraId.equals(o.cameraId) && width == o.width && height == o.height;
        }
    }

    static final class Frame {
        final byte[] jpeg; final long seq; final long timestampNs;
        Frame(byte[] j, long s, long t) { jpeg = j; seq = s; timestampNs = t; }
    }

    private static final String TAG = StreamService.TAG;

    private final CameraManager manager;
    private final HandlerThread thread = new HandlerThread("camera");
    private final Handler handler;
    private final Object lock = new Object();
    private final Object frameLock = new Object();

    private CameraDevice device;
    private CameraCaptureSession session;
    private ImageReader previewReader, stillReader;
    private CaptureRequest.Builder previewRequest;
    private Config active;
    private Size previewSize, stillSize;
    private volatile int quality = 70;
    private volatile Frame latest;
    private long seq;
    private int viewers;
    private String lastError = "";
    private long fpsWindowStart = System.nanoTime(); private int fpsCount; private volatile double fps;
    private final AtomicReference<CountDownLatch> stillLatch = new AtomicReference<>();
    private final AtomicReference<byte[]> stillResult = new AtomicReference<>();

    // focus state applied to every preview request
    private String focusMode = "continuous";
    private float focusDiopters = 0f;

    CameraEngine(Context ctx) {
        manager = (CameraManager) ctx.getSystemService(Context.CAMERA_SERVICE);
        thread.start();
        handler = new Handler(thread.getLooper());
    }

    // ── public API (called from HTTP threads) ────────────────────────────

    void ensure(Config cfg) throws Exception {
        synchronized (lock) {
            quality = cfg.quality;
            if (device != null && session != null && cfg.sameAs(active)) return;
            closeLocked();
            openLocked(cfg);
        }
    }

    Frame awaitFrame(long afterSeq, long timeoutMs) throws InterruptedException {
        long deadline = System.currentTimeMillis() + timeoutMs;
        synchronized (frameLock) {
            while (latest == null || latest.seq <= afterSeq) {
                long left = deadline - System.currentTimeMillis();
                if (left <= 0) return null;
                frameLock.wait(left);
            }
            return latest;
        }
    }

    void addViewer() { synchronized (lock) { viewers++; } }
    void removeViewer() { synchronized (lock) { viewers--; } }

    byte[] takePhoto(Config cfg, long timeoutMs) throws Exception {
        ensure(cfg);
        CountDownLatch latch = new CountDownLatch(1);
        synchronized (lock) {
            stillResult.set(null);
            stillLatch.set(latch);
            CaptureRequest.Builder b = device.createCaptureRequest(CameraDevice.TEMPLATE_STILL_CAPTURE);
            b.addTarget(stillReader.getSurface());
            b.addTarget(previewReader.getSurface());
            applyFocus(b);
            b.set(CaptureRequest.JPEG_QUALITY, (byte) 95);
            session.capture(b.build(), null, handler);
        }
        if (!latch.await(timeoutMs, TimeUnit.MILLISECONDS)) throw new IllegalStateException("photo timed out");
        return stillResult.get();
    }

    String focus(String mode, String diopters) {
        synchronized (lock) {
            if (mode != null) focusMode = mode;
            if (diopters != null) {
                try { focusDiopters = Float.parseFloat(diopters); focusMode = "manual"; } catch (NumberFormatException ignored) { }
            }
            try {
                if (session != null && previewRequest != null) {
                    applyFocus(previewRequest);
                    session.setRepeatingRequest(previewRequest.build(), null, handler);
                    if ("auto".equals(focusMode)) {               // one-shot AF trigger
                        previewRequest.set(CaptureRequest.CONTROL_AF_TRIGGER, CaptureRequest.CONTROL_AF_TRIGGER_START);
                        session.capture(previewRequest.build(), null, handler);
                        previewRequest.set(CaptureRequest.CONTROL_AF_TRIGGER, CaptureRequest.CONTROL_AF_TRIGGER_IDLE);
                    }
                }
            } catch (Exception e) {
                return "{\"ok\":false,\"error\":" + Json.str(e.toString()) + "}";
            }
            return "{\"ok\":true,\"mode\":" + Json.str(focusMode) + ",\"diopters\":" + focusDiopters + "}";
        }
    }

    String statusJson() {
        synchronized (lock) {
            return "{\"ok\":true,\"open\":" + (device != null) + ",\"camera\":" + Json.str(active == null ? "" : active.cameraId)
                    + ",\"preview\":" + Json.str(previewSize == null ? "" : previewSize.getWidth() + "x" + previewSize.getHeight())
                    + ",\"still\":" + Json.str(stillSize == null ? "" : stillSize.getWidth() + "x" + stillSize.getHeight())
                    + ",\"fps\":" + Math.round(fps * 10) / 10.0 + ",\"viewers\":" + viewers
                    + ",\"focus\":" + Json.str(focusMode) + ",\"diopters\":" + focusDiopters
                    + ",\"error\":" + Json.str(lastError) + "}";
        }
    }

    String camerasJson() {
        StringBuilder sb = new StringBuilder("{\"ok\":true,\"cameras\":[");
        try {
            String[] ids = manager.getCameraIdList();
            for (int i = 0; i < ids.length; i++) {
                CameraCharacteristics c = manager.getCameraCharacteristics(ids[i]);
                Integer facing = c.get(CameraCharacteristics.LENS_FACING);
                float[] focal = c.get(CameraCharacteristics.LENS_INFO_AVAILABLE_FOCAL_LENGTHS);
                Float minFocus = c.get(CameraCharacteristics.LENS_INFO_MINIMUM_FOCUS_DISTANCE);
                Integer level = c.get(CameraCharacteristics.INFO_SUPPORTED_HARDWARE_LEVEL);
                android.util.SizeF phys = c.get(CameraCharacteristics.SENSOR_INFO_PHYSICAL_SIZE);
                Integer orient = c.get(CameraCharacteristics.SENSOR_ORIENTATION);
                Integer focusCal = c.get(CameraCharacteristics.LENS_INFO_FOCUS_DISTANCE_CALIBRATION);
                StreamConfigurationMap map = c.get(CameraCharacteristics.SCALER_STREAM_CONFIGURATION_MAP);
                Size max = map == null ? null : largest(map.getOutputSizes(ImageFormat.JPEG));
                if (i > 0) sb.append(',');
                sb.append("{\"id\":").append(Json.str(ids[i]))
                  .append(",\"facing\":").append(Json.str(facing == null ? "unknown"
                          : facing == CameraCharacteristics.LENS_FACING_BACK ? "back"
                          : facing == CameraCharacteristics.LENS_FACING_FRONT ? "front" : "external"))
                  .append(",\"focal_mm\":").append(focal != null && focal.length > 0 ? focal[0] : 0)
                  .append(",\"min_focus_diopters\":").append(minFocus == null ? 0 : minFocus)
                  .append(",\"hardware_level\":").append(level == null ? -1 : level)
                  .append(",\"sensor_mm\":[").append(phys == null ? "0,0" : phys.getWidth() + "," + phys.getHeight()).append("]")
                  .append(",\"sensor_orientation\":").append(orient == null ? 0 : orient)
                  .append(",\"focus_calibration\":").append(Json.str(focusCal == null ? "unknown"
                          : focusCal == CameraCharacteristics.LENS_INFO_FOCUS_DISTANCE_CALIBRATION_CALIBRATED ? "calibrated"
                          : focusCal == CameraCharacteristics.LENS_INFO_FOCUS_DISTANCE_CALIBRATION_APPROXIMATE ? "approximate"
                          : "uncalibrated"))
                  .append(",\"max_size\":[").append(max == null ? "0,0" : max.getWidth() + "," + max.getHeight()).append("]}");
            }
        } catch (Exception e) {
            return "{\"ok\":false,\"error\":" + Json.str(e.toString()) + "}";
        }
        return sb.append("]}").toString();
    }

    void close() {
        synchronized (lock) { closeLocked(); }
        thread.quitSafely();
    }

    // ── camera lifecycle ─────────────────────────────────────────────────

    private void openLocked(Config cfg) throws Exception {
        CameraCharacteristics c = manager.getCameraCharacteristics(cfg.cameraId);
        StreamConfigurationMap map = c.get(CameraCharacteristics.SCALER_STREAM_CONFIGURATION_MAP);
        previewSize = closest(map.getOutputSizes(ImageFormat.YUV_420_888), cfg.width, cfg.height);
        stillSize = largest(map.getOutputSizes(ImageFormat.JPEG));
        previewReader = ImageReader.newInstance(previewSize.getWidth(), previewSize.getHeight(), ImageFormat.YUV_420_888, 3);
        stillReader = ImageReader.newInstance(stillSize.getWidth(), stillSize.getHeight(), ImageFormat.JPEG, 2);
        previewReader.setOnImageAvailableListener(this::onPreview, handler);
        stillReader.setOnImageAvailableListener(this::onStill, handler);

        CountDownLatch opened = new CountDownLatch(1);
        AtomicReference<Exception> err = new AtomicReference<>();
        try {
            manager.openCamera(cfg.cameraId, new CameraDevice.StateCallback() {
                @Override public void onOpened(CameraDevice d) { device = d; opened.countDown(); }
                @Override public void onDisconnected(CameraDevice d) { d.close(); lastError = "camera disconnected"; opened.countDown(); }
                @Override public void onError(CameraDevice d, int e) { d.close(); err.set(new IllegalStateException("camera error " + e)); opened.countDown(); }
            }, handler);
        } catch (SecurityException se) {
            throw new IllegalStateException("CAMERA permission not granted");
        }
        if (!opened.await(5, TimeUnit.SECONDS) || device == null) {
            throw err.get() != null ? err.get() : new IllegalStateException("camera open timed out");
        }

        CountDownLatch configured = new CountDownLatch(1);
        List<Surface> targets = new ArrayList<>(Arrays.asList(previewReader.getSurface(), stillReader.getSurface()));
        device.createCaptureSession(targets, new CameraCaptureSession.StateCallback() {
            @Override public void onConfigured(CameraCaptureSession s) { session = s; configured.countDown(); }
            @Override public void onConfigureFailed(CameraCaptureSession s) { lastError = "session configure failed"; configured.countDown(); }
        }, handler);
        if (!configured.await(5, TimeUnit.SECONDS) || session == null) throw new IllegalStateException("camera session failed: " + lastError);

        previewRequest = device.createCaptureRequest(CameraDevice.TEMPLATE_PREVIEW);
        previewRequest.addTarget(previewReader.getSurface());
        applyFocus(previewRequest);
        session.setRepeatingRequest(previewRequest.build(), null, handler);
        active = cfg;
        lastError = "";
        Log.i(TAG, "camera " + cfg.cameraId + " open: preview " + previewSize + ", still " + stillSize);
    }

    private void closeLocked() {
        try { if (session != null) session.close(); } catch (Exception ignored) { }
        try { if (device != null) device.close(); } catch (Exception ignored) { }
        if (previewReader != null) previewReader.close();
        if (stillReader != null) stillReader.close();
        session = null; device = null; previewReader = null; stillReader = null; active = null;
    }

    private void applyFocus(CaptureRequest.Builder b) {
        b.set(CaptureRequest.CONTROL_MODE, CaptureRequest.CONTROL_MODE_AUTO);
        switch (focusMode) {
            case "manual":
                b.set(CaptureRequest.CONTROL_AF_MODE, CaptureRequest.CONTROL_AF_MODE_OFF);
                b.set(CaptureRequest.LENS_FOCUS_DISTANCE, focusDiopters);
                break;
            case "auto":
                b.set(CaptureRequest.CONTROL_AF_MODE, CaptureRequest.CONTROL_AF_MODE_AUTO);
                break;
            default:
                b.set(CaptureRequest.CONTROL_AF_MODE, CaptureRequest.CONTROL_AF_MODE_CONTINUOUS_PICTURE);
        }
    }

    // ── frames ───────────────────────────────────────────────────────────

    private void onPreview(ImageReader r) {
        Image img = r.acquireLatestImage();
        if (img == null) return;
        try {
            byte[] jpeg = yuvToJpeg(img, quality);
            long ts = img.getTimestamp();
            synchronized (frameLock) {
                latest = new Frame(jpeg, ++seq, ts);
                frameLock.notifyAll();
            }
            fpsCount++;
            long now = System.nanoTime();
            if (now - fpsWindowStart > 1_000_000_000L) {
                fps = fpsCount * 1e9 / (now - fpsWindowStart);
                fpsCount = 0; fpsWindowStart = now;
            }
        } catch (Exception e) {
            lastError = e.toString();
        } finally {
            img.close();
        }
    }

    private void onStill(ImageReader r) {
        Image img = r.acquireLatestImage();
        if (img == null) return;
        try {
            ByteBuffer buf = img.getPlanes()[0].getBuffer();
            byte[] out = new byte[buf.remaining()];
            buf.get(out);
            stillResult.set(out);
        } finally {
            img.close();
            CountDownLatch l = stillLatch.getAndSet(null);
            if (l != null) l.countDown();
        }
    }

    /** YUV_420_888 (any stride / pixel layout) → NV21 → JPEG. */
    private static byte[] yuvToJpeg(Image img, int quality) {
        int w = img.getWidth(), h = img.getHeight();
        byte[] nv21 = new byte[w * h * 3 / 2];
        Image.Plane[] p = img.getPlanes();
        ByteBuffer y = p[0].getBuffer(), u = p[1].getBuffer(), v = p[2].getBuffer();
        int yRow = p[0].getRowStride(), yPix = p[0].getPixelStride();
        int pos = 0;
        if (yPix == 1 && yRow == w) {
            y.get(nv21, 0, w * h);                       // one bulk copy
            pos = w * h;
        } else if (yPix == 1) {
            for (int row = 0; row < h; row++) {          // bulk copy per row (padded rows)
                y.position(row * yRow);
                y.get(nv21, pos, w);
                pos += w;
            }
        } else {
            for (int row = 0; row < h; row++) {
                for (int col = 0; col < w; col++) nv21[pos++] = y.get(row * yRow + col * yPix);
            }
        }
        // Chroma: bulk-read each row of U and V, then interleave as V,U (NV21).
        int uvRow = p[1].getRowStride(), uvPix = p[1].getPixelStride();
        int rowLen = (w / 2 - 1) * uvPix + 1;
        byte[] uRow = new byte[rowLen], vRow = new byte[rowLen];
        for (int row = 0; row < h / 2; row++) {
            int base = row * uvRow;
            int len = Math.min(rowLen, u.capacity() - base);
            u.position(base); u.get(uRow, 0, len);
            v.position(base); v.get(vRow, 0, Math.min(rowLen, v.capacity() - base));
            for (int col = 0, i = 0; col < w / 2; col++, i += uvPix) {
                nv21[pos++] = vRow[i];
                nv21[pos++] = uRow[i];
            }
        }
        ByteArrayOutputStream out = new ByteArrayOutputStream(w * h / 4);
        new YuvImage(nv21, ImageFormat.NV21, w, h, null).compressToJpeg(new Rect(0, 0, w, h), quality, out);
        return out.toByteArray();
    }

    private static Size largest(Size[] sizes) {
        Size best = null;
        for (Size s : sizes) if (best == null || (long) s.getWidth() * s.getHeight() > (long) best.getWidth() * best.getHeight()) best = s;
        return best;
    }

    private static Size closest(Size[] sizes, int w, int h) {
        Size best = null;
        long bestScore = Long.MAX_VALUE;
        for (Size s : sizes) {
            long score = Math.abs((long) s.getWidth() * s.getHeight() - (long) w * h)
                    + 1000L * Math.abs(s.getWidth() * h - s.getHeight() * w) / Math.max(1, h);
            if (score < bestScore) { bestScore = score; best = s; }
        }
        return best;
    }
}
