// Thermal workspace entry point.
//
// Data flow (single source of truth):
//   server (/api/state, regions persisted server-side)
//     → store.server  (one poller, state.js)
//       → views render from it (header chips, live overlay, regions, run)
//   user action → API call → store.refresh() → views re-render

import { $, post, store as local, toast } from './util.js';
import { startSync, store } from './state.js';
import { LiveView } from './liveview.js';
import { RegionsPanel } from './regions.js';
import { RunPanel } from './run.js';
import { CameraPanel } from './camera.js';
import { loadHistory, loadReports } from './history.js';

const live = new LiveView();
const regions = new RegionsPanel();
const camera = new CameraPanel();
const run = new RunPanel({
  onMeasurementDone: result => {
    if (!result) return;
    const text = { pass: '✓ Measurement PASSED', fail: '✕ Measurement FAILED',
                   aborted: 'Measurement stopped', error: 'Measurement error' }[result.outcome];
    toast(`${text} — open History for details.`, result.outcome === 'pass' ? 'ok' : 'err', 8000);
  },
});

// ── tabs (ARIA + keyboard from ui-foundation.js) ───────────────────────
function showTab(name) {
  store.ui.tab = name;
  document.querySelectorAll('.tab-btn').forEach(b => b.classList.toggle('active', b.dataset.tab === name));
  document.querySelectorAll('.tab-panel').forEach(p => { p.hidden = p.id !== `tab-${name}`; });
  if (name === 'history') loadHistory();
  syncStream();
}
document.querySelectorAll('.tab-btn').forEach(b => b.addEventListener('click', () => showTab(b.dataset.tab)));

// Video only while the workspace is visible.
function syncStream() { live.setStreaming(!document.hidden && store.ui.tab === 'workspace'); }
document.addEventListener('visibilitychange', syncStream);

// ── one delegated handler for every button ─────────────────────────────
const ACTIONS = {
  'camera-open': () => camera.open(),
  'camera-close': () => camera.close(),
  calibrate: () => camera.calibrate(false),
  'calibrate-clear': () => camera.calibrate(true),
  'ff-capture': () => camera.flatField(false),
  'ff-clear': () => camera.flatField(true),
  'measure-start': () => run.startMeasurement(),
  'measure-stop': () => run.stopMeasurement(),
  'track-start': () => run.startTracking(),
  'track-stop': () => run.stopTracking(),
  'region-delete': () => regions.remove(),
  'reports-refresh': loadReports,
};
document.addEventListener('click', e => {
  const btn = e.target.closest('[data-action]');
  if (btn && !btn.disabled && ACTIONS[btn.dataset.action]) ACTIONS[btn.dataset.action]();
});

// ── one-time migration: regions kept in this browser by the old UI ─────
async function migrateLocalRegions() {
  const zones = local.load('zones', null), sels = local.load('trackSels', null);
  if (!zones && !sels) return;
  if (!store.regions.length) {
    const items = [
      ...(zones || []).map(z => ({ kind: 'rect', name: z.name, x: z.x, y: z.y, w: z.w, h: z.h, warn_c: z.warn, max_c: z.max })),
      ...(sels || []).map(s => s.type === 'patch'
        ? { kind: 'rect', name: s.name, x: s.x, y: s.y, w: s.w, h: s.h }
        : { kind: 'point', name: s.name, x: s.x, y: s.y }),
    ];
    for (const item of items) await post('regions', item).catch(() => {});
    if (items.length) toast(`Moved ${items.length} region(s) from this browser to the gateway.`, 'ok');
  }
  ['zones', 'trackSels', 'drawMode'].forEach(k => localStorage.removeItem(`thermal.${k}`));
  await store.refresh();
}

// ── start ──────────────────────────────────────────────────────────────
showTab('workspace');
await store.refresh();
await migrateLocalRegions();
startSync();
