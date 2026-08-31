/** pyontrust app shell: responsive navigation, deep-linking, and platform status. */
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

  async function pollStatus() {
    const controller = new AbortController();
    const timeout = window.setTimeout(() => controller.abort(), 4000);
    try {
      const response = await fetch('/hil/api/status', {headers: {'Accept': 'application/json'}, signal: controller.signal});
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const data = await response.json();
      const state = String(data.state || 'idle').toLowerCase();
      status.dataset.state = state;
      statusLabel.textContent = state === 'running' ? 'HIL run active'
        : state === 'stopping' ? 'HIL run stopping'
        : state === 'error' ? 'HIL run error'
        : 'HIL ready';
      const profile = data.profile || data.current_profile || '';
      statusDetail.textContent = profile ? `${state} · ${profile}` : state;
    } catch (error) {
      status.dataset.state = 'offline';
      statusLabel.textContent = 'Gateway unavailable';
      statusDetail.textContent = error.name === 'AbortError' ? 'Status request timed out' : 'HIL status could not be read';
    } finally {
      clearTimeout(timeout);
    }
  }

  const initial = normaliseTool(location.hash);
  history.replaceState({tool: initial}, '', `#${initial}`);
  selectTool(initial, {updateHistory: false});
  pollStatus();
  window.setInterval(pollStatus, 5000);
})();
