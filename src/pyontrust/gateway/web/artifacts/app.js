/* Artifacts — search-first artifact browser. */
(() => {
  'use strict';

  const list = document.getElementById('artifact-list');
  const statusLine = document.getElementById('status-line');
  const searchInput = document.getElementById('artifact-search');
  const scanButton = document.getElementById('scan-button');
  const refreshButton = document.getElementById('refresh-button');

  let controller = null;
  let debounceTimer = null;

  function announce(message, isError = false) {
    statusLine.hidden = !message;
    statusLine.textContent = message || '';
    statusLine.classList.toggle('is-error', !!isError);
  }

  function formatSize(bytes) {
    if (bytes == null) return '';
    const units = ['B', 'KB', 'MB', 'GB'];
    let value = Number(bytes), unit = 0;
    while (value >= 1024 && unit < units.length - 1) { value /= 1024; unit += 1; }
    return `${value.toFixed(value >= 10 || unit === 0 ? 0 : 1)} ${units[unit]}`;
  }

  function formatTime(ts) {
    if (!ts) return '';
    const date = new Date(ts * 1000);
    if (Number.isNaN(date.getTime())) return '';
    return date.toLocaleString(undefined, { year: 'numeric', month: 'short', day: '2-digit', hour: '2-digit', minute: '2-digit' });
  }

  function renderEmpty({ hasQuery }) {
    list.replaceChildren();
    const wrap = document.createElement('div');
    wrap.className = 'empty-state';
    const title = document.createElement('strong');
    title.textContent = hasQuery ? `No artifacts match “${searchInput.value.trim()}”` : 'No artifacts yet';
    const hint = document.createElement('p');
    hint.textContent = hasQuery
      ? 'Try a shorter query, or clear the search to see all runs.'
      : 'Run a test with pyontrust, then use “Scan directory” to index its output here.';
    wrap.append(title, hint);
    list.append(wrap);
  }

  function renderEntries(entries) {
    list.replaceChildren();
    if (!entries.length) { renderEmpty({ hasQuery: !!searchInput.value.trim() }); return; }

    for (const entry of entries) {
      const item = document.createElement('article');
      item.className = 'artifact-item';
      item.dataset.runId = entry.run_id;

      const head = document.createElement('div');
      head.className = 'artifact-head';
      const name = document.createElement('span');
      name.className = 'artifact-name';
      name.textContent = entry.test_name || entry.run_id;
      const runid = document.createElement('code');
      runid.className = 'artifact-runid';
      runid.textContent = entry.run_id;
      const time = document.createElement('time');
      time.className = 'artifact-time';
      if (entry.created) {
        time.dateTime = new Date(entry.created * 1000).toISOString();
        time.title = formatTime(entry.created);
        time.textContent = formatTime(entry.created);
      }
      head.append(name, runid, time);

      const badges = document.createElement('div');
      badges.className = 'badges';
      for (const [key, label] of [['has_trace', 'trace'], ['has_summary', 'summary'], ['has_report', 'report'], ['has_verdict', 'verdict']]) {
        const badge = document.createElement('span');
        badge.className = 'badge' + (entry[key] ? ' is-on' : '');
        badge.textContent = label;
        badges.append(badge);
      }

      const actions = document.createElement('div');
      actions.className = 'artifact-actions';
      const filesButton = document.createElement('button');
      filesButton.type = 'button';
      filesButton.className = 'btn';
      filesButton.textContent = 'Files';
      filesButton.setAttribute('aria-expanded', 'false');
      const deleteButton = document.createElement('button');
      deleteButton.type = 'button';
      deleteButton.className = 'btn btn-danger';
      deleteButton.textContent = 'Delete';

      actions.append(filesButton, deleteButton);
      item.append(head, badges, actions);
      list.append(item);

      let filePanel = null;
      filesButton.addEventListener('click', async () => {
        const expanded = filesButton.getAttribute('aria-expanded') === 'true';
        if (expanded) { filesButton.setAttribute('aria-expanded', 'false'); if (filePanel) filePanel.remove(); filePanel = null; return; }
        if (!filePanel) {
          filePanel = document.createElement('div');
          filePanel.className = 'file-list';
          filePanel.textContent = 'Loading…';
          item.append(filePanel);
          try {
            const res = await fetch(`/artifacts/api/${encodeURIComponent(entry.run_id)}/files`);
            if (!res.ok) throw new Error(`HTTP ${res.status}`);
            const files = await res.json();
            filePanel.replaceChildren();
            if (!Array.isArray(files) || !files.length) {
              filePanel.textContent = 'No files in this run.';
              return;
            }
            for (const file of files) {
              const row = document.createElement('div');
              row.className = 'file-row';
              const fname = document.createElement('span');
              fname.className = 'file-name';
              fname.textContent = file.name;
              const fsize = document.createElement('span');
              fsize.className = 'file-size';
              fsize.textContent = formatSize(file.size);
              const link = document.createElement('a');
              link.href = `/artifacts/api/${encodeURIComponent(entry.run_id)}/file/${encodeURIComponent(file.name)}`;
              link.download = file.name.split('/').pop();
              link.textContent = 'Download';
              row.append(fname, fsize, link);
              filePanel.append(row);
            }
          } catch (err) {
            filePanel.replaceChildren();
            filePanel.textContent = `Could not load files (${err.message}).`;
          }
        } else {
          filePanel.hidden = false;
        }
        filesButton.setAttribute('aria-expanded', 'true');
      });

      deleteButton.addEventListener('click', async () => {
        if (!window.confirm(`Delete artifact “${entry.test_name || entry.run_id}” (${entry.run_id})? This removes its files.`)) return;
        try {
          const res = await fetch(`/artifacts/api/${encodeURIComponent(entry.run_id)}`, { method: 'DELETE' });
          if (!res.ok && res.status !== 204) throw new Error(`HTTP ${res.status}`);
          announce(`Deleted ${entry.run_id}.`);
          load();
        } catch (err) {
          announce(`Delete failed: ${err.message}`, true);
        }
      });
    }
  }

  async function load() {
    if (controller) controller.abort();
    controller = new AbortController();
    list.setAttribute('aria-busy', 'true');
    const query = searchInput.value.trim();
    try {
      const url = `/artifacts/api/list?limit=200${query ? `&q=${encodeURIComponent(query)}` : ''}`;
      const res = await fetch(url, { signal: controller.signal });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      renderEntries(Array.isArray(data) ? data : (data.entries || []));
    } catch (err) {
      if (err.name === 'AbortError') return;
      list.replaceChildren();
      announce(`Could not load artifacts: ${err.message}`, true);
    } finally {
      if (!controller || controller.signal.aborted) return;
      list.setAttribute('aria-busy', 'false');
    }
  }

  searchInput.addEventListener('input', () => {
    clearTimeout(debounceTimer);
    debounceTimer = setTimeout(load, 250);
  });

  refreshButton.addEventListener('click', load);

  scanButton.addEventListener('click', async () => {
    scanButton.disabled = true;
    announce('Scanning artifact directory…');
    try {
      const res = await fetch('/artifacts/api/scan', { method: 'POST' });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json().catch(() => ({}));
      announce(data.indexed != null ? `Scan complete — indexed ${data.indexed} artifact(s).` : 'Scan complete.');
      load();
    } catch (err) {
      announce(`Scan failed: ${err.message}`, true);
    } finally {
      scanButton.disabled = false;
    }
  });

  load();
})();
