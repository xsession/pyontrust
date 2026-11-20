// Single source of truth on the client: the last /api/state snapshot from
// the server plus a little UI-only state.  Views never keep their own copy
// of server data — they subscribe and re-render from here.  Every mutation
// goes to the server and is followed by a fresh snapshot.

import { get, poller, toast } from './util.js';

export const store = {
  server: null,                       // last /api/state (authoritative)
  ui: { selectedId: null, runTab: 'measure', tab: 'workspace' },
  _subs: new Set(),

  subscribe(fn) { this._subs.add(fn); if (this.server) fn(this); return () => this._subs.delete(fn); },
  _emit() { this._subs.forEach(fn => { try { fn(this); } catch (e) { console.error(e); } }); },

  setUi(patch) { Object.assign(this.ui, patch); this._emit(); },

  async refresh() {
    try {
      this.server = await get('state');
      if (this.ui.selectedId && !this.regions.some(r => r.id === this.ui.selectedId)) this.ui.selectedId = null;
    } catch (e) {
      this.server = { ...(this.server || {}), offline: e.message };
    }
    this._emit();
  },

  /** Run a server mutation, then re-sync; errors become toasts. Returns the result or null. */
  async mutate(promise, okMessage) {
    try {
      const res = await promise;
      if (okMessage) toast(okMessage, 'ok');
      return res;
    } catch (e) {
      toast(e.message, 'err');
      return null;
    } finally {
      await this.refresh();
    }
  },

  // ── derived views of the snapshot ────────────────────────────────
  get regions() { return this.server?.regions || []; },
  get selected() { return this.regions.find(r => r.id === this.ui.selectedId) || null; },
  get activity() { return this.server?.activity || 'idle'; },
  get cameraOk() { return this.server?.camera?.status === 'connected'; },
};

const statePoller = poller(() => store.refresh(), 1000);
export const startSync = () => statePoller.start();
