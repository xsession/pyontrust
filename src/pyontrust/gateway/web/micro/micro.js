// Microscopy page: pick cameras (phones + USB), live feeds side by side,
// simultaneous capture / focus sweeps, per-camera stacks and results.

const $ = id => document.getElementById(id);
const esc = v => String(v ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
let cameras = [];            // from /api/cameras
let selected = [];           // selected source ids, in display order
const liveTimers = {};

async function api(path, body) {
  const r = await fetch(`/micro/api/${path}`, body === undefined ? {} : {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
  let d = {};
  try { d = await r.json(); } catch { /* non-JSON */ }
  if (!r.ok || d.ok === false) {
    const err = new Error(d.error || `HTTP ${r.status}`); err.data = d; throw err;
  }
  return d;
}
function toast(text, kind = 'info') {
  const t = document.createElement('div');
  t.className = `toast ${kind}`; t.textContent = text; t.addEventListener('click', () => t.remove());
  $('toasts').appendChild(t); setTimeout(() => t.remove(), kind === 'err' ? 12000 : 5000);
}
function msg(text, kind = 'info') { $('msg').textContent = text; $('msg').className = `status-line ${kind}`; }
function busy(on, label = 'working…') {
  $('run-status').textContent = on ? label : 'idle';
  $('run-status').className = `chip ${on ? 'running' : ''}`;
  document.querySelectorAll('[data-action]').forEach(b => { b.disabled = on; });
}
const labelOf = src => cameras.find(c => c.source === src)?.label || src;
const params = () => ({ rotate: +$('rotate').value, max_px: +$('max-px').value });

// ── cameras ────────────────────────────────────────────────────────────
async function loadCameras(refresh = false) {
  $('camera-list').innerHTML = '<p class="muted">Scanning phones and USB cameras…</p>';
  try {
    cameras = (await api('cameras' + (refresh ? '?refresh=1' : ''))).cameras;
  } catch (e) {
    $('camera-list').innerHTML = `<p class="status-line err">${esc(e.message)}</p>`;
    return;
  }
  const usable = cameras.filter(c => c.source);
  if (!selected.length || selected.some(s => !usable.some(c => c.source === s))) {
    // default: every phone's first back camera (both phones together); else first external USB camera
    const firstPerPhone = Object.values(Object.fromEntries(
      usable.filter(c => c.kind === 'phone').reverse().map(c => [c.serial, c.source])));
    selected = firstPerPhone.length ? firstPerPhone
      : usable.filter(c => c.kind === 'usb' && !/integrated|built-?in|facetime/i.test(c.name)).slice(0, 1).map(c => c.source);
  }
  $('camera-list').innerHTML = cameras.length ? cameras.map(c => c.source
    ? `<label class="cam-opt"><input type="checkbox" value="${esc(c.source)}" ${selected.includes(c.source) ? 'checked' : ''}>${esc(c.label)}</label>`
    : `<div class="cam-opt disabled" title="${esc(c.hint || '')}">${esc(c.label)}</div>`).join('')
    : '<p class="muted">No camera found — connect a phone (USB debugging) or a USB microscope, then ↻ Rescan.</p>';
  renderLive();
}
$('camera-list').addEventListener('change', e => {
  if (e.target.type !== 'checkbox') return;
  const phoneOf = s => s.startsWith('phone:') ? s.split(':')[1] : null;
  if (e.target.checked) {
    // a phone runs one camera at a time: selecting another camera of the same phone replaces it
    const ph = phoneOf(e.target.value);
    selected = selected.filter(s => !ph || phoneOf(s) !== ph);
    selected.push(e.target.value);
  } else {
    selected = selected.filter(s => s !== e.target.value);
  }
  document.querySelectorAll('#camera-list input').forEach(i => { i.checked = selected.includes(i.value); });
  renderLive();
});
$('rescan').addEventListener('click', () => loadCameras(true));
$('rotate').addEventListener('change', renderLive);

// ── live feeds ─────────────────────────────────────────────────────────
function renderLive() {
  Object.values(liveTimers).forEach(clearInterval);
  const grid = $('live-grid');
  grid.querySelectorAll('img').forEach(img => img.removeAttribute('src'));   // close old streams
  grid.innerHTML = selected.map((s, i) => `
    <div class="live-card"><h3>${esc(labelOf(s))}</h3>
      <img alt="live view ${i + 1}" data-src="${esc(s)}" src="/micro/api/stream?source=${encodeURIComponent(s)}&rotate=${$('rotate').value}&_=${Date.now()}">
      <div class="meter"><span></span></div>
      <div class="live-meta"><span class="meta">connecting…</span><span class="sharp"></span></div></div>`).join('');
  selected.forEach((s, i) => { liveTimers[s] = setInterval(() => pollLive(s, grid.children[i]), 400); });
  const phones = selected.filter(s => s.startsWith('phone:'));
  $('sweep-box').classList.toggle('disabled', !phones.length);
  $('capture-hint').textContent = selected.length ? `${selected.length} camera(s) selected` : 'select a camera above';
  refreshStacks();
}
const peaks = {};
async function pollLive(source, card) {
  if (!card || document.hidden) return;
  try {
    const d = await (await fetch(`/micro/api/live_stats?source=${encodeURIComponent(source)}`)).json();
    if (d.error) { card.querySelector('.meta').textContent = '⚠ ' + d.error; return; }
    if (!d.active) { card.querySelector('.meta').textContent = 'connecting…'; return; }
    peaks[source] = Math.max((peaks[source] || 0) * 0.995, d.sharpness || 0);
    card.querySelector('.meta').textContent = `● live · ${d.width}×${d.height} · ${d.fps ?? '–'} fps`;
    card.querySelector('.sharp').textContent = `focus ${d.sharpness} (${Math.round(100 * d.sharpness / (peaks[source] || 1))}% of peak)`;
    card.querySelector('.meter span').style.width = `${Math.min(100, 100 * d.sharpness / (peaks[source] || 1))}%`;
  } catch { /* transient */ }
}
document.addEventListener('visibilitychange', () => {
  document.querySelectorAll('#live-grid img').forEach(img => {
    if (document.hidden) img.removeAttribute('src');
    else img.src = `/micro/api/stream?source=${encodeURIComponent(img.dataset.src)}&rotate=${$('rotate').value}&_=${Date.now()}`;
  });
});

// ── stacks ─────────────────────────────────────────────────────────────
async function refreshStacks() {
  const d = await api('stack').catch(() => ({ stacks: {} }));
  $('stacks').innerHTML = Object.entries(d.stacks).filter(([, s]) => s.count).map(([src, s]) => `
    <div class="stack-row"><h4>${esc(labelOf(src))} — ${s.count} plane(s)${s.width ? ` · ${s.width}×${s.height}` : ''}</h4>
      <div class="thumbs">${(s.thumbs || []).map((t, i) => `<figure><img src="data:image/jpeg;base64,${t}" alt="plane ${i}">
        <figcaption>#${i}${s.z_mm[i] != null ? ` · ${s.z_mm[i]} mm` : ''} · ${s.sharpness[i]}</figcaption></figure>`).join('')}</div></div>`).join('');
}

async function capture() {
  if (!selected.length) return toast('Select a camera first', 'err');
  busy(true, 'capturing…');
  try {
    const d = await api('capture', { sources: selected, ...params() });
    const failed = Object.entries(d.results).filter(([, r]) => !r.ok);
    msg(failed.length ? `Captured on ${Object.keys(d.results).length - failed.length}; failed: ${failed.map(([s, r]) => `${labelOf(s)} — ${r.error}`).join('; ')}`
                      : 'Captured — step the focus and capture the next plane.', failed.length ? 'err' : 'ok');
  } catch (e) { msg(e.message, 'err'); }
  finally { busy(false); refreshStacks(); }
}

async function sweep() {
  const phones = selected.filter(s => s.startsWith('phone:'));
  if (!phones.length) return toast('Focus sweeps need a phone camera', 'err');
  busy(true, 'focus sweep…');
  msg(`Sweeping focus on ${phones.length} phone(s)… keep them still.`);
  try {
    const d = await api('sweep', { sources: phones, n_frames: +$('sweep-n').value, near_mm: +$('sweep-near').value,
      far_mm: +$('sweep-far').value, settle_ms: +$('sweep-settle').value, ...params() });
    msg(`Sweep done in ${d.elapsed_s}s: ${d.distances_mm.length} planes ${d.distances_mm[0]} → ${d.distances_mm.at(-1)} mm on ${phones.length} phone(s).`, 'ok');
  } catch (e) { msg(e.message, 'err'); }
  finally { busy(false); refreshStacks(); }
}

// ── run ────────────────────────────────────────────────────────────────
async function run() {
  busy(true, 'stacking…');
  $('progress').hidden = false;
  try {
    const d = await api('run', { sources: selected.length ? selected : undefined,
      step_um: +$('p-step-um').value, z0_um: +$('p-z0-um').value, px_um: +$('p-px-um').value, align: $('p-align').value === '1' });
    renderResults(d.results);
    msg(`Stacked ${d.results.filter(r => r.ok).length} camera(s).`, 'ok');
  } catch (e) {
    if (e.data?.results) renderResults(e.data.results);
    msg(e.message, 'err');
  } finally { busy(false); $('progress').hidden = true; }
}

function renderResults(results) {
  const labels = { stacked_png: 'Stacked PNG', heightmap_png: 'Height map PNG', mesh_stl: 'Surface STL', report_json: 'Report JSON' };
  $('results').innerHTML = results.map(r => {
    if (!r.ok) return `<div class="result"><h2>${esc(labelOf(r.source))}</h2><p class="status-line err">${esc(r.error)}</p></div>`;
    const s = r.stats, range = (s.height_max_um ?? 0) - (s.height_min_um ?? 0);
    const box = (l, v) => `<div class="stat-box"><div class="val">${esc(v)}</div><div class="lbl">${l}</div></div>`;
    return `<div class="result"><h2>${esc(labelOf(r.source))}</h2>
      <div class="stats-grid">${box('Planes', s.n_frames)}${box('Height range (µm)', range.toFixed(1))}
        ${box('Mean height (µm)', s.height_mean_um?.toFixed(1))}${box('Confidence', s.confidence_mean?.toFixed(3))}
        ${box('Depth scale', s.metric_from_focus ? 'focus distance' : 'Z-step')}${box('Elapsed (s)', s.elapsed_s)}</div>
      <div class="images"><div><h4 class="muted">All-in-focus composite</h4><img src="data:image/jpeg;base64,${r.stacked_png_b64}" alt="stacked"></div>
        ${r.heightmap_png_b64 ? `<div><h4 class="muted">Height map</h4><img src="data:image/png;base64,${r.heightmap_png_b64}" alt="height map"></div>` : ''}</div>
      <p class="exports">${Object.entries(r.export_urls || {}).map(([k, u]) => `<a href="${u}" download>⬇ ${labels[k] || k}</a>`).join('')}</p></div>`;
  }).join('');
}

// ── actions ────────────────────────────────────────────────────────────
const ACTIONS = {
  capture, sweep, run,
  undo: async () => { await api('stack/undo', {}).catch(() => {}); refreshStacks(); },
  clear: async () => { await api('stack/clear', {}).catch(() => {}); refreshStacks(); $('results').innerHTML = ''; },
};
document.addEventListener('click', e => {
  const b = e.target.closest('[data-action]');
  if (b && !b.disabled && ACTIONS[b.dataset.action]) ACTIONS[b.dataset.action]();
});
window.addEventListener('beforeunload', () => navigator.sendBeacon?.('/micro/api/release'));

loadCameras();
