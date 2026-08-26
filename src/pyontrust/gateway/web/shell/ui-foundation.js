/** Shared progressive enhancement for pyontrust web tools. */
(() => {
  'use strict';

  let generatedId = 0;
  const normalise = value => String(value || '')
    .replace(/[_-]+/g, ' ')
    .replace(/\s+/g, ' ')
    .trim();

  function ensureId(el, prefix = 'ui-control') {
    if (!el.id) el.id = `${prefix}-${++generatedId}`;
    return el.id;
  }

  function hasAccessibleName(el) {
    if (el.getAttribute('aria-label') || el.getAttribute('aria-labelledby')) return true;
    if (el.closest('label')) return true;
    if (el.id && document.querySelector(`label[for="${CSS.escape(el.id)}"]`)) return true;
    return false;
  }

  function candidateName(el) {
    const row = el.closest('.form-group, .prop-row, .send-row, .ifdoc-row, .sensor-select-row, .browser-path-row, .bench-actions, .modal-section');
    const rowLabel = row?.querySelector('label:not(:has(input, select, textarea))')?.textContent;
    const local = el.getAttribute('placeholder') || el.getAttribute('name') || el.getAttribute('title') || el.id;
    const combined = [normalise(rowLabel), normalise(local)].filter(Boolean).join(' — ');
    return combined || `${el.tagName.toLowerCase()} control`;
  }

  function labelControls(root = document) {
    root.querySelectorAll('input:not([type="hidden"]), select, textarea').forEach(el => {
      if (hasAccessibleName(el)) return;

      const prev = el.previousElementSibling;
      if (prev?.tagName === 'LABEL' && !prev.querySelector('input, select, textarea')) {
        prev.htmlFor = ensureId(el);
        return;
      }

      const group = el.closest('.form-group, .modal-section, .sensor-select-row');
      if (group) {
        const controls = group.querySelectorAll('input:not([type="hidden"]), select, textarea');
        const label = group.querySelector('label:not(:has(input, select, textarea))');
        if (controls.length === 1 && label) {
          label.htmlFor = ensureId(el);
          return;
        }
      }

      el.setAttribute('aria-label', candidateName(el));
    });
  }

  function enhanceTabs(root = document) {
    const sets = [
      {bar: '.tabs', tab: '.tab-btn', panelPrefix: 'tab-'},
      {bar: '#tab-bar', tab: '.tab', panelPrefix: 'panel-'},
      {bar: '.ifdoc-tabs', tab: '.ifdoc-tab', panelPrefix: 'panel-'},
    ];

    sets.forEach(({bar, tab, panelPrefix}) => {
      root.querySelectorAll(bar).forEach(tablist => {
        tablist.setAttribute('role', 'tablist');
        const tabs = [...tablist.querySelectorAll(tab)];
        tabs.forEach((item, index) => {
          const key = item.dataset.tab;
          const panel = key ? document.getElementById(`${panelPrefix}${key}`) : null;
          const id = ensureId(item, 'ui-tab');
          item.setAttribute('role', 'tab');
          item.tabIndex = item.classList.contains('active') ? 0 : -1;
          item.setAttribute('aria-selected', item.classList.contains('active') ? 'true' : 'false');
          if (panel) {
            panel.setAttribute('role', 'tabpanel');
            panel.setAttribute('aria-labelledby', id);
            item.setAttribute('aria-controls', panel.id);
          }
          if (item.dataset.uiKeysBound) return;
          item.dataset.uiKeysBound = 'true';
          item.addEventListener('keydown', event => {
            const keys = ['ArrowLeft', 'ArrowRight', 'Home', 'End'];
            if (!keys.includes(event.key)) return;
            event.preventDefault();
            let targetIndex = index;
            if (event.key === 'ArrowLeft') targetIndex = (index - 1 + tabs.length) % tabs.length;
            if (event.key === 'ArrowRight') targetIndex = (index + 1) % tabs.length;
            if (event.key === 'Home') targetIndex = 0;
            if (event.key === 'End') targetIndex = tabs.length - 1;
            tabs[targetIndex]?.focus();
            tabs[targetIndex]?.click();
          });
        });

        const sync = () => tabs.forEach(item => {
          const active = item.classList.contains('active');
          item.setAttribute('aria-selected', active ? 'true' : 'false');
          item.tabIndex = active ? 0 : -1;
        });
        tablist.addEventListener('click', () => requestAnimationFrame(sync));
      });
    });
  }

  function enhanceDialogs(root = document) {
    root.querySelectorAll('.modal-overlay, .live-overlay').forEach(dialog => {
      if (dialog.dataset.uiDialogEnhanced) return;
      dialog.dataset.uiDialogEnhanced = 'true';
      dialog.setAttribute('role', 'dialog');
      dialog.setAttribute('aria-modal', 'true');
      const heading = dialog.querySelector('h1, h2, h3, [data-dialog-title]');
      if (heading) {
        dialog.setAttribute('aria-labelledby', ensureId(heading, 'ui-dialog-title'));
      }

      let returnFocus = null;
      const sync = () => {
        const style = getComputedStyle(dialog);
        const visible = style.display !== 'none' && style.visibility !== 'hidden' && (dialog.classList.contains('open') || style.display === 'flex' || style.display === 'grid');
        dialog.setAttribute('aria-hidden', visible ? 'false' : 'true');
        if (visible) {
          returnFocus = document.activeElement;
          requestAnimationFrame(() => dialog.querySelector('button:not(:disabled), input:not(:disabled), select:not(:disabled), textarea:not(:disabled), [tabindex="0"]')?.focus());
        } else if (returnFocus && document.contains(returnFocus)) {
          returnFocus.focus({preventScroll: true});
          returnFocus = null;
        }
      };
      new MutationObserver(sync).observe(dialog, {attributes: true, attributeFilter: ['class', 'style']});
      sync();

      dialog.addEventListener('keydown', event => {
        if (event.key !== 'Tab' || dialog.getAttribute('aria-hidden') === 'true') return;
        const focusables = [...dialog.querySelectorAll('button:not(:disabled), input:not(:disabled), select:not(:disabled), textarea:not(:disabled), a[href], [tabindex]:not([tabindex="-1"])')]
          .filter(el => el.getClientRects().length > 0);
        if (!focusables.length) return;
        const first = focusables[0];
        const last = focusables[focusables.length - 1];
        if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
        if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
      });
    });
  }

  function enhanceStatus(root = document) {
    [
      '#exec-status', '#run-state', '#cam-status', '#dataset-pill', '#scan-time',
      '#conn-badge', '#sb-state', '#re-status', '#status-message', '#app-message',
      '#console-output', '#event-log', '#live-raw', '#send-log'
    ].forEach(selector => root.querySelectorAll(selector).forEach(el => {
      el.setAttribute('role', el.tagName === 'PRE' ? 'log' : 'status');
      el.setAttribute('aria-live', el.tagName === 'PRE' ? 'off' : 'polite');
      el.setAttribute('aria-atomic', 'true');
    }));
  }

  function enhanceGraphics(root = document) {
    root.querySelectorAll('canvas, svg[id], .plot-container').forEach(el => {
      if (el.getAttribute('role')) return;
      const heading = el.closest('.card, .hil-panel, .re-section')?.querySelector('h1, h2, h3, h4')?.textContent;
      el.setAttribute('role', 'img');
      el.setAttribute('aria-label', normalise(heading) || normalise(el.id) || 'Data visualization');
    });
  }

  function enhance(root = document) {
    labelControls(root);
    enhanceTabs(root);
    enhanceDialogs(root);
    enhanceStatus(root);
    enhanceGraphics(root);
  }

  function start() {
    enhance();
    let scheduled = false;
    new MutationObserver(mutations => {
      if (!mutations.some(m => m.addedNodes.length)) return;
      if (scheduled) return;
      scheduled = true;
      requestAnimationFrame(() => { scheduled = false; enhance(); });
    }).observe(document.body, {subtree: true, childList: true});
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', start, {once: true});
  else start();
})();
