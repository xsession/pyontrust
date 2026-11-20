// History tab: last measurement result + saved HTML reports.

import { $, esc, get } from './util.js';

const reportUrl = name => `/thermal/api/report/${encodeURIComponent(name)}`;
const box = (label, value) => `<div class="stat-box"><div class="val">${esc(value)}</div><div class="lbl">${label}</div></div>`;

export async function loadHistory() {
  await Promise.all([loadResult(), loadReports()]);
}

async function loadResult() {
  const el = $('result-content');
  let d;
  try {
    d = await get('result');
  } catch (e) {
    if (e.status === 404) return;                 // nothing run yet (placeholder stays)
    d = e.data && Object.keys(e.data).length ? e.data : { error: e.message };
  }
  if (d.error || d.aborted) {
    el.innerHTML = `<span class="badge fail big">${d.aborted ? '■ STOPPED' : '✕ ERROR'}</span>
      <p class="status-line err">${esc(d.error || d.message)}</p>`;
    return;
  }
  const fails = (d.fail_reasons || []).map(r => `<li>${esc(r)}</li>`).join('');
  const rows = (d.zone_stats || []).map(z => `<tr>
      <td>${esc(z.zone_name)}</td><td>${esc(z.min_temp_c)}</td><td>${esc(z.mean_temp_c)}</td><td>${esc(z.max_temp_c)}</td>
      <td>${z.temp_rise_c >= 0 ? '+' : ''}${esc(z.temp_rise_c)}</td>
      <td><span class="badge ${z.worst_verdict === 'NORMAL' ? 'pass' : 'fail'}">${esc(z.worst_verdict)}</span></td></tr>`).join('');
  const report = d.report_path ? d.report_path.split(/[\\/]/).pop() : null;
  el.innerHTML = `
    <span class="badge ${d.passed ? 'pass' : 'fail'} big">${d.passed ? '✓ PASS' : '✕ FAIL'}</span>
    ${fails ? `<ul class="fail-list">${fails}</ul>` : ''}
    <div class="stats-grid">${box('Mode', d.mode)}${box('Min °C', d.global_min_c)}${box('Mean °C', d.global_mean_c)}
      ${box('Max °C', d.global_max_c)}${box('Frames', d.total_frames)}${box('Duration s', d.duration_s)}</div>
    ${rows ? `<table class="tbl"><thead><tr><th>Region</th><th>Min</th><th>Mean</th><th>Max</th><th>Rise</th><th>Verdict</th></tr></thead><tbody>${rows}</tbody></table>` : ''}
    ${report ? `<div class="run-bar"><a class="btn btn-secondary" href="${reportUrl(report)}" target="_blank" rel="noopener">📄 Open HTML report</a></div>` : ''}`;
}

export async function loadReports() {
  const el = $('reports-list');
  try {
    const d = await get('reports');
    el.innerHTML = d.reports?.length
      ? d.reports.map(r => `<div class="report-item">
          <a href="${reportUrl(r.name)}" target="_blank" rel="noopener">📄 ${esc(r.name)}</a>
          <span class="muted">${esc(r.size_kb)} KB · ${esc(new Date(r.modified * 1000).toLocaleString())}</span></div>`).join('')
      : '<p class="muted">No reports saved yet.</p>';
  } catch (e) {
    el.innerHTML = `<p class="status-line err">Failed to load reports: ${esc(e.message)}</p>`;
  }
}
