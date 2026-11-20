// Camera dialog (calibration + flat-field) and the header status chips.

import { $, busy, post, setStatus } from './util.js';
import { store } from './state.js';

export class CameraPanel {
  constructor() {
    this.dialog = $('camera-dialog');
    store.subscribe(() => this.render());
  }

  open() { this.dialog.showModal(); }
  close() { this.dialog.close(); }

  render() {
    const s = store.server;
    if (!s) return;
    const chip = (id, text, cls = '') => { const el = $(id); el.textContent = text; el.className = `chip ${cls}`; el.hidden = !text; };

    // camera
    if (s.offline) chip('chip-camera', '⚠ gateway offline', 'bad');
    else if (store.cameraOk) chip('chip-camera', `● ${s.camera.info.type || 'Seek camera'}`, 'ok');
    else chip('chip-camera', s.camera?.status === 'no_driver' ? '⚠ no USB driver' : '○ no camera', 'bad');

    // what is happening right now
    const live = s.live || {};
    if (store.activity === 'measuring') {
      const m = s.measurement;
      chip('chip-activity', `◉ measuring ${m.total ? Math.round(m.frame / m.total * 100) + '%' : ''}`, 'busy');
    } else if (store.activity === 'tracking') chip('chip-activity', `● REC ${s.tracking.samples}`, 'rec');
    else if (store.ui.tab !== 'workspace') chip('chip-activity', '⏸ live paused', '');
    else if (live.ok) chip('chip-activity', `▶ live ${live.fps ?? ''} fps`, 'ok');
    else chip('chip-activity', '■ no image', '');

    // calibration offset is part of every reading — keep it visible
    const cal = s.calibration || {};
    chip('chip-cal', cal.calibrated ? `cal ${cal.offset_c >= 0 ? '+' : ''}${Number(cal.offset_c).toFixed(1)} °C` : '');

    $('cam-detail').textContent = store.cameraOk
      ? `${s.camera.info.type || 'Seek'} · ${s.camera.info.resolution || ''} · flat-field ${s.flat_field?.saved ? `active (${s.flat_field.set_at})` : 'not captured'}`
      : 'No Seek Thermal camera detected (USB 289D).';
    this.dialog.querySelectorAll('button[data-action^="calibrate"], button[data-action^="ff-"]').forEach(b => {
      b.disabled = !store.cameraOk || store.activity === 'measuring';
    });
  }

  async calibrate(clear) {
    const el = $('cal-status');
    const btns = [...this.dialog.querySelectorAll('[data-action^="calibrate"]')];
    await busy(btns, async () => {
      if (clear) {
        if (await store.mutate(post('calibrate', { clear: true }))) setStatus(el, '✓ Offset reset to zero.', 'ok');
        return;
      }
      const ref = parseFloat($('cal-ref-c').value);
      if (!isFinite(ref)) { setStatus(el, 'Enter a valid reference temperature.', 'err'); return; }
      setStatus(el, 'Measuring…');
      const d = await store.mutate(post('calibrate', { ref_c: ref }));
      if (d) setStatus(el, `✓ Offset ${d.offset_c >= 0 ? '+' : ''}${Number(d.offset_c).toFixed(2)} °C (scene median ${Number(d.scene_median_c).toFixed(1)} → ${ref} °C)`, 'ok');
      else setStatus(el, 'Calibration failed — see message.', 'err');
    });
  }

  async flatField(clear) {
    const el = $('ff-status');
    const btns = [...this.dialog.querySelectorAll('[data-action^="ff-"]')];
    await busy(btns, async () => {
      setStatus(el, clear ? 'Removing…' : 'Hold still — averaging 20 frames (~4 s)…');
      const d = await store.mutate(post('flat_field', clear ? { clear: true } : { frames: 20 }));
      if (!d) setStatus(el, 'Flat-field failed — see message.', 'err');
      else setStatus(el, d.cleared ? '✓ Flat-field removed.' : `✓ Captured from ${d.frames} frames.`, 'ok');
    });
  }
}
