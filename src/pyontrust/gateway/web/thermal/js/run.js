// Run panel: Measure (timed PASS/FAIL test) or Track (open-ended CSV log).
// Both use the regions; only one runs at a time.  Button state, progress and
// status all derive from the server snapshot (activity / measurement / tracking).

import { $, fmtElapsed, get, post, regionColor, setStatus } from './util.js';
import { store } from './state.js';

const num = id => +$(id).value;

export class RunPanel {
  constructor({ onMeasurementDone }) {
    this.onMeasurementDone = onMeasurementDone;
    this.prevActivity = null;
    this.chartAt = 0;
    document.querySelectorAll('[data-run]').forEach(b =>
      b.addEventListener('click', () => store.setUi({ runTab: b.dataset.run })));
    $('cfg-mode').addEventListener('change', () => this.updateModeFields());
    this.updateModeFields();
    store.subscribe(() => this.render());
  }

  updateModeFields() {
    const mode = $('cfg-mode').value;
    document.querySelectorAll('[data-mode-only]').forEach(el => { el.hidden = el.dataset.modeOnly !== mode; });
  }

  config() {
    const mode = $('cfg-mode').value;
    const cfg = {
      mode, board_id: $('cfg-board-id').value,
      duration_s: num('cfg-duration'), capture_interval_s: num('cfg-interval'), warmup_frames: num('cfg-warmup'),
      global_max_temp_c: num('cfg-max-temp'), max_gradient_c_per_mm: num('cfg-max-gradient'),
      pixel_pitch_mm: num('cfg-pixel-pitch'),
      // no "zones": the server uses the stored regions (single source of truth)
    };
    if (mode === 'soak') Object.assign(cfg, { soak_stable_window_s: num('cfg-soak-window'),
      soak_stable_threshold_c: num('cfg-soak-thresh'), soak_timeout_s: num('cfg-soak-timeout') });
    if (mode === 'delta') Object.assign(cfg, { delta_baseline_frames: num('cfg-delta-baseline'),
      delta_stimulus_frames: num('cfg-delta-stimulus'), delta_pause_s: num('cfg-delta-pause') });
    return cfg;
  }

  startMeasurement() { return store.mutate(post('start', this.config())); }
  stopMeasurement() { return store.mutate(post('stop')); }
  startTracking() { return store.mutate(post('tracking/start', { interval_s: num('track-interval') })); }
  stopTracking() { return store.mutate(post('tracking/stop')); }

  // ── render from the snapshot ──────────────────────────────────────
  render() {
    const s = store.server;
    if (!s || s.offline) return;
    const act = store.activity;

    // While something runs, show its panel; otherwise the user's choice.
    const tab = act === 'measuring' ? 'measure' : act === 'tracking' ? 'track' : store.ui.runTab;
    document.querySelectorAll('[data-run]').forEach(b => {
      b.setAttribute('aria-pressed', String(b.dataset.run === tab));
      b.disabled = act !== 'idle' && b.dataset.run !== tab;
    });
    document.querySelectorAll('[data-run-panel]').forEach(p => { p.hidden = p.dataset.runPanel !== tab; });

    // Why can't I start? — one place, one message.
    const blocked = !store.cameraOk ? 'Connect the Seek Thermal camera to start a run.'
      : act === 'measuring' && tab === 'track' ? 'A measurement is running.'
      : act === 'tracking' && tab === 'measure' ? 'Tracking is running.'
      : tab === 'track' && !store.regions.length ? 'Add at least one region to track (click or drag on the image).'
      : '';
    setStatus($('run-blocked'), blocked, 'info');

    const idle = act === 'idle';
    const q = sel => document.querySelector(`[data-action="${sel}"]`);
    q('measure-start').disabled = !idle || !store.cameraOk;
    q('measure-stop').disabled = act !== 'measuring';
    q('track-start').disabled = !idle || !store.cameraOk || !store.regions.length;
    q('track-stop').disabled = act !== 'tracking';
    document.querySelectorAll('[data-run-panel] input, [data-run-panel] select').forEach(el => { el.disabled = !idle; });

    this.renderMeasurement(s.measurement);
    this.renderTracking(s.tracking);
    this.renderChart(s.tracking);

    if (this.prevActivity === 'measuring' && act !== 'measuring') this.onMeasurementDone(s.measurement.result);
    this.prevActivity = act;
  }

  renderMeasurement(m) {
    const prog = $('measure-progress');
    prog.hidden = !m.running;
    if (m.running) {
      const pct = m.total > 0 ? Math.min(100, m.frame / m.total * 100) : 0;
      $('prog-fill').style.width = `${pct.toFixed(1)}%`;
      const snap = m.latest_snapshot;
      $('prog-text').textContent = `Frame ${m.frame} / ${m.total || '?'} · ${m.elapsed_s.toFixed(1)} s` +
        (snap ? ` · max ${snap.global_max_c?.toFixed(1)} °C · ${snap.verdict}` : '');
    }
    const r = m.result;
    const last = $('measure-last');
    if (!r || m.running) setStatus(last, '');
    else if (r.outcome === 'pass') setStatus(last, `Last run: ✓ PASS (${r.mode}) — details in History`, 'ok');
    else if (r.outcome === 'fail') setStatus(last, `Last run: ✕ FAIL (${r.mode}) — details in History`, 'err');
    else if (r.outcome === 'aborted') setStatus(last, 'Last run: stopped by user', 'info');
    else setStatus(last, `Last run failed: ${r.error}`, 'err');
  }

  renderTracking(t) {
    $('track-csv').hidden = !t.csv_path;
    const el = $('track-text');
    if (t.running) setStatus(el, `● Recording — ${t.samples} samples · ${fmtElapsed(t.elapsed_s)}`, 'rec');
    else if (t.samples) setStatus(el, `Last session: ${t.samples} samples (${t.names.join(', ')})`, 'info');
    else setStatus(el, '');
  }

  // ── chart (series fetched separately: only while there is data) ──
  async renderChart(t) {
    const panel = $('chart-panel');
    if (!t.samples) { panel.hidden = true; return; }
    panel.hidden = false;
    const interval = t.running ? 2000 : 15000;
    if (Date.now() - this.chartAt < interval) return;
    this.chartAt = Date.now();
    const d = await get('tracking/status').catch(() => null);
    if (d) this.drawChart(d);
  }

  drawChart(d) {
    const cv = $('track-plot'), g = cv.getContext('2d');
    const W = cv.width, H = cv.height, series = d.series || [], sels = d.selections || [];
    g.clearRect(0, 0, W, H);
    $('chart-sub').textContent = `${d.samples} samples` + (d.csv_path ? ` · ${d.csv_path.split(/[\\/]/).pop()}` : '');
    if (!series.length) return;
    // colour = the region's colour when the region still exists (same as on the image)
    const byName = Object.fromEntries(store.regions.map(r => [r.name, regionColor(r.id)]));
    const colour = (s, i) => byName[s.name] || ['#89b4fa', '#a6e3a1', '#cba6f7', '#fab387'][i % 4];

    const mL = 52, mR = 14, mT = 28, mB = 24;
    let tmin = Infinity, tmax = -Infinity, vmin = Infinity, vmax = -Infinity;
    for (const row of series) {
      tmin = Math.min(tmin, row[0]); tmax = Math.max(tmax, row[0]);
      for (let i = 1; i < row.length; i++) if (isFinite(row[i])) { vmin = Math.min(vmin, row[i]); vmax = Math.max(vmax, row[i]); }
    }
    if (!isFinite(vmin)) return;
    if (tmax - tmin < 1e-6) tmax = tmin + 1;
    const pad = Math.max((vmax - vmin) * 0.1, 0.5); vmin -= pad; vmax += pad;
    const X = t => mL + (t - tmin) / (tmax - tmin) * (W - mL - mR);
    const Y = v => H - mB - (v - vmin) / (vmax - vmin) * (H - mT - mB);

    g.font = '11px ui-monospace, monospace'; g.strokeStyle = '#313244'; g.fillStyle = '#7f849c';
    for (let k = 0; k <= 4; k++) {
      const v = vmin + (vmax - vmin) * k / 4, y = Y(v);
      g.beginPath(); g.moveTo(mL, y); g.lineTo(W - mR, y); g.stroke();
      g.fillText(`${v.toFixed(1)}°`, 6, y + 4);
      const t = tmin + (tmax - tmin) * k / 4;
      g.fillText(fmtElapsed(t), Math.min(W - 40, X(t) - 10), H - 6);
    }
    sels.forEach((s, i) => {
      g.strokeStyle = colour(s, i); g.lineWidth = 1.8; g.beginPath();
      let on = false;
      for (const row of series) {
        const v = row[i + 1];
        if (!isFinite(v)) continue;
        if (on) g.lineTo(X(row[0]), Y(v)); else { g.moveTo(X(row[0]), Y(v)); on = true; }
      }
      g.stroke();
    });
    let lx = mL; g.font = '12px sans-serif';
    sels.forEach((s, i) => {
      g.fillStyle = colour(s, i); g.fillRect(lx, 8, 11, 11);
      g.fillStyle = '#cdd6f4'; g.fillText(s.name, lx + 15, 18);
      lx += 30 + g.measureText(s.name).width;
    });
  }
}

