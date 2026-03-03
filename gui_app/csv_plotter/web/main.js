"use strict";

// ═══════════════════════════════════════════════════════════════════════════
// State
// ═══════════════════════════════════════════════════════════════════════════

let csvState = {
    path: null,
    folder: null,
    columns: [],
    rows: 0,
    separator: null,
    timestampScale: 1.0,
    mtime: null,
};

let subplots = [];
let subIdCounter = 0;

let cfgSettings = {
    autoReload: false,
    autoNewest: false,
    reloadInterval: 1000,
    maxPoints: 5000,
    autoSaveLayout: true,
    histBins: 50,
    recursiveFolder: true,
};

let _autoReloadTimer = null;
let _autoNewestTimer = null;
let _autoSaveTimer = null;
let _autoSaveDebounce = null;
let _highlightedSignals = new Set();
let _historyList = [];
let _historyIndex = -1;

// ═══════════════════════════════════════════════════════════════════════════
// DOM Helpers
// ═══════════════════════════════════════════════════════════════════════════

const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => document.querySelectorAll(sel);

function toast(msg, type) {
    const el = $("#toast");
    el.textContent = msg;
    el.className = "show" + (type === "error" ? " error" : "");
    clearTimeout(el._tid);
    el._tid = setTimeout(() => el.className = "", 3000);
}

async function api(path, opts = {}) {
    const defaults = {
        headers: { "Content-Type": "application/json" },
    };
    if (opts.body && typeof opts.body === "object" && !(opts.body instanceof FormData)) {
        opts.body = JSON.stringify(opts.body);
    }
    const resp = await fetch(path, { ...defaults, ...opts });
    if (!resp.ok) {
        let errMsg = `HTTP ${resp.status}`;
        try {
            const j = await resp.json();
            if (j.error) errMsg = j.error;
        } catch (_) {}
        throw new Error(errMsg);
    }
    return resp;
}

// Plotly dark theme layout
const PLOTLY_LAYOUT = {
    paper_bgcolor: "#1e1e2e",
    plot_bgcolor:  "#252538",
    font:   { color: "#cdd6f4", family: "Segoe UI, Consolas, monospace", size: 11 },
    xaxis:  { gridcolor: "#45475a", zerolinecolor: "#45475a" },
    yaxis:  { gridcolor: "#45475a", zerolinecolor: "#45475a" },
    legend: { bgcolor: "rgba(0,0,0,0)", font: { color: "#cdd6f4", size: 10 } },
    margin: { t: 30, b: 40, l: 55, r: 15 },
};

const PLOTLY_COLORS = [
    "#89b4fa", "#a6e3a1", "#f38ba8", "#f9e2af", "#fab387",
    "#cba6f7", "#f5c2e7", "#94e2d5", "#89dceb", "#b4befe",
];

const PLOT_MODES = [
    "Time series",
    "Histogram",
    "Abs check",
    "Rel change",
    "Custom code",
];

// ═══════════════════════════════════════════════════════════════════════════
// File / Folder Browser Module (brw*)
// ═══════════════════════════════════════════════════════════════════════════

let _brwResolve = null;  // Promise resolve for current browse session
let _brwMode = "file";   // "file" | "folder"
let _brwCurrent = "";    // Current directory being viewed
let _brwSelected = null; // Currently selected path
let _brwRoots = [];      // Cached drive roots

/**
 * Open the browser modal and return a Promise that resolves to the
 * chosen path (string) or null if cancelled.
 *
 * @param {"file"|"folder"} mode - what the user is selecting
 * @param {string} [startPath] - initial directory to show
 * @returns {Promise<string|null>}
 */
function brwOpen(mode, startPath) {
    _brwMode = mode || "file";
    _brwSelected = null;
    _brwCurrent = "";

    $("#brw-title").textContent = mode === "folder" ? "📁 Select Folder" : "📂 Select CSV File";
    $("#brw-confirm-btn").textContent = mode === "folder" ? "Select Folder" : "Open";
    $("#brw-confirm-btn").disabled = true;
    $("#brw-selected").textContent = "";
    $("#brw-path-input").value = startPath || "";
    $("#browseModal").classList.add("show");

    // Load roots then navigate to start path
    _brwLoadRoots().then(() => {
        if (startPath) {
            _brwNavigate(startPath);
        }
    });

    return new Promise((resolve) => { _brwResolve = resolve; });
}

function brwClose() {
    $("#browseModal").classList.remove("show");
    if (_brwResolve) { _brwResolve(null); _brwResolve = null; }
}

function brwConfirm() {
    const selected = _brwSelected || (_brwMode === "folder" ? _brwCurrent : null);
    $("#browseModal").classList.remove("show");
    if (_brwResolve) { _brwResolve(selected); _brwResolve = null; }
}

function brwGoToPath() {
    const val = $("#brw-path-input")?.value?.trim();
    if (!val) return;
    _brwNavigate(val);
}

function brwGoUp() {
    if (_brwCurrent) {
        // Go to parent: strip last path segment
        const parts = _brwCurrent.replace(/[/\\]+$/, "").split(/[/\\]/);
        if (parts.length > 1) {
            parts.pop();
            let parent = parts.join("\\");
            // Windows: "C:" → "C:\\"
            if (/^[A-Za-z]:$/.test(parent)) parent += "\\";
            _brwNavigate(parent);
        }
    }
}

async function _brwLoadRoots() {
    if (_brwRoots.length > 0) {
        _brwRenderRoots();
        return;
    }
    try {
        const resp = await api("/api/browse/roots");
        const data = await resp.json();
        _brwRoots = data.roots || [];
    } catch (_) {
        _brwRoots = [{ name: "C:", path: "C:\\" }];
    }
    _brwRenderRoots();
}

function _brwRenderRoots() {
    const el = $("#brw-roots");
    el.innerHTML = _brwRoots.map(r =>
        `<button class="sm" onclick="_brwNavigate('${r.path.replace(/\\/g, "\\\\")}')" title="${r.path}">💾 ${r.name}</button>`
    ).join("");
}

async function _brwNavigate(dirPath) {
    _brwSelected = null;
    $("#brw-confirm-btn").disabled = _brwMode === "file";
    if (_brwMode === "folder") {
        _brwSelected = dirPath;
        $("#brw-confirm-btn").disabled = false;
        $("#brw-selected").textContent = dirPath;
    } else {
        $("#brw-selected").textContent = "";
    }

    try {
        const resp = await api(`/api/folder/browse?path=${encodeURIComponent(dirPath)}`);
        const data = await resp.json();
        if (data.error) {
            toast(data.error, "error");
            return;
        }
        _brwCurrent = data.path;
        $("#brw-path-input").value = data.path;

        // Breadcrumb
        _brwRenderBreadcrumb(data.path);

        // Listing
        const listing = $("#brw-listing");
        let html = "";

        // Parent folder link
        if (data.parent) {
            html += `<div class="brw-item" ondblclick="_brwNavigate('${data.parent.replace(/\\/g, "\\\\").replace(/'/g, "\\'")}')">
                <span class="icon">⬆</span>
                <span class="name" style="color:var(--fg-dim);">..</span>
            </div>`;
        }

        // Folders
        for (const f of (data.folders || [])) {
            const esc = f.path.replace(/\\/g, "\\\\").replace(/'/g, "\\'");
            const isSelected = _brwMode === "folder" && _brwSelected === f.path;
            html += `<div class="brw-item ${isSelected ? "selected" : ""}"
                          onclick="_brwSelectFolder('${esc}', this)"
                          ondblclick="_brwNavigate('${esc}')">
                <span class="icon">📁</span>
                <span class="name">${f.name}</span>
            </div>`;
        }

        // Files (only in file mode)
        if (_brwMode === "file") {
            for (const f of (data.files || [])) {
                const esc = f.path.replace(/\\/g, "\\\\").replace(/'/g, "\\'");
                const size = _brwFormatSize(f.size);
                const mtime = f.mtime ? new Date(f.mtime * 1000).toLocaleString() : "";
                html += `<div class="brw-item" onclick="_brwSelectFile('${esc}', this)" ondblclick="_brwSelectFileAndConfirm('${esc}')">
                    <span class="icon">📄</span>
                    <span class="name">${f.name}</span>
                    <span class="meta">${size}</span>
                    <span class="meta">${mtime}</span>
                </div>`;
            }
        }

        if (!html) {
            html = '<div style="padding:20px; text-align:center; color:var(--fg-dim);">Empty folder</div>';
        }

        listing.innerHTML = html;

    } catch (e) {
        toast(`Browse error: ${e.message}`, "error");
    }
}

function _brwRenderBreadcrumb(fullPath) {
    const el = $("#brw-breadcrumb");
    // Split path into segments: "C:\Users\foo" → ["C:", "Users", "foo"]
    const parts = fullPath.replace(/[/\\]+$/, "").split(/[/\\]/);
    let html = "";
    let accumulated = "";
    for (let i = 0; i < parts.length; i++) {
        if (i === 0 && /^[A-Za-z]:$/.test(parts[i])) {
            accumulated = parts[i] + "\\";
        } else {
            accumulated += (i > 1 || !/^[A-Za-z]:$/.test(parts[0]) ? "\\" : "") + parts[i];
        }
        const esc = accumulated.replace(/\\/g, "\\\\").replace(/'/g, "\\'");
        if (i > 0) html += `<span class="brw-crumb-sep">›</span>`;
        html += `<span class="brw-crumb" onclick="_brwNavigate('${esc}')">${parts[i]}</span>`;
    }
    el.innerHTML = html;
}

function _brwSelectFolder(path, el) {
    // In folder mode, clicking a folder selects it; double-click navigates into it
    if (_brwMode === "folder") {
        _brwSelected = path;
        $("#brw-selected").textContent = path;
        $("#brw-confirm-btn").disabled = false;
    }
    // Visual highlight
    $$(".brw-item.selected").forEach(e => e.classList.remove("selected"));
    el.classList.add("selected");
}

function _brwSelectFile(path, el) {
    _brwSelected = path;
    $("#brw-selected").textContent = path.split(/[/\\]/).pop();
    $("#brw-confirm-btn").disabled = false;
    $$(".brw-item.selected").forEach(e => e.classList.remove("selected"));
    el.classList.add("selected");
}

function _brwSelectFileAndConfirm(path) {
    _brwSelected = path;
    brwConfirm();
}

function _brwFormatSize(bytes) {
    if (bytes == null) return "";
    if (bytes < 1024) return bytes + " B";
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + " KB";
    return (bytes / (1024 * 1024)).toFixed(1) + " MB";
}

// ═══════════════════════════════════════════════════════════════════════════
// CSV Module (csv*)
// ═══════════════════════════════════════════════════════════════════════════

function csvInit() {
    // Drag-and-drop on the whole page
    document.body.addEventListener("dragover", (e) => { e.preventDefault(); e.stopPropagation(); });
    document.body.addEventListener("drop", async (e) => {
        e.preventDefault();
        e.stopPropagation();
        const files = e.dataTransfer?.files;
        if (files && files.length > 0) {
            const file = files[0];
            if (file.name.toLowerCase().endsWith(".csv")) {
                // For security, we need a server-side path. Prompt user.
                toast("Drag-drop: use Open CSV to select the file path", "error");
            }
        }
    });
}

async function csvOpenFile() {
    const startDir = csvState.path
        ? csvState.path.replace(/[/\\][^/\\]+$/, "")
        : csvState.folder || "";
    const path = await brwOpen("file", startDir);
    if (!path) return;
    await csvLoadFile(path);
}

async function csvOpenFolder() {
    const startDir = csvState.folder || (csvState.path ? csvState.path.replace(/[/\\][^/\\]+$/, "") : "");
    const folder = await brwOpen("folder", startDir);
    if (!folder) return;
    try {
        const resp = await api("/api/csv/load-folder", {
            method: "POST",
            body: { folder: folder.trim(), recursive: cfgSettings.recursiveFolder },
        });
        const data = await resp.json();
        csvOnLoaded(data);
        toast(`Loaded newest: ${data.path?.split(/[/\\]/).pop()}`);
    } catch (e) {
        toast(e.message, "error");
    }
}

async function csvLoadFile(path) {
    try {
        const resp = await api("/api/csv/load", {
            method: "POST",
            body: { path },
        });
        const data = await resp.json();
        csvOnLoaded(data);
        toast(`Loaded: ${path.split(/[/\\]/).pop()}`);
    } catch (e) {
        toast(e.message, "error");
    }
}

async function csvReload() {
    try {
        const resp = await api("/api/csv/reload", { method: "POST" });
        const data = await resp.json();
        csvOnLoaded(data);
        toast("Reloaded");
    } catch (e) {
        toast(e.message, "error");
    }
}

function csvOnLoaded(data) {
    csvState.path = data.path;
    csvState.columns = data.columns || [];
    csvState.rows = data.rows || 0;
    csvState.separator = data.separator;
    csvState.timestampScale = data.timestamp_scale || 1.0;
    csvState.fileSize = data.file_size || null;

    // Update file info
    const fname = (data.path || "").split(/[/\\]/).pop();
    const folder = (data.path || "").replace(/[/\\][^/\\]+$/, "");
    const ncols = csvState.columns.length;
    let info = `<strong>${fname || "—"}</strong><br>`;
    info += `Rows: ${csvState.rows.toLocaleString()}  Cols: ${ncols}`;
    if (data.separator) info += `  Sep: <code>${data.separator === "\t" ? "TAB" : data.separator}</code>`;
    if (csvState.fileSize != null) info += `  Size: ${_brwFormatSize(csvState.fileSize)}`;
    if (folder) info += `<br><span style="font-size:10px;color:var(--fg-dim);">${folder}</span>`;
    $("#file-info").innerHTML = info;

    // Refresh history display
    _hstRefresh();

    // Refresh all subplot column lists
    subRenderAllColumns();

    // Hide empty state
    const es = $("#empty-state");
    if (es) es.style.display = "none";

    // Auto-add first subplot if none exist
    if (subplots.length === 0) {
        subAdd();
    }
}

// ═══════════════════════════════════════════════════════════════════════════
// Subplot Module (sub*)
// ═══════════════════════════════════════════════════════════════════════════

function subAdd(cfg) {
    const id = subIdCounter++;
    const sub = {
        id,
        columns: cfg?.columns || [],
        mode: cfg?.mode || "Time series",
        x_window: cfg?.x_window || null,
        ylim: cfg?.ylim || { enabled: false, ymin: "", ymax: "" },
        barriers: cfg?.barriers || { enabled: false, target: "", limit_in: "", limit_out: "", start_idx: "", end_idx: "" },
        customCode: cfg?.customCode || "def transform(x, signals, df):\n    return signals",
        alignment: cfg?.alignment || "aligned",
        file_shifts: cfg?.file_shifts || {},
        file_enabled: cfg?.file_enabled || {},
        showStats: cfg?.showStats !== undefined ? cfg.showStats : true,
        searchFilter: "",
    };
    subplots.push(sub);

    // Create selector panel in sidebar
    _subRenderSelector(sub);
    // Create plot container in main area
    _subRenderPlotContainer(sub);

    return sub;
}

function subRemove(id) {
    subplots = subplots.filter(s => s.id !== id);
    const sel = $(`#sub-sel-${id}`);
    if (sel) sel.remove();
    const plot = $(`#plot-ctr-${id}`);
    if (plot) plot.remove();
    if (subplots.length === 0) {
        const es = $("#empty-state");
        if (es) es.style.display = "";
    }
}

function subDuplicate(id) {
    const src = subplots.find(s => s.id === id);
    if (!src) return;
    subAdd({
        columns: [...src.columns],
        mode: src.mode,
        ylim: { ...src.ylim },
        barriers: { ...src.barriers },
        customCode: src.customCode,
        alignment: src.alignment,
        file_shifts: { ...src.file_shifts },
        file_enabled: { ...src.file_enabled },
    });
}

function subGetConfig(id) {
    return subplots.find(s => s.id === id) || null;
}

function _subRenderSelector(sub) {
    const container = $("#subplot-selectors");
    const panel = document.createElement("div");
    panel.className = "subplot-panel";
    panel.id = `sub-sel-${sub.id}`;

    const idx = subplots.indexOf(sub) + 1;

    panel.innerHTML = `
        <div class="subplot-header">
            <span>Subplot ${idx}</span>
            <div class="actions">
                <button class="sm" onclick="subDuplicate(${sub.id})" title="Duplicate">📋</button>
                <button class="sm danger" onclick="subRemove(${sub.id})" title="Remove">✕</button>
            </div>
        </div>
        <div class="subplot-body">
            <div class="mode-row">
                <span style="font-size:11px;color:var(--fg-dim);">Mode:</span>
                <select id="sub-mode-${sub.id}" onchange="_subModeChanged(${sub.id})">
                    ${PLOT_MODES.map(m => `<option value="${m}" ${m === sub.mode ? "selected" : ""}>${m}</option>`).join("")}
                </select>
            </div>
            <div class="search-box">
                <input type="text" placeholder="🔍 Filter columns..." id="sub-search-${sub.id}"
                       oninput="_subFilterColumns(${sub.id})">
            </div>
            <div class="column-list" id="sub-cols-${sub.id}">
                <!-- columns rendered dynamically -->
            </div>
            <div style="margin-top:4px; display:flex; gap:4px; align-items:center;">
                <button class="sm" onclick="_subSelectAll(${sub.id})">All</button>
                <button class="sm" onclick="_subSelectNone(${sub.id})">None</button>
                <button class="sm" onclick="_subInvert(${sub.id})">Invert</button>
                <span style="flex:1;"></span>
                <span id="sub-col-count-${sub.id}" style="font-size:10px;color:var(--fg-dim);"></span>
            </div>
            <div class="ylim-row">
                <label><input type="checkbox" id="sub-ylim-en-${sub.id}"
                       ${sub.ylim.enabled ? "checked" : ""}
                       onchange="_subYlimChanged(${sub.id})"> Y-lim:</label>
                <input type="text" id="sub-ylim-min-${sub.id}" value="${sub.ylim.ymin}" placeholder="min"
                       onchange="_subYlimChanged(${sub.id})">
                <span>–</span>
                <input type="text" id="sub-ylim-max-${sub.id}" value="${sub.ylim.ymax}" placeholder="max"
                       onchange="_subYlimChanged(${sub.id})">
            </div>
            <!-- Barrier Config (for Abs check / Rel change) -->
            <div class="barrier-section" id="sub-barrier-${sub.id}"
                 style="display:${sub.mode === "Abs check" || sub.mode === "Rel change" ? "block" : "none"}; margin-top:6px; border-top:1px solid var(--border); padding-top:6px;">
                <label style="font-size:11px;"><input type="checkbox" id="sub-barr-en-${sub.id}"
                       ${sub.barriers.enabled ? "checked" : ""}
                       onchange="_subBarrierChanged(${sub.id})"> Barriers</label>
                <div id="sub-barr-fields-${sub.id}" style="display:${sub.barriers.enabled ? "block" : "none"}; margin-top:4px;">
                    <div class="barrier-row">
                        <span>Target:</span>
                        <input type="text" id="sub-barr-target-${sub.id}" value="${sub.barriers.target || ""}"
                               placeholder="e.g. 3.3" onchange="_subBarrierChanged(${sub.id})">
                    </div>
                    <div class="barrier-row">
                        <span>Limit In:</span>
                        <input type="text" id="sub-barr-lim-in-${sub.id}" value="${sub.barriers.limit_in || ""}"
                               placeholder="e.g. 0.1" onchange="_subBarrierChanged(${sub.id})">
                    </div>
                    <div class="barrier-row">
                        <span>Limit Out:</span>
                        <input type="text" id="sub-barr-lim-out-${sub.id}" value="${sub.barriers.limit_out || ""}"
                               placeholder="e.g. 0.2" onchange="_subBarrierChanged(${sub.id})">
                    </div>
                    <div class="barrier-row">
                        <span>Start idx:</span>
                        <input type="text" id="sub-barr-start-${sub.id}" value="${sub.barriers.start_idx || ""}"
                               placeholder="0" onchange="_subBarrierChanged(${sub.id})">
                        <span>End:</span>
                        <input type="text" id="sub-barr-end-${sub.id}" value="${sub.barriers.end_idx || ""}"
                               placeholder="end" onchange="_subBarrierChanged(${sub.id})">
                    </div>
                </div>
            </div>
            <div class="overlay-section" id="sub-overlay-${sub.id}">
                <div style="display:flex; align-items:center; justify-content:space-between; margin-bottom:4px;">
                    <span style="font-size:11px; color:var(--fg-dim);">Overlay files</span>
                    <div style="display:flex;gap:4px;">
                        <button class="sm" onclick="ovlAddFile(${sub.id})">+ Add</button>
                        <button class="sm danger" onclick="ovlClearAll(${sub.id})">Clear</button>
                    </div>
                </div>
                <div style="margin-bottom:4px; display:flex; gap:4px; align-items:center;">
                    <span style="font-size:10px; color:var(--fg-dim);">X-align:</span>
                    <select id="sub-align-${sub.id}" style="width:auto;font-size:11px;padding:2px 4px;"
                            onchange="_subAlignChanged(${sub.id})">
                        <option value="aligned" ${sub.alignment === "aligned" ? "selected" : ""}>Aligned</option>
                        <option value="independent" ${sub.alignment === "independent" ? "selected" : ""}>Independent</option>
                    </select>
                </div>
                <div id="ovl-files-${sub.id}"></div>
            </div>
            <div class="custom-code-area" id="sub-custom-${sub.id}"
                 style="display:${sub.mode === "Custom code" ? "block" : "none"}">
                <textarea id="sub-code-${sub.id}" rows="5"
                          placeholder="def transform(x, signals, df):&#10;    return signals"
                >${sub.customCode}</textarea>
            </div>
            <div style="margin-top:8px;">
                <button class="primary sm" onclick="pltRender(${sub.id})" style="width:100%;">▶ Plot</button>
            </div>
        </div>
    `;
    container.appendChild(panel);

    // Render column checkboxes
    _subRenderColumns(sub);
}

function _subRenderPlotContainer(sub) {
    const panels = $("#plot-panels");
    const es = $("#empty-state");
    if (es) es.style.display = "none";

    const ctr = document.createElement("div");
    ctr.className = "plot-container";
    ctr.id = `plot-ctr-${sub.id}`;

    const idx = subplots.indexOf(sub) + 1;
    ctr.innerHTML = `
        <div class="plot-title">
            <span>Subplot ${idx}: <span id="plot-mode-label-${sub.id}">${sub.mode}</span></span>
            <div style="display:flex;gap:4px;align-items:center;">
                <button class="sm" onclick="pltExportSubPng(${sub.id})" title="Export this subplot as PNG">📷</button>
                <button class="sm" onclick="pltExportSubSvg(${sub.id})" title="Export this subplot as SVG">📐</button>
                <label style="font-size:10px;"><input type="checkbox" id="chk-stats-${sub.id}" ${sub.showStats ? "checked" : ""}
                       onchange="_subToggleStats(${sub.id})"> Stats</label>
            </div>
        </div>
        <div class="plot-div" id="plot-${sub.id}"></div>
        <div class="stats-section" id="stats-${sub.id}" style="display:${sub.showStats ? "" : "none"};"></div>
    `;
    panels.appendChild(ctr);
}

function _subRenderColumns(sub) {
    const container = $(`#sub-cols-${sub.id}`);
    if (!container) return;

    const filter = sub.searchFilter.toLowerCase();
    const cols = csvState.columns.filter(c => c !== "Timestamp" && c.toLowerCase().includes(filter));

    container.innerHTML = cols.map(col => {
        const checked = sub.columns.includes(col);
        return `<label class="${checked ? "checked" : ""}">
            <input type="checkbox" ${checked ? "checked" : ""}
                   onchange="_subColToggled(${sub.id}, '${col.replace(/'/g, "\\'")}', this.checked)">
            ${col}
        </label>`;
    }).join("");

    // Update column count
    const countEl = $(`#sub-col-count-${sub.id}`);
    if (countEl) {
        const total = csvState.columns.filter(c => c !== "Timestamp").length;
        countEl.textContent = `${sub.columns.length}/${total}`;
    }
}

function subRenderAllColumns() {
    subplots.forEach(sub => _subRenderColumns(sub));
}

function _subFilterColumns(id) {
    const sub = subGetConfig(id);
    if (!sub) return;
    sub.searchFilter = $(`#sub-search-${id}`)?.value || "";
    _subRenderColumns(sub);
}

function _subColToggled(id, col, checked) {
    const sub = subGetConfig(id);
    if (!sub) return;
    if (checked && !sub.columns.includes(col)) {
        sub.columns.push(col);
    } else if (!checked) {
        sub.columns = sub.columns.filter(c => c !== col);
    }
    _subRenderColumns(sub);
}

function _subSelectAll(id) {
    const sub = subGetConfig(id);
    if (!sub) return;
    const filter = sub.searchFilter.toLowerCase();
    sub.columns = csvState.columns.filter(c => c !== "Timestamp" && c.toLowerCase().includes(filter));
    _subRenderColumns(sub);
}

function _subSelectNone(id) {
    const sub = subGetConfig(id);
    if (!sub) return;
    sub.columns = [];
    _subRenderColumns(sub);
}

function _subInvert(id) {
    const sub = subGetConfig(id);
    if (!sub) return;
    const all = csvState.columns.filter(c => c !== "Timestamp");
    sub.columns = all.filter(c => !sub.columns.includes(c));
    _subRenderColumns(sub);
}

function _subModeChanged(id) {
    const sub = subGetConfig(id);
    if (!sub) return;
    sub.mode = $(`#sub-mode-${id}`).value;
    const customArea = $(`#sub-custom-${id}`);
    if (customArea) customArea.style.display = sub.mode === "Custom code" ? "block" : "none";
    const barrierArea = $(`#sub-barrier-${id}`);
    if (barrierArea) barrierArea.style.display = (sub.mode === "Abs check" || sub.mode === "Rel change") ? "block" : "none";
    const lbl = $(`#plot-mode-label-${id}`);
    if (lbl) lbl.textContent = sub.mode;
    _layScheduleAutoSave();
}

function _subYlimChanged(id) {
    const sub = subGetConfig(id);
    if (!sub) return;
    sub.ylim = {
        enabled: $(`#sub-ylim-en-${id}`)?.checked || false,
        ymin: $(`#sub-ylim-min-${id}`)?.value || "",
        ymax: $(`#sub-ylim-max-${id}`)?.value || "",
    };
    _layScheduleAutoSave();
}

function _subAlignChanged(id) {
    const sub = subGetConfig(id);
    if (!sub) return;
    sub.alignment = $(`#sub-align-${id}`)?.value || "aligned";
    _layScheduleAutoSave();
}

function _subBarrierChanged(id) {
    const sub = subGetConfig(id);
    if (!sub) return;
    const enabled = $(`#sub-barr-en-${id}`)?.checked || false;
    sub.barriers = {
        enabled,
        target: $(`#sub-barr-target-${id}`)?.value || "",
        limit_in: $(`#sub-barr-lim-in-${id}`)?.value || "",
        limit_out: $(`#sub-barr-lim-out-${id}`)?.value || "",
        start_idx: $(`#sub-barr-start-${id}`)?.value || "",
        end_idx: $(`#sub-barr-end-${id}`)?.value || "",
    };
    // Show/hide detail fields
    const fieldsEl = $(`#sub-barr-fields-${id}`);
    if (fieldsEl) fieldsEl.style.display = enabled ? "block" : "none";
    _layScheduleAutoSave();
}

function _subToggleStats(id) {
    const sub = subGetConfig(id);
    const statsEl = $(`#stats-${id}`);
    if (!statsEl) return;
    const show = $(`#chk-stats-${id}`)?.checked;
    if (sub) sub.showStats = !!show;
    statsEl.style.display = show ? "" : "none";
    _layScheduleAutoSave();
}

// ═══════════════════════════════════════════════════════════════════════════
// Plot Module (plt*)
// ═══════════════════════════════════════════════════════════════════════════

async function pltRender(id) {
    const sub = subGetConfig(id);
    if (!sub) return;
    if (!csvState.path && sub.mode !== "Custom code") {
        toast("No CSV loaded", "error");
        return;
    }
    if (sub.columns.length === 0) {
        toast("No columns selected", "error");
        return;
    }

    const plotDiv = $(`#plot-${id}`);
    if (!plotDiv) return;

    // Read current custom code from textarea
    if (sub.mode === "Custom code") {
        const ta = $(`#sub-code-${id}`);
        if (ta) sub.customCode = ta.value;
    }

    const subplotCfg = {
        alignment: sub.alignment,
        file_shifts: sub.file_shifts,
        file_enabled: sub.file_enabled,
    };

    try {
        let endpoint, body;

        // Build barriers dict for abs/rel check modes
        const barrierPayload = sub.barriers.enabled ? {
            target: parseFloat(sub.barriers.target) || 0,
            limit_in: parseFloat(sub.barriers.limit_in) || 0,
            limit_out: parseFloat(sub.barriers.limit_out) || 0,
            start_idx: sub.barriers.start_idx ? parseInt(sub.barriers.start_idx) : 0,
            end_idx: sub.barriers.end_idx ? parseInt(sub.barriers.end_idx) : null,
        } : null;

        switch (sub.mode) {
            case "Time series":
                endpoint = "/api/plot-data/timeseries";
                body = {
                    columns: sub.columns,
                    x_window: sub.x_window,
                    max_points: cfgSettings.maxPoints,
                    subplot_cfg: subplotCfg,
                };
                break;
            case "Histogram":
                endpoint = "/api/plot-data/histogram";
                body = {
                    columns: sub.columns,
                    x_window: sub.x_window,
                    nbins: cfgSettings.histBins,
                    subplot_cfg: subplotCfg,
                };
                break;
            case "Abs check":
                endpoint = "/api/plot-data/abs-check";
                body = {
                    columns: sub.columns,
                    barriers: barrierPayload,
                    max_points: cfgSettings.maxPoints,
                    subplot_cfg: subplotCfg,
                };
                break;
            case "Rel change":
                endpoint = "/api/plot-data/rel-change";
                body = {
                    columns: sub.columns,
                    barriers: barrierPayload,
                    max_points: cfgSettings.maxPoints,
                    subplot_cfg: subplotCfg,
                };
                break;
            case "Custom code":
                endpoint = "/api/plot-data/custom-code";
                body = {
                    columns: sub.columns,
                    code: sub.customCode,
                    x_window: sub.x_window,
                    max_points: cfgSettings.maxPoints,
                };
                break;
            default:
                endpoint = "/api/plot-data/timeseries";
                body = { columns: sub.columns, max_points: cfgSettings.maxPoints, subplot_cfg: subplotCfg };
        }

        const resp = await api(endpoint, { method: "POST", body });
        const data = await resp.json();

        if (data.error) {
            toast(data.error, "error");
            return;
        }

        // Apply colors
        (data.traces || []).forEach((tr, i) => {
            if (!tr.line) tr.line = {};
            if (!tr.line.color && !tr.marker) {
                tr.line.color = PLOTLY_COLORS[i % PLOTLY_COLORS.length];
            }
            if (tr.type === "bar" && !tr.marker) {
                tr.marker = { color: PLOTLY_COLORS[i % PLOTLY_COLORS.length], opacity: 0.7 };
            }
        });

        const layout = {
            ...PLOTLY_LAYOUT,
            ...(data.layout || {}),
        };

        // Apply Y-limits
        if (sub.ylim.enabled) {
            if (!layout.yaxis) layout.yaxis = { ...PLOTLY_LAYOUT.yaxis };
            const range = [];
            if (sub.ylim.ymin !== "") range.push(parseFloat(sub.ylim.ymin));
            else range.push(undefined);
            if (sub.ylim.ymax !== "") range.push(parseFloat(sub.ylim.ymax));
            else range.push(undefined);
            if (range[0] !== undefined || range[1] !== undefined) {
                layout.yaxis.range = range;
            }
        }

        Plotly.react(plotDiv, data.traces || [], layout, {
            responsive: true,
            displayModeBar: true,
            modeBarButtonsToRemove: ["lasso2d", "select2d"],
        });

        // Apply highlight: dim traces not in _highlightedSignals
        if (_highlightedSignals.size > 0 && (data.traces || []).length > 0) {
            const updates = { opacity: [] };
            for (const tr of (data.traces || [])) {
                const name = tr.name || "";
                updates.opacity.push(_highlightedSignals.has(name) ? 1.0 : 0.2);
            }
            Plotly.restyle(plotDiv, { opacity: updates.opacity.map((o, i) => o) },
                (data.traces || []).map((_, i) => i));
        }

        // Zoom sync: on relayout, update x_window and optionally sync
        plotDiv.removeAllListeners?.("plotly_relayout");
        plotDiv.on("plotly_relayout", (evt) => {
            if (evt["xaxis.range[0]"] !== undefined && evt["xaxis.range[1]"] !== undefined) {
                sub.x_window = [evt["xaxis.range[0]"], evt["xaxis.range[1]"]];
                pltSyncXRange(id, sub.x_window);
            } else if (evt["xaxis.autorange"]) {
                sub.x_window = null;
                pltSyncXRange(id, null);
            }
        });

        // Render metrics table
        if (data.metrics && sub.showStats) {
            staRender(id, data.metrics);
        }

    } catch (e) {
        toast(`Plot error: ${e.message}`, "error");
    }
}

async function pltRenderAll() {
    const start = performance.now();
    for (const sub of subplots) {
        await pltRender(sub.id);
    }
    const elapsed = ((performance.now() - start) / 1000).toFixed(1);
    $("#toolbar-status").textContent = `Plotted ${subplots.length} subplot(s) in ${elapsed}s`;
}

function pltSyncXRange(sourceId, xRange) {
    // Sync all time-series subplots to the same x-range
    for (const sub of subplots) {
        if (sub.id === sourceId) continue;
        if (sub.mode !== "Time series") continue;
        sub.x_window = xRange;
        const plotDiv = $(`#plot-${sub.id}`);
        if (!plotDiv) continue;
        if (xRange) {
            Plotly.relayout(plotDiv, { "xaxis.range": xRange });
        } else {
            Plotly.relayout(plotDiv, { "xaxis.autorange": true });
        }
    }
}

async function pltExportPng() {
    if (!csvState.path) { toast("No CSV loaded", "error"); return; }
    const allCols = subplots.flatMap(s => s.columns);
    if (allCols.length === 0) { toast("No columns selected", "error"); return; }
    try {
        const resp = await fetch("/api/plot/png", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ columns: [...new Set(allCols)], width: 1600, height: 900 }),
        });
        const blob = await resp.blob();
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = (csvState.path?.split(/[/\\]/).pop() || "plot") + ".png";
        a.click();
        URL.revokeObjectURL(url);
        toast("PNG exported");
    } catch (e) {
        toast(`Export failed: ${e.message}`, "error");
    }
}

async function pltExportSvg() {
    if (!csvState.path) { toast("No CSV loaded", "error"); return; }
    const allCols = subplots.flatMap(s => s.columns);
    if (allCols.length === 0) { toast("No columns selected", "error"); return; }
    try {
        const resp = await fetch("/api/plot/svg", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ columns: [...new Set(allCols)], width: 1600, height: 900 }),
        });
        const blob = await resp.blob();
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = (csvState.path?.split(/[/\\]/).pop() || "plot") + ".svg";
        a.click();
        URL.revokeObjectURL(url);
        toast("SVG exported");
    } catch (e) {
        toast(`Export failed: ${e.message}`, "error");
    }
}

// Per-subplot export via Plotly.downloadImage
function pltExportSubPng(id) {
    const plotDiv = $(`#plot-${id}`);
    if (!plotDiv) return;
    const fname = (csvState.path?.split(/[/\\]/).pop() || "subplot") + `_${id}.png`;
    Plotly.downloadImage(plotDiv, { format: "png", width: 1600, height: 600, filename: fname.replace(".png", "") });
    toast("PNG exported");
}

function pltExportSubSvg(id) {
    const plotDiv = $(`#plot-${id}`);
    if (!plotDiv) return;
    const fname = (csvState.path?.split(/[/\\]/).pop() || "subplot") + `_${id}.svg`;
    Plotly.downloadImage(plotDiv, { format: "svg", width: 1600, height: 600, filename: fname.replace(".svg", "") });
    toast("SVG exported");
}

// ═══════════════════════════════════════════════════════════════════════════
// Stats Module (sta*)
// ═══════════════════════════════════════════════════════════════════════════

function staRender(subplotId, metrics) {
    const el = $(`#stats-${subplotId}`);
    if (!el) return;

    const keys = Object.keys(metrics).filter(k => metrics[k] !== null);
    if (keys.length === 0) {
        el.innerHTML = "";
        return;
    }

    const headers = ["Signal", "Min", "Max", "Avg", "Median", "P2P", "StdDev", "RMS", "Crest", "Freq", "Period"];
    const fields = ["min", "max", "avg", "med", "p2p", "std", "rms", "crest", "freq", "period"];

    let html = `<div style="font-size:10px;color:var(--fg-dim);margin-bottom:4px;">${keys.length} signal(s)</div>`;
    html += `<table class="stats-table"><thead><tr>`;
    headers.forEach((h, i) => {
        html += `<th onclick="staSort(${subplotId}, ${i})">${h}</th>`;
    });
    html += `</tr></thead><tbody>`;

    keys.forEach((sig, rowIdx) => {
        const m = metrics[sig];
        const highlighted = _highlightedSignals.has(sig) ? " highlighted" : "";
        const stripe = rowIdx % 2 === 1 ? " style=\"background:var(--bg3);\"" : "";
        html += `<tr class="${highlighted}"${stripe} onclick="staRowClick('${sig.replace(/'/g, "\\'")}')">`;
        html += `<td>${sig}</td>`;
        fields.forEach(f => {
            html += `<td>${m?.[f] ?? "n/a"}</td>`;
        });
        html += `</tr>`;
    });

    html += `</tbody></table>`;
    html += `<div style="margin-top:4px;"><button class="sm" onclick="staCopy(${subplotId})">📋 Copy</button></div>`;
    el.innerHTML = html;
}

function staSort(subplotId, colIndex) {
    const el = $(`#stats-${subplotId}`);
    if (!el) return;
    const table = el.querySelector("table");
    if (!table) return;

    const tbody = table.querySelector("tbody");
    const rows = Array.from(tbody.querySelectorAll("tr"));

    const asc = table.dataset.sortCol == colIndex && table.dataset.sortDir === "asc";
    table.dataset.sortCol = colIndex;
    table.dataset.sortDir = asc ? "desc" : "asc";

    rows.sort((a, b) => {
        const av = a.querySelectorAll("td")[colIndex]?.textContent || "";
        const bv = b.querySelectorAll("td")[colIndex]?.textContent || "";
        const an = parseFloat(av), bn = parseFloat(bv);
        if (!isNaN(an) && !isNaN(bn)) return asc ? bn - an : an - bn;
        return asc ? bv.localeCompare(av) : av.localeCompare(bv);
    });

    rows.forEach(r => tbody.appendChild(r));
}

function staRowClick(sig) {
    if (_highlightedSignals.has(sig)) {
        _highlightedSignals.delete(sig);
    } else {
        _highlightedSignals.add(sig);
    }
    // Re-render stats for all subplots (highlight rows)
    subplots.forEach(sub => {
        const statsEl = $(`#stats-${sub.id}`);
        if (statsEl) {
            const rows = statsEl.querySelectorAll("tbody tr");
            rows.forEach(r => {
                const firstTd = r.querySelector("td");
                if (firstTd) {
                    const rowSig = firstTd.textContent;
                    r.classList.toggle("highlighted", _highlightedSignals.has(rowSig));
                }
            });
        }
        // Also restyle Plotly traces for highlight opacity
        const plotDiv = $(`#plot-${sub.id}`);
        if (plotDiv && plotDiv.data) {
            if (_highlightedSignals.size > 0) {
                const opacities = plotDiv.data.map(tr => _highlightedSignals.has(tr.name) ? 1.0 : 0.2);
                Plotly.restyle(plotDiv, { opacity: opacities }, plotDiv.data.map((_, i) => i));
            } else {
                Plotly.restyle(plotDiv, { opacity: 1.0 }, plotDiv.data.map((_, i) => i));
            }
        }
    });
}

function staCopy(subplotId) {
    const el = $(`#stats-${subplotId}`);
    if (!el) return;
    const table = el.querySelector("table");
    if (!table) return;

    const lines = [];
    table.querySelectorAll("tr").forEach(row => {
        const cells = Array.from(row.querySelectorAll("th, td")).map(c => c.textContent);
        lines.push(cells.join("\t"));
    });
    navigator.clipboard.writeText(lines.join("\n")).then(
        () => toast("Copied to clipboard"),
        () => toast("Copy failed", "error")
    );
}

// ═══════════════════════════════════════════════════════════════════════════
// Overlay Module (ovl*)
// ═══════════════════════════════════════════════════════════════════════════

async function ovlAddFile(subplotId) {
    const startDir = csvState.path
        ? csvState.path.replace(/[/\\][^/\\]+$/, "")
        : csvState.folder || "";
    const path = await brwOpen("file", startDir);
    if (!path) return;
    try {
        const resp = await api("/api/overlay/add", { method: "POST", body: { path } });
        const data = await resp.json();
        ovlRender(subplotId, data.files);
        toast(`Overlay added: ${path.split(/[/\\]/).pop()}`);
    } catch (e) {
        toast(e.message, "error");
    }
}

function ovlRender(subplotId, files) {
    const el = $(`#ovl-files-${subplotId}`);
    if (!el) return;
    const sub = subGetConfig(subplotId);

    if (!files || files.length === 0) {
        el.innerHTML = '<span style="font-size:10px;color:var(--fg-dim);">No overlays</span>';
        return;
    }

    el.innerHTML = files.map((f, i) => {
        const name = f.path.split(/[/\\]/).pop();
        const enabled = sub ? (sub.file_enabled[f.path] !== false) : true;
        const xShift = sub ? (sub.file_shifts[f.path]?.x || 0) : 0;
        const yShift = sub ? (sub.file_shifts[f.path]?.y || 0) : 0;
        return `<div class="overlay-file" style="flex-wrap:wrap;">
            <input type="checkbox" ${enabled ? "checked" : ""} onchange="_ovlToggle(${subplotId}, '${f.path.replace(/\\/g, "\\\\").replace(/'/g, "\\'")}', this.checked)">
            <span class="path" title="${f.path}">${name}</span>
            <span style="color:var(--fg-dim);font-size:10px;">(${f.rows}r)</span>
            <button class="sm danger" onclick="ovlRemoveFile(${subplotId}, ${i})">✕</button>
            <div style="display:flex;gap:3px;width:100%;margin-top:2px;font-size:10px;align-items:center;">
                <span style="color:var(--fg-dim);">ΔX:</span>
                <input type="number" value="${xShift}" step="0.1" style="width:55px;padding:1px 3px;font-size:10px;"
                       onchange="_ovlShiftChanged(${subplotId}, '${f.path.replace(/\\/g, "\\\\").replace(/'/g, "\\'")}', 'x', this.value)">
                <span style="color:var(--fg-dim);">ΔY:</span>
                <input type="number" value="${yShift}" step="0.1" style="width:55px;padding:1px 3px;font-size:10px;"
                       onchange="_ovlShiftChanged(${subplotId}, '${f.path.replace(/\\/g, "\\\\").replace(/'/g, "\\'")}', 'y', this.value)">
            </div>
        </div>`;
    }).join("");
}

async function ovlRemoveFile(subplotId, idx) {
    try {
        const resp = await api(`/api/overlay/${idx}`, { method: "DELETE" });
        const data = await resp.json();
        ovlRender(subplotId, data.files);
    } catch (e) {
        toast(e.message, "error");
    }
}

function _ovlToggle(subplotId, filePath, enabled) {
    const sub = subGetConfig(subplotId);
    if (!sub) return;
    sub.file_enabled[filePath] = enabled;
    _layScheduleAutoSave();
}

function _ovlShiftChanged(subplotId, filePath, axis, value) {
    const sub = subGetConfig(subplotId);
    if (!sub) return;
    if (!sub.file_shifts[filePath]) sub.file_shifts[filePath] = { x: 0, y: 0 };
    sub.file_shifts[filePath][axis] = parseFloat(value) || 0;
    _layScheduleAutoSave();
}

async function ovlClearAll(subplotId) {
    try {
        const resp = await api("/api/overlay/clear", { method: "POST" });
        const data = await resp.json();
        ovlRender(subplotId, data.files);
        const sub = subGetConfig(subplotId);
        if (sub) {
            sub.file_shifts = {};
            sub.file_enabled = {};
        }
        toast("Overlays cleared");
    } catch (e) {
        toast(e.message, "error");
    }
}

// ═══════════════════════════════════════════════════════════════════════════
// History Module (hst*)
// ═══════════════════════════════════════════════════════════════════════════

async function _hstRefresh() {
    try {
        const resp = await api("/api/history");
        const data = await resp.json();
        _historyList = data.history || [];
        _historyIndex = data.current_index ?? -1;
        _hstRenderButtons();
    } catch (_) {}
}

function _hstRenderButtons() {
    const el = $("#hst-controls");
    if (!el) return;
    el.innerHTML = `
        <button class="sm" onclick="hstPrev()" ${_historyIndex <= 0 ? "disabled" : ""} title="Ctrl+←">◀</button>
        <select id="hst-select" style="flex:1;font-size:11px;padding:2px 4px;" onchange="hstGoto()">
            ${_historyList.map((p, i) => {
                const name = p.split(/[/\\]/).pop();
                return `<option value="${i}" ${i === _historyIndex ? "selected" : ""}>${name}</option>`;
            }).join("")}
            ${_historyList.length === 0 ? '<option value="-1">No history</option>' : ''}
        </select>
        <button class="sm" onclick="hstNext()" ${_historyIndex >= _historyList.length - 1 ? "disabled" : ""} title="Ctrl+→">▶</button>
        <button class="sm danger" onclick="hstClear()" title="Clear history">✕</button>
    `;
}

async function hstPrev() {
    try {
        const resp = await api("/api/history/navigate", { method: "POST", body: { direction: "prev" } });
        const data = await resp.json();
        if (data.path) {
            csvOnLoaded(data);
            await pltRenderAll();
        }
    } catch (e) {
        toast(e.message, "error");
    }
}

async function hstNext() {
    try {
        const resp = await api("/api/history/navigate", { method: "POST", body: { direction: "next" } });
        const data = await resp.json();
        if (data.path) {
            csvOnLoaded(data);
            await pltRenderAll();
        }
    } catch (e) {
        toast(e.message, "error");
    }
}

async function hstGoto() {
    const sel = $("#hst-select");
    if (!sel) return;
    const idx = parseInt(sel.value);
    if (idx < 0 || idx >= _historyList.length) return;
    const path = _historyList[idx];
    await csvLoadFile(path);
    await pltRenderAll();
}

async function hstClear() {
    try {
        await api("/api/history/clear", { method: "POST" });
        _historyList = [];
        _historyIndex = -1;
        _hstRenderButtons();
        toast("History cleared");
    } catch (e) {
        toast(e.message, "error");
    }
}

// ═══════════════════════════════════════════════════════════════════════════
// Layout Module (lay*)
// ═══════════════════════════════════════════════════════════════════════════

async function layInit() {
    try {
        const resp = await api("/api/layout");
        const data = await resp.json();
        if (data && data.subplots && data.subplots.length > 0) {
            layApply(data);
        }
    } catch (_) {
        // No saved layout — fine
    }
}

function layApply(data) {
    if (!data) return;

    // Restore settings
    if (data.auto_save_layout !== undefined) {
        cfgSettings.autoSaveLayout = !!data.auto_save_layout;
        const el = $("#cfg-auto-save-layout");
        if (el) el.checked = cfgSettings.autoSaveLayout;
    }
    if (data.hist_bins !== undefined) {
        cfgSettings.histBins = parseInt(data.hist_bins) || 50;
        const el = $("#cfg-hist-bins");
        if (el) el.value = cfgSettings.histBins;
    }
    if (data.recursive_folder !== undefined) {
        cfgSettings.recursiveFolder = !!data.recursive_folder;
        const el = $("#cfg-recursive-folder");
        if (el) el.checked = cfgSettings.recursiveFolder;
    }
    if (data.highlighted_channels && Array.isArray(data.highlighted_channels)) {
        _highlightedSignals = new Set(data.highlighted_channels);
    }

    // Restore subplots
    if (data.subplots && Array.isArray(data.subplots)) {
        // Clear existing
        [...subplots].forEach(s => subRemove(s.id));

        data.subplots.forEach(sc => {
            subAdd({
                columns: sc.selected_columns || [],
                mode: sc.plot_mode || "Time series",
                ylim: sc.ylim || { enabled: false, ymin: "", ymax: "" },
                barriers: sc.barriers || { enabled: false, target: "", limit_in: "", limit_out: "", start_idx: "", end_idx: "" },
                customCode: sc.customCode || "",
                alignment: sc.x_alignment || "aligned",
                file_shifts: sc.file_shifts || {},
                file_enabled: sc.file_enabled || {},
                x_window: sc.x_window || null,
                showStats: sc.showStats !== undefined ? sc.showStats : true,
            });
        });
    }

    // Load the CSV if specified
    if (data.last_loaded_file) {
        csvLoadFile(data.last_loaded_file);
    } else if (data.current_folder) {
        csvOpenFolder_path(data.current_folder);
    }
}

async function csvOpenFolder_path(folder) {
    try {
        const resp = await api("/api/csv/load-folder", {
            method: "POST",
            body: { folder, recursive: cfgSettings.recursiveFolder },
        });
        const data = await resp.json();
        csvOnLoaded(data);
    } catch (_) {}
}

async function laySave() {
    const data = layBuild();
    try {
        await api("/api/layout", { method: "POST", body: data });
        toast("Layout saved");
    } catch (e) {
        toast(`Save failed: ${e.message}`, "error");
    }
}

function layBuild() {
    return {
        version: 3,
        current_folder: csvState.folder,
        last_loaded_file: csvState.path,
        auto_save_layout: cfgSettings.autoSaveLayout,
        hist_bins: cfgSettings.histBins,
        recursive_folder: cfgSettings.recursiveFolder,
        highlighted_channels: [..._highlightedSignals],
        subplots: subplots.map(sub => ({
            selected_columns: sub.columns,
            plot_mode: sub.mode,
            ylim: sub.ylim,
            barriers: sub.barriers,
            customCode: sub.mode === "Custom code" ? ($(`#sub-code-${sub.id}`)?.value || sub.customCode) : sub.customCode,
            x_alignment: sub.alignment,
            file_shifts: sub.file_shifts,
            file_enabled: sub.file_enabled,
            x_window: sub.x_window,
            showStats: sub.showStats,
        })),
    };
}

async function layLoad() {
    try {
        const resp = await api("/api/layout");
        const data = await resp.json();
        if (data && data.subplots) {
            layApply(data);
            toast("Layout loaded");
        } else {
            toast("No saved layout found", "error");
        }
    } catch (e) {
        toast(`Load failed: ${e.message}`, "error");
    }
}

async function layClear() {
    if (!confirm("Clear layout and reset all subplots?")) return;
    try {
        await api("/api/layout", { method: "DELETE" });
        [...subplots].forEach(s => subRemove(s.id));
        toast("Layout cleared");
    } catch (e) {
        toast(`Clear failed: ${e.message}`, "error");
    }
}

function layAutoSave() {
    if (!cfgSettings.autoSaveLayout) return;
    const data = layBuild();
    fetch("/api/layout", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(data),
    }).catch(() => {});
}

/** Debounced auto-save: call this from any sub/ovl/barrier change handler */
function _layScheduleAutoSave() {
    if (!cfgSettings.autoSaveLayout) return;
    clearTimeout(_autoSaveDebounce);
    _autoSaveDebounce = setTimeout(layAutoSave, 2000);
}

// ═══════════════════════════════════════════════════════════════════════════
// Settings Module (cfg*)
// ═══════════════════════════════════════════════════════════════════════════

function cfgInit() {
    const el1 = $("#cfg-reload-interval");
    if (el1) el1.value = cfgSettings.reloadInterval;
    const el2 = $("#cfg-max-points");
    if (el2) el2.value = cfgSettings.maxPoints;
    const el3 = $("#cfg-auto-save-layout");
    if (el3) el3.checked = cfgSettings.autoSaveLayout;
    const el4 = $("#cfg-hist-bins");
    if (el4) el4.value = cfgSettings.histBins;
    const el5 = $("#cfg-recursive-folder");
    if (el5) el5.checked = cfgSettings.recursiveFolder;
}

function cfgApply() {
    cfgSettings.reloadInterval = parseInt($("#cfg-reload-interval")?.value || "1000") || 1000;
    cfgSettings.maxPoints = parseInt($("#cfg-max-points")?.value || "5000") || 5000;
    cfgSettings.autoSaveLayout = $("#cfg-auto-save-layout")?.checked ?? true;
    cfgSettings.histBins = parseInt($("#cfg-hist-bins")?.value || "50") || 50;
    cfgSettings.recursiveFolder = $("#cfg-recursive-folder")?.checked ?? true;

    // Restart timers
    if (cfgSettings.autoReload) {
        cfgToggleAutoReload();
        cfgToggleAutoReload();
    }
    if (cfgSettings.autoSaveLayout) {
        clearInterval(_autoSaveTimer);
        _autoSaveTimer = setInterval(layAutoSave, 30000);
    } else {
        clearInterval(_autoSaveTimer);
    }
    toast("Settings applied");
}

function cfgShowSettings() {
    cfgInit();
    $("#settingsModal").classList.add("show");
}

function cfgToggleAutoReload() {
    const checked = $("#chk-auto-reload")?.checked;
    cfgSettings.autoReload = !!checked;
    clearInterval(_autoReloadTimer);
    if (cfgSettings.autoReload) {
        _autoReloadTimer = setInterval(async () => {
            try {
                const resp = await api("/api/csv/check-mtime");
                const data = await resp.json();
                if (data.changed) {
                    await csvReload();
                    await pltRenderAll();
                }
            } catch (_) {}
        }, cfgSettings.reloadInterval);
    }
}

function cfgToggleAutoNewest() {
    const checked = $("#chk-auto-newest")?.checked;
    cfgSettings.autoNewest = !!checked;
    clearInterval(_autoNewestTimer);
    if (cfgSettings.autoNewest && csvState.folder) {
        _autoNewestTimer = setInterval(async () => {
            try {
                const resp = await api("/api/csv/load-folder", {
                    method: "POST",
                    body: { folder: csvState.folder, recursive: cfgSettings.recursiveFolder },
                });
                const data = await resp.json();
                if (data.path !== csvState.path) {
                    csvOnLoaded(data);
                    await pltRenderAll();
                }
            } catch (_) {}
        }, cfgSettings.reloadInterval);
    }
}

// ═══════════════════════════════════════════════════════════════════════════
// Help Module (hlp*)
// ═══════════════════════════════════════════════════════════════════════════

async function hlpShowHelp() {
    try {
        const resp = await api("/api/strings");
        const data = await resp.json();
        const helpText = data?.en?.["help.text"] || "No help available.";
        $("#help-text").textContent = helpText;
    } catch (_) {
        $("#help-text").textContent = "Failed to load help text.";
    }
    $("#helpModal").classList.add("show");
}

// ═══════════════════════════════════════════════════════════════════════════
// Resize Handle
// ═══════════════════════════════════════════════════════════════════════════

function _initResize() {
    const handle = $("#resize-handle");
    const sidebar = $("#sidebar");
    let startX, startW;

    handle.addEventListener("mousedown", (e) => {
        startX = e.clientX;
        startW = sidebar.offsetWidth;
        handle.classList.add("active");
        document.addEventListener("mousemove", onMove);
        document.addEventListener("mouseup", onUp);
        e.preventDefault();
    });

    function onMove(e) {
        const delta = e.clientX - startX;
        const newW = Math.max(200, Math.min(700, startW + delta));
        sidebar.style.width = newW + "px";
    }

    function onUp() {
        handle.classList.remove("active");
        document.removeEventListener("mousemove", onMove);
        document.removeEventListener("mouseup", onUp);
    }
}

// ═══════════════════════════════════════════════════════════════════════════
// Keyboard Shortcuts
// ═══════════════════════════════════════════════════════════════════════════

function _initKeyboard() {
    document.addEventListener("keydown", (e) => {
        // Ctrl+O — Open file
        if (e.ctrlKey && !e.shiftKey && e.key === "o") {
            e.preventDefault();
            csvOpenFile();
        }
        // Ctrl+Shift+O — Open folder
        if (e.ctrlKey && e.shiftKey && e.key === "O") {
            e.preventDefault();
            csvOpenFolder();
        }
        // Ctrl+R — Plot all
        if (e.ctrlKey && e.key === "r") {
            e.preventDefault();
            pltRenderAll();
        }
        // Ctrl+S — Save layout
        if (e.ctrlKey && e.key === "s") {
            e.preventDefault();
            laySave();
        }
        // Ctrl+L — Load layout
        if (e.ctrlKey && e.key === "l") {
            e.preventDefault();
            layLoad();
        }
        // Ctrl+N — Add subplot
        if (e.ctrlKey && e.key === "n") {
            e.preventDefault();
            subAdd();
        }
        // Ctrl+P — Export PNG
        if (e.ctrlKey && e.key === "p") {
            e.preventDefault();
            pltExportPng();
        }
        // Ctrl+H — Clear highlights
        if (e.ctrlKey && e.key === "h") {
            e.preventDefault();
            _highlightedSignals.clear();
            // Re-render all stats and restore trace opacities
            subplots.forEach(sub => {
                const statsEl = $(`#stats-${sub.id}`);
                if (statsEl) {
                    statsEl.querySelectorAll("tbody tr").forEach(r => r.classList.remove("highlighted"));
                }
                const plotDiv = $(`#plot-${sub.id}`);
                if (plotDiv && plotDiv.data) {
                    Plotly.restyle(plotDiv, { opacity: 1.0 }, plotDiv.data.map((_, i) => i));
                }
            });
            toast("Highlights cleared");
        }
        // Ctrl+Left — History previous
        if (e.ctrlKey && e.key === "ArrowLeft") {
            e.preventDefault();
            hstPrev();
        }
        // Ctrl+Right — History next
        if (e.ctrlKey && e.key === "ArrowRight") {
            e.preventDefault();
            hstNext();
        }
        // Ctrl+Enter — Apply custom code (when textarea focused)
        if (e.ctrlKey && e.key === "Enter") {
            const active = document.activeElement;
            if (active && active.tagName === "TEXTAREA" && active.id?.startsWith("sub-code-")) {
                e.preventDefault();
                const subId = parseInt(active.id.replace("sub-code-", ""));
                if (!isNaN(subId)) pltRender(subId);
            }
        }
        // F5 — Reload
        if (e.key === "F5") {
            e.preventDefault();
            csvReload();
        }
        // F1 — Help
        if (e.key === "F1") {
            e.preventDefault();
            hlpShowHelp();
        }
        // Escape — Close modals
        if (e.key === "Escape") {
            // Close browse modal properly (resolves Promise with null)
            if ($("#browseModal").classList.contains("show")) {
                brwClose();
                return;
            }
            $$(".modal-backdrop.show").forEach(m => m.classList.remove("show"));
            _highlightedSignals.clear();
        }
    });
}

// ═══════════════════════════════════════════════════════════════════════════
// Init
// ═══════════════════════════════════════════════════════════════════════════

document.addEventListener("DOMContentLoaded", () => {
    csvInit();
    cfgInit();
    _initResize();
    _initKeyboard();

    // Auto-save layout timer
    if (cfgSettings.autoSaveLayout) {
        _autoSaveTimer = setInterval(layAutoSave, 30000);
    }

    // Try to restore saved layout
    layInit();
});
