// 3D Scan: left/right live feeds, live depth, synchronised pair capture.

const $ = id => document.getElementById(id);
const esc = v => String(v ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
let cameras = [];

async function api(path, body) {
  const r = await fetch(`/scan3d/api/${path}`, body === undefined ? {} : {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
  let d = {};
  try { d = await r.json(); } catch { /* non-JSON */ }
  if (!r.ok || d.ok === false) throw new Error(d.error || `HTTP ${r.status}`);
  return d;
}
function msg(t, kind = 'info') { $('msg').textContent = t; $('msg').className = `status-line ${kind}`; }
function busy(on, label) {
  $('run-status').textContent = on ? label : 'idle';
  $('run-status').className = `chip ${on ? 'running' : ''}`;
  document.querySelectorAll('[data-action]').forEach(b => { b.disabled = on; });
}
const rig = () => ({ left: $('left').value, right: $('right').value, rotate: +$('rotate').value,
  baseline_mm: +$('baseline').value, num_disp: $('num-disp').value,
  fx: +$('fx').value || undefined, fx_width: 1280 });
const pairQs = () => { const r = rig(); return `left=${encodeURIComponent(r.left)}&right=${encodeURIComponent(r.right)}&rotate=${r.rotate}`; };

// ── cameras ────────────────────────────────────────────────────────────
async function loadCameras(refresh = false) {
  try { cameras = (await api('cameras' + (refresh ? '?refresh=1' : ''))).cameras; }
  catch (e) { msg(e.message, 'err'); return; }
  const usable = cameras.filter(c => c.source);
  // one group per phone (main, other back cameras, front), then USB cameras
  const groups = new Map();
  for (const c of cameras) {
    const g = c.kind === 'phone' ? `📱 ${c.phone || c.serial || 'phone'}` : '🔌 USB cameras';
    if (!groups.has(g)) groups.set(g, []);
    groups.get(g).push(c);
  }
  const opts = [...groups].map(([g, cs]) => `<optgroup label="${esc(g)}">${cs.map(c => c.source
      ? `<option value="${esc(c.source)}">${esc(c.kind === 'phone' ? `${c.phone} · ${c.short || c.role}` : c.label)}</option>`
      : `<option disabled>${esc(c.label)}</option>`).join('')}</optgroup>`).join('');
  $('left').innerHTML = $('right').innerHTML = opts || '<option value="">no camera</option>';
  // default: the main cameras of two different phones; else two different cameras
  const phones = usable.filter(c => c.kind === 'phone');
  const bySerial = [...new Map(phones.slice().reverse().map(c => [c.serial, c])).values()].reverse();
  const pick = bySerial.length >= 2 ? bySerial : usable;
  if (pick[0]) $('left').value = pick[0].source;
  if (pick[1]) $('right').value = pick[1].source;
  if (!pick[1]) msg('Stereo needs two cameras — connect and authorise a second phone (or a second USB camera), then ↻ Rescan.', 'err');
  await autoFx();
  await showAlignment();
  restart();
}

async function autoFx() {
  const src = $('left').value;
  if (!src) return;
  const d = await api(`intrinsics?source=${encodeURIComponent(src)}&width=1280`).catch(() => null);
  if (d?.known) {
    $('fx').value = d.fx_px;
    $('fx-note').textContent = `fx from the phone: ${d.focal_mm} mm lens / ${d.sensor_mm[0]} mm sensor × 1280 px = ${d.fx_px} px`;
  } else {
    $('fx-note').textContent = d?.note || 'Enter fx from a calibration for metric depth.';
  }
}

// ── live ───────────────────────────────────────────────────────────────
let timers = [];
function streamUrl(src) { return `/scan3d/api/stream?source=${encodeURIComponent(src)}&rotate=${$('rotate').value}&_=${Date.now()}`; }
function restart() {
  timers.forEach(clearInterval); timers = [];
  ['img-left', 'img-right', 'img-depth'].forEach(id => $(id).removeAttribute('src'));
  const { left, right } = rig();
  if (left) $('img-left').src = streamUrl(left);
  if (right) $('img-right').src = streamUrl(right);
  if (pairProblem(rig())) msg(pairProblem(rig()), 'err');
  if ($('live-depth').checked && !pairProblem(rig())) {
    const p = new URLSearchParams(Object.entries({ ...rig(), track: $('track').checked ? 1 : 0 })
      .filter(([, v]) => v !== undefined));
    $('img-depth').src = `/scan3d/api/depth_stream?${p}&_=${Date.now()}`;
  }
  timers.push(setInterval(poll, 500));
}
async function poll() {
  if (document.hidden) return;
  const meta = async (src, el) => {
    if (!src) return;
    const d = await (await fetch(`/scan3d/api/live_stats?source=${encodeURIComponent(src)}`)).json().catch(() => ({}));
    el.textContent = d.error ? `⚠ ${d.error}` : d.active ? `● ${d.width}×${d.height} · ${d.fps ?? '–'} fps` : 'connecting…';
  };
  const { left, right } = rig();
  meta(left, $('meta-left')); meta(right, $('meta-right'));
  if ($('live-depth').checked) {
    const d = await (await fetch('/scan3d/api/depth_stats')).json().catch(() => ({}));
    $('meta-depth').textContent = d.error ? `⚠ ${d.error}` : d.active
      ? `● ${d.fps ?? '–'} fps · ${d.compute_ms} ms · ${d.valid_pct}% matched · median ${d.depth_median_m?.toFixed(2) ?? '—'} m`
        + (d.aligned ? ` · aligned${d.tracked_t && Date.now() / 1000 - d.tracked_t < 5 ? ' (following)' : ''}` : ' · not aligned')
      : 'starting…';
    placement(d.placement, d.aligned);
  } else { $('meta-depth').textContent = 'live depth off'; }
}

// Live placement guide: how well the two views overlap right now.
let shownAligned = false;
function placement(p, aligned) {
  const el = $('placement');
  if (!p || !$('track').checked) { el.textContent = ''; return; }
  if (p.error) {
    el.textContent = `placement: ${p.error} (side by side, same height, about the same distance)`;
    el.className = 'status-line err';
  } else {
    const tips = [];
    if (p.swapped) tips.push('the cameras look swapped — press ⇄ Swap');
    if (Math.abs(p.roll_deg) > 5) tips.push(`right phone rolled ${p.roll_deg.toFixed(1)}°`);
    if (Math.abs(p.scale - 1) > 0.15) tips.push(`right view ${p.scale < 1 ? 'larger' : 'smaller'} ×${(1 / p.scale).toFixed(2)} (different lens or distance)`);
    if (Math.abs(p.ty_px) > p.width * 0.08) tips.push(`right phone ${p.ty_px > 0 ? 'higher' : 'lower'} by ${Math.abs(p.ty_px)} px`);
    el.textContent = `placement: ${p.inliers}/${p.need} common features`
      + (p.ok ? ' ✓ compensating automatically' : ' — move the phones so they see more of the same scene')
      + (tips.length ? ` · ${tips.join(' · ')}` : '');
    el.className = `status-line ${p.ok ? 'ok' : 'err'}`;
  }
  if (aligned && !shownAligned) showAlignment();
  shownAligned = !!aligned;
}
['left', 'right', 'rotate', 'baseline', 'fx', 'num-disp', 'live-depth', 'track'].forEach(id => $(id).addEventListener('change', async () => {
  if (id === 'left') await autoFx();
  if (['left', 'right', 'rotate'].includes(id)) await showAlignment();
  restart();
}));

// ── camera position compensation ───────────────────────────────────────
function alignText(a) {
  return `aligned · zoom ×${a.scale.toFixed(3)} · roll ${a.roll_deg.toFixed(2)}° · height ${a.ty_px > 0 ? '+' : ''}${a.ty_px} px`
    + ` · rows off ${a.before_px.toFixed(1)} → ${a.residual_px.toFixed(2)} px · ${a.inliers} matches · depth window ${a.num_disp} px`;
}
async function showAlignment() {
  const r = rig();
  if (!r.left || !r.right || r.left === r.right) { $('align-status').textContent = ''; return; }
  const d = await api(`align?${pairQs()}`).catch(() => null);
  $('align-status').textContent = d?.aligned ? alignText(d.alignment) : 'not aligned — press 🎯 Auto-align';
  $('align-status').className = `status-line ${d?.aligned ? 'ok' : ''}`;
}
async function align() {
  const r = rig();
  if (pairProblem(r)) return msg(pairProblem(r), 'err');
  busy(true, 'aligning…');
  try {
    const d = await api('align', { ...r, ref_distance_mm: +$('ref-mm').value || undefined });
    $('align-status').textContent = alignText(d.alignment) + (d.note ? ` · ${d.note}` : '');
    $('align-status').className = `status-line ${d.warning ? 'err' : 'ok'}`;
    $('al-before').src = `data:image/jpeg;base64,${d.preview.before_b64}`;
    $('al-after').src = `data:image/jpeg;base64,${d.preview.after_b64}`;
    $('align-preview').hidden = false;
    msg(d.warning || `Cameras aligned in ${d.elapsed_s} s — live depth and captures use it now.`, d.warning ? 'err' : 'ok');
    restart();
  } catch (e) { $('align-status').textContent = e.message; $('align-status').className = 'status-line err'; }
  finally { busy(false); }
}
async function swap() {
  const l = $('left').value; $('left').value = $('right').value; $('right').value = l;
  await autoFx(); await showAlignment(); restart();
}
async function alignClear() {
  await api('align/clear', rig()).catch(e => msg(e.message, 'err'));
  $('align-preview').hidden = true;
  await showAlignment(); restart();
}
$('rescan').addEventListener('click', () => loadCameras(true));
document.addEventListener('visibilitychange', () => (document.hidden
  ? ['img-left', 'img-right', 'img-depth'].forEach(id => $(id).removeAttribute('src')) : restart()));

// ── capture ────────────────────────────────────────────────────────────
const phoneOf = s => (s || '').startsWith('phone:') ? s.split(':')[1] : null;
function pairProblem(r) {
  if (!r.left || !r.right || r.left === r.right) return 'Choose two different cameras';
  if (phoneOf(r.left) && phoneOf(r.left) === phoneOf(r.right)) return 'A phone runs one camera at a time — pick cameras on two different phones (or a USB camera)';
  return '';
}
async function capture(still) {
  const r = rig();
  if (pairProblem(r)) return msg(pairProblem(r), 'err');
  busy(true, still ? 'capturing stills…' : 'capturing…');
  try {
    const d = await api('capture', { ...r, still });
    const s = d.stats, im = d.images;
    const box = (l, v) => `<div class="stat-box"><div class="val">${esc(v ?? '—')}</div><div class="lbl">${l}</div></div>`;
    $('results').innerHTML = `<div class="result"><h2>Stereo result — ${esc(s.mode)}</h2>
      <div class="stats-grid">${box('Matched', s.valid_pct + '%')}${box('Points', s.n_points)}
        ${box('Near (m)', s.depth_min_m?.toFixed(3))}${box('Median (m)', s.depth_median_m?.toFixed(3))}${box('Far (m)', s.depth_max_m?.toFixed(3))}
        ${box('fx (px)', s.fx_px)}${box('Baseline (mm)', s.baseline_mm)}${box('Compute (s)', s.elapsed_s)}</div>
      <div class="images">
        <div><h4 class="muted">Depth</h4><img src="data:image/png;base64,${im.depth_b64}" alt="depth"></div>
        <div><h4 class="muted">Disparity</h4><img src="data:image/png;base64,${im.disparity_b64}" alt="disparity"></div>
        <div><h4 class="muted">Left (rectified)</h4><img src="data:image/png;base64,${im.left_b64}" alt="left"></div>
        <div><h4 class="muted">Right (rectified)</h4><img src="data:image/png;base64,${im.right_b64}" alt="right"></div></div></div>`;
    msg(`Captured ${s.width}×${s.height} pair — ${s.valid_pct}% of pixels matched.`, 'ok');
  } catch (e) { msg(e.message, 'err'); }
  finally { busy(false); }
}
document.addEventListener('click', e => {
  const b = e.target.closest('[data-action]');
  if (!b || b.disabled) return;
  if (b.dataset.action === 'capture-live') capture(false);
  if (b.dataset.action === 'capture-still') capture(true);
  if (b.dataset.action === 'align') align();
  if (b.dataset.action === 'swap') swap();
  if (b.dataset.action === 'align-clear') alignClear();
});

loadCameras();
