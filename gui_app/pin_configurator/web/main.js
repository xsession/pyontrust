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
let selectedPin  = null;   // Currently selected pin number

let generatedOverlay = "";
let generatedConf    = "";
let activeTab        = "overlay";

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

// ── Board loading ────────────────────────────────────────────────────

async function loadBoardList() {
  const res = await fetch("/api/boards");
  const boards = await res.json();
  boardSelect.innerHTML = "";
  boards.forEach(b => {
    const opt = document.createElement("option");
    opt.value = b.id;
    opt.textContent = `${b.name} (${b.board})`;
    boardSelect.appendChild(opt);
  });
  if (boards.length) {
    await loadBoard(boards[0].id);
  }
}

async function loadBoard(name) {
  const res = await fetch(`/api/board/${name}`);
  boardData = await res.json();
  pinStates = {};
  periphStates = {};
  selectedPin = null;

  chipLabel.textContent = boardData.soc;
  statsLabel.textContent =
    `Flash: ${boardData.flash_size_kb}KB | SRAM: ${boardData.sram_size_kb}KB | Clock: ${(boardData.clock_hz/1e6).toFixed(0)}MHz`;

  boardData.peripherals.forEach(p => {
    periphStates[p.name] = p.enabled || false;
  });

  renderPeripherals();
  renderChip();
  renderConfigPanel();
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
        <div class="periph-toggle ${periphStates[p.name] ? 'on' : ''}"
             data-periph="${p.name}"></div>
      `;

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

function renderChip() {
  if (!boardData) return;

  const pinCount = boardData.pin_count;
  const perSide  = pinCount / 4;

  // Layout constants
  const PAD_W     = 48;   // pin pad width
  const PAD_H     = 22;   // pin pad height
  const PAD_GAP   = 6;    // gap between pads
  const LABEL_W   = 90;   // space for labels outside
  const BODY_PAD  = 8;    // gap between pads and body

  const bodyW     = perSide * (PAD_H + PAD_GAP) + 20;
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

  // Assign pins to sides
  const sides = { left: [], bottom: [], right: [], top: [] };
  boardData.pins.forEach(p => sides[p.side].push(p));

  // Render pins per side
  // LEFT: pins go top to bottom, pads extend left from body
  sides.left.forEach((pin, i) => {
    const px = bodyX - BODY_PAD - PAD_W;
    const py = bodyY + 10 + i * (PAD_H + PAD_GAP);
    renderPin(pin, px, py, PAD_W, PAD_H, "left");
  });

  // BOTTOM: pins go left to right, pads extend below body
  sides.bottom.forEach((pin, i) => {
    const px = bodyX + 10 + i * (PAD_H + PAD_GAP);
    const py = bodyY + bodyH + BODY_PAD;
    renderPin(pin, px, py, PAD_H, PAD_W, "bottom");
  });

  // RIGHT: pins go bottom to top, pads extend right from body
  sides.right.forEach((pin, i) => {
    const px = bodyX + bodyW + BODY_PAD;
    const py = bodyY + bodyH - 10 - PAD_H - i * (PAD_H + PAD_GAP);
    renderPin(pin, px, py, PAD_W, PAD_H, "right");
  });

  // TOP: pins go right to left, pads extend above body
  sides.top.forEach((pin, i) => {
    const px = bodyX + bodyW - 10 - PAD_H - i * (PAD_H + PAD_GAP);
    const py = bodyY - BODY_PAD - PAD_W;
    renderPin(pin, px, py, PAD_H, PAD_W, "top");
  });

  function renderPin(pin, x, y, w, h, side) {
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

    // Pin number
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

    // Show assigned function
    const funcLabel = state && state.af ? state.af.name : (pin.kind !== "io" ? pin.default_function : "");
    if (funcLabel) {
      const fanchor = (side === "left") ? "end" : (side === "right") ? "start" : "middle";
      svg += `<text class="pin-func" x="${funcX}" y="${funcY}" text-anchor="${fanchor}">${funcLabel}</text>`;
    }
  }

  svg += `</svg>`;
  chipContainer.innerHTML = svg;

  // Attach click handlers
  chipContainer.querySelectorAll(".pin-pad").forEach(el => {
    el.addEventListener("click", () => {
      const pinNum = parseInt(el.dataset.pin);
      selectPin(pinNum);
    });
  });
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

  if (!selectedPin || !boardData) {
    panel.innerHTML = `<div class="empty-state"><div>Click a pin to configure</div>
      <div class="hint">or enable a peripheral on the left</div></div>`;
    return;
  }

  const pin = boardData.pins.find(p => p.number === selectedPin);
  if (!pin) return;

  if (pin.kind !== "io") {
    panel.innerHTML = `<h3><span class="pin-badge">${pin.name}</span> Pin ${pin.number}</h3>
      <div class="empty-state">${pin.kind === 'power' ? 'Power pin' : pin.kind === 'ground' ? 'Ground pin' : 'Special pin'}<br>${pin.default_function}</div>`;
    return;
  }

  const state = pinStates[pin.number] || {};

  let html = `<h3><span class="pin-badge">${pin.name}</span> Pin ${pin.number}</h3>`;

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

  panel.innerHTML = html;

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
  }));

  const res = await fetch("/api/generate", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      board: boardData.board,
      assignments: assignments,
      peripherals: periphs,
    }),
  });

  const result = await res.json();
  generatedOverlay = result.overlay;
  generatedConf    = result.prj_conf;

  showOutput(activeTab);
  outputBar.classList.remove("collapsed");
  toast("Generated overlay + prj.conf");
}

// ── Output bar ───────────────────────────────────────────────────────

function showOutput(tab) {
  activeTab = tab;
  outputPre.textContent = tab === "overlay" ? generatedOverlay : generatedConf;
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

// ── Event wiring ─────────────────────────────────────────────────────

document.addEventListener("DOMContentLoaded", () => {
  loadBoardList();

  boardSelect.addEventListener("change", () => loadBoard(boardSelect.value));

  $("#btnGenerate").addEventListener("click", generateOutput);

  // Output tabs
  $$(".output-tab").forEach(tab => {
    tab.addEventListener("click", () => showOutput(tab.dataset.tab));
  });

  // Output toggle
  $("#outputToggle").addEventListener("click", () => {
    outputBar.classList.toggle("collapsed");
  });

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

  // Keyboard shortcuts
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") {
      selectedPin = null;
      renderChip();
      renderConfigPanel();
      $("#saveModal").classList.remove("show");
    }
    if ((e.ctrlKey || e.metaKey) && e.key === "g") {
      e.preventDefault();
      generateOutput();
    }
  });
});
