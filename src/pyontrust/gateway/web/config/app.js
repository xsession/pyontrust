(() => {
  'use strict';

  const categories = ['profiles', 'benches', 'limits'];
  const state = {category: 'profiles', files: {}, selected: '', original: '', creating: false, dirty: false};
  const list = document.getElementById('config-list');
  const editor = document.getElementById('json-editor');
  const nameInput = document.getElementById('config-name');
  const message = document.getElementById('app-message');
  const editorState = document.getElementById('editor-state');
  const editorEmpty = document.getElementById('editor-empty');
  const editorContent = document.getElementById('editor-content');
  const confirmDialog = document.getElementById('confirm-dialog');

  categories.forEach(category => { state.files[category] = []; });

  function setMessage(text = '', type = '') {
    message.textContent = text;
    message.className = `ui-message${type ? ` is-${type}` : ''}`;
  }

  async function api(path, options = {}) {
    const headers = {'Accept': 'application/json', ...(options.headers || {})};
    const response = await fetch(path, {...options, headers});
    let body = null;
    try { body = await response.json(); } catch { body = null; }
    if (!response.ok) throw new Error(body?.error || `Request failed (${response.status})`);
    return body;
  }

  function baseName(value) {
    return String(value || '').trim().replace(/\.json$/i, '').replace(/[^a-zA-Z0-9_.-]+/g, '_').replace(/^\.+/, '');
  }

  function formatSize(bytes) {
    const value = Number(bytes) || 0;
    return value < 1024 ? `${value} B` : `${(value / 1024).toFixed(1)} KB`;
  }

  function formatDate(timestamp) {
    const numeric = Number(timestamp);
    if (!Number.isFinite(numeric) || numeric <= 0) return 'Unknown';
    return new Intl.DateTimeFormat(undefined, {dateStyle: 'medium'}).format(new Date(numeric * 1000));
  }

  function normaliseFile(file) {
    if (typeof file === 'string') return {name: file, size: 0, mtime: 0};
    return {
      name: String(file?.name || ''),
      size: Number(file?.size) || 0,
      mtime: Number(file?.mtime) || 0,
    };
  }

  function activeFiles() {
    const query = document.getElementById('config-search').value.trim().toLowerCase();
    return state.files[state.category].filter(file => !query || file.name.toLowerCase().includes(query));
  }

  function renderCounts() {
    categories.forEach(category => {
      document.getElementById(`${category}-count`).textContent = state.files[category].length;
    });
  }

  function renderList() {
    list.replaceChildren();
    list.setAttribute('aria-busy', 'false');
    const files = activeFiles();
    if (!files.length) {
      const hasAny = state.files[state.category].length > 0;
      list.innerHTML = `<div class="empty-state"><div><strong>${hasAny ? 'No matching files' : 'No configurations yet'}</strong><p>${hasAny ? 'Clear or change the filter.' : 'Create the first configuration in this category.'}</p></div></div>`;
      return;
    }
    files.forEach(file => {
      const button = document.createElement('button');
      button.type = 'button';
      button.className = `config-item${file.name === state.selected ? ' active' : ''}`;
      button.setAttribute('aria-pressed', file.name === state.selected ? 'true' : 'false');
      const copy = document.createElement('span');
      const title = document.createElement('strong');
      title.textContent = file.name;
      const meta = document.createElement('small');
      meta.textContent = formatSize(file.size);
      copy.append(title, meta);
      const time = document.createElement('time');
      if (file.mtime > 0) time.dateTime = new Date(file.mtime * 1000).toISOString();
      time.textContent = formatDate(file.mtime);
      button.append(copy, time);
      button.addEventListener('click', () => openFile(file.name));
      list.append(button);
    });
  }

  async function loadCategory(category, {announce = false} = {}) {
    list.setAttribute('aria-busy', 'true');
    list.innerHTML = '<div class="skeleton"></div><div class="skeleton"></div><div class="skeleton"></div>';
    try {
      const files = await api(`/config/api/${category}`);
      state.files[category] = Array.isArray(files)
        ? files.map(normaliseFile).filter(file => file.name)
        : [];
      renderCounts();
      if (state.category === category) renderList();
      if (announce) setMessage(`Loaded ${state.files[category].length} ${category} configuration${state.files[category].length === 1 ? '' : 's'}.`, 'success');
    } catch (error) {
      state.files[category] = [];
      renderCounts();
      if (state.category === category) {
        list.setAttribute('aria-busy', 'false');
        list.innerHTML = `<div class="empty-state"><div><strong>Configuration unavailable</strong><p>${escapeText(error.message)}</p></div></div>`;
      }
      setMessage(error.message, 'error');
    }
  }

  function escapeText(text) {
    const div = document.createElement('div');
    div.textContent = String(text || '');
    return div.innerHTML;
  }

  async function switchCategory(category) {
    if (!categories.includes(category) || category === state.category) return;
    if (!confirmDiscard()) return;
    state.category = category;
    state.selected = '';
    state.creating = false;
    clearEditor();
    document.querySelectorAll('.category-tab').forEach(tab => {
      const active = tab.dataset.category === category;
      tab.classList.toggle('active', active);
      if (active) tab.setAttribute('aria-current', 'page');
      else tab.removeAttribute('aria-current');
    });
    renderList();
    if (!state.files[category].length) await loadCategory(category);
  }

  function clearEditor() {
    editorEmpty.hidden = false;
    editorContent.hidden = true;
    state.original = '';
    state.dirty = false;
  }

  async function openFile(filename) {
    if (filename === state.selected && !state.creating) return;
    if (!confirmDiscard()) return;
    state.selected = filename;
    state.creating = false;
    renderList();
    editorEmpty.hidden = true;
    editorContent.hidden = false;
    nameInput.value = filename.replace(/\.json$/i, '');
    nameInput.disabled = true;
    editor.value = 'Loading…';
    editor.disabled = true;
    setMessage(`Loading ${filename}…`);
    try {
      const data = await api(`/config/api/${state.category}/${encodeURIComponent(filename)}`);
      const text = JSON.stringify(data, null, 2);
      editor.value = text;
      editor.disabled = false;
      state.original = text;
      state.dirty = false;
      updateEditorState();
      setMessage(`Loaded ${filename}.`, 'success');
    } catch (error) {
      clearEditor();
      state.selected = '';
      renderList();
      setMessage(error.message, 'error');
    }
  }

  function startNew() {
    if (!confirmDiscard()) return;
    state.selected = '';
    state.creating = true;
    renderList();
    editorEmpty.hidden = true;
    editorContent.hidden = false;
    nameInput.disabled = false;
    const singular = state.category === 'profiles' ? 'profile' : state.category === 'benches' ? 'bench' : 'limits';
    nameInput.value = `new_${singular}`;
    editor.disabled = false;
    editor.value = '{\n  \n}';
    state.original = '';
    state.dirty = true;
    updateEditorState();
    nameInput.focus();
    nameInput.select();
    setMessage(`Creating a new ${singular} configuration.`);
  }

  function confirmDiscard() {
    return !state.dirty || window.confirm('Discard unsaved configuration changes?');
  }

  function parseEditor() {
    let data;
    try { data = JSON.parse(editor.value); }
    catch (error) { throw new Error(`Invalid JSON: ${error.message}`); }
    if (!data || Array.isArray(data) || typeof data !== 'object') throw new Error('The top-level JSON value must be an object.');
    return data;
  }

  function updateEditorState() {
    const lines = editor.value.split('\n').length;
    const bytes = new Blob([editor.value]).size;
    document.getElementById('editor-stats').textContent = `${lines} line${lines === 1 ? '' : 's'} · ${bytes.toLocaleString()} bytes`;
    state.dirty = state.creating || editor.value !== state.original;
    editorState.className = `editor-state${state.dirty ? ' is-dirty' : ''}`;
    editorState.textContent = state.dirty ? 'Unsaved changes' : 'Saved';
    try {
      parseEditor();
      editor.setAttribute('aria-invalid', 'false');
      if (!state.dirty) editorState.className = 'editor-state is-valid';
    } catch {
      editor.setAttribute('aria-invalid', 'true');
      editorState.className = 'editor-state is-invalid';
      editorState.textContent = 'Invalid JSON';
    }
  }

  async function save() {
    let data;
    try { data = parseEditor(); }
    catch (error) { setMessage(error.message, 'error'); editor.focus(); return; }
    const name = baseName(nameInput.value);
    if (!name) { setMessage('Enter a valid file name.', 'error'); nameInput.focus(); return; }
    const filename = `${name}.json`;
    if (state.creating && state.files[state.category].some(file => file.name.toLowerCase() === filename.toLowerCase())) {
      setMessage(`${filename} already exists. Choose another name.`, 'error');
      nameInput.focus();
      return;
    }
    const button = document.getElementById('save-button');
    button.disabled = true;
    setMessage(`Saving ${filename}…`);
    try {
      const result = await api(`/config/api/${state.category}/${encodeURIComponent(filename)}`, {
        method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(data),
      });
      state.selected = result.name || filename;
      state.creating = false;
      nameInput.value = state.selected.replace(/\.json$/i, '');
      nameInput.disabled = true;
      editor.value = JSON.stringify(data, null, 2);
      state.original = editor.value;
      state.dirty = false;
      await loadCategory(state.category);
      updateEditorState();
      setMessage(`Saved ${state.selected}.`, 'success');
    } catch (error) { setMessage(error.message, 'error'); }
    finally { button.disabled = false; }
  }

  function formatJson() {
    try {
      editor.value = JSON.stringify(parseEditor(), null, 2);
      updateEditorState();
      setMessage('JSON formatted.', 'success');
    } catch (error) { setMessage(error.message, 'error'); editor.focus(); }
  }

  async function deleteSelected() {
    if (!state.selected || state.creating) return;
    const filename = state.selected;
    setMessage(`Deleting ${filename}…`);
    try {
      const result = await api(`/config/api/${state.category}/${encodeURIComponent(filename)}`, {method: 'DELETE'});
      if (!result.deleted) throw new Error('The configuration could not be deleted.');
      state.selected = '';
      clearEditor();
      await loadCategory(state.category);
      setMessage(`Deleted ${filename}.`, 'success');
    } catch (error) { setMessage(error.message, 'error'); }
  }

  document.querySelectorAll('.category-tab').forEach(tab => tab.addEventListener('click', () => switchCategory(tab.dataset.category)));
  document.getElementById('config-search').addEventListener('input', renderList);
  document.getElementById('refresh-button').addEventListener('click', () => loadCategory(state.category, {announce: true}));
  document.getElementById('new-button').addEventListener('click', startNew);
  document.getElementById('save-button').addEventListener('click', save);
  document.getElementById('format-button').addEventListener('click', formatJson);
  document.getElementById('delete-button').addEventListener('click', () => {
    if (state.creating) { clearEditor(); return; }
    if (!state.selected) return;
    document.getElementById('confirm-name').textContent = state.selected;
    if (typeof confirmDialog.showModal === 'function') confirmDialog.showModal();
    else if (window.confirm(`Delete ${state.selected}?`)) deleteSelected();
  });
  confirmDialog.addEventListener('close', () => { if (confirmDialog.returnValue === 'confirm') deleteSelected(); });
  editor.addEventListener('input', updateEditorState);
  nameInput.addEventListener('input', updateEditorState);
  editor.addEventListener('keydown', event => {
    if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 's') { event.preventDefault(); save(); return; }
    if (event.key === 'Tab') {
      event.preventDefault();
      const start = editor.selectionStart;
      editor.setRangeText('  ', start, editor.selectionEnd, 'end');
      updateEditorState();
    }
  });
  window.addEventListener('beforeunload', event => {
    if (!state.dirty) return;
    event.preventDefault();
    event.returnValue = '';
  });

  Promise.all(categories.map(category => loadCategory(category))).then(() => renderList());
})();
