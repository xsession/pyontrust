/** pyontrust app shell: responsive navigation, deep-linking, bench activity.
 *  Nav entries are rendered server-side from pyontrust.gateway.tools. */
(() => {
  'use strict';

  const frame = document.getElementById('tool-frame');
  const links = [...document.querySelectorAll('.tool-nav a[data-tool]')];
  const title = document.getElementById('workspace-title');
  const description = document.getElementById('workspace-description');
  const openTool = document.getElementById('open-tool');
  const loading = document.getElementById('frame-loading');
  const menuButton = document.getElementById('menu-button');
  const closeButton = document.getElementById('sidebar-close');
  const backdrop = document.getElementById('sidebar-backdrop');
  const reloadButton = document.getElementById('reload-tool');
  const status = document.getElementById('platform-status');
  const statusLabel = document.getElementById('status-label');
  const statusDetail = document.getElementById('status-detail');
  let activeTool = 'diag';
  let loadTimer = 0;

  const linkFor = tool => links.find(link => link.dataset.tool === tool);

  function normaliseTool(value) {
    const candidate = String(value || '').replace(/^#\/?/, '').split(/[/?&]/)[0];
    return linkFor(candidate) ? candidate : 'diag';
  }

  function closeNavigation({restoreFocus = false} = {}) {
    document.body.classList.remove('nav-open');
    menuButton.setAttribute('aria-expanded', 'false');
    backdrop.hidden = true;
    if (restoreFocus) menuButton.focus();
  }

  function openNavigation() {
    backdrop.hidden = false;
    requestAnimationFrame(() => document.body.classList.add('nav-open'));
    menuButton.setAttribute('aria-expanded', 'true');
    requestAnimationFrame(() => linkFor(activeTool)?.focus());
  }

  function setLoading(label) {
    clearTimeout(loadTimer);
    loading.querySelector('span:last-child').textContent = `Loading ${label}…`;
    loading.classList.add('is-visible');
    loadTimer = window.setTimeout(() => loading.classList.remove('is-visible'), 7000);
  }

  function selectTool(tool, {updateHistory = true, forceReload = false} = {}) {
    const safeTool = normaliseTool(tool);
    const link = linkFor(safeTool);
    if (!link) return;

    activeTool = safeTool;
    links.forEach(item => {
      const active = item === link;
      item.classList.toggle('active', active);
      if (active) item.setAttribute('aria-current', 'page');
      else item.removeAttribute('aria-current');
    });

    const label = link.dataset.title || link.textContent.trim();
    const detail = link.dataset.description || '';
    title.textContent = label;
    description.textContent = detail;
    frame.title = label;
    openTool.href = link.getAttribute('href');
    document.title = `pyontrust — ${label}`;

    const target = link.getAttribute('href');
    const currentPath = (() => {
      try { return new URL(frame.src, location.href).pathname; }
      catch { return ''; }
    })();
    if (forceReload || currentPath !== target) {
      setLoading(label);
      frame.src = target;
    }

    if (updateHistory && location.hash !== `#${safeTool}`) {
      history.pushState({tool: safeTool}, '', `#${safeTool}`);
    }
    if (matchMedia('(max-width: 820px)').matches) closeNavigation();
  }

  links.forEach(link => link.addEventListener('click', event => {
    if (event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return;
    event.preventDefault();
    selectTool(link.dataset.tool);
  }));

  menuButton.addEventListener('click', () => {
    if (document.body.classList.contains('nav-open')) closeNavigation({restoreFocus: true});
    else openNavigation();
  });
  closeButton.addEventListener('click', () => closeNavigation({restoreFocus: true}));
  backdrop.addEventListener('click', () => closeNavigation({restoreFocus: true}));
  document.addEventListener('keydown', event => {
    if (event.key === 'Escape' && document.body.classList.contains('nav-open')) closeNavigation({restoreFocus: true});
  });
  window.addEventListener('resize', () => {
    if (!matchMedia('(max-width: 820px)').matches) closeNavigation();
  });

  reloadButton.addEventListener('click', () => selectTool(activeTool, {updateHistory: false, forceReload: true}));
  frame.addEventListener('load', () => {
    clearTimeout(loadTimer);
    loading.classList.remove('is-visible');
  });
  window.addEventListener('hashchange', () => selectTool(location.hash, {updateHistory: false}));
  window.addEventListener('popstate', event => selectTool(event.state?.tool || location.hash, {updateHistory: false}));

  // Bench-wide activity: one endpoint reports every busy tool (registry-driven).
  async function pollStatus() {
    const controller = new AbortController();
    const timeout = window.setTimeout(() => controller.abort(), 4000);
    try {
      const response = await fetch('/api/activity', {headers: {'Accept': 'application/json'}, signal: controller.signal});
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const payload = await response.json();
      const busy = payload.activity || {};
      const session = payload.session || {};
      const chip = document.getElementById('session-chip');
      if (chip) {
        const parts = [session.operator ? `👤 ${session.operator}` : '👤 Set operator',
                       session.dut ? `🔖 ${session.dut}` : ''].filter(Boolean);
        chip.textContent = parts.join('  ·  ');
        chip.classList.toggle('unset', !session.operator);
        chip.title = `Station ${session.station || ''} — operator and DUT are recorded with every action. Click to change.`;
      }
      links.forEach(link => {
        const entry = busy[link.dataset.tool];
        if (entry) { link.dataset.activity = entry.state; link.title = entry.label; }
        else { delete link.dataset.activity; link.removeAttribute('title'); }
      });
      const entries = Object.entries(busy);
      const errors = entries.filter(([, e]) => e.state === 'error');
      status.dataset.state = errors.length ? 'error' : entries.length ? 'running' : 'idle';
      statusLabel.textContent = errors.length ? 'Attention needed'
        : entries.length ? `${entries.length} task${entries.length > 1 ? 's' : ''} running` : 'Bench idle';
      statusDetail.textContent = entries.length ? entries.map(([, e]) => e.label).join(' · ') : 'No measurement, capture or run active';
    } catch (error) {
      status.dataset.state = 'offline';
      statusLabel.textContent = 'Gateway unavailable';
      statusDetail.textContent = error.name === 'AbortError' ? 'Status request timed out' : 'Activity could not be read';
    } finally {
      clearTimeout(timeout);
    }
  }

  const initial = normaliseTool(location.hash);
  history.replaceState({tool: initial}, '', `#${initial}`);
  selectTool(initial, {updateHistory: false});
  pollStatus();
  window.setInterval(pollStatus, 3000);
})();
