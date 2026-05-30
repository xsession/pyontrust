const state = {
  appState: null,
  browser: null,
  roots: [],
  controlSync: false,
};

const els = {
  filePathInput: document.getElementById("file-path-input"),
  folderPathInput: document.getElementById("folder-path-input"),
  loadFileBtn: document.getElementById("load-file-btn"),
  loadFolderBtn: document.getElementById("load-folder-btn"),
  reloadBtn: document.getElementById("reload-btn"),
  saveLayoutBtn: document.getElementById("save-layout-btn"),
  loadLayoutBtn: document.getElementById("load-layout-btn"),
  datasetPill: document.getElementById("dataset-pill"),
  rootsSelect: document.getElementById("roots-select"),
  openRootBtn: document.getElementById("open-root-btn"),
  browserPathInput: document.getElementById("browser-path-input"),
  browsePathBtn: document.getElementById("browse-path-btn"),
  browseUpBtn: document.getElementById("browse-up-btn"),
  foldersList: document.getElementById("folders-list"),
  filesList: document.getElementById("files-list"),
  addSubplotBtn: document.getElementById("add-subplot-btn"),
  deleteSubplotBtn: document.getElementById("delete-subplot-btn"),
  subplotTabs: document.getElementById("subplot-tabs"),
  activeTitle: document.getElementById("active-title"),
  renderImage: document.getElementById("render-image"),
  renderPlaceholder: document.getElementById("render-placeholder"),
  detailsContent: document.getElementById("details-content"),
  messageBar: document.getElementById("message-bar"),
  exportDataFormat: document.getElementById("export-data-format"),
  exportDataBtn: document.getElementById("export-data-btn"),
  exportCurrentBtn: document.getElementById("export-current-btn"),
  exportCombinedBtn: document.getElementById("export-combined-btn"),
  titleInput: document.getElementById("title-input"),
  modeSelect: document.getElementById("mode-select"),
  signalsSelect: document.getElementById("signals-select"),
  xMinInput: document.getElementById("x-min-input"),
  xMaxInput: document.getElementById("x-max-input"),
  yMinInput: document.getElementById("y-min-input"),
  yMaxInput: document.getElementById("y-max-input"),
  xAlignSelect: document.getElementById("x-align-select"),
  showTriggersInput: document.getElementById("show-triggers-input"),
  histogramBinsInput: document.getElementById("histogram-bins-input"),
  spectrumCutoffInput: document.getElementById("spectrum-cutoff-input"),
  absEnabledInput: document.getElementById("abs-enabled-input"),
  absTargetInput: document.getElementById("abs-target-input"),
  absLimitInInput: document.getElementById("abs-limit-in-input"),
  absLimitOutInput: document.getElementById("abs-limit-out-input"),
  absStartInput: document.getElementById("abs-start-input"),
  absEndInput: document.getElementById("abs-end-input"),
  relEnabledInput: document.getElementById("rel-enabled-input"),
  relTargetInput: document.getElementById("rel-target-input"),
  relLimitInInput: document.getElementById("rel-limit-in-input"),
  relLimitOutInput: document.getElementById("rel-limit-out-input"),
  relStartInput: document.getElementById("rel-start-input"),
  relEndInput: document.getElementById("rel-end-input"),
  customCodeInput: document.getElementById("custom-code-input"),
  detectorRowsInput: document.getElementById("detector-rows-input"),
  detectorColsInput: document.getElementById("detector-cols-input"),
  detectorMappingInput: document.getElementById("detector-mapping-input"),
  detectorReducerInput: document.getElementById("detector-reducer-input"),
  detectorMapInput: document.getElementById("detector-map-input"),
  overlayPathInput: document.getElementById("overlay-path-input"),
  addOverlayBtn: document.getElementById("add-overlay-btn"),
  overlayList: document.getElementById("overlay-list"),
};

function setMessage(message, isError = false) {
  els.messageBar.textContent = message || "";
  els.messageBar.style.color = isError ? "#b42318" : "var(--accent-2)";
}

async function api(url, options = {}) {
  const requestOptions = { ...options };
  requestOptions.headers = { ...(options.headers || {}) };
  if (requestOptions.body && typeof requestOptions.body !== "string") {
    requestOptions.headers["Content-Type"] = "application/json";
    requestOptions.body = JSON.stringify(requestOptions.body);
  }
  const response = await fetch(url, requestOptions);
  const contentType = response.headers.get("content-type") || "";
  const payload = contentType.includes("application/json") ? await response.json() : await response.text();
  if (!response.ok) {
    const error = typeof payload === "string" ? payload : payload.error || JSON.stringify(payload);
    throw new Error(error);
  }
  return payload;
}

function getActiveSubplot() {
  const subplots = state.appState?.subplots || [];
  return subplots.find((item) => item.id === state.appState?.active_subplot_id) || subplots[0] || null;
}

function parseOptionalNumber(value) {
  if (value === "" || value === null || value === undefined) {
    return null;
  }
  const numeric = Number(value);
  return Number.isFinite(numeric) ? numeric : null;
}

function collectSubplotPatch() {
  return {
    title: els.titleInput.value.trim() || "Plot",
    mode: els.modeSelect.value,
    selected_columns: Array.from(els.signalsSelect.selectedOptions).map((option) => option.value),
    x_window: [parseOptionalNumber(els.xMinInput.value), parseOptionalNumber(els.xMaxInput.value)].every((item) => item !== null)
      ? [Number(els.xMinInput.value), Number(els.xMaxInput.value)]
      : null,
    y_limits: [parseOptionalNumber(els.yMinInput.value), parseOptionalNumber(els.yMaxInput.value)],
    x_align: els.xAlignSelect.value,
    show_trigger_markers: els.showTriggersInput.checked,
    histogram_bins: Number(els.histogramBinsInput.value || 30),
    spectrum_baseline_cutoff: parseOptionalNumber(els.spectrumCutoffInput.value),
    barrier_config: {
      abs: {
        enabled: els.absEnabledInput.checked,
        target: Number(els.absTargetInput.value || 0),
        limit_in: Number(els.absLimitInInput.value || 0),
        limit_out: Number(els.absLimitOutInput.value || 0),
        start_idx: Number(els.absStartInput.value || 0),
        end_idx: Number(els.absEndInput.value || 0),
      },
      rel: {
        enabled: els.relEnabledInput.checked,
        target: Number(els.relTargetInput.value || 0),
        limit_in: Number(els.relLimitInInput.value || 0),
        limit_out: Number(els.relLimitOutInput.value || 0),
        start_idx: Number(els.relStartInput.value || 0),
        end_idx: Number(els.relEndInput.value || 0),
      },
    },
    custom_code: els.customCodeInput.value,
    detector_config: {
      rows: Number(els.detectorRowsInput.value || 4),
      cols: Number(els.detectorColsInput.value || 4),
      mapping: els.detectorMappingInput.value,
      reducer: els.detectorReducerInput.value,
      signal_map: els.detectorMapInput.value,
    },
  };
}

async function refreshAppState() {
  state.appState = await api("/csv/api/app-state");
  renderAppState();
  await refreshDetails();
}

function renderAppState() {
  const appState = state.appState;
  const active = getActiveSubplot();

  els.datasetPill.textContent = appState?.path ? `${appState.path} · ${appState.rows} rows` : "No file loaded";
  els.filePathInput.value = appState?.path || els.filePathInput.value;
  els.folderPathInput.value = appState?.folder || els.folderPathInput.value;
  els.activeTitle.textContent = active?.title || "Plot";

  renderModeOptions(appState?.modes || []);
  renderSignalOptions(appState?.columns || [], active?.selected_columns || []);
  renderSubplots(appState?.subplots || [], appState?.active_subplot_id);
  renderControls(active);
  renderOverlays(active?.overlays || []);
  updateRenderImage(active);
}

function renderModeOptions(modes) {
  if (els.modeSelect.options.length === modes.length) {
    return;
  }
  els.modeSelect.innerHTML = modes.map((mode) => `<option value="${mode}">${mode}</option>`).join("");
}

function renderSignalOptions(columns, selected) {
  els.signalsSelect.innerHTML = columns
    .filter((column) => column !== "Timestamp")
    .map((column) => `<option value="${column}">${column}</option>`)
    .join("");
  Array.from(els.signalsSelect.options).forEach((option) => {
    option.selected = selected.includes(option.value);
  });
}

function renderSubplots(subplots, activeId) {
  els.subplotTabs.innerHTML = subplots
    .map(
      (subplot) => `
        <button class="subplot-tab ${subplot.id === activeId ? "active" : ""}" type="button" data-subplot-id="${subplot.id}">
          <strong>${subplot.title}</strong>
          <div class="subplot-mode">${subplot.mode}</div>
        </button>
      `
    )
    .join("");
}

function renderControls(active) {
  state.controlSync = true;
  els.titleInput.value = active?.title || "";
  els.modeSelect.value = active?.mode || "Time series";
  els.xMinInput.value = active?.x_window?.[0] ?? "";
  els.xMaxInput.value = active?.x_window?.[1] ?? "";
  els.yMinInput.value = active?.y_limits?.[0] ?? "";
  els.yMaxInput.value = active?.y_limits?.[1] ?? "";
  els.xAlignSelect.value = active?.x_align || "aligned";
  els.showTriggersInput.checked = Boolean(active?.show_trigger_markers ?? true);
  els.histogramBinsInput.value = active?.histogram_bins ?? 30;
  els.spectrumCutoffInput.value = active?.spectrum_baseline_cutoff ?? "";

  const abs = active?.barrier_config?.abs || {};
  const rel = active?.barrier_config?.rel || {};
  els.absEnabledInput.checked = Boolean(abs.enabled);
  els.absTargetInput.value = abs.target ?? 0;
  els.absLimitInInput.value = abs.limit_in ?? 0;
  els.absLimitOutInput.value = abs.limit_out ?? 0;
  els.absStartInput.value = abs.start_idx ?? 0;
  els.absEndInput.value = abs.end_idx ?? 0;
  els.relEnabledInput.checked = Boolean(rel.enabled);
  els.relTargetInput.value = rel.target ?? 0;
  els.relLimitInInput.value = rel.limit_in ?? 0;
  els.relLimitOutInput.value = rel.limit_out ?? 0;
  els.relStartInput.value = rel.start_idx ?? 0;
  els.relEndInput.value = rel.end_idx ?? 0;

  els.customCodeInput.value = active?.custom_code || "";
  const detector = active?.detector_config || {};
  els.detectorRowsInput.value = detector.rows ?? 4;
  els.detectorColsInput.value = detector.cols ?? 4;
  els.detectorMappingInput.value = detector.mapping ?? "Row-major";
  els.detectorReducerInput.value = detector.reducer ?? "Mean";
  els.detectorMapInput.value = detector.signal_map ?? "";
  state.controlSync = false;
}

function renderOverlays(overlays) {
  if (!overlays.length) {
    els.overlayList.innerHTML = '<div class="overlay-item"><div class="overlay-meta">No overlays configured for the active subplot.</div></div>';
    return;
  }
  els.overlayList.innerHTML = overlays
    .map(
      (overlay) => `
        <div class="overlay-item" data-overlay-index="${overlay.index}">
          <header>
            <strong>${overlay.label}</strong>
            <button type="button" data-action="remove-overlay">Remove</button>
          </header>
          <div class="overlay-meta">${overlay.path}</div>
          <div class="form-grid compact">
            <label class="toggle-row"><span>Enabled</span><input data-field="enabled" type="checkbox" ${overlay.enabled ? "checked" : ""}></label>
            <label><span>X shift s</span><input data-field="x_shift_s" type="number" step="any" value="${overlay.x_shift_s}"></label>
            <label><span>Y shift</span><input data-field="y_shift" type="number" step="any" value="${overlay.y_shift}"></label>
          </div>
        </div>
      `
    )
    .join("");
}

function updateRenderImage(active) {
  const pathLoaded = Boolean(state.appState?.path);
  if (!pathLoaded || !active) {
    els.renderImage.style.display = "none";
    els.renderPlaceholder.style.display = "grid";
    return;
  }
  els.renderPlaceholder.style.display = "none";
  els.renderImage.style.display = "block";
  els.renderImage.src = `/csv/api/subplots/${active.id}/render?fmt=png&width=1400&height=720&t=${Date.now()}`;
}

function formatMetricValue(value) {
  if (value === null || value === undefined || value === "") {
    return "-";
  }
  if (typeof value === "number") {
    return Number.isFinite(value) ? value.toFixed(4) : "-";
  }
  return String(value);
}

async function refreshDetails() {
  const active = getActiveSubplot();
  if (!active || !state.appState?.path) {
    els.detailsContent.innerHTML = '<div class="empty-state">Plot details will appear here after a signal file is loaded.</div>';
    return;
  }

  if (active.mode === "Statistics") {
    const response = await api(`/csv/api/subplots/${active.id}/panel`);
    const rows = response.payload?.rows || [];
    els.detailsContent.innerHTML = renderStatsTable(rows);
    return;
  }

  if (active.mode === "Time series" || active.mode === "AF-10047: Control vs Module") {
    const metrics = await api("/csv/api/csv/metrics", {
      method: "POST",
      body: { subplot_id: active.id },
    });
    els.detailsContent.innerHTML = renderMetricsCards(metrics);
    return;
  }

  const response = await api(`/csv/api/subplots/${active.id}/panel`);
  els.detailsContent.innerHTML = renderPayloadDetails(response.payload || {});
}

function renderStatsTable(rows) {
  if (!rows.length) {
    return '<div class="empty-state">No statistics are available for the active selection.</div>';
  }
  const headers = ["Source", "Signal", "Min", "Max", "Avg", "Med", "P2P", "Std", "RMS", "Crest", "Freq", "Period"];
  const body = rows
    .map(
      (row) => `
        <tr>
          <td>${row.source}</td>
          <td>${row.signal}</td>
          <td>${formatMetricValue(row.min)}</td>
          <td>${formatMetricValue(row.max)}</td>
          <td>${formatMetricValue(row.avg)}</td>
          <td>${formatMetricValue(row.med)}</td>
          <td>${formatMetricValue(row.p2p)}</td>
          <td>${formatMetricValue(row.std)}</td>
          <td>${formatMetricValue(row.rms)}</td>
          <td>${formatMetricValue(row.crest)}</td>
          <td>${formatMetricValue(row.freq)}</td>
          <td>${formatMetricValue(row.period)}</td>
        </tr>
      `
    )
    .join("");
  return `
    <div class="table-wrap">
      <table class="stats-table">
        <thead><tr>${headers.map((header) => `<th>${header}</th>`).join("")}</tr></thead>
        <tbody>${body}</tbody>
      </table>
    </div>
  `;
}

function renderMetricsCards(metrics) {
  const entries = Object.entries(metrics || {}).filter(([, value]) => value);
  if (!entries.length) {
    return '<div class="empty-state">No metric data is available for the current selection.</div>';
  }
  return `<div class="kv-grid">${entries
    .map(
      ([name, value]) => `
        <div class="kv-card">
          <strong>${name}</strong>
          <div>min ${formatMetricValue(value.min)}</div>
          <div>max ${formatMetricValue(value.max)}</div>
          <div>avg ${formatMetricValue(value.avg)}</div>
          <div>std ${formatMetricValue(value.std)}</div>
          <div>freq ${formatMetricValue(value.freq)}</div>
        </div>
      `
    )
    .join("")}</div>`;
}

function renderPayloadDetails(payload) {
  if (payload.error) {
    return `<div class="kv-card"><strong>Custom code error</strong><div>${payload.error}</div></div>`;
  }
  if (payload.kind === "detector") {
    return `
      <div class="kv-grid">
        <div class="kv-card"><strong>Grid</strong><div>${payload.rows} x ${payload.cols}</div></div>
        <div class="kv-card"><strong>Reducer</strong><div>${payload.reducer}</div></div>
        <div class="kv-card"><strong>Centroids</strong><div>${(payload.centroids || []).length}</div></div>
      </div>
      <pre>${JSON.stringify(payload.matrix, null, 2)}</pre>
    `;
  }
  const seriesCount = Array.isArray(payload.series) ? payload.series.length : 0;
  const barrierCount = Array.isArray(payload.barriers) ? payload.barriers.length : 0;
  return `
    <div class="kv-grid">
      <div class="kv-card"><strong>Kind</strong><div>${payload.kind || "plot"}</div></div>
      <div class="kv-card"><strong>Series</strong><div>${seriesCount}</div></div>
      <div class="kv-card"><strong>Barriers</strong><div>${barrierCount}</div></div>
    </div>
  `;
}

async function patchActiveSubplot() {
  if (state.controlSync) {
    return;
  }
  const active = getActiveSubplot();
  if (!active) {
    return;
  }
  await api(`/csv/api/subplots/${active.id}`, {
    method: "PATCH",
    body: collectSubplotPatch(),
  });
  await refreshAppState();
}

async function browsePath(path) {
  if (!path) {
    return;
  }
  state.browser = await api(`/csv/api/folder/browse?path=${encodeURIComponent(path)}`);
  els.browserPathInput.value = state.browser.path;
  renderBrowser();
}

function renderBrowser() {
  const browser = state.browser;
  els.foldersList.innerHTML = (browser?.folders || [])
    .map((item) => `<button type="button" class="browser-item" data-folder-path="${item.path}">${item.name}</button>`)
    .join("");
  els.filesList.innerHTML = (browser?.files || [])
    .map((item) => `<button type="button" class="browser-item" data-file-path="${item.path}">${item.name}</button>`)
    .join("");
}

async function loadRoots() {
  const response = await api("/csv/api/browse/roots");
  state.roots = response.roots || [];
  els.rootsSelect.innerHTML = state.roots.map((root) => `<option value="${root.path}">${root.name}</option>`).join("");
}

async function loadFile(path) {
  await api("/csv/api/csv/load", { method: "POST", body: { path } });
  await refreshAppState();
  setMessage(`Loaded ${path}`);
}

async function loadFolder(path) {
  await api("/csv/api/csv/load-folder", { method: "POST", body: { folder: path } });
  await refreshAppState();
  setMessage(`Loaded newest supported file from ${path}`);
}

async function addOverlay() {
  const active = getActiveSubplot();
  if (!active) {
    return;
  }
  const path = els.overlayPathInput.value.trim();
  if (!path) {
    return;
  }
  await api("/csv/api/overlay/add", {
    method: "POST",
    body: { subplot_id: active.id, path },
  });
  await refreshAppState();
}

async function updateOverlay(index, field, value) {
  const active = getActiveSubplot();
  if (!active) {
    return;
  }
  await api(`/csv/api/overlay/${index}`, {
    method: "PATCH",
    body: { subplot_id: active.id, [field]: value },
  });
  await refreshAppState();
}

async function removeOverlay(index) {
  const active = getActiveSubplot();
  if (!active) {
    return;
  }
  await api(`/csv/api/overlay/${index}`, {
    method: "DELETE",
    body: { subplot_id: active.id },
  });
  await refreshAppState();
}

async function downloadBlob(url, options, fallbackName) {
  const response = await fetch(url, options);
  if (!response.ok) {
    let error = `Request failed: ${response.status}`;
    try {
      const payload = await response.json();
      error = payload.error || error;
    } catch (_unused) {
      // ignore
    }
    throw new Error(error);
  }
  const blob = await response.blob();
  const header = response.headers.get("content-disposition") || "";
  const match = /filename="([^"]+)"/.exec(header);
  const downloadName = match?.[1] || fallbackName;
  const href = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = href;
  anchor.download = downloadName;
  anchor.click();
  URL.revokeObjectURL(href);
}

function bindEvents() {
  els.loadFileBtn.addEventListener("click", async () => {
    try {
      await loadFile(els.filePathInput.value.trim());
    } catch (error) {
      setMessage(error.message, true);
    }
  });

  els.loadFolderBtn.addEventListener("click", async () => {
    try {
      await loadFolder(els.folderPathInput.value.trim());
    } catch (error) {
      setMessage(error.message, true);
    }
  });

  els.reloadBtn.addEventListener("click", async () => {
    try {
      await api("/csv/api/csv/reload", { method: "POST" });
      await refreshAppState();
      setMessage("Reloaded active file");
    } catch (error) {
      setMessage(error.message, true);
    }
  });

  els.openRootBtn.addEventListener("click", async () => {
    try {
      await browsePath(els.rootsSelect.value);
    } catch (error) {
      setMessage(error.message, true);
    }
  });

  els.browsePathBtn.addEventListener("click", async () => {
    try {
      await browsePath(els.browserPathInput.value.trim());
    } catch (error) {
      setMessage(error.message, true);
    }
  });

  els.browseUpBtn.addEventListener("click", async () => {
    if (!state.browser?.parent) {
      return;
    }
    try {
      await browsePath(state.browser.parent);
    } catch (error) {
      setMessage(error.message, true);
    }
  });

  els.foldersList.addEventListener("click", async (event) => {
    const button = event.target.closest("[data-folder-path]");
    if (!button) {
      return;
    }
    try {
      await browsePath(button.dataset.folderPath);
    } catch (error) {
      setMessage(error.message, true);
    }
  });

  els.filesList.addEventListener("click", (event) => {
    const button = event.target.closest("[data-file-path]");
    if (!button) {
      return;
    }
    const path = button.dataset.filePath;
    els.filePathInput.value = path;
    els.overlayPathInput.value = path;
  });

  els.subplotTabs.addEventListener("click", async (event) => {
    const button = event.target.closest("[data-subplot-id]");
    if (!button) {
      return;
    }
    try {
      await api(`/csv/api/subplots/${button.dataset.subplotId}`);
      state.appState.active_subplot_id = button.dataset.subplotId;
      renderAppState();
      await refreshDetails();
    } catch (error) {
      setMessage(error.message, true);
    }
  });

  els.addSubplotBtn.addEventListener("click", async () => {
    try {
      await api("/csv/api/subplots", { method: "POST" });
      await refreshAppState();
    } catch (error) {
      setMessage(error.message, true);
    }
  });

  els.deleteSubplotBtn.addEventListener("click", async () => {
    const active = getActiveSubplot();
    if (!active) {
      return;
    }
    try {
      await api(`/csv/api/subplots/${active.id}`, { method: "DELETE" });
      await refreshAppState();
    } catch (error) {
      setMessage(error.message, true);
    }
  });

  [
    els.titleInput,
    els.modeSelect,
    els.signalsSelect,
    els.xMinInput,
    els.xMaxInput,
    els.yMinInput,
    els.yMaxInput,
    els.xAlignSelect,
    els.showTriggersInput,
    els.histogramBinsInput,
    els.spectrumCutoffInput,
    els.absEnabledInput,
    els.absTargetInput,
    els.absLimitInInput,
    els.absLimitOutInput,
    els.absStartInput,
    els.absEndInput,
    els.relEnabledInput,
    els.relTargetInput,
    els.relLimitInInput,
    els.relLimitOutInput,
    els.relStartInput,
    els.relEndInput,
    els.customCodeInput,
    els.detectorRowsInput,
    els.detectorColsInput,
    els.detectorMappingInput,
    els.detectorReducerInput,
    els.detectorMapInput,
  ].forEach((element) => {
    const eventName = element.tagName === "SELECT" || element.type === "checkbox" ? "change" : "input";
    element.addEventListener(eventName, async () => {
      try {
        await patchActiveSubplot();
      } catch (error) {
        setMessage(error.message, true);
      }
    });
  });

  els.addOverlayBtn.addEventListener("click", async () => {
    try {
      await addOverlay();
    } catch (error) {
      setMessage(error.message, true);
    }
  });

  els.overlayList.addEventListener("click", async (event) => {
    const removeButton = event.target.closest("[data-action='remove-overlay']");
    if (!removeButton) {
      return;
    }
    const container = removeButton.closest("[data-overlay-index]");
    if (!container) {
      return;
    }
    try {
      await removeOverlay(Number(container.dataset.overlayIndex));
    } catch (error) {
      setMessage(error.message, true);
    }
  });

  els.overlayList.addEventListener("change", async (event) => {
    const field = event.target.dataset.field;
    if (!field) {
      return;
    }
    const container = event.target.closest("[data-overlay-index]");
    if (!container) {
      return;
    }
    const value = event.target.type === "checkbox" ? event.target.checked : Number(event.target.value || 0);
    try {
      await updateOverlay(Number(container.dataset.overlayIndex), field, value);
    } catch (error) {
      setMessage(error.message, true);
    }
  });

  els.exportDataBtn.addEventListener("click", async () => {
    const active = getActiveSubplot();
    if (!active) {
      return;
    }
    try {
      await downloadBlob(
        `/csv/api/subplots/${active.id}/export-data`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ format: els.exportDataFormat.value }),
        },
        `export.${els.exportDataFormat.value}`
      );
    } catch (error) {
      setMessage(error.message, true);
    }
  });

  els.exportCombinedBtn.addEventListener("click", async () => {
    try {
      await downloadBlob(
        "/csv/api/export/combined",
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ format: "png" }),
        },
        "csv_plotter_combined.png"
      );
    } catch (error) {
      setMessage(error.message, true);
    }
  });

  els.exportCurrentBtn.addEventListener("click", () => {
    const active = getActiveSubplot();
    if (!active) {
      return;
    }
    window.open(`/csv/api/subplots/${active.id}/render?fmt=png&width=1600&height=900&t=${Date.now()}`, "_blank", "noopener");
  });

  els.saveLayoutBtn.addEventListener("click", async () => {
    try {
      await api("/csv/api/layout", {
        method: "POST",
        body: {
          subplots: state.appState?.subplots || [],
          active_subplot_id: state.appState?.active_subplot_id || null,
          browser_path: state.browser?.path || els.browserPathInput.value.trim(),
        },
      });
      setMessage("Layout saved");
    } catch (error) {
      setMessage(error.message, true);
    }
  });

  els.loadLayoutBtn.addEventListener("click", async () => {
    try {
      const layout = await api("/csv/api/layout");
      if (layout?.subplots) {
        await api("/csv/api/subplots/import", { method: "POST", body: layout });
      }
      await refreshAppState();
      if (layout?.browser_path) {
        await browsePath(layout.browser_path);
      }
      setMessage("Layout loaded");
    } catch (error) {
      setMessage(error.message, true);
    }
  });
}

async function init() {
  bindEvents();
  try {
    await loadRoots();
    await refreshAppState();
    if (state.roots[0]) {
      await browsePath(state.roots[0].path);
    }
  } catch (error) {
    setMessage(error.message, true);
  }
}

init();
