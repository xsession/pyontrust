// Shared helpers: DOM, formatting, HTTP, notifications, persistence.

export const $ = (id) => document.getElementById(id);

/** Escape text for safe insertion into innerHTML. */
export function esc(v) {
  return String(v ?? '').replace(/[&<>"']/g, c => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
  }[c]));
}

export const fmtC = (v, digits = 1) => (v == null || !isFinite(v)) ? '—' : `${Number(v).toFixed(digits)}°`;

export function fmtElapsed(s) {
  if (s == null) return '';
  const m = Math.floor(s / 60), sec = Math.round(s % 60);
  return m > 0 ? `${m}m ${sec}s` : `${sec}s`;
}

/** Status line under a control: kind = ok | err | info | rec. */
export function setStatus(el, text, kind = 'info') {
  el.textContent = text;
  el.className = `status-line ${kind}`;
}

/** Non-blocking notification (replaces alert()); click to dismiss. Errors stay longer. */
export function toast(text, kind = 'info', ms = kind === 'err' ? 12000 : 5000) {
  const box = $('toasts');
  const t = document.createElement('div');
  t.className = `toast ${kind}`;
  t.setAttribute('role', kind === 'err' ? 'alert' : 'status');
  t.textContent = text;
  t.title = 'Click to dismiss';
  t.addEventListener('click', () => t.remove());
  box.appendChild(t);
  setTimeout(() => t.remove(), ms);
}

// ── HTTP ─────────────────────────────────────────────────────────────

export class ApiError extends Error {
  constructor(message, status, data) { super(message); this.status = status; this.data = data; }
}

/** JSON request against /thermal/api; throws ApiError with the server's message. */
export async function api(path, { method = 'GET', body } = {}) {
  const opts = { method, headers: {} };
  if (body !== undefined) {
    opts.headers['Content-Type'] = 'application/json';
    opts.body = JSON.stringify(body);
  }
  const r = await fetch(`/thermal/api/${path}`, opts);
  let data = {};
  try { data = await r.json(); } catch { /* non-JSON error page */ }
  if (!r.ok || data.ok === false || data.error) {
    throw new ApiError(data.error || `HTTP ${r.status}`, r.status, data);
  }
  return data;
}
export const get = (path) => api(path);
export const post = (path, body = {}) => api(path, { method: 'POST', body });
export const patch = (path, body = {}) => api(path, { method: 'PATCH', body });
export const del = (path) => api(path, { method: 'DELETE' });

/** Run fn while `buttons` are disabled. */
export async function busy(buttons, fn) {
  buttons.forEach(b => { b.disabled = true; });
  try { return await fn(); } finally { buttons.forEach(b => { b.disabled = false; }); }
}

/** Interval that never overlaps itself (skips a tick while the last one runs). */
export function poller(fn, ms) {
  let timer = null, running = false;
  const tick = async () => {
    if (running) return;
    running = true;
    try { await fn(); } catch { /* transient */ } finally { running = false; }
  };
  return {
    start() { if (!timer) { tick(); timer = setInterval(tick, ms); } },
    stop() { clearInterval(timer); timer = null; },
    get active() { return timer !== null; },
    tick,
  };
}

// ── persistence ──────────────────────────────────────────────────────

export const store = {
  load(key, fallback) {
    try { const v = JSON.parse(localStorage.getItem(`thermal.${key}`)); return v ?? fallback; }
    catch { return fallback; }
  },
  save(key, value) {
    try { localStorage.setItem(`thermal.${key}`, JSON.stringify(value)); } catch { /* quota / private mode */ }
  },
};

// ── colours ──────────────────────────────────────────────────────────
const PALETTE = ['#89b4fa', '#a6e3a1', '#cba6f7', '#94e2d5', '#fab387', '#f5c2e7', '#74c7ec', '#b4befe'];
/** Stable colour for a region id (unchanged when other regions are deleted). */
export function regionColor(id) {
  let h = 0;
  for (const c of String(id)) h = (h * 31 + c.charCodeAt(0)) >>> 0;
  return PALETTE[h % PALETTE.length];
}
export const LEVEL_COLOR = { warn: '#f9e2af', max: '#f38ba8' };
