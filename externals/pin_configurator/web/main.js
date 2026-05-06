/**
 * Zephyr Pin Configurator – Frontend
 *
 * Visual point-and-click pin mux tool inspired by STM32CubeIDE.
 *  - SVG chip diagram with clickable pins
 *  - Peripheral enable toggles
 *  - Alt-function selector per pin
 *  - Live DTS overlay + prj.conf generation
 */

"use strict";

// ── State ────────────────────────────────────────────────────────────
let boardData    = null;   // Current board definition from API
let pinStates    = {};     // { pin_number: { af, props } }
let periphStates = {};     // { periph_name: enabled }
let periphCoreStates = {}; // { periph_name: core_id }
let externalDeviceStates = {}; // { device_id: { selected, bus } }
let selectedPin  = null;   // Currently selected pin number
let boardEditorDrafts = [];

let generatedOverlay = "";
let generatedConf    = "";
let generatedTargets = {};
let activeTab        = "overlay";
let boardEditorPendingDelete = "";
let boardEditorPreviewBoard = null;
let boardEditorCanvasStart = null;
let boardEditorCanvasDrag = null;
let boardEditorPreviewTimer = null;
let boardEditorDeviceLibrary = [];
let boardEditorCanvasZoom = 1.0;

// Zoom state
let chipZoom = 1.0;
const ZOOM_MIN = 0.2;
const ZOOM_MAX = 4.0;
const ZOOM_STEP = 0.15;
const BOARD_EDITOR_CANVAS_WIDTH = 1400;
const BOARD_EDITOR_CANVAS_HEIGHT = 900;

const DEFAULT_EXTERNAL_DEVICE_CATALOG = [
  {
    id: "bme280_i2c",
    display: "Bosch BME280",
    category: "sensor",
    bus_family: "i2c",
    compatible: "bosch,bme280",
    address: "0x76",
    required_signals: ["sda", "scl"],
    frameworks: ["zephyr", "arduino"],
    notes: "Temperature, humidity, and pressure sensor.",
  },
  {
    id: "lis2dh_i2c",
    display: "ST LIS2DH",
    category: "sensor",
    bus_family: "i2c",
    compatible: "st,lis2dh",
    address: "0x18",
    required_signals: ["sda", "scl", "int1"],
    frameworks: ["zephyr", "arduino"],
    notes: "3-axis accelerometer with optional interrupt line.",
  },
  {
    id: "ssd1306_i2c",
    display: "SSD1306 OLED",
    category: "display",
    bus_family: "i2c",
    compatible: "solomon,ssd1306fb",
    address: "0x3c",
    required_signals: ["sda", "scl"],
    frameworks: ["zephyr", "arduino"],
    notes: "128x64 monochrome OLED display.",
  },
  {
    id: "st7789v_spi",
    display: "ST7789V TFT",
    category: "display",
    bus_family: "spi",
    compatible: "sitronix,st7789v",
    address: "0",
    required_signals: ["mosi", "sck", "cs", "dc", "reset"],
    frameworks: ["zephyr", "arduino"],
    notes: "SPI TFT display with chip-select and data/command lines.",
  },
];

// ── DOM refs ─────────────────────────────────────────────────────────
const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => document.querySelectorAll(sel);

const boardSelect  = $("#boardSelect");
const chipLabel    = $("#chipLabel");
const statsLabel   = $("#statsLabel");
const chipArea     = $("#chipArea");
const chipContainer= $("#chipContainer");
const periphPanel  = $("#periphPanel");
const configPanel  = $("#configPanel");
const outputBar    = $("#outputBar");
const outputTabs   = $("#outputBar .output-tabs");
const outputPre    = $("#outputPre");

// ── Helpers ──────────────────────────────────────────────────────────

function toast(msg) {
  const el = $("#toast");
  el.textContent = msg;
  el.classList.add("show");
  setTimeout(() => el.classList.remove("show"), 2500);
}

function periphColor(periph) {
  if (periph.startsWith("uart"))  return "color-uart";
  if (periph.startsWith("spi"))   return "color-spi";
  if (periph.startsWith("i2c"))   return "color-i2c";
  if (periph.startsWith("can"))   return "color-can";
  if (periph.startsWith("tim"))   return "color-timer";
  if (periph.startsWith("adc"))   return "color-adc";
  if (periph.startsWith("dac"))   return "color-dac";
  if (periph.startsWith("gpio"))  return "color-gpio";
  if (periph.startsWith("comp"))  return "color-comp";
  return "";
}

function cloneJson(value) {
  return JSON.parse(JSON.stringify(value));
}

function escapeHtml(value) {
  return String(value ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/\"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

function inferDeviceBusFamily(device) {
  const bus = String(device.bus || "").toLowerCase();
  if (bus.startsWith("i2c")) return "i2c";
  if (bus.startsWith("spi")) return "spi";
  if (bus.startsWith("uart")) return "uart";
  if (bus.startsWith("can")) return "can";

  const requiredSignals = Array.isArray(device.required_signals)
    ? device.required_signals.map(signal => String(signal).toLowerCase())
    : [];
  if (requiredSignals.includes("sda") || requiredSignals.includes("scl")) return "i2c";
  if (requiredSignals.includes("mosi") || requiredSignals.includes("miso") || requiredSignals.includes("sck")) return "spi";
  return "";
}

function normalizeExternalDevice(device) {
  return {
    id: String(device.id || "").trim(),
    display: String(device.display || device.id || "").trim(),
    category: String(device.category || "device").trim() || "device",
    bus: String(device.bus || "").trim(),
    bus_family: String(device.bus_family || inferDeviceBusFamily(device)).trim(),
    compatible: String(device.compatible || "").trim(),
    address: String(device.address || "").trim(),
    required_signals: Array.isArray(device.required_signals)
      ? device.required_signals.map(signal => String(signal))
      : [],
    frameworks: Array.isArray(device.frameworks) && device.frameworks.length
      ? device.frameworks.map(framework => String(framework))
      : ["zephyr", "arduino"],
    notes: String(device.notes || "").trim(),
  };
}

function getExternalDeviceCatalog() {
  const merged = new Map();
  [...DEFAULT_EXTERNAL_DEVICE_CATALOG, ...(boardData?.external_devices || [])]
    .map(normalizeExternalDevice)
    .filter(device => device.id)
    .forEach(device => {
      merged.set(device.id, device);
    });
  return [...merged.values()];
}

function getPeripheralOptionsForBusFamily(busFamily) {
  if (!boardData || !busFamily) return [];
  return boardData.peripherals
    .filter(peripheral => peripheral.name.startsWith(busFamily))
    .map(peripheral => ({
      name: peripheral.name,
      display: peripheral.display || peripheral.name,
      enabled: !!periphStates[peripheral.name],
    }))
    .sort((left, right) => Number(right.enabled) - Number(left.enabled) || left.name.localeCompare(right.name));
}

function initExternalDeviceStates() {
  const next = {};
  getExternalDeviceCatalog().forEach(device => {
    const candidates = getPeripheralOptionsForBusFamily(device.bus_family);
    const preferredBus = candidates.some(candidate => candidate.name === device.bus)
      ? device.bus
      : (candidates[0]?.name || device.bus || "");
    next[device.id] = {
      selected: false,
      bus: preferredBus,
    };
  });
  externalDeviceStates = next;
}

function enableDeviceBus(deviceId) {
  const device = getExternalDeviceCatalog().find(entry => entry.id === deviceId);
  const state = externalDeviceStates[deviceId];
  if (!device || !state?.bus || !(state.bus in periphStates)) return;
  if (!periphStates[state.bus]) {
    periphStates[state.bus] = true;
    renderPeripherals();
  }
}

function selectedExternalDevices() {
  const catalog = getExternalDeviceCatalog();
  return catalog
    .filter(device => externalDeviceStates[device.id]?.selected)
    .map(device => ({
      ...device,
      bus: externalDeviceStates[device.id]?.bus || device.bus,
    }))
    .filter(device => device.bus);
}

function buildExternalDeviceSection() {
  const catalog = getExternalDeviceCatalog();
  if (!catalog.length) {
    return `
      <div class="config-section external-device-section">
        <label>External Devices</label>
        <div class="empty-state" style="padding: 18px 12px;">No preset devices available for this board.</div>
      </div>`;
  }

  const rows = catalog.map(device => {
    const state = externalDeviceStates[device.id] || { selected: false, bus: device.bus || "" };
    const busOptions = getPeripheralOptionsForBusFamily(device.bus_family);
    const disabled = busOptions.length === 0;
    const requiredSignals = device.required_signals.length
      ? `<div class="device-meta">Signals: ${escapeHtml(device.required_signals.join(", "))}</div>`
      : "";
    const notes = device.notes ? `<div class="device-note">${escapeHtml(device.notes)}</div>` : "";

    return `
      <div class="device-row ${state.selected ? "selected" : ""} ${disabled ? "disabled" : ""}">
        <div class="device-toggle-row">
          <input type="checkbox" data-device-toggle="${escapeHtml(device.id)}" ${state.selected ? "checked" : ""} ${disabled ? "disabled" : ""}>
          <div class="device-copy">
            <div class="device-title-row">
              <span class="device-title">${escapeHtml(device.display)}</span>
              <span class="device-pill">${escapeHtml(device.category)}</span>
            </div>
            <div class="device-meta">${escapeHtml(device.compatible || "custom device")}</div>
            ${requiredSignals}
            ${notes}
          </div>
        </div>
        <label class="device-bus-label">
          Bus
          <select data-device-bus="${escapeHtml(device.id)}" ${disabled ? "disabled" : ""}>
            ${busOptions.length ? busOptions.map(option => `
              <option value="${escapeHtml(option.name)}" ${state.bus === option.name ? "selected" : ""}>${escapeHtml(option.display)}</option>
            `).join("") : '<option value="">No compatible bus</option>'}
          </select>
        </label>
      </div>`;
  }).join("");

  return `
    <div class="config-section external-device-section">
      <label>External Devices</label>
      <div class="device-list">${rows}</div>
    </div>`;
}

function wireExternalDeviceControls(panel) {
  panel.querySelectorAll("[data-device-toggle]").forEach(input => {
    input.addEventListener("change", () => {
      const deviceId = input.dataset.deviceToggle;
      if (!deviceId || !externalDeviceStates[deviceId]) return;
      externalDeviceStates[deviceId].selected = input.checked;
      if (input.checked) {
        enableDeviceBus(deviceId);
      }
      renderConfigPanel();
    });
  });

  panel.querySelectorAll("[data-device-bus]").forEach(select => {
    select.addEventListener("change", () => {
      const deviceId = select.dataset.deviceBus;
      if (!deviceId || !externalDeviceStates[deviceId]) return;
      externalDeviceStates[deviceId].bus = select.value;
      if (externalDeviceStates[deviceId].selected) {
        enableDeviceBus(deviceId);
      }
    });
  });
}

function collectOutputViews() {
  const views = [
    { id: "overlay", label: ".overlay", content: generatedOverlay },
    { id: "conf", label: "prj.conf", content: generatedConf },
  ];

  for (const target of ["arduino", "baremetal"]) {
    const files = generatedTargets[target] || {};
    Object.keys(files).sort().forEach(filename => {
      views.push({
        id: `${target}:${filename}`,
        label: `${target}:${filename}`,
        content: files[filename],
      });
    });
  }

  return views.filter(view => view.content);
}

function appendOutputToggle() {
  const toggle = document.createElement("div");
  toggle.className = "output-toggle";
  toggle.id = "outputToggle";
  toggle.innerHTML = "&#9650; Output";
  toggle.addEventListener("click", () => {
    outputBar.classList.toggle("collapsed");
  });
  outputTabs.appendChild(toggle);
}

function renderOutputTabs() {
  const views = collectOutputViews();
  if (!views.length) {
    outputTabs.innerHTML = '<div class="output-tab active" data-tab="overlay">.overlay</div>';
    appendOutputToggle();
    activeTab = "overlay";
    return;
  }

  if (!views.some(view => view.id === activeTab)) {
    activeTab = views[0].id;
  }

  outputTabs.innerHTML = "";
  views.forEach(view => {
    const tab = document.createElement("div");
    tab.className = "output-tab" + (view.id === activeTab ? " active" : "");
    tab.dataset.tab = view.id;
    tab.textContent = view.label;
    tab.addEventListener("click", () => showOutput(view.id));
    outputTabs.appendChild(tab);
  });
  appendOutputToggle();
}

// ── Board loading ────────────────────────────────────────────────────

async function loadBoardList() {
  const res = await fetch("/api/boards");
  const boards = await res.json();
  boardSelect.innerHTML = "";
  boards.forEach(b => {
    const opt = document.createElement("option");
    opt.value = b.id;
    const pkg = b.package ? ` – ${b.package}` : "";
    opt.textContent = `${b.name}${pkg}`;
    boardSelect.appendChild(opt);
  });
  if (boards.length) {
    await loadBoard(boards[0].id);
  }
}

async function loadBoard(name) {
  const res = await fetch(`/api/board/${name}`);
  applyBoardDefinition(await res.json(), { syncEditor: true });
}

function applyBoardDefinition(nextBoard, options = {}) {
  const { syncEditor = false } = options;

  boardData = nextBoard;
  pinStates = {};
  periphStates = {};
  periphCoreStates = {};
  externalDeviceStates = {};
  selectedPin = null;
  generatedOverlay = "";
  generatedConf = "";
  generatedTargets = {};
  renderOutputTabs();

  chipLabel.textContent = boardData.soc;
  statsLabel.textContent =
    `Flash: ${boardData.flash_size_kb}KB | SRAM: ${boardData.sram_size_kb}KB | Clock: ${(boardData.clock_hz/1e6).toFixed(0)}MHz`;

  boardData.peripherals.forEach(p => {
    periphStates[p.name] = p.enabled || false;
    periphCoreStates[p.name] = p.core_id || (p.available_cores && p.available_cores[0]) || "";
  });

  initExternalDeviceStates();
  updateBoardEditorMeta();
  if (syncEditor) {
    setBoardEditorText(boardData);
    setBoardEditorStatus("Loaded current board into the editor.", "ok");
  }

  renderPeripherals();
  renderChip();
  renderConfigPanel();
}

function currentBoardForEditor() {
  if (!boardData) return null;
  return cloneJson(boardData);
}

function setBoardEditorText(board, options = {}) {
  const editor = $("#boardEditorJson");
  if (!editor) return;
  const { syncPreview = true } = options;
  editor.value = `${JSON.stringify(board, null, 2)}\n`;
  if (syncPreview) {
    boardEditorPreviewBoard = normalizeBoardEditorBoard(board);
    updateBoardEditorMeta(boardEditorPreviewBoard);
    renderBoardEditorCanvas(boardEditorPreviewBoard);
  }
}

function setBoardEditorStatus(message, tone = "") {
  const status = $("#boardEditorStatus");
  if (!status) return;
  status.textContent = message;
  status.className = `board-editor-status${tone ? ` ${tone}` : ""}`;
}

function setBoardEditorCanvasStatus(message, tone = "") {
  const status = $("#boardEditorCanvasStatus");
  if (!status) return;
  status.textContent = message;
  status.className = `board-editor-canvas-status${tone ? ` ${tone}` : ""}`;
}

function formatBoardDraftDate(timestamp) {
  if (!timestamp) return "Updated just now";
  return new Date(timestamp).toLocaleString([], {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function renderBoardEditorDrafts() {
  const list = $("#boardEditorDraftList");
  if (!list) return;
  if (!boardEditorDrafts.length) {
    list.innerHTML = '<div class="empty-state" style="padding: 18px 12px;">No saved board drafts yet.</div>';
    return;
  }

  list.innerHTML = boardEditorDrafts.map(draft => `
    <div class="board-editor-draft-item" data-board-draft="${escapeHtml(draft.filename)}">
      <div class="board-editor-draft-name">${escapeHtml(draft.filename)}</div>
      <div class="board-editor-draft-meta">${draft.size} bytes • ${escapeHtml(formatBoardDraftDate(draft.updated_at))}</div>
      <div class="board-editor-draft-actions">
        <button class="board-editor-draft-btn" data-board-draft-load="${escapeHtml(draft.filename)}">Load</button>
        <button class="board-editor-draft-btn" data-board-draft-duplicate="${escapeHtml(draft.filename)}">Duplicate</button>
        <button class="board-editor-draft-btn danger" data-board-draft-delete="${escapeHtml(draft.filename)}">${boardEditorPendingDelete === draft.filename ? "Confirm Delete" : "Delete"}</button>
      </div>
    </div>
  `).join("");

  list.querySelectorAll("[data-board-draft]").forEach(item => {
    item.addEventListener("click", async () => {
      const filename = item.dataset.boardDraft;
      if (!filename) return;
      try {
        await loadBoardEditorDraft(filename);
      } catch (err) {
        setBoardEditorStatus(err.message, "error");
      }
    });
  });

  list.querySelectorAll("[data-board-draft-load]").forEach(button => {
    button.addEventListener("click", async (event) => {
      event.stopPropagation();
      const filename = button.dataset.boardDraftLoad;
      if (!filename) return;
      try {
        await loadBoardEditorDraft(filename);
      } catch (err) {
        setBoardEditorStatus(err.message, "error");
      }
    });
  });

  list.querySelectorAll("[data-board-draft-duplicate]").forEach(button => {
    button.addEventListener("click", async (event) => {
      event.stopPropagation();
      const filename = button.dataset.boardDraftDuplicate;
      if (!filename) return;
      try {
        await duplicateBoardEditorDraft(filename);
      } catch (err) {
        setBoardEditorStatus(err.message, "error");
      }
    });
  });

  list.querySelectorAll("[data-board-draft-delete]").forEach(button => {
    button.addEventListener("click", async (event) => {
      event.stopPropagation();
      const filename = button.dataset.boardDraftDelete;
      if (!filename) return;
      try {
        await deleteBoardEditorDraft(filename);
      } catch (err) {
        setBoardEditorStatus(err.message, "error");
      }
    });
  });
}

async function loadBoardEditorDrafts() {
  try {
    const res = await fetch("/api/board-editor/drafts");
    const result = await res.json();
    if (!res.ok) {
      throw new Error(result.error || "Failed to load board drafts.");
    }
    boardEditorDrafts = Array.isArray(result.drafts) ? result.drafts : [];
    renderBoardEditorDrafts();
  } catch (err) {
    boardEditorDrafts = [];
    renderBoardEditorDrafts();
    setBoardEditorStatus(err.message || "Failed to load board drafts.", "error");
  }
}

async function saveBoardEditorDraft() {
  const board = validateBoardEditorJson();
  const res = await fetch("/api/board-editor/save", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ board }),
  });
  const result = await res.json();
  if (!res.ok) {
    throw new Error(result.error || "Failed to save board draft.");
  }
  await loadBoardEditorDrafts();
  setBoardEditorStatus(`Saved draft ${result.filename}.`, "ok");
  toast(`Saved board draft ${result.filename}`);
  return result;
}

function nextDuplicateDraftName(filename) {
  const base = filename.replace(/\.json$/i, "");
  const known = new Set(boardEditorDrafts.map(draft => draft.filename.toLowerCase()));
  let index = 1;
  let candidate = `${base}_copy.json`;
  while (known.has(candidate.toLowerCase())) {
    index += 1;
    candidate = `${base}_copy${index}.json`;
  }
  return candidate;
}

async function loadBoardEditorDraft(filename) {
  const res = await fetch(`/api/board-editor/draft/${encodeURIComponent(filename)}`);
  const result = await res.json();
  if (!res.ok) {
    throw new Error(result.error || `Failed to load ${filename}.`);
  }
  const board = normalizeBoardEditorBoard(result.board);
  setBoardEditorText(board);
  boardEditorPendingDelete = "";
  setBoardEditorCanvasStatus("Loaded draft into the wiring canvas. Drag devices or click pins to wire them.", "ok");
  setBoardEditorStatus(`Loaded draft ${result.filename}.`, "ok");
}

async function duplicateBoardEditorDraft(filename) {
  const draftRes = await fetch(`/api/board-editor/draft/${encodeURIComponent(filename)}`);
  const result = await draftRes.json();
  if (!draftRes.ok) {
    throw new Error(result.error || `Failed to load ${filename}.`);
  }
  const board = normalizeBoardEditorBoard(result.board);
  const nextFilename = nextDuplicateDraftName(filename);
  board.board = nextFilename.replace(/\.json$/i, "");
  const res = await fetch("/api/board-editor/save", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ filename: nextFilename, board }),
  });
  const saveResult = await res.json();
  if (!res.ok) {
    throw new Error(saveResult.error || "Failed to duplicate board draft.");
  }

  await loadBoardEditorDrafts();
  setBoardEditorStatus(`Duplicated draft as ${saveResult.filename}.`, "ok");
  toast(`Duplicated board draft ${saveResult.filename}`);
}

async function deleteBoardEditorDraft(filename) {
  if (boardEditorPendingDelete !== filename) {
    boardEditorPendingDelete = filename;
    renderBoardEditorDrafts();
    setBoardEditorStatus(`Click delete again to remove ${filename}.`, "error");
    return;
  }

  const res = await fetch("/api/board-editor/delete", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ filename }),
  });
  const result = await res.json();
  if (!res.ok) {
    throw new Error(result.error || "Failed to delete board draft.");
  }

  boardEditorPendingDelete = "";
  await loadBoardEditorDrafts();
  setBoardEditorStatus(`Deleted draft ${result.filename}.`, "ok");
  toast(`Deleted board draft ${result.filename}`);
}

function updateBoardEditorMeta() {
  const activeBoard = arguments.length ? arguments[0] : boardEditorPreviewBoard || boardData;
  if (!activeBoard) return;
  const boardLabel = $("#boardEditorBoard");
  const packageLabel = $("#boardEditorPackage");
  const countsLabel = $("#boardEditorCounts");
  if (boardLabel) boardLabel.textContent = activeBoard.board || activeBoard.soc || "Unnamed board";
  if (packageLabel) packageLabel.textContent = activeBoard.package || "-";
  if (countsLabel) {
    countsLabel.textContent = `${activeBoard.pins?.length || 0} pins / ${activeBoard.peripherals?.length || 0} peripherals`;
  }
}

function slugifyBoardEditorToken(value) {
  return String(value || "")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "_")
    .replace(/^_+|_+$/g, "") || "device";
}

function normalizeSearchToken(value) {
  return String(value || "").toLowerCase().replace(/[^a-z0-9]+/g, "");
}

function boardEditorSignalsForBus(protocol) {
  const normalized = String(protocol || "").toLowerCase();
  if (normalized === "i2c") return ["VCC", "GND", "SDA", "SCL"];
  if (normalized === "spi") return ["VCC", "GND", "SCK", "MOSI", "MISO", "CS"];
  if (normalized === "uart") return ["VCC", "GND", "TX", "RX"];
  if (normalized === "can") return ["VCC", "GND", "CAN_TX", "CAN_RX"];
  return ["VCC", "GND"];
}

function cleanBoardEditorPartLabel(summary, job) {
  const direct = String(summary?.part_number || "").trim();
  if (direct) return direct.toUpperCase();
  const fallback = String(job?.filename || job?.job_id || "sensor").trim();
  const noExt = fallback.replace(/\.pdf$/i, "");
  const normalized = noExt.replace(/^[a-f0-9]{8,}_/i, "");
  const vendorMatrix = normalized.match(/([a-z0-9+-]+)_vendor_matrix$/i);
  if (vendorMatrix) return vendorMatrix[1].toUpperCase();
  return normalized;
}

function cleanBoardEditorPackagePinName(name) {
  return String(name || "")
    .trim()
    .replace(/^[-_\s—–]+/, "")
    .replace(/^\d+[_\s/-]*/, "")
    .replace(/^[_\s/-]+/, "")
    .replace(/\s+/g, "_");
}

function cleanBoardEditorPackageInfo(packageInfo) {
  if (!packageInfo || typeof packageInfo !== "object") return null;
  const normalized = cloneJson(packageInfo);
  normalized.name = String(normalized.name || "").trim();
  normalized.package_type = String(normalized.package_type || "").trim();
  normalized.pin_count = Number(normalized.pin_count || 0);
  normalized.width_mm = Number.isFinite(Number(normalized.width_mm)) ? Number(normalized.width_mm) : undefined;
  normalized.height_mm = Number.isFinite(Number(normalized.height_mm)) ? Number(normalized.height_mm) : undefined;
  normalized.pitch_mm = Number.isFinite(Number(normalized.pitch_mm)) ? Number(normalized.pitch_mm) : undefined;
  normalized.pins = Array.isArray(normalized.pins)
    ? normalized.pins.map((pin, index) => ({
        number: Number(pin?.number || index + 1),
        name: cleanBoardEditorPackagePinName(pin?.name || `PIN${index + 1}`),
        kind: String(pin?.kind || "io"),
      })).filter((pin) => pin.name)
    : [];
  return normalized;
}

function boardEditorLibraryScore(entry) {
  const packageInfo = entry?.device?.package_info || {};
  return [
    entry?.source === "catalog" ? 1 : 0,
    entry?.device?.compatible ? 2 : 0,
    packageInfo?.name ? 4 : 0,
    Array.isArray(packageInfo?.pins) ? packageInfo.pins.length : 0,
    entry?.device?.display ? 1 : 0,
  ].reduce((sum, value) => sum + value, 0);
}

function boardEditorLibraryDedupeKey(entry) {
  if (entry.source === "catalog") return entry.key;
  const device = entry.device || {};
  const packageName = String(device.package_info?.name || device.package || "").toLowerCase();
  return [
    "sensor",
    normalizeSearchToken(device.display || entry.label),
    normalizeSearchToken(device.bus_family || device.bus),
    normalizeSearchToken(device.compatible || ""),
    normalizeSearchToken(packageName),
  ].join(":");
}

function updateBoardEditorCanvasZoomLabel() {
  const label = $("#boardEditorZoomLevel");
  if (label) label.textContent = `${Math.round(boardEditorCanvasZoom * 100)}%`;
}

function applyBoardEditorCanvasZoom() {
  const svg = $("#boardEditorCanvasShell svg");
  if (svg) {
    svg.style.width = `${Math.round(BOARD_EDITOR_CANVAS_WIDTH * boardEditorCanvasZoom)}px`;
    svg.style.height = `${Math.round(BOARD_EDITOR_CANVAS_HEIGHT * boardEditorCanvasZoom)}px`;
  }
  updateBoardEditorCanvasZoomLabel();
}

function boardEditorCanvasZoomIn() {
  boardEditorCanvasZoom = Math.min(ZOOM_MAX, boardEditorCanvasZoom + ZOOM_STEP);
  applyBoardEditorCanvasZoom();
}

function boardEditorCanvasZoomOut() {
  boardEditorCanvasZoom = Math.max(ZOOM_MIN, boardEditorCanvasZoom - ZOOM_STEP);
  applyBoardEditorCanvasZoom();
}

function boardEditorCanvasFit() {
  const shell = $("#boardEditorCanvasShell");
  if (!shell) return;
  const areaW = Math.max(200, shell.clientWidth - 32);
  const areaH = Math.max(180, shell.clientHeight - 32);
  boardEditorCanvasZoom = Math.min(areaW / BOARD_EDITOR_CANVAS_WIDTH, areaH / BOARD_EDITOR_CANVAS_HEIGHT);
  boardEditorCanvasZoom = Math.max(ZOOM_MIN, Math.min(ZOOM_MAX, boardEditorCanvasZoom));
  applyBoardEditorCanvasZoom();
}

function matchSupportedDeviceForPart(partNumber) {
  const token = normalizeSearchToken(partNumber);
  if (!token) return null;
  return DEFAULT_EXTERNAL_DEVICE_CATALOG.find((device) => {
    const haystack = [device.id, device.display, device.compatible]
      .map(normalizeSearchToken)
      .join(" ");
    return haystack.includes(token);
  }) || null;
}

function normalizeBoardEditorDevice(device, index) {
  const normalized = device && typeof device === "object" ? cloneJson(device) : {};
  normalized.id = String(normalized.id || `${slugifyBoardEditorToken(normalized.display || `device_${index + 1}`)}_${index + 1}`);
  normalized.display = String(normalized.display || normalized.id || `Device ${index + 1}`);
  normalized.category = String(normalized.category || "device");
  normalized.bus = String(normalized.bus || "");
  normalized.compatible = String(normalized.compatible || "");
  normalized.address = String(normalized.address || "");
  normalized.notes = String(normalized.notes || "");
  normalized.package_info = normalized.package_info && typeof normalized.package_info === "object"
    ? cleanBoardEditorPackageInfo(normalized.package_info)
    : null;
  normalized.package = String(normalized.package || normalized.package_info?.name || "");
  normalized.frameworks = Array.isArray(normalized.frameworks) ? normalized.frameworks.map(value => String(value)) : [];
  normalized.required_signals = Array.isArray(normalized.required_signals)
    ? normalized.required_signals.map(value => String(value))
    : [];
  const explicitPins = Array.isArray(normalized.pins)
    ? normalized.pins.map(value => String(value).trim()).filter(Boolean)
    : [];
  const packagePins = Array.isArray(normalized.package_info?.pins)
    ? normalized.package_info.pins.map(pin => String(pin?.name || "").trim()).filter(Boolean)
    : [];
  normalized.pins = explicitPins.length
    ? explicitPins
    : (packagePins.length
      ? packagePins
      : (normalized.required_signals.length
      ? normalized.required_signals.map(value => String(value).trim()).filter(Boolean)
      : ["VCC", "GND"]));
  normalized.x = Number.isFinite(Number(normalized.x)) ? Number(normalized.x) : 860 + (index % 2) * 250;
  normalized.y = Number.isFinite(Number(normalized.y)) ? Number(normalized.y) : 140 + Math.floor(index / 2) * 180;
  return normalized;
}

function buildBoardEditorSensorLibraryEntry(job) {
  const summary = job.result?.summary || job.summary || {};
  const address = job.result?.address || {};
  const packageInfo = cleanBoardEditorPackageInfo(job.result?.package || job.package || null);
  const partNumber = cleanBoardEditorPartLabel(summary, job);
  const protocol = String(address.protocol || summary.protocol || "").toLowerCase();
  const matched = matchSupportedDeviceForPart(partNumber);
  const busFamily = protocol || matched?.bus_family || inferDeviceBusFamily(matched || {});
  const addressValue = Array.isArray(address.i2c_addresses) && address.i2c_addresses.length
    ? String(address.i2c_addresses[0])
    : String(matched?.address || "");

  return {
    key: `sensor:${job.job_id}`,
    source: "sensor",
    label: `${partNumber} [parsed sensor]`,
    device: {
      id: matched?.id || `${slugifyBoardEditorToken(partNumber)}${busFamily ? `_${busFamily}` : ""}`,
      display: partNumber,
      category: String(summary.sensor_type || matched?.category || "sensor").trim() || "sensor",
      bus: busFamily ? `${busFamily}0` : "",
      bus_family: busFamily,
      compatible: matched?.compatible || "",
      address: addressValue,
      required_signals: matched?.required_signals || boardEditorSignalsForBus(busFamily),
      frameworks: matched?.frameworks || [],
      package: packageInfo?.name || "",
      package_info: packageInfo,
      notes: [
        `Imported from parsed sensor job ${job.job_id}.`,
        summary.vendor_name ? `Vendor: ${summary.vendor_name}.` : "",
        packageInfo?.name ? `Package: ${packageInfo.name}.` : "",
        matched?.compatible ? `Matched supported device ${matched.display}.` : "",
      ].filter(Boolean).join(" "),
      pins: Array.isArray(packageInfo?.pins) && packageInfo.pins.length
        ? packageInfo.pins.map(pin => cleanBoardEditorPackagePinName(pin.name))
        : (matched?.required_signals || boardEditorSignalsForBus(busFamily)),
    },
  };
}

function renderBoardEditorDeviceLibrary() {
  const select = $("#boardEditorDeviceLibrary");
  if (!select) return;

  const placeholder = '<option value="">Supported devices and parsed sensors</option>';
  if (!boardEditorDeviceLibrary.length) {
    select.innerHTML = `${placeholder}<option value="" disabled>No library devices available</option>`;
    return;
  }

  select.innerHTML = [
    placeholder,
    ...boardEditorDeviceLibrary.map((entry) => (
      `<option value="${escapeHtml(entry.key)}">${escapeHtml(entry.label)}</option>`
    )),
  ].join("");
}

async function loadBoardEditorDeviceLibrary() {
  const entries = DEFAULT_EXTERNAL_DEVICE_CATALOG.map((device) => ({
    key: `catalog:${device.id}`,
    source: "catalog",
    label: `${device.display} [zephyr/arduino]`,
    device: {
      ...cloneJson(device),
      bus: device.bus || (device.bus_family ? `${device.bus_family}0` : ""),
      pins: device.required_signals,
    },
  }));

  try {
    const res = await fetch("/api/sensor-jobs");
    const jobs = await res.json();
    if (res.ok && Array.isArray(jobs)) {
      const detailedJobs = await Promise.all(jobs.map(async (job) => {
        try {
          const detailRes = await fetch(`/api/sensor-job/${encodeURIComponent(job.job_id)}`);
          const detail = await detailRes.json();
          if (detailRes.ok && detail?.result) {
            return { ...job, result: detail.result };
          }
        } catch (_err) {
          // Fall back to the summary entry when the detail endpoint is unavailable.
        }
        return job;
      }));

      detailedJobs.forEach((job) => {
        entries.push(buildBoardEditorSensorLibraryEntry(job));
      });
    }
  } catch (_err) {
    // Keep the supported-device catalog even if sensor jobs are unavailable.
  }

  const deduped = new Map();
  entries.forEach((entry) => {
    const dedupeKey = boardEditorLibraryDedupeKey(entry);
    const current = deduped.get(dedupeKey);
    if (!current || boardEditorLibraryScore(entry) > boardEditorLibraryScore(current)) {
      deduped.set(dedupeKey, entry);
    }
  });
  boardEditorDeviceLibrary = [...deduped.values()];
  renderBoardEditorDeviceLibrary();
}

function normalizeBoardEditorConnection(connection) {
  if (!connection || typeof connection !== "object") return null;
  const normalized = {
    board_pin: Number(connection.board_pin),
    device_id: String(connection.device_id || "").trim(),
    device_pin: String(connection.device_pin || "").trim(),
  };
  if (!Number.isFinite(normalized.board_pin) || !normalized.device_id || !normalized.device_pin) {
    return null;
  }
  return normalized;
}

function queueBoardEditorPreviewSync() {
  if (boardEditorPreviewTimer) {
    clearTimeout(boardEditorPreviewTimer);
  }
  boardEditorPreviewTimer = setTimeout(() => {
    boardEditorPreviewTimer = null;
    syncBoardEditorPreview({ softFail: true });
  }, 180);
}

function syncBoardEditorPreview(options = {}) {
  const { softFail = false } = options;
  try {
    const board = parseBoardEditorJson();
    boardEditorPreviewBoard = board;
    updateBoardEditorMeta(board);
    renderBoardEditorCanvas(board);
    return board;
  } catch (err) {
    setBoardEditorCanvasStatus(`Preview paused until JSON is valid. ${err.message}`, "error");
    if (softFail) {
      return null;
    }
    throw err;
  }
}

function writeBoardEditorFromCanvas(board, message = "", tone = "ok") {
  const normalized = normalizeBoardEditorBoard(board);
  boardEditorPreviewBoard = normalized;
  setBoardEditorText(normalized, { syncPreview: false });
  updateBoardEditorMeta(normalized);
  renderBoardEditorCanvas(normalized);
  if (message) {
    setBoardEditorCanvasStatus(message, tone);
  }
}

function normalizeBoardEditorBoard(parsed) {
  if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
    throw new Error("Board JSON must be an object.");
  }

  const normalized = cloneJson(parsed);
  normalized.board = String(normalized.board || normalized.id || normalized.soc || "custom_board");
  normalized.soc = String(normalized.soc || normalized.board || "Custom SoC");
  normalized.vendor = String(normalized.vendor || "custom");
  normalized.package = String(normalized.package || "Custom");
  normalized.pins = Array.isArray(normalized.pins) ? normalized.pins : [];
  normalized.peripherals = Array.isArray(normalized.peripherals) ? normalized.peripherals : [];
  normalized.external_devices = Array.isArray(normalized.external_devices)
    ? normalized.external_devices.map((device, index) => normalizeBoardEditorDevice(device, index))
    : [];
  normalized.cores = Array.isArray(normalized.cores) ? normalized.cores : [];
  normalized.output_targets = Array.isArray(normalized.output_targets) ? normalized.output_targets : [];
  normalized.manual_connections = Array.isArray(normalized.manual_connections)
    ? normalized.manual_connections.map(normalizeBoardEditorConnection).filter(Boolean)
    : [];
  normalized.pin_count = Number(normalized.pin_count || normalized.pins.length || 0);
  normalized.flash_size_kb = Number(normalized.flash_size_kb || 0);
  normalized.sram_size_kb = Number(normalized.sram_size_kb || 0);
  normalized.clock_hz = Number(normalized.clock_hz || 0);

  if (!normalized.pins.every(pin => pin && typeof pin === "object" && "number" in pin && "name" in pin)) {
    throw new Error("Each pin must include at least number and name.");
  }
  if (!normalized.peripherals.every(peripheral => peripheral && typeof peripheral === "object" && "name" in peripheral)) {
    throw new Error("Each peripheral must include at least name.");
  }

  return normalized;
}

function parseBoardEditorJson() {
  const editor = $("#boardEditorJson");
  if (!editor) {
    throw new Error("Board editor is not available.");
  }
  let parsed;
  try {
    parsed = JSON.parse(editor.value);
  } catch (err) {
    throw new Error(`Invalid JSON: ${err.message}`);
  }
  return normalizeBoardEditorBoard(parsed);
}

function validateBoardEditorJson() {
  const board = parseBoardEditorJson();
  boardEditorPreviewBoard = board;
  updateBoardEditorMeta(board);
  renderBoardEditorCanvas(board);
  setBoardEditorCanvasStatus("Package canvas is in sync. Drag devices and click endpoints to add or remove wires.", "ok");
  setBoardEditorStatus(
    `Valid board JSON: ${board.board} with ${board.pins.length} pins and ${board.peripherals.length} peripherals.`,
    "ok",
  );
  return board;
}

function applyBoardEditorJson() {
  const board = validateBoardEditorJson();
  applyBoardDefinition(board, { syncEditor: true });
  toast(`Applied board editor JSON for ${board.board}`);
}

function exportBoardEditorJson() {
  const board = validateBoardEditorJson();
  const blob = new Blob([`${JSON.stringify(board, null, 2)}\n`], { type: "application/json" });
  const link = document.createElement("a");
  link.href = URL.createObjectURL(blob);
  link.download = `${board.board || "board"}.json`;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(link.href);
  setBoardEditorStatus(`Exported ${link.download}.`, "ok");
}

function boardEditorSvgPoint(svg, clientX, clientY) {
  const point = svg.createSVGPoint();
  point.x = clientX;
  point.y = clientY;
  return point.matrixTransform(svg.getScreenCTM().inverse());
}

function buildBoardEditorPackageLayout(board) {
  return isBgaPackage(board.package)
    ? buildBoardEditorBgaLayout(board)
    : buildBoardEditorQfpLayout(board);
}

function buildBoardEditorQfpLayout(board) {
  const sides = { left: [], bottom: [], right: [], top: [] };
  board.pins.forEach(pin => {
    const side = sides[pin.side] ? pin.side : "left";
    sides[side].push(pin);
  });

  const maxSide = Math.max(sides.left.length, sides.bottom.length, sides.right.length, sides.top.length, 1);
  const centerX = 360;
  const centerY = 420;
  const padLong = 34;
  const padShort = 18;
  const padGap = 6;
  const bodySize = Math.max(220, maxSide * (padShort + padGap) + 30);
  const bodyX = centerX - bodySize / 2;
  const bodyY = centerY - bodySize / 2;
  const bodyW = bodySize;
  const bodyH = bodySize;
  const inset = 12;
  const pins = [];

  sides.left.forEach((pin, index) => {
    const x = bodyX - padLong - 16;
    const y = bodyY + inset + index * (padShort + padGap);
    pins.push({ pin, x, y, w: padLong, h: padShort, side: "left", anchorX: x, anchorY: y + padShort / 2 });
  });
  sides.bottom.forEach((pin, index) => {
    const x = bodyX + inset + index * (padShort + padGap);
    const y = bodyY + bodyH + 16;
    pins.push({ pin, x, y, w: padShort, h: padLong, side: "bottom", anchorX: x + padShort / 2, anchorY: y + padLong });
  });
  sides.right.forEach((pin, index) => {
    const x = bodyX + bodyW + 16;
    const y = bodyY + bodyH - inset - padShort - index * (padShort + padGap);
    pins.push({ pin, x, y, w: padLong, h: padShort, side: "right", anchorX: x + padLong, anchorY: y + padShort / 2 });
  });
  sides.top.forEach((pin, index) => {
    const x = bodyX + bodyW - inset - padShort - index * (padShort + padGap);
    const y = bodyY - padLong - 16;
    pins.push({ pin, x, y, w: padShort, h: padLong, side: "top", anchorX: x + padShort / 2, anchorY: y });
  });

  return {
    type: "qfp",
    centerX,
    centerY,
    bodyX,
    bodyY,
    bodyW,
    bodyH,
    pins,
  };
}

function buildBoardEditorBgaLayout(board) {
  const pins = [...board.pins].sort((left, right) => left.number - right.number);
  const side = Math.ceil(Math.sqrt(Math.max(pins.length, 1)));
  const cell = 34;
  const radius = 11;
  const gridSize = side * cell;
  const originX = 220;
  const originY = 250;
  const pinLayouts = [];

  pins.forEach((pin, index) => {
    const row = Math.floor(index / side);
    const col = index % side;
    const cx = originX + col * cell + cell / 2;
    const cy = originY + row * cell + cell / 2;
    pinLayouts.push({ pin, cx, cy, r: radius, anchorX: cx, anchorY: cy, shortLabel: pin.name.slice(0, 4) });
  });

  return {
    type: "bga",
    centerX: originX + gridSize / 2,
    centerY: originY + gridSize / 2,
    bodyX: originX - 18,
    bodyY: originY - 18,
    bodyW: gridSize + 36,
    bodyH: gridSize + 36,
    pins: pinLayouts,
    gridSide: side,
  };
}

function buildBoardEditorDeviceLayout(device) {
  const packageInfo = device?.package_info && typeof device.package_info === "object"
    ? device.package_info
    : null;
  if (packageInfo) {
    const packageName = String(packageInfo.name || device.package || "PKG");
    const explicitPackagePins = Array.isArray(packageInfo.pins) ? packageInfo.pins : [];
    const fallbackPins = Array.isArray(device.pins) && device.pins.length ? device.pins : ["VCC", "GND"];
    const packagePins = (explicitPackagePins.length ? explicitPackagePins : fallbackPins.map((name, index) => ({ number: index + 1, name, kind: "io" })))
      .map((pin, index) => ({
        number: Number(pin.number || index + 1),
        name: String(pin.name || `PIN${index + 1}`),
        kind: String(pin.kind || "io") || "io",
      }))
      .sort((left, right) => left.number - right.number);
    const isBga = isBgaPackage(packageName);
    const bodyW = isBga ? 120 : 134;
    const bodyH = isBga ? 120 : 134;
    const pinLength = isBga ? 0 : 12;
    const pinThickness = 10;
    const originX = Number(device.x);
    const originY = Number(device.y);
    const bodyX = originX + (isBga ? 38 : 32);
    const bodyY = originY + 54;
    const pinLayouts = [];

    if (isBga) {
      const side = Math.max(2, Math.ceil(Math.sqrt(packagePins.length || 1)));
      const cell = 22;
      const grid = side * cell;
      const gridOriginX = originX + 30;
      const gridOriginY = originY + 62;
      packagePins.forEach((pin, index) => {
        const row = Math.floor(index / side);
        const col = index % side;
        const cx = gridOriginX + col * cell + cell / 2;
        const cy = gridOriginY + row * cell + cell / 2;
        pinLayouts.push({ pin, shape: "circle", cx, cy, r: 7, anchorX: cx, anchorY: cy });
      });
      return {
        type: "package-device",
        packageStyle: "bga",
        device,
        x: originX,
        y: originY,
        width: grid + 60,
        height: grid + 110,
        bodyX: gridOriginX - 8,
        bodyY: gridOriginY - 8,
        bodyW: grid + 16,
        bodyH: grid + 16,
        titleY: originY + 22,
        subtitleY: originY + 40,
        pinLayouts,
      };
    }

    const sideCount = Math.max(1, Math.ceil(packagePins.length / 4));
    packagePins.forEach((pin, index) => {
      let side = "left";
      let x = bodyX - pinLength;
      let y = bodyY + 10;
      if (index < sideCount) {
        side = "left";
        y = bodyY + 10 + index * ((bodyH - 20) / Math.max(1, sideCount));
      } else if (index < sideCount * 2) {
        side = "bottom";
        x = bodyX + 10 + (index - sideCount) * ((bodyW - 20) / Math.max(1, sideCount));
        y = bodyY + bodyH;
      } else if (index < sideCount * 3) {
        side = "right";
        x = bodyX + bodyW;
        y = bodyY + 10 + (index - sideCount * 2) * ((bodyH - 20) / Math.max(1, sideCount));
      } else {
        side = "top";
        x = bodyX + 10 + (index - sideCount * 3) * ((bodyW - 20) / Math.max(1, sideCount));
        y = bodyY - pinLength;
      }
      pinLayouts.push({
        pin,
        shape: "rect",
        side,
        x,
        y,
        w: side === "left" || side === "right" ? pinLength : pinThickness,
        h: side === "left" || side === "right" ? pinThickness : pinLength,
        anchorX: side === "left" ? x : side === "right" ? x + pinLength : x + pinThickness / 2,
        anchorY: side === "top" ? y : side === "bottom" ? y + pinLength : y + pinThickness / 2,
      });
    });

    return {
      type: "package-device",
      packageStyle: "perimeter",
      device,
      x: originX,
      y: originY,
      width: 204,
      height: 232,
      bodyX,
      bodyY,
      bodyW,
      bodyH,
      titleY: originY + 22,
      subtitleY: originY + 40,
      pinLayouts,
    };
  }

  const pinNames = Array.isArray(device.pins) && device.pins.length ? device.pins : ["VCC", "GND"];
  const width = 220;
  const rowHeight = 26;
  const headerHeight = 50;
  const height = headerHeight + pinNames.length * rowHeight + 14;
  const anchorSide = Number(device.x) >= 520 ? "left" : "right";
  const pinLayouts = pinNames.map((pinName, index) => {
    const y = Number(device.y) + headerHeight + index * rowHeight + rowHeight / 2;
    const anchorX = anchorSide === "left" ? Number(device.x) : Number(device.x) + width;
    return { name: pinName, x: Number(device.x), y, anchorX, anchorY: y, anchorSide };
  });
  return {
    device,
    x: Number(device.x),
    y: Number(device.y),
    width,
    height,
    headerHeight,
    pinLayouts,
    anchorSide,
  };
}

function boardEditorConnectionMaps(packageLayout, deviceLayouts) {
  const boardPins = new Map();
  packageLayout.pins.forEach((entry) => {
    boardPins.set(Number(entry.pin.number), entry);
  });

  const devicePins = new Map();
  deviceLayouts.forEach((layout) => {
    layout.pinLayouts.forEach((pin) => {
      devicePins.set(`${layout.device.id}:${pin.name}`, pin);
    });
  });

  return { boardPins, devicePins };
}

function renderBoardEditorCanvas(board) {
  const shell = $("#boardEditorCanvasShell");
  if (!shell) return;
  if (!board) {
    shell.innerHTML = '<div class="board-editor-canvas-empty">The selected MCU package and external devices will appear here once the Board Editor JSON is valid.</div>';
    updateBoardEditorCanvasZoomLabel();
    return;
  }

  const packageLayout = buildBoardEditorPackageLayout(board);
  const deviceLayouts = board.external_devices.map(buildBoardEditorDeviceLayout);
  const { boardPins, devicePins } = boardEditorConnectionMaps(packageLayout, deviceLayouts);
  const parts = [];
  parts.push(`<svg class="board-editor-canvas-svg" viewBox="0 0 ${BOARD_EDITOR_CANVAS_WIDTH} ${BOARD_EDITOR_CANVAS_HEIGHT}" xmlns="http://www.w3.org/2000/svg">`);
  parts.push(`<text x="46" y="44" class="board-editor-mcu-label" font-size="18">${escapeHtml(board.soc || board.board)}</text>`);
  parts.push(`<text x="46" y="66" class="board-editor-mcu-subtitle" font-size="12">${escapeHtml(board.package)} wiring canvas</text>`);

  board.manual_connections.forEach((connection, index) => {
    const boardPin = boardPins.get(Number(connection.board_pin));
    const devicePin = devicePins.get(`${connection.device_id}:${connection.device_pin}`);
    if (!boardPin || !devicePin) return;
    const bendX = boardPin.anchorX < devicePin.anchorX
      ? (boardPin.anchorX + devicePin.anchorX) / 2
      : Math.max(boardPin.anchorX, devicePin.anchorX) + 60;
    parts.push(`<path class="board-editor-wire" data-wire-index="${index}" d="M ${boardPin.anchorX} ${boardPin.anchorY} L ${bendX} ${boardPin.anchorY} L ${bendX} ${devicePin.anchorY} L ${devicePin.anchorX} ${devicePin.anchorY}" />`);
  });

  parts.push(`<rect class="board-editor-mcu-body" x="${packageLayout.bodyX}" y="${packageLayout.bodyY}" width="${packageLayout.bodyW}" height="${packageLayout.bodyH}" rx="14" />`);
  parts.push(`<circle cx="${packageLayout.bodyX + 18}" cy="${packageLayout.bodyY + 18}" r="6" fill="rgba(248,250,252,.88)" />`);
  parts.push(`<text x="${packageLayout.centerX}" y="${packageLayout.centerY - 10}" class="board-editor-mcu-label" font-size="18" text-anchor="middle">${escapeHtml(board.soc)}</text>`);
  parts.push(`<text x="${packageLayout.centerX}" y="${packageLayout.centerY + 14}" class="board-editor-mcu-subtitle" font-size="12" text-anchor="middle">${escapeHtml(board.package)}</text>`);

  if (packageLayout.type === "bga") {
    packageLayout.pins.forEach((entry) => {
      const selected = boardEditorCanvasStart?.type === "board" && Number(boardEditorCanvasStart.pin) === Number(entry.pin.number) ? " selected" : "";
      parts.push(`<circle class="board-editor-canvas-pin ${escapeHtml(entry.pin.kind || "io")}${selected}" data-board-pin="${entry.pin.number}" cx="${entry.cx}" cy="${entry.cy}" r="${entry.r}" />`);
      parts.push(`<text class="board-editor-canvas-pin-label" x="${entry.cx}" y="${entry.cy + 4}" text-anchor="middle">${escapeHtml(entry.shortLabel)}</text>`);
      parts.push(`<text class="board-editor-canvas-pin-num" x="${entry.cx}" y="${entry.cy + 22}" text-anchor="middle">${entry.pin.number}</text>`);
    });
  } else {
    packageLayout.pins.forEach((entry) => {
      const selected = boardEditorCanvasStart?.type === "board" && Number(boardEditorCanvasStart.pin) === Number(entry.pin.number) ? " selected" : "";
      parts.push(`<rect class="board-editor-canvas-pin ${escapeHtml(entry.pin.kind || "io")}${selected}" data-board-pin="${entry.pin.number}" x="${entry.x}" y="${entry.y}" width="${entry.w}" height="${entry.h}" rx="4" />`);
      if (entry.side === "left") {
        parts.push(`<text class="board-editor-canvas-pin-num" x="${entry.x + entry.w + 6}" y="${entry.y + entry.h / 2 + 4}" text-anchor="start">${entry.pin.number}</text>`);
        parts.push(`<text class="board-editor-canvas-pin-label" x="${entry.x - 6}" y="${entry.y + entry.h / 2 + 4}" text-anchor="end">${escapeHtml(entry.pin.name)}</text>`);
      } else if (entry.side === "right") {
        parts.push(`<text class="board-editor-canvas-pin-num" x="${entry.x - 6}" y="${entry.y + entry.h / 2 + 4}" text-anchor="end">${entry.pin.number}</text>`);
        parts.push(`<text class="board-editor-canvas-pin-label" x="${entry.x + entry.w + 6}" y="${entry.y + entry.h / 2 + 4}" text-anchor="start">${escapeHtml(entry.pin.name)}</text>`);
      } else if (entry.side === "top") {
        parts.push(`<text class="board-editor-canvas-pin-label" x="${entry.x + entry.w / 2}" y="${entry.y - 6}" text-anchor="middle">${escapeHtml(entry.pin.name)}</text>`);
        parts.push(`<text class="board-editor-canvas-pin-num" x="${entry.x + entry.w / 2}" y="${entry.y + entry.h + 14}" text-anchor="middle">${entry.pin.number}</text>`);
      } else {
        parts.push(`<text class="board-editor-canvas-pin-num" x="${entry.x + entry.w / 2}" y="${entry.y - 6}" text-anchor="middle">${entry.pin.number}</text>`);
        parts.push(`<text class="board-editor-canvas-pin-label" x="${entry.x + entry.w / 2}" y="${entry.y + entry.h + 16}" text-anchor="middle">${escapeHtml(entry.pin.name)}</text>`);
      }
    });
  }

  deviceLayouts.forEach((layout) => {
    if (layout.type === "package-device") {
      const packageInfo = layout.device.package_info || {};
      const dims = Number(packageInfo.width_mm) > 0 && Number(packageInfo.height_mm) > 0
        ? `${packageInfo.width_mm} x ${packageInfo.height_mm} mm`
        : "";
      const pitch = Number(packageInfo.pitch_mm) > 0 ? `${packageInfo.pitch_mm} mm pitch` : "";
      const subtitle = [layout.device.package || packageInfo.name || "package", dims, pitch].filter(Boolean).join(" • ");
      parts.push(`<g class="board-editor-device-card${boardEditorCanvasDrag?.deviceId === layout.device.id ? " dragging" : ""}" transform="translate(${layout.x} ${layout.y})">`);
      parts.push(`<text class="board-editor-device-title" x="10" y="22">${escapeHtml(layout.device.display)}</text>`);
      parts.push(`<text class="board-editor-device-subtitle" x="10" y="38">${escapeHtml(subtitle)}</text>`);
      parts.push(`<circle class="board-editor-device-delete" data-device-remove="${escapeHtml(layout.device.id)}" cx="${layout.width - 12}" cy="16" r="10" />`);
      parts.push(`<text class="board-editor-device-delete-label" x="${layout.width - 12}" y="20" text-anchor="middle">×</text>`);
      parts.push(`<rect class="board-editor-device-body" data-device-drag="${escapeHtml(layout.device.id)}" x="${layout.bodyX - layout.x}" y="${layout.bodyY - layout.y}" width="${layout.bodyW}" height="${layout.bodyH}" rx="12" />`);
      parts.push(`<text class="board-editor-mcu-subtitle" x="${layout.bodyX - layout.x + layout.bodyW / 2}" y="${layout.bodyY - layout.y + layout.bodyH / 2}" text-anchor="middle">${escapeHtml(layout.device.package || packageInfo.name || "pkg")}</text>`);
      layout.pinLayouts.forEach((pinLayout) => {
        const selected = boardEditorCanvasStart?.type === "device" && boardEditorCanvasStart.deviceId === layout.device.id && boardEditorCanvasStart.pin === pinLayout.pin.name ? " selected" : "";
        if (pinLayout.shape === "circle") {
          parts.push(`<circle class="board-editor-canvas-pin ${escapeHtml(pinLayout.pin.kind || "io")}${selected}" data-device-pin="${escapeHtml(layout.device.id)}" data-device-pin-name="${escapeHtml(pinLayout.pin.name)}" cx="${pinLayout.cx - layout.x}" cy="${pinLayout.cy - layout.y}" r="${pinLayout.r}" />`);
          parts.push(`<text class="board-editor-canvas-pin-label" x="${pinLayout.cx - layout.x}" y="${pinLayout.cy - layout.y + 4}" text-anchor="middle">${escapeHtml(pinLayout.pin.name)}</text>`);
        } else {
          parts.push(`<rect class="board-editor-canvas-pin ${escapeHtml(pinLayout.pin.kind || "io")}${selected}" data-device-pin="${escapeHtml(layout.device.id)}" data-device-pin-name="${escapeHtml(pinLayout.pin.name)}" x="${pinLayout.x - layout.x}" y="${pinLayout.y - layout.y}" width="${pinLayout.w}" height="${pinLayout.h}" rx="4" />`);
          if (pinLayout.side === "left") {
            parts.push(`<text class="board-editor-canvas-pin-label" x="${pinLayout.x - layout.x - 4}" y="${pinLayout.y - layout.y + 9}" text-anchor="end">${escapeHtml(pinLayout.pin.name)}</text>`);
          } else if (pinLayout.side === "right") {
            parts.push(`<text class="board-editor-canvas-pin-label" x="${pinLayout.x - layout.x + pinLayout.w + 4}" y="${pinLayout.y - layout.y + 9}" text-anchor="start">${escapeHtml(pinLayout.pin.name)}</text>`);
          } else if (pinLayout.side === "top") {
            parts.push(`<text class="board-editor-canvas-pin-label" x="${pinLayout.x - layout.x + pinLayout.w / 2}" y="${pinLayout.y - layout.y - 4}" text-anchor="middle">${escapeHtml(pinLayout.pin.name)}</text>`);
          } else {
            parts.push(`<text class="board-editor-canvas-pin-label" x="${pinLayout.x - layout.x + pinLayout.w / 2}" y="${pinLayout.y - layout.y + pinLayout.h + 12}" text-anchor="middle">${escapeHtml(pinLayout.pin.name)}</text>`);
          }
        }
      });
      parts.push("</g>");
      return;
    }

    parts.push(`<g class="board-editor-device-card${boardEditorCanvasDrag?.deviceId === layout.device.id ? " dragging" : ""}" transform="translate(${layout.x} ${layout.y})">`);
    parts.push(`<rect class="board-editor-device-body" data-device-drag="${escapeHtml(layout.device.id)}" width="${layout.width}" height="${layout.height}" rx="12" />`);
    parts.push(`<text class="board-editor-device-title" x="14" y="22">${escapeHtml(layout.device.display)}</text>`);
    parts.push(`<text class="board-editor-device-subtitle" x="14" y="38">${escapeHtml(layout.device.category || "device")}${layout.device.bus ? ` • ${escapeHtml(layout.device.bus)}` : ""}</text>`);
    parts.push(`<circle class="board-editor-device-delete" data-device-remove="${escapeHtml(layout.device.id)}" cx="${layout.width - 16}" cy="16" r="10" />`);
    parts.push(`<text class="board-editor-device-delete-label" x="${layout.width - 16}" y="20" text-anchor="middle">×</text>`);
    layout.pinLayouts.forEach((pin, index) => {
      const pinY = layout.headerHeight + index * 26 + 6;
      const selected = boardEditorCanvasStart?.type === "device" && boardEditorCanvasStart.deviceId === layout.device.id && boardEditorCanvasStart.pin === pin.name ? " selected" : "";
      parts.push(`<rect class="board-editor-device-pin${selected}" data-device-pin="${escapeHtml(layout.device.id)}" data-device-pin-name="${escapeHtml(pin.name)}" x="10" y="${pinY}" width="${layout.width - 20}" height="20" rx="8" />`);
      parts.push(`<text class="board-editor-device-pin-label" x="${layout.anchorSide === "left" ? 18 : layout.width - 18}" y="${pinY + 13}" text-anchor="${layout.anchorSide === "left" ? "start" : "end"}">${escapeHtml(pin.name)}</text>`);
    });
    parts.push("</g>");
  });

  parts.push("</svg>");
  shell.innerHTML = parts.join("");
  applyBoardEditorCanvasZoom();

  const svg = shell.querySelector("svg");
  if (!svg) return;

  svg.querySelectorAll("[data-board-pin]").forEach((element) => {
    element.addEventListener("click", () => {
      handleBoardEditorEndpointClick({ type: "board", pin: Number(element.dataset.boardPin) });
    });
  });

  svg.querySelectorAll("[data-device-pin]").forEach((element) => {
    element.addEventListener("click", () => {
      handleBoardEditorEndpointClick({
        type: "device",
        deviceId: element.dataset.devicePin,
        pin: element.dataset.devicePinName,
      });
    });
  });

  svg.querySelectorAll("[data-wire-index]").forEach((element) => {
    element.addEventListener("click", () => {
      removeBoardEditorConnection(Number(element.dataset.wireIndex));
    });
  });

  svg.querySelectorAll("[data-device-remove]").forEach((element) => {
    element.addEventListener("click", (event) => {
      event.stopPropagation();
      removeBoardEditorCanvasDevice(element.dataset.deviceRemove);
    });
  });

  svg.querySelectorAll("[data-device-drag]").forEach((element) => {
    element.addEventListener("pointerdown", (event) => {
      startBoardEditorDeviceDrag(element.dataset.deviceDrag, event, svg);
    });
  });
}

function handleBoardEditorEndpointClick(endpoint) {
  const board = boardEditorPreviewBoard || syncBoardEditorPreview();
  if (!board) return;

  if (!boardEditorCanvasStart) {
    boardEditorCanvasStart = endpoint;
    renderBoardEditorCanvas(board);
    setBoardEditorCanvasStatus("Connection start selected. Click the matching endpoint to create or remove a wire.");
    return;
  }

  const sameStart = boardEditorCanvasStart.type === endpoint.type
    && boardEditorCanvasStart.pin === endpoint.pin
    && boardEditorCanvasStart.deviceId === endpoint.deviceId;
  if (sameStart) {
    boardEditorCanvasStart = null;
    renderBoardEditorCanvas(board);
    setBoardEditorCanvasStatus("Pending connection cleared.");
    return;
  }

  if (boardEditorCanvasStart.type === endpoint.type) {
    boardEditorCanvasStart = endpoint;
    renderBoardEditorCanvas(board);
    setBoardEditorCanvasStatus("Start point changed. Click an endpoint on the other side to wire it.");
    return;
  }

  const boardPin = boardEditorCanvasStart.type === "board" ? Number(boardEditorCanvasStart.pin) : Number(endpoint.pin);
  const deviceId = boardEditorCanvasStart.type === "device" ? boardEditorCanvasStart.deviceId : endpoint.deviceId;
  const devicePin = boardEditorCanvasStart.type === "device" ? boardEditorCanvasStart.pin : endpoint.pin;
  const existingIndex = board.manual_connections.findIndex((connection) => (
    Number(connection.board_pin) === Number(boardPin)
    && connection.device_id === deviceId
    && connection.device_pin === devicePin
  ));

  if (existingIndex >= 0) {
    board.manual_connections.splice(existingIndex, 1);
    boardEditorCanvasStart = null;
    writeBoardEditorFromCanvas(board, `Removed wire from MCU pin ${boardPin} to ${deviceId}.${devicePin}.`);
    return;
  }

  board.manual_connections.push({ board_pin: Number(boardPin), device_id: deviceId, device_pin: devicePin });
  boardEditorCanvasStart = null;
  writeBoardEditorFromCanvas(board, `Connected MCU pin ${boardPin} to ${deviceId}.${devicePin}.`);
}

function removeBoardEditorConnection(index) {
  const board = boardEditorPreviewBoard || syncBoardEditorPreview();
  if (!board || !Number.isInteger(index) || index < 0 || index >= board.manual_connections.length) return;
  const [connection] = board.manual_connections.splice(index, 1);
  boardEditorCanvasStart = null;
  writeBoardEditorFromCanvas(board, `Removed wire from MCU pin ${connection.board_pin} to ${connection.device_id}.${connection.device_pin}.`);
}

function nextBoardEditorDeviceId(board, label) {
  const base = slugifyBoardEditorToken(label);
  const known = new Set(board.external_devices.map(device => device.id));
  let candidate = base;
  let index = 2;
  while (known.has(candidate)) {
    candidate = `${base}_${index}`;
    index += 1;
  }
  return candidate;
}

function addBoardEditorCanvasDevice() {
  const board = boardEditorPreviewBoard || syncBoardEditorPreview();
  if (!board) return;
  const nameInput = $("#boardEditorDeviceName");
  const pinsInput = $("#boardEditorDevicePins");
  const display = String(nameInput?.value || "").trim();
  if (!display) {
    setBoardEditorCanvasStatus("Enter a device name before adding it to the canvas.", "error");
    return;
  }

  const pins = String(pinsInput?.value || "")
    .split(",")
    .map(value => value.trim())
    .filter(Boolean);
  const device = normalizeBoardEditorDevice({
    id: nextBoardEditorDeviceId(board, display),
    display,
    category: "manual",
    required_signals: pins,
    pins,
  }, board.external_devices.length);
  board.external_devices.push(device);
  boardEditorCanvasStart = null;
  writeBoardEditorFromCanvas(board, `Added ${device.display} to the canvas. Drag it into place and start wiring pins.`);
  if (nameInput) nameInput.value = "";
  if (pinsInput) pinsInput.value = "";
}

function addBoardEditorLibraryDevice() {
  const board = boardEditorPreviewBoard || syncBoardEditorPreview();
  if (!board) return;
  const select = $("#boardEditorDeviceLibrary");
  const key = select?.value;
  if (!key) {
    setBoardEditorCanvasStatus("Select a supported device or parsed sensor first.", "error");
    return;
  }

  const entry = boardEditorDeviceLibrary.find((item) => item.key === key);
  if (!entry) {
    setBoardEditorCanvasStatus("Selected library device is no longer available.", "error");
    return;
  }

  const template = cloneJson(entry.device);
  const label = template.display || template.id || "device";
  const signals = Array.isArray(template.required_signals) && template.required_signals.length
    ? template.required_signals
    : boardEditorSignalsForBus(template.bus_family || inferDeviceBusFamily(template));
  const device = normalizeBoardEditorDevice({
    ...template,
    id: nextBoardEditorDeviceId(board, template.id || label),
    display: label,
    required_signals: signals,
    pins: signals,
  }, board.external_devices.length);
  board.external_devices.push(device);
  boardEditorCanvasStart = null;
  writeBoardEditorFromCanvas(board, `Added ${device.display} from the device library.`);
  if (select) select.value = "";
}

function removeBoardEditorCanvasDevice(deviceId) {
  const board = boardEditorPreviewBoard || syncBoardEditorPreview();
  if (!board || !deviceId) return;
  const before = board.external_devices.length;
  board.external_devices = board.external_devices.filter(device => device.id !== deviceId);
  if (board.external_devices.length === before) return;
  board.manual_connections = board.manual_connections.filter(connection => connection.device_id !== deviceId);
  if (boardEditorCanvasStart?.type === "device" && boardEditorCanvasStart.deviceId === deviceId) {
    boardEditorCanvasStart = null;
  }
  writeBoardEditorFromCanvas(board, `Removed ${deviceId} from the canvas.`);
}

function autoLayoutBoardEditorDevices() {
  const board = boardEditorPreviewBoard || syncBoardEditorPreview();
  if (!board) return;
  board.external_devices.forEach((device, index) => {
    device.x = 860 + (index % 2) * 260;
    device.y = 140 + Math.floor(index / 2) * 190;
  });
  writeBoardEditorFromCanvas(board, "Arranged external devices around the package.");
}

function clearBoardEditorConnections() {
  const board = boardEditorPreviewBoard || syncBoardEditorPreview();
  if (!board) return;
  board.manual_connections = [];
  boardEditorCanvasStart = null;
  writeBoardEditorFromCanvas(board, "Removed all manual wires from the canvas.");
}

function startBoardEditorDeviceDrag(deviceId, event, svg) {
  if (!deviceId || !boardEditorPreviewBoard) return;
  event.preventDefault();
  event.stopPropagation();
  const device = boardEditorPreviewBoard.external_devices.find((entry) => entry.id === deviceId);
  if (!device) return;
  const point = boardEditorSvgPoint(svg, event.clientX, event.clientY);
  boardEditorCanvasDrag = {
    deviceId,
    offsetX: point.x - Number(device.x),
    offsetY: point.y - Number(device.y),
  };

  const onMove = (moveEvent) => {
    if (!boardEditorCanvasDrag || !boardEditorPreviewBoard) return;
    const currentSvg = $("#boardEditorCanvasShell svg");
    if (!currentSvg) return;
    const nextPoint = boardEditorSvgPoint(currentSvg, moveEvent.clientX, moveEvent.clientY);
    const activeDevice = boardEditorPreviewBoard.external_devices.find((entry) => entry.id === boardEditorCanvasDrag.deviceId);
    if (!activeDevice) return;
    activeDevice.x = Math.max(560, Math.min(1140, nextPoint.x - boardEditorCanvasDrag.offsetX));
    activeDevice.y = Math.max(70, Math.min(760, nextPoint.y - boardEditorCanvasDrag.offsetY));
    renderBoardEditorCanvas(boardEditorPreviewBoard);
    setBoardEditorCanvasStatus(`Dragging ${activeDevice.display}. Release to keep the new position.`);
  };

  const onUp = () => {
    document.removeEventListener("pointermove", onMove);
    document.removeEventListener("pointerup", onUp);
    if (!boardEditorCanvasDrag || !boardEditorPreviewBoard) {
      boardEditorCanvasDrag = null;
      return;
    }
    const activeDevice = boardEditorPreviewBoard.external_devices.find((entry) => entry.id === boardEditorCanvasDrag.deviceId);
    boardEditorCanvasDrag = null;
    writeBoardEditorFromCanvas(boardEditorPreviewBoard, activeDevice ? `Placed ${activeDevice.display} on the canvas.` : "Updated canvas layout.");
  };

  document.addEventListener("pointermove", onMove);
  document.addEventListener("pointerup", onUp);
}

function initBoardEditor() {
  const loadBtn = $("#boardEditorBtnLoad");
  const validateBtn = $("#boardEditorBtnValidate");
  const formatBtn = $("#boardEditorBtnFormat");
  const applyBtn = $("#boardEditorBtnApply");
  const saveRepoBtn = $("#boardEditorBtnSaveRepo");
  const exportBtn = $("#boardEditorBtnExport");
  const importBtn = $("#boardEditorBtnImport");
  const fileInput = $("#boardEditorFileInput");
  const librarySelect = $("#boardEditorDeviceLibrary");
  const addLibraryBtn = $("#boardEditorBtnAddLibrary");
  const addDeviceBtn = $("#boardEditorBtnAddDevice");
  const autoLayoutBtn = $("#boardEditorBtnAutoLayout");
  const clearLinksBtn = $("#boardEditorBtnClearLinks");
  const zoomOutBtn = $("#boardEditorZoomOut");
  const zoomInBtn = $("#boardEditorZoomIn");
  const zoomFitBtn = $("#boardEditorZoomFit");
  const editor = $("#boardEditorJson");

  if (!loadBtn || !validateBtn || !formatBtn || !applyBtn || !saveRepoBtn || !exportBtn || !importBtn || !fileInput || !librarySelect || !addLibraryBtn || !addDeviceBtn || !autoLayoutBtn || !clearLinksBtn || !zoomOutBtn || !zoomInBtn || !zoomFitBtn || !editor) {
    return;
  }

  loadBtn.addEventListener("click", () => {
    if (!boardData) {
      setBoardEditorStatus("No board is currently loaded.", "error");
      return;
    }
    boardEditorCanvasStart = null;
    setBoardEditorText(currentBoardForEditor());
    setBoardEditorCanvasStatus(`Loaded ${boardData.board} into the canvas. Click a package pin, then a device pin to wire them.`, "ok");
    setBoardEditorStatus(`Loaded ${boardData.board} into the editor.`, "ok");
  });

  validateBtn.addEventListener("click", () => {
    try {
      validateBoardEditorJson();
    } catch (err) {
      setBoardEditorStatus(err.message, "error");
    }
  });

  formatBtn.addEventListener("click", () => {
    try {
      const board = validateBoardEditorJson();
      setBoardEditorText(board);
      setBoardEditorCanvasStatus(`Formatted ${board.board} and refreshed the canvas.`, "ok");
      setBoardEditorStatus(`Formatted ${board.board}.`, "ok");
    } catch (err) {
      setBoardEditorStatus(err.message, "error");
    }
  });

  applyBtn.addEventListener("click", () => {
    try {
      applyBoardEditorJson();
    } catch (err) {
      setBoardEditorStatus(err.message, "error");
    }
  });

  saveRepoBtn.addEventListener("click", async () => {
    try {
      await saveBoardEditorDraft();
    } catch (err) {
      setBoardEditorStatus(err.message, "error");
    }
  });

  exportBtn.addEventListener("click", () => {
    try {
      exportBoardEditorJson();
    } catch (err) {
      setBoardEditorStatus(err.message, "error");
    }
  });

  importBtn.addEventListener("click", () => {
    fileInput.value = "";
    fileInput.click();
  });

  fileInput.addEventListener("change", async () => {
    const [file] = fileInput.files || [];
    if (!file) return;
    try {
      const text = await file.text();
      editor.value = text;
      const board = validateBoardEditorJson();
      boardEditorCanvasStart = null;
      setBoardEditorStatus(`Imported ${file.name} for ${board.board}.`, "ok");
    } catch (err) {
      setBoardEditorStatus(err.message, "error");
    }
  });

  editor.addEventListener("input", () => {
    boardEditorCanvasStart = null;
    queueBoardEditorPreviewSync();
  });

  librarySelect.addEventListener("change", () => {
    const entry = boardEditorDeviceLibrary.find((item) => item.key === librarySelect.value);
    if (!entry) return;
    const nameInput = $("#boardEditorDeviceName");
    const pinsInput = $("#boardEditorDevicePins");
    if (nameInput) nameInput.value = entry.device.display || "";
    if (pinsInput) pinsInput.value = (entry.device.required_signals || []).join(", ");
  });

  addLibraryBtn.addEventListener("click", () => {
    try {
      addBoardEditorLibraryDevice();
    } catch (err) {
      setBoardEditorCanvasStatus(err.message, "error");
    }
  });

  addDeviceBtn.addEventListener("click", () => {
    try {
      addBoardEditorCanvasDevice();
    } catch (err) {
      setBoardEditorCanvasStatus(err.message, "error");
    }
  });

  autoLayoutBtn.addEventListener("click", () => {
    try {
      autoLayoutBoardEditorDevices();
    } catch (err) {
      setBoardEditorCanvasStatus(err.message, "error");
    }
  });

  clearLinksBtn.addEventListener("click", () => {
    try {
      clearBoardEditorConnections();
    } catch (err) {
      setBoardEditorCanvasStatus(err.message, "error");
    }
  });

  zoomOutBtn.addEventListener("click", () => {
    boardEditorCanvasZoomOut();
  });

  zoomInBtn.addEventListener("click", () => {
    boardEditorCanvasZoomIn();
  });

  zoomFitBtn.addEventListener("click", () => {
    boardEditorCanvasFit();
  });

  void loadBoardEditorDrafts();
  void loadBoardEditorDeviceLibrary();
  updateBoardEditorCanvasZoomLabel();
}

// ── Peripheral panel ─────────────────────────────────────────────────

function renderPeripherals() {
  const panel = periphPanel;
  // Keep the heading, clear the rest
  panel.innerHTML = '<h3>Peripherals</h3>';

  // Group by category
  const groups = {};
  boardData.peripherals.forEach(p => {
    let cat = "Other";
    if (p.name.startsWith("gpio"))  cat = "GPIO";
    else if (p.name.startsWith("uart")) cat = "UART";
    else if (p.name.startsWith("spi"))  cat = "SPI";
    else if (p.name.startsWith("i2c"))  cat = "I2C";
    else if (p.name.startsWith("can"))  cat = "CAN";
    else if (p.name.startsWith("tim"))  cat = "Timers / PWM";
    else if (p.name.startsWith("adc") || p.name.startsWith("dac")) cat = "Analog";
    else if (p.name.startsWith("comp")) cat = "Analog";
    if (!groups[cat]) groups[cat] = [];
    groups[cat].push(p);
  });

  for (const [cat, periphs] of Object.entries(groups)) {
    const h = document.createElement("h3");
    h.textContent = cat;
    panel.appendChild(h);

    periphs.forEach(p => {
      const row = document.createElement("div");
      row.className = "periph-item" + (periphStates[p.name] ? " enabled" : "");
      row.dataset.periph = p.name;

      row.innerHTML = `
        <span class="dot"></span>
        <span class="periph-label">${p.display}</span>
        ${boardData.cores && boardData.cores.length > 1 && p.available_cores && p.available_cores.length > 1 ? `
          <select class="periph-core-select" data-periph-core="${p.name}">
            ${p.available_cores.map(coreId => {
              const core = boardData.cores.find(entry => entry.id === coreId);
              const label = core ? core.name : coreId;
              const selected = periphCoreStates[p.name] === coreId ? 'selected' : '';
              return `<option value="${coreId}" ${selected}>${label}</option>`;
            }).join("")}
          </select>
        ` : ""}
        <div class="periph-toggle ${periphStates[p.name] ? 'on' : ''}"
             data-periph="${p.name}"></div>
      `;

      const coreSelect = row.querySelector(".periph-core-select");
      if (coreSelect) {
        coreSelect.addEventListener("click", e => e.stopPropagation());
        coreSelect.addEventListener("change", e => {
          periphCoreStates[p.name] = e.target.value;
        });
      }

      const toggle = row.querySelector(".periph-toggle");
      toggle.addEventListener("click", (e) => {
        e.stopPropagation();
        periphStates[p.name] = !periphStates[p.name];
        toggle.classList.toggle("on", periphStates[p.name]);
        row.classList.toggle("enabled", periphStates[p.name]);
        updatePinVisuals();
      });

      panel.appendChild(row);
    });
  }
}

// ── Chip SVG renderer ────────────────────────────────────────────────

/** Detect whether the package name indicates a BGA / grid layout. */
function isBgaPackage(pkgName) {
  if (!pkgName) return false;
  const up = pkgName.toUpperCase();
  return /BGA|WLCSP|CSP|LGA/i.test(up);
}

function renderChip() {
  if (!boardData) return;

  if (isBgaPackage(boardData.package)) {
    renderChipBga();
  } else {
    renderChipQfp();
  }

  // Attach click handlers (shared)
  chipContainer.querySelectorAll(".pin-pad").forEach(el => {
    el.addEventListener("click", () => {
      const pinNum = parseInt(el.dataset.pin);
      selectPin(pinNum);
    });
  });
}

// ── QFP / LQFP / QFN renderer (4-sided) ─────────────────────────────

function renderChipQfp() {
  const pinCount = boardData.pin_count;

  // Gather pins per side from board data
  const sides = { left: [], bottom: [], right: [], top: [] };
  boardData.pins.forEach(p => {
    const s = p.side || "left";
    if (sides[s]) sides[s].push(p);
    else sides.left.push(p); // fallback
  });

  // Compute how many pins on the longest side
  const maxSide = Math.max(sides.left.length, sides.bottom.length,
                           sides.right.length, sides.top.length, 1);

  // Layout constants
  const PAD_W     = 48;   // pin pad width
  const PAD_H     = 22;   // pin pad height
  const PAD_GAP   = 6;    // gap between pads
  const LABEL_W   = 90;   // space for labels outside
  const BODY_PAD  = 8;    // gap between pads and body

  const bodyW     = maxSide * (PAD_H + PAD_GAP) + 20;
  const bodyH     = bodyW;  // square body

  const svgW = bodyW + 2 * (PAD_W + LABEL_W + BODY_PAD + 20);
  const svgH = bodyH + 2 * (PAD_W + LABEL_W + BODY_PAD + 20);

  const cx = svgW / 2;
  const cy = svgH / 2;

  const bodyX = cx - bodyW / 2;
  const bodyY = cy - bodyH / 2;

  let svg = `<svg class="chip-svg" width="${svgW}" height="${svgH}" viewBox="0 0 ${svgW} ${svgH}" xmlns="http://www.w3.org/2000/svg">`;

  // Chip body
  svg += `<rect class="chip-body" x="${bodyX}" y="${bodyY}" width="${bodyW}" height="${bodyH}" rx="4"/>`;

  // Pin-1 dot
  svg += `<circle class="chip-dot" cx="${bodyX + 12}" cy="${bodyY + 12}" r="4"/>`;

  // Chip label
  svg += `<text x="${cx}" y="${cy - 8}" text-anchor="middle" fill="var(--fg-dim)" font-size="14" font-weight="700" font-family="Consolas">${boardData.soc}</text>`;
  svg += `<text x="${cx}" y="${cy + 10}" text-anchor="middle" fill="var(--fg-dim)" font-size="10" font-family="Consolas">${boardData.package}</text>`;

  // LEFT: pins go top to bottom, pads extend left from body
  sides.left.forEach((pin, i) => {
    const px = bodyX - BODY_PAD - PAD_W;
    const py = bodyY + 10 + i * (PAD_H + PAD_GAP);
    renderQfpPin(svg, pin, px, py, PAD_W, PAD_H, "left");
  });

  // BOTTOM: pins go left to right, pads extend below body
  sides.bottom.forEach((pin, i) => {
    const px = bodyX + 10 + i * (PAD_H + PAD_GAP);
    const py = bodyY + bodyH + BODY_PAD;
    renderQfpPin(svg, pin, px, py, PAD_H, PAD_W, "bottom");
  });

  // RIGHT: pins go bottom to top, pads extend right from body
  sides.right.forEach((pin, i) => {
    const px = bodyX + bodyW + BODY_PAD;
    const py = bodyY + bodyH - 10 - PAD_H - i * (PAD_H + PAD_GAP);
    renderQfpPin(svg, pin, px, py, PAD_W, PAD_H, "right");
  });

  // TOP: pins go right to left, pads extend above body
  sides.top.forEach((pin, i) => {
    const px = bodyX + bodyW - 10 - PAD_H - i * (PAD_H + PAD_GAP);
    const py = bodyY - BODY_PAD - PAD_W;
    renderQfpPin(svg, pin, px, py, PAD_H, PAD_W, "top");
  });

  function renderQfpPin(svg_, pin, x, y, w, h, side) {
    const state = pinStates[pin.number];
    const isSelected = selectedPin === pin.number;

    let cls = "pin-pad";
    if (pin.kind === "power")  cls += " power";
    else if (pin.kind === "ground") cls += " ground";
    else if (pin.kind === "special") cls += " special";
    else if (state && state.af) cls += " assigned " + periphColor(state.af.peripheral);
    if (isSelected) cls += " selected";

    svg += `<rect class="${cls}" x="${x}" y="${y}" width="${w}" height="${h}" rx="3"
                  data-pin="${pin.number}"/>`;

    let numX, numY, nameX, nameY, funcX, funcY;
    let numAnchor = "middle", nameAnchor = "middle";

    if (side === "left") {
      numX  = x + w + 4;  numY  = y + h/2 + 3;  numAnchor = "start";
      nameX = x - 4;      nameY = y + h/2 + 3;   nameAnchor = "end";
      funcX = x - 4;      funcY = y + h/2 + 13;
    } else if (side === "right") {
      numX  = x - 4;       numY  = y + h/2 + 3;  numAnchor = "end";
      nameX = x + w + 4;   nameY = y + h/2 + 3;  nameAnchor = "start";
      funcX = x + w + 4;   funcY = y + h/2 + 13;
    } else if (side === "bottom") {
      numX  = x + w/2;     numY  = y - 4;         numAnchor = "middle";
      nameX = x + w/2;     nameY = y + h + 12;    nameAnchor = "middle";
      funcX = x + w/2;     funcY = y + h + 23;
    } else { // top
      numX  = x + w/2;     numY  = y + h + 12;    numAnchor = "middle";
      nameX = x + w/2;     nameY = y - 4;         nameAnchor = "middle";
      funcX = x + w/2;     funcY = y - 14;
    }

    svg += `<text class="pin-num" x="${numX}" y="${numY}" text-anchor="${numAnchor}">${pin.number}</text>`;
    svg += `<text class="pin-name" x="${nameX}" y="${nameY}" text-anchor="${nameAnchor}">${pin.name}</text>`;

    const funcLabel = state && state.af ? state.af.name : (pin.kind !== "io" ? pin.default_function : "");
    if (funcLabel) {
      const fanchor = (side === "left") ? "end" : (side === "right") ? "start" : "middle";
      svg += `<text class="pin-func" x="${funcX}" y="${funcY}" text-anchor="${fanchor}">${funcLabel}</text>`;
    }
  }

  svg += `</svg>`;
  chipContainer.innerHTML = svg;
}

// ── BGA / WLCSP / UFBGA renderer (grid layout) ──────────────────────

function renderChipBga() {
  const pins = boardData.pins;
  const pinCount = boardData.pin_count;

  // Try to determine grid dimensions from pin names or pin numbers
  // BGA naming: letter(s) + number  e.g. "A1", "AB12"
  // Or encoded pin numbers: row*100 + col  (e.g. 101=row1/col1, 305=row3/col5)
  const bgaRe = /^([A-Z]{1,2})(\d+)$/;

  const rowSet = new Set();
  const colSet = new Set();
  const gridMap = {};  // { "row_col": pin }

  // First try BGA letter+number naming
  let bgaNameMatch = 0;
  for (const pin of pins) {
    const m = bgaRe.exec(pin.name.toUpperCase());
    if (m) bgaNameMatch++;
  }

  const useBgaNames = bgaNameMatch > pinCount * 0.3;

  if (useBgaNames) {
    // Use BGA ball names (A1, B2, ...)
    for (const pin of pins) {
      const m = bgaRe.exec(pin.name.toUpperCase());
      if (m) {
        rowSet.add(m[1]);
        colSet.add(parseInt(m[2]));
        gridMap[`${m[1]}_${m[2]}`] = pin;
      }
    }
  } else {
    // Use encoded pin numbers (row*100+col) or fall back to sequential grid
    let encoded = 0;
    for (const pin of pins) {
      if (pin.number >= 100) {
        const row = Math.floor(pin.number / 100);
        const col = pin.number % 100;
        if (row >= 1 && row <= 30 && col >= 1 && col <= 30) encoded++;
      }
    }

    if (encoded > pinCount * 0.5) {
      // Encoded row*100+col format
      for (const pin of pins) {
        const row = Math.floor(pin.number / 100);
        const col = pin.number % 100;
        const rowLetter = String.fromCharCode(64 + row); // 1→A, 2→B, ...
        rowSet.add(rowLetter);
        colSet.add(col);
        gridMap[`${rowLetter}_${col}`] = pin;
      }
    } else {
      // Fallback: arrange in a square grid by sequence
      const side = Math.ceil(Math.sqrt(pinCount));
      let idx = 0;
      for (let r = 0; r < side; r++) {
        const rowLetter = String.fromCharCode(65 + r);
        rowSet.add(rowLetter);
        for (let c = 1; c <= side; c++) {
          colSet.add(c);
          if (idx < pins.length) {
            gridMap[`${rowLetter}_${c}`] = pins[idx++];
          }
        }
      }
    }
  }

  // Letter sorting for rows (A, B, ..., Z, AA, AB, ...)
  const letterVal = (s) => {
    let v = 0;
    for (let i = 0; i < s.length; i++) v = v * 26 + (s.charCodeAt(i) - 64);
    return v;
  };

  const gridRows = [...rowSet].sort((a, b) => letterVal(a) - letterVal(b));
  const gridCols = [...colSet].sort((a, b) => a - b);

  const nRows = gridRows.length;
  const nCols = gridCols.length;

  // Layout constants for BGA
  const BALL_SIZE  = 28;   // ball pad size
  const BALL_GAP   = 4;    // gap between balls
  const CELL       = BALL_SIZE + BALL_GAP;
  const HEADER     = 24;   // row/col header width
  const MARGIN     = 60;   // outer margin for labels

  const gridW = nCols * CELL;
  const gridH = nRows * CELL;

  const svgW = gridW + 2 * MARGIN + HEADER;
  const svgH = gridH + 2 * MARGIN + HEADER;

  const gridX = MARGIN + HEADER;
  const gridY = MARGIN + HEADER;

  let svg = `<svg class="chip-svg" width="${svgW}" height="${svgH}" viewBox="0 0 ${svgW} ${svgH}" xmlns="http://www.w3.org/2000/svg">`;

  // Chip body background
  svg += `<rect class="chip-body" x="${gridX - 6}" y="${gridY - 6}" width="${gridW + 12}" height="${gridH + 12}" rx="6"/>`;

  // Pin-1 dot (top-left corner, A1)
  svg += `<circle class="chip-dot" cx="${gridX - 12}" cy="${gridY - 12}" r="5"/>`;

  // Chip label (centered above)
  const titleY = 20;
  svg += `<text x="${svgW / 2}" y="${titleY}" text-anchor="middle" fill="var(--fg-dim)" font-size="14" font-weight="700" font-family="Consolas">${boardData.soc}</text>`;
  svg += `<text x="${svgW / 2}" y="${titleY + 16}" text-anchor="middle" fill="var(--fg-dim)" font-size="10" font-family="Consolas">${boardData.package}</text>`;

  // Column headers (numbers)
  gridCols.forEach((c, ci) => {
    const x = gridX + ci * CELL + CELL / 2;
    svg += `<text x="${x}" y="${gridY - 10}" text-anchor="middle" fill="var(--fg-dim)" font-size="10" font-family="Consolas">${c}</text>`;
  });

  // Row headers (letters) + balls
  gridRows.forEach((r, ri) => {
    const y = gridY + ri * CELL;

    // Row header
    svg += `<text x="${gridX - 12}" y="${y + CELL / 2 + 3}" text-anchor="middle" fill="var(--fg-dim)" font-size="10" font-family="Consolas">${r}</text>`;

    gridCols.forEach((c, ci) => {
      const pin = gridMap[`${r}_${c}`];
      if (!pin) return; // empty position

      const x = gridX + ci * CELL;
      const state = pinStates[pin.number];
      const isSelected = selectedPin === pin.number;

      let cls = "pin-pad bga-ball";
      if (pin.kind === "power")  cls += " power";
      else if (pin.kind === "ground") cls += " ground";
      else if (pin.kind === "special") cls += " special";
      else if (state && state.af) cls += " assigned " + periphColor(state.af.peripheral);
      if (isSelected) cls += " selected";

      // Ball (circle inside cell)
      const bcx = x + CELL / 2;
      const bcy = y + CELL / 2;
      const br = BALL_SIZE / 2;
      svg += `<circle class="${cls}" cx="${bcx}" cy="${bcy}" r="${br}" data-pin="${pin.number}"/>`;

      // Pin name inside or below ball
      const shortName = pin.name.length > 4 ? pin.name.slice(0, 4) : pin.name;
      svg += `<text class="bga-label" x="${bcx}" y="${bcy + 3}" text-anchor="middle" font-size="7" font-family="Consolas" fill="var(--fg)">${shortName}</text>`;

      // Show assigned function as tooltip title
      const funcLabel = state && state.af ? state.af.name : (pin.kind !== "io" ? pin.default_function : "");
      if (funcLabel) {
        svg += `<title>${pin.name}: ${funcLabel}</title>`;
      }
    });
  });

  svg += `</svg>`;
  chipContainer.innerHTML = svg;
}

function updatePinVisuals() {
  renderChip();
}

// ── Pin selection & config panel ─────────────────────────────────────

function selectPin(pinNum) {
  selectedPin = pinNum;
  renderChip();
  renderConfigPanel();
}

function renderConfigPanel() {
  const panel = configPanel;
  const deviceSection = buildExternalDeviceSection();

  if (!selectedPin || !boardData) {
    panel.innerHTML = `<div class="empty-state"><div>Click a pin to configure</div>
      <div class="hint">or enable a peripheral on the left</div></div>${deviceSection}`;
    wireExternalDeviceControls(panel);
    return;
  }

  const pin = boardData.pins.find(p => p.number === selectedPin);
  if (!pin) return;

  // For BGA packages, show grid position (e.g. "A1") instead of raw pin number
  const bgaPkg = isBgaPackage(boardData.package);
  let pinLabel;
  if (bgaPkg && pin.number >= 100) {
    const row = Math.floor(pin.number / 100);
    const col = pin.number % 100;
    const rowLetter = String.fromCharCode(64 + row);
    pinLabel = `${rowLetter}${col}`;
  } else {
    pinLabel = `Pin ${pin.number}`;
  }

  if (pin.kind !== "io") {
    panel.innerHTML = `<h3><span class="pin-badge">${pin.name}</span> ${pinLabel}</h3>
      <div class="empty-state">${pin.kind === 'power' ? 'Power pin' : pin.kind === 'ground' ? 'Ground pin' : 'Special pin'}<br>${pin.default_function}</div>${deviceSection}`;
    wireExternalDeviceControls(panel);
    return;
  }

  const state = pinStates[pin.number] || {};

  let html = `<h3><span class="pin-badge">${pin.name}</span> ${pinLabel}</h3>`;

  // Reset button
  html += `<div style="margin-bottom:12px;">
    <button class="btn" id="btnResetPin" style="font-size:11px;">Reset to Default</button>
  </div>`;

  // Alternate functions list
  html += `<div class="config-section"><label>Alternate Function</label><ul class="af-list">`;

  // "Not assigned" option
  html += `<li class="${!state.af ? 'active' : ''}" data-af-idx="-1">
    <span class="af-id">--</span>
    <span>Not assigned</span></li>`;

  pin.alt_functions.forEach((af, idx) => {
    const isActive = state.af && state.af.function_id === af.function_id && state.af.name === af.name;
    // Check if peripheral is enabled
    const periphEnabled = periphStates[af.peripheral];
    const conflictClass = !periphEnabled && af.peripheral !== "gpio" ? " conflict" : "";

    html += `<li class="${isActive ? 'active' : ''}${conflictClass}" data-af-idx="${idx}">
      <span class="af-id">F${af.function_id}</span>
      <span>${af.name}</span>
      ${!periphEnabled && af.peripheral.startsWith("gpio") ? '' :
        !periphEnabled ? '<span class="conflict-badge">OFF</span>' : ''}
      <span class="af-dir">${af.direction}</span>
    </li>`;
  });

  html += `</ul></div>`;

  // Pin properties
  const props = state.props || {};
  html += `<div class="config-section"><label>Pin Properties</label>
    <div class="prop-row"><input type="checkbox" id="propPullUp" ${props.bias_pull_up ? 'checked' : ''}> <span>Pull-up</span></div>
    <div class="prop-row"><input type="checkbox" id="propPullDown" ${props.bias_pull_down ? 'checked' : ''}> <span>Pull-down</span></div>
    <div class="prop-row"><input type="checkbox" id="propOpenDrain" ${props.drive_open_drain ? 'checked' : ''}> <span>Open-drain</span></div>
    <div class="prop-row"><input type="checkbox" id="propInputEn" ${props.input_enable ? 'checked' : ''}> <span>Input enable</span></div>
  </div>`;

  // PINCM info
  if (pin.alt_functions.length) {
    const pincm = pin.alt_functions[0].pincm;
    html += `<div class="config-section" style="font-size:11px;color:var(--fg-dim);">
      PINCM: ${pincm} &nbsp;|&nbsp; Port ${pin.port} bit ${pin.gpio_num}
    </div>`;
  }

  panel.innerHTML = html + deviceSection;

  // Attach event handlers
  panel.querySelectorAll(".af-list li").forEach(li => {
    li.addEventListener("click", () => {
      const idx = parseInt(li.dataset.afIdx);
      if (idx === -1) {
        delete pinStates[pin.number];
      } else {
        const af = pin.alt_functions[idx];
        pinStates[pin.number] = {
          af: af,
          props: pinStates[pin.number]?.props || {},
        };
        // Auto-enable the peripheral
        if (!periphStates[af.peripheral]) {
          periphStates[af.peripheral] = true;
          renderPeripherals();
        }
      }
      renderChip();
      renderConfigPanel();
    });
  });

  // Property checkboxes
  ["propPullUp", "propPullDown", "propOpenDrain", "propInputEn"].forEach(id => {
    const el = panel.querySelector(`#${id}`);
    if (el) {
      el.addEventListener("change", () => {
        if (!pinStates[pin.number]) {
          pinStates[pin.number] = { af: null, props: {} };
        }
        const propKey = {
          propPullUp: "bias_pull_up",
          propPullDown: "bias_pull_down",
          propOpenDrain: "drive_open_drain",
          propInputEn: "input_enable",
        }[id];
        if (!pinStates[pin.number].props) pinStates[pin.number].props = {};
        pinStates[pin.number].props[propKey] = el.checked;
      });
    }
  });

  // Reset button
  const resetBtn = panel.querySelector("#btnResetPin");
  if (resetBtn) {
    resetBtn.addEventListener("click", () => {
      delete pinStates[pin.number];
      renderChip();
      renderConfigPanel();
    });
  }

  wireExternalDeviceControls(panel);
}

// ── Generate overlay ─────────────────────────────────────────────────

async function generateOutput() {
  if (!boardData) return;

  const assignments = [];
  for (const [pinNum, state] of Object.entries(pinStates)) {
    if (!state.af) continue;
    const pin = boardData.pins.find(p => p.number === parseInt(pinNum));
    if (!pin) continue;

    assignments.push({
      pin_name:        pin.name,
      pincm:           state.af.pincm,
      function_id:     state.af.function_id,
      af_name:         state.af.name,
      peripheral:      state.af.peripheral,
      signal:          state.af.signal,
      direction:       state.af.direction || "io",
      zephyr_pinmux:   state.af.zephyr_pinmux || "",
      bias_pull_up:    state.props?.bias_pull_up || false,
      bias_pull_down:  state.props?.bias_pull_down || false,
      drive_open_drain:state.props?.drive_open_drain || false,
      input_enable:    state.props?.input_enable || false,
    });
  }

  const periphs = boardData.peripherals.map(p => ({
    name:       p.name,
    dts_node:   p.dts_node,
    compatible: p.compatible,
    enabled:    periphStates[p.name] || false,
    core_id:    periphCoreStates[p.name] || p.core_id || "",
  }));

  const res = await fetch("/api/generate", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      board_id: boardSelect.value,
      board: boardData.board,
      assignments: assignments,
      peripherals: periphs,
      external_devices: selectedExternalDevices(),
    }),
  });

  const result = await res.json();
  generatedOverlay = result.overlay;
  generatedConf    = result.prj_conf;
  generatedTargets = result.targets || {};

  renderOutputTabs();
  showOutput(activeTab);
  outputBar.classList.remove("collapsed");
  toast("Generated Zephyr, Arduino, and bare-metal outputs");
}

// ── Output bar ───────────────────────────────────────────────────────

function showOutput(tab) {
  const views = collectOutputViews();
  const current = views.find(view => view.id === tab) || views[0] || { id: "overlay", content: generatedOverlay };
  activeTab = tab;
  outputPre.textContent = current.content || "";
  $$(".output-tab").forEach(t => t.classList.toggle("active", t.dataset.tab === tab));
}

// ── Save to project ──────────────────────────────────────────────────

async function saveToProject(projectPath) {
  if (!generatedOverlay) {
    await generateOutput();
  }
  const res = await fetch("/api/save-project", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      project_path: projectPath,
      overlay: generatedOverlay,
      prj_conf: generatedConf,
      board: boardData?.board || "custom_board",
    }),
  });
  const result = await res.json();
  if (result.saved) {
    toast(`Saved to ${projectPath}`);
  } else {
    toast(`Error: ${result.error}`);
  }
}

// ── Zoom controls ────────────────────────────────────────────────────

function applyZoom() {
  chipContainer.style.transform = `scale(${chipZoom})`;
  const label = $("#zoomLevel");
  if (label) label.textContent = `${Math.round(chipZoom * 100)}%`;
}

function zoomIn() {
  chipZoom = Math.min(ZOOM_MAX, chipZoom + ZOOM_STEP);
  applyZoom();
}

function zoomOut() {
  chipZoom = Math.max(ZOOM_MIN, chipZoom - ZOOM_STEP);
  applyZoom();
}

function zoomReset() {
  chipZoom = 1.0;
  applyZoom();
}

function zoomFit() {
  const svg = chipContainer.querySelector("svg.chip-svg");
  if (!svg || !chipArea) return;
  const areaW = chipArea.clientWidth - 40;
  const areaH = chipArea.clientHeight - 40;
  const svgW = svg.getAttribute("width");
  const svgH = svg.getAttribute("height");
  if (!svgW || !svgH) return;
  chipZoom = Math.min(areaW / parseFloat(svgW), areaH / parseFloat(svgH));
  chipZoom = Math.max(ZOOM_MIN, Math.min(ZOOM_MAX, chipZoom));
  applyZoom();
}

// ── Project file save/load ───────────────────────────────────────────

function serializePinStates() {
  // Convert pinStates into a clean serializable form
  const out = {};
  for (const [pinNum, state] of Object.entries(pinStates)) {
    const entry = {};
    if (state.af) {
      entry.af = {
        function_id: state.af.function_id,
        name: state.af.name,
        pincm: state.af.pincm,
        peripheral: state.af.peripheral,
        signal: state.af.signal,
        direction: state.af.direction || "io",
      };
    }
    if (state.props) {
      entry.props = { ...state.props };
    }
    out[pinNum] = entry;
  }
  return out;
}

async function saveProjectFile(filePath) {
  if (!boardData) {
    toast("No board loaded");
    return;
  }

  // Serialize sensor & MCU job histories for project save
  const snsJobsData = snsJobs.map(j => ({
    job_id: j.job_id,
    filename: j.filename,
    result: j.result,
    summary: j.summary || null,
  }));
  const pkgJobsData = pkgJobs.map(j => ({
    job_id: j.job_id,
    filename: j.filename,
    result: j.result,
  }));

  const res = await fetch("/api/project-file/save", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      file_path: filePath,
      board_id: boardData.board || boardSelect.value,
      pin_states: serializePinStates(),
      periph_states: { ...periphStates },
      periph_core_states: { ...periphCoreStates },
      external_device_states: { ...externalDeviceStates },
      generated_overlay: generatedOverlay,
      generated_conf: generatedConf,
      sensor_jobs: snsJobsData,
      sensor_selected: snsSelectedJob || "",
      mcu_jobs: pkgJobsData,
      mcu_selected: pkgSelectedJob || "",
    }),
  });
  const result = await res.json();
  if (result.saved) {
    toast(`Project saved to ${result.file_path}`);
  } else {
    toast(`Error: ${result.error}`);
  }
}

async function loadProjectFile(filePath) {
  const res = await fetch("/api/project-file/load", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ file_path: filePath }),
  });
  const project = await res.json();
  if (project.error) {
    toast(`Error: ${project.error}`);
    return;
  }

  // Load the board first if different from current
  const boardId = project.board_id;
  if (!boardData || boardData.board !== boardId) {
    // Find it in the select dropdown
    const opts = [...boardSelect.options];
    const match = opts.find(o => o.value === boardId);
    if (match) {
      boardSelect.value = boardId;
      await loadBoard(boardId);
    } else {
      toast(`Board "${boardId}" not found in board list`);
      return;
    }
  }

  // Restore pin states by re-matching alt functions from boardData
  pinStates = {};
  for (const [pinNum, state] of Object.entries(project.pin_states || {})) {
    const boardPin = boardData.pins.find(p => p.number === parseInt(pinNum));
    if (!boardPin) continue;

    const entry = {};
    if (state.af) {
      // Match the AF back to the actual board data object
      const af = boardPin.alt_functions.find(a =>
        a.pincm === state.af.pincm && a.function_id === state.af.function_id
      ) || boardPin.alt_functions.find(a =>
        a.peripheral === state.af.peripheral && a.signal === state.af.signal
      );
      if (af) entry.af = af;
    }
    if (state.props) {
      entry.props = { ...state.props };
    }
    if (entry.af || entry.props) {
      pinStates[pinNum] = entry;
    }
  }

  // Restore peripheral states
  for (const [name, enabled] of Object.entries(project.periph_states || {})) {
    if (name in periphStates) {
      periphStates[name] = enabled;
    }
  }

  for (const [name, coreId] of Object.entries(project.periph_core_states || {})) {
    if (name in periphCoreStates) {
      periphCoreStates[name] = coreId;
    }
  }

  const projectDeviceStates = project.external_device_states || {};
  for (const [deviceId, state] of Object.entries(projectDeviceStates)) {
    if (!(deviceId in externalDeviceStates) || !state || typeof state !== "object") continue;
    externalDeviceStates[deviceId] = {
      selected: !!state.selected,
      bus: String(state.bus || externalDeviceStates[deviceId].bus || ""),
    };
  }

  // Restore generated output
  generatedOverlay = project.generated_overlay || "";
  generatedConf = project.generated_conf || "";
  generatedTargets = {};
  renderOutputTabs();
  if (generatedOverlay || generatedConf) {
    showOutput(activeTab);
    outputBar.classList.remove("collapsed");
  }

  // Re-render everything
  renderPeripherals();
  renderChip();
  renderConfigPanel();

  // Restore sensor job history from project file
  if (project.sensor_jobs && Array.isArray(project.sensor_jobs) && project.sensor_jobs.length) {
    snsJobs = project.sensor_jobs;
    snsSelectedJob = project.sensor_selected || null;
    snsSaveToStorage();
    snsRenderJobList();
    if (snsSelectedJob) snsSelectJob(snsSelectedJob);
  }

  // Restore MCU/package job history from project file
  if (project.mcu_jobs && Array.isArray(project.mcu_jobs) && project.mcu_jobs.length) {
    pkgJobs = project.mcu_jobs;
    pkgSelectedJob = project.mcu_selected || null;
    pkgSaveToStorage();
    pkgRenderJobList();
    if (pkgSelectedJob) pkgSelectJob(pkgSelectedJob);
  }

  toast(`Project loaded (${Object.keys(pinStates).length} pin(s))`);
}

// ── Event wiring ─────────────────────────────────────────────────────

document.addEventListener("DOMContentLoaded", () => {
  loadBoardList();
  initBoardEditor();

  boardSelect.addEventListener("change", () => loadBoard(boardSelect.value));

  $("#btnGenerate").addEventListener("click", generateOutput);

  renderOutputTabs();

  // Save modal
  $("#btnSave").addEventListener("click", () => {
    $("#saveModal").classList.add("show");
  });
  $("#btnCancelSave").addEventListener("click", () => {
    $("#saveModal").classList.remove("show");
  });
  $("#btnConfirmSave").addEventListener("click", () => {
    const path = $("#projectPath").value.trim();
    if (path) {
      saveToProject(path);
      $("#saveModal").classList.remove("show");
    }
  });

  // Close modal on backdrop click
  $("#saveModal").addEventListener("click", (e) => {
    if (e.target === e.currentTarget) {
      $("#saveModal").classList.remove("show");
    }
  });

  // ── Save project file modal ──────────────────────────────────────
  $("#btnSaveProject").addEventListener("click", () => {
    $("#saveProjectModal").classList.add("show");
  });
  $("#btnCancelSaveProject").addEventListener("click", () => {
    $("#saveProjectModal").classList.remove("show");
  });
  $("#btnConfirmSaveProject").addEventListener("click", () => {
    const path = $("#projectFilePath").value.trim();
    if (path) {
      saveProjectFile(path);
      $("#saveProjectModal").classList.remove("show");
    }
  });
  $("#saveProjectModal").addEventListener("click", (e) => {
    if (e.target === e.currentTarget) {
      $("#saveProjectModal").classList.remove("show");
    }
  });

  // ── Load project file modal ──────────────────────────────────────
  $("#btnLoadProject").addEventListener("click", () => {
    $("#loadProjectModal").classList.add("show");
  });
  $("#btnCancelLoadProject").addEventListener("click", () => {
    $("#loadProjectModal").classList.remove("show");
  });
  $("#btnConfirmLoadProject").addEventListener("click", () => {
    const path = $("#loadProjectFilePath").value.trim();
    if (path) {
      loadProjectFile(path);
      $("#loadProjectModal").classList.remove("show");
    }
  });
  $("#loadProjectModal").addEventListener("click", (e) => {
    if (e.target === e.currentTarget) {
      $("#loadProjectModal").classList.remove("show");
    }
  });

  // ── Zoom controls ─────────────────────────────────────────────────
  $("#zoomIn").addEventListener("click", zoomIn);
  $("#zoomOut").addEventListener("click", zoomOut);
  $("#zoomReset").addEventListener("click", zoomReset);
  $("#zoomFit").addEventListener("click", zoomFit);

  // Mouse wheel zoom on chip area
  chipArea.addEventListener("wheel", (e) => {
    // Only zoom when hovering over chip area
    e.preventDefault();
    if (e.deltaY < 0) zoomIn();
    else zoomOut();
  }, { passive: false });

  // Keyboard shortcuts
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") {
      selectedPin = null;
      renderChip();
      renderConfigPanel();
      $("#saveModal").classList.remove("show");
      $("#importModal").classList.remove("show");
      $("#saveProjectModal").classList.remove("show");
      $("#loadProjectModal").classList.remove("show");
    }
    if ((e.ctrlKey || e.metaKey) && e.key === "g") {
      e.preventDefault();
      generateOutput();
    }
    // Ctrl+S = save project file
    if ((e.ctrlKey || e.metaKey) && e.key === "s") {
      // Only intercept if configurator tab is active
      const confTab = document.querySelector('.tab-content[data-app-content="configurator"]');
      if (confTab && confTab.classList.contains("active")) {
        e.preventDefault();
        $("#saveProjectModal").classList.add("show");
      }
    }
  });

  // ── App-level tab switching ────────────────────────────────────────
  $$(".app-tab").forEach(tab => {
    tab.addEventListener("click", () => {
      const target = tab.dataset.appTab;
      $$(".app-tab").forEach(t => t.classList.toggle("active", t.dataset.appTab === target));
      $$(".tab-content").forEach(c => c.classList.toggle("active", c.dataset.appContent === target));

      // Load existing packages when switching to the tab
      if (target === "packages") {
        pkgLoadExisting();
      }
      if (target === "board-editor") {
        updateBoardEditorMeta();
        loadBoardEditorDrafts();
        loadBoardEditorDeviceLibrary();
      }
      if (target === "peripherals") {
        pcfgLoadBoards();
      }
      if (target === "clock") {
        clkLoadTrees();
      }
      if (target === "sensors") {
        snsLoadJobs();
      }
    });
  });

  // ── Module Configurator init ───────────────────────────────────────
  modInit();

  // ── Package Manager init ───────────────────────────────────────────
  pkgInit();

  // ── Peripheral Configurator init ───────────────────────────────────
  pcfgInit();

  // ── Clock System Configurator init ─────────────────────────────────
  clkInit();

  // ── Import Configurator init ───────────────────────────────────────
  impInit();

  // ── MCU Lookup init ────────────────────────────────────────────────
  mcuInit();

  // ── Sensor Parser init ─────────────────────────────────────────────
  snsInit();
});


// ══════════════════════════════════════════════════════════════════════
// Package Manager module
// ══════════════════════════════════════════════════════════════════════

let pkgJobs = [];           // Parsed PDF jobs
let pkgSelectedJob = null;  // Currently selected job_id
let pkgSelectedPkgs = new Set(); // Selected package names for generation

// ── LocalStorage persistence helpers ─────────────────────────────────

function pkgSaveToStorage() {
  try {
    const data = pkgJobs.map(j => ({
      job_id: j.job_id,
      filename: j.filename,
      result: j.result,
    }));
    localStorage.setItem("zpincfg_pkg_jobs", JSON.stringify(data));
    localStorage.setItem("zpincfg_pkg_selected", pkgSelectedJob || "");
  } catch (e) { console.warn("pkgSaveToStorage:", e); }
}

function pkgLoadFromStorage() {
  try {
    const raw = localStorage.getItem("zpincfg_pkg_jobs");
    if (raw) {
      const data = JSON.parse(raw);
      if (Array.isArray(data) && data.length) {
        pkgJobs = data;
        pkgSelectedJob = localStorage.getItem("zpincfg_pkg_selected") || null;
        return true;
      }
    }
  } catch (e) { console.warn("pkgLoadFromStorage:", e); }
  return false;
}

function pkgRemoveJob(jobId) {
  pkgJobs = pkgJobs.filter(j => j.job_id !== jobId);
  if (pkgSelectedJob === jobId) {
    pkgSelectedJob = pkgJobs.length ? pkgJobs[0].job_id : null;
  }
  pkgSaveToStorage();
  pkgRenderJobList();
  if (pkgSelectedJob) pkgSelectJob(pkgSelectedJob);
  else {
    $("#pkgMain").innerHTML = `<div class="pkg-empty">
      <div class="icon">&#128230;</div>
      <div>MCU Package Generator</div>
      <div class="hint">Upload an MCU datasheet PDF to extract pin-mux data<br>
        and generate board definition files.</div>
    </div>`;
  }
}

function pkgInit() {
  const uploadArea = $("#pdfUploadArea");
  const fileInput  = $("#pdfFileInput");

  // Click to browse
  uploadArea.addEventListener("click", () => fileInput.click());

  // File selected via browse dialog
  fileInput.addEventListener("change", () => {
    if (fileInput.files.length) {
      pkgUploadPdf(fileInput.files[0]);
      fileInput.value = "";
    }
  });

  // Drag & drop
  uploadArea.addEventListener("dragover", (e) => {
    e.preventDefault();
    uploadArea.classList.add("dragover");
  });
  uploadArea.addEventListener("dragleave", () => {
    uploadArea.classList.remove("dragover");
  });
  uploadArea.addEventListener("drop", (e) => {
    e.preventDefault();
    uploadArea.classList.remove("dragover");
    if (e.dataTransfer.files.length) {
      const file = e.dataTransfer.files[0];
      if (file.name.toLowerCase().endsWith(".pdf")) {
        pkgUploadPdf(file);
      } else {
        toast("Please drop a .pdf file");
      }
    }
  });

  // Load existing packages on init
  pkgLoadExisting();

  // Restore from localStorage
  if (pkgLoadFromStorage()) {
    pkgRenderJobList();
    if (pkgSelectedJob) {
      pkgSelectJob(pkgSelectedJob);
    }
  }
}


async function pkgUploadPdf(file) {
  const uploadArea = $("#pdfUploadArea");
  const origHTML = uploadArea.innerHTML;

  // Show spinner
  uploadArea.innerHTML = `
    <div class="spinner"></div>
    <div style="margin-top:8px;">Parsing ${file.name}...</div>
    <div class="upload-hint">This may take a moment for large PDFs</div>
  `;

  const formData = new FormData();
  formData.append("pdf", file);

  try {
    const res = await fetch("/api/parse-pdf", {
      method: "POST",
      body: formData,
    });

    const data = await res.json();

    if (!res.ok) {
      toast(`Error: ${data.error}`);
      uploadArea.innerHTML = origHTML;
      return;
    }

    // Add to job list
    pkgJobs.push({
      job_id: data.job_id,
      filename: data.filename,
      result: data.result,
    });

    pkgSaveToStorage();
    pkgRenderJobList();
    pkgSelectJob(data.job_id);
    toast(`Parsed ${data.filename}: ${data.result.packages.length} package(s) found`);

  } catch (err) {
    toast(`Upload failed: ${err.message}`);
  }

  uploadArea.innerHTML = origHTML;
}


function pkgRenderJobList() {
  const list = $("#pkgJobList");

  if (pkgJobs.length === 0) {
    list.innerHTML = `<div class="empty-state" style="padding:20px;">
      <div>No datasheets parsed yet</div>
      <div class="hint">Upload a PDF above</div>
    </div>`;
    return;
  }

  list.innerHTML = pkgJobs.map(job => {
    const r = job.result;
    const isSelected = pkgSelectedJob === job.job_id;
    const pkgNames = r.packages.map(p => p.name).join(", ") || "No packages";
    return `
      <div class="pkg-job-item ${isSelected ? 'selected' : ''}"
           data-job-id="${job.job_id}">
        <button class="job-remove-btn" data-remove-id="${job.job_id}" title="Remove">&times;</button>
        <div class="job-filename">
          ${job.filename}
          ${r.device.soc ? `<span class="soc-badge">${r.device.soc}</span>` : ''}
        </div>
        <div class="job-meta">
          ${r.packages.length} package(s): ${pkgNames}
          &middot; ${r.pin_mux_count} pins, ${r.pin_mux_total_funcs} alt-funcs
        </div>
      </div>
    `;
  }).join("");

  // Attach click handlers
  list.querySelectorAll(".pkg-job-item").forEach(el => {
    el.addEventListener("click", (e) => {
      if (e.target.closest(".job-remove-btn")) return;
      pkgSelectJob(el.dataset.jobId);
    });
  });

  // Attach remove handlers
  list.querySelectorAll(".job-remove-btn").forEach(btn => {
    btn.addEventListener("click", (e) => {
      e.stopPropagation();
      pkgRemoveJob(btn.dataset.removeId);
    });
  });
}


function pkgSelectJob(jobId) {
  pkgSelectedJob = jobId;
  pkgSelectedPkgs = new Set();
  pkgSaveToStorage();
  pkgRenderJobList();
  pkgRenderDetail();
}


function pkgRenderDetail() {
  const main = $("#pkgMain");
  const job = pkgJobs.find(j => j.job_id === pkgSelectedJob);

  if (!job) {
    main.innerHTML = `<div class="pkg-empty">
      <div class="icon">&#128230;</div>
      <div>MCU Package Generator</div>
      <div class="hint">Upload an MCU datasheet PDF to extract pin-mux data<br>
        and generate board definition files.</div>
    </div>`;
    return;
  }

  const r = job.result;
  const dev = r.device;

  // Select all packages by default
  if (pkgSelectedPkgs.size === 0) {
    r.packages.forEach(p => pkgSelectedPkgs.add(p.name));
  }

  let html = `
    <div class="pkg-detail-header">
      <h2>${dev.soc || job.filename}</h2>
      <div class="device-specs">
        <span>&#128190; Flash: ${dev.flash_size_kb ? dev.flash_size_kb + ' KB' : '?'}</span>
        <span>&#128200; SRAM: ${dev.sram_size_kb ? dev.sram_size_kb + ' KB' : '?'}</span>
        <span>&#9201; Clock: ${dev.clock_hz ? (dev.clock_hz / 1e6).toFixed(0) + ' MHz' : '?'}</span>
        <span>&#128204; Vendor: ${dev.vendor}</span>
      </div>
    </div>

    <div class="pkg-detail-body">

      <!-- Packages -->
      <div class="pkg-section">
        <h3>Packages Found (${r.packages.length})</h3>
        <div class="pkg-card-grid">
          ${r.packages.map(pkg => {
            const sel = pkgSelectedPkgs.has(pkg.name);
            const ioPins = pkg.pins.filter(p => p.kind === 'io').length;
            const pwrPins = pkg.pins.filter(p => p.kind === 'power' || p.kind === 'ground').length;
            const specPins = pkg.pins.filter(p => p.kind === 'special').length;
            return `
              <div class="pkg-card ${sel ? 'selected' : ''}" data-pkg="${pkg.name}">
                <div class="pkg-card-check">${sel ? '&#10003;' : ''}</div>
                <div class="pkg-card-name">${pkg.name}</div>
                <div class="pkg-card-meta">
                  ${pkg.pin_count} pins &middot;
                  ${ioPins} I/O, ${pwrPins} pwr/gnd, ${specPins} special
                </div>
              </div>`;
          }).join("")}
        </div>
      </div>

      <!-- Pin-mux sample -->
      <div class="pkg-section">
        <h3>Pin-Mux Preview (${r.pin_mux_count} pins, ${r.pin_mux_total_funcs} functions)</h3>
        ${Object.keys(r.pin_mux_sample).length > 0 ? `
          <table class="mux-table">
            <thead>
              <tr>
                <th>Pin</th>
                <th>Function</th>
                <th>Peripheral</th>
                <th>Signal</th>
                <th>Dir</th>
              </tr>
            </thead>
            <tbody>
              ${Object.entries(r.pin_mux_sample).flatMap(([pin, funcs]) =>
                funcs.map((f, i) => `
                  <tr>
                    ${i === 0 ? `<td rowspan="${funcs.length}" style="font-weight:600;">${pin}</td>` : ''}
                    <td><span class="af-id" style="display:inline-block;margin-right:4px;">F${f.function_id}</span>${f.function_name}</td>
                    <td>${f.peripheral}</td>
                    <td>${f.signal}</td>
                    <td style="color:var(--fg-dim);">${f.direction}</td>
                  </tr>`)
              ).join("")}
            </tbody>
          </table>
          ${r.pin_mux_count > 5 ? `<div style="font-size:11px;color:var(--fg-dim);margin-top:6px;">Showing first 5 pins of ${r.pin_mux_count}</div>` : ''}
        ` : '<div class="empty-state">No pin-mux data extracted</div>'}
      </div>

      <!-- Generation overrides -->
      <div class="pkg-section">
        <h3>Generation Options</h3>
        <div class="pkg-overrides">
          <label>Board Name</label>
          <input id="pkgBoardName" placeholder="lp_${(dev.soc || 'custom').toLowerCase()}" value="">
          <label>DTS SOC Include</label>
          <input id="pkgDtsSoc" placeholder="auto-detect" value="">
          <label>DTS Pinctrl Include</label>
          <input id="pkgDtsPinctrl" placeholder="auto-detect" value="">
          <label>Pinctrl Header</label>
          <input id="pkgPinctrlHeader" placeholder="mspm0-pinctrl.h" value="">
          <label>External Devices</label>
          <textarea id="pkgExternalDevices" placeholder='[\n  {\n    "id": "bme280_i2c",\n    "display": "BME280 Sensor",\n    "category": "sensor",\n    "bus": "i2c0",\n    "compatible": "bosch,bme280",\n    "address": "0x76",\n    "required_signals": ["scl", "sda"],\n    "frameworks": ["zephyr", "arduino"]\n  }\n]'></textarea>
        </div>
      </div>
    </div>

    <!-- Action bar -->
    <div class="pkg-actions">
      <span class="pkg-status" id="pkgStatus">${pkgSelectedPkgs.size} of ${r.packages.length} package(s) selected</span>
      <span class="spacer"></span>
      <button class="btn" id="pkgBtnSelectAll">Select All</button>
      <button class="btn btn-accent" id="pkgBtnGenerate" ${pkgSelectedPkgs.size === 0 ? 'disabled' : ''}>
        Generate ${pkgSelectedPkgs.size} Board File(s)
      </button>
    </div>
  `;

  main.innerHTML = html;

  // Wire up package card toggles
  main.querySelectorAll(".pkg-card").forEach(card => {
    card.addEventListener("click", () => {
      const name = card.dataset.pkg;
      if (pkgSelectedPkgs.has(name)) {
        pkgSelectedPkgs.delete(name);
      } else {
        pkgSelectedPkgs.add(name);
      }
      pkgRenderDetail();
    });
  });

  // Select All button
  const btnAll = main.querySelector("#pkgBtnSelectAll");
  if (btnAll) {
    btnAll.addEventListener("click", () => {
      r.packages.forEach(p => pkgSelectedPkgs.add(p.name));
      pkgRenderDetail();
    });
  }

  // Generate button
  const btnGen = main.querySelector("#pkgBtnGenerate");
  if (btnGen) {
    btnGen.addEventListener("click", () => pkgGenerate());
  }
}


async function pkgGenerate() {
  const job = pkgJobs.find(j => j.job_id === pkgSelectedJob);
  if (!job) return;

  const statusEl = $("#pkgStatus");
  const btnGen = $("#pkgBtnGenerate");

  if (btnGen) {
    btnGen.disabled = true;
    btnGen.innerHTML = '<span class="spinner" style="width:12px;height:12px;border-width:1.5px;"></span> Generating...';
  }
  if (statusEl) statusEl.textContent = "Generating board files...";

  let externalDevices;
  const externalDevicesRaw = $("#pkgExternalDevices")?.value.trim() || "";
  if (externalDevicesRaw) {
    try {
      externalDevices = JSON.parse(externalDevicesRaw);
      if (!Array.isArray(externalDevices)) {
        throw new Error("External devices must be a JSON array");
      }
    } catch (err) {
      toast(`Invalid external devices JSON: ${err.message}`);
      if (statusEl) statusEl.textContent = `Invalid external devices JSON: ${err.message}`;
      if (btnGen) {
        btnGen.disabled = false;
        btnGen.innerHTML = `Generate ${pkgSelectedPkgs.size} Board File(s)`;
      }
      return;
    }
  }

  const body = {
    job_id: job.job_id,
    packages: [...pkgSelectedPkgs],
    board_name: $("#pkgBoardName")?.value.trim() || undefined,
    dts_soc_include: $("#pkgDtsSoc")?.value.trim() || undefined,
    dts_pinctrl_include: $("#pkgDtsPinctrl")?.value.trim() || undefined,
    pinctrl_header: $("#pkgPinctrlHeader")?.value.trim() || undefined,
    external_devices: externalDevices,
    register: true,
  };

  // Remove undefined keys
  Object.keys(body).forEach(k => body[k] === undefined && delete body[k]);

  try {
    const res = await fetch("/api/generate-package", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });

    const data = await res.json();

    if (!res.ok) {
      toast(`Error: ${data.error}`);
      if (statusEl) statusEl.textContent = `Error: ${data.error}`;
    } else {
      const names = data.files.map(f => f.filename).join(", ");
      toast(`Generated: ${names}`);
      if (statusEl) statusEl.textContent = `✓ Generated: ${names}`;

      // Reload existing packages list
      pkgLoadExisting();

      // Reload board list in the Pin Configurator tab
      loadBoardList();
    }
  } catch (err) {
    toast(`Failed: ${err.message}`);
    if (statusEl) statusEl.textContent = `Failed: ${err.message}`;
  }

  if (btnGen) {
    btnGen.disabled = false;
    btnGen.innerHTML = `Generate ${pkgSelectedPkgs.size} Board File(s)`;
  }
}


async function pkgLoadExisting() {
  try {
    const res = await fetch("/api/generated-packages");
    const files = await res.json();
    const list = $("#existingPkgList");

    if (files.length === 0) {
      list.innerHTML = '<li style="color:var(--fg-dim);font-size:12px;padding:8px 10px;">No board files yet</li>';
      return;
    }

    list.innerHTML = files.map(f => {
      // Derive a display name from the module: e.g. "stm32l476_lqfp64" → "STM32L476 – LQFP64"
      const parts = f.module.split("_");
      let soc = "", pkg = "";
      // Find where package part starts (common suffixes: qfp, lqfp, ufbga, wlcsp, bga, qfn, etc.)
      const pkgRe = /^(lqfp|qfp|ufbga|wlcsp|bga|qfn|csp|lga|ssop|tssop|soic)\d*$/i;
      for (let i = parts.length - 1; i >= 0; i--) {
        if (pkgRe.test(parts[i])) {
          pkg = parts.slice(i).join("_").toUpperCase();
          soc = parts.slice(0, i).join("_").toUpperCase();
          break;
        }
      }
      if (!soc) { soc = f.module.toUpperCase(); }
      const label = pkg ? `${soc} – ${pkg}` : soc;

      return `
      <li class="pkg-board-link" data-module="${f.module}" title="Click to open in Pin Configurator">
        <span class="file-icon">&#128196;</span>
        <span>${label}</span>
        <span class="file-size">${(f.size / 1024).toFixed(1)} KB</span>
      </li>`;
    }).join("");

    // Make entries clickable → switch to Pin Configurator with that board
    list.querySelectorAll(".pkg-board-link").forEach(li => {
      li.style.cursor = "pointer";
      li.addEventListener("click", () => {
        const mod = li.dataset.module;
        // Find matching board in select
        const opts = [...boardSelect.options];
        const match = opts.find(o => o.value === mod || o.value.includes(mod));
        if (match) {
          boardSelect.value = match.value;
          loadBoard(match.value);
          // Switch to Pin Configurator tab
          $$(".app-tab").forEach(t => t.classList.toggle("active", t.dataset.appTab === "configurator"));
          $$(".tab-content").forEach(c => c.classList.toggle("active", c.dataset.appContent === "configurator"));
          toast(`Loaded ${mod} in Pin Configurator`);
        } else {
          toast(`Board "${mod}" not found in selector`);
        }
      });
    });

  } catch (err) {
    console.warn("Failed to load existing packages", err);
  }
}


// ══════════════════════════════════════════════════════════════════════
// Module Configurator  (dynamic – all Zephyr modules)
// ══════════════════════════════════════════════════════════════════════

let modModules = [];            // All module definitions from API
let modActiveId = null;         // Currently selected module in sidebar
let modEnabled = {};            // { moduleId: bool } — which modules are "enabled"
let modValuesMap = {};          // { moduleId: { CONFIG_KEY: value } }
let modDefaultsMap = {};        // { moduleId: { CONFIG_KEY: default } }

// Convenience accessors for current module
function _modValues()   { return modValuesMap[modActiveId]   || {}; }
function _modDefaults() { return modDefaultsMap[modActiveId] || {}; }

async function modInit() {
  try {
    const res = await fetch("/api/modules");
    modModules = await res.json();

    // Initialise per-module state
    for (const m of modModules) {
      modEnabled[m.id] = false;
      modValuesMap[m.id] = {};
      modDefaultsMap[m.id] = {};
      for (const cat of m.categories) {
        for (const opt of cat.options) {
          modDefaultsMap[m.id][opt.key] = opt.default;
          modValuesMap[m.id][opt.key] = opt.default;
        }
      }
    }

    modRenderSidebar();

    // Search filter
    const search = document.getElementById("modSearch");
    if (search) {
      search.addEventListener("input", () => modRenderSidebar(search.value.trim().toLowerCase()));
    }
  } catch (err) {
    console.error("Failed to load modules", err);
  }
}

function modRenderSidebar(filter = "") {
  const list = document.getElementById("modModuleList");
  if (!list) return;

  const filtered = modModules.filter(m =>
    !filter || m.name.toLowerCase().includes(filter) || m.id.toLowerCase().includes(filter)
  );

  list.innerHTML = filtered.map(m => {
    const optCount = m.categories.reduce((n, c) => n + c.options.length, 0);
    const enabled = modEnabled[m.id];
    const changed = modCountChanged(m.id);
    return `
      <div class="modcfg-module-item ${m.id === modActiveId ? 'active' : ''} ${enabled ? 'enabled' : ''}"
           data-mod-id="${m.id}">
        <div class="mod-icon">${m.icon || '📦'}</div>
        <div class="mod-label">
          ${m.name}
          ${changed > 0 ? `<span class="mod-changed-dot" title="${changed} changed">●</span>` : ''}
        </div>
        <div class="mod-badge">${optCount}</div>
        <input type="checkbox" class="mod-enable-cb" data-mod-enable="${m.id}"
               ${enabled ? 'checked' : ''} title="Enable ${m.name} in output">
      </div>`;
  }).join("");

  // Click on item → select
  list.querySelectorAll(".modcfg-module-item").forEach(el => {
    el.addEventListener("click", (e) => {
      // Don't select when clicking the checkbox itself
      if (e.target.classList.contains("mod-enable-cb")) return;
      const id = el.dataset.modId;
      modActiveId = id;
      modSelectModule(id);
      list.querySelectorAll(".modcfg-module-item").forEach(e2 =>
        e2.classList.toggle("active", e2.dataset.modId === id));
    });
  });

  // Enable checkbox
  list.querySelectorAll(".mod-enable-cb").forEach(cb => {
    cb.addEventListener("change", (e) => {
      e.stopPropagation();
      modEnabled[cb.dataset.modEnable] = cb.checked;
      cb.closest(".modcfg-module-item").classList.toggle("enabled", cb.checked);
      modUpdateGenerateAllBtn();
    });
  });
}

function modCountChanged(moduleId) {
  const vals = modValuesMap[moduleId] || {};
  const defs = modDefaultsMap[moduleId] || {};
  let n = 0;
  for (const k in defs) {
    if (vals[k] !== undefined && vals[k] !== defs[k]) n++;
  }
  return n;
}

function modUpdateGenerateAllBtn() {
  const btn = document.getElementById("modGenerateAllBtn");
  if (!btn) return;
  const count = Object.values(modEnabled).filter(Boolean).length;
  btn.textContent = `⚡ Generate All (${count} module${count !== 1 ? 's' : ''})`;
  btn.disabled = count === 0;
}

function modSelectModule(id) {
  const mod = modModules.find(m => m.id === id);
  if (!mod) return;

  const main = document.getElementById("modMain");
  main.innerHTML = `
    <div class="modcfg-header">
      <h2>${mod.icon || ''} ${mod.name}
        <span class="version-badge">v${mod.version || '?'}</span>
      </h2>
      <div class="mod-desc">${mod.desc || ''}</div>
    </div>
    <div class="modcfg-body" id="modBody"></div>
    <div class="modcfg-actions">
      <button class="btn" id="modResetBtn">⟲ Reset Module</button>
      <button class="btn" id="modEnableBtn">${modEnabled[id] ? '✓ Enabled' : '○ Enable'}</button>
      <span class="spacer"></span>
      <label style="font-size:12px;display:flex;align-items:center;gap:6px;">
        <input type="checkbox" id="modFullOverlay"> Full overlay
      </label>
      <button class="btn btn-primary" id="modGenerateAllBtn">⚡ Generate All (0)</button>
      <button class="btn" id="modCopyBtn" style="display:none">📋 Copy</button>
    </div>
    <div class="modcfg-output" id="modOutput" style="display:none">
      <pre id="modOutputPre"></pre>
    </div>
  `;

  modRenderBody(mod);
  modUpdateGenerateAllBtn();

  // Reset this module
  document.getElementById("modResetBtn").addEventListener("click", () => {
    modValuesMap[id] = { ...modDefaultsMap[id] };
    modRenderBody(mod);
    modRenderSidebar(document.getElementById("modSearch")?.value?.trim().toLowerCase() || "");
    const outEl = document.getElementById("modOutput");
    if (outEl) outEl.style.display = "none";
    const cpBtn = document.getElementById("modCopyBtn");
    if (cpBtn) cpBtn.style.display = "none";
  });

  // Enable toggle in main area
  const enableBtn = document.getElementById("modEnableBtn");
  enableBtn.addEventListener("click", () => {
    modEnabled[id] = !modEnabled[id];
    enableBtn.textContent = modEnabled[id] ? "✓ Enabled" : "○ Enable";
    modUpdateGenerateAllBtn();
    modRenderSidebar(document.getElementById("modSearch")?.value?.trim().toLowerCase() || "");
    // Re-highlight the active item
    document.querySelectorAll(".modcfg-module-item").forEach(e =>
      e.classList.toggle("active", e.dataset.modId === id));
  });

  document.getElementById("modGenerateAllBtn").addEventListener("click", () => modGenerateAll());

  document.getElementById("modCopyBtn").addEventListener("click", () => {
    const text = document.getElementById("modOutputPre").textContent;
    navigator.clipboard.writeText(text).then(() => {
      const btn = document.getElementById("modCopyBtn");
      btn.textContent = "✓ Copied!";
      setTimeout(() => btn.textContent = "📋 Copy", 1500);
    });
  });
}

function modRenderBody(mod) {
  const body = document.getElementById("modBody");
  if (!body) return;
  const vals = modValuesMap[mod.id] || {};
  const defs = modDefaultsMap[mod.id] || {};

  body.innerHTML = mod.categories.map(cat => {
    const rows = cat.options.map(opt => modRenderOption(opt, vals, defs)).join("");
    return `
      <div class="cfg-group" data-cat="${cat.id}">
        <div class="cfg-group-header">
          <span class="chevron">▼</span>
          ${cat.title}
          <span class="group-count">${cat.options.length} options</span>
        </div>
        <div class="cfg-group-body">${rows}</div>
      </div>`;
  }).join("");

  // Collapsible groups
  body.querySelectorAll(".cfg-group-header").forEach(hdr => {
    hdr.addEventListener("click", () => {
      hdr.parentElement.classList.toggle("collapsed");
    });
  });

  // Wire up value changes
  body.querySelectorAll("[data-cfg-key]").forEach(el => {
    el.addEventListener("change", () => {
      const key = el.dataset.cfgKey;
      const opt = modFindOption(mod, key);
      if (!opt) return;

      if (opt.type === "bool") {
        vals[key] = el.checked;
      } else if (opt.type === "int") {
        vals[key] = parseInt(el.value, 10) || 0;
      } else {
        vals[key] = el.value;
      }

      // Highlight changed rows
      const row = el.closest(".cfg-row");
      if (row) {
        row.classList.toggle("changed", vals[key] !== defs[key]);
      }

      // Update sidebar changed dot
      modRenderSidebar(document.getElementById("modSearch")?.value?.trim().toLowerCase() || "");
      // Re-highlight active
      document.querySelectorAll(".modcfg-module-item").forEach(e =>
        e.classList.toggle("active", e.dataset.modId === modActiveId));
    });
  });
}

function modRenderOption(opt, vals, defs) {
  const val = vals[opt.key] ?? opt.default;
  const changed = val !== defs[opt.key];
  let inputHtml = "";

  if (opt.type === "bool") {
    inputHtml = `<input type="checkbox" data-cfg-key="${opt.key}" ${val ? "checked" : ""}>`;
  } else if (opt.type === "int") {
    inputHtml = `<input type="number" data-cfg-key="${opt.key}" value="${val}">`;
  } else if (opt.type === "choice") {
    const opts = (opt.choices || []).map(c =>
      `<option value="${c}" ${c === String(val) ? 'selected' : ''}>${c}</option>`
    ).join("");
    inputHtml = `<select data-cfg-key="${opt.key}">${opts}</select>`;
  } else {
    inputHtml = `<input type="text" data-cfg-key="${opt.key}" value="${val}">`;
  }

  return `
    <div class="cfg-row ${changed ? 'changed' : ''}">
      <div class="cfg-label">
        <span class="cfg-name">${opt.key}</span>
        <span class="cfg-help">${opt.help || ''}</span>
      </div>
      <div class="cfg-value">
        ${inputHtml}
        <span class="cfg-default">(${opt.type === 'bool' ? (opt.default ? 'y' : 'n') : opt.default})</span>
      </div>
    </div>`;
}

function modFindOption(mod, key) {
  for (const cat of mod.categories) {
    for (const opt of cat.options) {
      if (opt.key === key) return opt;
    }
  }
  return null;
}

async function modGenerateAll() {
  const btn = document.getElementById("modGenerateAllBtn");
  const outEl = document.getElementById("modOutput");
  const preEl = document.getElementById("modOutputPre");
  const copyBtn = document.getElementById("modCopyBtn");
  const fullOverlay = document.getElementById("modFullOverlay")?.checked;

  // Build multi-module payload
  const modulesPayload = {};
  for (const [id, en] of Object.entries(modEnabled)) {
    if (en) modulesPayload[id] = modValuesMap[id] || {};
  }

  if (Object.keys(modulesPayload).length === 0) {
    if (preEl) preEl.textContent = "No modules enabled. Check the boxes next to modules in the sidebar.";
    if (outEl) outEl.style.display = "";
    return;
  }

  btn.textContent = "⏳ Generating…";
  btn.disabled = true;

  try {
    const res = await fetch("/api/generate-module-config", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ modules: modulesPayload }),
    });
    const data = await res.json();

    if (!res.ok) {
      throw new Error(data.error || "Generation failed");
    }

    const text = fullOverlay ? data.overlay_conf : data.prj_conf;
    preEl.textContent = text;
    outEl.style.display = "";
    copyBtn.style.display = "";
  } catch (err) {
    preEl.textContent = `ERROR: ${err.message}`;
    outEl.style.display = "";
  } finally {
    modUpdateGenerateAllBtn();
    btn.disabled = false;
  }
}


// ══════════════════════════════════════════════════════════════════════
// Peripheral Configurator  (board-aware instance config)
// ══════════════════════════════════════════════════════════════════════

let pcfgInstances   = [];          // enriched peripheral instance list from API
let pcfgActiveInst  = null;        // currently selected instance name
let pcfgValues      = {};          // { instanceName: { propKey: value } }
let pcfgDefaults    = {};          // { instanceName: { propKey: default } }
let pcfgBoardName   = null;        // current board id
let pcfgBoardsLoaded = false;
let pcfgOutputTab   = "overlay";   // "overlay" | "prjconf"

function pcfgInit() {
  const search = document.getElementById("pcfgSearch");
  if (search) {
    search.addEventListener("input", () =>
      pcfgRenderSidebar(search.value.trim().toLowerCase())
    );
  }

  const boardSel = document.getElementById("pcfgBoardSelect");
  if (boardSel) {
    boardSel.addEventListener("change", () => {
      pcfgBoardName = boardSel.value;
      if (pcfgBoardName) pcfgLoadInstances(pcfgBoardName);
    });
  }
}

async function pcfgLoadBoards() {
  if (pcfgBoardsLoaded) return;
  try {
    const res = await fetch("/api/boards");
    const boards = await res.json();
    const sel = document.getElementById("pcfgBoardSelect");
    sel.innerHTML = "";

    if (boards.length === 0) {
      sel.innerHTML = '<option value="">No boards available</option>';
      return;
    }

    boards.forEach(b => {
      const opt = document.createElement("option");
      opt.value = b.id;
      opt.textContent = `${b.name} (${b.board})`;
      sel.appendChild(opt);
    });

    pcfgBoardsLoaded = true;
    pcfgBoardName = boards[0].id;
    await pcfgLoadInstances(pcfgBoardName);
  } catch (err) {
    console.error("Failed to load boards for peripheral configurator", err);
  }
}

async function pcfgLoadInstances(boardName) {
  try {
    const res = await fetch(`/api/peripheral-instances/${boardName}`);
    const data = await res.json();
    pcfgInstances = data.instances || [];
    pcfgActiveInst = null;

    // Build per-instance value & default maps
    pcfgValues = {};
    pcfgDefaults = {};
    for (const inst of pcfgInstances) {
      pcfgValues[inst.instance] = {};
      pcfgDefaults[inst.instance] = {};
      for (const grp of inst.groups) {
        for (const prop of grp.props) {
          pcfgDefaults[inst.instance][prop.key] = prop.default;
          pcfgValues[inst.instance][prop.key] = prop.default;
        }
      }
    }

    pcfgRenderSidebar();

    // Show empty main area
    const main = document.getElementById("pcfgMain");
    main.innerHTML = `<div class="pkg-empty">
      <div class="icon">🔧</div>
      <div>Peripheral Configurator</div>
      <div class="hint">Select a peripheral from the sidebar to configure it.<br>
        ${pcfgInstances.length} peripheral instance(s) found for ${data.soc || boardName}.</div>
    </div>`;
  } catch (err) {
    console.error("Failed to load peripheral instances", err);
  }
}

function pcfgRenderSidebar(filter = "") {
  const list = document.getElementById("pcfgInstanceList");
  if (!list) return;

  const filtered = pcfgInstances.filter(inst =>
    !filter ||
    inst.instance.toLowerCase().includes(filter) ||
    inst.display.toLowerCase().includes(filter) ||
    (inst.template || "").toLowerCase().includes(filter)
  );

  // Group by template type
  const groups = {};
  for (const inst of filtered) {
    const tpl = inst.template || "other";
    if (!groups[tpl]) groups[tpl] = [];
    groups[tpl].push(inst);
  }

  let html = "";
  for (const [tplId, insts] of Object.entries(groups)) {
    html += insts.map(inst => {
      const isActive = inst.instance === pcfgActiveInst;
      const statusVal = (pcfgValues[inst.instance] || {})["status"] || "okay";
      const changed = pcfgCountChanged(inst.instance);
      return `
        <div class="pcfg-instance-item ${isActive ? 'active' : ''}" data-inst="${inst.instance}">
          <div class="pcfg-icon">${inst.icon || '⚙️'}</div>
          <div class="pcfg-inst-label">
            ${inst.display}
            ${changed > 0 ? `<span class="pcfg-changed-dot" title="${changed} changed">●</span>` : ''}
          </div>
          <div class="pcfg-inst-compat">${inst.compatible.split(',').pop() || ''}</div>
          <div class="pcfg-status-dot ${statusVal === 'okay' ? 'enabled' : 'disabled'}"
               title="${statusVal}"></div>
        </div>`;
    }).join("");
  }

  list.innerHTML = html || '<div class="empty-state" style="padding:20px;font-size:12px;color:var(--fg-dim)">No peripherals found</div>';

  // Click handlers
  list.querySelectorAll(".pcfg-instance-item").forEach(el => {
    el.addEventListener("click", () => {
      pcfgActiveInst = el.dataset.inst;
      pcfgSelectInstance(pcfgActiveInst);
      list.querySelectorAll(".pcfg-instance-item").forEach(e2 =>
        e2.classList.toggle("active", e2.dataset.inst === pcfgActiveInst)
      );
    });
  });
}

function pcfgCountChanged(instName) {
  const vals = pcfgValues[instName] || {};
  const defs = pcfgDefaults[instName] || {};
  let n = 0;
  for (const k in defs) {
    if (String(vals[k]) !== String(defs[k])) n++;
  }
  return n;
}

function pcfgSelectInstance(instName) {
  const inst = pcfgInstances.find(i => i.instance === instName);
  if (!inst) return;

  const main = document.getElementById("pcfgMain");

  // Build signals HTML
  const signalsHtml = inst.signals.length > 0
    ? `<div class="pcfg-signals">
        ${inst.signals.map(s => `<span class="signal-tag">${s}</span>`).join('')}
       </div>`
    : '';

  main.innerHTML = `
    <div class="pcfg-header">
      <h2>${inst.icon || ''} ${inst.display}
        <span class="pcfg-compat-badge">${inst.compatible}</span>
      </h2>
      <div class="pcfg-desc">DTS node: <code>${inst.dts_node || '&' + inst.instance}</code></div>
      ${signalsHtml}
    </div>
    <div class="pcfg-body" id="pcfgBody"></div>
    <div class="pcfg-actions">
      <button class="btn" id="pcfgResetBtn">⟲ Reset</button>
      <span class="spacer"></span>
      <button class="btn btn-accent" id="pcfgGenerateBtn">⚡ Generate Config</button>
      <button class="btn" id="pcfgCopyBtn" style="display:none">📋 Copy</button>
    </div>
    <div class="pcfg-output" id="pcfgOutput" style="display:none">
      <div class="pcfg-output-tabs">
        <div class="pcfg-output-tab ${pcfgOutputTab === 'overlay' ? 'active' : ''}" data-ptab="overlay">.overlay</div>
        <div class="pcfg-output-tab ${pcfgOutputTab === 'prjconf' ? 'active' : ''}" data-ptab="prjconf">prj.conf</div>
      </div>
      <pre id="pcfgOutputPre"></pre>
    </div>
  `;

  pcfgRenderBody(inst);

  // Reset button
  document.getElementById("pcfgResetBtn").addEventListener("click", () => {
    pcfgValues[instName] = { ...pcfgDefaults[instName] };
    pcfgRenderBody(inst);
    pcfgRenderSidebar(document.getElementById("pcfgSearch")?.value?.trim().toLowerCase() || "");
    document.querySelectorAll(".pcfg-instance-item").forEach(e =>
      e.classList.toggle("active", e.dataset.inst === pcfgActiveInst));
    const outEl = document.getElementById("pcfgOutput");
    if (outEl) outEl.style.display = "none";
    document.getElementById("pcfgCopyBtn").style.display = "none";
  });

  // Generate button
  document.getElementById("pcfgGenerateBtn").addEventListener("click", () => pcfgGenerate());

  // Copy button
  document.getElementById("pcfgCopyBtn").addEventListener("click", () => {
    const text = document.getElementById("pcfgOutputPre").textContent;
    navigator.clipboard.writeText(text).then(() => {
      const btn = document.getElementById("pcfgCopyBtn");
      btn.textContent = "✓ Copied!";
      setTimeout(() => btn.textContent = "📋 Copy", 1500);
    });
  });

  // Output tab switching
  document.querySelectorAll(".pcfg-output-tab").forEach(tab => {
    tab.addEventListener("click", () => {
      pcfgOutputTab = tab.dataset.ptab;
      document.querySelectorAll(".pcfg-output-tab").forEach(t =>
        t.classList.toggle("active", t.dataset.ptab === pcfgOutputTab));
      // Re-display existing output
      const preEl = document.getElementById("pcfgOutputPre");
      if (preEl && preEl._overlayText) {
        preEl.textContent = pcfgOutputTab === "overlay" ? preEl._overlayText : preEl._prjconfText;
      }
    });
  });
}

function pcfgRenderBody(inst) {
  const body = document.getElementById("pcfgBody");
  if (!body) return;
  const vals = pcfgValues[inst.instance] || {};
  const defs = pcfgDefaults[inst.instance] || {};

  if (!inst.groups || inst.groups.length === 0) {
    body.innerHTML = '<div class="pkg-empty" style="padding:40px;"><div class="icon">⚙️</div><div>No configurable properties</div><div class="hint">This peripheral has no configuration template.</div></div>';
    return;
  }

  body.innerHTML = inst.groups.map(grp => {
    const rows = grp.props.map(prop => pcfgRenderProp(prop, vals, defs)).join("");
    return `
      <div class="cfg-group" data-cat="${grp.id}">
        <div class="cfg-group-header">
          <span class="chevron">▼</span>
          ${grp.title}
          <span class="group-count">${grp.props.length} properties</span>
        </div>
        <div class="cfg-group-body">${rows}</div>
      </div>`;
  }).join("");

  // Collapsible groups
  body.querySelectorAll(".cfg-group-header").forEach(hdr => {
    hdr.addEventListener("click", () => {
      hdr.parentElement.classList.toggle("collapsed");
    });
  });

  // Wire up value changes
  body.querySelectorAll("[data-pcfg-key]").forEach(el => {
    el.addEventListener("change", () => {
      const key = el.dataset.pcfgKey;
      const prop = pcfgFindProp(inst, key);
      if (!prop) return;

      if (prop.type === "bool") {
        vals[key] = el.checked;
      } else if (prop.type === "int") {
        vals[key] = parseInt(el.value, 10) || 0;
      } else if (prop.type === "choice") {
        // Numeric choices: parse as number
        const num = Number(el.value);
        vals[key] = isNaN(num) ? el.value : num;
      } else {
        vals[key] = el.value;
      }

      // Highlight changed rows
      const row = el.closest(".cfg-row");
      if (row) {
        row.classList.toggle("changed", String(vals[key]) !== String(defs[key]));
      }

      // Update sidebar status dots and changed indicators
      pcfgRenderSidebar(document.getElementById("pcfgSearch")?.value?.trim().toLowerCase() || "");
      document.querySelectorAll(".pcfg-instance-item").forEach(e =>
        e.classList.toggle("active", e.dataset.inst === pcfgActiveInst));
    });
  });
}

function pcfgRenderProp(prop, vals, defs) {
  const val = vals[prop.key] ?? prop.default;
  const changed = String(val) !== String(defs[prop.key]);
  let inputHtml = "";
  const dtsTag = prop.dts
    ? '<span style="font-size:10px;color:var(--teal);margin-left:4px;" title="DTS property">DTS</span>'
    : '';
  const kcTag = prop.kconfig
    ? '<span style="font-size:10px;color:var(--mauve);margin-left:4px;" title="Kconfig property">KC</span>'
    : '';

  if (prop.type === "bool") {
    inputHtml = `<input type="checkbox" data-pcfg-key="${prop.key}" ${val ? "checked" : ""}>`;
  } else if (prop.type === "int") {
    inputHtml = `<input type="number" data-pcfg-key="${prop.key}" value="${val}">`;
  } else if (prop.type === "choice") {
    const opts = (prop.choices || []).map(c =>
      `<option value="${c}" ${String(c) === String(val) ? 'selected' : ''}>${c}</option>`
    ).join("");
    inputHtml = `<select data-pcfg-key="${prop.key}">${opts}</select>`;
  } else {
    inputHtml = `<input type="text" data-pcfg-key="${prop.key}" value="${val || ''}" placeholder="${prop.default || ''}">`;
  }

  const defaultLabel = prop.type === 'bool' ? (prop.default ? 'y' : 'n') : prop.default;

  return `
    <div class="cfg-row ${changed ? 'changed' : ''}">
      <div class="cfg-label">
        <span class="cfg-name">${prop.label || prop.key}${dtsTag}${kcTag}</span>
        <span class="cfg-help">${prop.help || ''}</span>
      </div>
      <div class="cfg-value">
        ${inputHtml}
        <span class="cfg-default">(${defaultLabel})</span>
      </div>
    </div>`;
}

function pcfgFindProp(inst, key) {
  for (const grp of inst.groups) {
    for (const prop of grp.props) {
      if (prop.key === key) return prop;
    }
  }
  return null;
}

async function pcfgGenerate() {
  const btn = document.getElementById("pcfgGenerateBtn");
  const outEl = document.getElementById("pcfgOutput");
  const preEl = document.getElementById("pcfgOutputPre");
  const copyBtn = document.getElementById("pcfgCopyBtn");

  // Build payload: all instances that have changes OR are currently selected
  const payload = {};
  for (const inst of pcfgInstances) {
    const vals = pcfgValues[inst.instance] || {};
    const defs = pcfgDefaults[inst.instance] || {};
    const hasChanges = Object.keys(defs).some(k => String(vals[k]) !== String(defs[k]));
    if (hasChanges || inst.instance === pcfgActiveInst) {
      payload[inst.instance] = vals;
    }
  }

  if (Object.keys(payload).length === 0) {
    preEl.textContent = "No peripheral configuration changes to generate.";
    outEl.style.display = "";
    return;
  }

  btn.textContent = "⏳ Generating…";
  btn.disabled = true;

  try {
    const res = await fetch("/api/generate-peripheral-config", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        board: pcfgBoardName,
        instances: payload,
      }),
    });
    const data = await res.json();

    if (!res.ok) {
      throw new Error(data.error || "Generation failed");
    }

    // Store both texts on the element for tab switching
    preEl._overlayText = data.overlay;
    preEl._prjconfText = data.prj_conf;
    preEl.textContent = pcfgOutputTab === "overlay" ? data.overlay : data.prj_conf;
    outEl.style.display = "";
    copyBtn.style.display = "";
    toast("Peripheral config generated");
  } catch (err) {
    preEl.textContent = `ERROR: ${err.message}`;
    outEl.style.display = "";
  } finally {
    btn.textContent = "⚡ Generate Config";
    btn.disabled = false;
  }
}


// ══════════════════════════════════════════════════════════════════════
// Clock System Configurator module
// ══════════════════════════════════════════════════════════════════════

let clkTrees = [];          // summary list from /api/clock-trees
let clkCurrentTree = null;  // full tree object
let clkSelectedNode = null; // currently selected node id
let clkValues = {};         // { "prop-key": value, ... }
let clkFreqs = {};          // { "node_id": hz, ... }
let clkOutputTab = "overlay";
let clkTreesLoaded = false;

function clkInit() {
  const sel = $("#clkTreeSelect");
  if (sel) {
    sel.addEventListener("change", () => {
      const id = sel.value;
      if (id) clkLoadTree(id);
    });
  }
}

async function clkLoadTrees() {
  if (clkTreesLoaded) return;
  try {
    const res = await fetch("/api/clock-trees");
    clkTrees = await res.json();
    const sel = $("#clkTreeSelect");
    sel.innerHTML = '<option value="">— Select clock tree —</option>';
    clkTrees.forEach(t => {
      const opt = document.createElement("option");
      opt.value = t.id;
      opt.textContent = `${t.name} (${t.node_count} nodes)`;
      sel.appendChild(opt);
    });
    clkTreesLoaded = true;
  } catch (err) {
    console.error("Failed to load clock trees:", err);
  }
}

async function clkLoadTree(treeId) {
  try {
    const res = await fetch(`/api/clock-tree/${treeId}`);
    if (!res.ok) throw new Error("Not found");
    clkCurrentTree = await res.json();
    clkSelectedNode = null;
    clkValues = {};

    // Set defaults
    for (const node of clkCurrentTree.nodes) {
      for (const prop of node.props || []) {
        clkValues[prop.key] = prop.default;
      }
    }

    // Compute initial frequencies
    await clkComputeFreqs();
    clkRenderSidebar();
    clkRenderEmpty();
  } catch (err) {
    console.error("Failed to load clock tree:", err);
  }
}

async function clkComputeFreqs() {
  if (!clkCurrentTree) return;
  try {
    const res = await fetch("/api/clock-frequencies", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ tree: clkCurrentTree.id, values: clkValues }),
    });
    const data = await res.json();
    clkFreqs = data.frequencies || {};
  } catch (err) {
    console.error("Failed to compute frequencies:", err);
  }
}

function clkFormatFreq(hz) {
  if (!hz || hz <= 0) return "OFF";
  if (hz >= 1_000_000) return `${(hz / 1_000_000).toFixed(2)} MHz`;
  if (hz >= 1_000) return `${(hz / 1_000).toFixed(2)} kHz`;
  return `${hz} Hz`;
}

function clkRenderSidebar() {
  const list = $("#clkNodeList");
  if (!list || !clkCurrentTree) return;

  // Group by type for nice ordering
  const typeOrder = ["source", "pll", "mux", "divider", "output"];
  const sorted = [...clkCurrentTree.nodes].sort((a, b) => {
    return typeOrder.indexOf(a.type) - typeOrder.indexOf(b.type);
  });

  list.innerHTML = "";
  for (const node of sorted) {
    const item = document.createElement("div");
    item.className = "clkcfg-node-item" + (node.id === clkSelectedNode ? " active" : "");
    const freq = clkFreqs[node.id] || 0;
    item.innerHTML = `
      <span class="node-icon">${node.icon}</span>
      <span class="node-name">${node.name}</span>
      <span class="node-type t-${node.type}">${node.type}</span>
      <span class="node-freq">${clkFormatFreq(freq)}</span>
    `;
    item.addEventListener("click", () => clkSelectNode(node.id));
    list.appendChild(item);
  }
}

function clkSelectNode(nodeId) {
  clkSelectedNode = nodeId;
  clkRenderSidebar();
  clkRenderBody();
}

function clkRenderEmpty() {
  const main = $("#clkMain");
  if (!main) return;
  main.innerHTML = `
    <div class="pkg-empty">
      <div class="icon">⏱</div>
      <div>Clock System Configurator</div>
      <div class="hint">${clkCurrentTree
        ? "Select a clock node from the sidebar to configure it."
        : "Select a clock tree and configure oscillators, PLLs,<br>multiplexers, and dividers for your Zephyr project."}</div>
    </div>
  `;
}

function clkRenderBody() {
  const main = $("#clkMain");
  if (!main || !clkCurrentTree || !clkSelectedNode) { clkRenderEmpty(); return; }

  const node = clkCurrentTree.nodes.find(n => n.id === clkSelectedNode);
  if (!node) { clkRenderEmpty(); return; }

  const freq = clkFreqs[node.id] || 0;
  const props = node.props || [];

  // ── Header ──
  let html = `
    <div class="clkcfg-header">
      <div class="clkcfg-title">
        <span>${node.icon}</span>
        <span>${node.name}</span>
        <span class="node-type t-${node.type}" style="font-size:11px;padding:2px 8px;border-radius:6px;font-weight:600;text-transform:uppercase;">${node.type}</span>
      </div>
      <div class="clkcfg-desc">${node.desc}</div>
      <div class="clkcfg-freq-badge">${clkFormatFreq(freq)}</div>
    </div>
  `;

  // ── Tree diagram (visual) ──
  html += `<div class="clkcfg-body">`;

  // Show upstream/downstream context
  const conns = clkCurrentTree.connections || [];
  const upstreamIds = conns.filter(c => c.to === node.id).map(c => c.from);
  const downstreamIds = conns.filter(c => c.from === node.id).map(c => c.to);
  const nodeMap = {};
  clkCurrentTree.nodes.forEach(n => { nodeMap[n.id] = n; });

  if (upstreamIds.length || downstreamIds.length) {
    html += `<div class="cfg-group"><div class="cfg-group-header" style="cursor:default;">
      <span class="toggle">🔗</span> Clock Path
    </div><div class="cfg-group-body" style="display:block;">`;

    html += `<div class="clkcfg-tree-diagram">`;

    // Upstream column
    if (upstreamIds.length) {
      html += `<div class="clkcfg-tree-column">
        <div class="clkcfg-tree-column-label">Upstream</div>`;
      upstreamIds.forEach(uid => {
        const un = nodeMap[uid];
        if (!un) return;
        const uf = clkFreqs[uid] || 0;
        html += `<div class="clkcfg-tree-node" onclick="clkSelectNode('${uid}')">
          <div class="tn-name">${un.icon} ${un.name}</div>
          <div class="tn-freq">${clkFormatFreq(uf)}</div>
        </div>`;
      });
      html += `</div>`;
    }

    // Current node column
    html += `<div class="clkcfg-tree-column">
      <div class="clkcfg-tree-column-label">Current</div>
      <div class="clkcfg-tree-node active">
        <div class="tn-name">${node.icon} ${node.name}</div>
        <div class="tn-freq">${clkFormatFreq(freq)}</div>
      </div>
    </div>`;

    // Downstream column
    if (downstreamIds.length) {
      html += `<div class="clkcfg-tree-column">
        <div class="clkcfg-tree-column-label">Downstream</div>`;
      downstreamIds.forEach(did => {
        const dn = nodeMap[did];
        if (!dn) return;
        const df = clkFreqs[did] || 0;
        html += `<div class="clkcfg-tree-node" onclick="clkSelectNode('${did}')">
          <div class="tn-name">${dn.icon} ${dn.name}</div>
          <div class="tn-freq">${clkFormatFreq(df)}</div>
        </div>`;
      });
      html += `</div>`;
    }

    html += `</div></div></div>`;
  }

  // ── Properties group ──
  if (props.length) {
    html += `<div class="cfg-group"><div class="cfg-group-header" style="cursor:default;">
      <span class="toggle">⚙</span> Configuration
    </div><div class="cfg-group-body" style="display:block;">`;

    for (const prop of props) {
      const val = clkValues[prop.key] ?? prop.default;
      html += `<div class="cfg-row">`;
      html += `<div class="cfg-label">
        <span class="cfg-name">${prop.label}</span>
        <span class="cfg-help">${prop.help || ""}</span>
        <span class="cfg-default">Default: ${prop.default}</span>
      </div>`;
      html += `<div class="cfg-value">`;

      if (prop.type === "bool") {
        html += `<label style="display:flex;align-items:center;gap:6px;cursor:pointer;">
          <input type="checkbox" data-clk-key="${prop.key}" ${val ? "checked" : ""} style="accent-color:var(--accent);width:16px;height:16px;">
          <span style="font-size:13px;">${val ? "Enabled" : "Disabled"}</span>
        </label>`;
      } else if (prop.type === "choice") {
        html += `<select data-clk-key="${prop.key}" style="padding:5px 8px;font-size:13px;background:var(--bg);color:var(--fg);border:1px solid var(--border);border-radius:6px;">`;
        for (const ch of prop.choices) {
          const sel = (String(ch) === String(val)) ? " selected" : "";
          let label = ch;
          if (typeof ch === "number" && ch >= 1_000_000) label = `${(ch / 1_000_000).toFixed(1)} MHz`;
          else if (typeof ch === "number" && ch >= 1_000) label = `${(ch / 1_000).toFixed(1)} kHz`;
          html += `<option value="${ch}"${sel}>${label}</option>`;
        }
        html += `</select>`;
      } else if (prop.type === "int") {
        html += `<input type="number" data-clk-key="${prop.key}" value="${val}" style="width:120px;padding:5px 8px;font-size:13px;background:var(--bg);color:var(--fg);border:1px solid var(--border);border-radius:6px;">`;
      }

      html += `</div></div>`;
    }

    html += `</div></div>`;
  } else {
    html += `<div class="cfg-group"><div class="cfg-group-header" style="cursor:default;">
      <span class="toggle">ℹ</span> Info
    </div><div class="cfg-group-body" style="display:block;">
      <div style="padding:12px;color:var(--fg-dim);font-size:13px;">
        This node has no configurable properties. Its frequency is derived from upstream nodes.
      </div>
    </div></div>`;
  }

  // ── Peripheral clock assignments ──
  if (node.type === "output" && clkCurrentTree.peripheral_clocks) {
    const assignments = Object.entries(clkCurrentTree.peripheral_clocks)
      .filter(([, clk]) => clk === node.id);
    if (assignments.length) {
      html += `<div class="cfg-group"><div class="cfg-group-header" style="cursor:default;">
        <span class="toggle">🔌</span> Peripheral Assignments
      </div><div class="cfg-group-body" style="display:block;">`;
      html += `<div style="display:flex;flex-wrap:wrap;gap:6px;padding:8px 0;">`;
      for (const [periph] of assignments) {
        html += `<span style="font-size:12px;background:var(--bg);color:var(--teal);padding:3px 10px;border-radius:8px;border:1px solid var(--border);">${periph}</span>`;
      }
      html += `</div></div></div>`;
    }
  }

  html += `</div>`; // close clkcfg-body

  // ── Actions ──
  html += `
    <div class="clkcfg-actions">
      <button class="btn btn-accent" id="clkGenerateBtn" onclick="clkGenerate()">⚡ Generate Config</button>
      <button class="btn" id="clkCopyBtn" style="display:none;" onclick="clkCopyOutput()">📋 Copy</button>
      <span class="spacer"></span>
      <span style="font-size:12px;color:var(--fg-dim);">
        Max SoC freq: ${clkFormatFreq(clkCurrentTree.max_freq)}
      </span>
    </div>
    <div class="clkcfg-output" id="clkOutput" style="display:none;">
      <div class="clkcfg-output-tabs">
        <div class="clkcfg-output-tab ${clkOutputTab === "overlay" ? "active" : ""}" data-clk-out="overlay">.overlay</div>
        <div class="clkcfg-output-tab ${clkOutputTab === "prj_conf" ? "active" : ""}" data-clk-out="prj_conf">prj.conf</div>
        <div class="clkcfg-output-tab ${clkOutputTab === "freq" ? "active" : ""}" data-clk-out="freq">Frequencies</div>
      </div>
      <pre id="clkOutputPre"></pre>
    </div>
  `;

  main.innerHTML = html;

  // ── Wire up change events ──
  main.querySelectorAll("[data-clk-key]").forEach(el => {
    const key = el.dataset.clkKey;
    const evName = (el.type === "checkbox") ? "change" : "input";
    el.addEventListener(evName, async () => {
      if (el.type === "checkbox") {
        clkValues[key] = el.checked;
        const span = el.closest("label").querySelector("span:last-child");
        if (span) span.textContent = el.checked ? "Enabled" : "Disabled";
      } else if (el.type === "number") {
        clkValues[key] = parseInt(el.value) || 0;
      } else {
        // select: try numeric parse
        const num = Number(el.value);
        clkValues[key] = isNaN(num) ? el.value : num;
      }
      await clkComputeFreqs();
      clkRenderSidebar();
      // Update freq badge inline
      const badge = main.querySelector(".clkcfg-freq-badge");
      if (badge) badge.textContent = clkFormatFreq(clkFreqs[clkSelectedNode] || 0);
      // Update tree diagram freqs
      main.querySelectorAll(".clkcfg-tree-node .tn-freq").forEach(tnf => {
        // find node id from onclick
        const parent = tnf.closest(".clkcfg-tree-node");
        if (!parent) return;
        const onclick = parent.getAttribute("onclick") || "";
        const m = onclick.match(/clkSelectNode\('(.+?)'\)/);
        if (m) tnf.textContent = clkFormatFreq(clkFreqs[m[1]] || 0);
      });
      // Update current node in diagram
      const activeNode = main.querySelector(".clkcfg-tree-node.active .tn-freq");
      if (activeNode) activeNode.textContent = clkFormatFreq(clkFreqs[clkSelectedNode] || 0);
    });
  });

  // ── Wire up output tab switching ──
  main.querySelectorAll("[data-clk-out]").forEach(tab => {
    tab.addEventListener("click", () => {
      clkOutputTab = tab.dataset.clkOut;
      main.querySelectorAll("[data-clk-out]").forEach(t => t.classList.toggle("active", t.dataset.clkOut === clkOutputTab));
      const preEl = $("#clkOutputPre");
      if (preEl && preEl._data) {
        if (clkOutputTab === "overlay") preEl.textContent = preEl._data.overlay;
        else if (clkOutputTab === "prj_conf") preEl.textContent = preEl._data.prj_conf;
        else if (clkOutputTab === "freq") preEl.textContent = clkFormatFreqTable(preEl._data.frequencies);
      }
    });
  });
}

function clkFormatFreqTable(freqs) {
  if (!freqs || !clkCurrentTree) return "";
  const lines = ["Clock Node Frequencies", "═".repeat(50), ""];
  const nodeMap = {};
  clkCurrentTree.nodes.forEach(n => { nodeMap[n.id] = n; });
  for (const [id, hz] of Object.entries(freqs)) {
    const n = nodeMap[id];
    if (!n) continue;
    const pad = 25 - n.name.length;
    lines.push(`  ${n.icon} ${n.name}${" ".repeat(Math.max(1, pad))}${clkFormatFreq(hz).padStart(14)}`);
  }
  // Peripheral assignments
  if (clkCurrentTree.peripheral_clocks && Object.keys(clkCurrentTree.peripheral_clocks).length) {
    lines.push("");
    lines.push("Peripheral Clock Assignments");
    lines.push("─".repeat(50));
    for (const [periph, clk] of Object.entries(clkCurrentTree.peripheral_clocks)) {
      const hz = freqs[clk] || 0;
      const pad = 25 - periph.length;
      lines.push(`  ${periph}${" ".repeat(Math.max(1, pad))}← ${clk} (${clkFormatFreq(hz)})`);
    }
  }
  return lines.join("\n");
}

async function clkGenerate() {
  if (!clkCurrentTree) return;
  const btn = $("#clkGenerateBtn");
  const outEl = $("#clkOutput");
  const preEl = $("#clkOutputPre");
  const copyBtn = $("#clkCopyBtn");

  btn.textContent = "Generating...";
  btn.disabled = true;

  try {
    const res = await fetch("/api/generate-clock-config", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ tree: clkCurrentTree.id, values: clkValues }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || "Generation failed");

    preEl._data = data;
    clkFreqs = data.frequencies || clkFreqs;

    if (clkOutputTab === "overlay") preEl.textContent = data.overlay;
    else if (clkOutputTab === "prj_conf") preEl.textContent = data.prj_conf;
    else preEl.textContent = clkFormatFreqTable(data.frequencies);

    outEl.style.display = "";
    copyBtn.style.display = "";
    clkRenderSidebar();
    toast("Clock config generated");
  } catch (err) {
    preEl.textContent = `ERROR: ${err.message}`;
    outEl.style.display = "";
  } finally {
    btn.textContent = "⚡ Generate Config";
    btn.disabled = false;
  }
}

function clkCopyOutput() {
  const preEl = $("#clkOutputPre");
  if (preEl && preEl.textContent) {
    navigator.clipboard.writeText(preEl.textContent).then(() => toast("Copied to clipboard"));
  }
}


// ══════════════════════════════════════════════════════════════════════
// Import Configuration module
// ══════════════════════════════════════════════════════════════════════

let impOverlayText = "";
let impConfText = "";
let impParsed = null;     // Last parsed result from the server
let impScannedFiles = []; // Files found by project scan

function impInit() {
  if (!$("#btnImport") || !$("#importModal")) return;

  // Open modal
  $("#btnImport").addEventListener("click", () => {
    impReset();
    $("#importModal").classList.add("show");
  });

  // Close modal
  $("#impBtnCancel").addEventListener("click", () => {
    $("#importModal").classList.remove("show");
  });
  $("#importModal").addEventListener("click", (e) => {
    if (e.target === e.currentTarget) {
      $("#importModal").classList.remove("show");
    }
  });

  // Tab switching
  $$("#importModal .imp-tab").forEach(tab => {
    tab.addEventListener("click", () => {
      const target = tab.dataset.impTab;
      $$("#importModal .imp-tab").forEach(t => t.classList.toggle("active", t.dataset.impTab === target));
      $$("#importModal .imp-panel").forEach(p => p.classList.toggle("active", p.dataset.impPanel === target));
    });
  });

  // File upload: overlay
  const dropOverlay = $("#impDropOverlay");
  const overlayInput = $("#impOverlayFile");
  dropOverlay.addEventListener("click", () => overlayInput.click());
  overlayInput.addEventListener("change", () => {
    if (overlayInput.files.length) {
      impReadFile(overlayInput.files[0], "overlay");
      overlayInput.value = "";
    }
  });
  impSetupDragDrop(dropOverlay, "overlay");

  // File upload: conf
  const dropConf = $("#impDropConf");
  const confInput = $("#impConfFile");
  dropConf.addEventListener("click", () => confInput.click());
  confInput.addEventListener("change", () => {
    if (confInput.files.length) {
      impReadFile(confInput.files[0], "conf");
      confInput.value = "";
    }
  });
  impSetupDragDrop(dropConf, "conf");

  // Project scan
  $("#impBtnScan").addEventListener("click", impScanProject);

  // Paste text: auto-parse on input
  $("#impPasteOverlay").addEventListener("input", impPasteChanged);
  $("#impPasteConf").addEventListener("input", impPasteChanged);

  // Apply
  $("#impBtnApply").addEventListener("click", impApply);
}

function impReset() {
  impOverlayText = "";
  impConfText = "";
  impParsed = null;
  impScannedFiles = [];
  $("#impOverlayName").textContent = "No file selected";
  $("#impConfName").textContent = "No file selected";
  $("#impPasteOverlay").value = "";
  $("#impPasteConf").value = "";
  $("#impFileList").innerHTML = "";
  $("#impPreview").style.display = "none";
  $("#impBtnApply").disabled = true;
}

function impSetupDragDrop(zone, type) {
  zone.addEventListener("dragover", (e) => {
    e.preventDefault();
    zone.classList.add("drag-over");
  });
  zone.addEventListener("dragleave", () => {
    zone.classList.remove("drag-over");
  });
  zone.addEventListener("drop", (e) => {
    e.preventDefault();
    zone.classList.remove("drag-over");
    if (e.dataTransfer.files.length) {
      impReadFile(e.dataTransfer.files[0], type);
    }
  });
}

function impReadFile(file, type) {
  const reader = new FileReader();
  reader.onload = () => {
    const text = reader.result;
    if (type === "overlay") {
      impOverlayText = text;
      $("#impOverlayName").textContent = `${file.name} (${(file.size/1024).toFixed(1)} KB)`;
    } else {
      impConfText = text;
      $("#impConfName").textContent = `${file.name} (${(file.size/1024).toFixed(1)} KB)`;
    }
    impParseAndPreview();
  };
  reader.readAsText(file);
}

function impPasteChanged() {
  impOverlayText = $("#impPasteOverlay").value;
  impConfText = $("#impPasteConf").value;
  // Debounce parse
  clearTimeout(impPasteChanged._timer);
  impPasteChanged._timer = setTimeout(impParseAndPreview, 400);
}

async function impParseAndPreview() {
  if (!impOverlayText && !impConfText) {
    $("#impPreview").style.display = "none";
    $("#impBtnApply").disabled = true;
    return;
  }

  try {
    const res = await fetch("/api/import-config", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        overlay: impOverlayText,
        conf: impConfText,
        board_name: boardData?.board || "",
      }),
    });

    const data = await res.json();
    if (!res.ok) {
      toast(`Parse error: ${data.error}`);
      return;
    }

    impParsed = data;
    impRenderPreview(data);
    $("#impBtnApply").disabled = false;
  } catch (err) {
    toast(`Parse failed: ${err.message}`);
  }
}

function impRenderPreview(data) {
  const el = $("#impPreviewContent");
  const pinCount = data.pins?.length || 0;
  const periphCount = data.peripherals?.length || 0;
  const kconfigCount = data.kconfig?.length || 0;
  const warnings = data.warnings || [];

  let html = `<div style="margin-bottom:6px;"><b>Found:</b></div>`;
  html += `<div>\u2022 <b>${pinCount}</b> pin assignment(s)`;
  if (pinCount > 0) {
    html += `: ` + data.pins.map(p =>
      `<span style="color:var(--accent)">${p.pin_name || p.node_label}</span> = ${p.peripheral}.${p.signal}`
    ).join(", ");
  }
  html += `</div>`;

  html += `<div>\u2022 <b>${periphCount}</b> peripheral(s)`;
  if (periphCount > 0) {
    html += `: ` + data.peripherals.map(p =>
      `<span style="color:${p.enabled ? 'var(--green)' : 'var(--fg-dim)'}">${p.name}</span>`
    ).join(", ");
  }
  html += `</div>`;

  html += `<div>\u2022 <b>${kconfigCount}</b> Kconfig option(s)</div>`;

  if (warnings.length) {
    html += `<div style="margin-top:6px;color:var(--yellow);">\u26A0 Warnings:</div>`;
    warnings.forEach(w => { html += `<div style="font-size:10px;color:var(--yellow);">\u2022 ${w}</div>`; });
  }

  el.innerHTML = html;
  $("#impPreview").style.display = "";
}

async function impScanProject() {
  const path = $("#impProjectPath").value.trim();
  if (!path) {
    toast("Enter a project directory path");
    return;
  }

  try {
    const res = await fetch("/api/scan-project", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ project_path: path }),
    });

    const data = await res.json();
    if (!res.ok) {
      toast(`Scan error: ${data.error}`);
      return;
    }

    impScannedFiles = data.files || [];
    impRenderFileList();

    if (impScannedFiles.length === 0) {
      toast("No .overlay or .conf files found");
    } else {
      toast(`Found ${impScannedFiles.length} file(s)`);
      // Auto-select overlay + conf if we find them
      impAutoSelectScanned();
    }
  } catch (err) {
    toast(`Scan failed: ${err.message}`);
  }
}

function impRenderFileList() {
  const el = $("#impFileList");
  if (impScannedFiles.length === 0) {
    el.innerHTML = `<div style="padding:12px;text-align:center;color:var(--fg-dim);font-size:11px;">No files found</div>`;
    return;
  }

  el.innerHTML = impScannedFiles.map((f, i) => {
    const icon = f.type === "overlay" ? "&#128196;" : "&#9881;";
    const sel = f._selected ? " selected" : "";
    return `<div class="imp-file-item${sel}" data-idx="${i}">
      <span class="file-icon">${icon}</span>
      <span class="file-name">${f.relative}</span>
      <span class="file-size">${(f.size/1024).toFixed(1)} KB</span>
    </div>`;
  }).join("");

  el.querySelectorAll(".imp-file-item").forEach(item => {
    item.addEventListener("click", () => {
      const idx = parseInt(item.dataset.idx);
      const f = impScannedFiles[idx];
      f._selected = !f._selected;
      impRenderFileList();
      impUpdateFromScanned();
    });
  });
}

function impAutoSelectScanned() {
  // Prefer board-specific overlay + conf, fall back to prj.conf
  let overlayFile = null;
  let confFile = null;

  for (const f of impScannedFiles) {
    if (f.type === "overlay" && !overlayFile) {
      overlayFile = f;
    }
    if (f.type === "conf") {
      if (f.name !== "prj.conf" && !confFile) {
        confFile = f; // Board-specific conf
      } else if (!confFile) {
        confFile = f; // prj.conf as fallback
      }
    }
  }

  if (overlayFile) overlayFile._selected = true;
  if (confFile) confFile._selected = true;

  impRenderFileList();
  impUpdateFromScanned();
}

function impUpdateFromScanned() {
  impOverlayText = "";
  impConfText = "";

  for (const f of impScannedFiles) {
    if (!f._selected) continue;
    if (f.type === "overlay") {
      impOverlayText += f.content + "\n";
    } else {
      impConfText += f.content + "\n";
    }
  }

  impParseAndPreview();
}

function impApply() {
  if (!impParsed || !boardData) {
    toast("No parsed data to apply");
    return;
  }

  // Apply pin assignments
  const data = impParsed;
  let applied = 0;

  // Match parsed pins to board pins by pin_name + pincm + peripheral
  for (const pp of (data.pins || [])) {
    // Find the board pin by name
    const boardPin = boardData.pins.find(p =>
      p.name.toUpperCase() === (pp.pin_name || "").toUpperCase()
    );
    if (!boardPin) continue;

    // Find matching alt function
    const af = boardPin.alt_functions.find(a =>
      a.pincm === pp.pincm && a.function_id === pp.function_id
    ) || boardPin.alt_functions.find(a =>
      a.peripheral === pp.peripheral && a.signal === pp.signal
    );

    if (af) {
      pinStates[boardPin.number] = {
        af: af,
        props: {
          bias_pull_up: pp.bias_pull_up || false,
          bias_pull_down: pp.bias_pull_down || false,
          drive_open_drain: pp.drive_open_drain || false,
          input_enable: pp.input_enable || false,
        }
      };
      applied++;
    }
  }

  // Apply peripheral enables
  for (const pp of (data.peripherals || [])) {
    if (pp.name in periphStates) {
      periphStates[pp.name] = pp.enabled;
    }
  }

  // Re-render
  renderPeripherals();
  renderChip();
  renderConfigPanel();

  // Close modal
  $("#importModal").classList.remove("show");
  toast(`Imported ${applied} pin(s), ${(data.peripherals||[]).length} peripheral(s)`);
}


// ══════════════════════════════════════════════════════════════════════
// MCU Lookup module (in Package Manager)
// ══════════════════════════════════════════════════════════════════════

function mcuInit() {
  const input = $("#mcuPartInput");
  const btn = $("#mcuBtnLookup");

  if (!btn) return;

  btn.addEventListener("click", mcuLookup);
  input.addEventListener("keydown", (e) => {
    if (e.key === "Enter") mcuLookup();
  });
}

async function mcuLookup() {
  const input = $("#mcuPartInput");
  const resultEl = $("#mcuLookupResult");
  const pn = input.value.trim();

  if (!pn) {
    toast("Enter an MCU part number");
    return;
  }

  resultEl.innerHTML = `<div style="padding:8px;text-align:center;">Looking up ${pn}...</div>`;

  try {
    // Step 1: Identify the MCU
    const idRes = await fetch("/api/identify-mcu", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ part_number: pn }),
    });

    const idData = await idRes.json();
    if (!idRes.ok) {
      resultEl.innerHTML = `<div style="color:var(--red);padding:4px;">${idData.error}</div>`;
      return;
    }

    let html = "";

    if (idData.existing_board) {
      html += `<div style="padding:4px;color:var(--green);">\u2705 Board <b>${idData.existing_board}</b> already exists</div>`;
    }

    if (idData.known) {
      html += `<div style="padding:4px;">\u2022 Vendor: <b>${idData.vendor_name}</b></div>`;
      html += `<div style="padding:4px;">\u2022 Family: <b>${idData.family}</b></div>`;

      if (idData.datasheet_urls.length) {
        html += `<div style="padding:4px;">\u2022 Datasheet URLs:</div>`;
        idData.datasheet_urls.forEach(url => {
          html += `<div style="padding:2px 4px 2px 16px;">
            <a href="${url}" target="_blank" style="color:var(--accent);font-size:10px;word-break:break-all;">${url}</a>
          </div>`;
        });
      }

      if (!idData.existing_board) {
        html += `<div style="margin-top:8px;">
          <button class="btn btn-accent" id="mcuBtnFetch" style="font-size:11px;padding:4px 12px;">
            \u2B07 Fetch & Parse Datasheet
          </button>
          <div style="margin-top:4px;">
            <label style="font-size:10px;color:var(--fg-dim);">Or enter a custom URL:</label>
            <input type="text" id="mcuCustomUrl" style="width:100%;padding:4px 6px;margin-top:2px;font-size:10px;background:var(--bg);color:var(--fg);border:1px solid var(--border);border-radius:var(--radius);"
                   placeholder="https://...datasheet.pdf">
          </div>
        </div>`;
      }
    } else {
      html += `<div style="padding:4px;color:var(--yellow);">\u26A0 Unknown vendor for "${pn}"</div>`;
      html += `<div style="margin-top:8px;">
        <label style="font-size:10px;color:var(--fg-dim);">Provide a direct datasheet PDF URL:</label>
        <input type="text" id="mcuCustomUrl" style="width:100%;padding:4px 6px;margin-top:2px;font-size:10px;background:var(--bg);color:var(--fg);border:1px solid var(--border);border-radius:var(--radius);"
               placeholder="https://...datasheet.pdf">
        <button class="btn btn-accent" id="mcuBtnFetch" style="font-size:11px;padding:4px 12px;margin-top:6px;">
          \u2B07 Fetch & Parse Datasheet
        </button>
      </div>`;
    }

    resultEl.innerHTML = html;

    // Wire up fetch button if present
    const fetchBtn = $("#mcuBtnFetch");
    if (fetchBtn) {
      fetchBtn.addEventListener("click", () => mcuFetchDatasheet(pn));
    }

  } catch (err) {
    resultEl.innerHTML = `<div style="color:var(--red);">Error: ${err.message}</div>`;
  }
}

async function mcuFetchDatasheet(partNumber) {
  const resultEl = $("#mcuLookupResult");
  const customUrl = $("#mcuCustomUrl")?.value?.trim() || "";
  const fetchBtn = $("#mcuBtnFetch");

  if (fetchBtn) {
    fetchBtn.disabled = true;
    fetchBtn.textContent = "Downloading...";
  }

  try {
    const body = { part_number: partNumber };
    if (customUrl) body.url = customUrl;

    const res = await fetch("/api/fetch-datasheet", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });

    const data = await res.json();

    if (!res.ok) {
      resultEl.innerHTML += `<div style="color:var(--red);margin-top:8px;">\u274C ${data.error}</div>`;
      return;
    }

    // Success! Add to parsed jobs list and select it
    pkgJobs.push({
      job_id: data.job_id,
      filename: data.part_number + "_datasheet.pdf",
      result: data.result,
    });

    pkgSaveToStorage();
    pkgRenderJobList();
    pkgSelectJob(data.job_id);

    resultEl.innerHTML += `<div style="color:var(--green);margin-top:8px;">
      \u2705 ${data.message}<br>
      Found ${data.result.packages.length} package(s), ${data.result.pin_mux_count} PINCM entries
    </div>`;

    toast(`Fetched & parsed datasheet for ${partNumber}`);

  } catch (err) {
    resultEl.innerHTML += `<div style="color:var(--red);margin-top:8px;">Error: ${err.message}</div>`;
  } finally {
    if (fetchBtn) {
      fetchBtn.disabled = false;
      fetchBtn.textContent = "\u2B07 Fetch & Parse Datasheet";
    }
  }
}


// ══════════════════════════════════════════════════════════════════════
// Sensor Parser module
// ══════════════════════════════════════════════════════════════════════

let snsJobs = [];
let snsSelectedJob = null;

// ── LocalStorage persistence helpers ─────────────────────────────────

function snsSaveToStorage() {
  try {
    const data = snsJobs.map(j => ({
      job_id: j.job_id,
      filename: j.filename,
      result: j.result,
      summary: j.summary || null,
    }));
    localStorage.setItem("zpincfg_sns_jobs", JSON.stringify(data));
    localStorage.setItem("zpincfg_sns_selected", snsSelectedJob || "");
  } catch (e) { console.warn("snsSaveToStorage:", e); }
}

function snsLoadFromStorage() {
  try {
    const raw = localStorage.getItem("zpincfg_sns_jobs");
    if (raw) {
      const data = JSON.parse(raw);
      if (Array.isArray(data) && data.length) {
        snsJobs = data;
        snsSelectedJob = localStorage.getItem("zpincfg_sns_selected") || null;
        return true;
      }
    }
  } catch (e) { console.warn("snsLoadFromStorage:", e); }
  return false;
}

function snsRemoveJob(jobId) {
  snsJobs = snsJobs.filter(j => j.job_id !== jobId);
  if (snsSelectedJob === jobId) {
    snsSelectedJob = snsJobs.length ? snsJobs[0].job_id : null;
  }
  snsSaveToStorage();
  snsRenderJobList();
  if (snsSelectedJob) snsSelectJob(snsSelectedJob);
  else {
    $("#snsMain").innerHTML = `<div class="sns-empty">
      <div class="icon">🔬</div>
      <div>Sensor / IC Register Parser</div>
      <div class="hint">Upload a sensor datasheet PDF to extract the register map,<br>
        I2C/SPI addresses, bit-fields, and generate C headers.</div>
    </div>`;
  }
}

function snsInit() {
  const uploadArea = $("#snsUploadArea");
  const fileInput  = $("#snsFileInput");

  // Click to browse
  uploadArea.addEventListener("click", () => fileInput.click());

  // File selected via browse
  fileInput.addEventListener("change", () => {
    if (fileInput.files.length) {
      snsUploadPdf(fileInput.files[0]);
      fileInput.value = "";
    }
  });

  // Drag & drop
  uploadArea.addEventListener("dragover", (e) => {
    e.preventDefault();
    uploadArea.classList.add("dragover");
  });
  uploadArea.addEventListener("dragleave", () => {
    uploadArea.classList.remove("dragover");
  });
  uploadArea.addEventListener("drop", (e) => {
    e.preventDefault();
    uploadArea.classList.remove("dragover");
    if (e.dataTransfer.files.length) {
      const file = e.dataTransfer.files[0];
      if (file.name.toLowerCase().endsWith(".pdf")) {
        snsUploadPdf(file);
      } else {
        toast("Please drop a .pdf file");
      }
    }
  });

  // Sensor identify button
  const idBtn = $("#snsBtnIdentify");
  const idInput = $("#snsPartInput");
  idBtn.addEventListener("click", () => snsIdentifySensor());
  idInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter") snsIdentifySensor();
  });

  // Restore from localStorage on init
  if (snsLoadFromStorage()) {
    snsRenderJobList();
    if (snsSelectedJob) {
      snsSelectJob(snsSelectedJob);
    }
  }
}


// ── Upload & Parse ───────────────────────────────────────────────────

async function snsUploadPdf(file) {
  const uploadArea = $("#snsUploadArea");
  const origHTML = uploadArea.innerHTML;

  uploadArea.innerHTML = `
    <div class="spinner"></div>
    <div style="margin-top:8px;">Parsing ${file.name}...</div>
    <div class="upload-hint">Extracting register map &amp; addresses</div>
  `;

  const formData = new FormData();
  formData.append("pdf", file);

  try {
    const res = await fetch("/api/parse-sensor-pdf", { method: "POST", body: formData });
    const data = await res.json();

    if (!res.ok) {
      uploadArea.innerHTML = origHTML;
      toast(data.error || "Upload failed");
      return;
    }

    snsJobs.push({
      job_id: data.job_id,
      filename: data.filename,
      result: data.result,
    });

    snsSaveToStorage();
    snsRenderJobList();
    snsSelectJob(data.job_id);
    toast(`Parsed ${data.result.summary.part_number || file.name}: ${data.result.register_map.registers.length} registers found`);
  } catch (err) {
    toast("Upload error: " + err.message);
  } finally {
    uploadArea.innerHTML = origHTML;
  }
}


// ── Load existing jobs ───────────────────────────────────────────────

async function snsLoadJobs() {
  // First restore from localStorage (has full result data)
  const hadLocal = snsLoadFromStorage();

  try {
    const res = await fetch("/api/sensor-jobs");
    const serverJobs = await res.json();

    // Merge: server jobs that we don't already have locally
    const existingIds = new Set(snsJobs.map(j => j.job_id));
    for (const j of serverJobs) {
      if (!existingIds.has(j.job_id)) {
        snsJobs.push({
          job_id: j.job_id,
          filename: j.filename,
          result: null,           // lazy-loaded
          summary: {
            part_number: j.part_number,
            vendor: j.vendor,
            sensor_type: j.sensor_type,
            register_count: j.register_count,
            i2c_addresses: j.i2c_addresses,
            protocol: j.protocol,
          },
        });
      }
    }

    snsSaveToStorage();
    snsRenderJobList();

    // Auto-select the previously selected job
    if (snsSelectedJob) {
      snsSelectJob(snsSelectedJob);
    }
  } catch (err) {
    console.error("snsLoadJobs:", err);
    // If server is unreachable but we have local data, still render
    if (hadLocal) {
      snsRenderJobList();
      if (snsSelectedJob) snsSelectJob(snsSelectedJob);
    }
  }
}


// ── Render job list ──────────────────────────────────────────────────

function snsRenderJobList() {
  const list = $("#snsJobList");
  if (!snsJobs.length) {
    list.innerHTML = `<div class="empty-state" style="padding:20px;">
      <div>No sensors parsed yet</div>
      <div class="hint">Upload a PDF above</div>
    </div>`;
    return;
  }

  list.innerHTML = snsJobs.map(j => {
    const s = j.result ? j.result.summary : j.summary;
    const pn = s ? (s.part_number || j.filename) : j.filename;
    const vendor = s ? (s.vendor_name || s.vendor || "") : "";
    const type = s ? (s.sensor_type || "") : "";
    const regCount = j.result ? j.result.register_map.registers.length : (s ? s.register_count || 0 : 0);
    const selected = j.job_id === snsSelectedJob ? " selected" : "";

    return `<div class="sns-job-item${selected}" data-id="${j.job_id}">
      <button class="job-remove-btn" data-remove-id="${j.job_id}" title="Remove">&times;</button>
      <div class="job-name">
        ${pn}
        ${vendor ? `<span class="sns-badge">${vendor}</span>` : ""}
      </div>
      <div class="job-info">${type ? type + " · " : ""}${regCount} registers</div>
    </div>`;
  }).join("");

  list.querySelectorAll(".sns-job-item").forEach(el => {
    el.addEventListener("click", (e) => {
      if (e.target.closest(".job-remove-btn")) return;
      snsSelectJob(el.dataset.id);
    });
  });

  // Attach remove handlers
  list.querySelectorAll(".job-remove-btn").forEach(btn => {
    btn.addEventListener("click", (e) => {
      e.stopPropagation();
      snsRemoveJob(btn.dataset.removeId);
    });
  });
}


// ── Select job & render detail ───────────────────────────────────────

async function snsSelectJob(jobId) {
  snsSelectedJob = jobId;
  snsSaveToStorage();

  // Highlight in list
  $$("#snsJobList .sns-job-item").forEach(el => {
    el.classList.toggle("selected", el.dataset.id === jobId);
  });

  const job = snsJobs.find(j => j.job_id === jobId);
  if (!job) return;

  // Lazy-load full result if needed
  if (!job.result) {
    try {
      const res = await fetch(`/api/sensor-job/${jobId}`);
      const data = await res.json();
      job.result = data.result;
      snsSaveToStorage(); // persist the full result
    } catch (err) {
      toast("Failed to load sensor data");
      return;
    }
  }

  snsRenderDetail(job);
}


function snsRenderDetail(job) {
  const r = job.result;
  const s = r.summary;
  const regs = r.register_map.registers;
  const addr = r.address;
  const main = $("#snsMain");

  // Header
  let headerHTML = `<div class="sns-detail-header">
    <h2>${s.part_number || job.filename}</h2>
    <div class="sns-specs">
      ${s.vendor_name ? `<span>🏭 ${s.vendor_name}</span>` : ""}
      ${s.sensor_type ? `<span>📡 ${s.sensor_type}</span>` : ""}
      ${addr.protocol ? `<span>🔌 ${addr.protocol.toUpperCase()}</span>` : ""}
      ${addr.i2c_addresses && addr.i2c_addresses.length ? `<span>📍 I2C: ${addr.i2c_addresses.join(", ")}</span>` : ""}
      ${addr.spi_max_freq_mhz ? `<span>⚡ SPI ${addr.spi_max_freq_mhz} MHz</span>` : ""}
      <span>📋 ${regs.length} registers</span>
    </div>
  </div>`;

  // Body
  let bodyHTML = `<div class="sns-detail-body">`;

  // ─── Description ───
  if (s.description) {
    bodyHTML += `<div class="sns-section">
      <h3>📄 Description</h3>
      <p style="font-size:12px;line-height:1.6;color:var(--fg);">${snsEsc(s.description)}</p>
    </div>`;
  }

  // ─── Address Info ───
  bodyHTML += `<div class="sns-section">
    <h3>📍 Address / Interface</h3>
    <table class="sns-reg-table" style="max-width:500px;">
      <tr><th>Property</th><th>Value</th></tr>
      <tr><td>Protocol</td><td>${addr.protocol || "unknown"}</td></tr>
      ${addr.i2c_addresses && addr.i2c_addresses.length ? `<tr><td>I2C Addresses</td><td class="addr">${addr.i2c_addresses.join(", ")}</td></tr>` : ""}
      ${addr.spi_max_freq_mhz ? `<tr><td>SPI Max Freq</td><td>${addr.spi_max_freq_mhz} MHz</td></tr>` : ""}
    </table>
  </div>`;

  // ─── Register Map ───
  if (regs.length) {
    bodyHTML += `<div class="sns-section">
      <h3>🗂 Register Map (${regs.length} registers)</h3>
      <table class="sns-reg-table">
        <thead>
          <tr>
            <th style="width:80px">Address</th>
            <th style="width:180px">Name</th>
            <th style="width:55px">Size</th>
            <th style="width:55px">Access</th>
            <th style="width:80px">Reset</th>
            <th>Description</th>
          </tr>
        </thead>
        <tbody>`;

    for (const reg of regs) {
      const rwClass = reg.access === "R" ? "rw-r" : reg.access === "W" ? "rw-w" : "rw-rw";
      bodyHTML += `<tr>
        <td class="addr">${reg.address}</td>
        <td>${snsEsc(reg.name)}</td>
        <td>${reg.size}</td>
        <td class="${rwClass}">${reg.access || "-"}</td>
        <td class="addr">${reg.reset_value || "-"}</td>
        <td style="font-family:'Segoe UI',sans-serif;font-size:11px;">${snsEsc(reg.description || "")}</td>
      </tr>`;

      // Bit-fields
      if (reg.fields && reg.fields.length) {
        for (const f of reg.fields) {
          bodyHTML += `<tr class="sns-field-row">
            <td></td>
            <td style="color:var(--mauve);">[${f.bits}] ${snsEsc(f.name)}</td>
            <td></td>
            <td class="${f.access === "R" ? "rw-r" : f.access === "W" ? "rw-w" : "rw-rw"}">${f.access || "-"}</td>
            <td class="addr">${f.reset_value || "-"}</td>
            <td style="font-family:'Segoe UI',sans-serif;">${snsEsc(f.description || "")}</td>
          </tr>`;
        }
      }
    }

    bodyHTML += `</tbody></table></div>`;
  }

  // ─── C Header Generation ───
  bodyHTML += `<div class="sns-section">
    <h3>💻 C Register Header</h3>
    <div class="sns-code-actions">
      <button class="btn" id="snsGenHeader">Generate Header</button>
      <button class="btn" id="snsCopyHeader" style="display:none;">📋 Copy</button>
      <button class="btn" id="snsGenDriver">🔧 Generate Zephyr Driver</button>
    </div>
    <div id="snsHeaderCode" class="sns-code-block" style="display:none;"></div>
  </div>`;

  // ─── Driver Generation ───
  bodyHTML += `<div class="sns-section" id="snsDriverSection" style="display:none;">
    <h3>🔧 Generated Zephyr Driver</h3>
    <div id="snsDriverFiles"></div>
  </div>`;

  bodyHTML += `</div>`;

  main.innerHTML = headerHTML + bodyHTML;

  // Wire header generation
  $("#snsGenHeader").addEventListener("click", () => snsGenerateHeader(job.job_id));
  $("#snsCopyHeader").addEventListener("click", () => snsCopyHeaderToClipboard());
  $("#snsGenDriver").addEventListener("click", () => snsGenerateDriver(job.job_id));
}


// ── Generate C header ────────────────────────────────────────────────

async function snsGenerateHeader(jobId) {
  const btn = $("#snsGenHeader");
  btn.disabled = true;
  btn.textContent = "Generating...";

  try {
    const res = await fetch(`/api/sensor-job/${jobId}/header`);
    const data = await res.json();

    if (!res.ok) {
      toast(data.error || "Header generation failed");
      return;
    }

    const codeEl = $("#snsHeaderCode");
    codeEl.textContent = data.code;
    codeEl.style.display = "block";

    const copyBtn = $("#snsCopyHeader");
    copyBtn.style.display = "inline-flex";

    toast(`Generated ${data.filename}`);
  } catch (err) {
    toast("Error: " + err.message);
  } finally {
    btn.disabled = false;
    btn.textContent = "Generate Header";
  }
}

function snsCopyHeaderToClipboard() {
  const code = $("#snsHeaderCode").textContent;
  navigator.clipboard.writeText(code).then(() => {
    toast("Header copied to clipboard");
  }).catch(() => {
    // Fallback
    const ta = document.createElement("textarea");
    ta.value = code;
    document.body.appendChild(ta);
    ta.select();
    document.execCommand("copy");
    document.body.removeChild(ta);
    toast("Header copied to clipboard");
  });
}


// ── Generate Zephyr driver ───────────────────────────────────────────

async function snsGenerateDriver(jobId) {
  const btn = $("#snsGenDriver");
  btn.disabled = true;
  btn.textContent = "Generating driver...";

  try {
    const res = await fetch(`/api/sensor-job/${jobId}/driver`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({}),
    });
    const data = await res.json();

    if (!res.ok) {
      toast(data.error || "Driver generation failed");
      return;
    }

    const section = $("#snsDriverSection");
    section.style.display = "block";

    const filesDiv = $("#snsDriverFiles");
    let html = "";

    // Show each generated file
    const fileEntries = [
      { label: "Driver Source", key: "source", ext: ".c" },
      { label: "Kconfig", key: "kconfig", ext: "" },
      { label: "CMakeLists", key: "cmake", ext: "" },
      { label: "Device Tree Binding", key: "binding", ext: ".yaml" },
      { label: "Register Header", key: "register_header", ext: ".h" },
      { label: "Register Defines", key: "register_defines", ext: ".h" },
    ];

    for (const entry of fileEntries) {
      const code = data[entry.key];
      if (!code) continue;
      html += `<div style="margin-bottom:16px;">
        <div style="font-size:12px;font-weight:600;margin-bottom:6px;color:var(--accent);">${entry.label}</div>
        <div class="sns-code-block">${snsEsc(code)}</div>
      </div>`;
    }

    filesDiv.innerHTML = html;
    toast("Zephyr driver generated successfully");
    section.scrollIntoView({ behavior: "smooth", block: "start" });
  } catch (err) {
    toast("Error: " + err.message);
  } finally {
    btn.disabled = false;
    btn.textContent = "🔧 Generate Zephyr Driver";
  }
}


// ── Sensor Identify ──────────────────────────────────────────────────

async function snsIdentifySensor() {
  const input = $("#snsPartInput");
  const resultEl = $("#snsIdResult");
  const pn = input.value.trim();

  if (!pn) {
    resultEl.textContent = "Enter a part number";
    return;
  }

  resultEl.innerHTML = "Identifying...";

  try {
    const res = await fetch("/api/identify-sensor", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ part_number: pn }),
    });
    const data = await res.json();

    if (data.known) {
      resultEl.innerHTML = `<span style="color:var(--green);">✅ ${data.vendor_name}</span> (${data.vendor})`;
    } else {
      resultEl.innerHTML = `<span style="color:var(--yellow);">⚠ Unknown vendor for "${pn}"</span>`;
    }
  } catch (err) {
    resultEl.innerHTML = `<span style="color:var(--red);">Error: ${err.message}</span>`;
  }
}


// ── Utility ──────────────────────────────────────────────────────────

function snsEsc(str) {
  if (!str) return "";
  return str.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
}
