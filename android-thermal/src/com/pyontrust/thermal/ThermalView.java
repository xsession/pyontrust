package com.pyontrust.thermal;

import android.content.Context;
import android.graphics.Bitmap;
import android.graphics.Canvas;
import android.graphics.Color;
import android.graphics.DashPathEffect;
import android.graphics.Paint;
import android.graphics.Rect;
import android.graphics.RectF;
import android.view.GestureDetector;
import android.view.MotionEvent;
import android.view.ScaleGestureDetector;
import android.view.View;

import java.util.List;

/**
 * The live image with every overlay: regions + readings (coloured by limit
 * level), hottest / coldest / centre markers, a tap-to-read cursor, the
 * colour scale, and touch tools to add / move / delete regions.
 * Pinch to zoom, drag to pan when zoomed.
 */
final class ThermalView extends View {
    static final int TOOL_NONE = 0, TOOL_POINT = 1, TOOL_RECT = 2, TOOL_LINE = 3, TOOL_DELETE = 4;

    interface Listener {
        void onRegionAdded(Region r);
        void onRegionChanged(Region r);
        void onRegionDeleted(Region r);
        void onRegionLongPress(Region r);
        void onRegionSelected(Region r);
    }

    private final Settings s;
    private Bitmap bmp;
    private Frame frame;
    private float rangeLo, rangeHi;
    private List<Region> regions;
    Region selected;
    int tool = TOOL_NONE;
    Listener listener;
    String banner;                       // e.g. "● REC" / "FROZEN"

    private float zoom = 1f, panX, panY;  // digital zoom
    private float scale, ox, oy;          // sensor px → view px
    private int cursorX = -1, cursorY = -1;
    private Region draft, dragging;
    private float dragSX, dragSY;
    private int dragRX, dragRY;
    private float downX, downY;
    private boolean panning;

    private final Paint bmpPaint = new Paint();
    private final Paint line = new Paint(Paint.ANTI_ALIAS_FLAG);
    private final Paint text = new Paint(Paint.ANTI_ALIAS_FLAG);
    private final Paint bg = new Paint();
    private final Paint fillP = new Paint();
    private final ScaleGestureDetector pinch;
    private final GestureDetector gestures;

    ThermalView(Context c, Settings s) {
        super(c);
        this.s = s;
        bmpPaint.setFilterBitmap(true);
        line.setStyle(Paint.Style.STROKE);
        text.setTextSize(13 * getResources().getDisplayMetrics().scaledDensity);
        text.setColor(Color.WHITE);
        text.setShadowLayer(3, 0, 0, Color.BLACK);
        bg.setColor(0xaa101018);
        setBackgroundColor(Color.BLACK);
        pinch = new ScaleGestureDetector(c, new ScaleGestureDetector.SimpleOnScaleGestureListener() {
            @Override
            public boolean onScale(ScaleGestureDetector d) {
                zoom = Math.max(1f, Math.min(8f, zoom * d.getScaleFactor()));
                clampPan();
                invalidate();
                return true;
            }
        });
        gestures = new GestureDetector(c, new GestureDetector.SimpleOnGestureListener() {
            @Override
            public void onLongPress(MotionEvent e) {
                Region r = hit(e.getX(), e.getY());
                if (r != null && listener != null) {
                    dragging = null;
                    listener.onRegionLongPress(r);
                }
            }

            @Override
            public boolean onDoubleTap(MotionEvent e) {
                zoom = zoom > 1f ? 1f : 2.5f;
                panX = panY = 0;
                invalidate();
                return true;
            }
        });
    }

    void setFrame(Frame f, Bitmap b, float lo, float hi, List<Region> regs) {
        frame = f;
        bmp = b;
        rangeLo = lo;
        rangeHi = hi;
        regions = regs;
        invalidate();
    }

    Frame frame() { return frame; }

    /** Forget the image (camera unplugged / waiting): only the banner is shown. */
    void clear() {
        frame = null;
        bmp = null;
        invalidate();
    }

    /** Draw the current image + overlays into a bitmap (for snapshots / reports). */
    Bitmap renderToBitmap() {
        if (frame == null || bmp == null) return null;
        int sc = Math.max(1, Math.round(640f / frame.w));
        int wv = frame.w * sc + (int) barWidth(), hv = frame.h * sc;
        Bitmap out = Bitmap.createBitmap(wv, hv, Bitmap.Config.ARGB_8888);
        Canvas c = new Canvas(out);
        c.drawColor(Color.BLACK);
        float z = zoom, px = panX, py = panY;
        zoom = 1; panX = panY = 0;
        int cx = cursorX;
        cursorX = -1;
        drawAll(c, wv, hv);
        zoom = z; panX = px; panY = py; cursorX = cx;
        return out;
    }

    @Override
    protected void onDraw(Canvas c) {
        drawAll(c, getWidth(), getHeight());
    }

    private int canvasW;

    private void drawAll(Canvas c, int W, int H) {
        canvasW = W;
        if (bmp == null || frame == null) {
            text.setTextAlign(Paint.Align.CENTER);
            List<String> lines = new java.util.ArrayList<>();
            for (String para : (banner != null ? banner : "No image").split("\n")) {      // word-wrap
                StringBuilder ln = new StringBuilder();
                for (String w : para.split(" ")) {
                    if (ln.length() > 0 && text.measureText(ln + " " + w) > W * 0.9f) { lines.add(ln.toString()); ln.setLength(0); }
                    ln.append(ln.length() > 0 ? " " : "").append(w);
                }
                lines.add(ln.toString());
            }
            float lh = text.getTextSize() * 1.5f;
            for (int i = 0; i < lines.size(); i++) c.drawText(lines.get(i), W / 2f, H / 2f + (i - (lines.size() - 1) / 2f) * lh, text);
            text.setTextAlign(Paint.Align.LEFT);
            return;
        }
        float barW = barWidth();
        float availW = W - barW;
        float base = Math.min(availW / frame.w, (float) H / frame.h);
        scale = base * zoom;
        ox = (availW - frame.w * base) / 2f - panX * zoom + frame.w * base * (1 - zoom) / 2f;
        oy = (H - frame.h * base) / 2f - panY * zoom + frame.h * base * (1 - zoom) / 2f;
        c.save();
        c.clipRect(0, 0, availW, H);
        c.drawBitmap(bmp, new Rect(0, 0, bmp.getWidth(), bmp.getHeight()),
                new RectF(ox, oy, ox + frame.w * scale, oy + frame.h * scale), bmpPaint);
        float dp = getResources().getDisplayMetrics().density;
        line.setStrokeWidth(2 * dp);

        if (regions != null) for (Region r : regions) drawRegion(c, r, dp);
        if (draft != null) drawRegion(c, draft, dp);

        if (s.showHot) marker(c, frame.maxX, frame.maxY, 0xffff3b30, "▲ " + s.fmt(frame.max), dp);
        if (s.showCold) marker(c, frame.minX, frame.minY, 0xff36a3ff, "▼ " + s.fmt(frame.min), dp);
        if (s.showCenter) {
            float cx = vx(frame.w / 2f), cy = vy(frame.h / 2f);
            line.setColor(Color.WHITE);
            c.drawLine(cx - 10 * dp, cy, cx + 10 * dp, cy, line);
            c.drawLine(cx, cy - 10 * dp, cx, cy + 10 * dp, line);
            c.drawText(s.fmt(frame.center), cx + 8 * dp, cy + 18 * dp, text);
        }
        if (cursorX >= 0) {
            float v = frame.at(cursorX, cursorY);
            float cx = vx(cursorX + .5f), cy = vy(cursorY + .5f);
            line.setColor(0xff39ff14);
            c.drawCircle(cx, cy, 8 * dp, line);
            label(c, cx + 10 * dp, cy - 10 * dp, s.fmt(v), 0xff39ff14);
        }
        c.restore();

        // HUD (top-left): min / max / centre, emissivity if not 1
        String hud = "max " + s.fmt(frame.max) + "   min " + s.fmt(frame.min) + "   ⌀ " + s.fmt(frame.mean)
                + (s.emissivity < 0.999f ? String.format(java.util.Locale.US, "   ε %.2f", s.emissivity) : "");
        label(c, 8 * dp, 20 * dp, hud, Color.WHITE);
        if (banner != null) label(c, 8 * dp, 40 * dp, banner, 0xffff5050);
        if (zoom > 1.01f) label(c, 8 * dp, H - 10 * dp, String.format(java.util.Locale.US, "zoom %.1f×", zoom), Color.LTGRAY);

        if (s.showScale) drawScale(c, W - barW, H, barW, dp);
    }

    private float barWidth() {
        return s.showScale ? 62 * getResources().getDisplayMetrics().density : 0;
    }

    private void drawScale(Canvas c, float x0, int H, float barW, float dp) {
        int[] lut = Palette.lut(s.palette);
        float top = 24 * dp, bottom = H - 24 * dp, bw = 16 * dp;
        float h = bottom - top;
        for (int i = 0; i < 256; i++) {
            fillP.setColor(lut[i]);
            float y1 = bottom - h * (i + 1) / 256f, y0 = bottom - h * i / 256f;
            c.drawRect(x0 + 6 * dp, y1, x0 + 6 * dp + bw, y0 + 1, fillP);
        }
        text.setTextSize(11 * getResources().getDisplayMetrics().scaledDensity);
        for (int g = 0; g <= 4; g++) {
            float v = rangeLo + (rangeHi - rangeLo) * g / 4f;
            float y = bottom - h * g / 4f;
            c.drawText(String.format(java.util.Locale.US, "%.1f", s.disp(v)), x0 + bw + 9 * dp, y + 4 * dp, text);
        }
        c.drawText(s.unit() + (s.autoRange ? " A" : " M"), x0 + 4 * dp, top - 8 * dp, text);
        if (s.isoMode != 0) {
            line.setColor(0xff39ff14);
            for (float iso : s.isoMode == 3 ? new float[]{s.isoLo, s.isoHi} : new float[]{s.isoLo}) {
                if (iso < rangeLo || iso > rangeHi) continue;
                float y = bottom - h * (iso - rangeLo) / (rangeHi - rangeLo);
                c.drawLine(x0 + 2 * dp, y, x0 + 10 * dp + bw, y, line);
            }
        }
        text.setTextSize(13 * getResources().getDisplayMetrics().scaledDensity);
    }

    private void drawRegion(Canvas c, Region r, float dp) {
        int col = r.level == 2 ? 0xffff3b30 : r.level == 1 ? 0xffffcc00 : 0xff7cff6b;
        if (r == draft) col = Color.WHITE;
        line.setColor(col);
        line.setPathEffect(r == selected ? new DashPathEffect(new float[]{8 * dp, 5 * dp}, 0) : null);
        String val;
        float lx, ly;
        if (r.isPoint()) {
            float cx = vx(r.x + .5f), cy = vy(r.y + .5f);
            c.drawCircle(cx, cy, 7 * dp, line);
            c.drawLine(cx - 12 * dp, cy, cx - 4 * dp, cy, line);
            c.drawLine(cx + 4 * dp, cy, cx + 12 * dp, cy, line);
            val = s.fmt(r.rMean);
            lx = cx + 10 * dp;
            ly = cy - 10 * dp;
        } else if (r.isLine()) {
            float x1 = vx(r.x + .5f), y1 = vy(r.y + .5f), x2 = vx(r.x + r.w + .5f), y2 = vy(r.y + r.h + .5f);
            c.drawLine(x1, y1, x2, y2, line);
            c.drawCircle(x1, y1, 3 * dp, line);
            c.drawCircle(x2, y2, 3 * dp, line);
            val = "max " + s.fmt(r.rMax);
            lx = Math.max(x1, x2) + 6 * dp;
            ly = Math.min(y1, y2);
        } else {
            c.drawRect(vx(r.x), vy(r.y), vx(r.x + r.w), vy(r.y + r.h), line);
            val = "max " + s.fmt(r.rMax) + "  ⌀ " + s.fmt(r.rMean);
            lx = vx(r.x) + 3 * dp;
            ly = vy(r.y) - 5 * dp;
        }
        line.setPathEffect(null);
        if (r != draft) label(c, lx, ly, (r.name == null ? "" : r.name + "  ") + val, col);
    }

    private void marker(Canvas c, int x, int y, int col, String txt, float dp) {
        float cx = vx(x + .5f), cy = vy(y + .5f);
        line.setColor(col);
        c.drawLine(cx - 9 * dp, cy - 9 * dp, cx + 9 * dp, cy + 9 * dp, line);
        c.drawLine(cx - 9 * dp, cy + 9 * dp, cx + 9 * dp, cy - 9 * dp, line);
        label(c, cx + 8 * dp, cy - 8 * dp, txt, col);
    }

    private void label(Canvas c, float x, float y, String t, int col) {
        float w = text.measureText(t);
        float dp = getResources().getDisplayMetrics().density;
        float right = (canvasW > 0 ? canvasW : getWidth()) - barWidth() - 4 * dp;
        if (x + w > right) x = Math.max(4 * dp, right - w);          // keep labels on screen
        if (y - text.getTextSize() < 0) y = text.getTextSize() + 2 * dp;
        c.drawRect(x - 3 * dp, y - text.getTextSize(), x + w + 3 * dp, y + 4 * dp, bg);
        text.setColor(col);
        c.drawText(t, x, y, text);
        text.setColor(Color.WHITE);
    }

    private float vx(float sx) { return ox + sx * scale; }
    private float vy(float sy) { return oy + sy * scale; }
    private int sx(float vx) { return (int) Math.floor((vx - ox) / scale); }
    private int sy(float vy) { return (int) Math.floor((vy - oy) / scale); }

    private void clampPan() {
        if (frame == null) return;
        float lim = frame.w * scale / zoom / 2f;
        panX = Math.max(-lim, Math.min(lim, panX));
        float limY = frame.h * scale / zoom / 2f;
        panY = Math.max(-limY, Math.min(limY, panY));
    }

    private Region hit(float x, float y) {
        if (regions == null || frame == null) return null;
        float tol = 18 * getResources().getDisplayMetrics().density;
        Region best = null;
        float bestD = tol;
        for (Region r : regions) {
            float d;
            if (r.isPoint()) {
                d = (float) Math.hypot(vx(r.x + .5f) - x, vy(r.y + .5f) - y);
            } else if (r.isLine()) {
                d = segDist(x, y, vx(r.x + .5f), vy(r.y + .5f), vx(r.x + r.w + .5f), vy(r.y + r.h + .5f));
            } else {
                boolean in = x >= vx(r.x) && x <= vx(r.x + r.w) && y >= vy(r.y) && y <= vy(r.y + r.h);
                d = in ? 0 : tol;
            }
            if (d < bestD) { bestD = d; best = r; }
        }
        return best;
    }

    private static float segDist(float px, float py, float ax, float ay, float bx, float by) {
        float dx = bx - ax, dy = by - ay;
        float len = dx * dx + dy * dy;
        float t = len == 0 ? 0 : Math.max(0, Math.min(1, ((px - ax) * dx + (py - ay) * dy) / len));
        return (float) Math.hypot(px - (ax + t * dx), py - (ay + t * dy));
    }

    @Override
    public boolean onTouchEvent(MotionEvent e) {
        if (frame == null) return true;
        pinch.onTouchEvent(e);
        gestures.onTouchEvent(e);
        if (pinch.isInProgress() || e.getPointerCount() > 1) {
            draft = null;
            dragging = null;
            return true;
        }
        float x = e.getX(), y = e.getY();
        int px = Math.max(0, Math.min(frame.w - 1, sx(x))), py = Math.max(0, Math.min(frame.h - 1, sy(y)));
        switch (e.getActionMasked()) {
            case MotionEvent.ACTION_DOWN:
                downX = x;
                downY = y;
                panning = false;
                if (tool == TOOL_RECT || tool == TOOL_LINE) {
                    draft = new Region(tool == TOOL_RECT ? "rect" : "line", px, py, 0, 0);
                } else if (tool == TOOL_NONE) {
                    dragging = hit(x, y);
                    if (dragging != null) {
                        dragSX = x; dragSY = y; dragRX = dragging.x; dragRY = dragging.y;
                    }
                }
                break;
            case MotionEvent.ACTION_MOVE:
                if (draft != null) {
                    draft.w = px - draft.x;
                    draft.h = py - draft.y;
                } else if (dragging != null) {
                    dragging.x = Math.max(0, Math.min(frame.w - 1, dragRX + Math.round((x - dragSX) / scale)));
                    dragging.y = Math.max(0, Math.min(frame.h - 1, dragRY + Math.round((y - dragSY) / scale)));
                } else if (tool == TOOL_NONE && zoom > 1f && (panning || Math.hypot(x - downX, y - downY) > 20)) {
                    panning = true;
                    panX -= (x - downX) / zoom;
                    panY -= (y - downY) / zoom;
                    downX = x;
                    downY = y;
                    clampPan();
                }
                invalidate();
                break;
            case MotionEvent.ACTION_UP:
                boolean tap = Math.hypot(x - downX, y - downY) < 12 * getResources().getDisplayMetrics().density;
                if (draft != null) {
                    Region d = draft;
                    draft = null;
                    if ("rect".equals(d.kind)) {      // normalise
                        if (d.w < 0) { d.x += d.w; d.w = -d.w; }
                        if (d.h < 0) { d.y += d.h; d.h = -d.h; }
                        d.w++;
                        d.h++;
                        if (d.w >= 2 && d.h >= 2 && listener != null) listener.onRegionAdded(d);
                    } else if (Math.abs(d.w) + Math.abs(d.h) >= 3 && listener != null) {
                        listener.onRegionAdded(d);
                    }
                } else if (tool == TOOL_POINT && tap) {
                    if (listener != null) listener.onRegionAdded(new Region("point", px, py, 1, 1));
                } else if (tool == TOOL_DELETE && tap) {
                    Region r = hit(x, y);
                    if (r != null && listener != null) listener.onRegionDeleted(r);
                } else if (tool == TOOL_NONE) {
                    if (dragging != null && !tap && listener != null) listener.onRegionChanged(dragging);
                    else if (tap) {
                        Region r = hit(x, y);
                        selected = r;
                        if (listener != null) listener.onRegionSelected(r);
                        if (r == null) {             // tap-to-read cursor (tap again on it to hide)
                            if (Math.abs(px - cursorX) <= 2 && Math.abs(py - cursorY) <= 2) cursorX = cursorY = -1;
                            else { cursorX = px; cursorY = py; }
                        }
                    }
                }
                dragging = null;
                invalidate();
                break;
            case MotionEvent.ACTION_CANCEL:
                draft = null;
                dragging = null;
                break;
            default:
        }
        return true;
    }
}
