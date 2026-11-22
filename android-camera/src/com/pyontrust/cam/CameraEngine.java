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
import android.os.Build;
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
    /** Old-API camera: hidden vendor cameras that the Camera2 legacy shim refuses ("Unknown camera ID"). */
    @SuppressWarnings("deprecation") private android.hardware.Camera legacy;
    private android.graphics.SurfaceTexture legacyTex;
    private final java.util.Set<String> listedIds = java.util.Collections.synchronizedSet(new java.util.HashSet<String>());
    private final java.util.Set<String> legacyIds = java.util.Collections.synchronizedSet(new java.util.HashSet<String>());
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
            if (isOpen() && cfg.sameAs(active)) return;
            closeLocked();
            openLocked(cfg);
        }
    }

    private boolean isOpen() { return (device != null && session != null) || legacy != null; }

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
            if (legacy != null) {
                legacyTakePicture();
            } else {
            CaptureRequest.Builder b = device.createCaptureRequest(CameraDevice.TEMPLATE_STILL_CAPTURE);
            b.addTarget(stillReader.getSurface());
            b.addTarget(previewReader.getSurface());
            applyFocus(b);
            b.set(CaptureRequest.JPEG_QUALITY, (byte) 95);
            session.capture(b.build(), null, handler);
            }
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
                if (legacy != null) {
                    if ("manual".equals(focusMode)) {
                        focusMode = "continuous";
                        return "{\"ok\":false,\"error\":\"manual focus is not available on this camera (old camera API)\"}";
                    }
                    legacyApplyFocus();
                } else if (session != null && previewRequest != null) {
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
            return "{\"ok\":true,\"open\":" + isOpen() + ",\"api\":" + Json.str(legacy != null ? "camera1" : "camera2") + ",\"camera\":" + Json.str(active == null ? "" : active.cameraId)
                    + ",\"preview\":" + Json.str(previewSize == null ? "" : previewSize.getWidth() + "x" + previewSize.getHeight())
                    + ",\"still\":" + Json.str(stillSize == null ? "" : stillSize.getWidth() + "x" + stillSize.getHeight())
                    + ",\"fps\":" + Math.round(fps * 10) / 10.0 + ",\"viewers\":" + viewers
                    + ",\"focus\":" + Json.str(focusMode) + ",\"diopters\":" + focusDiopters
                    + ",\"error\":" + Json.str(lastError) + "}";
        }
    }

    /** physical sub-camera id → its logical parent (null for directly openable cameras). */
    private final java.util.Map<String, String> physicalParent = java.util.Collections.synchronizedMap(new java.util.HashMap<>());

    /** Every camera the phone lets this app open: listed ids, hidden ids that still open
     *  (vendor aux cameras), and the physical sensors behind logical multi-cameras (API 28+). */
    String camerasJson() {
        StringBuilder sb = new StringBuilder("{\"ok\":true,\"cameras\":[");
        try {
            java.util.LinkedHashSet<String> listed = new java.util.LinkedHashSet<>(Arrays.asList(manager.getCameraIdList()));
            listedIds.clear(); listedIds.addAll(listed);
            java.util.LinkedHashSet<String> seen = new java.util.LinkedHashSet<>();
            boolean first = true;
            for (String id : listed) {
                first = appendCamera(sb, id, true, null, first);
                seen.add(id);
                if (Build.VERSION.SDK_INT >= 28) {
                    CameraCharacteristics c = manager.getCameraCharacteristics(id);
                    for (String pid : c.getPhysicalCameraIds()) {
                        if (seen.add(pid)) first = appendCamera(sb, pid, false, id, first);
                    }
                }
            }
            for (int i = 0; i < 10; i++) {                   // hidden ids (aux cameras not in the list)
                String id = String.valueOf(i);
                if (seen.contains(id)) continue;
                try {
                    manager.getCameraCharacteristics(id);
                } catch (Exception notThere) { continue; }
                seen.add(id);
                first = appendCamera(sb, id, false, null, first);
            }
        } catch (Exception e) {
            return "{\"ok\":false,\"error\":" + Json.str(e.toString()) + "}";
        }
        return sb.append("]}").toString();
    }

    private boolean appendCamera(StringBuilder sb, String id, boolean listed, String physicalOf, boolean first) {
        try {
            CameraCharacteristics c = manager.getCameraCharacteristics(id);
            Integer facing = c.get(CameraCharacteristics.LENS_FACING);
            float[] focal = c.get(CameraCharacteristics.LENS_INFO_AVAILABLE_FOCAL_LENGTHS);
            Float minFocus = c.get(CameraCharacteristics.LENS_INFO_MINIMUM_FOCUS_DISTANCE);
            Integer level = c.get(CameraCharacteristics.INFO_SUPPORTED_HARDWARE_LEVEL);
            android.util.SizeF phys = c.get(CameraCharacteristics.SENSOR_INFO_PHYSICAL_SIZE);
            Integer orient = c.get(CameraCharacteristics.SENSOR_ORIENTATION);
            Integer focusCal = c.get(CameraCharacteristics.LENS_INFO_FOCUS_DISTANCE_CALIBRATION);
            Integer cfa = c.get(CameraCharacteristics.SENSOR_INFO_COLOR_FILTER_ARRANGEMENT);
            StreamConfigurationMap map = c.get(CameraCharacteristics.SCALER_STREAM_CONFIGURATION_MAP);
            Size max = map == null ? null : largest(map.getOutputSizes(ImageFormat.JPEG));
            boolean oldApi = !listed && physicalOf == null && level != null
                    && level == CameraCharacteristics.INFO_SUPPORTED_HARDWARE_LEVEL_LEGACY;
            if (oldApi) legacyIds.add(id); else legacyIds.remove(id);
            boolean logical = false;
            if (Build.VERSION.SDK_INT >= 28) logical = c.getPhysicalCameraIds().size() > 1;
            boolean mono = Build.VERSION.SDK_INT >= 29 && cfa != null
                    && (cfa == CameraCharacteristics.SENSOR_INFO_COLOR_FILTER_ARRANGEMENT_MONO
                        || cfa == CameraCharacteristics.SENSOR_INFO_COLOR_FILTER_ARRANGEMENT_NIR);
            if (!first) sb.append(',');
            sb.append("{\"id\":").append(Json.str(id))
              .append(",\"facing\":").append(Json.str(facing == null ? "unknown"
                      : facing == CameraCharacteristics.LENS_FACING_BACK ? "back"
                      : facing == CameraCharacteristics.LENS_FACING_FRONT ? "front" : "external"))
              .append(",\"listed\":").append(listed)
              .append(",\"physical_of\":").append(physicalOf == null ? "null" : Json.str(physicalOf))
              .append(",\"logical\":").append(logical)
              .append(",\"api\":").append(Json.str(oldApi ? "camera1" : "camera2"))
              .append(",\"mono\":").append(mono)
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
            physicalParent.put(id, physicalOf);
            return false;
        } catch (Exception e) {
            Log.w(TAG, "camera " + id + " not usable: " + e);
            return first;
        }
    }

    void close() {
        synchronized (lock) { closeLocked(); }
        thread.quitSafely();
    }

    // ── camera lifecycle ─────────────────────────────────────────────────

    private void openLocked(Config cfg) throws Exception {
        if (physicalParent.isEmpty()) camerasJson();          // learn which ids are physical sub-cameras
        if (legacyIds.contains(cfg.cameraId)) { openLegacy(cfg); return; }
        String parent = physicalParent.get(cfg.cameraId);
        String openId = parent != null ? parent : cfg.cameraId;
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
            manager.openCamera(openId, new CameraDevice.StateCallback() {
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
        CameraCaptureSession.StateCallback cb = new CameraCaptureSession.StateCallback() {
            @Override public void onConfigured(CameraCaptureSession s) { session = s; configured.countDown(); }
            @Override public void onConfigureFailed(CameraCaptureSession s) { lastError = "session configure failed"; configured.countDown(); }
        };
        if (parent != null && Build.VERSION.SDK_INT >= 28) {
            // one sensor of a logical multi-camera: both streams come from that physical sensor
            List<android.hardware.camera2.params.OutputConfiguration> outs = new ArrayList<>();
            for (Surface sf : Arrays.asList(previewReader.getSurface(), stillReader.getSurface())) {
                android.hardware.camera2.params.OutputConfiguration oc = new android.hardware.camera2.params.OutputConfiguration(sf);
                oc.setPhysicalCameraId(cfg.cameraId);
                outs.add(oc);
            }
            device.createCaptureSessionByOutputConfigurations(outs, cb, handler);
        } else {
            device.createCaptureSession(new ArrayList<>(Arrays.asList(previewReader.getSurface(), stillReader.getSurface())), cb, handler);
        }
        if (!configured.await(5, TimeUnit.SECONDS) || session == null) throw new IllegalStateException("camera session failed: " + lastError);

        previewRequest = device.createCaptureRequest(CameraDevice.TEMPLATE_PREVIEW);
        previewRequest.addTarget(previewReader.getSurface());
        applyFocus(previewRequest);
        session.setRepeatingRequest(previewRequest.build(), null, handler);
        active = cfg;
        lastError = "";
        Log.i(TAG, "camera " + cfg.cameraId + " open: preview " + previewSize + ", still " + stillSize);
    }

    @SuppressWarnings("deprecation")
    private void closeLocked() {
        if (legacy != null) {
            try { legacy.setPreviewCallbackWithBuffer(null); legacy.stopPreview(); } catch (Exception ignored) { }
            try { legacy.release(); } catch (Exception ignored) { }
            legacy = null;
        }
        if (legacyTex != null) { legacyTex.release(); legacyTex = null; }
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

    // ── old camera API (hidden vendor cameras) ───────────────────────────

    @SuppressWarnings("deprecation")
    private void openLegacy(Config cfg) throws Exception {
        final int id = Integer.parseInt(cfg.cameraId);
        final CountDownLatch done = new CountDownLatch(1);
        final AtomicReference<Exception> err = new AtomicReference<>();
        handler.post(() -> {                          // callbacks arrive on the camera thread's looper
            try {
                android.hardware.Camera cam = openOldApi(id);
                android.hardware.Camera.Parameters prm = cam.getParameters();
                android.hardware.Camera.Size pv = closestLegacy(prm.getSupportedPreviewSizes(), cfg.width, cfg.height);
                android.hardware.Camera.Size pic = largestLegacy(prm.getSupportedPictureSizes());
                prm.setPreviewSize(pv.width, pv.height);
                prm.setPictureSize(pic.width, pic.height);
                prm.setPreviewFormat(ImageFormat.NV21);
                prm.setJpegQuality(95);
                cam.setParameters(prm);
                legacy = cam;
                legacyApplyFocus();
                legacyTex = new android.graphics.SurfaceTexture(10);
                cam.setPreviewTexture(legacyTex);
                final int w = pv.width, h = pv.height;
                for (int i = 0; i < 3; i++) cam.addCallbackBuffer(new byte[w * h * 3 / 2]);
                cam.setPreviewCallbackWithBuffer((data, c) -> {
                    try { onNv21(data, w, h); } finally { if (legacy != null) c.addCallbackBuffer(data); }
                });
                cam.startPreview();
                previewSize = new Size(w, h);
                stillSize = new Size(pic.width, pic.height);
            } catch (Exception e) {
                err.set(e);
            } finally {
                done.countDown();
            }
        });
        if (!done.await(8, TimeUnit.SECONDS)) throw new IllegalStateException("camera " + id + " open timed out");
        if (err.get() != null) { closeLocked(); throw new IllegalStateException("camera " + id + ": " + err.get().getMessage()); }
        active = cfg;
        lastError = "";
        Log.i(TAG, "camera " + id + " open (old API): preview " + previewSize + ", still " + stillSize);
    }

    /** Camera.open() refuses ids ≥ getNumberOfCameras(), which vendors lower to hide aux
     *  cameras; the camera service itself serves them.  openLegacy(id, HAL1) skips that
     *  Java-side check (framework API, reached by reflection). */
    @SuppressWarnings("deprecation")
    private static android.hardware.Camera openOldApi(int id) {
        try {
            java.lang.reflect.Method m = android.hardware.Camera.class.getMethod("openLegacy", int.class, int.class);
            return (android.hardware.Camera) m.invoke(null, id, 0x100);      // CAMERA_HAL_API_VERSION_1_0
        } catch (java.lang.reflect.InvocationTargetException e) {
            Log.w(TAG, "openLegacy(" + id + ") failed: " + e.getCause() + " — trying Camera.open");
        } catch (Throwable t) {
            Log.w(TAG, "openLegacy not available: " + t + " — trying Camera.open");
        }
        return android.hardware.Camera.open(id);
    }

    @SuppressWarnings("deprecation")
    private void legacyApplyFocus() {
        android.hardware.Camera.Parameters prm = legacy.getParameters();
        List<String> modes = prm.getSupportedFocusModes();
        String want = "auto".equals(focusMode) ? android.hardware.Camera.Parameters.FOCUS_MODE_AUTO
                : android.hardware.Camera.Parameters.FOCUS_MODE_CONTINUOUS_PICTURE;
        if (modes != null && modes.contains(want)) {
            prm.setFocusMode(want);
            legacy.setParameters(prm);
            if ("auto".equals(focusMode)) legacy.autoFocus((ok, c) -> { });
        }
    }

    @SuppressWarnings("deprecation")
    private void legacyTakePicture() {
        final android.hardware.Camera cam = legacy;
        cam.takePicture(null, null, (data, c) -> {
            stillResult.set(data);
            CountDownLatch l = stillLatch.getAndSet(null);
            if (l != null) l.countDown();
            try { c.startPreview(); } catch (Exception e) { lastError = e.toString(); }   // preview stops after a picture
        });
    }

    private void onNv21(byte[] nv21, int w, int h) {
        try {
            ByteArrayOutputStream out = new ByteArrayOutputStream(w * h / 4);
            new YuvImage(nv21, ImageFormat.NV21, w, h, null).compressToJpeg(new Rect(0, 0, w, h), quality, out);
            publish(out.toByteArray(), System.nanoTime());
        } catch (Exception e) {
            lastError = e.toString();
        }
    }

    @SuppressWarnings("deprecation")
    private static android.hardware.Camera.Size largestLegacy(List<android.hardware.Camera.Size> sizes) {
        android.hardware.Camera.Size best = null;
        for (android.hardware.Camera.Size s : sizes) if (best == null || (long) s.width * s.height > (long) best.width * best.height) best = s;
        return best;
    }

    @SuppressWarnings("deprecation")
    private static android.hardware.Camera.Size closestLegacy(List<android.hardware.Camera.Size> sizes, int w, int h) {
        android.hardware.Camera.Size best = null;
        long bestScore = Long.MAX_VALUE;
        for (android.hardware.Camera.Size s : sizes) {
            long score = Math.abs((long) s.width * s.height - (long) w * h)
                    + 1000L * Math.abs(s.width * h - s.height * w) / Math.max(1, h);
            if (score < bestScore) { bestScore = score; best = s; }
        }
        return best;
    }

    // ── frames ───────────────────────────────────────────────────────────

    private void onPreview(ImageReader r) {
        Image img = r.acquireLatestImage();
        if (img == null) return;
        try {
            publish(yuvToJpeg(img, quality), img.getTimestamp());
        } catch (Exception e) {
            lastError = e.toString();
        } finally {
            img.close();
        }
    }

    private void publish(byte[] jpeg, long ts) {
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
