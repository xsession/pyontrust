"use strict";
// ═══════════════════════════════════════════════════════════════════════════
//  BaramFlow Web — main.js
//  Single-file vanilla JS frontend (no build step, no framework)
//  Convention: each UI module uses a 3-letter prefix for all its functions.
// ═══════════════════════════════════════════════════════════════════════════

// ── DOM helpers ──────────────────────────────────────────────────────────
const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => [...document.querySelectorAll(sel)];

let _toastTimer = null;
function toast(msg, ms = 3000) {
  const el = $("#toast");
  el.textContent = msg;
  el.classList.add("show");
  clearTimeout(_toastTimer);
  _toastTimer = setTimeout(() => el.classList.remove("show"), ms);
}

function showModal(id) { $("#" + id).classList.add("show"); }
function closeModal(id) { $("#" + id).classList.remove("show"); }

async function apiFetch(url, opts = {}) {
  try {
    const r = await fetch(url, opts);
    const d = await r.json();
    if (!r.ok) {
      toast("⚠️ " + (d.error || `HTTP ${r.status}`));
      return null;
    }
    return d;
  } catch (e) {
    toast("❌ Network error: " + e.message);
    return null;
  }
}

async function apiPost(url, body) {
  return apiFetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

async function apiPut(url, body) {
  return apiFetch(url, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

// ═══════════════════════════════════════════════════════════════════════════
//  prj* — Project Manager  (replaces start_window.py + App singleton)
// ═══════════════════════════════════════════════════════════════════════════

let prjData = null; // current project summary

async function prjInit() {
  const d = await apiFetch("/api/project");
  if (d) {
    prjData = d;
    prjUpdateUI();
    navSelect("general");
  }
}

function prjUpdateUI() {
  if (prjData) {
    $("#projectName").textContent = prjData.name || prjData.path;
  } else {
    $("#projectName").textContent = "No project open";
  }
}

function prjOpenDialog() {
  $("#projectModalTitle").textContent = "Open Project";
  $("#projectActionBtn").textContent = "Open";
  $("#projectActionBtn").onclick = prjDoOpen;
  $("#projectPathInput").value = "";
  prjLoadRecent();
  showModal("projectModal");
}

function prjNewDialog() {
  $("#projectModalTitle").textContent = "New Project";
  $("#projectActionBtn").textContent = "Create";
  $("#projectActionBtn").onclick = prjDoNew;
  $("#projectPathInput").value = "";
  showModal("projectModal");
}

async function prjDoOpen() {
  const path = $("#projectPathInput").value.trim();
  if (!path) { toast("⚠️ Enter a project path"); return; }
  const d = await apiPost("/api/project/open", { path });
  if (d) {
    prjData = d;
    prjUpdateUI();
    closeModal("projectModal");
    toast("✅ Project opened: " + d.name);
    navSelect("general");
  }
}

async function prjDoNew() {
  const path = $("#projectPathInput").value.trim();
  if (!path) { toast("⚠️ Enter a project path"); return; }
  const d = await apiPost("/api/project/new", { path });
  if (d) {
    prjData = d;
    prjUpdateUI();
    closeModal("projectModal");
    toast("✅ Project created: " + d.name);
    navSelect("general");
  }
}

async function prjSave() {
  const d = await apiPost("/api/project/save", {});
  if (d && d.success) toast("✅ Project saved");
}

async function prjLoadRecent() {
  const list = await apiFetch("/api/project/recent");
  const el = $("#recentProjectsList");
  if (!list || !list.length) { el.innerHTML = '<div class="text-dim">No recent projects</div>'; return; }
  el.innerHTML = '<label style="font-size:12px;font-weight:600;color:var(--fg-dim)">Recent Projects</label>' +
    list.map(p => `<div class="nav-item" onclick="document.getElementById('projectPathInput').value='${p.replace(/\\/g, "\\\\")}'">${p}</div>`).join("");
}


// ═══════════════════════════════════════════════════════════════════════════
//  nav* — Navigator  (replaces NavigatorView + QStackedWidget)
// ═══════════════════════════════════════════════════════════════════════════

let navCurrentPage = null;

// Map page names → load+render functions
const NAV_PAGES = {
  "general":              { load: genLoad, render: genRender },
  "models":               { load: mdlLoad, render: mdlRender },
  "materials":            { load: matLoad, render: matRender },
  "cell-zones":           { load: cznLoad, render: cznRender },
  "boundary-conditions":  { load: bcsLoad, render: bcsRender },
  "numerical":            { load: numLoad, render: numRender },
  "monitors":             { load: monLoad, render: monRender },
  "initialization":       { load: iniLoad, render: iniRender },
  "run-conditions":       { load: rcoLoad, render: rcoRender },
  "run":                  { load: slvLoad, render: slvRender },
  "heat-sources":         { load: hsrcLoad, render: hsrcRender },
  "fans":                 { load: fansLoad, render: fansRender },
};

// FloEFD-style tree definition
const NAV_TREE = [
  { id: "project-root", label: "Project", icon: "📁", page: null, expanded: true, children: [
    { id: "input-data", label: "Input Data", icon: "📂", page: null, expanded: true, children: [
      { id: "general", label: "General Settings", icon: "⚙️", page: "general" },
      { id: "comp-domain", label: "Computational Domain", icon: "📦", page: "cell-zones" },
      { id: "fluid-subdomains", label: "Fluid Subdomains", icon: "💧", page: "materials" },
      { id: "solid-materials", label: "Solid Materials", icon: "🧱", page: null, expanded: false, children: [] },
      { id: "boundary-conditions", label: "Boundary Conditions", icon: "🔲", page: "boundary-conditions" },
      { id: "heat-sources", label: "Heat Sources", icon: "🔥", page: "heat-sources", expanded: false, children: [] },
      { id: "fans", label: "Fans", icon: "🌀", page: "fans", expanded: false, children: [] },
      { id: "radiative-surfaces", label: "Radiative Surfaces", icon: "☀️", page: null, expanded: false, children: [] },
      { id: "contact-resistances", label: "Contact Resistances", icon: "🔗", page: null, expanded: false, children: [] },
      { id: "goals", label: "Goals", icon: "🎯", page: "monitors" },
    ]},
    { id: "models", label: "Models", icon: "📐", page: "models" },
    { id: "mesh-group", label: "Mesh", icon: "🔷", page: null, expanded: false, children: [
      { id: "global-mesh", label: "Global Mesh", icon: "🌐", page: null },
    ]},
    { id: "numerical", label: "Numerical Conditions", icon: "🔢", page: "numerical" },
  ]},
  { id: "solution-group", label: "Solution", icon: "▶️", page: null, expanded: true, children: [
    { id: "initialization", label: "Initialization", icon: "🎯", page: "initialization" },
    { id: "run-conditions", label: "Run Conditions", icon: "⏱️", page: "run-conditions" },
    { id: "run", label: "Run / Solve", icon: "▶️", page: "run" },
  ]},
  { id: "results", label: "Results (Not loaded)", icon: "📊", page: null },
];

function navInit() {
  navBuildTree();
}

function navBuildTree() {
  const root = $("#flowTree");
  if (!root) return;
  root.innerHTML = _navRenderNodes(NAV_TREE, 0);
  // Attach click handlers
  root.querySelectorAll(".tree-node").forEach(el => {
    el.addEventListener("click", (e) => {
      e.stopPropagation();
      const page = el.dataset.page;
      const nodeId = el.dataset.nodeId;
      // Toggle expand/collapse if has children
      const childUl = el.nextElementSibling;
      if (childUl && childUl.classList.contains("tree-children")) {
        const toggle = el.querySelector(".tree-toggle");
        if (childUl.classList.contains("collapsed")) {
          childUl.classList.remove("collapsed");
          if (toggle) toggle.textContent = "▼";
        } else {
          childUl.classList.add("collapsed");
          if (toggle) toggle.textContent = "▶";
        }
      }
      if (page && page !== "null") navSelect(page, el);
    });
  });
}

function _navRenderNodes(nodes, depth) {
  return nodes.map(n => {
    const hasKids = n.children && n.children.length > 0;
    const toggleIcon = hasKids ? (n.expanded !== false ? "▼" : "▶") : "";
    const collapsed = hasKids && n.expanded === false ? " collapsed" : "";
    const pad = 4 + depth * 4;
    let html = `<li>`;
    html += `<div class="tree-node" data-page="${n.page||''}" data-node-id="${n.id}" style="padding-left:${pad}px">`;
    html += `<span class="tree-toggle">${toggleIcon}</span>`;
    html += `<span class="tree-icon">${n.icon||''}</span>`;
    html += `<span class="tree-label">${n.label}</span>`;
    html += `</div>`;
    if (hasKids) {
      html += `<ul class="tree-children${collapsed}">${_navRenderNodes(n.children, depth+1)}</ul>`;
    }
    html += `</li>`;
    return html;
  }).join("");
}

async function navSelect(page, clickedEl) {
  if (!prjData && page !== "general") {
    toast("⚠️ Open a project first");
    return;
  }
  navCurrentPage = page;

  // Highlight active tree node
  $$("#flowTree .tree-node").forEach(el => el.classList.remove("active"));
  if (clickedEl) {
    clickedEl.classList.add("active");
  } else {
    // Find node by page name
    const n = $(`#flowTree .tree-node[data-page="${page}"]`);
    if (n) n.classList.add("active");
  }

  const handler = NAV_PAGES[page];
  if (handler) {
    $("#pageContent").innerHTML = '<div style="padding:40px;text-align:center"><div class="spinner"></div></div>';
    await handler.load();
    handler.render();
  } else {
    $("#pageContent").innerHTML = `<div class="page-header">${page}</div><p class="text-dim">Page not yet implemented.</p>`;
  }
}


// ═══════════════════════════════════════════════════════════════════════════
//  gen* — General Page  (replaces GeneralPage .ui + .py)
// ═══════════════════════════════════════════════════════════════════════════

let genData = {};

async function genLoad() {
  if (!prjData) return;
  genData = await apiFetch("/api/pages/general") || {};
}

function genRender() {
  const d = genData;
  $("#pageContent").innerHTML = `
    <div class="page-header">General</div>

    <div class="form-section">
      <label>Solver Type</label>
      <select id="genSolverType">
        <option value="pressureBased" ${d.solver_type === "pressureBased" ? "selected" : ""}>Pressure-Based</option>
        <option value="densityBased" ${d.solver_type === "densityBased" ? "selected" : ""}>Density-Based</option>
      </select>
    </div>

    <div class="form-section">
      <label>Time</label>
      <div class="radio-group">
        <label><input type="radio" name="genTime" value="false" ${!d.time_transient ? "checked" : ""}> Steady</label>
        <label><input type="radio" name="genTime" value="true" ${d.time_transient ? "checked" : ""}> Transient</label>
      </div>
    </div>

    <div class="form-section">
      <label>Flow Type</label>
      <select id="genFlowType">
        <option value="incompressible" ${d.flow_type === "incompressible" ? "selected" : ""}>Incompressible</option>
        <option value="compressible" ${d.flow_type === "compressible" ? "selected" : ""}>Compressible</option>
      </select>
    </div>

    <div class="form-section">
      <label>Gravity (m/s²)</label>
      <div class="input-row">
        <input type="number" id="genGravX" value="${d.gravity?.[0] ?? 0}" step="any" placeholder="X">
        <input type="number" id="genGravY" value="${d.gravity?.[1] ?? 0}" step="any" placeholder="Y">
        <input type="number" id="genGravZ" value="${d.gravity?.[2] ?? -9.81}" step="any" placeholder="Z">
      </div>
    </div>

    <div class="form-section">
      <label>Operating Pressure (Pa)</label>
      <input type="number" id="genOpPressure" value="${d.operating_pressure ?? 101325}" step="any">
    </div>

    <div class="btn-row">
      <button class="btn btn-accent" onclick="genSave()">Save</button>
    </div>
  `;
}

async function genSave() {
  const body = {
    solver_type: $("#genSolverType").value,
    time_transient: $('input[name="genTime"]:checked').value === "true",
    flow_type: $("#genFlowType").value,
    gravity: [
      parseFloat($("#genGravX").value),
      parseFloat($("#genGravY").value),
      parseFloat($("#genGravZ").value),
    ],
    operating_pressure: parseFloat($("#genOpPressure").value),
  };
  const d = await apiPut("/api/pages/general", body);
  if (d && d.success) toast("✅ General settings saved");
}


// ═══════════════════════════════════════════════════════════════════════════
//  mdl* — Models Page  (replaces ModelsPage .ui + .py)
// ═══════════════════════════════════════════════════════════════════════════

let mdlData = {};

async function mdlLoad() {
  mdlData = await apiFetch("/api/pages/models") || {};
}

function mdlRender() {
  const d = mdlData;
  $("#pageContent").innerHTML = `
    <div class="page-header">Models</div>

    <div class="form-section">
      <label>Multiphase</label>
      <select id="mdlMultiphase">
        <option value="off" ${d.multiphase_model === "off" ? "selected" : ""}>Off</option>
        <option value="volumeOfFluid" ${d.multiphase_model === "volumeOfFluid" ? "selected" : ""}>Volume of Fluid</option>
      </select>
    </div>

    <div class="form-section">
      <label>Energy</label>
      <div class="checkbox-row">
        <input type="checkbox" id="mdlEnergy" ${d.energy_model ? "checked" : ""}>
        <span>Include energy equation</span>
      </div>
    </div>

    <div class="form-section">
      <label>Species Transport</label>
      <select id="mdlSpecies">
        <option value="off" ${d.species_model === "off" ? "selected" : ""}>Off</option>
        <option value="on" ${d.species_model !== "off" ? "selected" : ""}>On</option>
      </select>
    </div>

    <div class="btn-row">
      <button class="btn btn-accent" onclick="mdlSave()">Save</button>
    </div>
  `;
}

async function mdlSave() {
  const body = {
    multiphase_model: $("#mdlMultiphase").value,
    energy_model: $("#mdlEnergy").checked,
    species_model: $("#mdlSpecies").value,
  };
  const d = await apiPut("/api/pages/models", body);
  if (d && d.success) toast("✅ Models saved");
}


// ═══════════════════════════════════════════════════════════════════════════
//  mat* — Materials Page  (replaces MaterialPage .ui + .py)
// ═══════════════════════════════════════════════════════════════════════════

let matList = [];

async function matLoad() {
  matList = await apiFetch("/api/pages/materials") || [];
}

function matRender() {
  let rows = matList.map(m => `
    <tr>
      <td>${m.mid}</td>
      <td>${m.name}</td>
      <td>${m.phase || "—"}</td>
      <td>${m.type || "—"}</td>
      <td>${m.formula || "—"}</td>
    </tr>
  `).join("");

  if (!rows) rows = '<tr><td colspan="5" class="text-dim">No materials defined</td></tr>';

  $("#pageContent").innerHTML = `
    <div class="page-header">Materials</div>
    <table class="data-table">
      <thead><tr><th>ID</th><th>Name</th><th>Phase</th><th>Type</th><th>Formula</th></tr></thead>
      <tbody>${rows}</tbody>
    </table>
  `;
}


// ═══════════════════════════════════════════════════════════════════════════
//  czn* — Cell Zone Conditions  (placeholder)
// ═══════════════════════════════════════════════════════════════════════════

let cznData = {};
async function cznLoad() { /* TODO: GET /api/pages/cell-zones */ }
function cznRender() {
  $("#pageContent").innerHTML = `
    <div class="page-header">Cell Zone Conditions</div>
    <p class="text-dim">Cell zone configuration will appear here once a mesh is loaded.</p>
  `;
}


// ═══════════════════════════════════════════════════════════════════════════
//  bcs* — Boundary Conditions  (replaces BoundaryConditionsPage + 31 dialogs)
// ═══════════════════════════════════════════════════════════════════════════

let bcsList = [];
let bcsSelectedId = null;

async function bcsLoad() {
  bcsList = await apiFetch("/api/boundary-conditions") || [];
}

function bcsRender() {
  let rows = bcsList.map(bc => `
    <tr class="${bc.bcid === bcsSelectedId ? "selected" : ""}"
        onclick="bcsSelect('${bc.bcid}')">
      <td>${bc.bcid}</td>
      <td>${bc.name}</td>
      <td>${bc.type}</td>
      <td>${bc.region}</td>
      <td><button class="btn" style="padding:2px 8px;font-size:11px" onclick="event.stopPropagation();bcsEdit('${bc.bcid}')">Edit</button></td>
    </tr>
  `).join("");

  if (!rows) rows = '<tr><td colspan="5" class="text-dim">No boundary conditions</td></tr>';

  $("#pageContent").innerHTML = `
    <div class="page-header">Boundary Conditions</div>
    <table class="data-table">
      <thead><tr><th>ID</th><th>Name</th><th>Type</th><th>Region</th><th></th></tr></thead>
      <tbody>${rows}</tbody>
    </table>
  `;
}

function bcsSelect(bcid) {
  bcsSelectedId = bcid;
  bcsRender();
}

async function bcsEdit(bcid) {
  const detail = await apiFetch(`/api/boundary-conditions/${bcid}`);
  if (!detail) return;

  const body = $("#bcEditBody");
  body.innerHTML = `
    <div class="form-section">
      <label>Name</label>
      <input type="text" id="bcEditName" value="${detail.name}" disabled>
    </div>
    <div class="form-section">
      <label>Physical Type</label>
      <select id="bcEditType">
        ${_BC_TYPES.map(t => `<option value="${t}" ${t === detail.physical_type ? "selected" : ""}>${t}</option>`).join("")}
      </select>
    </div>
    <div class="form-section">
      <label>Type-Specific Data</label>
      <pre style="background:var(--bg);padding:10px;border-radius:var(--radius);font-size:11px;overflow:auto;max-height:300px">${JSON.stringify(detail.type_data, null, 2)}</pre>
    </div>
  `;
  bcsSelectedId = bcid;
  showModal("bcEditModal");
}

async function bcsSave() {
  // Collect writes from the modal and PUT
  closeModal("bcEditModal");
  toast("✅ Boundary condition updated (stub — implement per-type fields)");
}

const _BC_TYPES = [
  "velocityInlet","flowRateInlet","pressureInlet","intakeFan","ablInlet",
  "openChannelInlet","freeStream","farFieldRiemann","subsonicInlet","supersonicInflow",
  "flowRateOutlet","pressureOutlet","exhaustFan","openChannelOutlet","outflow",
  "subsonicOutflow","supersonicOutflow",
  "wall","thermoCoupledWall","porousJump","fan",
  "symmetry","interface","empty","cyclic","wedge",
];


// ═══════════════════════════════════════════════════════════════════════════
//  num* — Numerical Conditions  (replaces NumericalConditionsPage)
// ═══════════════════════════════════════════════════════════════════════════

let numData = {};

async function numLoad() {
  numData = await apiFetch("/api/pages/numerical") || {};
}

function numRender() {
  const d = numData;
  $("#pageContent").innerHTML = `
    <div class="page-header">Numerical Conditions</div>

    <div class="form-section">
      <label>Pressure-Velocity Coupling</label>
      <select id="numPVCoupling">
        <option value="SIMPLE" ${d.pressure_velocity_coupling === "SIMPLE" ? "selected" : ""}>SIMPLE</option>
        <option value="SIMPLEC" ${d.pressure_velocity_coupling === "SIMPLEC" ? "selected" : ""}>SIMPLEC</option>
      </select>
    </div>

    <div class="form-section">
      <label>Momentum Discretization</label>
      <select id="numMomentum">
        <option value="firstOrderUpwind" ${d.discretization_momentum === "firstOrderUpwind" ? "selected" : ""}>First Order Upwind</option>
        <option value="secondOrderUpwind" ${d.discretization_momentum === "secondOrderUpwind" ? "selected" : ""}>Second Order Upwind</option>
      </select>
    </div>

    <div class="form-section">
      <label>Under-Relaxation: Pressure</label>
      <input type="number" id="numURPressure" value="${d.under_relaxation_pressure ?? 0.3}" step="0.01" min="0" max="1">
    </div>

    <div class="form-section">
      <label>Under-Relaxation: Momentum</label>
      <input type="number" id="numURMomentum" value="${d.under_relaxation_momentum ?? 0.7}" step="0.01" min="0" max="1">
    </div>

    <div class="form-section">
      <label>Max Iterations Per Time Step</label>
      <input type="number" id="numMaxIter" value="${d.max_iterations_per_step ?? 20}" step="1" min="1">
    </div>

    <div class="btn-row">
      <button class="btn btn-accent" onclick="numSave()">Save</button>
    </div>
  `;
}

async function numSave() {
  const body = {
    pressureVelocityCouplingScheme: $("#numPVCoupling").value,
    "discretizationSchemes/momentum": $("#numMomentum").value,
    "underRelaxationFactors/pressure": parseFloat($("#numURPressure").value),
    "underRelaxationFactors/momentum": parseFloat($("#numURMomentum").value),
    maxIterationsPerTimeStep: parseInt($("#numMaxIter").value),
  };
  const d = await apiPut("/api/pages/numerical", body);
  if (d && d.success) toast("✅ Numerical conditions saved");
}


// ═══════════════════════════════════════════════════════════════════════════
//  mon* — Monitors  (replaces MonitorPage)
// ═══════════════════════════════════════════════════════════════════════════

let monData = {};

async function monLoad() {
  monData = await apiFetch("/api/monitors") || {};
}

function monRender() {
  const all = [
    ...(monData.force_monitors || []).map(m => ({...m, category: "Force"})),
    ...(monData.point_monitors || []).map(m => ({...m, category: "Point"})),
    ...(monData.surface_monitors || []).map(m => ({...m, category: "Surface"})),
    ...(monData.volume_monitors || []).map(m => ({...m, category: "Volume"})),
  ];

  let rows = all.map(m => `
    <tr><td>${m.category}</td><td>${m.name}</td></tr>
  `).join("");

  if (!rows) rows = '<tr><td colspan="2" class="text-dim">No monitors defined</td></tr>';

  $("#pageContent").innerHTML = `
    <div class="page-header">Monitors</div>
    <table class="data-table">
      <thead><tr><th>Category</th><th>Name</th></tr></thead>
      <tbody>${rows}</tbody>
    </table>
  `;
}


// ═══════════════════════════════════════════════════════════════════════════
//  ini* — Initialization  (replaces InitializationPage)
// ═══════════════════════════════════════════════════════════════════════════

let iniData = {};

async function iniLoad() {
  iniData = await apiFetch("/api/pages/initialization") || {};
}

function iniRender() {
  const regions = iniData.regions || {};
  const regionNames = Object.keys(regions);

  let html = '<div class="page-header">Initialization</div>';

  if (!regionNames.length) {
    html += '<p class="text-dim">No regions available. Load a mesh first.</p>';
  }

  for (const rname of regionNames) {
    const r = regions[rname];
    html += `
      <h3 style="margin:12px 0 8px;font-size:14px;color:var(--accent)">${rname || "Default Region"}</h3>
      <div class="form-section">
        <label>Initial Velocity (m/s)</label>
        <div class="input-row">
          <input type="number" id="iniVelX_${rname}" value="${r.velocity?.[0] ?? 0}" step="any" placeholder="X">
          <input type="number" id="iniVelY_${rname}" value="${r.velocity?.[1] ?? 0}" step="any" placeholder="Y">
          <input type="number" id="iniVelZ_${rname}" value="${r.velocity?.[2] ?? 0}" step="any" placeholder="Z">
        </div>
      </div>
      <div class="form-section">
        <label>Initial Pressure (Pa)</label>
        <input type="number" id="iniPressure_${rname}" value="${r.pressure ?? 0}" step="any">
      </div>
      <div class="form-section">
        <label>Initial Temperature (K)</label>
        <input type="number" id="iniTemp_${rname}" value="${r.temperature ?? 300}" step="any">
      </div>
    `;
  }

  html += `
    <div class="btn-row mt-16">
      <button class="btn btn-accent" onclick="iniInitialize()">🚀 Initialize Fields</button>
    </div>
  `;

  $("#pageContent").innerHTML = html;
}

async function iniInitialize() {
  toast("⏳ Initialising case…");
  const d = await apiPost("/api/solver/initialize", {});
  if (d && d.success) toast("✅ Case initialised successfully");
}


// ═══════════════════════════════════════════════════════════════════════════
//  rco* — Run Conditions  (replaces RunConditionsPage)
// ═══════════════════════════════════════════════════════════════════════════

let rcoData = {};

async function rcoLoad() {
  rcoData = await apiFetch("/api/pages/run-conditions") || {};
}

function rcoRender() {
  const d = rcoData;
  $("#pageContent").innerHTML = `
    <div class="page-header">Run Conditions</div>

    <div class="form-section">
      <label>Time Stepping Method</label>
      <select id="rcoTimeStepping">
        <option value="fixed" ${d.time_stepping_method === "fixed" ? "selected" : ""}>Fixed</option>
        <option value="adaptive" ${d.time_stepping_method === "adaptive" ? "selected" : ""}>Adaptive</option>
      </select>
    </div>

    <div class="form-section">
      <label>Time Step Size / Number of Iterations</label>
      <input type="number" id="rcoTimeStep" value="${d.time_step_size || d.num_iterations || 1000}" step="any">
    </div>

    <div class="form-section">
      <label>End Time / Total Iterations</label>
      <input type="number" id="rcoEndTime" value="${d.end_time || d.num_iterations || 1000}" step="any">
    </div>

    <div class="form-section">
      <label>Report Interval (steps)</label>
      <input type="number" id="rcoReportInterval" value="${d.report_interval ?? 1}" step="1" min="1">
    </div>

    <div class="form-section">
      <label>Save Interval (steps)</label>
      <input type="number" id="rcoSaveInterval" value="${d.save_interval ?? 100}" step="1" min="1">
    </div>

    <div class="form-section">
      <label>Data Write Format</label>
      <select id="rcoWriteFormat">
        <option value="binary" ${d.data_write_format === "binary" ? "selected" : ""}>Binary</option>
        <option value="ascii" ${d.data_write_format === "ascii" ? "selected" : ""}>ASCII</option>
      </select>
    </div>

    <div class="btn-row">
      <button class="btn btn-accent" onclick="rcoSave()">Save</button>
    </div>
  `;
}

async function rcoSave() {
  const body = {
    timeSteppingMethod: $("#rcoTimeStepping").value,
    timeStepSize: $("#rcoTimeStep").value,
    endTime: $("#rcoEndTime").value,
    reportIntervalSteps: $("#rcoReportInterval").value,
    saveIntervalSteps: $("#rcoSaveInterval").value,
    dataWriteFormat: $("#rcoWriteFormat").value,
  };
  const d = await apiPut("/api/pages/run-conditions", body);
  if (d && d.success) toast("✅ Run conditions saved");
}


// ═══════════════════════════════════════════════════════════════════════════
//  slv* — Solver Run  (replaces ProcessInformationPage + CaseManager)
// ═══════════════════════════════════════════════════════════════════════════

let slvSocket = null;
let slvChart = null;
let slvChartData = {};  // field → [values]
let slvPollingId = null;

async function slvLoad() {}

function slvRender() {
  $("#pageContent").innerHTML = `
    <div class="page-header">Run Solver</div>

    <div class="btn-row mb-8">
      <button class="btn btn-green" onclick="slvStart()">▶ Start</button>
      <button class="btn btn-red" onclick="slvStop()">⏹ Stop</button>
      <button class="btn" onclick="slvRefreshStatus()">🔄 Refresh Status</button>
    </div>

    <div id="slvStatusInfo" class="text-dim mb-8">Click Start to run the solver.</div>

    <div class="form-section">
      <label>Solver Console (last 200 lines)</label>
    </div>
    <pre class="console-log" id="slvConsole" style="height:300px;overflow-y:auto;margin-bottom:16px"></pre>

    <div class="form-section">
      <label>Residual Plot</label>
    </div>
    <div style="height:280px;position:relative">
      <canvas id="slvResidualChart"></canvas>
    </div>
  `;

  slvInitChart();
}

async function slvStart() {
  toast("⏳ Starting solver…");
  const d = await apiPost("/api/solver/start", {});
  if (d && d.status === "running") {
    toast("✅ Solver started (PID " + d.pid + ")");
    slvUpdateBadge("running");
    slvConnectWebSocket();
    slvStartPolling();
  }
}

async function slvStop() {
  const d = await apiPost("/api/solver/stop", {});
  if (d) {
    toast("⏹ Solver stopped");
    slvUpdateBadge("idle");
    slvStopPolling();
    if (slvSocket) { slvSocket.close(); slvSocket = null; }
  }
}

async function slvRefreshStatus() {
  const d = await apiFetch("/api/solver/status");
  if (d) {
    const el = $("#slvStatusInfo");
    if (el) el.textContent = `State: ${d.state}  |  Iteration: ${d.iteration}  |  PID: ${d.pid || "—"}`;
    slvUpdateBadge(d.state);
  }
}

function slvUpdateBadge(state) {
  const badge = $("#solverStatus");
  badge.textContent = state.toUpperCase();
  badge.className = "status-badge " + state;
}

function slvConnectWebSocket() {
  if (slvSocket) { slvSocket.close(); slvSocket = null; }
  const proto = location.protocol === "https:" ? "wss:" : "ws:";
  try {
    slvSocket = new WebSocket(`${proto}//${location.host}/ws/solver-log`);
  } catch (e) {
    console.warn("WebSocket not available, falling back to polling");
    return;
  }
  slvSocket.onmessage = (e) => {
    const msg = JSON.parse(e.data);
    if (msg.type === "log") {
      slvAppendConsole(msg.text);
      slvParseResidual(msg.text);
    } else if (msg.type === "end") {
      slvUpdateBadge(msg.state);
      slvStopPolling();
    }
  };
  slvSocket.onerror = () => console.warn("WebSocket error");
  slvSocket.onclose = () => { slvSocket = null; };
}

function slvAppendConsole(line) {
  const el = $("#slvConsole");
  if (!el) return;
  el.textContent += line + "\n";
  // Keep only last 200 lines
  const lines = el.textContent.split("\n");
  if (lines.length > 200) {
    el.textContent = lines.slice(-200).join("\n");
  }
  el.scrollTop = el.scrollHeight;
}

function slvParseResidual(line) {
  const m = line.match(/Solving for (\w+),\s+Initial residual = ([0-9.eE+-]+)/);
  if (!m) return;
  const field = m[1];
  const value = parseFloat(m[2]);
  if (!slvChartData[field]) slvChartData[field] = [];
  slvChartData[field].push(value);
  slvUpdateChart();
}

function slvInitChart() {
  const canvas = $("#slvResidualChart");
  if (!canvas || typeof Chart === "undefined") return;
  slvChartData = {};
  slvChart = new Chart(canvas, {
    type: "line",
    data: { labels: [], datasets: [] },
    options: {
      responsive: true, maintainAspectRatio: false,
      animation: false,
      scales: {
        y: {
          type: "logarithmic",
          title: { display: true, text: "Initial Residual", color: "#6c7086" },
          ticks: { color: "#6c7086" }, grid: { color: "#313244" },
        },
        x: {
          title: { display: true, text: "Sample", color: "#6c7086" },
          ticks: { color: "#6c7086" }, grid: { color: "#313244" },
        },
      },
      plugins: { legend: { labels: { color: "#cdd6f4" } } },
    },
  });
}

const _CHART_COLORS = ["#89b4fa","#a6e3a1","#f38ba8","#f9e2af","#fab387","#cba6f7","#94e2d5","#f5c2e7"];

function slvUpdateChart() {
  if (!slvChart) return;
  const fields = Object.keys(slvChartData);
  const maxLen = Math.max(...fields.map(f => slvChartData[f].length));
  slvChart.data.labels = Array.from({ length: maxLen }, (_, i) => i + 1);
  slvChart.data.datasets = fields.map((f, i) => ({
    label: f,
    data: slvChartData[f],
    borderColor: _CHART_COLORS[i % _CHART_COLORS.length],
    backgroundColor: "transparent",
    borderWidth: 1.5,
    pointRadius: 0,
  }));
  slvChart.update();
}

function slvStartPolling() {
  slvStopPolling();
  slvPollingId = setInterval(slvRefreshStatus, 3000);
}
function slvStopPolling() {
  if (slvPollingId) { clearInterval(slvPollingId); slvPollingId = null; }
}


// ═══════════════════════════════════════════════════════════════════════════
//  msh* — Mesh  (replaces BaramMesh views)
// ═══════════════════════════════════════════════════════════════════════════

// ── Import from local path (file or folder) ──────────────────────────────
async function mshImportPath() {
  const path = $("#mshPathInput").value.trim();
  if (!path) { toast("⚠️ Enter a file or folder path"); return; }
  toast("⏳ Importing from " + path + "…");
  const d = await apiPost("/api/mesh/import-path", { path });
  if (d && d.count) {
    toast(`✅ Imported ${d.count} file(s)`);
    mshLoadGeometries();
  }
}

// ── Browser file-picker upload (fallback) ────────────────────────────────
function mshUploadClick() {
  const input = $("#meshFileInput");
  input.onchange = async () => {
    if (!input.files.length) return;
    let ok = 0;
    for (const file of input.files) {
      const fd = new FormData();
      fd.append("file", file);
      toast("⏳ Uploading " + file.name + "…");
      const r = await fetch("/api/mesh/upload", { method: "POST", body: fd });
      const d = await r.json();
      if (!d.error) ok++;
    }
    toast(`✅ Uploaded ${ok} file(s)`);
    mshLoadGeometries();
    input.value = "";  // reset so same file can be re-selected
  };
  input.click();
}

// ── Geometry list with delete ────────────────────────────────────────────
async function mshLoadGeometries() {
  const list = await apiFetch("/api/mesh/geometries") || [];
  const el = $("#meshGeometryList");
  if (!el) return;
  if (!list.length) {
    el.innerHTML = '<p class="text-dim">No geometries imported yet.</p>';
    return;
  }
  el.innerHTML = `
    <label style="font-size:12px;font-weight:600;color:var(--fg-dim)">Imported Geometries (${list.length})</label>
    <table class="data-table">
      <thead><tr><th>File</th><th>Size</th><th></th></tr></thead>
      <tbody>
        ${list.map(f => `<tr>
          <td>${f.name}</td>
          <td>${(f.size/1024).toFixed(1)} KB</td>
          <td><button class="btn" style="padding:1px 6px;font-size:11px;color:var(--red)"
                onclick="mshDelete('${f.name.replace(/'/g,"\\'")}')">✕</button></td>
        </tr>`).join("")}
      </tbody>
    </table>
  `;
}

async function mshDelete(name) {
  const d = await apiFetch(`/api/mesh/geometries/${encodeURIComponent(name)}`, { method: "DELETE" });
  if (d) { toast("🗑 Deleted"); mshLoadGeometries(); }
}

// ── File / folder browser ────────────────────────────────────────────────
let _browseCwd = "";
let _browseSelected = "";

function mshBrowseOpen() {
  _browseSelected = "";
  const startPath = $("#mshPathInput").value.trim() || "";
  mshBrowseGo(startPath);
  showModal("browseModal");
}

async function mshBrowseGo(path) {
  const params = new URLSearchParams({ path, filter: ".stl,.step,.stp,.iges,.igs,.brep,.brp,.obj" });
  const d = await apiFetch("/api/browse?" + params);
  if (!d) return;
  _browseCwd = d.path;
  $("#browseCwdInput").value = d.path;
  $("#browseTitle").textContent = "Browse — " + d.path;

  const el = $("#browseEntries");
  if (!d.entries.length) {
    el.innerHTML = '<p class="text-dim" style="padding:20px">Empty directory</p>';
    return;
  }
  el.innerHTML = d.entries.map(e => {
    const icon = e.is_dir ? "📁" : (e.match ? "📄" : "📃");
    const cls = e.is_dir ? "browse-dir" : (e.match ? "browse-file match" : "browse-file");
    const size = e.is_dir ? "" : `<span style="color:var(--fg-dim);font-size:11px;margin-left:auto">${(e.size/1024).toFixed(1)} KB</span>`;
    return `<div class="browse-entry ${cls}" data-path="${e.path.replace(/"/g,'&quot;')}" data-isdir="${e.is_dir}"
                onclick="mshBrowseClick(this)" ondblclick="mshBrowseDblClick(this)"
                style="display:flex;align-items:center;gap:6px;padding:4px 8px;cursor:pointer;border-radius:var(--radius);
                       ${e.match ? 'color:var(--accent);font-weight:600' : ''}">
      <span>${icon}</span><span style="flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${e.name}</span>${size}
    </div>`;
  }).join("");
}

function mshBrowseUp() {
  // Go to parent
  const parts = _browseCwd.replace(/\\/g, "/").replace(/\/$/, "").split("/");
  if (parts.length > 1) {
    parts.pop();
    mshBrowseGo(parts.join("/") || "/");
  }
}

function mshBrowseClick(el) {
  // Single click — highlight
  $$("#browseEntries .browse-entry").forEach(e => e.style.background = "");
  el.style.background = "var(--surface1)";
  _browseSelected = el.dataset.path;
}

function mshBrowseDblClick(el) {
  if (el.dataset.isdir === "true") {
    mshBrowseGo(el.dataset.path);
  } else {
    _browseSelected = el.dataset.path;
    mshBrowseSelect();
  }
}

function mshBrowseSelect() {
  if (!_browseSelected && _browseCwd) _browseSelected = _browseCwd;
  if (_browseSelected) {
    $("#mshPathInput").value = _browseSelected;
  }
  closeModal("browseModal");
}


// ═══════════════════════════════════════════════════════════════════════════
//  hsrc* — Heat Sources Page
// ═══════════════════════════════════════════════════════════════════════════

let hsrcList = [];

async function hsrcLoad() {
  const d = await apiFetch("/api/heat-sources");
  if (d) hsrcList = d;
}

function hsrcRender() {
  const el = $("#pageContent");
  const rows = hsrcList.map((h, i) =>
    `<tr class="${i === 0 ? 'selected' : ''}">
      <td>${h.name || 'Heat Source ' + (i+1)}</td>
      <td>${h.type || 'Volume Source'}</td>
      <td>${h.value || 0} ${h.unit || 'W'}</td>
    </tr>`
  ).join("") || '<tr><td colspan="3" class="text-dim">No heat sources defined</td></tr>';

  el.innerHTML = `
    <div class="page-header">🔥 Heat Sources</div>
    <p class="text-dim mb-8">Define volumetric or surface heat sources. Use the Engineering Database to browse pre-defined heat generation rates.</p>
    <div class="btn-row mb-8">
      <button class="btn btn-accent" onclick="hsrcAdd()">➕ Add Heat Source</button>
      <button class="btn" onclick="hsrcRemove()">🗑 Remove</button>
      <button class="btn" onclick="engDbOpen('Heat Sources')">📚 Engineering DB</button>
    </div>
    <table class="data-table">
      <thead><tr><th>Name</th><th>Type</th><th>Value</th></tr></thead>
      <tbody>${rows}</tbody>
    </table>

    <div class="form-section mt-16">
      <label>Heat Source Type</label>
      <select id="hsrcType" style="width:240px">
        <option value="volumeRate" selected>Volume Heat Generation Rate (W/m³)</option>
        <option value="totalPower">Total Power (W)</option>
        <option value="surfaceFlux">Surface Heat Flux (W/m²)</option>
        <option value="temperatureSource">Temperature Source (K)</option>
      </select>
    </div>
    <div class="form-section">
      <label>Value</label>
      <div class="input-row">
        <input type="number" id="hsrcValue" value="0" step="any" style="width:180px">
        <span style="font-size:12px;color:var(--fg-dim);align-self:center" id="hsrcUnit">W/m³</span>
      </div>
    </div>
    <div class="form-section">
      <label>Name</label>
      <input type="text" id="hsrcName" value="VS Heat Generation Rate 1" style="width:300px">
    </div>
  `;
}

function hsrcAdd() {
  hsrcList.push({
    name: "Heat Source " + (hsrcList.length + 1),
    type: "Volume Source",
    value: 0, unit: "W/m³"
  });
  hsrcRender();
  toast("➕ Heat source added");
}

function hsrcRemove() {
  if (hsrcList.length > 0) {
    hsrcList.pop();
    hsrcRender();
    toast("🗑 Heat source removed");
  }
}


// ═══════════════════════════════════════════════════════════════════════════
//  fans* — Fans Page
// ═══════════════════════════════════════════════════════════════════════════

let fansList = [];

async function fansLoad() {
  const d = await apiFetch("/api/fans");
  if (d) fansList = d;
}

function fansRender() {
  const el = $("#pageContent");
  const rows = fansList.map((f, i) =>
    `<tr class="${i === 0 ? 'selected' : ''}">
      <td>${f.name || 'Fan ' + (i+1)}</td>
      <td>${f.type || 'Axial'}</td>
      <td>${f.flowRate || 0} ${f.unit || 'm³/s'}</td>
    </tr>`
  ).join("") || '<tr><td colspan="3" class="text-dim">No fans defined</td></tr>';

  el.innerHTML = `
    <div class="page-header">🌀 Fans</div>
    <p class="text-dim mb-8">Define fans with flow rate curves. Browse the Engineering Database for pre-defined fan curves.</p>
    <div class="btn-row mb-8">
      <button class="btn btn-accent" onclick="fansAdd()">➕ Add Fan</button>
      <button class="btn" onclick="fansRemove()">🗑 Remove</button>
      <button class="btn" onclick="engDbOpen('Fans')">📚 Engineering DB</button>
    </div>
    <table class="data-table">
      <thead><tr><th>Name</th><th>Type</th><th>Flow Rate</th></tr></thead>
      <tbody>${rows}</tbody>
    </table>

    <div class="form-section mt-16">
      <label>Fan Type</label>
      <select id="fanType" style="width:240px">
        <option value="axial">Axial Fan</option>
        <option value="centrifugal">Centrifugal Fan</option>
        <option value="external">External Fan (Curve)</option>
      </select>
    </div>
    <div class="form-section">
      <label>Max Flow Rate</label>
      <div class="input-row">
        <input type="number" id="fanFlowRate" value="0" step="any" style="width:180px">
        <span style="font-size:12px;color:var(--fg-dim);align-self:center">m³/s</span>
      </div>
    </div>
    <div class="form-section">
      <label>Max Pressure Rise</label>
      <div class="input-row">
        <input type="number" id="fanPressure" value="0" step="any" style="width:180px">
        <span style="font-size:12px;color:var(--fg-dim);align-self:center">Pa</span>
      </div>
    </div>
    <div class="form-section">
      <label>Name</label>
      <input type="text" id="fanName" value="Fan 1" style="width:300px">
    </div>
  `;
}

function fansAdd() {
  fansList.push({ name: "Fan " + (fansList.length+1), type: "Axial", flowRate: 0, unit: "m³/s" });
  fansRender();
  toast("➕ Fan added");
}

function fansRemove() {
  if (fansList.length > 0) { fansList.pop(); fansRender(); toast("🗑 Fan removed"); }
}


// ═══════════════════════════════════════════════════════════════════════════
//  engDb* — Engineering Database (FloEFD-style)
// ═══════════════════════════════════════════════════════════════════════════

const ENG_DB_TREE = [
  { id: "fans", label: "Fans", icon: "🌀", expanded: false, children: [
    { id: "fans-axial", label: "Axial", icon: "📁", items: [
      { name: "60mm Axial Fan", flowRate: 0.012, pressureRise: 25, rpm: 3000 },
      { name: "80mm Axial Fan", flowRate: 0.028, pressureRise: 40, rpm: 2500 },
      { name: "120mm Axial Fan", flowRate: 0.055, pressureRise: 55, rpm: 1800 },
      { name: "140mm Axial Fan", flowRate: 0.082, pressureRise: 70, rpm: 1500 },
      { name: "200mm Axial Fan", flowRate: 0.150, pressureRise: 100, rpm: 1200 },
    ]},
    { id: "fans-centrifugal", label: "Centrifugal", icon: "📁", items: [
      { name: "Centrifugal Blower 1", flowRate: 0.10, pressureRise: 500, rpm: 3500 },
      { name: "Centrifugal Blower 2", flowRate: 0.25, pressureRise: 800, rpm: 2800 },
    ]},
    { id: "fans-radial", label: "Radial", icon: "📁", items: [
      { name: "Radial Fan 1", flowRate: 0.05, pressureRise: 200, rpm: 4000 },
    ]},
  ]},
  { id: "heat-sinks", label: "Heat Sinks", icon: "🧊", expanded: false, children: [
    { id: "hs-pin-fin", label: "Pin Fin", icon: "📁", items: [
      { name: "40x40mm Pin Fin", baseArea: "40x40", finHeight: 25, material: "Aluminum 6063", thermalR: 3.2 },
      { name: "60x60mm Pin Fin", baseArea: "60x60", finHeight: 35, material: "Aluminum 6063", thermalR: 1.8 },
    ]},
    { id: "hs-extruded", label: "Extruded", icon: "📁", items: [
      { name: "50x50 Extruded", baseArea: "50x50", finHeight: 20, material: "Aluminum 6063", thermalR: 2.5 },
      { name: "100x50 Extruded", baseArea: "100x50", finHeight: 30, material: "Aluminum 6063", thermalR: 1.2 },
    ]},
    { id: "hs-bonded", label: "Bonded Fin", icon: "📁", items: [
      { name: "80x80 Bonded", baseArea: "80x80", finHeight: 40, material: "Copper + Aluminum", thermalR: 0.8 },
    ]},
  ]},
  { id: "leds", label: "LEDs", icon: "💡", expanded: false, children: [
    { id: "leds-smd", label: "SMD", icon: "📁", items: [
      { name: "LED 3528", power: 0.06, lumens: 8, thermalR: 250 },
      { name: "LED 5050", power: 0.18, lumens: 20, thermalR: 120 },
      { name: "LED 5630", power: 0.50, lumens: 55, thermalR: 80 },
    ]},
    { id: "leds-cob", label: "COB", icon: "📁", items: [
      { name: "COB 10W", power: 10, lumens: 1000, thermalR: 3.5 },
      { name: "COB 50W", power: 50, lumens: 5000, thermalR: 1.2 },
    ]},
  ]},
  { id: "materials", label: "Materials", icon: "🧱", expanded: false, children: [
    { id: "mat-metals", label: "Metals", icon: "📁", items: [
      { name: "Aluminum 6063", density: 2700, specificHeat: 900, conductivity: 200 },
      { name: "Copper (Pure)", density: 8960, specificHeat: 385, conductivity: 401 },
      { name: "Steel AISI 304", density: 8000, specificHeat: 500, conductivity: 16.2 },
      { name: "Brass", density: 8530, specificHeat: 380, conductivity: 110 },
      { name: "Gold", density: 19300, specificHeat: 129, conductivity: 317 },
    ]},
    { id: "mat-polymers", label: "Polymers", icon: "📁", items: [
      { name: "ABS", density: 1050, specificHeat: 1400, conductivity: 0.17 },
      { name: "Nylon 6/6", density: 1140, specificHeat: 1670, conductivity: 0.26 },
      { name: "PEEK", density: 1310, specificHeat: 320, conductivity: 0.25 },
      { name: "Polycarbonate", density: 1200, specificHeat: 1200, conductivity: 0.20 },
    ]},
    { id: "mat-ceramics", label: "Ceramics", icon: "📁", items: [
      { name: "Alumina (Al₂O₃)", density: 3900, specificHeat: 880, conductivity: 30 },
      { name: "Silicon Nitride", density: 3200, specificHeat: 700, conductivity: 30 },
    ]},
    { id: "mat-pcb", label: "PCB Materials", icon: "📁", items: [
      { name: "FR4", density: 1900, specificHeat: 600, conductivity: 0.3 },
      { name: "Solder (Sn 63%/Pb 37%)", density: 8400, specificHeat: 180, conductivity: 50 },
      { name: "Epoxy Overmold (Typical)", density: 1200, specificHeat: 1000, conductivity: 0.7 },
      { name: "Silicon", density: 2330, specificHeat: 700, conductivity: 148 },
    ]},
    { id: "mat-semiconductors", label: "Semiconductors", icon: "📁", items: [
      { name: "Silicon (Single Crystal)", density: 2330, specificHeat: 700, conductivity: 148 },
      { name: "Gallium Arsenide", density: 5320, specificHeat: 330, conductivity: 55 },
    ]},
  ]},
  { id: "pcb", label: "Printed Circuit Boards", icon: "🟩", expanded: false, children: [
    { id: "pcb-predefined", label: "Pre-Defined", icon: "📁", items: [
      { name: "2S2P", comment: "2 Signal 2 Power. Conductor - Copper. Dielectric - FR4.",
        dielectricDensity: 1200, dielectricCp: 880, dielectricK: 0.3,
        conductorDensity: 8960, conductorCp: 385, conductorK: 401,
        thickness: 0.0016, layers: 4,
        inPlaneK: 21.34, throughPlaneK: 0.317,
        effectiveDensity: 1607.4, effectiveCp: 735.14 },
    ]},
    { id: "pcb-user", label: "User Defined", icon: "📁", items: [] },
  ]},
  { id: "radiation-patterns", label: "Radiation Patterns", icon: "☀️", expanded: false, children: [] },
  { id: "radiation-spectra", label: "Radiation Spectra", icon: "🌈", expanded: false, children: [] },
  { id: "radiative-surfaces", label: "Radiative Surfaces", icon: "🔲", expanded: false, children: [] },
  { id: "thermoelectric", label: "Thermoelectric Coolers", icon: "❄️", expanded: false, children: [] },
  { id: "contact-resistance", label: "Contact Resistances", icon: "🔗", expanded: false, children: [
    { id: "cr-predefined", label: "Pre-Defined", icon: "📁", items: [
      { name: "Contact Resistance 1", value: 0.0001, unit: "m²·K/W" },
      { name: "Contact Resistance 2", value: 0.0005, unit: "m²·K/W" },
    ]},
  ]},
];

let engDbSelectedNode = null;
let engDbSelectedItem = null;

function engDbOpen(focusCategory) {
  engDbRenderTree();
  engDbSwitchTab("items");
  if (focusCategory) {
    // Auto-expand the requested category
    const node = ENG_DB_TREE.find(n => n.label === focusCategory);
    if (node) { node.expanded = true; engDbRenderTree(); engDbSelectNode(node.id); }
  } else {
    $("#engDbItems").innerHTML = '<div class="text-dim" style="padding:20px">Select a category from the tree to view items.</div>';
  }
  showModal("engDbModal");
}

function engDbRenderTree() {
  const el = $("#engDbTree");
  el.innerHTML = '<ul class="tree-root">' + _engDbRenderNodes(ENG_DB_TREE, 0) + '</ul>';
  // Attach handlers
  el.querySelectorAll(".tree-node").forEach(nd => {
    nd.addEventListener("click", (e) => {
      e.stopPropagation();
      const nid = nd.dataset.nodeId;
      // Toggle
      const childUl = nd.nextElementSibling;
      if (childUl && childUl.classList.contains("tree-children")) {
        const toggle = nd.querySelector(".tree-toggle");
        if (childUl.classList.contains("collapsed")) {
          childUl.classList.remove("collapsed");
          if (toggle) toggle.textContent = "▼";
        } else {
          childUl.classList.add("collapsed");
          if (toggle) toggle.textContent = "▶";
        }
      }
      engDbSelectNode(nid);
    });
  });
}

function _engDbRenderNodes(nodes, depth) {
  return nodes.map(n => {
    const hasKids = n.children && n.children.length > 0;
    const toggleIcon = hasKids ? (n.expanded !== false ? "▼" : "▶") : "";
    const collapsed = hasKids && n.expanded === false ? " collapsed" : "";
    const pad = 6 + depth * 12;
    let html = `<li>`;
    html += `<div class="tree-node ${engDbSelectedNode === n.id ? 'active' : ''}" data-node-id="${n.id}" style="padding-left:${pad}px">`;
    html += `<span class="tree-toggle">${toggleIcon}</span>`;
    html += `<span class="tree-icon">${n.icon||''}</span>`;
    html += `<span class="tree-label">${n.label}</span>`;
    html += `</div>`;
    if (hasKids) {
      html += `<ul class="tree-children${collapsed}">${_engDbRenderNodes(n.children, depth+1)}</ul>`;
    }
    html += `</li>`;
    return html;
  }).join("");
}

function engDbSelectNode(nodeId) {
  engDbSelectedNode = nodeId;
  // Highlight
  $$("#engDbTree .tree-node").forEach(n => n.classList.toggle("active", n.dataset.nodeId === nodeId));
  // Find node in tree
  const node = _engDbFindNode(ENG_DB_TREE, nodeId);
  if (node && node.items) {
    engDbRenderItems(node);
  } else if (node && node.children) {
    // Category level — show aggregate
    const allItems = [];
    _engDbCollectItems(node.children, allItems);
    engDbRenderItemsList(allItems, node.label);
  } else {
    $("#engDbItems").innerHTML = '<div class="text-dim" style="padding:20px">No items in this category.</div>';
    $("#engDbProperties").innerHTML = '';
    $("#engDbTables").innerHTML = '';
  }
}

function _engDbFindNode(nodes, id) {
  for (const n of nodes) {
    if (n.id === id) return n;
    if (n.children) {
      const found = _engDbFindNode(n.children, id);
      if (found) return found;
    }
  }
  return null;
}

function _engDbCollectItems(nodes, out) {
  for (const n of nodes) {
    if (n.items) out.push(...n.items);
    if (n.children) _engDbCollectItems(n.children, out);
  }
}

function engDbRenderItems(node) {
  const items = node.items || [];
  engDbRenderItemsList(items, node.label);
}

function engDbRenderItemsList(items, label) {
  const el = $("#engDbItems");
  if (items.length === 0) {
    el.innerHTML = `<div class="text-dim" style="padding:20px">No items in "${label}".</div>`;
    return;
  }
  // Get column keys from first item
  const keys = Object.keys(items[0]);
  const headerRow = keys.map(k => `<th>${k}</th>`).join("");
  const rows = items.map((item, i) => {
    const cls = i === 0 ? ' class="selected"' : '';
    const cells = keys.map(k => `<td>${item[k] ?? ''}</td>`).join("");
    return `<tr${cls} onclick="engDbClickItem(${i})" style="cursor:pointer">${cells}</tr>`;
  }).join("");

  el.innerHTML = `
    <h4 style="margin:0 0 8px;font-size:13px;color:var(--fg-dim)">${label} (${items.length} items)</h4>
    <table class="data-table"><thead><tr>${headerRow}</tr></thead><tbody>${rows}</tbody></table>
  `;
  // Auto-select first item
  engDbSelectedItem = items[0];
  engDbRenderProperties(items[0]);
}

function engDbClickItem(idx) {
  // Find current items from selected node
  const node = _engDbFindNode(ENG_DB_TREE, engDbSelectedNode);
  let items = [];
  if (node && node.items) items = node.items;
  else if (node && node.children) _engDbCollectItems(node.children, items);
  if (idx < items.length) {
    engDbSelectedItem = items[idx];
    engDbRenderProperties(items[idx]);
    // Highlight
    $$("#engDbItems tr").forEach((tr, i) => tr.classList.toggle("selected", i-1 === idx)); // -1 for header
  }
}

function engDbRenderProperties(item) {
  const el = $("#engDbProperties");
  if (!item) { el.innerHTML = ''; return; }
  const rows = Object.entries(item).map(([k, v]) =>
    `<tr><td style="width:220px;font-weight:500">${k}</td><td>${v}</td></tr>`
  ).join("");
  el.innerHTML = `
    <h4 style="margin:0 0 8px;font-size:13px;color:var(--fg-dim)">Properties: ${item.name || ''}</h4>
    <table class="param-table"><thead><tr><th>Property</th><th>Value</th></tr></thead><tbody>${rows}</tbody></table>
  `;
}

function engDbSwitchTab(tab) {
  $$(".engdb-tab").forEach(t => t.classList.toggle("active", t.dataset.engdbTab === tab));
  $$(".engdb-panel").forEach(p => p.classList.toggle("active", p.dataset.engdbPanel === tab));
  if (tab === "tables") {
    $("#engDbTables").innerHTML = '<div class="text-dim" style="padding:20px">Tables and curves view — fan curves, material property vs. temperature tables, etc.<br><br><em>Coming soon</em></div>';
  }
}

function engDbNew() { toast("📄 Create new item — not yet implemented"); }
function engDbCopy() { toast("📋 Copy item — not yet implemented"); }
function engDbSave() { toast("💾 Saved to engineering database"); }
function engDbDelete() { toast("🗑 Delete item — not yet implemented"); }


// ═══════════════════════════════════════════════════════════════════════════
//  wiz* — Project Wizard (FloEFD-style step-by-step)
// ═══════════════════════════════════════════════════════════════════════════

const WIZ_STEPS = [
  { id: "project-name",     label: "Project name",     icon: "📋", illust: "📋" },
  { id: "unit-system",      label: "Units system",     icon: "📐", illust: "📐" },
  { id: "analysis-type",    label: "Analysis type",    icon: "🌀", illust: "🌀" },
  { id: "fluids",           label: "Fluids",           icon: "💧", illust: "💧" },
  { id: "wall-conditions",  label: "Wall conditions",  icon: "🧱", illust: "🧱" },
  { id: "initial-conditions", label: "Initial conditions", icon: "🌡️", illust: "🌡️" },
  { id: "finish",           label: "Finish",           icon: "🏁", illust: "🏁" },
];

let wizStep = 0;
let wizData = {
  projectName: "Project(1)",
  projectPath: "",
  comments: "",
  configName: "Default",
  unitSystem: "SI (m-kg-s)",
  analysisType: "internal",
  excludeCavities: true,
  excludeInternalSpace: false,
  heatConduction: false,
  radiation: false,
  timeDependent: false,
  gravity: false,
  gravityX: 0,
  gravityY: -9.81,
  gravityZ: 0,
  rotation: false,
  freeSurface: false,
  selectedFluids: ["air"],
  flowType: "laminarAndTurbulent",
  wallThermalCondition: "adiabatic",
  wallRoughness: 0,
  initPressure: 101325,
  initTemperature: 293.2,
  initVelX: 0,
  initVelY: 0,
  initVelZ: 0,
  turbulenceIntensity: 0.1,
  turbulenceLengthScale: 0.01,
};

function wizStart() {
  wizStep = 0;
  wizData.projectName = "Project(1)";
  wizData.projectPath = "";
  wizRenderNav();
  wizRenderStep();
  showModal("wizardModal");
}

function wizRenderNav() {
  const el = $("#wizNav");
  el.innerHTML = '<div class="wizard-nav-title">Navigator</div>' +
    WIZ_STEPS.map((s, i) => {
      let cls = "";
      if (i === wizStep) cls = "active";
      else if (i < wizStep) cls = "completed";
      return `<div class="wizard-nav-item ${cls}" onclick="wizGoto(${i})">
        <span class="wiz-icon">${i < wizStep ? "✅" : s.icon}</span>
        <span>${s.label}</span>
      </div>`;
    }).join("");
}

function wizGoto(i) {
  if (i > wizStep + 1) return; // can't skip ahead
  wizStep = i;
  wizRenderNav();
  wizRenderStep();
}

function wizBack() {
  if (wizStep > 0) { wizStep--; wizRenderNav(); wizRenderStep(); }
}

function wizNext() {
  // Collect data from current step
  wizCollectStep();
  if (wizStep < WIZ_STEPS.length - 1) {
    wizStep++;
    wizRenderNav();
    wizRenderStep();
  }
}

function wizHelp() {
  toast("ℹ️ Step " + (wizStep + 1) + ": " + WIZ_STEPS[wizStep].label);
}

function wizRenderStep() {
  const step = WIZ_STEPS[wizStep];
  $("#wizardTitle").textContent = "Wizard — " + step.label;
  $("#wizIllustration").textContent = step.illust;

  // Back/Next button states
  $("#wizBtnBack").disabled = wizStep === 0;
  $("#wizBtnBack").style.visibility = wizStep === 0 ? "hidden" : "visible";
  const isLast = wizStep === WIZ_STEPS.length - 1;
  $("#wizBtnNext").textContent = isLast ? "Finish" : "Next >";
  if (isLast) {
    $("#wizBtnNext").onclick = wizFinish;
  } else {
    $("#wizBtnNext").onclick = wizNext;
  }

  const el = $("#wizStepContent");
  const renderers = {
    "project-name": wizRenderProjectName,
    "unit-system": wizRenderUnits,
    "analysis-type": wizRenderAnalysis,
    "fluids": wizRenderFluids,
    "wall-conditions": wizRenderWall,
    "initial-conditions": wizRenderInitial,
    "finish": wizRenderFinish,
  };
  (renderers[step.id] || (() => { el.innerHTML = ""; }))(el);
}

// ── Step 1: Project Name ──────────────────────────────────────────────
function wizRenderProjectName(el) {
  el.innerHTML = `
    <h3 style="margin:0 0 12px;font-size:15px">Project</h3>
    <table class="param-table">
      <tr><td style="width:140px">Project name:</td><td><input type="text" id="wizProjName" value="${wizData.projectName}"></td></tr>
      <tr><td>Comments:</td><td><textarea id="wizProjComments" rows="3" style="width:100%;background:var(--surface0);color:var(--fg);border:1px solid var(--border);border-radius:4px;padding:4px 6px;font-size:12px;resize:vertical">${wizData.comments}</textarea></td></tr>
    </table>

    <h3 style="margin:16px 0 8px;font-size:14px;color:var(--fg-dim)">Configuration to add the project</h3>
    <table class="param-table">
      <tr><td style="width:140px">Configuration:</td>
        <td><select id="wizProjConfig" style="width:100%">
          <option value="current" selected>Use Current</option>
          <option value="new">Create New</option>
        </select></td>
      </tr>
      <tr><td>Configuration name:</td><td><input type="text" id="wizProjConfigName" value="${wizData.configName}"></td></tr>
    </table>

    <h3 style="margin:16px 0 8px;font-size:14px;color:var(--fg-dim)">Save location</h3>
    <div style="display:flex;gap:6px;align-items:center">
      <input type="text" id="wizProjPath" value="${wizData.projectPath}" placeholder="C:\\projects\\myproject" style="flex:1">
      <button class="btn" onclick="wizBrowsePath()">📁 Browse</button>
    </div>
  `;
}

async function wizBrowsePath() {
  // Reuse the existing file browser
  _browseSelected = "";
  const startPath = $("#wizProjPath") ? $("#wizProjPath").value.trim() : "";
  mshBrowseGo(startPath);
  // Temporarily override browse-select to write into wizard path field
  const origSelect = mshBrowseSelect;
  window._wizBrowseRestore = origSelect;
  window.mshBrowseSelect = function() {
    if (!_browseSelected && _browseCwd) _browseSelected = _browseCwd;
    if (_browseSelected) {
      const el = $("#wizProjPath");
      if (el) el.value = _browseSelected;
    }
    closeModal("browseModal");
    window.mshBrowseSelect = window._wizBrowseRestore;
  };
  showModal("browseModal");
}

// ── Step 2: Unit System ───────────────────────────────────────────────
const WIZ_UNIT_SYSTEMS = [
  { name: "CGS (cm-g-s)",   path: "Pre-Defined", comment: "CGS (cm-g-s)" },
  { name: "FPS (ft-lb-s)",  path: "Pre-Defined", comment: "FPS (ft-lb-s)" },
  { name: "IPS (in-lb-s)",  path: "Pre-Defined", comment: "IPS (in-lb-s)" },
  { name: "NMM (mm-g-s)",   path: "Pre-Defined", comment: "NMM (mm-g-s)" },
  { name: "SI (m-kg-s)",    path: "Pre-Defined", comment: "SI (m-kg-s)" },
  { name: "USA",            path: "Pre-Defined", comment: "USA" },
];

const WIZ_UNIT_PARAMS = [
  { group: "Main", items: [
    { name: "Pressure & stress", si: "Pa", cgs: "dyn/cm²", fps: "lbf/in²" },
    { name: "Velocity",          si: "m/s", cgs: "cm/s", fps: "ft/s" },
    { name: "Mass",              si: "kg",  cgs: "g",   fps: "lb" },
    { name: "Length",            si: "m",   cgs: "cm",  fps: "ft" },
    { name: "Temperature",       si: "K",   cgs: "K",   fps: "°F" },
    { name: "Physical time",     si: "s",   cgs: "s",   fps: "s" },
    { name: "Percentage",        si: "%",   cgs: "%",   fps: "%" },
  ]},
  { group: "HVAC", items: [
    { name: "Flow rate", si: "m³/s", cgs: "cm³/s", fps: "ft³/min" },
  ]},
];

function wizRenderUnits(el) {
  const sysRows = WIZ_UNIT_SYSTEMS.map(s =>
    `<tr class="${wizData.unitSystem === s.name ? 'selected' : ''}" style="${s.name === 'SI (m-kg-s)' ? '' : 'opacity:0.4;'}">
      <td>${s.name}</td><td>${s.path}</td><td>${s.comment}</td>
      <td style="width:20px;text-align:center">${s.name === 'SI (m-kg-s)' ? '🔒' : ''}</td>
    </tr>`
  ).join("");

  const paramRows = WIZ_UNIT_PARAMS.map(g =>
    `<tr class="group-header"><td colspan="4">${g.group}</td></tr>` +
    g.items.map(p => `<tr><td>${p.name}</td><td><strong>${p.si}</strong></td><td>—</td><td>1</td></tr>`).join("")
  ).join("");

  el.innerHTML = `
    <div style="display:flex;align-items:center;gap:8px;margin-bottom:12px">
      <div style="background:var(--accent);color:var(--bg);padding:3px 10px;border-radius:var(--radius);font-size:12px;font-weight:600">🔒 SI (m-kg-s)</div>
      <span style="font-size:12px;color:var(--fg-dim)">BaramFlow uses SI units exclusively. This cannot be changed.</span>
    </div>

    <h3 style="margin:0 0 8px;font-size:14px">Unit Systems (reference only):</h3>
    <div style="max-height:140px;overflow-y:auto;border:1px solid var(--border);border-radius:var(--radius)">
      <table class="param-table">
        <thead><tr><th>System</th><th>Path</th><th>Comment</th><th></th></tr></thead>
        <tbody>${sysRows}</tbody>
      </table>
    </div>

    <h3 style="margin:16px 0 8px;font-size:14px">SI Parameters:</h3>
    <div style="max-height:200px;overflow-y:auto;border:1px solid var(--border);border-radius:var(--radius)">
      <table class="param-table">
        <thead><tr><th>Parameter</th><th>SI Unit</th><th>Decimals</th><th>Factor</th></tr></thead>
        <tbody>${paramRows}</tbody>
      </table>
    </div>
  `;
}

function wizSelectUnit(name) {
  // Locked to SI — no-op
  toast("ℹ️ Unit system is locked to SI (m-kg-s)");
}

// ── Step 3: Analysis Type ─────────────────────────────────────────────
function wizRenderAnalysis(el) {
  const gravExpanded = wizData.gravity;
  const gravSection = gravExpanded ? `
    <div id="wizGravityAxes" style="margin-top:8px;padding:8px 12px;background:var(--bg);border:1px solid var(--border);border-radius:var(--radius)">
      <div style="font-size:12px;font-weight:600;color:var(--fg-dim);margin-bottom:6px">Gravity Vector (m/s²)</div>
      <div style="display:flex;gap:12px;align-items:center">
        <label style="font-size:12px;display:flex;align-items:center;gap:4px">X:
          <input type="number" id="wizGravX" value="${wizData.gravityX}" step="any" style="width:90px">
        </label>
        <label style="font-size:12px;display:flex;align-items:center;gap:4px">Y:
          <input type="number" id="wizGravY" value="${wizData.gravityY}" step="any" style="width:90px">
        </label>
        <label style="font-size:12px;display:flex;align-items:center;gap:4px">Z:
          <input type="number" id="wizGravZ" value="${wizData.gravityZ}" step="any" style="width:90px">
        </label>
      </div>
      <div style="margin-top:6px;display:flex;gap:6px">
        <button class="btn" style="font-size:11px;padding:2px 8px" onclick="wizSetGravPreset(0,-9.81,0)">↓ -Y (default)</button>
        <button class="btn" style="font-size:11px;padding:2px 8px" onclick="wizSetGravPreset(0,0,-9.81)">↓ -Z</button>
        <button class="btn" style="font-size:11px;padding:2px 8px" onclick="wizSetGravPreset(-9.81,0,0)">↓ -X</button>
        <button class="btn" style="font-size:11px;padding:2px 8px" onclick="wizSetGravPreset(0,9.81,0)">↑ +Y</button>
      </div>
    </div>
  ` : '';

  el.innerHTML = `
    <div style="display:flex;gap:24px">
      <div style="flex:1">
        <h3 style="margin:0 0 8px;font-size:14px">Analysis type</h3>
        <div class="radio-group" style="margin-bottom:12px">
          <label><input type="radio" name="wizAnalType" value="internal" ${wizData.analysisType === "internal" ? "checked" : ""} onchange="wizData.analysisType=this.value"> Internal</label>
          <label><input type="radio" name="wizAnalType" value="external" ${wizData.analysisType === "external" ? "checked" : ""} onchange="wizData.analysisType=this.value"> External</label>
        </div>
      </div>
      <div style="flex:1">
        <h3 style="margin:0 0 8px;font-size:14px">Consider closed cavities</h3>
        <div>
          <label style="font-size:13px"><input type="checkbox" id="wizExcludeCavities" ${wizData.excludeCavities ? "checked" : ""}> Exclude cavities without flow conditions</label>
        </div>
        <div style="margin-top:4px">
          <label style="font-size:13px"><input type="checkbox" id="wizExcludeInternal" ${wizData.excludeInternalSpace ? "checked" : ""}> Exclude internal space</label>
        </div>
      </div>
    </div>

    <h3 style="margin:16px 0 8px;font-size:14px">Physical Features</h3>
    <div style="border:1px solid var(--border);border-radius:var(--radius);overflow:hidden">
      <table class="param-table">
        <thead><tr><th>Physical Feature</th><th style="width:60px">Value</th></tr></thead>
        <tbody>
          <tr><td><strong>Heat conduction in solids</strong></td><td><input type="checkbox" id="wizHeatCond" ${wizData.heatConduction ? "checked" : ""}></td></tr>
          <tr><td><strong>Radiation</strong></td><td><input type="checkbox" id="wizRadiation" ${wizData.radiation ? "checked" : ""}></td></tr>
          <tr><td><strong>Time-dependent</strong></td><td><input type="checkbox" id="wizTimeDep" ${wizData.timeDependent ? "checked" : ""}></td></tr>
          <tr><td><strong>Gravity</strong></td><td><input type="checkbox" id="wizGravity" ${wizData.gravity ? "checked" : ""} onchange="wizToggleGravity(this.checked)"></td></tr>
        </tbody>
      </table>
    </div>
    ${gravSection}

    <h3 style="margin:16px 0 8px;font-size:14px">Additional Features</h3>
    <div style="border:1px solid var(--border);border-radius:var(--radius);overflow:hidden">
      <table class="param-table">
        <tbody>
          <tr><td><strong>Rotation</strong></td><td style="width:60px"><input type="checkbox" id="wizRotation" ${wizData.rotation ? "checked" : ""}></td></tr>
          <tr><td><strong>Free surface</strong></td><td style="width:60px"><input type="checkbox" id="wizFreeSurf" ${wizData.freeSurface ? "checked" : ""}></td></tr>
        </tbody>
      </table>
    </div>
  `;
}

function wizToggleGravity(checked) {
  wizData.gravity = checked;
  if (checked && wizData.gravityX === 0 && wizData.gravityY === 0 && wizData.gravityZ === 0) {
    wizData.gravityY = -9.81; // sensible default
  }
  wizCollectStep();
  wizRenderStep();
}

function wizSetGravPreset(x, y, z) {
  const xi = $("#wizGravX"), yi = $("#wizGravY"), zi = $("#wizGravZ");
  if (xi) xi.value = x;
  if (yi) yi.value = y;
  if (zi) zi.value = z;
  wizData.gravityX = x;
  wizData.gravityY = y;
  wizData.gravityZ = z;
}

// ── Step 4: Fluids ────────────────────────────────────────────────────
const WIZ_FLUID_DB = {
  Gases: ["air", "oxygen", "nitrogen", "carbonDioxide", "hydrogen", "helium", "argon", "carbonMonoxide", "methane", "waterVapor"],
  Liquids: ["waterLiquid", "kerosene", "ethanol", "methanol", "mercury", "benzene"],
  "Non-Newtonian Liquids": [],
  "Compressible Liquids": [],
  "Real Gases": [],
  Steam: [],
  "Combustible Mixtures": [],
};

function wizRenderFluids(el) {
  // Build tree
  let treeHtml = '<ul class="fluid-tree">';
  for (const [group, items] of Object.entries(WIZ_FLUID_DB)) {
    treeHtml += `<li class="tree-group">⊞ ${group}</li>`;
    for (const f of items) {
      const sel = wizData.selectedFluids.includes(f) ? "selected" : "";
      treeHtml += `<li class="${sel}" onclick="wizToggleFluid('${f}', this)" style="padding-left:24px">${f}</li>`;
    }
  }
  treeHtml += '</ul>';

  const projFluids = wizData.selectedFluids.map(f =>
    `<tr><td>${f}</td><td>${_wizFluidPhase(f)}</td></tr>`
  ).join("") || '<tr><td colspan="2" class="text-dim">No fluids selected</td></tr>';

  el.innerHTML = `
    <div style="display:flex;gap:16px;height:100%">
      <div style="flex:1;display:flex;flex-direction:column">
        <h3 style="margin:0 0 8px;font-size:14px">Fluids Database</h3>
        <div style="flex:1;overflow-y:auto;border:1px solid var(--border);border-radius:var(--radius);max-height:280px">
          ${treeHtml}
        </div>
      </div>
      <div style="display:flex;flex-direction:column;gap:6px;justify-content:center">
        <button class="btn btn-accent" style="padding:4px 12px" onclick="wizRenderStep()">Add →</button>
        <button class="btn" style="padding:4px 12px" onclick="wizRemoveFluid()">← Remove</button>
      </div>
      <div style="flex:1;display:flex;flex-direction:column">
        <h3 style="margin:0 0 8px;font-size:14px">Project Fluids</h3>
        <div style="flex:1;overflow-y:auto;border:1px solid var(--border);border-radius:var(--radius);max-height:160px">
          <table class="param-table">
            <thead><tr><th>Fluid</th><th>Default Fluid</th></tr></thead>
            <tbody>${projFluids}</tbody>
          </table>
        </div>

        <h3 style="margin:16px 0 8px;font-size:14px">Flow Characteristic</h3>
        <table class="param-table">
          <tr><td style="width:100px"><strong>Flow type</strong></td><td>
            <select id="wizFlowType" style="width:100%">
              <option value="laminarAndTurbulent" ${wizData.flowType === "laminarAndTurbulent" ? "selected" : ""}>Laminar and Turbulent</option>
              <option value="laminar" ${wizData.flowType === "laminar" ? "selected" : ""}>Laminar</option>
              <option value="turbulent" ${wizData.flowType === "turbulent" ? "selected" : ""}>Turbulent</option>
            </select>
          </td></tr>
        </table>
      </div>
    </div>
  `;
}

function _wizFluidPhase(name) {
  const liquids = ["waterLiquid","kerosene","ethanol","methanol","mercury","benzene","molten steel"];
  return liquids.includes(name) ? "Liquid" : "Gas";
}

function wizToggleFluid(name, liEl) {
  const idx = wizData.selectedFluids.indexOf(name);
  if (idx >= 0) {
    wizData.selectedFluids.splice(idx, 1);
    liEl.classList.remove("selected");
  } else {
    wizData.selectedFluids.push(name);
    liEl.classList.add("selected");
  }
  wizRenderStep();
}

function wizRemoveFluid() {
  if (wizData.selectedFluids.length > 0) {
    wizData.selectedFluids.pop();
    wizRenderStep();
  }
}

// ── Step 5: Wall Conditions ───────────────────────────────────────────
function wizRenderWall(el) {
  el.innerHTML = `
    <h3 style="margin:0 0 12px;font-size:14px">Default Wall Conditions</h3>
    <div style="border:1px solid var(--border);border-radius:var(--radius);overflow:hidden">
      <table class="param-table">
        <thead><tr><th style="width:250px">Parameter</th><th>Value</th></tr></thead>
        <tbody>
          <tr><td><strong>Default wall thermal condition</strong></td><td>
            <select id="wizWallThermal" style="width:100%">
              <option value="adiabatic" ${wizData.wallThermalCondition === "adiabatic" ? "selected" : ""}>Adiabatic wall</option>
              <option value="heatFlux" ${wizData.wallThermalCondition === "heatFlux" ? "selected" : ""}>Heat flux</option>
              <option value="heatTransferRate" ${wizData.wallThermalCondition === "heatTransferRate" ? "selected" : ""}>Heat transfer rate</option>
              <option value="wallTemperature" ${wizData.wallThermalCondition === "wallTemperature" ? "selected" : ""}>Wall temperature</option>
            </select>
          </td></tr>
          <tr><td><strong>Roughness</strong></td><td>
            <input type="number" id="wizWallRoughness" value="${wizData.wallRoughness}" step="0.001" min="0" style="width:120px"> m
          </td></tr>
        </tbody>
      </table>
    </div>
  `;
}

// ── Step 6: Initial Conditions ────────────────────────────────────────
function wizRenderInitial(el) {
  el.innerHTML = `
    <h3 style="margin:0 0 4px;font-size:14px">Initial Conditions</h3>

    <div style="border:1px solid var(--border);border-radius:var(--radius);overflow:hidden">
      <table class="param-table">
        <thead><tr><th style="width:220px">Parameter</th><th>Value</th></tr></thead>
        <tbody>
          <tr><td><strong>Parameter Definition</strong></td><td>
            <select style="width:100%"><option selected>User Defined</option><option>Automatic</option></select>
          </td></tr>

          <tr class="group-header"><td colspan="2">Thermodynamic Parameters</td></tr>
          <tr><td>Parameters</td><td>
            <select style="width:100%"><option selected>Pressure, temperature</option></select>
          </td></tr>
          <tr><td>Pressure</td><td>
            <input type="number" id="wizInitPressure" value="${wizData.initPressure}" step="any" style="width:140px"> Pa
          </td></tr>
          <tr><td>Temperature</td><td>
            <input type="number" id="wizInitTemp" value="${wizData.initTemperature}" step="any" style="width:140px"> K
          </td></tr>

          <tr class="group-header"><td colspan="2">Velocity Parameters</td></tr>
          <tr><td>Velocity in X direction</td><td>
            <input type="number" id="wizInitVX" value="${wizData.initVelX}" step="any" style="width:140px"> m/s
          </td></tr>
          <tr><td>Velocity in Y direction</td><td>
            <input type="number" id="wizInitVY" value="${wizData.initVelY}" step="any" style="width:140px"> m/s
          </td></tr>
          <tr><td>Velocity in Z direction</td><td>
            <input type="number" id="wizInitVZ" value="${wizData.initVelZ}" step="any" style="width:140px"> m/s
          </td></tr>

          <tr class="group-header"><td colspan="2">Turbulence Parameters</td></tr>
          <tr><td>Turbulence intensity</td><td>
            <input type="number" id="wizTurbI" value="${wizData.turbulenceIntensity}" step="0.01" min="0" max="1" style="width:140px">
          </td></tr>
          <tr><td>Turbulence length scale</td><td>
            <input type="number" id="wizTurbL" value="${wizData.turbulenceLengthScale}" step="0.001" min="0" style="width:140px"> m
          </td></tr>
        </tbody>
      </table>
    </div>
  `;
}

// ── Step 7: Finish ────────────────────────────────────────────────────
function wizRenderFinish(el) {
  const f = wizData;
  el.innerHTML = `
    <h3 style="margin:0 0 12px;font-size:15px">Project Summary</h3>
    <div style="border:1px solid var(--border);border-radius:var(--radius);overflow:hidden">
      <table class="param-table">
        <tr class="group-header"><td colspan="2">Project</td></tr>
        <tr><td style="width:180px">Name</td><td><strong>${f.projectName}</strong></td></tr>
        <tr><td>Path</td><td>${f.projectPath || "(will use name as path)"}</td></tr>
        <tr><td>Configuration</td><td>${f.configName}</td></tr>

        <tr class="group-header"><td colspan="2">Settings</td></tr>
        <tr><td>Unit System</td><td>${f.unitSystem}</td></tr>
        <tr><td>Analysis Type</td><td>${f.analysisType}</td></tr>
        <tr><td>Time-Dependent</td><td>${f.timeDependent ? "Yes" : "No"}</td></tr>
        <tr><td>Gravity</td><td>${f.gravity ? `Yes (${f.gravityX}, ${f.gravityY}, ${f.gravityZ}) m/s²` : "No"}</td></tr>
        <tr><td>Heat Conduction</td><td>${f.heatConduction ? "Yes" : "No"}</td></tr>
        <tr><td>Radiation</td><td>${f.radiation ? "Yes" : "No"}</td></tr>

        <tr class="group-header"><td colspan="2">Fluids</td></tr>
        <tr><td>Selected</td><td>${f.selectedFluids.join(", ") || "None"}</td></tr>
        <tr><td>Flow Type</td><td>${f.flowType}</td></tr>

        <tr class="group-header"><td colspan="2">Wall Conditions</td></tr>
        <tr><td>Thermal</td><td>${f.wallThermalCondition}</td></tr>
        <tr><td>Roughness</td><td>${f.wallRoughness} m</td></tr>

        <tr class="group-header"><td colspan="2">Initial Conditions</td></tr>
        <tr><td>Pressure</td><td>${f.initPressure} Pa</td></tr>
        <tr><td>Temperature</td><td>${f.initTemperature} K</td></tr>
        <tr><td>Velocity</td><td>(${f.initVelX}, ${f.initVelY}, ${f.initVelZ}) m/s</td></tr>
      </table>
    </div>
    <p style="margin-top:12px;font-size:13px;color:var(--accent)">Click <strong>Finish</strong> to create the project with these settings.</p>
  `;
}

// ── Collect values from the current step ──────────────────────────────
function wizCollectStep() {
  const step = WIZ_STEPS[wizStep];
  switch (step.id) {
    case "project-name":
      wizData.projectName = ($("#wizProjName")?.value || "").trim() || "Project(1)";
      wizData.projectPath = ($("#wizProjPath")?.value || "").trim();
      wizData.comments = ($("#wizProjComments")?.value || "").trim();
      wizData.configName = ($("#wizProjConfigName")?.value || "").trim() || "Default";
      break;
    case "analysis-type":
      wizData.excludeCavities = !!$("#wizExcludeCavities")?.checked;
      wizData.excludeInternalSpace = !!$("#wizExcludeInternal")?.checked;
      wizData.heatConduction = !!$("#wizHeatCond")?.checked;
      wizData.radiation = !!$("#wizRadiation")?.checked;
      wizData.timeDependent = !!$("#wizTimeDep")?.checked;
      wizData.gravity = !!$("#wizGravity")?.checked;
      if (wizData.gravity) {
        wizData.gravityX = parseFloat($("#wizGravX")?.value || 0);
        wizData.gravityY = parseFloat($("#wizGravY")?.value || -9.81);
        wizData.gravityZ = parseFloat($("#wizGravZ")?.value || 0);
      }
      wizData.rotation = !!$("#wizRotation")?.checked;
      wizData.freeSurface = !!$("#wizFreeSurf")?.checked;
      break;
    case "fluids":
      wizData.flowType = $("#wizFlowType")?.value || wizData.flowType;
      break;
    case "wall-conditions":
      wizData.wallThermalCondition = $("#wizWallThermal")?.value || wizData.wallThermalCondition;
      wizData.wallRoughness = parseFloat($("#wizWallRoughness")?.value || 0);
      break;
    case "initial-conditions":
      wizData.initPressure = parseFloat($("#wizInitPressure")?.value || 101325);
      wizData.initTemperature = parseFloat($("#wizInitTemp")?.value || 293.2);
      wizData.initVelX = parseFloat($("#wizInitVX")?.value || 0);
      wizData.initVelY = parseFloat($("#wizInitVY")?.value || 0);
      wizData.initVelZ = parseFloat($("#wizInitVZ")?.value || 0);
      wizData.turbulenceIntensity = parseFloat($("#wizTurbI")?.value || 0.1);
      wizData.turbulenceLengthScale = parseFloat($("#wizTurbL")?.value || 0.01);
      break;
  }
}

// ── Finish → create project via API ───────────────────────────────────
async function wizFinish() {
  wizCollectStep();

  const path = wizData.projectPath || wizData.projectName;
  if (!path) { toast("⚠️ Enter a project name or path"); return; }

  toast("⏳ Creating project with wizard settings…");

  // Step 1: Create the project
  const proj = await apiPost("/api/project/new", { path });
  if (!proj) return;

  // Step 2: Apply wizard settings via dedicated endpoint
  const d = await apiPost("/api/wizard/apply", wizData);
  if (d && d.success) {
    prjData = proj;
    prjUpdateUI();
    closeModal("wizardModal");
    toast("✅ Project created: " + proj.name);
    navSelect("general");
  } else {
    // Project was created but settings may have partially failed
    prjData = proj;
    prjUpdateUI();
    closeModal("wizardModal");
    toast("⚠️ Project created, but some wizard settings could not be applied");
    navSelect("general");
  }
}


// ═══════════════════════════════════════════════════════════════════════════
//  Tab / dock switching
// ═══════════════════════════════════════════════════════════════════════════

function initTabSwitching() {
  // App-level tabs
  $$(".app-tab").forEach(tab => {
    tab.addEventListener("click", () => {
      $$(".app-tab").forEach(t => t.classList.remove("active"));
      $$(".tab-content").forEach(c => c.classList.remove("active"));
      tab.classList.add("active");
      const target = tab.dataset.appTab;
      const content = $(`.tab-content[data-app-content="${target}"]`);
      if (content) content.classList.add("active");
    });
  });

  // Dock tabs
  $$(".dock-tab").forEach(tab => {
    tab.addEventListener("click", () => {
      const panel = tab.closest(".detail-panel");
      panel.querySelectorAll(".dock-tab").forEach(t => t.classList.remove("active"));
      panel.querySelectorAll(".dock-content").forEach(c => c.classList.remove("active"));
      tab.classList.add("active");
      const target = tab.dataset.dock;
      const content = panel.querySelector(`.dock-content[data-dock-content="${target}"]`);
      if (content) content.classList.add("active");
    });
  });
}


// ═══════════════════════════════════════════════════════════════════════════
//  Keyboard shortcuts
// ═══════════════════════════════════════════════════════════════════════════

document.addEventListener("keydown", (e) => {
  // Escape → close any open modal
  if (e.key === "Escape") {
    $$(".modal-backdrop.show").forEach(m => m.classList.remove("show"));
  }
  // Ctrl+S → save project
  if (e.ctrlKey && e.key === "s") {
    e.preventDefault();
    prjSave();
  }
  // Ctrl+R → run solver
  if (e.ctrlKey && e.key === "r") {
    e.preventDefault();
    slvStart();
  }
});


// ═══════════════════════════════════════════════════════════════════════════
//  DOMContentLoaded — bootstrap
// ═══════════════════════════════════════════════════════════════════════════

document.addEventListener("DOMContentLoaded", () => {
  initTabSwitching();
  navInit();
  prjInit();
  mshLoadGeometries();
});
