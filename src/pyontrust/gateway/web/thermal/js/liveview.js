// Live image: MJPEG video + one overlay canvas that draws the regions from
// the store.  Gestures: click empty area = new point, drag = new rectangle,
// click a region = select it.

import { $, LEVEL_COLOR, post, regionColor } from './util.js';
import { store } from './state.js';

const DRAG_MIN_PX = 6;      // shorter pointer moves count as a click
const POINT_HIT_PX = 10;    // click radius that selects a point region

export class LiveView {
  constructor() {
    this.wrap = $('live-wrap'); this.img = $('live-img');
    this.canvas = $('live-overlay'); this.metaEl = $('live-meta');
    this.drag = null;
    new ResizeObserver(() => this.draw()).observe(this.wrap);
    this._bindPointer();
    store.subscribe(() => { this.draw(); this.renderMeta(); });
  }

  // ── stream (runs only while visible) ──────────────────────────────
  setStreaming(on) {
    if (on && !this.img.getAttribute('src')) this.img.src = `/thermal/api/stream?annotate=0&_=${Date.now()}`;
    if (!on) this.img.removeAttribute('src');   // closes the MJPEG connection
  }

  get native() {
    const l = store.server?.live;
    return l?.width ? { w: l.width, h: l.height } : { w: 206, h: 154 };
  }
  toPx(nx, ny) { const n = this.native; return [nx / n.w * this.wrap.clientWidth, ny / n.h * this.wrap.clientHeight]; }
  toNative(px, py) {
    const n = this.native;
    return [Math.max(0, Math.min(n.w - 1, Math.round(px / this.wrap.clientWidth * n.w))),
            Math.max(0, Math.min(n.h - 1, Math.round(py / this.wrap.clientHeight * n.h)))];
  }
  _eventPx(e) {
    const r = this.wrap.getBoundingClientRect();
    return [Math.max(0, Math.min(r.width, e.clientX - r.left)), Math.max(0, Math.min(r.height, e.clientY - r.top))];
  }

  renderMeta() {
    const s = store.server;
    if (!s) return;
    const l = s.live || {};
    if (s.offline) this.metaEl.textContent = `⚠ Gateway unreachable: ${s.offline}`;
    else if (l.error) this.metaEl.textContent = `⚠ ${l.error}`;
    else if (!l.active) this.metaEl.textContent = 'Connecting to camera…';
    else this.metaEl.textContent = `${l.min_c.toFixed(1)} … ${l.max_c.toFixed(1)} °C · centre ${l.center_c.toFixed(1)} °C · ${l.fps ?? '–'} fps`;
  }

  // ── overlay ───────────────────────────────────────────────────────
  draw() {
    const w = this.wrap.clientWidth, h = this.wrap.clientHeight;
    if (this.canvas.width !== w || this.canvas.height !== h) { this.canvas.width = w; this.canvas.height = h; }
    const g = this.canvas.getContext('2d');
    g.clearRect(0, 0, w, h);
    for (const r of store.regions) this._drawRegion(g, r, r.id === store.ui.selectedId);
    if (this.drag?.moved) {
      const { x0, y0, x1, y1 } = this.drag;
      g.strokeStyle = '#fff'; g.lineWidth = 1.5; g.setLineDash([4, 3]);
      g.strokeRect(Math.min(x0, x1), Math.min(y0, y1), Math.abs(x1 - x0), Math.abs(y1 - y0));
      g.setLineDash([]);
    }
  }

  _drawRegion(g, r, selected) {
    const lvl = r.reading?.level;
    const col = LEVEL_COLOR[lvl] || regionColor(r.id);
    const [x, y] = this.toPx(r.x, r.y);
    g.strokeStyle = col; g.lineWidth = selected ? 3 : 2;
    if (r.kind === 'rect') {
      const [x1, y1] = this.toPx(r.x + r.w, r.y + r.h);
      g.setLineDash(selected ? [] : [6, 3]);
      g.strokeRect(x, y, x1 - x, y1 - y);
      g.setLineDash([]);
      g.fillStyle = col + (selected ? '33' : '14');
      g.fillRect(x, y, x1 - x, y1 - y);
      label(g, r, col, x, y > 18 ? y - 5 : y + 15);
    } else {
      g.beginPath(); g.arc(x, y, selected ? 8 : 6, 0, Math.PI * 2); g.stroke();
      g.beginPath(); g.moveTo(x - 11, y); g.lineTo(x + 11, y); g.moveTo(x, y - 11); g.lineTo(x, y + 11); g.stroke();
      label(g, r, col, x + 11, y - 7);
    }
  }

  hitTest(px, py) {
    const regions = store.regions;
    for (let i = regions.length - 1; i >= 0; i--) {     // topmost first
      const r = regions[i];
      const [x, y] = this.toPx(r.x, r.y);
      if (r.kind === 'point') {
        if (Math.hypot(px - x, py - y) <= POINT_HIT_PX) return r;
      } else {
        const [x1, y1] = this.toPx(r.x + r.w, r.y + r.h);
        if (px >= x && px <= x1 && py >= y && py <= y1) return r;
      }
    }
    return null;
  }

  // ── gestures ──────────────────────────────────────────────────────
  _bindPointer() {
    this.wrap.addEventListener('pointerdown', e => {
      if (e.button !== 0) return;
      const [x, y] = this._eventPx(e);
      this.drag = { x0: x, y0: y, x1: x, y1: y, moved: false };
      this.wrap.setPointerCapture(e.pointerId);
      e.preventDefault();
    });
    this.wrap.addEventListener('pointermove', e => {
      if (!this.drag) return;
      [this.drag.x1, this.drag.y1] = this._eventPx(e);
      this.drag.moved ||= Math.hypot(this.drag.x1 - this.drag.x0, this.drag.y1 - this.drag.y0) >= DRAG_MIN_PX;
      if (this.drag.moved) this.draw();
    });
    const finish = e => {
      const d = this.drag; this.drag = null;
      if (!d || e.type === 'pointercancel') { this.draw(); return; }
      if (!d.moved) {
        const hit = this.hitTest(d.x0, d.y0);
        if (hit) { store.setUi({ selectedId: hit.id }); return; }
        const [x, y] = this.toNative(d.x0, d.y0);
        this._create({ kind: 'point', x, y });
      } else {
        const [x0, y0] = this.toNative(Math.min(d.x0, d.x1), Math.min(d.y0, d.y1));
        const [x1, y1] = this.toNative(Math.max(d.x0, d.x1), Math.max(d.y0, d.y1));
        this._create({ kind: 'rect', x: x0, y: y0, w: Math.max(2, x1 - x0), h: Math.max(2, y1 - y0) });
      }
      this.draw();
    };
    this.wrap.addEventListener('pointerup', finish);
    this.wrap.addEventListener('pointercancel', finish);
  }

  async _create(region) {
    const res = await store.mutate(post('regions', region));
    if (res?.region) store.setUi({ selectedId: res.region.id });
  }
}

function label(g, r, col, x, y) {
  const t = r.name + (r.reading?.max_c != null ? `  ${r.reading.max_c.toFixed(1)}°` : '');
  g.font = 'bold 12px ui-monospace, monospace';
  const w = g.measureText(t).width;
  g.fillStyle = 'rgba(17,17,27,.78)'; g.fillRect(x, y - 12, w + 8, 16);
  g.fillStyle = col; g.fillText(t, x + 4, y);
}
