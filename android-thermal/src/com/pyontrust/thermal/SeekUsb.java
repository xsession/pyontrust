package com.pyontrust.thermal;

import android.hardware.usb.UsbConstants;
import android.hardware.usb.UsbDevice;
import android.hardware.usb.UsbDeviceConnection;
import android.hardware.usb.UsbEndpoint;
import android.hardware.usb.UsbInterface;
import android.hardware.usb.UsbManager;

import java.io.DataInputStream;
import java.io.DataOutputStream;
import java.io.File;
import java.io.FileInputStream;
import java.io.FileOutputStream;
import java.util.Arrays;

/**
 * Seek Thermal Compact / CompactXR / CompactPRO over Android USB host.
 *
 * Java port of pyontrust's {@code instruments/libseek_driver.py} (itself a port
 * of OpenThermal/libseek-thermal): same init sequence, same frame pipeline —
 * shutter flat-field, persistent bad-pixel map, column destriping, optional
 * user flat-field — and the same raw → °C mapping, so readings match the PC.
 */
final class SeekUsb implements FrameSource {
    static final int VID = 0x289D, PID_COMPACT = 0x0010, PID_PRO = 0x0011;

    // vendor commands (SeekDevice.h)
    private static final int GET_FACTORY_SETTINGS = 88, GET_FIRMWARE_INFO = 78, GET_OPERATION_MODE = 61,
            READ_CHIP_ID = 54, SET_FACTORY_SETTINGS_FEATURES = 86, SET_FIRMWARE_INFO_FEATURES = 85,
            SET_IMAGE_PROCESSING_MODE = 62, SET_OPERATION_MODE = 60, START_GET_IMAGE_TRANSFER = 83,
            TARGET_PLATFORM = 84;
    private static final int REQ_OUT = 0x41, REQ_IN = 0xC1, TIMEOUT = 1000;

    private static final int ID_CALIBRATION = 1, ID_IMAGE = 3, ID_DEAD_PIXEL = 4;
    private static final float BAD_SIGMA = 6f;
    private static final int BAD_FRAMES = 4;

    /** Raw count → °C (pyontrust RAW_TEMP_OFFSET / RAW_TEMP_SCALE); adjustable in Settings. */
    static float rawOffset = 6000f, rawScale = 50f;

    private final UsbManager manager;
    private final UsbDevice device;
    private final File flatFieldDir;
    private final boolean pro;
    private final int rawW, rawH, w, h, rx, ry, requestSize;

    private UsbDeviceConnection conn;
    private UsbInterface intf;
    private UsbEndpoint epIn;
    private byte[] rawBytes;
    private float[] ffc;          // last shutter frame (ROI)
    private float ffcMedian;
    private boolean[] deadMask;   // from the id=4 frame, used until the first shutter frame
    private boolean[] badMask;    // persistent bad pixels, learnt from the first corrected frames
    private boolean[][] badVotes = new boolean[BAD_FRAMES][];
    private int badVoteCount;
    private float[] userFlat;     // zero-mean residual map (vignetting)
    String firmware = "", chipId = "";

    SeekUsb(UsbManager manager, UsbDevice device, File flatFieldDir) {
        this.manager = manager;
        this.device = device;
        this.flatFieldDir = flatFieldDir;
        this.pro = device.getProductId() == PID_PRO;
        if (pro) {
            rawW = 342; rawH = 260; w = 320; h = 240; rx = 1; ry = 4; requestSize = 13680;
        } else {
            rawW = 208; rawH = 156; w = 206; h = 154; rx = 0; ry = 1; requestSize = 16224;
        }
    }

    static boolean isSeek(UsbDevice d) {
        return d != null && d.getVendorId() == VID
                && (d.getProductId() == PID_COMPACT || d.getProductId() == PID_PRO);
    }

    @Override public String name() { return (pro ? "Seek CompactPRO" : "Seek Compact") + " (USB)"; }
    @Override public String calibrationKey() { return pro ? "usb_pro" : "usb_compact"; }
    @Override public boolean isPlayback() { return false; }
    @Override public boolean supportsFlatField() { return true; }

    int width() { return w; }
    int height() { return h; }

    // ── USB plumbing ───────────────────────────────────────────────────

    @Override
    public void open() throws Exception {
        conn = manager.openDevice(device);
        if (conn == null) throw new IllegalStateException("cannot open the camera (USB permission?)");
        intf = device.getInterface(0);
        if (!conn.claimInterface(intf, true)) {
            close();
            throw new IllegalStateException("camera interface is busy");
        }
        for (int i = 0; i < intf.getEndpointCount(); i++) {
            UsbEndpoint e = intf.getEndpoint(i);
            if (e.getDirection() == UsbConstants.USB_DIR_IN && e.getType() == UsbConstants.USB_ENDPOINT_XFER_BULK) {
                epIn = e;
            }
        }
        if (epIn == null) { close(); throw new IllegalStateException("no bulk IN endpoint"); }
        rawBytes = new byte[rawW * rawH * 2];
        loadUserFlat();
        try {
            initialise();
        } catch (Exception e) {
            close();
            throw e;
        }
    }

    @Override
    public void close() {
        if (conn != null) {
            for (int i = 0; i < 3; i++) set(SET_OPERATION_MODE, new byte[]{0, 0});
            try { conn.releaseInterface(intf); } catch (Exception ignored) { }
            conn.close();
        }
        conn = null;
        ffc = null; badMask = null; badVoteCount = 0; deadMask = null;
    }

    private boolean set(int cmd, byte[] data) {
        return conn != null && conn.controlTransfer(REQ_OUT, cmd, 0, 0, data, data.length, TIMEOUT) >= 0;
    }

    private byte[] get(int cmd, int len) {
        byte[] b = new byte[len];
        int n = conn.controlTransfer(REQ_IN, cmd, 0, 0, b, len, TIMEOUT);
        return n < 0 ? null : Arrays.copyOf(b, n);
    }

    private void must(boolean ok, String what) {
        if (!ok) throw new IllegalStateException("camera init failed at " + what);
    }

    private byte[] mustGet(int cmd, int len, String what) {
        byte[] b = get(cmd, len);
        must(b != null, what);
        return b;
    }

    private void initialise() {
        for (int attempt = 0; attempt < 3; attempt++) {
            if (pro) initPro(); else initCompact();
            int[] raw = fetch();
            if (raw == null) continue;
            int id = frameId(raw);
            if (id != ID_DEAD_PIXEL) throw new IllegalStateException("expected first frame id=4, got " + id);
            deadMask = deadPixels(crop(raw));
            if (!grabImage()) throw new IllegalStateException("first frame failed after init");
            for (int i = 0; i < 5; i++) {      // warm-up
                try { grab(); } catch (Exception ignored) { }
            }
            return;
        }
        throw new IllegalStateException("camera did not start after 3 attempts");
    }

    private void targetPlatform() {
        if (!set(TARGET_PLATFORM, new byte[]{1})) {
            for (int i = 0; i < 3; i++) set(SET_OPERATION_MODE, new byte[]{0, 0});
            must(set(TARGET_PLATFORM, new byte[]{1}), "TARGET_PLATFORM");
        }
        must(set(SET_OPERATION_MODE, new byte[]{0, 0}), "SET_OPERATION_MODE 0");
        firmware = hex(mustGet(GET_FIRMWARE_INFO, 4, "GET_FIRMWARE_INFO"));
        chipId = hex(mustGet(READ_CHIP_ID, 12, "READ_CHIP_ID"));
    }

    private void factory(byte[] sel, int len) {
        must(set(SET_FACTORY_SETTINGS_FEATURES, sel), "SET_FACTORY_SETTINGS_FEATURES");
        mustGet(GET_FACTORY_SETTINGS, len, "GET_FACTORY_SETTINGS");
    }

    private void initCompact() {
        targetPlatform();
        factory(new byte[]{0x20, 0, 0x30, 0, 0, 0}, 64);
        factory(new byte[]{0x20, 0, 0x50, 0, 0, 0}, 64);
        factory(new byte[]{0x0C, 0, 0x70, 0, 0, 0}, 24);
        factory(new byte[]{0x06, 0, 0x08, 0, 0, 0}, 12);
        must(set(SET_IMAGE_PROCESSING_MODE, new byte[]{0x08, 0}), "SET_IMAGE_PROCESSING_MODE");
        get(GET_OPERATION_MODE, 2);
        must(set(SET_IMAGE_PROCESSING_MODE, new byte[]{0x08, 0}), "SET_IMAGE_PROCESSING_MODE");
        must(set(SET_OPERATION_MODE, new byte[]{1, 0}), "SET_OPERATION_MODE 1");
        get(GET_OPERATION_MODE, 2);
    }

    private void initPro() {
        targetPlatform();
        factory(new byte[]{0x06, 0, 0x08, 0, 0, 0}, 12);
        must(set(SET_FIRMWARE_INFO_FEATURES, new byte[]{0x17, 0}), "SET_FIRMWARE_INFO_FEATURES");
        mustGet(GET_FIRMWARE_INFO, 64, "GET_FIRMWARE_INFO 64");
        factory(new byte[]{0x01, 0, 0x00, 0x06, 0, 0}, 2);
        factory(new byte[]{0x01, 0, 0x01, 0x06, 0, 0}, 2);
        for (int addr = 0; addr < 2560; addr += 32) {
            factory(new byte[]{0x20, 0, (byte) (addr & 0xFF), (byte) (addr >> 8), 0, 0}, 64);
        }
        must(set(SET_FIRMWARE_INFO_FEATURES, new byte[]{0x15, 0}), "SET_FIRMWARE_INFO_FEATURES");
        mustGet(GET_FIRMWARE_INFO, 64, "GET_FIRMWARE_INFO 64");
        must(set(SET_IMAGE_PROCESSING_MODE, new byte[]{0x08, 0}), "SET_IMAGE_PROCESSING_MODE");
        must(set(SET_OPERATION_MODE, new byte[]{1, 0}), "SET_OPERATION_MODE 1");
    }

    /** START_GET_IMAGE_TRANSFER + bulk read of one raw frame (uint16 words). */
    private int[] fetch() {
        int size = rawW * rawH;
        if (!set(START_GET_IMAGE_TRANSFER, new byte[]{
                (byte) size, (byte) (size >> 8), (byte) (size >> 16), (byte) (size >> 24)})) return null;
        int total = rawBytes.length, off = 0;
        while (off < total) {
            int n = conn.bulkTransfer(epIn, rawBytes, off, Math.min(requestSize, total - off), TIMEOUT);
            if (n <= 0) return null;
            off += n;
        }
        int[] words = new int[size];
        for (int i = 0; i < size; i++) words[i] = (rawBytes[2 * i] & 0xFF) | ((rawBytes[2 * i + 1] & 0xFF) << 8);
        return words;
    }

    private int frameId(int[] raw) { return raw[pro ? 2 : 10]; }

    private float[] crop(int[] raw) {
        float[] o = new float[w * h];
        for (int y = 0; y < h; y++) {
            int src = (y + ry) * rawW + rx, dst = y * w;
            for (int x = 0; x < w; x++) o[dst + x] = raw[src + x];
        }
        return o;
    }

    private float[] lastImage;

    /** Read frames until a scene image (id=3); remember shutter frames (id=1). */
    private boolean grabImage() {
        for (int i = 0; i < 40; i++) {
            int[] raw = fetch();
            if (raw == null) return false;
            int id = frameId(raw);
            if (id == ID_IMAGE) { lastImage = crop(raw); return true; }
            if (id == ID_CALIBRATION) {
                ffc = crop(raw);
                float[] s = ffc.clone();
                Arrays.sort(s);
                ffcMedian = s[s.length / 2];
            }
        }
        return false;
    }

    // ── frame pipeline ─────────────────────────────────────────────────

    /** Corrected counts of the next scene frame. */
    float[] grabCounts() {
        if (conn == null) throw new IllegalStateException("camera not open");
        if (!grabImage()) throw new IllegalStateException("frame acquisition failed (camera unplugged?)");
        float[] img = lastImage.clone();
        if (ffc != null) {
            for (int i = 0; i < img.length; i++) img[i] = img[i] - ffc[i] + ffcMedian;
            boolean[] cur;
            if (badMask == null) {
                cur = outliers(img, median5(img), BAD_SIGMA);
                badVotes[badVoteCount++] = cur;
                if (badVoteCount >= BAD_FRAMES) {
                    boolean[] m = new boolean[img.length];
                    for (int i = 0; i < m.length; i++) {
                        boolean all = true;
                        for (boolean[] v : badVotes) all &= v[i];
                        m[i] = all;
                    }
                    badMask = m;
                    badVotes = new boolean[BAD_FRAMES][];
                }
            } else {
                cur = badMask;
            }
            img = fillBad(img, cur);
            img = destripe(img);
        } else if (deadMask != null) {
            img = fillBad(img, deadMask);
        }
        if (userFlat != null && userFlat.length == img.length) {
            for (int i = 0; i < img.length; i++) img[i] -= userFlat[i];
        }
        return img;
    }

    @Override
    public Frame grab() {
        float[] c = grabCounts();
        float[] t = new float[c.length];
        for (int i = 0; i < c.length; i++) t[i] = (Math.round(c[i]) - rawOffset) / rawScale;
        return new Frame(w, h, t, System.currentTimeMillis(), name());
    }

    /** Dead pixels in the id=4 frame: far below the histogram peak (libseek). */
    private boolean[] deadPixels(float[] f) {
        int[] hist = new int[0x4000];
        float max = 0;
        for (float v : f) {
            max = Math.max(max, v);
            int b = (int) v;
            if (b > 0 && b < hist.length) hist[b]++;
        }
        boolean[] dead = new boolean[f.length];
        if (max <= 0) return dead;
        int peak = 0;
        for (int i = 1; i < hist.length; i++) if (hist[i] > hist[peak]) peak = i;
        float thr = Math.max(0, peak - (max - peak));
        for (int i = 0; i < f.length; i++) dead[i] = f[i] < thr;
        return dead;
    }

    private float[] median5(float[] img) {
        float[] out = new float[img.length];
        float[] win = new float[25];
        for (int y = 0; y < h; y++) {
            for (int x = 0; x < w; x++) {
                int n = 0;
                for (int dy = -2; dy <= 2; dy++) {
                    int yy = reflect(y + dy, h);
                    for (int dx = -2; dx <= 2; dx++) win[n++] = img[yy * w + reflect(x + dx, w)];
                }
                // insertion sort of 25 values
                for (int i = 1; i < 25; i++) {
                    float v = win[i];
                    int j = i - 1;
                    while (j >= 0 && win[j] > v) { win[j + 1] = win[j]; j--; }
                    win[j + 1] = v;
                }
                out[y * w + x] = win[12];
            }
        }
        return out;
    }

    private static int reflect(int i, int n) {
        if (i < 0) return -i - 1;
        if (i >= n) return 2 * n - i - 1;
        return i;
    }

    private static boolean[] outliers(float[] img, float[] med, float nSigma) {
        float[] r = new float[img.length];
        for (int i = 0; i < r.length; i++) r[i] = Math.abs(img[i] - med[i]);
        float[] s = r.clone();
        Arrays.sort(s);
        float sigma = Math.max(1f, s[s.length / 2] * 1.4826f);
        boolean[] o = new boolean[img.length];
        for (int i = 0; i < r.length; i++) o[i] = r[i] > nSigma * sigma;
        return o;
    }

    /** Bad pixels ← mean of good neighbours (3×3, widening to 5×5 / 7×7 for clusters). */
    private float[] fillBad(float[] img, boolean[] bad) {
        float[] out = img.clone();
        for (int y = 0; y < h; y++) {
            for (int x = 0; x < w; x++) {
                int i = y * w + x;
                if (!bad[i]) continue;
                for (int k = 1; k <= 3; k++) {
                    double sum = 0;
                    int n = 0;
                    for (int dy = -k; dy <= k; dy++) {
                        int yy = y + dy;
                        if (yy < 0 || yy >= h) continue;
                        for (int dx = -k; dx <= k; dx++) {
                            int xx = x + dx;
                            if (xx < 0 || xx >= w || bad[yy * w + xx]) continue;
                            sum += img[yy * w + xx];
                            n++;
                        }
                    }
                    if (n > 0) { out[i] = (float) (sum / n); break; }
                }
            }
        }
        return out;
    }

    /** Remove the per-column read-out offset: column median of the high-pass residual. */
    private float[] destripe(float[] img) {
        float[] med = median5(img);
        float[] col = new float[h];
        float[] out = img.clone();
        for (int x = 0; x < w; x++) {
            for (int y = 0; y < h; y++) col[y] = img[y * w + x] - med[y * w + x];
            Arrays.sort(col);
            float off = col[h / 2];
            for (int y = 0; y < h; y++) out[y * w + x] -= off;
        }
        return out;
    }

    // ── user flat-field ────────────────────────────────────────────────

    private File flatFile() { return new File(flatFieldDir, "seek_flat_field_" + (pro ? "pro" : "compact") + ".bin"); }

    private void loadUserFlat() {
        File f = flatFile();
        if (!f.isFile()) return;
        try (DataInputStream in = new DataInputStream(new FileInputStream(f))) {
            int fw = in.readInt(), fh = in.readInt();
            if (fw != w || fh != h) return;
            float[] m = new float[fw * fh];
            for (int i = 0; i < m.length; i++) m[i] = in.readFloat();
            userFlat = m;
        } catch (Exception ignored) {
            userFlat = null;
        }
    }

    @Override
    public String captureFlatField(int frames) throws Exception {
        frames = Math.max(4, Math.min(100, frames));
        float[] prev = userFlat;
        userFlat = null;
        double[] acc = new double[w * h];
        try {
            for (int k = 0; k < frames; k++) {
                float[] c = grabCounts();
                for (int i = 0; i < c.length; i++) acc[i] += c[i];
            }
        } catch (RuntimeException e) {
            userFlat = prev;
            throw e;
        }
        float[] avg = new float[acc.length];
        for (int i = 0; i < avg.length; i++) avg[i] = (float) (acc[i] / frames);
        float[] s = avg.clone();
        Arrays.sort(s);
        float med = s[s.length / 2];
        double sq = 0;
        float lo = Float.MAX_VALUE, hi = -Float.MAX_VALUE;
        for (int i = 0; i < avg.length; i++) {
            avg[i] -= med;
            sq += avg[i] * avg[i];
            lo = Math.min(lo, avg[i]);
            hi = Math.max(hi, avg[i]);
        }
        userFlat = avg;
        flatFieldDir.mkdirs();
        try (DataOutputStream out = new DataOutputStream(new FileOutputStream(flatFile()))) {
            out.writeInt(w);
            out.writeInt(h);
            for (float v : avg) out.writeFloat(v);
        }
        return String.format(java.util.Locale.US, "flat-field learnt from %d frames: residual %.1f counts rms, %.0f p-p",
                frames, Math.sqrt(sq / avg.length), hi - lo);
    }

    @Override
    public void clearFlatField() {
        userFlat = null;
        //noinspection ResultOfMethodCallIgnored
        flatFile().delete();
    }

    boolean hasFlatField() { return userFlat != null; }

    private static String hex(byte[] b) {
        StringBuilder sb = new StringBuilder();
        for (byte x : b) sb.append(String.format("%02x", x));
        return sb.toString();
    }
}
