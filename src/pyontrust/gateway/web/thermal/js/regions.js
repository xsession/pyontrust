// Regions panel: one table (live readings + limits + status) and an editor
// for the selected region.  Rendered from the store; edits PATCH the server.

import { $, del, esc, patch, regionColor, setStatus } from './util.js';
import { store } from './state.js';

const fmt = v => (v == null || !isFinite(v)) ? '—' : v.toFixed(1);
const LEVEL_TEXT = { ok: 'OK', warn: 'WARN', max: 'MAX' };
const FIELDS = ['name', 'x', 'y', 'w', 'h', 'warn_c', 'max_c'];

export class RegionsPanel {
  constructor() {
    this.table = $('regions-table');
    this.form = $('region-editor');
    this.msg = $('editor-msg');
    this.lockEl = $('regions-lock');
    this.editingId = null;

    this.table.addEventListener('click', e => {
      const row = e.target.closest('tr[data-id]');
      if (row) store.setUi({ selectedId: row.dataset.id });
    });
    this.form.addEventListener('change', e => this.save(e.target));
    this.form.addEventListener('submit', e => e.preventDefault());
    document.addEventListener('keydown', e => {
      const typing = /^(INPUT|SELECT|TEXTAREA)$/.test(document.activeElement?.tagName);
      if (!typing && e.key === 'Delete' && store.selected) { e.preventDefault(); this.remove(); }
      if (!typing && e.key === 'Escape') store.setUi({ selectedId: null });
    });
    store.subscribe(() => this.render());
  }

  get locked() { return store.activity !== 'idle'; }

  render() {
    const regions = store.regions;
    this.lockEl.hidden = !this.locked;

    this.table.innerHTML = regions.length
      ? `<table class="tbl"><thead><tr><th>Region</th><th>Min</th><th>Mean</th><th>Max</th><th>Warn</th><th>Limit</th><th>Status</th></tr></thead><tbody>${
          regions.map(r => {
            const rd = r.reading || {};
            return `<tr data-id="${esc(r.id)}" class="${r.id === store.ui.selectedId ? 'sel' : ''}">
              <td><span class="swatch" style="background:${regionColor(r.id)}"></span>${esc(r.name)}<span class="kind">${r.kind === 'point' ? '•' : '▭'}</span></td>
              <td>${fmt(rd.min_c)}</td><td>${fmt(rd.mean_c)}</td><td>${fmt(rd.max_c)}</td>
              <td>${fmt(r.warn_c)}</td><td>${fmt(r.max_c)}</td>
              <td>${rd.level ? `<span class="lvl lvl-${rd.level}">● ${LEVEL_TEXT[rd.level]}</span>` : '<span class="muted">—</span>'}</td></tr>`;
          }).join('')}</tbody></table>`
      : '<div class="empty">No regions yet.<br>Click the image to add a point, or drag to draw a rectangle around a component.</div>';

    this.renderEditor();
  }

  renderEditor() {
    const r = store.selected;
    this.form.hidden = !r;
    if (!r) { this.editingId = null; return; }
    const switched = this.editingId !== r.id;
    this.editingId = r.id;
    this.form.querySelectorAll('[data-rect-only]').forEach(el => { el.hidden = r.kind !== 'rect'; });
    for (const f of FIELDS) {
      const input = this.form.elements[f];
      input.disabled = this.locked;
      // Never overwrite what the user is typing; refresh everything else.
      if (switched || document.activeElement !== input) input.value = r[f];
    }
    this.form.querySelector('[data-action="region-delete"]').disabled = this.locked;
    if (switched) setStatus(this.msg, '');
  }

  async save(input) {
    const r = store.selected;
    if (!r || !FIELDS.includes(input.name)) return;
    const value = input.name === 'name' ? input.value.trim() : Number(input.value);
    const res = await store.mutate(patch(`regions/${r.id}`, { [input.name]: value }));
    if (res) setStatus(this.msg, '✓ saved', 'ok');
    else { input.value = store.selected?.[input.name] ?? ''; setStatus(this.msg, 'not saved', 'err'); }
  }

  async remove() {
    const r = store.selected;
    if (!r || this.locked) return;
    store.setUi({ selectedId: null });
    await store.mutate(del(`regions/${r.id}`), `Removed ${r.name}`);
  }
}
