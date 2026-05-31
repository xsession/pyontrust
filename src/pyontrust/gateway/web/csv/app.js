const state = {
  appState: null,
  browser: null,
  browserSelection: null,
  patchInFlight: false,
  selectorActionInFlight: false,
  patchStatusText: "",
  signalFilter: "",
  roots: [],
  controlSync: false,
  mtimePollHandle: null,
  externalChangeDetected: false,
};

const MODE_CONTROL_PRESENTATION = {
  "Time series": {
    title: "Waveform workflow",
    copy: "Inspect raw traces, align time windows, and compare selected signals directly on the active subplot.",
    sections: [],
  },
  "AF-10047: Control vs Module": {
    title: "Comparison workflow",
    copy: "Compare control and module traces with shared timing controls and the active signal subset.",
    sections: [],
  },
  Histogram: {
    title: "Distribution workflow",
    copy: "Tune histogram density and inspect peak bins, spread, and sample distribution across the active channels.",
    sections: ["histogram-spectrum"],
  },
  Spectrum: {
    title: "Frequency workflow",
    copy: "Focus on dominant frequencies and magnitude peaks while shaping baseline treatment for the active signal.",
    sections: ["histogram-spectrum"],
  },
  "Absolute check": {
    title: "Absolute threshold workflow",
    copy: "Validate signals against absolute barriers and tune guard bands for pass/fail investigations.",
    sections: ["range-checks"],
  },
  "Relative change": {
    title: "Relative delta workflow",
    copy: "Track step-to-step change envelopes and tune differential barriers for drift or excursion analysis.",
    sections: ["range-checks"],
  },
  "Custom code": {
    title: "Derived signal workflow",
    copy: "Author transforms over the current signal set and inspect the derived output without leaving the analyzer.",
    sections: ["custom-code"],
  },
  "Detector map": {
    title: "Spatial detector workflow",
    copy: "Reduce channel energy into a detector grid and inspect hotspots, filled slots, and centroid movement.",
    sections: ["detector-map"],
  },
  Statistics: {
    title: "Statistics workflow",
    copy: "Review descriptive metrics for the active signal set with minimal control noise on screen.",
    sections: [],
  },
};

const els = {
  filePathInput: document.getElementById("file-path-input"),
  folderPathInput: document.getElementById("folder-path-input"),
  loadFileBtn: document.getElementById("load-file-btn"),
  loadFolderBtn: document.getElementById("load-folder-btn"),
  reloadBtn: document.getElementById("reload-btn"),
  saveLayoutBtn: document.getElementById("save-layout-btn"),
  loadLayoutBtn: document.getElementById("load-layout-btn"),
  quickLoadFileBtn: document.getElementById("quick-load-file-btn"),
  quickLoadFolderBtn: document.getElementById("quick-load-folder-btn"),
  quickAddSubplotBtn: document.getElementById("quick-add-subplot-btn"),
  quickExportBtn: document.getElementById("quick-export-btn"),
  datasetPill: document.getElementById("dataset-pill"),
  healthCard: document.getElementById("health-card"),
  healthCopy: document.getElementById("health-copy"),
  healthPill: document.getElementById("health-pill"),
  healthStats: document.getElementById("health-stats"),
  summaryFile: document.getElementById("summary-file"),
  summaryShape: document.getElementById("summary-shape"),
  summarySelection: document.getElementById("summary-selection"),
  summaryWindow: document.getElementById("summary-window"),
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
  controlStatus: document.getElementById("control-status"),
  controlModeTitle: document.getElementById("control-mode-title"),
  controlModeCopy: document.getElementById("control-mode-copy"),
  controlModePill: document.getElementById("control-mode-pill"),
  infoCurrentFile: document.getElementById("info-current-file"),
  infoDataShape: document.getElementById("info-data-shape"),
  infoCurrentFolder: document.getElementById("info-current-folder"),
  autoRefreshSummary: document.getElementById("auto-refresh-summary"),
  statusbarMessage: document.getElementById("statusbar-message"),
  statusbarFile: document.getElementById("statusbar-file"),
  statusbarShape: document.getElementById("statusbar-shape"),
  statusbarFolder: document.getElementById("statusbar-folder"),
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
  signalPanelSummary: document.getElementById("signal-panel-summary"),
  signalFilterInput: document.getElementById("signal-filter-input"),
  signalSelectVisibleBtn: document.getElementById("signal-select-visible-btn"),
  signalClearVisibleBtn: document.getElementById("signal-clear-visible-btn"),
  signalList: document.getElementById("signal-list"),
  overlayPathInput: document.getElementById("overlay-path-input"),
  addOverlayBtn: document.getElementById("add-overlay-btn"),
  overlayList: document.getElementById("overlay-list"),
  controlSections: Array.from(document.querySelectorAll("[data-control-group]")),
};

function setMessage(message, tone = "info") {
  if (typeof tone === "boolean") {
    tone = tone ? "error" : "info";
  }
  const text = message || "";
  const color = tone === "error"
    ? "#b42318"
    : tone === "warning"
      ? "var(--yellow)"
      : "var(--accent)";
  els.messageBar.textContent = text;
  els.messageBar.style.color = color;
  els.statusbarMessage.textContent = text || "Ready";
  els.statusbarMessage.style.color = color;
}

function pluralize(count, singular, plural = `${singular}s`) {
  return `${count} ${count === 1 ? singular : plural}`;
}

function setPatchBusy(isBusy, statusText = "") {
  state.patchInFlight = isBusy;
  state.patchStatusText = isBusy ? statusText || "Updating subplot" : "";
  [
    els.modeSelect,
    els.signalsSelect,
    els.signalSelectVisibleBtn,
    els.signalClearVisibleBtn,
  ].forEach((element) => {
    element.disabled = isBusy;
  });
  els.signalList.classList.toggle("busy-surface", isBusy);
  renderControlExperience(getActiveSubplot());
}

function setSelectorActionBusy(isBusy) {
  state.selectorActionInFlight = isBusy;
  [
    els.addSubplotBtn,
    els.deleteSubplotBtn,
    els.quickAddSubplotBtn,
  ].forEach((element) => {
    element.disabled = isBusy;
  });
  els.subplotTabs.classList.toggle("busy-surface", isBusy);
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
  if (state.externalChangeDetected && state.appState?.mtime) {
    state.externalChangeDetected = false;
  }
  await refreshDetails();
}

function renderAppState() {
  const appState = state.appState;
  const active = getActiveSubplot();
  const selectableColumns = appState?.selectable_columns || [];

  els.datasetPill.textContent = appState?.path ? `${appState.path} · ${appState.rows} rows` : "No file loaded";
  els.filePathInput.value = appState?.path || els.filePathInput.value;
  els.folderPathInput.value = appState?.folder || els.folderPathInput.value;
  els.activeTitle.textContent = active?.title || "Plot";

  renderModeOptions(appState?.modes || []);
  renderSignalOptions(selectableColumns, active?.selected_columns || []);
  renderSubplots(appState?.subplots || [], appState?.active_subplot_id);
  renderHealth(appState, active);
  renderSummaryRibbon(appState, active);
  renderConsoleInfo(appState, active);
  renderControlExperience(active);
  renderControls(active);
  renderSignalRoster(selectableColumns, active?.selected_columns || []);
  renderOverlays(active?.overlays || []);
  updateRenderImage(active);
}

function renderConsoleInfo(appState, active) {
  const fileName = appState?.path
    ? appState.path.split(/[/\\]/).pop()
    : "(none)";
  const folderName = appState?.folder || (appState?.path ? appState.path.split(/[/\\]/).slice(0, -1).join("\\") : "(none)");
  const rows = formatCompactInteger(Number(appState?.rows || 0));
  const cols = formatCompactInteger(Number(appState?.cols || 0));
  const autoRefreshCopy = appState?.path
    ? `Watching the loaded signal file for changes every 15 seconds. Active mode: ${active?.mode || "Time series"}.`
    : "Watching the loaded signal file for changes every 15 seconds once a dataset is active.";

  els.infoCurrentFile.textContent = `File: ${fileName}`;
  els.infoDataShape.textContent = `Rows: ${rows}  Cols: ${cols}`;
  els.infoCurrentFolder.textContent = `Folder: ${folderName}`;
  els.autoRefreshSummary.textContent = autoRefreshCopy;

  els.statusbarFile.textContent = `File: ${fileName}`;
  els.statusbarShape.textContent = `Rows: ${rows}  Cols: ${cols}`;
  els.statusbarFolder.textContent = `Folder: ${folderName}`;
}

function renderControlExperience(active) {
  const mode = active?.mode || "Time series";
  const presentation = MODE_CONTROL_PRESENTATION[mode] || MODE_CONTROL_PRESENTATION["Time series"];
  const visibleSections = new Set(presentation.sections || []);

  els.controlModeTitle.textContent = presentation.title;
  if (state.patchInFlight) {
    els.controlModeCopy.textContent = `${state.patchStatusText || "Updating subplot"}. Large files can take several seconds while metrics and render artifacts refresh.`;
    els.controlModePill.textContent = "Syncing";
    els.controlModePill.classList.add("busy");
  } else {
    els.controlModeCopy.textContent = presentation.copy;
    els.controlModePill.textContent = active ? mode : "Idle";
    els.controlModePill.classList.remove("busy");
  }

  els.controlSections.forEach((section) => {
    const sectionKey = section.dataset.controlGroup;
    section.classList.toggle("is-hidden", !visibleSections.has(sectionKey));
  });
}

function renderSummaryRibbon(appState, active) {
  const path = appState?.path || "No file loaded";
  const fileName = path.includes("\\") || path.includes("/") ? path.split(/[/\\]/).pop() : path;
  const rows = Number(appState?.rows || 0);
  const cols = Number(appState?.cols || 0);
  const selectedSignals = active?.selected_columns?.length || 0;
  const overlays = active?.overlays?.length || 0;
  const xWindow = Array.isArray(active?.x_window) && active.x_window.length === 2
    ? `${formatMetricValue(active.x_window[0])} to ${formatMetricValue(active.x_window[1])}`
    : "Full span";
  els.summaryFile.textContent = fileName || "No file loaded";
  els.summaryFile.title = path;
  els.summaryShape.textContent = `${formatCompactInteger(rows)} rows · ${formatCompactInteger(cols)} cols`;
  els.summarySelection.textContent = active
    ? `${active.mode} · ${selectedSignals} signal${selectedSignals === 1 ? "" : "s"} · ${overlays} overlay${overlays === 1 ? "" : "s"}`
    : "No subplot active";
  els.summaryWindow.textContent = xWindow;
}

function renderHealth(appState, active) {
  const rows = Number(appState?.rows || 0);
  const columnCount = Array.isArray(appState?.selectable_columns) ? appState.selectable_columns.length : 0;
  const selectedSignals = active?.selected_columns?.length || 0;
  const overlayCount = active?.overlays?.length || 0;
  const ready = Boolean(appState?.path) && selectedSignals > 0;
  const copy = !appState?.path
    ? "Load a signal file to activate subplot analysis, overlays, and export surfaces."
    : ready
      ? `Active mode ${active?.mode || "Time series"} is ready with ${selectedSignals} selected signal${selectedSignals === 1 ? "" : "s"}.`
      : "The active subplot has no selected signals yet. Choose one or more signal columns to render and export.";

  els.healthCard.className = `config-health-card ${ready ? "ok" : "alert"}`;
  els.healthPill.className = `config-health-pill ${ready ? "ok" : "alert"}`;
  els.healthPill.textContent = ready ? "Clean" : appState?.path ? "Needs input" : "Idle";
  els.healthCopy.textContent = copy;
  els.healthStats.innerHTML = [
    { value: rows || "-", label: "Rows" },
    { value: columnCount || "-", label: "Signals" },
    { value: active?.mode || "-", label: "Mode" },
    { value: overlayCount, label: "Overlays" },
  ]
    .map(
      (item) => `
        <div class="config-health-stat">
          <strong>${item.value}</strong>
          <span>${item.label}</span>
        </div>
      `
    )
    .join("");
}

function renderModeOptions(modes) {
  if (els.modeSelect.options.length === modes.length) {
    return;
  }
  els.modeSelect.innerHTML = modes.map((mode) => `<option value="${mode}">${mode}</option>`).join("");
}

function renderSignalRoster(columns, selected) {
  const signals = columns.filter((column) => column !== "Timestamp");
  const selectedSet = new Set(selected || []);
  const filterText = state.signalFilter.trim().toLowerCase();
  const visibleSignals = filterText
    ? signals.filter((signal) => signal.toLowerCase().includes(filterText))
    : signals;
  els.signalFilterInput.value = state.signalFilter;
  els.signalPanelSummary.textContent = `${selectedSet.size}/${signals.length} selected · ${visibleSignals.length} visible`;
  if (!signals.length) {
    els.signalList.innerHTML = '<div class="overlay-item"><div class="overlay-meta">Load a dataset to inspect available numeric channels.</div></div>';
    return;
  }
  if (!visibleSignals.length) {
    els.signalList.innerHTML = '<div class="signal-empty">No signals match the current filter.</div>';
    return;
  }
  els.signalList.innerHTML = visibleSignals
    .map(
      (signal) => `
        <button class="signal-row ${selectedSet.has(signal) ? "active" : ""}" type="button" data-signal-name="${signal}">
          <span class="signal-row-index">${String(signals.indexOf(signal) + 1).padStart(2, "0")}</span>
          <span class="signal-row-copy">
            <strong>${signal}</strong>
            <span>${selectedSet.has(signal) ? "Included in active subplot" : "Available channel"}</span>
          </span>
          <span class="signal-row-state">${selectedSet.has(signal) ? "ON" : "OFF"}</span>
        </button>
      `
    )
    .join("");
}

function renderSignalOptions(columns, selected) {
  els.signalsSelect.innerHTML = columns
    .map((column) => `<option value="${column}">${column}</option>`)
    .join("");
  Array.from(els.signalsSelect.options).forEach((option) => {
    option.selected = selected.includes(option.value);
  });
}

function visibleSignalNames() {
  const signals = state.appState?.selectable_columns || [];
  const filterText = state.signalFilter.trim().toLowerCase();
  return filterText
    ? signals.filter((signal) => signal.toLowerCase().includes(filterText))
    : signals;
}

function formatWindowSummary(windowRange) {
  if (!Array.isArray(windowRange) || windowRange.length !== 2) {
    return "Window: full span";
  }
  return `Window: ${formatMetricValue(windowRange[0])} to ${formatMetricValue(windowRange[1])}`;
}

function formatSignalPreview(selectedColumns) {
  const columns = Array.isArray(selectedColumns) ? selectedColumns.filter(Boolean) : [];
  if (!columns.length) {
    return "No signals selected";
  }
  if (columns.length <= 2) {
    return columns.join(" · ");
  }
  return `${columns.slice(0, 2).join(" · ")} +${columns.length - 2} more`;
}

function findSubplot(subplotId) {
  return (state.appState?.subplots || []).find((subplot) => subplot.id === subplotId) || null;
}

async function updateVisibleSignalSelection(selectVisible) {
  const visible = new Set(visibleSignalNames());
  if (!visible.size) {
    setMessage("No visible signals matched the current filter", "warning");
    return;
  }
  Array.from(els.signalsSelect.options).forEach((option) => {
    if (!visible.has(option.value)) {
      return;
    }
    option.selected = selectVisible;
  });
  await patchActiveSubplot(selectVisible ? "Including visible signals" : "Clearing visible signals");
  setMessage(`${selectVisible ? "Included" : "Cleared"} ${pluralize(visible.size, "visible signal")} from the active subplot`);
}

function renderSubplots(subplots, activeId) {
  els.subplotTabs.innerHTML = subplots
    .map(
      (subplot) => `
        <article class="subplot-tab ${subplot.id === activeId ? "active" : ""}" data-subplot-id="${subplot.id}">
          <button class="subplot-tab-main" type="button" data-action="open-subplot" data-subplot-id="${subplot.id}">
            <div class="subplot-tab-head">
              <div>
                <div class="subplot-title">${subplot.title}</div>
                <div class="subplot-mode">${subplot.mode}</div>
              </div>
              ${subplot.id === activeId ? '<span class="subplot-active-pill">Active</span>' : ""}
            </div>
            <div class="subplot-summary-grid">
              <div class="subplot-stat">
                <span class="subplot-stat-label">Signals</span>
                <span class="subplot-stat-value">${subplot.selected_columns?.length || 0}</span>
              </div>
              <div class="subplot-stat">
                <span class="subplot-stat-label">Overlays</span>
                <span class="subplot-stat-value">${subplot.overlays?.length || 0}</span>
              </div>
            </div>
            <div class="subplot-signal-preview">${formatSignalPreview(subplot.selected_columns)}</div>
            <div class="subplot-window">${formatWindowSummary(subplot.x_window)}</div>
          </button>
          <div class="subplot-card-actions">
            <button class="subplot-action-btn" type="button" data-action="duplicate-subplot" data-subplot-id="${subplot.id}">Duplicate</button>
            <button class="subplot-action-btn" type="button" data-action="subplot-mode" data-subplot-id="${subplot.id}" data-mode="Histogram">Hist</button>
            <button class="subplot-action-btn" type="button" data-action="subplot-mode" data-subplot-id="${subplot.id}" data-mode="Statistics">Stats</button>
          </div>
        </article>
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
            <button class="btn" type="button" data-action="remove-overlay">Remove</button>
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
  return `
    <div class="detail-stack">
      <div class="kv-grid">
        <div class="kv-card"><strong>Signals</strong><div>${entries.length}</div></div>
        <div class="kv-card"><strong>Rows</strong><div>${formatCompactInteger(Number(state.appState?.rows || 0))}</div></div>
        <div class="kv-card"><strong>Timestamp Scale</strong><div>${formatMetricValue(state.appState?.timestamp_scale ?? 1)}</div></div>
      </div>
      <div class="table-wrap">
        <table class="stats-table metrics-table">
          <thead>
            <tr><th>Signal</th><th>Min</th><th>Max</th><th>Avg</th><th>Std</th><th>RMS</th><th>Freq</th></tr>
          </thead>
          <tbody>
            ${entries
              .map(
                ([name, value]) => `
                  <tr>
                    <td>${name}</td>
                    <td>${formatMetricValue(value.min)}</td>
                    <td>${formatMetricValue(value.max)}</td>
                    <td>${formatMetricValue(value.avg)}</td>
                    <td>${formatMetricValue(value.std)}</td>
                    <td>${formatMetricValue(value.rms)}</td>
                    <td>${formatMetricValue(value.freq)}</td>
                  </tr>
                `
              )
              .join("")}
          </tbody>
        </table>
      </div>
    </div>
  `;
}

function formatSummaryNumber(value, digits = 3) {
  const numeric = Number(value);
  if (!Number.isFinite(numeric)) {
    return "-";
  }
  return Math.abs(numeric) >= 1000
    ? formatCompactInteger(numeric)
    : numeric.toFixed(digits).replace(/\.0+$/, "").replace(/(\.\d*?)0+$/, "$1");
}

function maxSeriesSamples(seriesList) {
  return (seriesList || []).reduce((maxValue, series) => {
    const samples = Array.isArray(series?.x)
      ? series.x.length
      : Array.isArray(series?.centers)
        ? series.centers.length
        : Array.isArray(series?.y)
          ? series.y.length
          : 0;
    return Math.max(maxValue, samples);
  }, 0);
}

function renderSummaryCards(items) {
  return `
    <div class="kv-grid">
      ${items
        .map(
          (item) => `
            <div class="kv-card">
              <strong>${item.label}</strong>
              <div>${item.value}</div>
            </div>
          `
        )
        .join("")}
    </div>
  `;
}

function renderDetectorDetails(payload) {
  const matrix = Array.isArray(payload.matrix) ? payload.matrix : [];
  const flatCells = matrix.flatMap((row, rowIndex) =>
    (Array.isArray(row) ? row : []).map((value, colIndex) => ({ rowIndex, colIndex, value: Number(value) }))
  );
  const filledCells = flatCells.filter((cell) => Number.isFinite(cell.value));
  const hottestCell = filledCells.reduce((best, cell) => {
    if (!best || cell.value > best.value) {
      return cell;
    }
    return best;
  }, null);
  const latestCentroid = Array.isArray(payload.centroids) && payload.centroids.length
    ? payload.centroids[payload.centroids.length - 1]
    : null;
  return `
    <div class="detail-stack">
      ${renderSummaryCards([
        { label: "Grid", value: `${payload.rows} x ${payload.cols}` },
        { label: "Filled Slots", value: `${filledCells.length}` },
        { label: "Mapping", value: payload.mapping || "-" },
        { label: "Reducer", value: payload.reducer || "-" },
        {
          label: "Hottest Cell",
          value: hottestCell ? `R${hottestCell.rowIndex + 1} C${hottestCell.colIndex + 1} · ${formatSummaryNumber(hottestCell.value)}` : "-",
        },
        {
          label: "Latest Centroid",
          value: latestCentroid
            ? `${formatSummaryNumber(latestCentroid.x, 2)}, ${formatSummaryNumber(latestCentroid.y, 2)} · E ${formatSummaryNumber(latestCentroid.energy, 2)}`
            : "-",
        },
      ])}
      <pre>${JSON.stringify(payload.matrix, null, 2)}</pre>
    </div>
  `;
}

function renderHistogramDetails(payload) {
  const seriesList = Array.isArray(payload.series) ? payload.series : [];
  const peakBin = seriesList.reduce((best, series) => {
    const counts = Array.isArray(series.counts) ? series.counts : [];
    const centers = Array.isArray(series.centers) ? series.centers : [];
    counts.forEach((count, index) => {
      const numericCount = Number(count);
      if (!Number.isFinite(numericCount)) {
        return;
      }
      if (!best || numericCount > best.count) {
        best = {
          label: series.label || "series",
          count: numericCount,
          center: Number(centers[index]),
        };
      }
    });
    return best;
  }, null);
  return renderSummaryCards([
    { label: "Series", value: `${seriesList.length}` },
    { label: "Max Samples", value: formatCompactInteger(maxSeriesSamples(seriesList)) },
    {
      label: "Peak Bin",
      value: peakBin ? `${peakBin.label} @ ${formatSummaryNumber(peakBin.center, 2)}` : "-",
    },
    {
      label: "Peak Count",
      value: peakBin ? formatCompactInteger(peakBin.count) : "-",
    },
  ]);
}

function renderSpectrumDetails(payload) {
  const seriesList = Array.isArray(payload.series) ? payload.series : [];
  const peakPoint = seriesList.reduce((best, series) => {
    const frequencies = Array.isArray(series.x) ? series.x : [];
    const magnitudes = Array.isArray(series.y) ? series.y : [];
    magnitudes.forEach((magnitude, index) => {
      const numericMagnitude = Number(magnitude);
      if (!Number.isFinite(numericMagnitude)) {
        return;
      }
      if (!best || numericMagnitude > best.magnitude) {
        best = {
          label: series.label || "series",
          magnitude: numericMagnitude,
          frequency: Number(frequencies[index]),
        };
      }
    });
    return best;
  }, null);
  return renderSummaryCards([
    { label: "Series", value: `${seriesList.length}` },
    { label: "Max Samples", value: formatCompactInteger(maxSeriesSamples(seriesList)) },
    {
      label: "Peak Frequency",
      value: peakPoint ? `${formatSummaryNumber(peakPoint.frequency, 2)} Hz` : "-",
    },
    {
      label: "Peak Magnitude",
      value: peakPoint ? `${peakPoint.label} · ${formatSummaryNumber(peakPoint.magnitude, 4)}` : "-",
    },
  ]);
}

function renderLineModeSummary(payload, seriesCount, barrierCount) {
  const seriesList = Array.isArray(payload.series) ? payload.series : [];
  const peakSeries = seriesList.reduce((best, series) => {
    const yValues = Array.isArray(series.y) ? series.y : [];
    yValues.forEach((value) => {
      const numericValue = Number(value);
      if (!Number.isFinite(numericValue)) {
        return;
      }
      if (!best || Math.abs(numericValue) > Math.abs(best.value)) {
        best = { label: series.label || "series", value: numericValue };
      }
    });
    return best;
  }, null);
  return renderSummaryCards([
    { label: "Kind", value: payload.kind || "plot" },
    { label: "Series", value: `${seriesCount}` },
    { label: "Barriers", value: `${barrierCount}` },
    { label: "Max Samples", value: formatCompactInteger(maxSeriesSamples(seriesList)) },
    {
      label: "Peak Response",
      value: peakSeries ? `${peakSeries.label} · ${formatSummaryNumber(peakSeries.value, 4)}` : "-",
    },
  ]);
}

function renderPayloadDetails(payload) {
  if (payload.error) {
    return `<div class="kv-card"><strong>Custom code error</strong><div>${payload.error}</div></div>`;
  }
  if (payload.kind === "detector") {
    return renderDetectorDetails(payload);
  }
  const seriesCount = Array.isArray(payload.series) ? payload.series.length : 0;
  const barrierCount = Array.isArray(payload.barriers) ? payload.barriers.length : 0;
  const rows = Array.isArray(payload.series)
    ? payload.series.map((series) => {
        const samples = Array.isArray(series.x)
          ? series.x.length
          : Array.isArray(series.centers)
            ? series.centers.length
            : Array.isArray(series.y)
              ? series.y.length
              : 0;
        return `
          <tr>
            <td>${series.label || "series"}</td>
            <td>${samples}</td>
            <td>${Array.isArray(series.counts) ? "hist" : payload.kind || "plot"}</td>
          </tr>
        `;
      }).join("")
    : "";
  let summaryMarkup = renderSummaryCards([
    { label: "Kind", value: payload.kind || "plot" },
    { label: "Series", value: `${seriesCount}` },
    { label: "Barriers", value: `${barrierCount}` },
  ]);
  if (payload.kind === "histogram") {
    summaryMarkup = renderHistogramDetails(payload);
  } else if (payload.kind === "spectrum") {
    summaryMarkup = renderSpectrumDetails(payload);
  } else if (["abs", "rel", "custom"].includes(payload.kind)) {
    summaryMarkup = renderLineModeSummary(payload, seriesCount, barrierCount);
  }
  return `
    <div class="detail-stack">
      ${summaryMarkup}
      <div class="table-wrap">
        <table class="stats-table payload-table">
          <thead><tr><th>Series</th><th>Samples</th><th>Type</th></tr></thead>
          <tbody>${rows || '<tr><td colspan="3">No derived series available</td></tr>'}</tbody>
        </table>
      </div>
    </div>
  `;
}

function formatCompactInteger(value) {
  const numeric = Number(value || 0);
  if (!Number.isFinite(numeric)) {
    return "-";
  }
  return new Intl.NumberFormat().format(numeric);
}

async function patchActiveSubplot(statusText = "Updating subplot") {
  if (state.controlSync || state.patchInFlight) {
    return;
  }
  const active = getActiveSubplot();
  if (!active) {
    return;
  }
  setPatchBusy(true, statusText);
  try {
    await api(`/csv/api/subplots/${active.id}`, {
      method: "PATCH",
      body: collectSubplotPatch(),
    });
    await refreshAppState();
  } finally {
    setPatchBusy(false);
  }
}

async function pollForExternalChanges() {
  if (!state.appState?.path) {
    state.externalChangeDetected = false;
    return;
  }
  try {
    const response = await api("/csv/api/csv/check-mtime");
    if (response?.changed && !state.externalChangeDetected) {
      state.externalChangeDetected = true;
      setMessage("Source file changed on disk. Click Reload to refresh the analyzer.", "warning");
    }
  } catch (_unused) {
    // Ignore transient polling failures; explicit user actions will surface errors.
  }
}

function ensureMtimePolling() {
  if (state.mtimePollHandle !== null) {
    return;
  }
  state.mtimePollHandle = window.setInterval(() => {
    void pollForExternalChanges();
  }, 15000);
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
    .map(
      (item) => `
        <button type="button" class="browser-item ${state.browserSelection === item.path ? "active" : ""}" data-folder-path="${item.path}">
          <span class="browser-item-name">${item.name}</span>
          <span class="browser-item-meta">Folder</span>
        </button>
      `
    )
    .join("");
  els.filesList.innerHTML = (browser?.files || [])
    .map(
      (item) => `
        <button type="button" class="browser-item ${state.browserSelection === item.path ? "active" : ""}" data-file-path="${item.path}">
          <span class="browser-item-name">${item.name}</span>
          <span class="browser-item-meta">${formatFileSize(item.size)} · ${formatDateTime(item.mtime)}</span>
        </button>
      `
    )
    .join("");
}

function formatFileSize(bytes) {
  const value = Number(bytes || 0);
  if (!Number.isFinite(value) || value <= 0) {
    return "0 B";
  }
  const units = ["B", "KB", "MB", "GB"];
  let unitIndex = 0;
  let size = value;
  while (size >= 1024 && unitIndex < units.length - 1) {
    size /= 1024;
    unitIndex += 1;
  }
  return `${size.toFixed(size >= 10 || unitIndex === 0 ? 0 : 1)} ${units[unitIndex]}`;
}

function formatDateTime(value) {
  const numeric = Number(value);
  if (!Number.isFinite(numeric) || numeric <= 0) {
    return "unknown";
  }
  return new Date(numeric * 1000).toLocaleString();
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

async function createSubplot(body = {}, pendingMessage = "Creating subplot...", completionPrefix = "Created") {
  if (state.selectorActionInFlight) {
    return;
  }
  setSelectorActionBusy(true);
  setMessage(pendingMessage);
  try {
    const response = await api("/csv/api/subplots", { method: "POST", body });
    const title = response?.subplot?.title || "a new subplot";
    if (state.appState && response?.subplot) {
      const nextSubplots = [...(state.appState.subplots || [])];
      nextSubplots.push(response.subplot);
      state.appState = {
        ...state.appState,
        subplots: nextSubplots,
        active_subplot_id: response.active_subplot_id || response.subplot.id,
      };
      renderAppState();
    }
    await refreshAppState();
    setMessage(`${completionPrefix} ${title}`);
  } finally {
    setSelectorActionBusy(false);
  }
}

async function switchActiveSubplot(subplotId) {
  if (state.selectorActionInFlight) {
    return;
  }
  const target = findSubplot(subplotId);
  const targetTitle = target?.title || subplotId;
  try {
    setSelectorActionBusy(true);
    setMessage(`Opening ${targetTitle}...`);
    await api(`/csv/api/subplots/${subplotId}`);
    state.appState.active_subplot_id = subplotId;
    renderAppState();
    await refreshDetails();
    setMessage(`Switched to ${targetTitle}`);
  } catch (error) {
    setMessage(error.message, true);
  } finally {
    setSelectorActionBusy(false);
  }
}

async function duplicateSubplot(subplotId) {
  const source = findSubplot(subplotId);
  if (!source) {
    return;
  }
  await createSubplot(
    {
      title: `${source.title} copy`,
      mode: source.mode,
      selected_columns: source.selected_columns,
      x_window: source.x_window,
      y_limits: source.y_limits,
      x_align: source.x_align,
      show_trigger_markers: source.show_trigger_markers,
      histogram_bins: source.histogram_bins,
      spectrum_baseline_cutoff: source.spectrum_baseline_cutoff,
      barrier_config: source.barrier_config,
      custom_code: source.custom_code,
      detector_config: source.detector_config,
    },
    `Duplicating ${source.title}...`,
    "Duplicated"
  );
}

async function setSubplotMode(subplotId, mode) {
  if (state.selectorActionInFlight) {
    return;
  }
  const target = findSubplot(subplotId);
  const targetTitle = target?.title || subplotId;
  try {
    setSelectorActionBusy(true);
    setMessage(`Switching ${targetTitle} to ${mode}...`);
    const response = await api(`/csv/api/subplots/${subplotId}`, {
      method: "PATCH",
      body: { mode },
    });
    if (state.appState && response?.subplot) {
      state.appState = {
        ...state.appState,
        active_subplot_id: response.subplot.id,
        subplots: (state.appState.subplots || []).map((subplot) =>
          subplot.id === response.subplot.id ? response.subplot : subplot
        ),
      };
      renderAppState();
    }
    await refreshDetails();
    setMessage(`${targetTitle} set to ${mode}`);
  } catch (error) {
    setMessage(error.message, true);
  } finally {
    setSelectorActionBusy(false);
  }
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
  els.quickLoadFileBtn.addEventListener("click", () => {
    els.filePathInput.focus();
    els.filePathInput.select();
  });

  els.quickLoadFolderBtn.addEventListener("click", () => {
    els.folderPathInput.focus();
    els.folderPathInput.select();
  });

  els.quickAddSubplotBtn.addEventListener("click", () => {
    void createSubplot().catch((error) => {
      setMessage(error.message, true);
    });
  });

  els.quickExportBtn.addEventListener("click", () => {
    els.exportCombinedBtn.click();
  });

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
      state.browserSelection = button.dataset.folderPath;
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
    state.browserSelection = path;
    els.filePathInput.value = path;
    els.overlayPathInput.value = path;
    renderBrowser();
  });

  els.signalList.addEventListener("click", async (event) => {
    const button = event.target.closest("[data-signal-name]");
    if (!button) {
      return;
    }
    const signalName = button.dataset.signalName;
    const option = Array.from(els.signalsSelect.options).find((candidate) => candidate.value === signalName);
    if (!option) {
      return;
    }
    option.selected = !option.selected;
    try {
      await patchActiveSubplot(`Updating signal ${signalName}`);
      setMessage(`${option.selected ? "Enabled" : "Removed"} signal ${signalName} in the active subplot`);
    } catch (error) {
      setMessage(error.message, true);
    }
  });

  els.signalFilterInput.addEventListener("input", () => {
    state.signalFilter = els.signalFilterInput.value;
    renderSignalRoster(state.appState?.selectable_columns || [], getActiveSubplot()?.selected_columns || []);
  });

  els.signalSelectVisibleBtn.addEventListener("click", async () => {
    try {
      await updateVisibleSignalSelection(true);
    } catch (error) {
      setMessage(error.message, true);
    }
  });

  els.signalClearVisibleBtn.addEventListener("click", async () => {
    try {
      await updateVisibleSignalSelection(false);
    } catch (error) {
      setMessage(error.message, true);
    }
  });

  els.subplotTabs.addEventListener("click", async (event) => {
    const actionButton = event.target.closest("[data-action]");
    if (!actionButton || state.selectorActionInFlight) {
      return;
    }
    try {
      if (actionButton.dataset.action === "open-subplot") {
        await switchActiveSubplot(actionButton.dataset.subplotId);
        return;
      }
      if (actionButton.dataset.action === "duplicate-subplot") {
        await duplicateSubplot(actionButton.dataset.subplotId);
        return;
      }
      if (actionButton.dataset.action === "subplot-mode") {
        await setSubplotMode(actionButton.dataset.subplotId, actionButton.dataset.mode);
      }
    } catch (error) {
      setMessage(error.message, true);
    }
  });

  els.addSubplotBtn.addEventListener("click", async () => {
    try {
      await createSubplot();
    } catch (error) {
      setMessage(error.message, true);
    }
  });

  els.deleteSubplotBtn.addEventListener("click", async () => {
    const active = getActiveSubplot();
    if (!active || state.selectorActionInFlight) {
      return;
    }
    try {
      const deletedTitle = active.title;
      setSelectorActionBusy(true);
      setMessage(`Deleting ${deletedTitle}...`);
      await api(`/csv/api/subplots/${active.id}`, { method: "DELETE" });
      await refreshAppState();
      setMessage(`Deleted ${deletedTitle}`);
    } catch (error) {
      setMessage(error.message, true);
    } finally {
      setSelectorActionBusy(false);
    }
  });

  els.modeSelect.addEventListener("change", async () => {
    try {
      await patchActiveSubplot(`Switching to ${els.modeSelect.value}`);
      setMessage(`Mode set to ${els.modeSelect.value}`);
    } catch (error) {
      setMessage(error.message, true);
    }
  });

  els.signalsSelect.addEventListener("change", async () => {
    try {
      await patchActiveSubplot("Refreshing signal selection");
      setMessage(`Active subplot now tracks ${pluralize(els.signalsSelect.selectedOptions.length, "signal")}`);
    } catch (error) {
      setMessage(error.message, true);
    }
  });

  [
    els.titleInput,
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
        await patchActiveSubplot("Updating analysis parameters");
      } catch (error) {
        setMessage(error.message, true);
      }
    });
  });

  els.addOverlayBtn.addEventListener("click", async () => {
    try {
      await addOverlay();
      setMessage(`Added overlay ${els.overlayPathInput.value.trim()}`);
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
      setMessage(`Updated overlay ${field}`);
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
      setMessage(`Exported active selection as ${els.exportDataFormat.value.toUpperCase()}`);
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
      setMessage("Exported combined workspace image");
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
    setMessage(`Opened render for ${active.title}`);
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
      setMessage(`Layout saved with ${pluralize((state.appState?.subplots || []).length, "subplot")}`);
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
      setMessage(`Layout loaded with ${pluralize((layout?.subplots || []).length, "subplot")}`);
    } catch (error) {
      setMessage(error.message, true);
    }
  });
}

async function init() {
  bindEvents();
  ensureMtimePolling();
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
