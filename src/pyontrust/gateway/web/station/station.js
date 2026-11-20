// Station page: readiness, session (operator / DUT), self-tests, yield,
// run history, instrument register, audit trail.  All data comes from
// /station/api/* — the station's single source of truth.

const $ = id => document.getElementById(id);
const esc = v => String(v ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const when = iso => iso ? new Date(iso).toLocaleString() : '—';

async function api(path, { method = 'GET', body } = {}) {
  const r = await fetch(`/station/api/${path}`, {
    method, headers: body ? { 'Content-Type': 'application/json' } : {}, body: body ? JSON.stringify(body) : undefined,
  });
  let d = {};
  try { d = await r.json(); } catch { /* non-JSON */ }
  if (!r.ok || d.ok === false) throw new Error(d.error || `HTTP ${r.status}`);
  return d;
}
function toast(text, kind = 'info') {
  const t = document.createElement('div');
  t.className = `toast ${kind}`; t.textContent = text; t.addEventListener('click', () => t.remove());
  $('toasts').appendChild(t); setTimeout(() => t.remove(), kind === 'err' ? 12000 : 4000);
}
function status(el, text, kind = 'info') { el.textContent = text; el.className = `status-line ${kind}`; }
const table = (head, rows, cls = 'data') => rows.length
  ? `<table class="${cls}"><thead><tr>${head.map(h => `<th>${h}</th>`).join('')}</tr></thead><tbody>${rows.join('')}</tbody></table>`
  : '<div class="empty">Nothing yet.</div>';

// ── tabs ───────────────────────────────────────────────────────────────
const loaders = { overview: loadOverview, runs: loadRuns, instruments: loadInstruments, audit: loadAudit };
function showTab(name) {
  document.querySelectorAll('.tab-btn').forEach(b => b.classList.toggle('active', b.dataset.tab === name));
  document.querySelectorAll('.tab-panel').forEach(p => { p.hidden = p.id !== `tab-${name}`; });
  loaders[name]?.();
}
document.querySelectorAll('.tab-btn').forEach(b => b.addEventListener('click', () => showTab(b.dataset.tab)));

// ── readiness banner (+ tool lists for filters) ────────────────────────
async function loadHeader() {
  const d = await api('overview');
  const b = $('ready-banner');
  b.className = `ready-banner ${d.readiness.ready ? 'ready' : 'not-ready'}`;
  b.textContent = d.readiness.ready ? '✓ Station ready' : `✕ Not ready — ${d.readiness.reasons.length} issue(s)`;
  b.title = d.readiness.reasons.join('\n');
  const sf = $('session-form'), st = $('station-form');
  for (const k of ['operator', 'dut']) if (document.activeElement !== sf.elements[k]) sf.elements[k].value = d.session[k] || '';
  for (const k of ['name', 'location']) if (document.activeElement !== st.elements[k]) st.elements[k].value = d.station[k] || '';
  return d;
}

// ── overview ───────────────────────────────────────────────────────────
async function loadOverview() {
  loadHeader().catch(e => toast(e.message, 'err'));
  runSelftest();
  loadYield();
}

async function runSelftest() {
  $('selftest-meta').textContent = 'running…';
  try {
    const d = await api('selftest');
    const icon = { pass: '✓', warn: '!', fail: '✕' };
    $('selftest').innerHTML = Object.entries(d.results).map(([tool, r]) => `
      <div class="st-card ${r.status}"><h3>${esc(tool)}</h3>${r.checks.map(c => `
        <div class="st-check"><span class="s-${c.status}">${icon[c.status]}</span><span>${esc(c.name)}</span>
        ${c.detail ? `<span class="d">${esc(c.detail)}</span>` : ''}</div>`).join('')}</div>`).join('');
    $('selftest-meta').textContent = `${d.status.toUpperCase()} · ${d.elapsed_s}s · ${new Date().toLocaleTimeString()}`;
    loadHeader().catch(() => {});
  } catch (e) {
    $('selftest').innerHTML = `<p class="status-line err">${esc(e.message)}</p>`;
  }
}

async function loadYield() {
  const d = await api('runs/stats?days=30').catch(e => ({ groups: [], error: e.message }));
  $('yield').innerHTML = table(['Tool', 'Kind', 'Runs', 'Pass', 'Fail', 'Error', 'Yield'], d.groups.map(g => {
    const y = g.yield == null ? null : Math.round(g.yield * 1000) / 10;
    return `<tr><td>${esc(g.tool)}</td><td>${esc(g.kind)}</td><td>${g.total}</td><td>${g.counts.pass || 0}</td>
      <td>${g.counts.fail || 0}</td><td>${(g.counts.error || 0) + (g.counts.aborted || 0)}</td>
      <td>${y == null ? '—' : `<div style="display:flex;gap:8px;align-items:center"><div class="bar"><span style="width:${y}%"></span></div>${y}%</div>`}</td></tr>`;
  }));
}

// session / station forms save on change
$('session-form').addEventListener('change', async e => {
  try {
    await api('session', { method: 'POST', body: { [e.target.name]: e.target.value } });
    status($('session-msg'), `✓ ${e.target.name === 'dut' ? 'DUT' : 'Operator'} set`, 'ok');
  } catch (err) { status($('session-msg'), err.message, 'err'); }
});
$('station-form').addEventListener('change', async e => {
  try {
    await api('config', { method: 'PUT', body: { [e.target.name]: e.target.value } });
    status($('station-msg'), '✓ saved', 'ok');
  } catch (err) { status($('station-msg'), err.message, 'err'); }
});

// ── runs ───────────────────────────────────────────────────────────────
let runsCache = [];
async function fillToolFilters() {
  const r = await fetch('/api/tools').then(x => x.json()).catch(() => ({ tools: [] }));
  for (const sel of document.querySelectorAll('select[name="tool"]')) {
    if (sel.options.length > 1) continue;
    sel.insertAdjacentHTML('beforeend', r.tools.map(t => `<option value="${esc(t.id)}">${esc(t.nav_label)}</option>`).join(''));
  }
}
function runQuery() {
  const f = new FormData($('runs-filter'));
  const q = new URLSearchParams([...f.entries()].filter(([, v]) => v !== ''));
  $('runs-csv').href = `/station/api/runs/export.csv?${q}`;
  return q;
}
async function loadRuns() {
  await fillToolFilters();
  try {
    runsCache = (await api(`runs?${runQuery()}`)).runs;
    $('runs-table').innerHTML = table(['Started', 'Tool', 'Kind', 'DUT', 'Operator', 'Outcome', 'Duration'], runsCache.map((r, i) => `
      <tr class="clickable" data-i="${i}"><td>${when(r.started_at)}</td><td>${esc(r.tool)}</td><td>${esc(r.kind)}</td>
      <td class="mono">${esc(r.dut) || '—'}</td><td>${esc(r.operator) || '—'}</td>
      <td><span class="outcome o-${esc(r.outcome)}">${esc(r.outcome)}</span></td>
      <td>${r.duration_s != null ? `${r.duration_s}s` : '—'}</td></tr>`));
  } catch (e) { $('runs-table').innerHTML = `<p class="status-line err">${esc(e.message)}</p>`; }
}
$('runs-filter').addEventListener('change', loadRuns);
$('runs-filter').addEventListener('submit', e => { e.preventDefault(); loadRuns(); });
$('runs-table').addEventListener('click', e => {
  const tr = e.target.closest('tr[data-i]');
  if (!tr) return;
  document.querySelectorAll('#runs-table tr').forEach(x => x.classList.toggle('sel', x === tr));
  const r = runsCache[+tr.dataset.i];
  const el = $('run-detail');
  el.hidden = false;
  el.innerHTML = `<div class="panel-head"><h2>Run ${esc(r.id)}</h2><span class="outcome o-${esc(r.outcome)}">${esc(r.outcome)}</span></div>
    <p class="muted">${esc(r.tool)} · ${esc(r.kind)} · station ${esc(r.station)} · ${when(r.started_at)} → ${when(r.finished_at)}</p>
    <h3 class="muted" style="margin:10px 0 4px">Summary</h3><pre class="json">${esc(JSON.stringify(r.summary, null, 2))}</pre>
    ${r.artifacts.length ? `<h3 class="muted" style="margin:10px 0 4px">Artifacts</h3><ul>${r.artifacts.map(a => `<li class="mono">${esc(a)}</li>`).join('')}</ul>` : ''}`;
});

// ── instruments ────────────────────────────────────────────────────────
let instCache = [], editing = null;
const ST_TEXT = { ok: 'in calibration', due_soon: 'due soon', overdue: 'OVERDUE', no_cal: 'no calibration date' };
async function loadInstruments() {
  try {
    const d = await api('instruments');
    instCache = d.instruments;
    const s = d.summary;
    $('inst-summary').textContent = `${instCache.length} instrument(s) · ${s.overdue} overdue · ${s.due_soon} due soon`;
    $('inst-table').innerHTML = table(['Name', 'Kind', 'Model', 'Serial', 'Location', 'Cal. due', 'Status'], instCache.map((it, i) => `
      <tr class="clickable" data-i="${i}"><td>${esc(it.name)}</td><td>${esc(it.kind)}</td><td>${esc(it.model)}</td>
      <td class="mono">${esc(it.serial)}</td><td>${esc(it.location)}</td><td class="mono">${esc(it.cal_due) || '—'}</td>
      <td class="st-${it.status}">${ST_TEXT[it.status]}${it.days_to_due != null ? ` (${it.days_to_due} d)` : ''}</td></tr>`));
  } catch (e) { $('inst-table').innerHTML = `<p class="status-line err">${esc(e.message)}</p>`; }
}
function openEditor(item) {
  editing = item;
  const f = $('inst-form');
  f.reset();
  for (const el of f.elements) if (el.name) el.value = item?.[el.name] ?? '';
  $('inst-editor-title').textContent = item ? `Edit ${item.name}` : 'New instrument';
  f.closest('.panel').querySelector('[data-action="inst-delete"]').hidden = !item;
  $('inst-editor').hidden = false;
  status($('inst-msg'), '');
  f.elements.name.focus();
}
$('inst-table').addEventListener('click', e => {
  const tr = e.target.closest('tr[data-i]');
  if (tr) openEditor(instCache[+tr.dataset.i]);
});
async function saveInstrument() {
  const body = Object.fromEntries(new FormData($('inst-form')).entries());
  try {
    if (editing) await api(`instruments/${editing.id}`, { method: 'PATCH', body });
    else await api('instruments', { method: 'POST', body });
    $('inst-editor').hidden = true;
    toast(`Saved ${body.name}`, 'ok');
    loadInstruments(); loadHeader().catch(() => {});
  } catch (e) { status($('inst-msg'), e.message, 'err'); }
}
async function deleteInstrument() {
  if (!editing || !confirm(`Delete ${editing.name} from the register?`)) return;
  try {
    await api(`instruments/${editing.id}`, { method: 'DELETE' });
    $('inst-editor').hidden = true;
    loadInstruments(); loadHeader().catch(() => {});
  } catch (e) { status($('inst-msg'), e.message, 'err'); }
}

// ── audit ──────────────────────────────────────────────────────────────
async function loadAudit() {
  await fillToolFilters();
  verifyAudit();
  const q = new URLSearchParams([...new FormData($('audit-filter')).entries()].filter(([, v]) => v !== ''));
  try {
    const d = await api(`audit?limit=300&${q}`);
    $('audit-table').innerHTML = table(['#', 'Time', 'Operator', 'DUT', 'Action', 'Status', 'Client'], d.entries.map(e => `
      <tr title="${esc(JSON.stringify(e.body ?? {}))}"><td class="mono">${e.seq}</td><td>${when(e.ts)}</td>
      <td>${esc(e.operator) || '—'}</td><td class="mono">${esc(e.dut) || '—'}</td>
      <td class="mono">${esc(e.action)}</td><td class="${e.status >= 400 ? 's-fail' : 's-pass'}">${e.status}</td>
      <td class="mono">${esc(e.client)}</td></tr>`));
  } catch (err) { $('audit-table').innerHTML = `<p class="status-line err">${esc(err.message)}</p>`; }
}
async function verifyAudit() {
  const chip = $('audit-verify');
  const d = await fetch('/station/api/audit/verify').then(r => r.json()).catch(e => ({ ok: false, error: e.message }));
  chip.className = `chip ${d.ok ? 'ok' : 'bad'}`;
  chip.textContent = d.ok ? `✓ integrity verified · ${d.entries} entries` : `✕ ${d.error}${d.seq ? ` at #${d.seq}` : ''}`;
}
let auditTimer = 0;
$('audit-filter').addEventListener('input', () => { clearTimeout(auditTimer); auditTimer = setTimeout(loadAudit, 300); });
$('audit-filter').addEventListener('submit', e => e.preventDefault());

// ── actions ────────────────────────────────────────────────────────────
const ACTIONS = {
  selftest: runSelftest, 'inst-new': () => openEditor(null), 'inst-save': saveInstrument,
  'inst-cancel': () => { $('inst-editor').hidden = true; }, 'inst-delete': deleteInstrument,
  'audit-verify': verifyAudit,
};
document.addEventListener('click', e => {
  const b = e.target.closest('[data-action]');
  if (b && ACTIONS[b.dataset.action]) ACTIONS[b.dataset.action]();
});

showTab('overview');
