package com.pyontrust.thermal;

import org.json.JSONObject;

import java.io.BufferedOutputStream;
import java.io.DataOutputStream;
import java.io.File;
import java.io.FileOutputStream;
import java.io.IOException;
import java.io.RandomAccessFile;
import java.nio.ByteBuffer;
import java.nio.charset.StandardCharsets;

/**
 * Radiometric image / recording file ({@code .thr}): every pixel's °C is kept,
 * so a snapshot or recording can be re-measured later (new spots, palettes,
 * emissivity) exactly like the live image.
 *
 * Layout (big-endian): "PTHR", int version=1, int w, int h, int metaLen,
 * metaLen bytes UTF-8 JSON, then frames of {long timeMs, float[w*h]}.
 */
final class ThrFile {
    static final String EXT = ".thr";

    // ── writing ──────────────────────────────────────────────────────

    static final class Writer {
        private final DataOutputStream out;
        private final int w, h;
        int frames;

        Writer(File f, int w, int h, JSONObject meta) throws IOException {
            this.w = w;
            this.h = h;
            out = new DataOutputStream(new BufferedOutputStream(new FileOutputStream(f), 1 << 16));
            byte[] m = meta.toString().getBytes(StandardCharsets.UTF_8);
            out.writeBytes("PTHR");
            out.writeInt(1);
            out.writeInt(w);
            out.writeInt(h);
            out.writeInt(m.length);
            out.write(m);
        }

        void add(Frame f) throws IOException {
            if (f.w != w || f.h != h) return;      // rotation changed mid-recording: skip
            out.writeLong(f.timeMs);
            ByteBuffer bb = ByteBuffer.allocate(f.t.length * 4);
            bb.asFloatBuffer().put(f.t);
            out.write(bb.array());
            frames++;
        }

        void close() throws IOException { out.close(); }
    }

    static void writeSingle(File f, Frame fr, JSONObject meta) throws IOException {
        Writer w = new Writer(f, fr.w, fr.h, meta);
        w.add(fr);
        w.close();
    }

    // ── reading ──────────────────────────────────────────────────────

    static final class Reader implements AutoCloseable {
        final int w, h, frames;
        final JSONObject meta;
        private final RandomAccessFile raf;
        private final long dataStart;
        private final int frameBytes;
        final String name;

        Reader(File f) throws IOException {
            name = f.getName();
            raf = new RandomAccessFile(f, "r");
            byte[] magic = new byte[4];
            raf.readFully(magic);
            if (!"PTHR".equals(new String(magic, StandardCharsets.US_ASCII))) {
                raf.close();
                throw new IOException("not a pyontrust thermal file");
            }
            raf.readInt();
            w = raf.readInt();
            h = raf.readInt();
            byte[] m = new byte[raf.readInt()];
            raf.readFully(m);
            JSONObject j;
            try { j = new JSONObject(new String(m, StandardCharsets.UTF_8)); } catch (Exception e) { j = new JSONObject(); }
            meta = j;
            dataStart = raf.getFilePointer();
            frameBytes = 8 + w * h * 4;
            frames = (int) ((raf.length() - dataStart) / frameBytes);
        }

        Frame frame(int i, String source) throws IOException {
            raf.seek(dataStart + (long) i * frameBytes);
            long ts = raf.readLong();
            byte[] b = new byte[w * h * 4];
            raf.readFully(b);
            float[] t = new float[w * h];
            ByteBuffer.wrap(b).asFloatBuffer().get(t);
            return new Frame(w, h, t, ts, source);
        }

        @Override public void close() throws IOException { raf.close(); }
    }

    /** Plays a .thr file as a live source (original pace, looping). */
    static final class Playback implements FrameSource {
        private final File file;
        private Reader r;
        private int idx;
        private long lastWall, lastTs;
        volatile boolean paused;

        Playback(File file) { this.file = file; }

        @Override public String name() { return "▶ " + file.getName(); }
        @Override public void open() throws IOException { r = new Reader(file); idx = 0; }
        @Override public String calibrationKey() { return "playback"; }
        @Override public boolean isPlayback() { return true; }
        @Override public boolean supportsFlatField() { return false; }
        @Override public String captureFlatField(int frames) { throw new UnsupportedOperationException(); }
        @Override public void clearFlatField() { }
        int frames() { return r == null ? 0 : r.frames; }
        int index() { return idx; }

        @Override
        public synchronized Frame grab() throws Exception {
            if (r.frames == 0) throw new IOException("empty recording");
            Frame f = r.frame(idx, name());
            long gap = r.frames == 1 || paused ? 200 : Math.min(5000, Math.max(30, f.timeMs - lastTs));
            long sleep = gap - (System.currentTimeMillis() - lastWall);
            if (lastWall != 0 && sleep > 0) Thread.sleep(sleep);
            lastWall = System.currentTimeMillis();
            lastTs = f.timeMs;
            if (!paused) idx = (idx + 1) % r.frames;
            return new Frame(f.w, f.h, f.t, System.currentTimeMillis(), f.source);
        }

        synchronized void step(int d) {
            if (r != null && r.frames > 0) idx = ((idx + d) % r.frames + r.frames) % r.frames;
        }

        @Override
        public void close() {
            try { if (r != null) r.close(); } catch (IOException ignored) { }
        }
    }
}
