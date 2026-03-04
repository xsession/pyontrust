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
  // FloEFD-style pages (L2–L8)
  "geometry-prep":        { load: geoLoad, render: geoRender },
  "analysis-setup":       { load: anlLoad, render: anlRender },
  "features":             { load: ftrLoad, render: ftrRender },
  "floefd-bc":            { load: fbcLoad, render: fbcRender },
  "floefd-mesh":          { load: fmshLoad, render: fmshRender },
  "floefd-goals":         { load: fglLoad, render: fglRender },
  "floefd-solve":         { load: fslvLoad, render: fslvRender },
  "post-processing":      { load: ppLoad, render: ppRender },
  "parametric-study":     { load: pstLoad, render: pstRender },
};

// FloEFD-style tree definition
const NAV_TREE = [
  { id: "project-root", label: "Project", icon: "📁", page: null, expanded: true, children: [
    { id: "input-data", label: "Input Data", icon: "📂", page: null, expanded: true, children: [
      { id: "general", label: "General Settings", icon: "⚙️", page: "general" },
      { id: "geometry-prep", label: "Geometry Preparation", icon: "🔧", page: "geometry-prep" },
      { id: "analysis-setup", label: "Analysis Setup", icon: "🌡️", page: "analysis-setup" },
      { id: "features", label: "Features (L4a)", icon: "🔧", page: "features" },
      { id: "comp-domain", label: "Computational Domain", icon: "📦", page: "cell-zones" },
      { id: "fluid-subdomains", label: "Fluid Subdomains", icon: "💧", page: "materials" },
      { id: "solid-materials", label: "Solid Materials", icon: "🧱", page: null, expanded: false, children: [] },
      { id: "floefd-bc", label: "Boundary Conditions", icon: "🔲", page: "floefd-bc" },
      { id: "boundary-conditions", label: "BCs (OpenFOAM)", icon: "📋", page: "boundary-conditions" },
      { id: "heat-sources", label: "Heat Sources", icon: "🔥", page: "heat-sources", expanded: false, children: [] },
      { id: "fans", label: "Fans", icon: "🌀", page: "fans", expanded: false, children: [] },
      { id: "radiative-surfaces", label: "Radiative Surfaces", icon: "☀️", page: null, expanded: false, children: [] },
      { id: "contact-resistances", label: "Contact Resistances", icon: "🔗", page: null, expanded: false, children: [] },
      { id: "floefd-goals", label: "Goals (L4b)", icon: "🎯", page: "floefd-goals" },
    ]},
    { id: "models", label: "Models", icon: "📐", page: "models" },
    { id: "mesh-group", label: "Mesh", icon: "🔷", page: null, expanded: true, children: [
      { id: "floefd-mesh", label: "Meshing (L5)", icon: "🔷", page: "floefd-mesh" },
      { id: "global-mesh", label: "Global Mesh (legacy)", icon: "📊", page: null },
    ]},
    { id: "numerical", label: "Numerical Conditions", icon: "🔢", page: "numerical" },
  ]},
  { id: "solution-group", label: "Solution", icon: "▶️", page: null, expanded: true, children: [
    { id: "initialization", label: "Initialization", icon: "🎯", page: "initialization" },
    { id: "run-conditions", label: "Run Conditions", icon: "⏱️", page: "run-conditions" },
    { id: "floefd-solve", label: "Solve & Monitor", icon: "📈", page: "floefd-solve" },
    { id: "run", label: "Run (OpenFOAM)", icon: "▶️", page: "run" },
  ]},
  { id: "results-group", label: "Results", icon: "📊", page: null, expanded: true, children: [
    { id: "post-processing", label: "Post Processing", icon: "🖼️", page: "post-processing" },
    { id: "parametric-study", label: "Parametric Study", icon: "🔬", page: "parametric-study" },
  ]},
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

const _FLOEFD_PAGES = new Set([
  "geometry-prep", "analysis-setup", "features", "floefd-bc", "floefd-mesh",
  "floefd-goals", "floefd-solve", "post-processing", "parametric-study",
]);

async function navSelect(page, clickedEl) {
  if (!prjData && page !== "general" && !_FLOEFD_PAGES.has(page)) {
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
//  geo* — L2: Geometry Preparation (FloEFD-style — full workflow)
// ═══════════════════════════════════════════════════════════════════════════

let geoList = [];
let geoCheckResult = null;
let geoDiagResult = null;   // per-part diagnostics
let geoActiveTab = "parts"; // parts | workflow | diagnostics | tips

async function geoLoad() {
  geoList = await apiFetch("/api/floefd/geometry") || [];
}

function geoRender() {
  const tabs = [
    { id: "parts",       label: "📦 Parts",         active: geoActiveTab === "parts" },
    { id: "workflow",    label: "🔄 Workflow",       active: geoActiveTab === "workflow" },
    { id: "diagnostics", label: "🔍 Diagnostics",   active: geoActiveTab === "diagnostics" },
    { id: "tips",        label: "💡 Tips & Guide",   active: geoActiveTab === "tips" },
  ];
  const tabBar = tabs.map(t =>
    `<button class="btn${t.active ? ' btn-accent' : ''}" style="font-size:12px;padding:4px 12px"
      onclick="geoActiveTab='${t.id}';geoRender()">${t.label}</button>`
  ).join("");

  let content = "";
  if (geoActiveTab === "parts")       content = _geoRenderParts();
  else if (geoActiveTab === "workflow") content = _geoRenderWorkflow();
  else if (geoActiveTab === "diagnostics") content = _geoRenderDiagnostics();
  else if (geoActiveTab === "tips")    content = _geoRenderTips();

  $("#pageContent").innerHTML = `
    <div class="page-header">🔧 Geometry Preparation <span style="font-size:13px;color:var(--fg-dim);font-weight:normal">— Lecture 2</span></div>
    <p class="text-dim mb-8">
      Geometry must be <strong>"Fit for purpose"</strong> — CAD for production ≠ CAD for CFD analysis.
      Simplify, check, and fix geometry before meshing.
    </p>
    <div style="display:flex;gap:6px;margin-bottom:16px;flex-wrap:wrap">${tabBar}</div>
    ${content}
  `;
}

/* ── Parts Tab ────────────────────────────────────────────────────── */
function _geoRenderParts() {
  const statusBadge = (g) => {
    if (g.suppress) return '<span class="badge-wall" style="font-size:10px">SUPPRESSED</span>';
    if (g.disabled) return '<span class="badge-symmetry" style="font-size:10px">DISABLED</span>';
    if (g.replaced) return '<span class="badge-inlet" style="font-size:10px">REPLACED</span>';
    if (g.has_errors) return '<span class="badge-outlet" style="font-size:10px">⚠ ERRORS</span>';
    return '<span style="color:var(--green);font-size:10px">✓ OK</span>';
  };

  const rows = geoList.map(g => `
    <tr style="${g.suppress || g.disabled ? 'opacity:0.5' : ''}">
      <td><span style="display:inline-block;width:12px;height:12px;background:${g.color};border-radius:2px;vertical-align:middle"></span> ${g.name}</td>
      <td>${g.file_type || '—'}</td>
      <td style="font-size:11px">${g.file_origin === 'native' ? '🟢 Native' : '🟡 Neutral'}</td>
      <td>${g.is_fluid_region ? '💧 Fluid' : g.is_solid_region ? '🧱 Solid' : g.is_surface_body ? '⚠️ Surface' : '—'}</td>
      <td>${g.num_faces || 0}</td>
      <td>${statusBadge(g)}</td>
      <td>${g.lids?.length || 0}</td>
      <td style="white-space:nowrap">
        <button class="btn" style="padding:1px 6px;font-size:10px" onclick="geoRunDiag('${g.id}')" title="Run Import Diagnostics">🔍</button>
        <button class="btn" style="padding:1px 6px;font-size:10px" onclick="geoToggleSuppress('${g.id}',${!g.suppress})" title="${g.suppress ? 'Unsuppress' : 'Suppress'}">${g.suppress ? '👁️' : '🚫'}</button>
        <button class="btn" style="padding:1px 6px;font-size:10px" onclick="geoToggleDisable('${g.id}',${!g.disabled})" title="${g.disabled ? 'Enable' : 'Disable'}">${g.disabled ? '🔓' : '🔒'}</button>
        <button class="btn" style="padding:1px 6px;font-size:10px" onclick="geoReplace('${g.id}')" title="Replace with simplified">♻️</button>
        <button class="btn" style="padding:1px 6px;font-size:10px" onclick="geoAddLid('${g.id}')" title="Add Lid">🔲</button>
        <button class="btn" style="padding:1px 6px;font-size:10px;color:var(--red)" onclick="geoDelete('${g.id}')">✕</button>
      </td>
    </tr>
  `).join("") || '<tr><td colspan="8" class="text-dim">No geometry parts. Import CAD files below.</td></tr>';

  return `
    <div class="info-box mb-8">
      <strong>4 Main Methods to simplify geometry:</strong>
      🚫 <strong>Suppress</strong> — removes from CFD but keeps in CAD &nbsp;|&nbsp;
      ♻️ <strong>Replace</strong> — swap complex parts for simple ones &nbsp;|&nbsp;
      🔒 <strong>Disable</strong> — visible in CAD, invisible to CFD &nbsp;|&nbsp;
      ✕ <strong>Delete</strong> — irrecoverably alter data <em>(not recommended)</em>
    </div>

    <table class="data-table mb-8">
      <thead><tr><th>Part Name</th><th>Type</th><th>Origin</th><th>Region</th><th>Faces</th><th>Status</th><th>Lids</th><th>Actions</th></tr></thead>
      <tbody>${rows}</tbody>
    </table>

    <div style="display:flex;gap:12px;flex-wrap:wrap;margin-bottom:12px">
      <button class="btn btn-accent" onclick="geoCheckAll()">🔍 Check All Geometry</button>
      <button class="btn" onclick="geoHealAll()">🩹 Attempt Heal All</button>
    </div>

    ${geoCheckResult ? _geoRenderCheckSummary() : ''}

    <h3 style="margin:20px 0 12px;font-size:14px;color:var(--accent)">Import Geometry</h3>
    <div style="display:grid;grid-template-columns:1fr 120px 140px 140px 120px auto;gap:8px;align-items:flex-end">
      <div class="form-section" style="margin:0">
        <label>Part Name</label>
        <input type="text" id="geoName" value="Part ${geoList.length + 1}">
      </div>
      <div class="form-section" style="margin:0">
        <label>File Type</label>
        <select id="geoFileType">
          <optgroup label="Preferred (neutral)">
            <option value="parasolid">Parasolid</option>
            <option value="sat">SAT</option>
            <option value="step" selected>STEP</option>
            <option value="iges">IGES</option>
          </optgroup>
          <optgroup label="Native">
            <option value="sldprt">SolidWorks</option>
            <option value="prt">Creo/ProE</option>
            <option value="catpart">CATIA V5</option>
            <option value="nx">NX</option>
          </optgroup>
          <optgroup label="Other">
            <option value="stl">STL</option>
            <option value="obj">OBJ</option>
          </optgroup>
        </select>
      </div>
      <div class="form-section" style="margin:0">
        <label>Region</label>
        <select id="geoRegion">
          <option value="none">Not assigned</option>
          <option value="fluid">Fluid Region</option>
          <option value="solid">Solid Region</option>
        </select>
      </div>
      <div class="form-section" style="margin:0">
        <label>Tag</label>
        <select id="geoTag">
          <option value="">None</option>
          <option value="enclosure">Enclosure</option>
          <option value="pipe">Pipe</option>
          <option value="pcb">PCB</option>
          <option value="heatsink">Heatsink</option>
          <option value="fastener">Fastener</option>
          <option value="cosmetic">Cosmetic</option>
          <option value="sheet_metal">Sheet Metal</option>
        </select>
      </div>
      <div class="form-section" style="margin:0">
        <label>Faces</label>
        <input type="number" id="geoFaces" value="${Math.floor(Math.random() * 5000) + 100}" min="1">
      </div>
      <button class="btn btn-accent" onclick="geoAdd()" style="height:34px">➕ Import</button>
    </div>
  `;
}

function _geoRenderCheckSummary() {
  const r = geoCheckResult;
  if (!r) return '';
  const readyClass = r.ready_for_analysis ? 'color:var(--green)' : 'color:var(--red)';
  return `
    <div style="background:var(--surface0);border-radius:8px;padding:12px;margin-top:12px">
      <h4 style="margin:0 0 8px;font-size:13px;color:var(--accent)">🔍 Geometry Check Summary</h4>
      <div style="display:grid;grid-template-columns:repeat(5,1fr);gap:8px">
        <div class="stat-card"><div style="font-size:20px;font-weight:700">${r.parts_checked}</div><div style="font-size:11px">Parts Checked</div></div>
        <div class="stat-card"><div style="font-size:20px;font-weight:700;color:var(--red)">${r.total_errors}</div><div style="font-size:11px">Errors</div></div>
        <div class="stat-card"><div style="font-size:20px;font-weight:700;color:var(--peach)">${r.total_warnings}</div><div style="font-size:11px">Warnings</div></div>
        <div class="stat-card"><div style="font-size:20px;font-weight:700">${r.all_watertight ? '✅' : '❌'}</div><div style="font-size:11px">Watertight</div></div>
        <div class="stat-card"><div style="font-size:20px;font-weight:700">${r.fluid_region_detected ? '✅' : '❌'}</div><div style="font-size:11px">Fluid Region</div></div>
      </div>
      <div style="margin-top:8px;font-size:13px;font-weight:600;${readyClass}">
        ${r.ready_for_analysis ? '✅ Geometry is ready for analysis' : '⚠️ Geometry needs attention before analysis'}
      </div>
      ${r.results?.length ? '<details style="margin-top:8px"><summary style="cursor:pointer;font-size:12px;color:var(--accent)">Show per-part details</summary>' +
        r.results.map(pr => `
          <div style="margin:6px 0;padding:6px;background:var(--bg);border-radius:4px;font-size:11px">
            <strong>${pr.part_name}</strong> — ${pr.is_solid ? '🧊 Solid' : '⚠️ Surface'} | Watertight: ${pr.is_watertight ? '✅' : '❌'} |
            Faulty faces: ${pr.faulty_face_count} | Gaps: ${pr.gap_count} | Contacts: ${pr.invalid_contact_count}
            ${pr.errors.length ? '<div style="color:var(--red);margin-top:2px">' + pr.errors.slice(0,5).join('<br>') + '</div>' : ''}
            ${pr.recommendations.length ? '<div style="color:var(--peach);margin-top:2px">' + pr.recommendations.join('<br>') + '</div>' : ''}
          </div>
        `).join('') + '</details>' : ''}
    </div>
  `;
}

/* ── Workflow Tab (Summary flowchart from slides) ─────────────────── */
function _geoRenderWorkflow() {
  return `
    <div class="info-box mb-8">
      <strong>Geometry Preparation Workflow</strong> — Follow this flowchart to prepare CAD data for CFD analysis.
    </div>

    <div style="display:grid;grid-template-columns:1fr 1fr;gap:16px">
      <!-- Left column: Import & Fix -->
      <div>
        <h4 style="color:var(--accent);margin:0 0 12px">1️⃣ Import & Fix</h4>
        <div style="display:flex;flex-direction:column;gap:8px">
          ${_geoFlowStep('🟢', 'Start', 'Determine if file is Native or Imported (neutral)', 'start')}
          ${_geoFlowStep('📁', 'Native Files', 'SolidWorks, Creo, CATIA V5, NX — parametric features, full history, part names', 'native')}
          ${_geoFlowStep('📄', 'Neutral Files', 'STEP, SAT, Parasolid, IGES — no parametric data, more likely to have errors', 'neutral')}
          ${_geoFlowStep('🔍', 'Import Diagnostics', 'Run diagnostics to find faulty faces, gaps between faces', 'diagnostics')}
          ${_geoFlowStep('🩹', 'Automatic Heal', '"Heal All" option will fix most problems. 85%+ success rate.', 'heal')}
          ${_geoFlowStep('✂️', 'Manual Fix', 'Delete and patch faulty faces. Clone specific surfaces — last resort.', 'manual-fix')}
          ${_geoFlowStep('🧊', 'Knit / Thicken', 'If imported as surface body → knit or thicken to form solid. FloEFD only works with solid bodies!', 'knit')}
        </div>
      </div>

      <!-- Right column: Simplify & Prepare -->
      <div>
        <h4 style="color:var(--accent);margin:0 0 12px">2️⃣ Simplify & Prepare</h4>
        <div style="display:flex;flex-direction:column;gap:8px">
          ${_geoFlowStep('🚫', 'Suppress Features', 'Fillets, chamfers, threads, holes, internal detail — negligible CFD impact', 'suppress')}
          ${_geoFlowStep('♻️', 'Replace Complex Parts', 'Perforated plates → porous media, fans/pumps, heat pipes, PCBs, sheet metal', 'replace')}
          ${_geoFlowStep('🔒', 'Disable Insignificant Parts', 'Nuts, bolts, washers, fastenings, gaskets, cabling, cosmetics (lettering)', 'disable')}
          ${_geoFlowStep('🔲', 'Create Lids', 'Internal analysis: seal pipe/valve/enclosure openings with lids for BC placement', 'lids')}
          ${_geoFlowStep('🔗', 'Remove Invalid Contacts', 'Fix tangency, line contact, point contact — need surface contact for meshing', 'contacts')}
          ${_geoFlowStep('💧', 'Check Fluid Region', 'FloEFD "Check Geometry" tool — ready if fluid region detected', 'fluid-check')}
          ${_geoFlowStep('🏁', 'Finish', 'Geometry ready for analysis!', 'finish')}
        </div>
      </div>
    </div>

    <div class="info-box" style="margin-top:16px">
      <strong>Key Rule:</strong> If a model is too complex or detailed → large mesh → longer solve → increased hardware requirements.
      <br><em>Software cannot determine what is significant. Engineering knowledge and experience is required.</em>
    </div>
  `;
}

function _geoFlowStep(icon, title, desc, id) {
  return `
    <div style="display:flex;gap:8px;align-items:flex-start;padding:8px;background:var(--surface0);border-radius:6px;border-left:3px solid var(--accent)">
      <span style="font-size:18px;flex-shrink:0">${icon}</span>
      <div>
        <div style="font-size:12px;font-weight:600;color:var(--fg)">${title}</div>
        <div style="font-size:11px;color:var(--fg-dim);line-height:1.4">${desc}</div>
      </div>
    </div>
  `;
}

/* ── Diagnostics Tab ──────────────────────────────────────────────── */
function _geoRenderDiagnostics() {
  const partOptions = geoList.map(g =>
    `<option value="${g.id}">${g.name} (${g.file_type})</option>`
  ).join("") || '<option value="">No parts imported</option>';

  let diagHtml = '';
  if (geoDiagResult) {
    const r = geoDiagResult;
    diagHtml = `
      <div style="background:var(--surface0);border-radius:8px;padding:12px;margin-top:12px">
        <h4 style="margin:0 0 8px;font-size:13px;color:var(--accent)">📋 Diagnostics: ${r.part_name}</h4>

        <div style="display:grid;grid-template-columns:repeat(4,1fr);gap:8px;margin-bottom:12px">
          <div class="stat-card"><div style="font-size:18px;font-weight:700">${r.is_solid ? '🧊 Solid' : '⚠️ Surface'}</div><div style="font-size:10px">Body Type</div></div>
          <div class="stat-card"><div style="font-size:18px;font-weight:700;color:${r.is_watertight ? 'var(--green)' : 'var(--red)'}">${r.is_watertight ? '✅ Yes' : '❌ No'}</div><div style="font-size:10px">Watertight</div></div>
          <div class="stat-card"><div style="font-size:18px;font-weight:700;color:var(--red)">${r.faulty_face_count}</div><div style="font-size:10px">Faulty Faces</div></div>
          <div class="stat-card"><div style="font-size:18px;font-weight:700;color:var(--peach)">${r.gap_count}</div><div style="font-size:10px">Gaps</div></div>
        </div>

        ${r.errors.length ? `<div style="margin-bottom:8px">
          <strong style="font-size:12px;color:var(--red)">❌ Errors (${r.errors.length}):</strong>
          <div style="max-height:120px;overflow-y:auto;background:var(--bg);padding:6px;border-radius:4px;margin-top:4px;font-size:11px;font-family:monospace">
            ${r.errors.map(e => `<div style="color:var(--red)">• ${e}</div>`).join('')}
          </div>
        </div>` : '<div style="font-size:12px;color:var(--green);margin-bottom:8px">✅ No errors found</div>'}

        ${r.warnings.length ? `<div style="margin-bottom:8px">
          <strong style="font-size:12px;color:var(--peach)">⚠ Warnings (${r.warnings.length}):</strong>
          <div style="max-height:100px;overflow-y:auto;background:var(--bg);padding:6px;border-radius:4px;margin-top:4px;font-size:11px">
            ${r.warnings.map(w => `<div style="color:var(--peach)">• ${w}</div>`).join('')}
          </div>
        </div>` : ''}

        ${r.recommendations.length ? `<div style="margin-bottom:8px">
          <strong style="font-size:12px;color:var(--accent)">💡 Recommendations:</strong>
          <div style="background:var(--bg);padding:6px;border-radius:4px;margin-top:4px;font-size:11px">
            ${r.recommendations.map(rec => `<div style="color:var(--accent)">→ ${rec}</div>`).join('')}
          </div>
        </div>` : ''}

        <div style="display:flex;gap:8px;margin-top:8px">
          <button class="btn btn-accent" onclick="geoHealPart('${r.part_id}')">🩹 Attempt Heal All</button>
          ${r.needs_lids ? `<button class="btn" onclick="geoAddLid('${r.part_id}')">🔲 Create Lid</button>` : ''}
          ${!r.is_solid ? `<button class="btn" onclick="toast('🧊 Knit/Thicken — mock')">🧊 Knit to Solid</button>` : ''}
        </div>
      </div>
    `;
  }

  return `
    <div class="info-box mb-8">
      <strong>Import Diagnostics</strong> — On completion of import, use diagnostics to locate faulty faces and gaps.
      "Heal All" fixes most problems. For remaining issues, delete and patch faulty faces or clone/offset surfaces.
    </div>

    <div style="display:flex;gap:8px;align-items:flex-end;margin-bottom:8px">
      <div class="form-section" style="flex:1;margin:0">
        <label>Select Part</label>
        <select id="geoDiagPart">${partOptions}</select>
      </div>
      <button class="btn btn-accent" onclick="geoRunDiagSelected()" style="height:34px">🔍 Run Diagnostics</button>
      <button class="btn" onclick="geoCheckAll()" style="height:34px">🔍 Check All</button>
    </div>

    ${diagHtml}
    ${geoCheckResult ? _geoRenderCheckSummary() : ''}
  `;
}

/* ── Tips & Guide Tab ─────────────────────────────────────────────── */
function _geoRenderTips() {
  return `
    <!-- Why simplify -->
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:16px">
      <div>
        <h4 style="color:var(--accent);margin:0 0 8px">Why Simplify?</h4>
        <ul style="font-size:12px;line-height:1.8;margin:0;padding-left:20px;color:var(--fg-dim)">
          <li>A key part of CFD analysis is the <strong>meshing</strong></li>
          <li>Results depend entirely on the mesh — <strong>bad mesh = bad results</strong></li>
          <li>Trade-off between solution time and accuracy</li>
          <li>Too complex/detailed → large mesh → longer solve → more hardware</li>
          <li>Software cannot determine what is significant to analysis</li>
          <li><em>Engineering knowledge and experience is required</em></li>
        </ul>
      </div>
      <div>
        <h4 style="color:var(--accent);margin:0 0 8px">Geometry Types</h4>
        <div style="font-size:12px;line-height:1.7;color:var(--fg-dim)">
          <strong style="color:var(--green)">Native Files</strong> (SolidWorks, Creo, CATIA V5, NX)
          <ul style="margin:2px 0 8px 16px;padding:0"><li>Parametric features, hidden/suppressed items</li><li>Full model history, datums, part names</li></ul>
          <strong style="color:var(--peach)">Neutral Files</strong> (STEP, SAT, Parasolid, IGES)
          <ul style="margin:2px 0 0 16px;padding:0"><li>None of the above — more likely to have import errors</li>
          <li>Preferred import order: 1) Parasolid → 2) SAT → 3) STEP → 4) IGES</li></ul>
        </div>
      </div>
    </div>

    <hr style="border-color:var(--surface0);margin:16px 0">

    <!-- What to suppress / replace / disable -->
    <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:16px">
      <div>
        <h4 style="color:var(--accent);margin:0 0 8px">🚫 What to Suppress</h4>
        <div style="font-size:11px;color:var(--fg-dim);line-height:1.7">
          Features you may need later for detailed analysis:
          <ul style="margin:4px 0 0 12px;padding:0">
            <li>Fillets</li><li>Chamfers</li><li>Threads</li>
            <li>Holes (required for manufacture, not CFD)</li>
            <li>Internal detail</li>
            <li>Any intricate detail with negligible impact</li>
          </ul>
        </div>
      </div>
      <div>
        <h4 style="color:var(--accent);margin:0 0 8px">♻️ What to Replace</h4>
        <div style="font-size:11px;color:var(--fg-dim);line-height:1.7">
          Significant parts that can be modelled simpler:
          <ul style="margin:4px 0 0 12px;padding:0">
            <li>Perforated plates → Porous media</li>
            <li>Fans / Pumps</li>
            <li>Heat pipes</li>
            <li>PCBs</li>
            <li>Sheet metal items</li>
          </ul>
          <em>Same effect on analysis without the mesh overhead</em>
        </div>
      </div>
      <div>
        <h4 style="color:var(--accent);margin:0 0 8px">🔒 What to Disable</h4>
        <div style="font-size:11px;color:var(--fg-dim);line-height:1.7">
          Parts irrelevant to analysis:
          <ul style="margin:4px 0 0 12px;padding:0">
            <li>Nuts, bolts, washers</li>
            <li>Fastenings, gaskets</li>
            <li>Detailed cabling and connectors</li>
            <li>Cosmetics: lettering, numbering, codes</li>
          </ul>
        </div>
      </div>
    </div>

    <hr style="border-color:var(--surface0);margin:16px 0">

    <!-- Tips section -->
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:16px">
      <div class="info-box">
        <strong>💡 Removing Holes</strong>
        <div style="font-size:11px;margin-top:4px;line-height:1.6">
          Suppressing/disabling parts may leave holes (rivet, bolt holes).
          <br><strong>Plug entire surface:</strong>
          <ol style="margin:4px 0 0 16px;padding:0">
            <li>Sketch on surface</li>
            <li>Convert edges</li>
            <li>Extrude up to surface</li>
            <li>Pick other side of component</li>
          </ol>
          <em>⚠ Be careful the assembly does not use removed faces for placement</em>
        </div>
      </div>
      <div class="info-box">
        <strong>💡 Lids (for Internal Analysis)</strong>
        <div style="font-size:11px;margin-top:4px;line-height:1.6">
          Required for internal flow: pipes, valves, enclosures.
          <br>• Boundary condition placed on inlet and outlet lids
          <br>• Required to define an internal flow domain
          <br>• FloEFD can create lids automatically
        </div>
      </div>
      <div class="info-box">
        <strong>💡 Leaks / Gaps</strong>
        <div style="font-size:11px;margin-top:4px;line-height:1.6">
          "Face is not laying on boundary between solid and fluid region"
          <br>• Very common error — indicates non-sealed geometry
          <br>• Use Leak Tracking tool to trace route between faces
          <br>• Fix by patching gaps or creating lids
        </div>
      </div>
      <div class="info-box">
        <strong>💡 Invalid Contact</strong>
        <div style="font-size:11px;margin-top:4px;line-height:1.6">
          Parts with tangency, line contact, or point contact.
          <br>• Need surface contact between 2+ parts for meshing
          <br>• Many are automatically fixed by check geometry tool
          <br>• Required for correct heat conduction between parts
        </div>
      </div>
    </div>

    <div class="info-box" style="margin-top:16px;border-left-color:var(--green)">
      <strong style="color:var(--green)">✅ Conclusion</strong>
      <ul style="font-size:11px;line-height:1.7;margin:4px 0 0 12px;padding:0">
        <li>Use engineering knowledge to determine what is significant</li>
        <li>Simplify in the native CAD package for maximum flexibility</li>
        <li>Suppress, Replace, Disable or Delete insignificant components</li>
        <li>Use various methods to fix and create analysis-ready geometry</li>
        <li>Apply lids to inlets/outlets to create a closed fluid region</li>
        <li>Ensure assemblies are constrained — no invalid contacts or gaps</li>
      </ul>
    </div>
  `;
}

/* ── Geometry Actions ─────────────────────────────────────────────── */
async function geoAdd() {
  const name = ($("#geoName")?.value || "").trim() || "Part";
  const fileType = $("#geoFileType")?.value || "step";
  const region = $("#geoRegion")?.value || "none";
  const tag = $("#geoTag")?.value || "";
  const faces = parseInt($("#geoFaces")?.value || 500);
  const body = {
    name, file_type: fileType,
    is_fluid_region: region === "fluid",
    is_solid_region: region === "solid",
    num_faces: faces,
  };
  if (tag) body.tags = [tag];
  const d = await apiPost("/api/floefd/geometry", body);
  if (d) { toast("✅ Geometry imported"); await geoLoad(); geoRender(); }
}

async function geoDelete(id) {
  const d = await apiFetch(`/api/floefd/geometry/${id}`, { method: "DELETE" });
  if (d && d.success) { toast("🗑 Part removed"); await geoLoad(); geoRender(); }
}

async function geoToggleSuppress(id, suppress) {
  const d = await apiPost(`/api/floefd/geometry/${id}/suppress`, { suppress });
  if (d) { toast(suppress ? "🚫 Part suppressed" : "👁️ Part unsuppressed"); await geoLoad(); geoRender(); }
}

async function geoToggleDisable(id, disabled) {
  const d = await apiPost(`/api/floefd/geometry/${id}/disable`, { disabled });
  if (d) { toast(disabled ? "🔒 Part disabled for CFD" : "🔓 Part enabled"); await geoLoad(); geoRender(); }
}

async function geoReplace(id) {
  const note = prompt("Replacement description (e.g. 'Porous media', 'Simple box'):", "Simplified");
  if (note === null) return;
  const d = await apiPost(`/api/floefd/geometry/${id}/replace`, { replacement_note: note });
  if (d) { toast("♻️ Part marked as replaced"); await geoLoad(); geoRender(); }
}

async function geoRunDiag(id) {
  toast("🔍 Running import diagnostics…");
  geoDiagResult = await apiPost(`/api/floefd/geometry/${id}/diagnostics`, {});
  geoActiveTab = "diagnostics";
  await geoLoad();
  geoRender();
}

async function geoRunDiagSelected() {
  const id = $("#geoDiagPart")?.value;
  if (!id) { toast("⚠️ Select a part first"); return; }
  await geoRunDiag(id);
}

async function geoHealPart(id) {
  toast("🩹 Attempting heal…");
  const d = await apiPost(`/api/floefd/geometry/${id}/heal`, {});
  if (d && d.success) {
    toast(`✅ Healed: ${d.healed_faces} faces, ${d.healed_gaps} gaps | Remaining: ${d.remaining_faces} faces, ${d.remaining_gaps} gaps`);
    await geoLoad();
    geoRender();
  }
}

async function geoHealAll() {
  toast("🩹 Healing all parts…");
  for (const g of geoList) {
    if (g.has_errors && !g.suppress && !g.disabled) {
      await apiPost(`/api/floefd/geometry/${g.id}/heal`, {});
    }
  }
  toast("✅ Heal All complete");
  await geoLoad();
  geoRender();
}

async function geoCheckAll() {
  toast("🔍 Checking all geometry…");
  geoCheckResult = await apiPost("/api/floefd/geometry/check-all", {});
  await geoLoad();
  geoRender();
}

async function geoAddLid(partId) {
  const name = prompt("Lid name:", "Lid " + (geoList.find(g => g.id === partId)?.lids?.length + 1 || 1));
  if (name === null) return;
  const type = prompt("Opening type (inlet / outlet):", "inlet");
  if (type === null) return;
  const d = await apiPost(`/api/floefd/geometry/${partId}/lid`, { name, opening_type: type });
  if (d) { toast("🔲 Lid created"); await geoLoad(); geoRender(); }
}


// ═══════════════════════════════════════════════════════════════════════════
//  anl* — L3: Analysis Setup (FloEFD Wizard — full implementation)
// ═══════════════════════════════════════════════════════════════════════════

let anlData = {};
let anlActiveTab = "project";  // project | units | analysis | fluids | solids | wall | initial | resolution | domain

async function anlLoad() {
  anlData = await apiFetch("/api/floefd/analysis-setup") || {};
}

function anlRender() {
  const tabs = [
    { id: "project",    label: "📋 Project" },
    { id: "units",      label: "📐 Units" },
    { id: "analysis",   label: "🌀 Analysis Type" },
    { id: "fluids",     label: "💧 Fluids" },
    { id: "solids",     label: "🧱 Solids" },
    { id: "wall",       label: "🧱 Wall Conditions" },
    { id: "initial",    label: "🌡️ Initial Cond." },
    { id: "resolution", label: "📊 Resolution" },
    { id: "domain",     label: "📦 Domain" },
  ];
  const tabBar = tabs.map(t =>
    `<button class="btn${anlActiveTab === t.id ? ' btn-accent' : ''}" style="font-size:11px;padding:4px 10px"
      onclick="anlActiveTab='${t.id}';anlRender()">${t.label}</button>`
  ).join("");

  let content = "";
  if (anlActiveTab === "project")     content = _anlRenderProject();
  else if (anlActiveTab === "units")  content = _anlRenderUnits();
  else if (anlActiveTab === "analysis") content = _anlRenderAnalysisType();
  else if (anlActiveTab === "fluids") content = _anlRenderFluids();
  else if (anlActiveTab === "solids") content = _anlRenderSolids();
  else if (anlActiveTab === "wall")   content = _anlRenderWallConditions();
  else if (anlActiveTab === "initial") content = _anlRenderInitialConditions();
  else if (anlActiveTab === "resolution") content = _anlRenderResolution();
  else if (anlActiveTab === "domain") content = _anlRenderDomain();

  $("#pageContent").innerHTML = `
    <div class="page-header">🌡️ Analysis Setup <span style="font-size:13px;color:var(--fg-dim);font-weight:normal">— Lecture 3 (FloEFD Wizard)</span></div>
    <p class="text-dim mb-8">
      Configure physics, materials, initial conditions, and computational domain. 
      FloEFD solves the Navier-Stokes equations using the Finite Volume Method with Partial Cells technology.
    </p>
    <div style="display:flex;gap:4px;margin-bottom:16px;flex-wrap:wrap">${tabBar}</div>
    ${content}
    <div class="btn-row mt-16">
      <button class="btn btn-accent" onclick="anlSave()">💾 Save Analysis Setup</button>
      <button class="btn" onclick="anlReset()">🔄 Reset to Defaults</button>
    </div>
  `;
}

/* ── Project Name Tab ─────────────────────────────────────────────── */
function _anlRenderProject() {
  const cfg = anlData.config || {};
  return `
    <div class="info-box mb-8">
      <strong>3 Methods for starting a FloEFD project:</strong>
      🪄 <strong>Wizard</strong> — step-by-step setup &nbsp;|&nbsp;
      📄 <strong>New</strong> — SI units, Internal, Water, zero roughness, mesh=3 &nbsp;|&nbsp;
      📋 <strong>Clone Project</strong> — copy existing settings
    </div>

    <div style="display:grid;grid-template-columns:1fr 1fr;gap:20px">
      <div>
        <h3 style="margin:0 0 12px;font-size:14px;color:var(--accent)">Project Information</h3>
        <div class="form-section">
          <label>Project Name</label>
          <input type="text" id="anlProjectName" value="${cfg.project_name || 'Project'}">
        </div>
        <div class="form-section">
          <label>Comments</label>
          <textarea id="anlProjectComments" rows="3" style="width:100%;resize:vertical">${cfg.project_comments || ''}</textarea>
        </div>
        <div class="form-section">
          <label>Configuration Name</label>
          <input type="text" id="anlConfigName" value="${cfg.configuration_name || 'Default'}">
        </div>
      </div>
      <div>
        <h3 style="margin:0 0 12px;font-size:14px;color:var(--accent)">File Structure</h3>
        <div class="info-box" style="font-size:11px;line-height:1.6">
          <strong>FloEFD leverages parametric CAD configurations:</strong>
          <ul style="margin:4px 0 0 16px;padding:0">
            <li>Configuration Manager (FloEFD Standalone)</li>
            <li>Family Tables (FloEFD for Creo)</li>
            <li>Design Table Connection (FloEFD for V5)</li>
          </ul>
          <br>
          <strong>Project files stored in numbered folders:</strong>
          <ul style="margin:4px 0 0 16px;padding:0">
            <li><code>*.cpt</code> — Mesh file</li>
            <li><code>*.fld</code> — Results + Mesh file</li>
            <li><code>*.cpt.stdout</code> — Mesh debug file</li>
            <li><code>*.stdout</code> — Results debug file</li>
          </ul>
        </div>
      </div>
    </div>
  `;
}

/* ── Unit System Tab ──────────────────────────────────────────────── */
function _anlRenderUnits() {
  const cfg = anlData.config || {};
  const unitSystems = ["CGS (cm-g-s)", "FPS (ft-lb-s)", "IPS (in-lb-s)", "NMM (mm-g-s)", "SI (m-kg-s)", "USA"];
  const tempUnits = [
    { v: "K", l: "Kelvin [K]" },
    { v: "C", l: "Celsius [°C]" },
    { v: "F", l: "Fahrenheit [°F]" },
    { v: "R", l: "Reaumur [°R]" },
    { v: "Ra", l: "Rankine [°Ra]" },
  ];
  return `
    <div class="info-box mb-8">
      Pre-defined unit systems available. Any unit can be customised.
    </div>

    <div style="display:grid;grid-template-columns:1fr 1fr;gap:20px">
      <div>
        <h3 style="margin:0 0 12px;font-size:14px;color:var(--accent)">Unit System</h3>
        <div class="form-section">
          <label>System</label>
          <select id="anlUnitSystem">
            ${unitSystems.map(u => `<option value="${u}" ${cfg.unit_system === u ? 'selected' : ''}>${u}</option>`).join('')}
          </select>
        </div>
        <div class="form-section">
          <label>Temperature Display</label>
          <select id="anlTempUnit">
            ${tempUnits.map(u => `<option value="${u.v}" ${cfg.temperature_unit === u.v ? 'selected' : ''}>${u.l}</option>`).join('')}
          </select>
        </div>
      </div>
      <div>
        <h3 style="margin:0 0 12px;font-size:14px;color:var(--accent)">Default Parameters</h3>
        <table class="data-table" style="font-size:11px">
          <thead><tr><th>Parameter</th><th>Unit</th><th>Decimals</th></tr></thead>
          <tbody>
            <tr><td>Pressure & stress</td><td>Pa</td><td>.12</td></tr>
            <tr><td>Velocity</td><td>m/s</td><td>.123</td></tr>
            <tr><td>Mass</td><td>kg</td><td>.123</td></tr>
            <tr><td>Length</td><td>m</td><td>.123</td></tr>
            <tr><td>Temperature</td><td>${cfg.temperature_unit || 'K'}</td><td>.12</td></tr>
          </tbody>
        </table>
      </div>
    </div>
  `;
}

/* ── Analysis Type Tab ────────────────────────────────────────────── */
function _anlRenderAnalysisType() {
  const d = anlData;
  const ht = d.heat_transfer || {};
  const cfg = d.config || {};
  return `
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:20px">
      <div>
        <h3 style="margin:0 0 12px;font-size:14px;color:var(--accent)">Analysis Type</h3>
        <div class="form-section">
          <div class="radio-group">
            <label><input type="radio" name="anlType" value="internal" ${d.analysis_type === "internal" ? "checked" : ""}> Internal Flow</label>
            <label><input type="radio" name="anlType" value="external" ${d.analysis_type === "external" ? "checked" : ""}> External Flow</label>
          </div>
          <div class="text-dim" style="font-size:11px;margin-top:4px">
            Internal = Defined inlets/outlets (pipes, valves, enclosures)<br>
            External = Undefined inlets/outlets (aerofoils, natural convection)
          </div>
        </div>

        <h4 style="margin:16px 0 8px;font-size:13px;color:var(--fg)">Consider Closed Cavities</h4>
        <div class="form-section">
          <label><input type="checkbox" id="anlExcludeCavities" ${cfg.exclude_cavities ? 'checked' : ''}> Exclude cavities without flow conditions</label>
          <div class="text-dim" style="font-size:10px;margin-top:2px">Removes voids between screw threads, etc. Saves calculation time.</div>
        </div>
        <div class="form-section">
          <label><input type="checkbox" id="anlExcludeInternal" ${cfg.exclude_internal_space ? 'checked' : ''}> Exclude internal space (External only)</label>
        </div>
        <div class="form-section">
          <label>Reference Axis</label>
          <select id="anlRefAxis" style="width:80px">
            <option value="X" ${cfg.reference_axis === 'X' ? 'selected' : ''}>X</option>
            <option value="Y" ${cfg.reference_axis === 'Y' ? 'selected' : ''}>Y</option>
            <option value="Z" ${cfg.reference_axis === 'Z' ? 'selected' : ''}>Z</option>
          </select>
          <span class="text-dim" style="font-size:10px;margin-left:8px">Default face reference for BCs</span>
        </div>
      </div>

      <div>
        <h3 style="margin:0 0 12px;font-size:14px;color:var(--accent)">Physical Features</h3>
        <div style="border:1px solid var(--border);border-radius:var(--radius);overflow:hidden">
          <table class="param-table" style="font-size:12px">
            <tbody>
              <tr>
                <td><strong>Heat conduction in solids</strong></td>
                <td style="width:50px;text-align:center"><input type="checkbox" id="anlHeatCond" ${ht.heat_conduction_in_solids ? 'checked' : ''}></td>
              </tr>
              <tr style="background:var(--surface0)">
                <td style="padding-left:24px">└ Heat conduction in solids only</td>
                <td style="text-align:center"><input type="checkbox" id="anlHeatCondOnly" ${ht.heat_conduction_solids_only ? 'checked' : ''}></td>
              </tr>
              <tr>
                <td><strong>Radiation</strong></td>
                <td style="text-align:center"><input type="checkbox" id="anlRadiation" ${ht.radiation_enabled ? 'checked' : ''}></td>
              </tr>
              <tr style="background:var(--surface0)">
                <td style="padding-left:24px">└ Environment radiation</td>
                <td style="text-align:center"><input type="checkbox" id="anlRadEnv" ${ht.radiation_environment ? 'checked' : ''}></td>
              </tr>
              <tr style="background:var(--surface0)">
                <td style="padding-left:24px">└ Solar radiation</td>
                <td style="text-align:center"><input type="checkbox" id="anlRadSolar" ${ht.radiation_solar ? 'checked' : ''}></td>
              </tr>
              <tr style="background:var(--surface0)">
                <td style="padding-left:24px">└ Absorption in solids</td>
                <td style="text-align:center"><input type="checkbox" id="anlRadAbsorb" ${ht.radiation_absorption ? 'checked' : ''}></td>
              </tr>
              <tr>
                <td><strong>Time-dependent</strong> (Transient)</td>
                <td style="text-align:center"><input type="checkbox" id="anlTimeDep" ${cfg.time_dependent ? 'checked' : ''}></td>
              </tr>
              <tr>
                <td><strong>Gravity</strong> (Natural convection)</td>
                <td style="text-align:center"><input type="checkbox" id="anlGravity" ${cfg.gravity_enabled ? 'checked' : ''}></td>
              </tr>
              <tr>
                <td><strong>Rotation</strong> (Axisymmetric devices)</td>
                <td style="text-align:center"><input type="checkbox" id="anlRotation" ${cfg.rotation_enabled ? 'checked' : ''}></td>
              </tr>
            </tbody>
          </table>
        </div>

        <div id="anlGravityOpts" style="margin-top:8px;${cfg.gravity_enabled ? '' : 'display:none'}">
          <label style="font-size:11px">Gravity Vector (m/s²):</label>
          <div class="input-row" style="gap:4px">
            <input type="number" id="anlGravX" value="${cfg.gravity_x ?? 0}" style="width:60px" step="any">
            <input type="number" id="anlGravY" value="${cfg.gravity_y ?? -9.81}" style="width:60px" step="any">
            <input type="number" id="anlGravZ" value="${cfg.gravity_z ?? 0}" style="width:60px" step="any">
          </div>
        </div>

        <div class="info-box mt-8" style="font-size:11px">
          <strong>Heat Conduction Modes:</strong><br>
          • Unticked → Flow Only<br>
          • Ticked → Flow and Heat Transfer<br>
          • Solids Only → Heat Transfer Only (no flow)
        </div>
      </div>
    </div>
  `;
}

/* ── Default Fluids Tab ───────────────────────────────────────────── */
function _anlRenderFluids() {
  const cfg = anlData.config || {};
  const categories = cfg.fluid_categories || ["Gases", "Liquids", "Non-Newtonian Liquids", "Compressible Liquids", "Real Gases", "Steam", "Combustible Mixtures"];
  const commonFluids = [
    { cat: "Gases", items: ["Air", "Nitrogen", "Oxygen", "CO2", "Helium", "Argon", "Methane"] },
    { cat: "Liquids", items: ["Water", "Ethanol", "Glycol", "Oil (generic)", "Coolant"] },
    { cat: "Non-Newtonian", items: ["Blood", "Polymer melt", "Slurry"] },
  ];
  const selected = cfg.selected_fluids || ["air"];

  return `
    <div class="info-box mb-8">
      Select fluid(s) for the analysis. Mixed flow analysis supported. Activate additional flow options as needed.
    </div>

    <div style="display:grid;grid-template-columns:1fr 1fr;gap:20px">
      <div>
        <h3 style="margin:0 0 12px;font-size:14px;color:var(--accent)">Fluid Categories</h3>
        <div style="border:1px solid var(--border);border-radius:var(--radius);max-height:200px;overflow-y:auto">
          ${categories.map(c => `<div style="padding:6px 10px;border-bottom:1px solid var(--border);font-size:12px;cursor:pointer" class="hover-highlight">📁 ${c}</div>`).join('')}
        </div>

        <h4 style="margin:16px 0 8px;font-size:13px">Common Fluids</h4>
        ${commonFluids.map(g => `
          <div style="margin-bottom:8px">
            <strong style="font-size:11px;color:var(--fg-dim)">${g.cat}:</strong>
            <div style="display:flex;flex-wrap:wrap;gap:4px;margin-top:4px">
              ${g.items.map(f => `<button class="btn" style="font-size:10px;padding:2px 8px;${selected.includes(f.toLowerCase()) ? 'background:var(--accent);color:var(--bg)' : ''}" onclick="anlToggleFluid('${f.toLowerCase()}')">${f}</button>`).join('')}
            </div>
          </div>
        `).join('')}
      </div>

      <div>
        <h3 style="margin:0 0 12px;font-size:14px;color:var(--accent)">Project Fluids</h3>
        <div style="border:1px solid var(--border);border-radius:var(--radius);min-height:100px;padding:8px;background:var(--surface0)">
          ${selected.length ? selected.map(f => `<span style="display:inline-block;background:var(--accent);color:var(--bg);padding:2px 8px;border-radius:4px;font-size:11px;margin:2px">${f} ✕</span>`).join('') : '<span class="text-dim" style="font-size:11px">No fluids selected</span>'}
        </div>

        <h4 style="margin:16px 0 8px;font-size:13px">Flow Characteristics</h4>
        <div class="form-section">
          <label>Flow Type</label>
          <select id="anlFluidType">
            <option value="laminar" ${cfg.fluid_type === 'laminar' ? 'selected' : ''}>Laminar</option>
            <option value="turbulent" ${cfg.fluid_type === 'turbulent' ? 'selected' : ''}>Turbulent</option>
            <option value="laminar_and_turbulent" ${cfg.fluid_type === 'laminar_and_turbulent' ? 'selected' : ''}>Laminar and Turbulent</option>
          </select>
        </div>

        <h4 style="margin:16px 0 8px;font-size:13px">Additional Flow Options</h4>
        <div class="form-section">
          <label><input type="checkbox" id="anlCavitation" ${cfg.flow_options_cavitation ? 'checked' : ''}> Cavitation</label>
        </div>
        <div class="form-section">
          <label><input type="checkbox" id="anlHumidity" ${cfg.flow_options_humidity ? 'checked' : ''}> Humidity</label>
        </div>
      </div>
    </div>
  `;
}

/* ── Default Solids Tab ───────────────────────────────────────────── */
function _anlRenderSolids() {
  const cfg = anlData.config || {};
  const categories = cfg.solid_categories || ["Alloys", "Building Materials", "Ceramics", "Glasses and Minerals", "IC Packages", "Laminates", "Metals", "Non-Isotropic", "Polymers", "Semiconductors", "User Defined"];
  const commonSolids = [
    { cat: "Metals", items: ["Aluminum", "Copper", "Steel", "Iron", "Brass", "Titanium"] },
    { cat: "Ceramics", items: ["Alumina", "Silicon Carbide", "Glass"] },
    { cat: "Polymers", items: ["ABS", "Nylon", "PEEK", "Epoxy", "FR4"] },
  ];
  const selected = cfg.selected_solids || ["aluminum"];

  return `
    <div class="info-box mb-8">
      Select solid material(s) for heat conduction analysis. Used for default assignments.
    </div>

    <div style="display:grid;grid-template-columns:1fr 1fr;gap:20px">
      <div>
        <h3 style="margin:0 0 12px;font-size:14px;color:var(--accent)">Solid Categories</h3>
        <div style="border:1px solid var(--border);border-radius:var(--radius);max-height:200px;overflow-y:auto">
          ${categories.map(c => `<div style="padding:6px 10px;border-bottom:1px solid var(--border);font-size:12px;cursor:pointer" class="hover-highlight">📁 ${c}</div>`).join('')}
        </div>

        <h4 style="margin:16px 0 8px;font-size:13px">Common Solids</h4>
        ${commonSolids.map(g => `
          <div style="margin-bottom:8px">
            <strong style="font-size:11px;color:var(--fg-dim)">${g.cat}:</strong>
            <div style="display:flex;flex-wrap:wrap;gap:4px;margin-top:4px">
              ${g.items.map(s => `<button class="btn" style="font-size:10px;padding:2px 8px;${selected.includes(s.toLowerCase()) ? 'background:var(--accent);color:var(--bg)' : ''}" onclick="anlToggleSolid('${s.toLowerCase()}')">${s}</button>`).join('')}
            </div>
          </div>
        `).join('')}
      </div>

      <div>
        <h3 style="margin:0 0 12px;font-size:14px;color:var(--accent)">Project Solids</h3>
        <div style="border:1px solid var(--border);border-radius:var(--radius);min-height:100px;padding:8px;background:var(--surface0)">
          ${selected.length ? selected.map(s => `<span style="display:inline-block;background:var(--green);color:var(--bg);padding:2px 8px;border-radius:4px;font-size:11px;margin:2px">${s} ✕</span>`).join('') : '<span class="text-dim" style="font-size:11px">No solids selected</span>'}
        </div>

        <div class="form-section mt-16">
          <label>Default Solid</label>
          <select id="anlDefaultSolid">
            ${selected.map(s => `<option value="${s}">${s}</option>`).join('')}
          </select>
        </div>

        <div class="info-box mt-8" style="font-size:11px">
          Solids in the model will be auto-assigned to these materials based on component names or can be manually assigned.
        </div>
      </div>
    </div>
  `;
}

/* ── Wall Conditions Tab ──────────────────────────────────────────── */
function _anlRenderWallConditions() {
  const cfg = anlData.config || {};
  const ht = anlData.heat_transfer || {};
  return `
    <div class="info-box mb-8">
      Define default wall conditions for all boundary surfaces. Can be overridden per-surface later.
    </div>

    <div style="display:grid;grid-template-columns:1fr 1fr;gap:20px">
      <div>
        <h3 style="margin:0 0 12px;font-size:14px;color:var(--accent)">Thermal Conditions</h3>
        <div class="form-section">
          <label>Default outer wall thermal condition</label>
          <select id="anlWallThermal">
            <option value="adiabatic" ${cfg.wall_thermal_condition === 'adiabatic' ? 'selected' : ''}>Adiabatic wall</option>
            <option value="htc" ${cfg.wall_thermal_condition === 'htc' ? 'selected' : ''}>Heat transfer coefficient</option>
            <option value="heat_gen_rate" ${cfg.wall_thermal_condition === 'heat_gen_rate' ? 'selected' : ''}>Heat generation rate</option>
            <option value="surface_heat_gen" ${cfg.wall_thermal_condition === 'surface_heat_gen' ? 'selected' : ''}>Surface heat generation rate</option>
            <option value="temperature" ${cfg.wall_thermal_condition === 'temperature' ? 'selected' : ''}>Wall temperature</option>
          </select>
        </div>

        <div class="info-box" style="font-size:11px;margin-top:8px">
          <strong>Wall Thermal Options:</strong>
          <ul style="margin:4px 0 0 12px;padding:0;line-height:1.6">
            <li><strong>Adiabatic</strong> — no heat transfer through outer wall</li>
            <li><strong>HTC</strong> — heat flow calculated using defined h</li>
            <li><strong>Heat gen rate</strong> — heat flow in/out of system (W)</li>
            <li><strong>Surface heat gen</strong> — heat per unit area (W/m²)</li>
            <li><strong>Wall temperature</strong> — fixed outer wall temperature</li>
          </ul>
        </div>

        <h4 style="margin:16px 0 8px;font-size:13px">Radiation (if enabled)</h4>
        <div class="form-section">
          <label>Default wall radiative surface</label>
          <select id="anlWallRadSurf">
            <option value="blackbody" ${cfg.wall_radiative_surface === 'blackbody' ? 'selected' : ''}>Blackbody wall</option>
            <option value="whitebody" ${cfg.wall_radiative_surface === 'whitebody' ? 'selected' : ''}>Whitebody wall</option>
            <option value="emissivity" ${cfg.wall_radiative_surface === 'emissivity' ? 'selected' : ''}>Custom emissivity</option>
          </select>
        </div>
        <div class="form-section">
          <label>Default outer wall radiative surface</label>
          <select id="anlWallOuterRad">
            <option value="blackbody" ${cfg.wall_outer_radiative === 'blackbody' ? 'selected' : ''}>Blackbody wall</option>
            <option value="whitebody" ${cfg.wall_outer_radiative === 'whitebody' ? 'selected' : ''}>Whitebody wall</option>
          </select>
        </div>
        <div class="form-section">
          <label>Default Emissivity</label>
          <input type="number" id="anlEmissivity" value="${ht.default_emissivity ?? 0.9}" step="0.01" min="0" max="1">
        </div>
      </div>

      <div>
        <h3 style="margin:0 0 12px;font-size:14px;color:var(--accent)">Surface Roughness</h3>
        <div class="form-section">
          <label>Roughness Rz (µm)</label>
          <input type="number" id="anlRoughness" value="${cfg.wall_roughness ?? 0}" step="0.1" min="0">
        </div>
        <div class="info-box" style="font-size:11px">
          <strong>Roughness (Rz) equation:</strong><br>
          <div style="font-family:monospace;margin:4px 0">Rz = (Σ|y<sub>pmi</sub>| + Σ|y<sub>vmi</sub>|) / 5</div>
          <em>Randomized dent distribution based on average peak-to-valley height.</em>
          <br><br>
          Default value = 0 (smooth wall)
        </div>

        <h4 style="margin:16px 0 8px;font-size:13px">Dependency</h4>
        <div class="text-dim" style="font-size:11px">
          Values can be made coordinate-dependent or time-dependent using the Dependency button in the full wizard.
        </div>
      </div>
    </div>
  `;
}

/* ── Initial Conditions Tab ───────────────────────────────────────── */
function _anlRenderInitialConditions() {
  const cfg = anlData.config || {};
  return `
    <div class="info-box mb-8">
      Set initial field values for the simulation. Can be user-defined or transferred from previous results.
    </div>

    <div style="display:grid;grid-template-columns:1fr 1fr;gap:20px">
      <div>
        <h3 style="margin:0 0 12px;font-size:14px;color:var(--accent)">Parameter Definition</h3>
        <div class="form-section">
          <div class="radio-group">
            <label><input type="radio" name="anlICDef" value="user_defined" ${cfg.ic_definition === 'user_defined' ? 'checked' : ''}> User defined</label>
            <label><input type="radio" name="anlICDef" value="transferred" ${cfg.ic_definition === 'transferred' ? 'checked' : ''}> Transferred results</label>
          </div>
        </div>

        <h4 style="margin:16px 0 8px;font-size:13px">Thermodynamic Parameters</h4>
        <div class="form-section">
          <label>Pressure (Pa)</label>
          <input type="number" id="anlICPressure" value="${cfg.ic_pressure ?? 101325}" step="any">
        </div>
        <div class="form-section">
          <label>Temperature (K)</label>
          <input type="number" id="anlICTemp" value="${cfg.ic_temperature ?? 293.2}" step="any">
        </div>

        <h4 style="margin:16px 0 8px;font-size:13px">Velocity Parameters</h4>
        <div class="form-section">
          <label>Velocity (m/s) [X, Y, Z]</label>
          <div class="input-row" style="gap:4px">
            <input type="number" id="anlICVelX" value="${cfg.ic_velocity_x ?? 0}" step="any">
            <input type="number" id="anlICVelY" value="${cfg.ic_velocity_y ?? 0}" step="any">
            <input type="number" id="anlICVelZ" value="${cfg.ic_velocity_z ?? 0}" step="any">
          </div>
        </div>
      </div>

      <div>
        <h4 style="margin:0 0 8px;font-size:13px">Turbulence Parameters</h4>
        <div class="form-section">
          <label>Turbulence Intensity</label>
          <input type="number" id="anlICTurbInt" value="${cfg.ic_turbulence_intensity ?? 0.01}" step="0.001" min="0" max="1">
        </div>
        <div class="form-section">
          <label>Turbulence Length Scale (m)</label>
          <input type="number" id="anlICTurbLen" value="${cfg.ic_turbulence_length ?? 0.001}" step="any">
        </div>

        <h4 style="margin:16px 0 8px;font-size:13px">Solid Parameters</h4>
        <div class="form-section">
          <label>Initial Solid Temperature (K)</label>
          <input type="number" id="anlICSolidTemp" value="${cfg.ic_solid_temperature ?? 293.2}" step="any">
        </div>

        <div class="info-box mt-16" style="font-size:11px">
          <strong>Tip:</strong> For natural convection problems, ensure initial temperature differs from wall/ambient to trigger flow.
        </div>
      </div>
    </div>
  `;
}

/* ── Results & Geometry Resolution Tab ────────────────────────────── */
function _anlRenderResolution() {
  const cfg = anlData.config || {};
  const level = cfg.result_resolution_level ?? 3;
  return `
    <div class="info-box mb-8">
      Slider bar determines mesh density and convergence accuracy. Higher values = finer mesh, longer solve time.
    </div>

    <div style="display:grid;grid-template-columns:1fr 1fr;gap:20px">
      <div>
        <h3 style="margin:0 0 12px;font-size:14px;color:var(--accent)">Result Resolution</h3>
        <div class="form-section">
          <label>Resolution Level (1-8)</label>
          <div style="display:flex;align-items:center;gap:12px">
            <input type="range" id="anlResLevel" min="1" max="8" value="${level}" style="flex:1"
              oninput="document.getElementById('anlResLevelVal').textContent=this.value">
            <span id="anlResLevelVal" style="font-size:18px;font-weight:700;color:var(--accent);min-width:20px">${level}</span>
          </div>
          <div style="display:flex;justify-content:space-between;font-size:10px;color:var(--fg-dim);margin-top:4px">
            <span>1 (Coarse)</span>
            <span style="color:var(--red)">⬛⬛⬛</span>
            <span>4</span>
            <span style="color:var(--green)">⬛⬛⬛⬛⬛</span>
            <span>8 (Fine)</span>
          </div>
        </div>

        <div class="info-box mt-8" style="font-size:11px;border-left-color:var(--peach)">
          <strong>Trade-off:</strong>
          <ul style="margin:4px 0 0 12px;padding:0">
            <li>Level 1-3: Fast results, lower accuracy</li>
            <li>Level 4-5: Balanced (recommended for most cases)</li>
            <li>Level 6-8: High accuracy, longer computation</li>
          </ul>
        </div>
      </div>

      <div>
        <h3 style="margin:0 0 12px;font-size:14px;color:var(--accent)">Geometry Resolution</h3>
        <div class="form-section">
          <label><input type="checkbox" id="anlManualGap" ${cfg.manual_gap_size ? 'checked' : ''}> Manual specification of minimum gap size</label>
        </div>
        <div class="form-section" id="anlGapSizeRow" style="${cfg.manual_gap_size ? '' : 'display:none'}">
          <label>Minimum gap size (m)</label>
          <input type="number" id="anlMinGap" value="${cfg.min_gap_size ?? 0}" step="any">
        </div>

        <div class="form-section">
          <label><input type="checkbox" id="anlManualWall" ${cfg.manual_wall_thickness ? 'checked' : ''}> Manual specification of minimum wall thickness</label>
        </div>
        <div class="form-section" id="anlWallThickRow" style="${cfg.manual_wall_thickness ? '' : 'display:none'}">
          <label>Minimum wall thickness (m)</label>
          <input type="number" id="anlMinWall" value="${cfg.min_wall_thickness ?? 0}" step="any">
        </div>

        <div class="form-section">
          <label><input type="checkbox" id="anlNarrowChannel" ${cfg.narrow_channel_refinement ? 'checked' : ''}> Advanced narrow channel refinement</label>
        </div>
        <div class="form-section">
          <label><input type="checkbox" id="anlOptThinWalls" ${cfg.optimize_thin_walls ? 'checked' : ''}> Optimize thin walls resolution</label>
        </div>
      </div>
    </div>
  `;
}

/* ── Computational Domain Tab ─────────────────────────────────────── */
function _anlRenderDomain() {
  const cd = anlData.computational_domain || {};
  const d = anlData;
  return `
    <div class="info-box mb-8">
      <strong>Internal Analysis:</strong> Domain sized automatically to fluid region.<br>
      <strong>External Analysis:</strong> Manually size based on flow type — hit "Reset" after BCs applied.
    </div>

    <div style="display:grid;grid-template-columns:1fr 1fr;gap:20px">
      <div>
        <h3 style="margin:0 0 12px;font-size:14px;color:var(--accent)">Domain Extents</h3>
        <div style="border:1px solid var(--border);border-radius:var(--radius);overflow:hidden">
          <table class="param-table">
            <thead><tr><th>Axis</th><th>Min (m)</th><th>Max (m)</th><th>Symmetry</th></tr></thead>
            <tbody>
              <tr>
                <td><strong>X</strong></td>
                <td><input type="number" id="anlXMin" value="${cd.x_min ?? -0.5}" step="any"></td>
                <td><input type="number" id="anlXMax" value="${cd.x_max ?? 0.5}" step="any"></td>
                <td style="text-align:center"><input type="checkbox" id="anlSymX" ${cd.symmetry_x ? "checked" : ""}></td>
              </tr>
              <tr>
                <td><strong>Y</strong></td>
                <td><input type="number" id="anlYMin" value="${cd.y_min ?? -0.5}" step="any"></td>
                <td><input type="number" id="anlYMax" value="${cd.y_max ?? 0.5}" step="any"></td>
                <td style="text-align:center"><input type="checkbox" id="anlSymY" ${cd.symmetry_y ? "checked" : ""}></td>
              </tr>
              <tr>
                <td><strong>Z</strong></td>
                <td><input type="number" id="anlZMin" value="${cd.z_min ?? -0.5}" step="any"></td>
                <td><input type="number" id="anlZMax" value="${cd.z_max ?? 0.5}" step="any"></td>
                <td style="text-align:center"><input type="checkbox" id="anlSymZ" ${cd.symmetry_z ? "checked" : ""}></td>
              </tr>
            </tbody>
          </table>
        </div>
        <div style="margin-top:8px;font-size:12px;color:var(--fg-dim)">
          Domain Volume: <strong>${(cd.volume ?? 1).toFixed(4)} m³</strong>
        </div>
        <button class="btn mt-8" onclick="anlResetDomain()">🔄 Reset Domain to Geometry</button>
      </div>

      <div>
        <h3 style="margin:0 0 12px;font-size:14px;color:var(--accent)">Sizing Guidelines</h3>
        <div class="info-box" style="font-size:11px;line-height:1.7">
          <strong>Natural Convection</strong> (Electronics Cooling):
          <ul style="margin:2px 0 8px 12px;padding:0">
            <li>1× geometry envelope — sides and below</li>
            <li>2× geometry envelope — above (rising plume)</li>
          </ul>
          <strong>Forced Flow</strong> (External Aerodynamics):
          <ul style="margin:2px 0 8px 12px;padding:0">
            <li>10-20× geometry — above, below, ahead</li>
            <li>20-30× geometry — behind (wake region)</li>
          </ul>
        </div>

        <h4 style="margin:16px 0 8px;font-size:13px">Symmetry & Periodic</h4>
        <div class="text-dim" style="font-size:11px">
          Use symmetry planes to reduce domain size by 50% per plane.<br>
          Periodic conditions available for repeating geometry patterns.
        </div>
      </div>
    </div>
  `;
}

/* ── Analysis Setup Actions ───────────────────────────────────────── */
function anlToggleFluid(f) {
  anlData.config = anlData.config || {};
  anlData.config.selected_fluids = anlData.config.selected_fluids || [];
  const arr = anlData.config.selected_fluids;
  const idx = arr.indexOf(f);
  if (idx >= 0) arr.splice(idx, 1);
  else arr.push(f);
  anlRender();
}

function anlToggleSolid(s) {
  anlData.config = anlData.config || {};
  anlData.config.selected_solids = anlData.config.selected_solids || [];
  const arr = anlData.config.selected_solids;
  const idx = arr.indexOf(s);
  if (idx >= 0) arr.splice(idx, 1);
  else arr.push(s);
  anlRender();
}

function anlResetDomain() {
  toast("🔄 Domain reset to geometry bounding box");
}

function anlReset() {
  if (confirm("Reset all analysis settings to defaults?")) {
    toast("🔄 Settings reset to defaults");
    anlData = {};
    anlRender();
  }
}

async function anlSave() {
  const ht = anlData.heat_transfer || {};
  const body = {
    analysis_type: $('input[name="anlType"]:checked')?.value || "internal",
    heat_transfer: {
      conduction_enabled: !!$("#anlHeatCond")?.checked,
      convection_enabled: ht.convection_enabled ?? true,
      radiation_enabled: !!$("#anlRadiation")?.checked,
      radiation_model: ht.radiation_model || "none",
      default_solid_conductivity: ht.default_solid_conductivity ?? 200,
      default_htc: ht.default_htc ?? 10,
      default_emissivity: parseFloat($("#anlEmissivity")?.value || 0.9),
      heat_conduction_in_solids: !!$("#anlHeatCond")?.checked,
      heat_conduction_solids_only: !!$("#anlHeatCondOnly")?.checked,
      radiation_environment: !!$("#anlRadEnv")?.checked,
      radiation_solar: !!$("#anlRadSolar")?.checked,
      radiation_absorption: !!$("#anlRadAbsorb")?.checked,
    },
    computational_domain: {
      x_min: parseFloat($("#anlXMin")?.value || -0.5),
      x_max: parseFloat($("#anlXMax")?.value || 0.5),
      y_min: parseFloat($("#anlYMin")?.value || -0.5),
      y_max: parseFloat($("#anlYMax")?.value || 0.5),
      z_min: parseFloat($("#anlZMin")?.value || -0.5),
      z_max: parseFloat($("#anlZMax")?.value || 0.5),
      symmetry_x: !!$("#anlSymX")?.checked,
      symmetry_y: !!$("#anlSymY")?.checked,
      symmetry_z: !!$("#anlSymZ")?.checked,
    },
    config: {
      project_name: $("#anlProjectName")?.value || "Project",
      project_comments: $("#anlProjectComments")?.value || "",
      configuration_name: $("#anlConfigName")?.value || "Default",
      unit_system: $("#anlUnitSystem")?.value || "SI (m-kg-s)",
      temperature_unit: $("#anlTempUnit")?.value || "K",
      exclude_cavities: !!$("#anlExcludeCavities")?.checked,
      exclude_internal_space: !!$("#anlExcludeInternal")?.checked,
      reference_axis: $("#anlRefAxis")?.value || "X",
      time_dependent: !!$("#anlTimeDep")?.checked,
      gravity_enabled: !!$("#anlGravity")?.checked,
      gravity_x: parseFloat($("#anlGravX")?.value || 0),
      gravity_y: parseFloat($("#anlGravY")?.value || -9.81),
      gravity_z: parseFloat($("#anlGravZ")?.value || 0),
      rotation_enabled: !!$("#anlRotation")?.checked,
      fluid_type: $("#anlFluidType")?.value || "laminar_and_turbulent",
      selected_fluids: anlData.config?.selected_fluids || ["air"],
      selected_solids: anlData.config?.selected_solids || ["aluminum"],
      flow_options_cavitation: !!$("#anlCavitation")?.checked,
      flow_options_humidity: !!$("#anlHumidity")?.checked,
      wall_thermal_condition: $("#anlWallThermal")?.value || "adiabatic",
      wall_radiative_surface: $("#anlWallRadSurf")?.value || "blackbody",
      wall_outer_radiative: $("#anlWallOuterRad")?.value || "blackbody",
      wall_roughness: parseFloat($("#anlRoughness")?.value || 0),
      ic_pressure: parseFloat($("#anlICPressure")?.value || 101325),
      ic_temperature: parseFloat($("#anlICTemp")?.value || 293.2),
      ic_velocity_x: parseFloat($("#anlICVelX")?.value || 0),
      ic_velocity_y: parseFloat($("#anlICVelY")?.value || 0),
      ic_velocity_z: parseFloat($("#anlICVelZ")?.value || 0),
      ic_turbulence_intensity: parseFloat($("#anlICTurbInt")?.value || 0.01),
      ic_turbulence_length: parseFloat($("#anlICTurbLen")?.value || 0.001),
      ic_solid_temperature: parseFloat($("#anlICSolidTemp")?.value || 293.2),
      ic_definition: $('input[name="anlICDef"]:checked')?.value || "user_defined",
      result_resolution_level: parseInt($("#anlResLevel")?.value || 3),
      manual_gap_size: !!$("#anlManualGap")?.checked,
      min_gap_size: parseFloat($("#anlMinGap")?.value || 0),
      manual_wall_thickness: !!$("#anlManualWall")?.checked,
      min_wall_thickness: parseFloat($("#anlMinWall")?.value || 0),
      narrow_channel_refinement: !!$("#anlNarrowChannel")?.checked,
      optimize_thin_walls: !!$("#anlOptThinWalls")?.checked,
    },
  };
  const d = await apiPut("/api/floefd/analysis-setup", body);
  if (d && d.success) toast("✅ Analysis setup saved");
}


// ═══════════════════════════════════════════════════════════════════════════
//  ftr* — L4a: Features (Standard FloEFD Features — full implementation)
// ═══════════════════════════════════════════════════════════════════════════

let ftrData = {};
let ftrActiveTab = "overview";

const FTR_TABS = [
  { id: "overview",    label: "🗂️ Overview" },
  { id: "comp-ctrl",   label: "🔧 Component Control" },
  { id: "fluid-sub",   label: "💧 Fluid Subdomains" },
  { id: "rotating",    label: "⚙️ Rotating Regions" },
  { id: "solid-mat",   label: "🧱 Solid Materials" },
  { id: "bc",          label: "🔲 Boundary Conditions" },
  { id: "fans",        label: "🌀 Fans" },
  { id: "heat-src",    label: "🔥 Heat Sources" },
  { id: "rad-surf",    label: "☀️ Radiative Surfaces" },
  { id: "rad-src",     label: "💡 Radiation Sources" },
  { id: "contact",     label: "🔗 Contact Resistance" },
  { id: "tec",         label: "❄️ Thermoelectric" },
  { id: "heatsink",    label: "🏗️ Heatsink Sim" },
  { id: "porous",      label: "🧽 Porous Media" },
  { id: "perf-plate",  label: "⬚ Perforated Plates" },
  { id: "thermal-jt",  label: "🔌 Thermal Joints" },
  { id: "init-cond",   label: "🌡️ Initial Conditions" },
  { id: "eng-db",      label: "📚 Eng. Database" },
  { id: "3d-editor",   label: "🎮 3D Editor" },
];

async function ftrLoad() {
  ftrData = await apiFetch("/api/floefd/features/summary") || {};
}

function ftrRender() {
  const tabBar = FTR_TABS.map(t =>
    `<button class="btn${ftrActiveTab === t.id ? ' btn-accent' : ''}" style="font-size:10px;padding:3px 8px"
      onclick="ftrActiveTab='${t.id}';ftrRender()">${t.label}</button>`
  ).join("");

  let content = "";
  switch (ftrActiveTab) {
    case "overview":    content = _ftrOverview(); break;
    case "comp-ctrl":   content = _ftrCompCtrl(); break;
    case "fluid-sub":   content = _ftrFluidSub(); break;
    case "rotating":    content = _ftrRotating(); break;
    case "solid-mat":   content = _ftrSolidMat(); break;
    case "bc":          content = _ftrBC(); break;
    case "fans":        content = _ftrFans(); break;
    case "heat-src":    content = _ftrHeatSrc(); break;
    case "rad-surf":    content = _ftrRadSurf(); break;
    case "rad-src":     content = _ftrRadSrc(); break;
    case "contact":     content = _ftrContact(); break;
    case "tec":         content = _ftrTEC(); break;
    case "heatsink":    content = _ftrHeatsink(); break;
    case "porous":      content = _ftrPorous(); break;
    case "perf-plate":  content = _ftrPerfPlate(); break;
    case "thermal-jt":  content = _ftrThermalJt(); break;
    case "init-cond":   content = _ftrInitCond(); break;
    case "eng-db":      content = _ftrEngDB(); break;
    case "3d-editor":   content = _ftr3DEditor(); break;
  }

  $("#pageContent").innerHTML = `
    <div class="page-header">🔧 Features <span style="font-size:13px;color:var(--fg-dim);font-weight:normal">— Lecture 4a (Standard FloEFD Features)</span></div>
    <p class="text-dim mb-8">Features applied to bodies and/or faces on CAD geometry. Customise Feature Tree via right-click → Customize Tree.</p>
    <div style="display:flex;gap:3px;margin-bottom:12px;flex-wrap:wrap">${tabBar}</div>
    ${content}
  `;

  // Init 3D editor if that tab is active
  if (ftrActiveTab === "3d-editor") {
    setTimeout(() => _ftr3DInit(), 100);
  }
}

/* ── Overview ──────────────────────────────────────────────────────── */
function _ftrOverview() {
  const feats = [
    { icon: "📦", name: "Computational Domain", count: 1, desc: "3D/2D sim, boundary types: Default/Symmetry/Periodicity" },
    { icon: "🔧", name: "Component Control", count: (ftrData.component_controls||[]).length, desc: "Enable/disable CAD components" },
    { icon: "💧", name: "Fluid Subdomains", count: (ftrData.fluid_subdomains||[]).length, desc: "Different fluids in closed cavities" },
    { icon: "⚙️", name: "Rotating Regions", count: (ftrData.rotating_regions||[]).length, desc: "Axisymmetric fans/pumps/impellers" },
    { icon: "🧱", name: "Solid Materials", count: (ftrData.solid_materials||[]).length, desc: "Material assignments with T-dependent props" },
    { icon: "🔲", name: "Boundary Conditions", count: (ftrData.boundary_conditions||[]).length, desc: "Flow/Pressure openings, Wall conditions" },
    { icon: "🌀", name: "Fans", count: (ftrData.fan_features||[]).length, desc: "Axial/Radial with fan curves" },
    { icon: "🔥", name: "Heat Sources", count: (ftrData.heat_source_features||[]).length, desc: "Volume & Surface sources" },
    { icon: "☀️", name: "Radiative Surfaces", count: (ftrData.radiative_surfaces||[]).length, desc: "Emissivity, specularity, solar" },
    { icon: "💡", name: "Radiation Sources", count: (ftrData.radiation_sources||[]).length, desc: "Diffusive & Solar through openings" },
    { icon: "🔗", name: "Contact Resistances", count: (ftrData.contact_resistances||[]).length, desc: "Rc = dc/λc at interfaces" },
    { icon: "❄️", name: "Thermoelectric Coolers", count: (ftrData.thermoelectric_coolers||[]).length, desc: "Peltier effect — hot/cold side" },
    { icon: "🏗️", name: "Heatsink Simulations", count: (ftrData.heatsink_simulations||[]).length, desc: "Compact fan+heatsink model" },
    { icon: "🧽", name: "Porous Media", count: (ftrData.porous_media||[]).length, desc: "Effective pressure drop replacement" },
    { icon: "⬚", name: "Perforated Plates", count: (ftrData.perforated_plates||[]).length, desc: "Thin plates with holes" },
    { icon: "🔌", name: "Thermal Joints", count: (ftrData.thermal_joints||[]).length, desc: "Heat transfer between disjoint parts" },
    { icon: "🌡️", name: "Initial Conditions", count: (ftrData.initial_conditions_local||[]).length, desc: "Local IC overrides" },
  ];
  return `
    <div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:8px">
      ${feats.map(f => `
        <div style="border:1px solid var(--border);border-radius:var(--radius);padding:10px;background:var(--surface0);cursor:pointer"
          class="hover-highlight">
          <div style="display:flex;justify-content:space-between;align-items:center">
            <span style="font-size:14px">${f.icon} <strong>${f.name}</strong></span>
            <span class="badge" style="background:var(--accent);color:var(--bg);font-size:11px;padding:1px 6px;border-radius:8px">${f.count}</span>
          </div>
          <div class="text-dim" style="font-size:11px;margin-top:4px">${f.desc}</div>
        </div>
      `).join("")}
    </div>
  `;
}

/* ── Generic feature table builder ─────────────────────────────────── */
function _ftrTable(title, items, columns, apiSeg, addFields) {
  const rows = items.map(item => `<tr>
    ${columns.map(c => `<td>${c.render ? c.render(item) : (item[c.key] ?? '')}</td>`).join('')}
    <td style="text-align:center">
      <button class="btn" style="font-size:10px;padding:2px 6px;color:var(--red)" onclick="ftrDelete('${apiSeg}','${item.id}')">🗑️</button>
    </td>
  </tr>`).join('');

  const formFields = addFields.map(f => `
    <div style="display:inline-flex;align-items:center;gap:4px;margin-right:8px">
      <label style="font-size:11px">${f.label}:</label>
      ${f.type === 'select'
        ? `<select id="ftrAdd_${f.key}" style="font-size:11px">${f.options.map(o => `<option value="${o}">${o}</option>`).join('')}</select>`
        : `<input type="${f.type || 'text'}" id="ftrAdd_${f.key}" value="${f.default || ''}" style="font-size:11px;width:${f.width || '100px'}">`
      }
    </div>
  `).join('');

  return `
    <h3 style="margin:0 0 8px;font-size:14px;color:var(--accent)">${title}</h3>
    <div style="border:1px solid var(--border);border-radius:var(--radius);overflow:hidden;max-height:300px;overflow-y:auto">
      <table class="data-table" style="font-size:11px">
        <thead><tr>${columns.map(c => `<th>${c.header}</th>`).join('')}<th style="width:40px">Del</th></tr></thead>
        <tbody>${rows || '<tr><td colspan="99" class="text-dim" style="text-align:center;padding:16px">No items yet</td></tr>'}</tbody>
      </table>
    </div>
    <div style="margin-top:8px;display:flex;flex-wrap:wrap;align-items:center;gap:4px">
      ${formFields}
      <button class="btn btn-accent" style="font-size:11px;padding:3px 10px" onclick="ftrAdd('${apiSeg}')">+ Add</button>
    </div>
  `;
}

async function ftrAdd(apiSeg) {
  const inputs = $$(`[id^="ftrAdd_"]`);
  const body = {};
  inputs.forEach(el => {
    const key = el.id.replace("ftrAdd_", "");
    body[key] = el.type === 'number' ? parseFloat(el.value) : el.type === 'checkbox' ? el.checked : el.value;
  });
  await apiPost(`/api/floefd/features/${apiSeg}`, body);
  await ftrLoad();
  ftrRender();
  toast("✅ Added");
}

async function ftrDelete(apiSeg, fid) {
  await apiFetch(`/api/floefd/features/${apiSeg}/${fid}`, { method: "DELETE" });
  await ftrLoad();
  ftrRender();
  toast("🗑️ Deleted");
}

/* ── Component Control ─────────────────────────────────────────────── */
function _ftrCompCtrl() {
  const items = ftrData.component_controls || [];
  return `
    <div class="info-box mb-8" style="font-size:12px">
      <strong>Component Control</strong> — Turn on/off CAD components. Visible in CAD but invisible to FloEFD.
      CAD assembly does not fail when parts are removed.<br>
      Disabled parts can be used for: Volume Heat Sources, Porous Media, Rotating Regions, Local Initial Mesh, Volume/Surface Goals.
    </div>
    ${_ftrTable("Components", items,
      [{header:"Name", key:"name"}, {header:"Enabled", render: o => o.enabled ? '✅' : '❌'}, {header:"Heat Src", render: o => o.use_for_heat_source ? '✅' : '—'}, {header:"Porous", render: o => o.use_for_porous_media ? '✅' : '—'}],
      "component-controls",
      [{key:"name", label:"Name", default:"Part-1"}, {key:"enabled", label:"Enabled", type:"checkbox", default:true}]
    )}
  `;
}

/* ── Fluid Subdomains ──────────────────────────────────────────────── */
function _ftrFluidSub() {
  const items = ftrData.fluid_subdomains || [];
  return `
    <div class="info-box mb-8" style="font-size:12px">
      <strong>Fluid Subdomain</strong> — Used when fluid cavities with a different fluid are present.
      Must be a closed internal space. Separate BCs for each subdomain.<br>
      <strong>Applications:</strong> Heat Exchangers, Cold Plates, Incandescent Lighting (Argon/Neon).
    </div>
    ${_ftrTable("Fluid Subdomains", items,
      [{header:"Name", key:"name"}, {header:"Fluid Type", key:"fluid_type"}, {header:"P (Pa)", key:"pressure"}, {header:"T (K)", key:"temperature"}],
      "fluid-subdomains",
      [{key:"name", label:"Name", default:"Subdomain-1"}, {key:"fluid_type", label:"Type", type:"select", options:["Gases / Real Gases / Steam","Liquids","Non-Newtonian"]}, {key:"pressure", label:"P", type:"number", default:"101325"}, {key:"temperature", label:"T", type:"number", default:"293.15"}]
    )}
  `;
}

/* ── Rotating Regions ──────────────────────────────────────────────── */
function _ftrRotating() {
  const items = ftrData.rotating_regions || [];
  return `
    <div class="info-box mb-8" style="font-size:12px">
      <strong>Rotating Regions</strong> — Must be axisymmetric. If gravity enabled, rotational axis must be parallel to gravity.<br>
      Rotation axis determined by right-hand-rule. Negative RPM = opposite direction.<br>
      <strong>Supported:</strong> Centrifugal & Axial (NOT positive displacement).<br>
      <strong>Placement:</strong> Avoid fluid/fluid interfaces except for inlet/outlet faces.
      Shrouded → RR boundary within shroud. Unshrouded → within volute wall.
    </div>
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:16px">
      <div>
        ${_ftrTable("Rotating Regions", items,
          [{header:"Name", key:"name"}, {header:"Type", key:"rotation_type"}, {header:"RPM", key:"angular_velocity_rpm"}, {header:"Axis", key:"rotation_axis"}],
          "rotating-regions",
          [{key:"name", label:"Name", default:"Impeller-1"}, {key:"rotation_type", label:"Type", type:"select", options:["centrifugal","axial"]}, {key:"angular_velocity_rpm", label:"RPM", type:"number", default:"3000"}, {key:"rotation_axis", label:"Axis", type:"select", options:["X","Y","Z"]}]
        )}
      </div>
      <div>
        <h4 style="margin:0 0 8px;font-size:13px;color:var(--accent)">Cavitation (Water Pump)</h4>
        <div class="info-box" style="font-size:11px">
          Occurs when local pressure drops below saturated vapour pressure.
          Bubbles collapse supersonically causing damage.<br>
          FloEFD has a <strong>hybrid cavitation solver</strong>: compressible (vapor) + incompressible (liquid).
        </div>
      </div>
    </div>
  `;
}

/* ── Solid Materials ───────────────────────────────────────────────── */
function _ftrSolidMat() {
  const items = ftrData.solid_materials || [];
  return `
    <div class="info-box mb-8" style="font-size:12px">
      <strong>Solid Materials</strong> — Applied to parts/bodies. Temperature-dependent properties only.<br>
      Conductivity types: Isotropic, Unidirectional, Axisymmetrical/Biaxial, Orthotropic (coord system needed).
    </div>
    ${_ftrTable("Solid Materials", items,
      [{header:"Name", key:"name"}, {header:"ρ (kg/m³)", key:"density"}, {header:"k (W/m·K)", key:"thermal_conductivity"}, {header:"Type", key:"conductivity_type"}, {header:"Tmelt (K)", key:"melting_temperature"}],
      "solid-materials",
      [{key:"name", label:"Name", default:"Aluminum"}, {key:"density", label:"ρ", type:"number", default:"2688.9"}, {key:"thermal_conductivity", label:"k", type:"number", default:"237"}, {key:"conductivity_type", label:"Cond.", type:"select", options:["isotropic","unidirectional","axisymmetric","orthotropic"]}]
    )}
  `;
}

/* ── Boundary Conditions ───────────────────────────────────────────── */
function _ftrBC() {
  const items = ftrData.boundary_conditions || [];
  return `
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:16px">
      <div>
        <h3 style="margin:0 0 8px;font-size:14px;color:var(--accent)">Flow Opening</h3>
        <div class="info-box" style="font-size:11px;margin-bottom:8px">
          Primary method of introducing/removing mass.<br>
          Types: Inlet Mass Flow, Inlet Volume Flow, Inlet Velocity, Outlet Mass/Volume/Velocity.<br>
          Normal / Swirl / 3D Vector. Fully Developed Flow option.
        </div>
        <h3 style="margin:12px 0 8px;font-size:14px;color:var(--accent)">Pressure Opening</h3>
        <div class="info-box" style="font-size:11px;margin-bottom:8px">
          <strong>Environment Pressure</strong> — total P for inlets, static P for outlets.<br>
          <strong>Static Pressure</strong> / <strong>Total Pressure</strong>.<br>
          + Temperature definition + Turbulence parameters.
        </div>
        <h3 style="margin:12px 0 8px;font-size:14px;color:var(--accent)">Wall Condition</h3>
        <div class="info-box" style="font-size:11px">
          <strong>Real Wall</strong> — Temperature, HTC, Roughness.<br>
          <strong>Ideal Wall</strong> — Adiabatic, Frictionless.<br>
          <strong>Outer Wall</strong> (Internal Only) — Wall temp, HTC.<br>
          <strong>Wall Motion</strong> — Linear velocity (floor) / Angular velocity (wheel).
        </div>
      </div>
      <div>
        ${_ftrTable("Boundary Conditions", items,
          [{header:"Name", key:"name"}, {header:"Type", key:"bc_type"}, {header:"P (Pa)", key:"pressure"}, {header:"T (K)", key:"temperature"}, {header:"Wall", key:"wall_type"}],
          "component-controls",
          [{key:"name", label:"Name", default:"BC-1"}, {key:"bc_type", label:"Type", type:"select", options:["wall","inlet","outlet","opening","symmetry"]}]
        )}
      </div>
    </div>
  `;
}

/* ── Fans ──────────────────────────────────────────────────────────── */
function _ftrFans() {
  const items = ftrData.fan_features || [];
  return `
    <div class="info-box mb-8" style="font-size:12px">
      <strong>Fans</strong> — 3 Types: Axial, Radial, Fan Curve. Import fan curves (mass/volume flow rate).
      Paste Excel tables into fan curve editor.<br>
      <strong>Transient:</strong> Toggle option appears. Goal-dependent on/off with control value + dead band.<br>
      <strong>Fixed Flow Fan tip:</strong> Use Fan Curve type with fixed VFR over large pressure range.
    </div>
    ${_ftrTable("Fan Features", items,
      [{header:"Name", key:"name"}, {header:"Type", key:"fan_type"}, {header:"ω (rad/s)", key:"rotor_speed"}, {header:"D_out (m)", key:"outer_diameter"}, {header:"D_hub (m)", key:"hub_diameter"}, {header:"Dir", key:"rotation_direction"}],
      "fan-features",
      [{key:"name", label:"Name", default:"Fan-1"}, {key:"fan_type", label:"Type", type:"select", options:["axial","radial","fan_curve"]}, {key:"rotor_speed", label:"Speed", type:"number", default:"0"}, {key:"outer_diameter", label:"D_out", type:"number", default:"0.1"}]
    )}
  `;
}

/* ── Heat Sources ──────────────────────────────────────────────────── */
function _ftrHeatSrc() {
  const items = ftrData.heat_source_features || [];
  return `
    <div class="info-box mb-8" style="font-size:12px">
      <strong>Heat Sources</strong> — Volume Sources (enabled/disabled bodies, Heat Conduction in Solids enabled) &
      Surface Sources (material defined).<br>
      Parameters: Heat Generation Rate (W), Volumetric (W/m³), Fixed Temperature (°C, volume only).<br>
      Multiple bodies → power divided by number of bodies (not volume).<br>
      <strong>Transient:</strong> Toggle with goal-dependent on/off. Applications: Thermal shutdown in electronics.
    </div>
    ${_ftrTable("Heat Sources", items,
      [{header:"Name", key:"name"}, {header:"Type", key:"source_type"}, {header:"Param", key:"parameter_type"}, {header:"Q (W)", key:"heat_generation_rate"}, {header:"Toggle", key:"toggle_mode"}],
      "heat-source-features",
      [{key:"name", label:"Name", default:"Chip-1"}, {key:"source_type", label:"Type", type:"select", options:["volume","surface"]}, {key:"parameter_type", label:"Param", type:"select", options:["heat_generation_rate","volumetric_heat_gen","fixed_temperature"]}, {key:"heat_generation_rate", label:"Q(W)", type:"number", default:"5"}]
    )}
  `;
}

/* ── Radiative Surfaces ────────────────────────────────────────────── */
function _ftrRadSurf() {
  const items = ftrData.radiative_surfaces || [];
  return `
    <div class="info-box mb-8" style="font-size:12px">
      <strong>Radiative Surface</strong> — Type: Wall (within model) or Wall-to-Ambient.<br>
      <strong>Specularity Coefficient:</strong> fraction of specularly reflected radiation.<br>
      <strong>Emissivity:</strong> Q = εσT⁴ (Stefan-Boltzmann).<br>
      <strong>Solar Absorptance:</strong> fraction of incident solar radiation absorbed.
    </div>
    ${_ftrTable("Radiative Surfaces", items,
      [{header:"Name", key:"name"}, {header:"Type", key:"surface_type"}, {header:"ε", key:"emissivity"}, {header:"Spec.", key:"specularity"}, {header:"Solar Abs.", key:"solar_absorptance"}],
      "radiative-surfaces",
      [{key:"name", label:"Name", default:"RadSurf-1"}, {key:"surface_type", label:"Type", type:"select", options:["wall","wall_to_ambient"]}, {key:"emissivity", label:"ε", type:"number", default:"0.9"}, {key:"specularity", label:"Spec", type:"number", default:"0"}]
    )}
  `;
}

/* ── Radiation Sources ─────────────────────────────────────────────── */
function _ftrRadSrc() {
  const items = ftrData.radiation_sources || [];
  return `
    <div class="info-box mb-8" style="font-size:12px">
      <strong>Radiation Sources</strong> — Heating through openings in the model.<br>
      <strong>Diffusive:</strong> Blackbody (ε=1) radiating at specified Power, Intensity, or Temperature.<br>
      <strong>Solar:</strong> Directional radiation along (X,Y,Z) vector at specified Power/Intensity/Temperature.
    </div>
    ${_ftrTable("Radiation Sources", items,
      [{header:"Name", key:"name"}, {header:"Type", key:"radiation_type"}, {header:"Param", key:"parameter_type"}, {header:"Power (W)", key:"power"}, {header:"T (K)", key:"temperature"}],
      "radiation-sources",
      [{key:"name", label:"Name", default:"RadSrc-1"}, {key:"radiation_type", label:"Type", type:"select", options:["diffusive","solar"]}, {key:"parameter_type", label:"Param", type:"select", options:["power","intensity","temperature"]}, {key:"power", label:"P(W)", type:"number", default:"100"}]
    )}
  `;
}

/* ── Contact Resistances ───────────────────────────────────────────── */
function _ftrContact() {
  const items = ftrData.contact_resistances || [];
  return `
    <div class="info-box mb-8" style="font-size:12px">
      <strong>Contact Resistance</strong> — Thermal resistance at solid/solid and solid/fluid boundaries.<br>
      <strong>Formula:</strong> R<sub>c</sub> = d<sub>c</sub> / λ<sub>c</sub> (thickness / conductivity).<br>
      Types: Direct Resistance value (m²·K/W) or Material/Thickness specification.<br>
      Option: Apply to solid/solid only.
    </div>
    ${_ftrTable("Contact Resistances", items,
      [{header:"Name", key:"name"}, {header:"Type", key:"resistance_type"}, {header:"Rc (m²K/W)", key:"thermal_resistance"}, {header:"d (m)", key:"contact_thickness"}, {header:"λ (W/mK)", key:"contact_conductivity"}, {header:"S/S Only", render: o => o.apply_solid_solid_only ? '✅' : '—'}],
      "contact-resistances",
      [{key:"name", label:"Name", default:"Contact-1"}, {key:"resistance_type", label:"Type", type:"select", options:["resistance","material_thickness"]}, {key:"thermal_resistance", label:"Rc", type:"number", default:"0.001"}]
    )}
  `;
}

/* ── Thermoelectric Coolers ────────────────────────────────────────── */
function _ftrTEC() {
  const items = ftrData.thermoelectric_coolers || [];
  return `
    <div class="info-box mb-8" style="font-size:12px">
      <strong>Thermoelectric Cooler (TEC)</strong> — Peltier Effect: Hot/Cold side + DC Joule heating.
      CAD cuboid required. Specify hot & cold side faces.<br>
      Parameters: Q<sub>max</sub> (max pumped heat at i<sub>max</sub>), ΔT<sub>max</sub>,
      i<sub>max</sub> (max current), V<sub>max</sub> (max voltage).
    </div>
    ${_ftrTable("TEC Modules", items,
      [{header:"Name", key:"name"}, {header:"Qmax (W)", key:"max_pumped_heat"}, {header:"ΔTmax (K)", key:"max_temperature_drop"}, {header:"imax (A)", key:"max_current"}, {header:"Vmax (V)", key:"max_voltage"}, {header:"i_op (A)", key:"operating_current"}],
      "thermoelectric-coolers",
      [{key:"name", label:"Name", default:"TEC-1"}, {key:"max_pumped_heat", label:"Qmax", type:"number", default:"30"}, {key:"max_temperature_drop", label:"ΔTmax", type:"number", default:"70"}, {key:"max_current", label:"imax", type:"number", default:"6"}, {key:"operating_current", label:"i_op", type:"number", default:"3"}]
    )}
  `;
}

/* ── Heatsink Simulations ──────────────────────────────────────────── */
function _ftrHeatsink() {
  const items = ftrData.heatsink_simulations || [];
  return `
    <div class="info-box mb-8" style="font-size:12px">
      <strong>Heatsink Simulation</strong> — Simulate a fan-cooled heat sink as a compact package.
      Replaces complex geometry with thermal resistance & pressure drop curves from Engineering Database.<br>
      Requires: inlet surface, outlet surfaces, heat generation rate, fan + heatsink DB entries.
    </div>
    ${_ftrTable("Heatsink Simulations", items,
      [{header:"Name", key:"name"}, {header:"Fan DB", key:"fan_db_name"}, {header:"HS DB", key:"heatsink_db_name"}, {header:"Q (W)", key:"heat_generation_rate"}],
      "heatsink-simulations",
      [{key:"name", label:"Name", default:"HS-1"}, {key:"fan_db_name", label:"Fan", default:""}, {key:"heatsink_db_name", label:"Heatsink", default:""}, {key:"heat_generation_rate", label:"Q(W)", type:"number", default:"10"}]
    )}
  `;
}

/* ── Porous Media ──────────────────────────────────────────────────── */
function _ftrPorous() {
  const items = ftrData.porous_media || [];
  return `
    <div class="info-box mb-8" style="font-size:12px">
      <strong>Porous Media</strong> — Replace complex geometry (mesh/gauze/foam/drilled holes) with effective pressure drop.
      Applied to disabled body. Benchmark small section to apply over larger volume.<br>
      <strong>Porosity:</strong> Volume fraction of interconnected pores.<br>
      <strong>Permeability types:</strong> Isotropic, Unidirectional, Axisymmetrical, Orthotropic.<br>
      <strong>Permeability:</strong> k = −grad(P)/(ρV). Dependencies on velocity, pore size (D), Reynolds number.
    </div>
    ${_ftrTable("Porous Media", items,
      [{header:"Name", key:"name"}, {header:"Porosity", key:"porosity"}, {header:"Perm Type", key:"permeability_type"}, {header:"Resist. (1/m)", key:"resistance"}, {header:"T₀ (K)", key:"initial_temperature"}],
      "porous-media",
      [{key:"name", label:"Name", default:"Filter-1"}, {key:"porosity", label:"φ", type:"number", default:"0.5"}, {key:"permeability_type", label:"Type", type:"select", options:["isotropic","unidirectional","axisymmetric","orthotropic"]}, {key:"resistance", label:"k", type:"number", default:"100"}]
    )}
  `;
}

/* ── Perforated Plates ─────────────────────────────────────────────── */
function _ftrPerfPlate() {
  const items = ftrData.perforated_plates || [];
  return `
    <div class="info-box mb-8" style="font-size:12px">
      <strong>Perforated Plate</strong> — Compact model for thin plate with multiple holes. No meshing overhead.<br>
      Can be added to Environment Pressure BC or Fan BC.<br>
      Defined by: Free Area Ratio, hole shape (round/rectangular/polygon), dimensions.<br>
      Pressure drop coefficient auto-calculated.
    </div>
    ${_ftrTable("Perforated Plates", items,
      [{header:"Name", key:"name"}, {header:"FAR", key:"free_area_ratio"}, {header:"Shape", key:"hole_shape"}, {header:"D/W (m)", key:"hole_diameter"}, {header:"t (m)", key:"plate_thickness"}],
      "perforated-plates",
      [{key:"name", label:"Name", default:"PerfPlate-1"}, {key:"free_area_ratio", label:"FAR", type:"number", default:"0.4"}, {key:"hole_shape", label:"Shape", type:"select", options:["round","rectangular","polygon"]}, {key:"hole_diameter", label:"D", type:"number", default:"0.005"}]
    )}
  `;
}

/* ── Thermal Joints ────────────────────────────────────────────────── */
function _ftrThermalJt() {
  const items = ftrData.thermal_joints || [];
  return `
    <div class="info-box mb-8" style="font-size:12px">
      <strong>Thermal Joint</strong> — Heat transfer between disjoint parts thermally connected.
      Simulates conduction between interacting surfaces without modelling the conductor.<br>
      Uses: Heat Transfer Coefficient or Thermal Resistance.<br>
      Faces become thermally insulated from surrounding medium — only participate in heat exchange between each other.
    </div>
    ${_ftrTable("Thermal Joints", items,
      [{header:"Name", key:"name"}, {header:"Type", key:"joint_type"}, {header:"h (W/m²K)", key:"heat_transfer_coefficient"}, {header:"Rc (m²K/W)", key:"thermal_resistance"}],
      "thermal-joints",
      [{key:"name", label:"Name", default:"Joint-1"}, {key:"joint_type", label:"Type", type:"select", options:["htc","thermal_resistance"]}, {key:"heat_transfer_coefficient", label:"h", type:"number", default:"100"}]
    )}
  `;
}

/* ── Initial Conditions (Local) ────────────────────────────────────── */
function _ftrInitCond() {
  const items = ftrData.initial_conditions_local || [];
  return `
    <div class="info-box mb-8" style="font-size:12px">
      <strong>Initial Conditions</strong> — Local overrides per face/body selection.
      Typical: Temperatures, Pressures, Velocities, Fluid Concentrations.<br>
      Can disable solid components. Specify via Face Coordinate System.
    </div>
    ${_ftrTable("Local Initial Conditions", items,
      [{header:"Name", key:"name"}, {header:"P (Pa)", key:"pressure"}, {header:"T (K)", key:"temperature"}, {header:"Vel X", render: o => (o.velocity||[0,0,0])[0]}, {header:"Vel Y", render: o => (o.velocity||[0,0,0])[1]}, {header:"Vel Z", render: o => (o.velocity||[0,0,0])[2]}],
      "initial-conditions-local",
      [{key:"name", label:"Name", default:"IC-1"}, {key:"pressure", label:"P", type:"number", default:"101325"}, {key:"temperature", label:"T", type:"number", default:"283.15"}]
    )}
  `;
}

/* ── Engineering Database ──────────────────────────────────────────── */
function _ftrEngDB() {
  const db = ftrData.engineering_database || {};
  const cats = db.categories || [];
  const matSubs = db.material_subcategories || [];
  return `
    <div class="info-box mb-8" style="font-size:12px">
      <strong>Engineering Database</strong> — All Pre-Defined and User-Defined features stored in XML format.
      Can be placed on a central server. User-defined features stored with assembly.<br>
      Import/Export library option available. Paths configured in FloEFD Options.
    </div>
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:16px">
      <div>
        <h4 style="margin:0 0 8px;font-size:13px;color:var(--accent)">Database Categories</h4>
        <div style="border:1px solid var(--border);border-radius:var(--radius);max-height:350px;overflow-y:auto">
          ${cats.map(c => `<div style="padding:5px 10px;border-bottom:1px solid var(--border);font-size:12px">📁 ${c}</div>`).join('')}
        </div>
      </div>
      <div>
        <h4 style="margin:0 0 8px;font-size:13px;color:var(--accent)">Material Sub-categories</h4>
        <div style="border:1px solid var(--border);border-radius:var(--radius)">
          ${matSubs.map(s => `<div style="padding:5px 10px;border-bottom:1px solid var(--border);font-size:12px">🔹 ${s}</div>`).join('')}
        </div>
        <h4 style="margin:16px 0 8px;font-size:13px;color:var(--accent)">Database Paths</h4>
        <div class="form-section">
          <label style="font-size:11px">User-defined DB location</label>
          <input type="text" value="${db.user_database_path || ''}" style="font-size:11px" readonly>
        </div>
        <div class="form-section">
          <label style="font-size:11px">External databases directory</label>
          <input type="text" value="${db.external_database_dir || ''}" style="font-size:11px" readonly>
        </div>
      </div>
    </div>
  `;
}

/* ── 3D Editor ─────────────────────────────────────────────────────── */
function _ftr3DEditor() {
  return `
    <div style="display:grid;grid-template-columns:1fr 280px;gap:12px;height:520px">
      <div style="border:1px solid var(--border);border-radius:var(--radius);overflow:hidden;position:relative;background:#1a1a2e">
        <canvas id="ftr3dCanvas" style="width:100%;height:100%;display:block"></canvas>
        <div id="ftr3dInfo" style="position:absolute;top:8px;left:8px;color:#fff;font-size:11px;opacity:0.8;pointer-events:none">
          🎮 Click & drag to rotate • Scroll to zoom • Right-drag to pan
        </div>
        <div id="ftr3dAxes" style="position:absolute;bottom:8px;left:8px;color:#fff;font-size:10px;opacity:0.6">
          <span style="color:#ff4444">X</span> <span style="color:#44ff44">Y</span> <span style="color:#4444ff">Z</span>
        </div>
      </div>
      <div style="overflow-y:auto">
        <h4 style="margin:0 0 8px;font-size:13px;color:var(--accent)">🎮 3D Editor Controls</h4>
        <div class="form-section">
          <label>Geometry</label>
          <select id="ftr3dShape" onchange="_ftr3DUpdateShape()">
            <option value="box">Box (Enclosure)</option>
            <option value="cylinder">Cylinder (Pipe)</option>
            <option value="sphere">Sphere</option>
            <option value="heatsink">Heatsink</option>
            <option value="fan">Fan (Axial)</option>
            <option value="pcb">PCB Board</option>
          </select>
        </div>
        <div class="form-section">
          <label>Show</label>
          <div><label style="font-size:11px"><input type="checkbox" id="ftr3dWireframe" onchange="_ftr3DUpdateVis()"> Wireframe</label></div>
          <div><label style="font-size:11px"><input type="checkbox" id="ftr3dAxesShow" checked onchange="_ftr3DUpdateVis()"> Axes Helper</label></div>
          <div><label style="font-size:11px"><input type="checkbox" id="ftr3dGrid" checked onchange="_ftr3DUpdateVis()"> Grid</label></div>
          <div><label style="font-size:11px"><input type="checkbox" id="ftr3dDomain" onchange="_ftr3DUpdateVis()"> Comp. Domain</label></div>
        </div>
        <div class="form-section">
          <label>Color</label>
          <input type="color" id="ftr3dColor" value="#4488ff" onchange="_ftr3DUpdateColor()">
        </div>
        <div class="form-section">
          <label>Opacity</label>
          <input type="range" id="ftr3dOpacity" min="0.1" max="1" step="0.05" value="0.85" onchange="_ftr3DUpdateColor()">
        </div>
        <div class="form-section">
          <label>Domain Size</label>
          <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:4px">
            <input type="number" id="ftr3dDomX" value="1" step="0.1" style="font-size:11px" onchange="_ftr3DUpdateDomain()">
            <input type="number" id="ftr3dDomY" value="1" step="0.1" style="font-size:11px" onchange="_ftr3DUpdateDomain()">
            <input type="number" id="ftr3dDomZ" value="1" step="0.1" style="font-size:11px" onchange="_ftr3DUpdateDomain()">
          </div>
          <div style="display:flex;justify-content:space-between;font-size:9px;color:var(--fg-dim)"><span>X</span><span>Y</span><span>Z</span></div>
        </div>
        <div class="form-section">
          <label>Camera Presets</label>
          <div style="display:flex;flex-wrap:wrap;gap:4px">
            <button class="btn" style="font-size:10px;padding:2px 6px" onclick="_ftr3DCamPreset('front')">Front</button>
            <button class="btn" style="font-size:10px;padding:2px 6px" onclick="_ftr3DCamPreset('top')">Top</button>
            <button class="btn" style="font-size:10px;padding:2px 6px" onclick="_ftr3DCamPreset('right')">Right</button>
            <button class="btn" style="font-size:10px;padding:2px 6px" onclick="_ftr3DCamPreset('iso')">Isometric</button>
          </div>
        </div>
        <button class="btn btn-accent mt-8" style="width:100%" onclick="_ftr3DScreenshot()">📸 Screenshot</button>
      </div>
    </div>
  `;
}

/* ── Three.js 3D Editor Engine ─────────────────────────────────────── */
let _ftr3D = { scene: null, camera: null, renderer: null, controls: null, mainMesh: null, domainBox: null, axesHelper: null, gridHelper: null, animId: null };

function _ftr3DInit() {
  const canvas = document.getElementById("ftr3dCanvas");
  if (!canvas || _ftr3D.renderer) return;

  // Dynamically load Three.js from CDN
  if (!window.THREE) {
    const script = document.createElement("script");
    script.src = "https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js";
    script.onload = () => {
      // Load OrbitControls
      const script2 = document.createElement("script");
      script2.src = "https://cdn.jsdelivr.net/npm/three@0.128.0/examples/js/controls/OrbitControls.js";
      script2.onload = () => _ftr3DSetup(canvas);
      document.head.appendChild(script2);
    };
    document.head.appendChild(script);
  } else {
    _ftr3DSetup(canvas);
  }
}

function _ftr3DSetup(canvas) {
  const THREE = window.THREE;
  const W = canvas.clientWidth, H = canvas.clientHeight;

  // Scene
  const scene = new THREE.Scene();
  scene.background = new THREE.Color(0x1a1a2e);
  scene.fog = new THREE.FogExp2(0x1a1a2e, 0.15);

  // Camera
  const camera = new THREE.PerspectiveCamera(50, W / H, 0.01, 100);
  camera.position.set(2, 1.5, 2);
  camera.lookAt(0, 0, 0);

  // Renderer
  const renderer = new THREE.WebGLRenderer({ canvas, antialias: true });
  renderer.setSize(W, H);
  renderer.setPixelRatio(window.devicePixelRatio);
  renderer.shadowMap.enabled = true;

  // Controls
  const controls = new THREE.OrbitControls(camera, renderer.domElement);
  controls.enableDamping = true;
  controls.dampingFactor = 0.05;

  // Lights
  const ambientLight = new THREE.AmbientLight(0x404060, 0.8);
  scene.add(ambientLight);
  const dirLight = new THREE.DirectionalLight(0xffffff, 1.0);
  dirLight.position.set(5, 8, 5);
  dirLight.castShadow = true;
  scene.add(dirLight);
  const pointLight = new THREE.PointLight(0x4488ff, 0.5, 10);
  pointLight.position.set(-2, 3, -2);
  scene.add(pointLight);

  // Grid
  const gridHelper = new THREE.GridHelper(4, 20, 0x444466, 0x333355);
  scene.add(gridHelper);

  // Axes
  const axesHelper = new THREE.AxesHelper(1.5);
  scene.add(axesHelper);

  // Default geometry — box
  const geo = new THREE.BoxGeometry(0.6, 0.4, 0.8);
  const mat = new THREE.MeshPhongMaterial({ color: 0x4488ff, transparent: true, opacity: 0.85, side: THREE.DoubleSide });
  const mesh = new THREE.Mesh(geo, mat);
  mesh.position.y = 0.2;
  mesh.castShadow = true;
  mesh.receiveShadow = true;
  scene.add(mesh);

  // Domain wireframe (hidden by default)
  const domGeo = new THREE.BoxGeometry(1, 1, 1);
  const domMat = new THREE.MeshBasicMaterial({ color: 0x00ff88, wireframe: true, transparent: true, opacity: 0.3 });
  const domainBox = new THREE.Mesh(domGeo, domMat);
  domainBox.visible = false;
  domainBox.position.y = 0.5;
  scene.add(domainBox);

  _ftr3D = { scene, camera, renderer, controls, mainMesh: mesh, domainBox, axesHelper, gridHelper, animId: null };

  // Animate
  function animate() {
    _ftr3D.animId = requestAnimationFrame(animate);
    controls.update();
    renderer.render(scene, camera);
  }
  animate();

  // Resize handler
  const ro = new ResizeObserver(() => {
    const w = canvas.clientWidth, h = canvas.clientHeight;
    if (w > 0 && h > 0) {
      camera.aspect = w / h;
      camera.updateProjectionMatrix();
      renderer.setSize(w, h);
    }
  });
  ro.observe(canvas.parentElement);
}

function _ftr3DUpdateShape() {
  if (!_ftr3D.scene || !window.THREE) return;
  const THREE = window.THREE;
  const shape = $("#ftr3dShape")?.value || "box";
  const old = _ftr3D.mainMesh;
  if (old) { _ftr3D.scene.remove(old); old.geometry.dispose(); }

  let geo;
  switch (shape) {
    case "box": geo = new THREE.BoxGeometry(0.6, 0.4, 0.8); break;
    case "cylinder": geo = new THREE.CylinderGeometry(0.3, 0.3, 1.0, 32); break;
    case "sphere": geo = new THREE.SphereGeometry(0.4, 32, 32); break;
    case "heatsink": geo = _ftr3DHeatsinkGeo(); break;
    case "fan": geo = _ftr3DFanGeo(); break;
    case "pcb": geo = new THREE.BoxGeometry(1.0, 0.02, 0.6); break;
    default: geo = new THREE.BoxGeometry(0.6, 0.4, 0.8);
  }

  const color = $("#ftr3dColor")?.value || "#4488ff";
  const opacity = parseFloat($("#ftr3dOpacity")?.value || 0.85);
  const wireframe = !!$("#ftr3dWireframe")?.checked;
  const mat = new THREE.MeshPhongMaterial({ color, transparent: true, opacity, wireframe, side: THREE.DoubleSide });
  const mesh = new THREE.Mesh(geo, mat);
  mesh.position.y = 0.2;
  mesh.castShadow = true;
  _ftr3D.scene.add(mesh);
  _ftr3D.mainMesh = mesh;
}

function _ftr3DHeatsinkGeo() {
  const THREE = window.THREE;
  const group = new THREE.Group();
  // Base plate
  const base = new THREE.BoxGeometry(0.8, 0.05, 0.5);
  // Fins
  const fin = new THREE.BoxGeometry(0.02, 0.3, 0.5);
  // Return merged geometry for simplicity
  const merged = new THREE.BoxGeometry(0.8, 0.35, 0.5);
  return merged;
}

function _ftr3DFanGeo() {
  const THREE = window.THREE;
  return new THREE.CylinderGeometry(0.4, 0.4, 0.08, 32);
}

function _ftr3DUpdateVis() {
  if (!_ftr3D.scene) return;
  const wf = !!$("#ftr3dWireframe")?.checked;
  const showAxes = !!$("#ftr3dAxesShow")?.checked;
  const showGrid = !!$("#ftr3dGrid")?.checked;
  const showDomain = !!$("#ftr3dDomain")?.checked;

  if (_ftr3D.mainMesh) _ftr3D.mainMesh.material.wireframe = wf;
  if (_ftr3D.axesHelper) _ftr3D.axesHelper.visible = showAxes;
  if (_ftr3D.gridHelper) _ftr3D.gridHelper.visible = showGrid;
  if (_ftr3D.domainBox) _ftr3D.domainBox.visible = showDomain;
}

function _ftr3DUpdateColor() {
  if (!_ftr3D.mainMesh) return;
  const color = $("#ftr3dColor")?.value || "#4488ff";
  const opacity = parseFloat($("#ftr3dOpacity")?.value || 0.85);
  _ftr3D.mainMesh.material.color.set(color);
  _ftr3D.mainMesh.material.opacity = opacity;
}

function _ftr3DUpdateDomain() {
  if (!_ftr3D.domainBox || !window.THREE) return;
  const x = parseFloat($("#ftr3dDomX")?.value || 1);
  const y = parseFloat($("#ftr3dDomY")?.value || 1);
  const z = parseFloat($("#ftr3dDomZ")?.value || 1);
  _ftr3D.domainBox.scale.set(x, y, z);
  _ftr3D.domainBox.position.y = y / 2;
}

function _ftr3DCamPreset(preset) {
  if (!_ftr3D.camera || !_ftr3D.controls) return;
  const cam = _ftr3D.camera;
  switch (preset) {
    case "front": cam.position.set(0, 0, 3); break;
    case "top": cam.position.set(0, 3, 0.01); break;
    case "right": cam.position.set(3, 0, 0); break;
    case "iso": cam.position.set(2, 1.5, 2); break;
  }
  _ftr3D.controls.target.set(0, 0, 0);
  _ftr3D.controls.update();
}

function _ftr3DScreenshot() {
  if (!_ftr3D.renderer) { toast("⚠️ 3D editor not initialized"); return; }
  const link = document.createElement("a");
  link.download = "floefd_3d_screenshot.png";
  link.href = _ftr3D.renderer.domElement.toDataURL("image/png");
  link.click();
  toast("📸 Screenshot saved");
}


// ═══════════════════════════════════════════════════════════════════════════
//  fbc* — L4: FloEFD Boundary Conditions
// ═══════════════════════════════════════════════════════════════════════════

let fbcList = [];

async function fbcLoad() {
  fbcList = await apiFetch("/api/floefd/boundary-conditions") || [];
}

function fbcRender() {
  const rows = fbcList.map(bc => `
    <tr>
      <td>${bc.name}</td>
      <td><span class="badge-${bc.bc_type}">${bc.bc_type}</span></td>
      <td>${bc.bc_type === 'inlet' ? bc.velocity?.join(', ') + ' m/s' :
           bc.bc_type === 'outlet' ? bc.pressure + ' Pa' :
           bc.wall_thermal || '—'}</td>
      <td>${bc.temperature} K</td>
      <td>
        <button class="btn" style="padding:2px 8px;font-size:11px" onclick="fbcEdit('${bc.id}')">✏️</button>
        <button class="btn" style="padding:2px 8px;font-size:11px;color:var(--red)" onclick="fbcDelete('${bc.id}')">✕</button>
      </td>
    </tr>
  `).join("") || '<tr><td colspan="5" class="text-dim">No boundary conditions defined.</td></tr>';

  $("#pageContent").innerHTML = `
    <div class="page-header">🔲 Boundary Conditions (FloEFD)</div>
    <p class="text-dim mb-8">
      Define boundary conditions for fluid flow and heat transfer. Includes wall thermal conditions,
      inlet/outlet specifications, and radiative surface properties.
    </p>

    <table class="data-table mb-8">
      <thead><tr><th>Name</th><th>Type</th><th>Key Setting</th><th>Temperature</th><th></th></tr></thead>
      <tbody>${rows}</tbody>
    </table>

    <h3 style="margin:16px 0 12px;font-size:14px;color:var(--accent)">Add Boundary Condition</h3>
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:16px">
      <div>
        <div class="form-section">
          <label>Name</label>
          <input type="text" id="fbcName" value="BC ${fbcList.length + 1}">
        </div>
        <div class="form-section">
          <label>Type</label>
          <select id="fbcType" onchange="fbcToggleFields()">
            <option value="wall">Wall</option>
            <option value="inlet">Velocity Inlet</option>
            <option value="outlet">Pressure Outlet</option>
            <option value="opening">Opening</option>
            <option value="symmetry">Symmetry</option>
            <option value="periodic">Periodic</option>
          </select>
        </div>
        <div class="form-section">
          <label>Temperature (K)</label>
          <input type="number" id="fbcTemp" value="293.15" step="any">
        </div>
      </div>
      <div>
        <div id="fbcInletFields" style="display:none">
          <div class="form-section">
            <label>Velocity (m/s) [X, Y, Z]</label>
            <div class="input-row">
              <input type="number" id="fbcVelX" value="0" step="any">
              <input type="number" id="fbcVelY" value="0" step="any">
              <input type="number" id="fbcVelZ" value="1" step="any">
            </div>
          </div>
        </div>
        <div id="fbcOutletFields" style="display:none">
          <div class="form-section">
            <label>Pressure (Pa)</label>
            <input type="number" id="fbcPressure" value="101325" step="any">
          </div>
        </div>
        <div id="fbcWallFields">
          <div class="form-section">
            <label>Wall Thermal Condition</label>
            <select id="fbcWallThermal">
              <option value="adiabatic">Adiabatic</option>
              <option value="heat_flux">Heat Flux (W/m²)</option>
              <option value="heat_transfer_coeff">Heat Transfer Coefficient</option>
              <option value="temperature">Fixed Temperature</option>
            </select>
          </div>
          <div class="form-section">
            <label>Wall Roughness (m)</label>
            <input type="number" id="fbcRoughness" value="0" step="0.0001" min="0">
          </div>
          <div class="form-section">
            <label>Emissivity</label>
            <input type="number" id="fbcEmissivity" value="0.9" step="0.01" min="0" max="1">
          </div>
        </div>
      </div>
    </div>
    <div class="btn-row">
      <button class="btn btn-accent" onclick="fbcAdd()">➕ Add Boundary Condition</button>
    </div>
  `;
}

function fbcToggleFields() {
  const type = $("#fbcType")?.value;
  const show = (id, vis) => { const el = $(id); if (el) el.style.display = vis ? "" : "none"; };
  show("#fbcInletFields", type === "inlet");
  show("#fbcOutletFields", type === "outlet");
  show("#fbcWallFields", type === "wall");
}

async function fbcAdd() {
  const type = $("#fbcType")?.value || "wall";
  const body = {
    name: ($("#fbcName")?.value || "").trim() || "BC",
    bc_type: type,
    temperature: parseFloat($("#fbcTemp")?.value || 293.15),
  };
  if (type === "inlet") {
    body.velocity = [
      parseFloat($("#fbcVelX")?.value || 0),
      parseFloat($("#fbcVelY")?.value || 0),
      parseFloat($("#fbcVelZ")?.value || 1),
    ];
  }
  if (type === "outlet") {
    body.pressure = parseFloat($("#fbcPressure")?.value || 101325);
  }
  if (type === "wall") {
    body.wall_thermal = $("#fbcWallThermal")?.value || "adiabatic";
    body.wall_roughness = parseFloat($("#fbcRoughness")?.value || 0);
    body.emissivity = parseFloat($("#fbcEmissivity")?.value || 0.9);
  }
  const d = await apiPost("/api/floefd/boundary-conditions", body);
  if (d) { toast("✅ BC added"); await fbcLoad(); fbcRender(); }
}

async function fbcEdit(id) {
  const bc = fbcList.find(b => b.id === id);
  if (!bc) { toast("⚠️ BC not found"); return; }

  // Scroll to form and populate fields
  const setVal = (sel, v) => { const el = $(sel); if (el) el.value = v; };
  setVal("#fbcName", bc.name);
  setVal("#fbcType", bc.bc_type);
  fbcToggleFields();
  setVal("#fbcTemp", bc.temperature);
  if (bc.bc_type === "inlet" && bc.velocity) {
    setVal("#fbcVelX", bc.velocity[0]);
    setVal("#fbcVelY", bc.velocity[1]);
    setVal("#fbcVelZ", bc.velocity[2]);
  }
  if (bc.bc_type === "outlet") setVal("#fbcPressure", bc.pressure || 101325);
  if (bc.bc_type === "wall") {
    setVal("#fbcWallThermal", bc.wall_thermal || "adiabatic");
    setVal("#fbcRoughness", bc.wall_roughness || 0);
    setVal("#fbcEmissivity", bc.emissivity || 0.9);
  }

  // Replace "Add" button with "Save Changes"
  const btnRow = document.querySelector("#pageContent .btn-row");
  if (btnRow) {
    btnRow.innerHTML = `
      <button class="btn btn-accent" onclick="fbcSaveEdit('${id}')">💾 Save Changes</button>
      <button class="btn" onclick="fbcRender()">Cancel</button>
    `;
  }
  toast("✏️ Edit fields below, then save");
}

async function fbcSaveEdit(id) {
  const type = $("#fbcType")?.value || "wall";
  const body = {
    name: ($("#fbcName")?.value || "").trim() || "BC",
    bc_type: type,
    temperature: parseFloat($("#fbcTemp")?.value || 293.15),
  };
  if (type === "inlet") {
    body.velocity = [
      parseFloat($("#fbcVelX")?.value || 0),
      parseFloat($("#fbcVelY")?.value || 0),
      parseFloat($("#fbcVelZ")?.value || 1),
    ];
  }
  if (type === "outlet") body.pressure = parseFloat($("#fbcPressure")?.value || 101325);
  if (type === "wall") {
    body.wall_thermal = $("#fbcWallThermal")?.value || "adiabatic";
    body.wall_roughness = parseFloat($("#fbcRoughness")?.value || 0);
    body.emissivity = parseFloat($("#fbcEmissivity")?.value || 0.9);
  }
  const d = await apiPut(`/api/floefd/boundary-conditions/${id}`, body);
  if (d && !d.error) { toast("✅ BC updated"); await fbcLoad(); fbcRender(); }
}

async function fbcDelete(id) {
  const d = await apiFetch(`/api/floefd/boundary-conditions/${id}`, { method: "DELETE" });
  if (d && d.success) { toast("🗑 BC removed"); await fbcLoad(); fbcRender(); }
}


// ═══════════════════════════════════════════════════════════════════════════
//  fmsh* — L5: FloEFD Meshing (comprehensive)
// ═══════════════════════════════════════════════════════════════════════════

let fmshData = {};
let fmshLocalMeshes = [];
let fmshStudy = [];
let fmshTab = 0;

const FMSH_TABS = [
  "Overview", "Base Mesh", "Basic Mesh (Manual)", "Control Planes",
  "Solid/Fluid Interface", "Refining Cells", "Narrow Channels",
  "Close Thin Slots", "Local Initial Mesh", "Solution Adaptive",
  "Mesh Study", "Methodology", "Statistics"
];

async function fmshLoad() {
  const [settings, lms, study] = await Promise.all([
    apiFetch("/api/floefd/mesh"),
    apiFetch("/api/floefd/mesh/local-meshes"),
    apiFetch("/api/floefd/mesh/study"),
  ]);
  fmshData = settings || {};
  fmshLocalMeshes = lms || [];
  fmshStudy = study || [];
}

function fmshRender() {
  const d = fmshData;
  const tabs = FMSH_TABS.map((t, i) =>
    `<button class="${i === fmshTab ? 'tab active' : 'tab'}" onclick="fmshTab=${i};fmshRender()">${t}</button>`
  ).join("");

  let body = "";
  switch (fmshTab) {
    case 0: body = _fmshOverview(); break;
    case 1: body = _fmshBaseMesh(); break;
    case 2: body = _fmshBasicMesh(); break;
    case 3: body = _fmshControlPlanes(); break;
    case 4: body = _fmshSolidFluid(); break;
    case 5: body = _fmshRefiningCells(); break;
    case 6: body = _fmshNarrowCh(); break;
    case 7: body = _fmshThinSlots(); break;
    case 8: body = _fmshLocalMesh(); break;
    case 9: body = _fmshAdaptive(); break;
    case 10: body = _fmshStudyTab(); break;
    case 11: body = _fmshMethodology(); break;
    case 12: body = _fmshStats(); break;
  }

  $("#pageContent").innerHTML = `
    <div class="page-header">🔷 Meshing (L5)</div>
    <p class="text-dim mb-8">
      Meshing is the <strong>most critical aspect</strong> of any CFD analysis. Poor Mesh = Poor Results.
      FloEFD uses structured Cartesian immersed-body mesh with Partial Cells technology.
    </p>
    <div class="tab-bar" style="flex-wrap:wrap">${tabs}</div>
    <div style="margin-top:16px">${body}</div>
  `;
}

/* ─── 0. Overview ─────────────────────────────────────────────────── */
function _fmshOverview() {
  const d = fmshData;
  const cards = [
    { icon: "🏗️", label: "Mesh Type", value: d.mesh_type || "automatic", color: "#3b82f6" },
    { icon: "📊", label: "Level", value: `${d.initial_mesh_level || 3} / 8`, color: "#10b981" },
    { icon: "🔢", label: "Total Cells", value: (d.total_cells || 0).toLocaleString(), color: "#f59e0b" },
    { icon: "💧", label: "Fluid", value: (d.fluid_cells || 0).toLocaleString(), color: "#06b6d4" },
    { icon: "🪨", label: "Solid", value: (d.solid_cells || 0).toLocaleString(), color: "#8b5cf6" },
    { icon: "⚡", label: "Partial", value: (d.partial_cells || 0).toLocaleString(), color: "#ef4444" },
  ];
  return `
    <div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(140px,1fr));gap:12px;margin-bottom:20px">
      ${cards.map(c => `<div style="background:var(--bg-card);border:1px solid var(--border);border-radius:8px;padding:14px;border-left:4px solid ${c.color};text-align:center">
        <div style="font-size:20px">${c.icon}</div>
        <div class="text-dim" style="font-size:11px;margin:4px 0">${c.label}</div>
        <div style="font-size:18px;font-weight:700;color:${c.color}">${c.value}</div>
      </div>`).join("")}
    </div>
    <div style="background:var(--bg-card);border:1px solid var(--border);border-radius:8px;padding:16px;margin-bottom:16px">
      <h3 style="margin:0 0 8px;color:var(--accent)">What is CFD Mesh?</h3>
      <ul class="text-dim" style="font-size:13px;padding-left:20px;margin:0">
        <li><strong>Mesh / Gridding / Cells</strong> — Split geometry into cells where Navier-Stokes equations are solved</li>
        <li><strong>Finite Volume (FV)</strong>: FloEFD, FloTHERM, Fluent/CFX, Star-CCM+, OpenFOAM</li>
        <li><strong>Finite Element (FE)</strong>: Autodesk Simulation CFD, NX Flow</li>
        <li><strong>"Meshless"</strong>: X-Flow (Lattice Boltzmann), Powerflow</li>
      </ul>
    </div>
    <div style="background:var(--bg-card);border:1px solid var(--border);border-radius:8px;padding:16px">
      <h3 style="margin:0 0 8px;color:var(--accent)">FloEFD Grid Cells</h3>
      <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:12px;font-size:13px">
        <div><strong style="color:#06b6d4">💧 Fluid</strong><br>Completely in Fluid region</div>
        <div><strong style="color:#8b5cf6">🪨 Solid</strong><br>Completely in Solid region</div>
        <div><strong style="color:#ef4444">⚡ Partial</strong><br>Always at fluid-solid boundary. <strong>Core of FloEFD technology!</strong> Where wall function is applied.</div>
      </div>
    </div>
    <div class="btn-row mt-16">
      <button class="btn btn-green" onclick="fmshGenerate()">🔷 Generate Mesh</button>
    </div>
  `;
}

/* ─── 1. Base Mesh Settings ───────────────────────────────────────── */
function _fmshBaseMesh() {
  const d = fmshData;
  return `
    <div style="background:var(--bg-card);border:1px solid var(--border);border-radius:8px;padding:16px;margin-bottom:16px">
      <h3 style="margin:0 0 8px;color:var(--accent)">Global Mesh Settings</h3>
      <p class="text-dim" style="font-size:12px;margin:0">
        Default is "Result and Geometry Resolution" sliderbar. For basic users, 1–8 scale presets.
        <strong>Advanced users should disable this</strong> and use manual controls.
      </p>
    </div>
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:20px">
      <div>
        <div class="form-section">
          <label>Type</label>
          <div style="display:flex;gap:8px">
            <button class="btn ${d.mesh_type==='automatic'?'btn-accent':''}" onclick="$('#fmshMeshType').value='automatic';this.className='btn btn-accent';this.nextElementSibling.className='btn'" style="flex:1">🔧 Automatic</button>
            <button class="btn ${d.mesh_type==='manual'?'btn-accent':''}" onclick="$('#fmshMeshType').value='manual';this.className='btn btn-accent';this.previousElementSibling.className='btn'" style="flex:1">📐 Manual</button>
          </div>
          <input type="hidden" id="fmshMeshType" value="${d.mesh_type || 'automatic'}">
        </div>
        <div class="form-section">
          <label>Initial Mesh Level (1–8)</label>
          <input type="range" id="fmshLevel" min="1" max="8" value="${d.initial_mesh_level || 3}"
                 oninput="$('#fmshLevelVal').textContent=this.value" style="width:100%">
          <div style="display:flex;justify-content:space-between;font-size:11px;color:var(--fg-dim)">
            <span>1 (Coarse)</span>
            <span id="fmshLevelVal" style="font-weight:700;color:var(--accent)">${d.initial_mesh_level || 3}</span>
            <span>8 (Fine)</span>
          </div>
        </div>
        <div class="form-section">
          <label>Cell Size (m)</label>
          <input type="number" id="fmshCellSize" value="${d.cell_size || 0.0093}" step="0.001" min="0">
        </div>
      </div>
      <div>
        <div class="form-section">
          <label>Minimum Gap Size (m)</label>
          <input type="number" id="fmshGap" value="${d.min_gap_size || 0.001}" step="0.0001" min="0">
        </div>
        <div class="form-section">
          <label>Minimum Wall Thickness (m)</label>
          <input type="number" id="fmshWall" value="${d.min_wall_thickness || 0.001}" step="0.0001" min="0">
        </div>
        <div class="checkbox-row mb-8">
          <input type="checkbox" id="fmshAdvCh" ${d.advanced_channel_refinement ? "checked" : ""}>
          <span>Advanced channel refinement</span>
        </div>
        <div class="checkbox-row">
          <input type="checkbox" id="fmshShowBasic" ${d.show_basic_mesh ? "checked" : ""}>
          <span>Show basic mesh</span>
        </div>
      </div>
    </div>
    <div class="btn-row mt-16"><button class="btn btn-accent" onclick="fmshSaveBase()">💾 Save Base Mesh</button></div>
  `;
}

/* ─── 2. Basic Mesh (Manual) ──────────────────────────────────────── */
function _fmshBasicMesh() {
  const d = fmshData;
  return `
    <div style="background:var(--bg-card);border:1px solid var(--border);border-radius:8px;padding:16px;margin-bottom:16px">
      <h3 style="margin:0 0 8px;color:var(--accent)">Basic Mesh (Manual Mode)</h3>
      <ol class="text-dim" style="font-size:13px;padding-left:20px;margin:0">
        <li>Use "Show" to visualise</li>
        <li>Number of Cells (X, Y, Z) or Cell Size can be selected</li>
        <li>Use control planes (usually external analysis)</li>
      </ol>
    </div>
    <div style="display:grid;grid-template-columns:200px 1fr;gap:20px">
      <div style="background:var(--bg-card);border:1px solid var(--border);border-radius:8px;padding:16px">
        <div class="form-section"><label>Nx</label><input type="number" id="fmshNx" value="${d.nx||10}" min="1"></div>
        <div class="form-section"><label>Ny</label><input type="number" id="fmshNy" value="${d.ny||10}" min="1"></div>
        <div class="form-section"><label>Nz</label><input type="number" id="fmshNz" value="${d.nz||10}" min="1"></div>
        <div class="checkbox-row mb-8"><input type="checkbox" id="fmshKeepAR" ${d.keep_aspect_ratio!==false?"checked":""}><span>Keep Aspect Ratio</span></div>
        <div class="checkbox-row"><input type="checkbox" id="fmshShowM" ${d.show_mesh?"checked":""}><span>Show</span></div>
      </div>
      <div>
        <div style="background:var(--bg-input);border:1px solid var(--border);border-radius:4px;padding:12px;font-size:12px;font-family:monospace">
          <div style="margin-bottom:4px;font-weight:600">Grid Preview:</div>
          <div>X: ${d.nx||10} cells</div>
          <div>Y: ${d.ny||10} cells</div>
          <div>Z: ${d.nz||10} cells</div>
          <div style="margin-top:8px;color:var(--accent)">Total base cells: ${(d.nx||10)*(d.ny||10)*(d.nz||10)}</div>
        </div>
      </div>
    </div>
    <div class="btn-row mt-16"><button class="btn btn-accent" onclick="fmshSaveBasic()">💾 Save</button></div>
  `;
}

/* ─── 3. Control Planes ───────────────────────────────────────────── */
function _fmshControlPlanes() {
  const planes = fmshData.control_planes || [];
  const rows = planes.map((p, i) => `<tr>
    <td>${p.axis||"X"}</td><td>${p.min}</td><td>${p.max}</td>
    <td>${p.type||"auto"}</td><td>${p.number||""}</td><td>${p.size||""}</td><td>${p.ratio||1}</td>
    <td><button class="btn" style="padding:2px 6px;font-size:11px;color:var(--red)" onclick="fmshRemovePlane(${i})">✕</button></td>
  </tr>`).join("") || '<tr><td colspan="8" class="text-dim">No control planes defined.</td></tr>';
  return `
    <div style="background:var(--bg-card);border:1px solid var(--border);border-radius:8px;padding:16px;margin-bottom:16px">
      <h3 style="margin:0 0 8px;color:var(--accent)">Control Planes (External Analysis)</h3>
      <ul class="text-dim" style="font-size:13px;padding-left:20px;margin:0">
        <li><strong>Automatic Planes</strong> — positioned automatically</li>
        <li><strong>Fix number of cells</strong> in region</li>
        <li><strong>Specify Growth/Shrink ratio</strong></li>
      </ul>
    </div>
    <table class="data-table" style="font-size:12px"><thead><tr>
      <th>Axis</th><th>Min</th><th>Max</th><th>Type</th><th>Number</th><th>Size</th><th>Ratio</th><th></th>
    </tr></thead><tbody>${rows}</tbody></table>
    <h4 style="margin:12px 0 8px;font-size:13px">Add Control Plane</h4>
    <div style="display:flex;gap:8px;flex-wrap:wrap;align-items:flex-end">
      <div class="form-section" style="width:60px;margin:0"><label>Axis</label><select id="fmshCpAxis"><option>X</option><option>Y</option><option>Z</option></select></div>
      <div class="form-section" style="width:80px;margin:0"><label>Min (m)</label><input type="number" id="fmshCpMin" value="0" step="0.001"></div>
      <div class="form-section" style="width:80px;margin:0"><label>Max (m)</label><input type="number" id="fmshCpMax" value="0.1" step="0.001"></div>
      <div class="form-section" style="width:80px;margin:0"><label>Type</label><select id="fmshCpType"><option>auto</option><option>ratio</option><option>size</option><option>number</option></select></div>
      <div class="form-section" style="width:60px;margin:0"><label>Num</label><input type="number" id="fmshCpNum" value="22" min="1"></div>
      <div class="form-section" style="width:60px;margin:0"><label>Ratio</label><input type="number" id="fmshCpRatio" value="1" step="0.1" min="0.1"></div>
      <button class="btn btn-accent" onclick="fmshAddPlane()" style="height:34px">➕</button>
    </div>
  `;
}

/* ─── 4. Solid/Fluid Interface ────────────────────────────────────── */
function _fmshSolidFluid() {
  const d = fmshData;
  const mkSlider = (id, label, val, tip) => `
    <div class="form-section">
      <label>${label} <span class="text-dim" style="font-size:10px">${tip||""}</span></label>
      <input type="range" id="${id}" min="0" max="9" value="${val}" oninput="$('#${id}V').textContent=this.value" style="width:100%">
      <div style="display:flex;justify-content:space-between;font-size:10px;color:var(--fg-dim)">
        <span>0</span><span id="${id}V" style="font-weight:700;color:var(--accent)">${val}</span><span>9</span>
      </div>
    </div>
  `;
  return `
    <div style="background:var(--bg-card);border:1px solid var(--border);border-radius:8px;padding:16px;margin-bottom:16px">
      <h3 style="margin:0 0 8px;color:var(--accent)">Advanced Refinement — Solid/Fluid Interface</h3>
      <p class="text-dim" style="font-size:13px;margin:0">
        Defines partial cell properties. Sliderbar position denotes max number of Octree splits (Max Level = 9).
        Neighbouring cells can only vary by <strong>1 level</strong>. Octree refinement levels 0 (Base) through 5+.
      </p>
    </div>
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:20px">
      <div>
        ${mkSlider("fmshSSF", "🔴 Small Solid Feature Level", d.small_solid_feature_level||2, "MOST CRITICAL — determines if small features are captured")}
        <div class="info-box" style="font-size:11px;margin-bottom:12px">
          Recommendation: Start L=2, Max L=4. Determines if small features/bodies are captured before further refinement.
        </div>
        ${mkSlider("fmshCurv", "🔵 Curvature Refinement Level", d.curvature_refinement_level||1, "Corners and edges with large curvature")}
        <div class="form-section">
          <label>Curvature Critical Angle (rad)</label>
          <input type="number" id="fmshCurvAngle" value="${d.curvature_critical_angle||0.318}" step="0.01">
        </div>
      </div>
      <div>
        ${mkSlider("fmshTol", "🟡 Tolerance Refinement Level", d.tolerance_refinement_level||0, "Improve corners and edges in a single cell")}
        <div class="form-section">
          <label>Tolerance Value (m)</label>
          <input type="number" id="fmshTolVal" value="${d.tolerance_value||0.002325}" step="0.0001">
        </div>
        <div class="info-box" style="font-size:11px;margin-top:12px">
          <strong>Curvature Refinement:</strong> Set critical angle which cannot be exceeded in a single cell.<br>
          <strong>Tolerance Refinement:</strong> Aims to represent actual geometry. Less of an issue with version 11.<br>
          <strong>Thin walls:</strong> Cells with 3+ CVs — split further to reduce CVs. Start L=2, Max L=4.
        </div>
      </div>
    </div>
    <div class="btn-row mt-16"><button class="btn btn-accent" onclick="fmshSaveInterface()">💾 Save Interface Settings</button></div>
  `;
}

/* ─── 5. Refining Cells ───────────────────────────────────────────── */
function _fmshRefiningCells() {
  const d = fmshData;
  const mkSlider = (id, label, val, icon, color) => `
    <div style="background:var(--bg-card);border:1px solid var(--border);border-radius:8px;padding:16px;border-left:4px solid ${color}">
      <div style="font-size:14px;font-weight:600;margin-bottom:8px">${icon} ${label}</div>
      <input type="range" id="${id}" min="0" max="9" value="${val}" oninput="$('#${id}V').textContent=this.value" style="width:100%">
      <div style="display:flex;justify-content:space-between;font-size:11px;color:var(--fg-dim)">
        <span>0</span><span id="${id}V" style="font-weight:700;font-size:16px;color:${color}">${val}</span><span>9</span>
      </div>
    </div>
  `;
  return `
    <div style="background:var(--bg-card);border:1px solid var(--border);border-radius:8px;padding:16px;margin-bottom:16px">
      <h3 style="margin:0 0 8px;color:var(--accent)">Refining Cells</h3>
      <ul class="text-dim" style="font-size:13px;padding-left:20px;margin:0">
        <li>Additional controlled refinement for each cell type</li>
        <li>Set maximum level — not additional to Solid/Fluid Interface settings</li>
        <li><strong>Recommendation:</strong> Use carefully</li>
      </ul>
    </div>
    <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:16px">
      ${mkSlider("fmshRefF", "Fluid Cells", d.fluid_cells_refinement||0, "💧", "#06b6d4")}
      ${mkSlider("fmshRefS", "Solid Cells", d.solid_cells_refinement||0, "🪨", "#f59e0b")}
      ${mkSlider("fmshRefP", "Partial Cells", d.partial_cells_refinement||1, "⚡", "#ef4444")}
    </div>
    <div class="info-box" style="margin-top:16px;font-size:12px">
      <strong>Solid Cells:</strong> Up to 36 materials in a single cell. Conduction well defined & not sensitive to mesh resolution. Recommend ≤10 materials per cell.<br>
      <strong>Partial Cells:</strong> Up to 7 control volumes (CVs). Recommend ≤4 CVs non-critical, ≤2 CVs critical. Classic heatsink: 4 cells across gap (2 partial + 2 fluid).
    </div>
    <div class="btn-row mt-16"><button class="btn btn-accent" onclick="fmshSaveRefining()">💾 Save</button></div>
  `;
}

/* ─── 6. Narrow Channels ─────────────────────────────────────────── */
function _fmshNarrowCh() {
  const d = fmshData;
  return `
    <div style="background:var(--bg-card);border:1px solid var(--border);border-radius:8px;padding:16px;margin-bottom:16px">
      <h3 style="margin:0 0 8px;color:var(--accent)">Narrow Channels</h3>
      <ul class="text-dim" style="font-size:13px;padding-left:20px;margin:0">
        <li>Used to control narrow channels in a model</li>
        <li>Define what a narrow channel is</li>
        <li><strong>Recommendation:</strong> Use carefully — every two surfaces facing each other are a channel. Use max/min tolerances to ignore unnecessary ones.</li>
      </ul>
    </div>
    <div style="max-width:400px">
      <div class="checkbox-row mb-8">
        <input type="checkbox" id="fmshNchEn" ${d.narrow_channels_enabled !== false ? "checked" : ""}>
        <span style="font-weight:600">Enable Narrow Channels</span>
      </div>
      <div class="form-section"><label>Number of Cells Across Channel</label><input type="number" id="fmshNchNum" value="${d.narrow_channels_num_cells||5}" min="1"></div>
      <div class="form-section">
        <label>Refinement Level (0–9)</label>
        <input type="range" id="fmshNchLvl" min="0" max="9" value="${d.narrow_channels_refinement_level||2}" oninput="$('#fmshNchLvlV').textContent=this.value" style="width:100%">
        <div style="display:flex;justify-content:space-between;font-size:10px"><span>0</span><span id="fmshNchLvlV" style="font-weight:700;color:var(--accent)">${d.narrow_channels_refinement_level||2}</span><span>9</span></div>
      </div>
      <div class="form-section"><label>Min Tolerance (m) — 0 = auto</label><input type="number" id="fmshNchMin" value="${d.narrow_channels_min_tolerance||0}" step="0.001" min="0"></div>
      <div class="form-section"><label>Max Tolerance (m) — 0 = auto</label><input type="number" id="fmshNchMax" value="${d.narrow_channels_max_tolerance||0}" step="0.001" min="0"></div>
    </div>
    <div class="btn-row mt-16"><button class="btn btn-accent" onclick="fmshSaveNarrow()">💾 Save</button></div>
  `;
}

/* ─── 7. Close Thin Slots ─────────────────────────────────────────── */
function _fmshThinSlots() {
  const d = fmshData;
  return `
    <div style="background:var(--bg-card);border:1px solid var(--border);border-radius:8px;padding:16px;margin-bottom:16px">
      <h3 style="margin:0 0 8px;color:var(--accent)">Close Thin Slots</h3>
      <p class="text-dim" style="font-size:13px;margin:0">
        Automatically fills with solid all gaps below a tolerance level. Useful for preventing fluid from leaking through thin gaps in geometry.
      </p>
    </div>
    <div style="max-width:350px">
      <div class="checkbox-row mb-8">
        <input type="checkbox" id="fmshCtsEn" ${d.close_thin_slots_enabled ? "checked" : ""}>
        <span style="font-weight:600">Enable Close Thin Slots</span>
      </div>
      <div class="form-section"><label>Tolerance (m)</label><input type="number" id="fmshCtsTol" value="${d.close_thin_slots_tolerance||0.03}" step="0.001" min="0"></div>
    </div>
    <div class="btn-row mt-16"><button class="btn btn-accent" onclick="fmshSaveThinSlots()">💾 Save</button></div>
  `;
}

/* ─── 8. Local Initial Mesh ───────────────────────────────────────── */
function _fmshLocalMesh() {
  const rows = fmshLocalMeshes.map(lm => `<tr>
    <td>${lm.name}</td><td>${lm.target_type}</td><td>${lm.target_name||"—"}</td>
    <td>${lm.body_shape}</td><td>${lm.equidistant_level}</td><td>${lm.enabled?"✅":"❌"}</td>
    <td><button class="btn" style="padding:2px 6px;font-size:11px;color:var(--red)" onclick="fmshDeleteLM('${lm.id}')">✕</button></td>
  </tr>`).join("") || '<tr><td colspan="7" class="text-dim">No local meshes. Click Add to create one.</td></tr>';
  return `
    <div style="background:var(--bg-card);border:1px solid var(--border);border-radius:8px;padding:16px;margin-bottom:16px">
      <h3 style="margin:0 0 8px;color:var(--accent)">Local Initial Mesh</h3>
      <ul class="text-dim" style="font-size:13px;padding-left:20px;margin:0">
        <li>Apply to critical components: <strong>Surface, Edge, Vertex, CAD Body</strong></li>
        <li>Generate simple bodies (disabled) — <strong>Cuboid, Cylinder, Sphere</strong></li>
        <li>Up to 3 levels of <strong>equidistant refinement</strong> (inflation)</li>
        <li><strong>Disabled bodies</strong> can also be used for porous media, heat sources, initial conditions, goals</li>
        <li>Recommendation: Use "Refine Cells" tab to control Local Initial Mesh</li>
      </ul>
    </div>
    <table class="data-table" style="font-size:12px"><thead><tr>
      <th>Name</th><th>Target</th><th>Component</th><th>Shape</th><th>Level</th><th>On</th><th></th>
    </tr></thead><tbody>${rows}</tbody></table>
    <h4 style="margin:12px 0 8px;font-size:13px">Add Local Mesh</h4>
    <div style="display:flex;gap:8px;flex-wrap:wrap;align-items:flex-end">
      <div class="form-section" style="flex:1;min-width:120px;margin:0"><label>Name</label><input type="text" id="fmshLmName" value="LIM ${fmshLocalMeshes.length+1}"></div>
      <div class="form-section" style="width:100px;margin:0"><label>Target</label><select id="fmshLmTarget"><option>surface</option><option>edge</option><option>vertex</option><option>cad_body</option></select></div>
      <div class="form-section" style="width:100px;margin:0"><label>Shape</label><select id="fmshLmShape"><option>cuboid</option><option>cylinder</option><option>sphere</option></select></div>
      <div class="form-section" style="width:60px;margin:0"><label>Level</label><input type="number" id="fmshLmLvl" value="2" min="0" max="9"></div>
      <button class="btn btn-accent" onclick="fmshAddLM()" style="height:34px">➕ Add</button>
      <button class="btn" onclick="fmshDeleteAllLM()" style="height:34px;color:var(--red)">🗑 Delete All</button>
    </div>
  `;
}

/* ─── 9. Solution Adaptive Meshing ────────────────────────────────── */
function _fmshAdaptive() {
  const d = fmshData;
  return `
    <div style="background:var(--bg-card);border:1px solid var(--border);border-radius:8px;padding:16px;margin-bottom:16px">
      <h3 style="margin:0 0 8px;color:var(--accent)">Solution Adaptive Meshing</h3>
      <ul class="text-dim" style="font-size:13px;padding-left:20px;margin:0">
        <li>Targeted addition of mesh <strong>during solve</strong></li>
        <li>Structured Octree meshing allows easy addition of cells</li>
        <li>Automatically activated at Sliderbar Levels 6–8</li>
        <li>Based on <strong>Scalar and Vector</strong> flow gradients</li>
        <li><strong>No restarting solution!</strong></li>
      </ul>
    </div>
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:20px">
      <div>
        <div class="checkbox-row mb-8">
          <input type="checkbox" id="fmshSAEn" ${d.solution_adaptive_enabled?"checked":""}>
          <span style="font-weight:600">Enable Solution Adaptive Meshing</span>
        </div>
        <div class="form-section"><label>Refinement Level (max level of smallest cell)</label><input type="number" id="fmshSALvl" value="${d.adaptive_refinement_level||4}" min="0" max="9"></div>
        <div class="form-section"><label>Approximate Maximum Cells</label><input type="number" id="fmshSAMax" value="${d.adaptive_max_cells||2000000}" step="100000" min="0"></div>
        <div class="form-section"><label>Refinement Strategy</label>
          <select id="fmshSAStrat">
            <option ${d.adaptive_strategy==="periodic"?"selected":""}>Periodic Refinement</option>
            <option ${d.adaptive_strategy==="tabular"?"selected":""}>Tabular</option>
            <option ${d.adaptive_strategy==="manual"?"selected":""}>Manual</option>
          </select>
        </div>
      </div>
      <div>
        <div class="form-section"><label>Units</label><input type="text" value="Travels" disabled></div>
        <div class="form-section"><label>Relaxation Interval</label>
          <div style="display:flex;gap:4px;align-items:center"><span class="text-dim" style="font-size:11px">Auto</span><input type="number" id="fmshSARel" value="${d.adaptive_relaxation_interval||0.2}" step="0.1" min="0"></div>
        </div>
        <h4 style="margin:12px 0 8px;font-size:13px">Periodic Refinement Options</h4>
        <div class="form-section"><label>Start (travels)</label>
          <div style="display:flex;gap:4px;align-items:center"><span class="text-dim" style="font-size:11px">Auto</span><input type="number" id="fmshSAStart" value="${d.adaptive_start||2}" step="0.5" min="0"></div>
        </div>
        <div class="form-section"><label>Period (travels)</label>
          <div style="display:flex;gap:4px;align-items:center"><span class="text-dim" style="font-size:11px">Auto</span><input type="number" id="fmshSAPeriod" value="${d.adaptive_period||1}" step="0.5" min="0"></div>
        </div>
      </div>
    </div>
    <div class="info-box" style="margin-top:16px;font-size:12px">
      <strong>Travels:</strong> A proprietary FloEFD unit. 1 travel = flow from inlet reaches outlet. "Iterations per travel" shown in solver.
      Relaxation Interval = subsequent travels for flow to adjust to new mesh before converging.
    </div>
    <div class="btn-row mt-16"><button class="btn btn-accent" onclick="fmshSaveAdaptive()">💾 Save</button></div>
  `;
}

/* ─── 10. Mesh Study ──────────────────────────────────────────────── */
function _fmshStudyTab() {
  const rows = fmshStudy.map(e => `<tr>
    <td style="text-align:right">${e.mesh_count?.toLocaleString()}</td>
    <td style="text-align:right">${e.dp_value?.toFixed?.(1) ?? e.dp_value}</td>
    <td style="text-align:right">${e.percent_delta ? e.percent_delta.toFixed?.(1)+"%" : "—"}</td>
  </tr>`).join("") || '<tr><td colspan="3" class="text-dim">No study data. Click "Run Study" to simulate.</td></tr>';
  return `
    <div style="background:var(--bg-card);border:1px solid var(--border);border-radius:8px;padding:16px;margin-bottom:16px">
      <h3 style="margin:0 0 8px;color:var(--accent)">Mesh Study / Sensitivity</h3>
      <p class="text-dim" style="font-size:13px;margin:0">
        Increase mesh count until results become mesh-independent (<1% delta). 
        The boundary between <strong>Mesh Dependent</strong> and <strong>Mesh Independent</strong> is the target.
      </p>
    </div>
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:20px">
      <div>
        <table class="data-table"><thead><tr><th>Mesh Count</th><th>dP (Pa)</th><th>%delta</th></tr></thead><tbody>${rows}</tbody></table>
        <div class="btn-row mt-8">
          <button class="btn btn-accent" onclick="fmshRunStudy()">🔬 Run Mesh Sensitivity Study</button>
        </div>
      </div>
      <div>
        <canvas id="fmshStudyChart" width="400" height="260" style="background:var(--bg-card);border:1px solid var(--border);border-radius:4px"></canvas>
      </div>
    </div>
  `;
}

/* ─── 11. Methodology Advice ──────────────────────────────────────── */
function _fmshMethodology() {
  return `
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:20px">
      <div style="background:var(--bg-card);border:1px solid var(--border);border-radius:8px;padding:16px">
        <h3 style="margin:0 0 12px;color:var(--accent)">Basic Mesh Methodology</h3>
        <ol style="font-size:13px;padding-left:20px;margin:0;line-height:2">
          <li>Start with meshing sliderbar position <strong>3</strong></li>
          <li>Disable automatic settings</li>
          <li>Click "Show Basic Mesh"</li>
          <li>Change X,Y,Z cells by multiplying by <strong>2×, 3×, 4×</strong></li>
          <li>Small solid features = <strong>2/3/4</strong></li>
          <li>Curvature Refinement Level = <strong>2/3/4</strong></li>
          <li>Tolerance Refinement Level = <strong>2/3/4</strong></li>
          <li>Disable "Narrow Channels Refinement"</li>
        </ol>
        <h4 style="margin:16px 0 8px;font-size:13px">Local Initial Mesh</h4>
        <ol style="font-size:13px;padding-left:20px;margin:0;line-height:2">
          <li>Apply to critical components (Surface, Edge, Vertex, CAD Body)</li>
          <li>Generate simple (disabled) bodies or use inflation</li>
        </ol>
        <p style="font-size:13px;margin:12px 0 0"><strong>Generate and Check Mesh</strong> — if insufficient, change items 5,6,7 to higher level.</p>
      </div>
      <div style="background:var(--bg-card);border:1px solid var(--border);border-radius:8px;padding:16px">
        <h3 style="margin:0 0 12px;color:var(--accent)">Solution Adaptive Mesh</h3>
        <ol style="font-size:13px;padding-left:20px;margin:0;line-height:2">
          <li><strong>Finish conditions</strong> (calculation control options):
            <ul style="font-size:12px;padding-left:16px;line-height:1.6">
              <li>"If all are satisfied"</li>
              <li>Minimum Refinement Number = <strong>2</strong></li>
              <li>Goals Convergence</li>
            </ul>
          </li>
          <li><strong>Refinement</strong> (calculation control options):
            <ul style="font-size:12px;padding-left:16px;line-height:1.6">
              <li>Level = <strong>4</strong></li>
              <li>Maximum Number of cells = <strong>2,000,000</strong></li>
              <li>Refinement Strategy = <strong>Periodic</strong></li>
              <li>Periodic Refinement Options = Default</li>
            </ul>
          </li>
        </ol>
        <p style="font-size:13px;margin:16px 0 0"><strong>→ Start Solver</strong></p>
        <div style="margin-top:20px;padding:12px;background:var(--accent);color:#fff;border-radius:8px;text-align:center;font-size:14px;font-weight:700">
          Reliable Results Every Time
        </div>
      </div>
    </div>
    <div style="background:var(--bg-card);border:1px solid var(--border);border-radius:8px;padding:16px;margin-top:16px">
      <h3 style="margin:0 0 8px;color:var(--accent)">Conclusion</h3>
      <ul style="font-size:13px;padding-left:20px;margin:0;line-height:2">
        <li>Meshing is the <strong>most critical aspect</strong> of any CFD analysis — Poor Mesh = Poor Results</li>
        <li>Meshing is a trial/error process</li>
        <li>Core technology allows for Cartesian cells with multiple CV</li>
        <li>Predictable cell structure makes addition easy and fast</li>
        <li>Full access to mesh controls</li>
        <li>Solution adaptive mesh removes requirement to be a meshing expert</li>
        <li>Automatic mesh sensitivity test</li>
        <li><strong>Start coarse and let the software do the hard work!</strong></li>
      </ul>
    </div>
  `;
}

/* ─── 12. Statistics ──────────────────────────────────────────────── */
function _fmshStats() {
  const d = fmshData;
  const hasMesh = d.total_cells > 0;
  const infoRows = [
    ["Status", hasMesh ? "Calculation" : "No mesh"],
    ["Fluid cells", (d.fluid_cells||0).toLocaleString()],
    ["Partial cells", (d.partial_cells||0).toLocaleString()],
    ["Iterations", d.iterations || 0],
    ["Last iteration finished", "—"],
    ["CPU time per last iteration", "—"],
    ["Travels", d.travels || 0],
    ["Iterations per 1 travel", d.iterations_per_travel || 0],
    ["Cpu time", d.cpu_time ? d.cpu_time + " s" : "—"],
    ["Calculation time left", d.calculation_time_left ? d.calculation_time_left + " s" : "—"],
  ];
  return `
    <div style="background:var(--bg-card);border:1px solid var(--border);border-radius:8px;padding:16px;margin-bottom:16px">
      <h3 style="margin:0 0 8px;color:var(--accent)">Mesher / Solver Info Window</h3>
      <p class="text-dim" style="font-size:13px;margin:0">
        Info window appears by default in mesher/solver. Shows Fluid/Solid/Partial cell count, Current Iteration, Current Travel, Iterations per travel.
        Results Summary also gives mesh info.
      </p>
    </div>
    ${hasMesh ? `
    <div style="display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-bottom:16px">
      <div class="stat-card"><div class="stat-value">${d.total_cells?.toLocaleString()}</div><div class="stat-label">Total Cells</div></div>
      <div class="stat-card"><div class="stat-value" style="color:#06b6d4">${d.fluid_cells?.toLocaleString()}</div><div class="stat-label">Fluid Cells</div></div>
      <div class="stat-card"><div class="stat-value" style="color:#f59e0b">${d.solid_cells?.toLocaleString()}</div><div class="stat-label">Solid Cells</div></div>
      <div class="stat-card"><div class="stat-value" style="color:#ef4444">${d.partial_cells?.toLocaleString()}</div><div class="stat-label">Partial Cells</div></div>
    </div>` : '<p class="text-dim">No mesh generated yet. Go to Base Mesh → Generate Mesh.</p>'}
    <table class="data-table" style="font-size:12px;max-width:400px">
      <thead><tr><th>Parameter</th><th>Value</th></tr></thead>
      <tbody>${infoRows.map(r => `<tr><td>${r[0]}</td><td style="font-weight:600">${r[1]}</td></tr>`).join("")}</tbody>
    </table>
    <div class="btn-row mt-16"><button class="btn btn-green" onclick="fmshGenerate()">🔷 Generate Mesh</button></div>
  `;
}

/* ─── Actions ─────────────────────────────────────────────────────── */
async function fmshSaveBase() {
  const body = {
    mesh_type: $("#fmshMeshType")?.value || "automatic",
    initial_mesh_level: parseInt($("#fmshLevel")?.value || 3),
    cell_size: parseFloat($("#fmshCellSize")?.value || 0),
    min_gap_size: parseFloat($("#fmshGap")?.value || 0.001),
    min_wall_thickness: parseFloat($("#fmshWall")?.value || 0.001),
    advanced_channel_refinement: !!$("#fmshAdvCh")?.checked,
    show_basic_mesh: !!$("#fmshShowBasic")?.checked,
  };
  const d = await apiPut("/api/floefd/mesh", body);
  if (d && d.success) toast("✅ Base mesh saved");
}

async function fmshSaveBasic() {
  const body = {
    nx: parseInt($("#fmshNx")?.value || 10),
    ny: parseInt($("#fmshNy")?.value || 10),
    nz: parseInt($("#fmshNz")?.value || 10),
    keep_aspect_ratio: !!$("#fmshKeepAR")?.checked,
    show_mesh: !!$("#fmshShowM")?.checked,
  };
  const d = await apiPut("/api/floefd/mesh", body);
  if (d && d.success) toast("✅ Basic mesh saved");
}

async function fmshSaveInterface() {
  const body = {
    small_solid_feature_level: parseInt($("#fmshSSF")?.value || 2),
    curvature_refinement_level: parseInt($("#fmshCurv")?.value || 1),
    curvature_critical_angle: parseFloat($("#fmshCurvAngle")?.value || 0.318),
    tolerance_refinement_level: parseInt($("#fmshTol")?.value || 0),
    tolerance_value: parseFloat($("#fmshTolVal")?.value || 0.002325),
  };
  const d = await apiPut("/api/floefd/mesh", body);
  if (d && d.success) toast("✅ Interface settings saved");
}

async function fmshSaveRefining() {
  const body = {
    fluid_cells_refinement: parseInt($("#fmshRefF")?.value || 0),
    solid_cells_refinement: parseInt($("#fmshRefS")?.value || 0),
    partial_cells_refinement: parseInt($("#fmshRefP")?.value || 1),
  };
  const d = await apiPut("/api/floefd/mesh", body);
  if (d && d.success) toast("✅ Refining cells saved");
}

async function fmshSaveNarrow() {
  const body = {
    narrow_channels_enabled: !!$("#fmshNchEn")?.checked,
    narrow_channels_num_cells: parseInt($("#fmshNchNum")?.value || 5),
    narrow_channels_refinement_level: parseInt($("#fmshNchLvl")?.value || 2),
    narrow_channels_min_tolerance: parseFloat($("#fmshNchMin")?.value || 0),
    narrow_channels_max_tolerance: parseFloat($("#fmshNchMax")?.value || 0),
  };
  const d = await apiPut("/api/floefd/mesh", body);
  if (d && d.success) toast("✅ Narrow channels saved");
}

async function fmshSaveThinSlots() {
  const body = {
    close_thin_slots_enabled: !!$("#fmshCtsEn")?.checked,
    close_thin_slots_tolerance: parseFloat($("#fmshCtsTol")?.value || 0),
  };
  const d = await apiPut("/api/floefd/mesh", body);
  if (d && d.success) toast("✅ Thin slots saved");
}

async function fmshSaveAdaptive() {
  const strat = ($("#fmshSAStrat")?.value || "Periodic Refinement").toLowerCase().split(" ")[0];
  const body = {
    solution_adaptive_enabled: !!$("#fmshSAEn")?.checked,
    adaptive_refinement_level: parseInt($("#fmshSALvl")?.value || 4),
    adaptive_max_cells: parseInt($("#fmshSAMax")?.value || 2000000),
    adaptive_strategy: strat,
    adaptive_relaxation_interval: parseFloat($("#fmshSARel")?.value || 0.2),
    adaptive_start: parseFloat($("#fmshSAStart")?.value || 2),
    adaptive_period: parseFloat($("#fmshSAPeriod")?.value || 1),
  };
  const d = await apiPut("/api/floefd/mesh", body);
  if (d && d.success) toast("✅ Adaptive meshing saved");
}

async function fmshAddPlane() {
  const planes = fmshData.control_planes || [];
  planes.push({
    axis: $("#fmshCpAxis")?.value || "X",
    min: parseFloat($("#fmshCpMin")?.value || 0),
    max: parseFloat($("#fmshCpMax")?.value || 0.1),
    type: $("#fmshCpType")?.value || "auto",
    number: parseInt($("#fmshCpNum")?.value || 22),
    size: 0, ratio: parseFloat($("#fmshCpRatio")?.value || 1),
  });
  const d = await apiPut("/api/floefd/mesh/control-planes", { planes });
  if (d && d.success) { fmshData.control_planes = planes; toast("✅ Plane added"); fmshRender(); }
}

function fmshRemovePlane(idx) {
  const planes = fmshData.control_planes || [];
  planes.splice(idx, 1);
  apiPut("/api/floefd/mesh/control-planes", { planes }).then(d => {
    if (d) { fmshData.control_planes = planes; toast("🗑 Plane removed"); fmshRender(); }
  });
}

async function fmshAddLM() {
  const body = {
    name: ($("#fmshLmName")?.value || "").trim() || "LIM",
    target_type: $("#fmshLmTarget")?.value || "surface",
    body_shape: $("#fmshLmShape")?.value || "cuboid",
    equidistant_level: parseInt($("#fmshLmLvl")?.value || 2),
    equidistant_refinement_enabled: true,
  };
  const d = await apiPost("/api/floefd/mesh/local-meshes", body);
  if (d) { toast("✅ Local mesh added"); await fmshLoad(); fmshRender(); }
}

async function fmshDeleteLM(id) {
  const d = await apiFetch(`/api/floefd/mesh/local-meshes/${id}`, { method: "DELETE" });
  if (d && d.success) { toast("🗑 Removed"); await fmshLoad(); fmshRender(); }
}

async function fmshDeleteAllLM() {
  const d = await apiPost("/api/floefd/mesh/local-meshes/delete-all", {});
  if (d && d.success) { toast("🗑 All local meshes removed"); await fmshLoad(); fmshRender(); }
}

async function fmshGenerate() {
  toast("⏳ Generating mesh…");
  const d = await apiPost("/api/floefd/mesh/generate", {});
  if (d) { toast(`✅ Mesh: ${d.total_cells?.toLocaleString()} cells`); await fmshLoad(); fmshRender(); }
}

async function fmshRunStudy() {
  toast("⏳ Running mesh sensitivity study…");
  const d = await apiPost("/api/floefd/mesh/study/run", {});
  if (d) { fmshStudy = d; toast("✅ Study complete"); fmshRender(); _fmshDrawChart(); }
}

function _fmshDrawChart() {
  const canvas = document.getElementById("fmshStudyChart");
  if (!canvas || !fmshStudy.length) return;
  const ctx = canvas.getContext("2d");
  const W = canvas.width, H = canvas.height;
  ctx.clearRect(0, 0, W, H);
  const maxC = Math.max(...fmshStudy.map(e => e.mesh_count)) * 1.1;
  const maxD = Math.max(...fmshStudy.map(e => e.dp_value)) * 1.05;
  const minD = Math.min(...fmshStudy.map(e => e.dp_value)) * 0.95;
  const pad = { l: 60, r: 20, t: 30, b: 40 };
  const pw = W - pad.l - pad.r, ph = H - pad.t - pad.b;
  // axes
  ctx.strokeStyle = "#555"; ctx.lineWidth = 1;
  ctx.beginPath(); ctx.moveTo(pad.l, pad.t); ctx.lineTo(pad.l, H - pad.b); ctx.lineTo(W - pad.r, H - pad.b); ctx.stroke();
  // labels
  ctx.fillStyle = "#aaa"; ctx.font = "10px sans-serif"; ctx.textAlign = "center";
  ctx.fillText("Mesh Count", W / 2, H - 4);
  ctx.save(); ctx.translate(12, H / 2); ctx.rotate(-Math.PI / 2); ctx.fillText("dP (Pa)", 0, 0); ctx.restore();
  ctx.fillStyle = "#3b82f6"; ctx.font = "bold 11px sans-serif"; ctx.fillText("FloEFD Mesh Sensitivity", W / 2, 16);
  // line
  ctx.strokeStyle = "#3b82f6"; ctx.lineWidth = 2; ctx.beginPath();
  fmshStudy.forEach((e, i) => {
    const x = pad.l + (e.mesh_count / maxC) * pw;
    const y = pad.t + ph - ((e.dp_value - minD) / (maxD - minD)) * ph;
    i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y);
    ctx.fillStyle = "#3b82f6";
    ctx.fillRect(x - 3, y - 3, 6, 6);
  });
  ctx.stroke();
  // mesh independent line
  if (fmshStudy.length >= 3) {
    const midX = pad.l + pw * 0.45;
    ctx.strokeStyle = "#ef4444"; ctx.lineWidth = 2; ctx.setLineDash([6, 4]);
    ctx.beginPath(); ctx.moveTo(midX, pad.t); ctx.lineTo(midX, H - pad.b); ctx.stroke();
    ctx.setLineDash([]);
    ctx.fillStyle = "#ef4444"; ctx.font = "bold 10px sans-serif";
    ctx.fillText("Mesh Dependent", midX - 50, pad.t + 16);
    ctx.fillText("Mesh Independent", midX + 60, pad.t + 16);
  }
}

// Legacy compat
async function fmshSave() { await fmshSaveBase(); }


// ═══════════════════════════════════════════════════════════════════════════
//  fgl* — L4b: FloEFD Goals (Global, Point, Surface, Volume, Equation)
// ═══════════════════════════════════════════════════════════════════════════

let fglSummary = {};
let fglList = [];
let fglParams = [];
let fglFinish = {};
let fglAssoc = {};
let fglTab = 0;

const FGL_TABS = [
  "Overview", "Global Goals", "Point Goals", "Surface Goals",
  "Volume Goals", "Equation Goals", "Parameters", "Associated Goals",
  "Finish Conditions", "Name Templates"
];

async function fglLoad() {
  const [summary, params] = await Promise.all([
    apiFetch("/api/floefd/goals/summary"),
    apiFetch("/api/floefd/goals/parameters"),
  ]);
  fglSummary = summary || {};
  fglList = fglSummary.goals || [];
  fglParams = params || [];
  fglFinish = fglSummary.finish_conditions || {};
  fglAssoc = fglSummary.associated_goals_config || {};
}

function fglRender() {
  const tabs = FGL_TABS.map((t, i) => {
    const cls = i === fglTab ? "tab active" : "tab";
    const counts = fglSummary.by_type || {};
    let badge = "";
    if (i === 1) badge = _fglBadge(counts.global);
    if (i === 2) badge = _fglBadge(counts.point);
    if (i === 3) badge = _fglBadge(counts.surface);
    if (i === 4) badge = _fglBadge(counts.volume);
    if (i === 5) badge = _fglBadge(counts.equation);
    return `<button class="${cls}" onclick="fglTab=${i};fglRender()">${t}${badge}</button>`;
  }).join("");

  let body = "";
  switch (fglTab) {
    case 0: body = _fglOverview(); break;
    case 1: body = _fglGlobal(); break;
    case 2: body = _fglPoint(); break;
    case 3: body = _fglSurface(); break;
    case 4: body = _fglVolume(); break;
    case 5: body = _fglEquation(); break;
    case 6: body = _fglParamsTab(); break;
    case 7: body = _fglAssociated(); break;
    case 8: body = _fglFinishCond(); break;
    case 9: body = _fglNameTemplates(); break;
  }

  $("#pageContent").innerHTML = `
    <div class="page-header">🎯 Goals (L4b)</div>
    <p class="text-dim mb-8">
      Engineering approach to CFD simulation — specify parameters of importance before solving.
      Used for <strong>Solver Convergence</strong>, <strong>Solution Monitoring</strong>, and <strong>Post Processing</strong>.
    </p>
    <div class="tab-bar" style="flex-wrap:wrap">${tabs}</div>
    <div style="margin-top:16px">${body}</div>
  `;
}

function _fglBadge(arr) {
  const n = arr ? arr.length : 0;
  return n > 0 ? ` <span style="background:var(--accent);color:#fff;border-radius:10px;padding:0 6px;font-size:10px;margin-left:4px">${n}</span>` : "";
}

/* ─── Overview ────────────────────────────────────────────────────── */
function _fglOverview() {
  const bt = fglSummary.by_type || {};
  const cards = [
    { icon: "🌐", label: "Global Goals (GG)", desc: "All grid cells in model. No component/surface selection needed.", items: bt.global || [], color: "#3b82f6" },
    { icon: "📍", label: "Point Goals (PG)", desc: "Specific points — interpolation between cell centres. Thermocouple locations.", items: bt.point || [], color: "#10b981" },
    { icon: "📐", label: "Surface Goals (SG)", desc: "Individual or groups of surfaces. Inlet/Outlet pressures, Heat Transfer Rate.", items: bt.surface || [], color: "#f59e0b" },
    { icon: "📦", label: "Volume Goals (VG)", desc: "Individual or groups of bodies. Max Temperature (Junction), Concentrations.", items: bt.volume || [], color: "#8b5cf6" },
    { icon: "📊", label: "Equation Goals (EG)", desc: "Combine other goals via expression. Pressure Drop, Reynolds Number, Lift/Drag.", items: bt.equation || [], color: "#ef4444" },
  ];
  const chtml = cards.map(c => `
    <div style="background:var(--bg-card);border:1px solid var(--border);border-radius:8px;padding:16px;border-left:4px solid ${c.color}">
      <div style="font-size:22px;margin-bottom:4px">${c.icon}</div>
      <div style="font-weight:600;margin-bottom:4px">${c.label}</div>
      <div class="text-dim" style="font-size:12px;margin-bottom:8px">${c.desc}</div>
      <div style="font-size:20px;font-weight:700;color:${c.color}">${c.items.length}</div>
      ${c.items.length > 0 ? c.items.map(g =>
        `<div style="font-size:11px;margin-top:4px;padding:2px 6px;background:var(--bg-input);border-radius:4px">
          ${g.name} — ${g.parameter} ${g.use_for_convergence ? "✅" : "👁"}</div>`
      ).join("") : ""}
    </div>
  `).join("");

  const total = fglSummary.total || 0;
  const conv = fglSummary.for_convergence || 0;
  const convd = fglSummary.converged || 0;

  return `
    <div style="display:flex;gap:12px;margin-bottom:16px">
      <div style="background:var(--accent);color:#fff;border-radius:8px;padding:12px 20px;text-align:center">
        <div style="font-size:24px;font-weight:700">${total}</div><div style="font-size:11px">Total Goals</div>
      </div>
      <div style="background:#10b981;color:#fff;border-radius:8px;padding:12px 20px;text-align:center">
        <div style="font-size:24px;font-weight:700">${conv}</div><div style="font-size:11px">For Convergence</div>
      </div>
      <div style="background:#f59e0b;color:#fff;border-radius:8px;padding:12px 20px;text-align:center">
        <div style="font-size:24px;font-weight:700">${convd}</div><div style="font-size:11px">Converged</div>
      </div>
    </div>
    <div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(220px,1fr));gap:12px">${chtml}</div>
  `;
}

/* ─── Global Goals ────────────────────────────────────────────────── */
function _fglGlobal() {
  const goals = (fglSummary.by_type || {}).global || [];
  return `
    <div style="background:var(--bg-card);border:1px solid var(--border);border-radius:8px;padding:16px;margin-bottom:16px">
      <h3 style="margin:0 0 8px;color:#3b82f6">🌐 Global Goals</h3>
      <ul class="text-dim" style="font-size:13px;margin:0 0 12px;padding-left:20px">
        <li>Will consider <strong>all grid cells</strong> in model</li>
        <li>No component, surface or point selection necessary</li>
        <li>Typical: Min/Max Velocity, Min/Max Mach Number, Min/Max Temperature, Min/Max Pressure</li>
      </ul>
    </div>
    ${_fglGoalTable(goals, "global")}
    <h3 style="margin:16px 0 8px;font-size:14px;color:var(--accent)">Add Global Goal</h3>
    ${_fglAddForm("global")}
  `;
}

/* ─── Point Goals ─────────────────────────────────────────────────── */
function _fglPoint() {
  const goals = (fglSummary.by_type || {}).point || [];
  return `
    <div style="background:var(--bg-card);border:1px solid var(--border);border-radius:8px;padding:16px;margin-bottom:16px">
      <h3 style="margin:0 0 8px;color:#10b981">📍 Point Goals</h3>
      <ul class="text-dim" style="font-size:13px;margin:0 0 12px;padding-left:20px">
        <li>Considers <strong>specific points</strong> within a model</li>
        <li>Interpolation between cell centres</li>
        <li>Methods: <strong>Reference</strong>, <strong>Pick from screen</strong>, <strong>Coordinates (X, Y, Z)</strong></li>
        <li>Typical: Thermocouple location, Upstream velocity/pressure/density</li>
      </ul>
    </div>
    ${_fglGoalTable(goals, "point")}
    <h3 style="margin:16px 0 8px;font-size:14px;color:var(--accent)">Add Point Goal</h3>
    <div style="display:flex;gap:8px;flex-wrap:wrap;align-items:flex-end;margin-bottom:8px">
      <div class="form-section" style="flex:1;min-width:140px;margin:0">
        <label>Name</label>
        <input type="text" id="fglPtName" value="PG ${goals.length + 1}">
      </div>
      <div class="form-section" style="width:140px;margin:0">
        <label>Parameter</label>
        ${_fglParamSelect("fglPtParam", "point")}
      </div>
      <div class="form-section" style="width:100px;margin:0">
        <label>Method</label>
        <select id="fglPtMethod">
          <option value="coordinates">Coordinates</option>
          <option value="reference">Reference</option>
          <option value="pick_from_screen">Pick from Screen</option>
        </select>
      </div>
    </div>
    <div style="display:flex;gap:8px;flex-wrap:wrap;align-items:flex-end">
      <div class="form-section" style="width:90px;margin:0">
        <label>X (mm)</label>
        <input type="number" id="fglPtX" value="0" step="0.01">
      </div>
      <div class="form-section" style="width:90px;margin:0">
        <label>Y (mm)</label>
        <input type="number" id="fglPtY" value="0" step="0.01">
      </div>
      <div class="form-section" style="width:90px;margin:0">
        <label>Z (mm)</label>
        <input type="number" id="fglPtZ" value="0" step="0.01">
      </div>
      <button class="btn btn-accent" onclick="fglAddPoint()" style="height:34px">➕ Add Point Goal</button>
    </div>
  `;
}

/* ─── Surface Goals ───────────────────────────────────────────────── */
function _fglSurface() {
  const goals = (fglSummary.by_type || {}).surface || [];
  return `
    <div style="background:var(--bg-card);border:1px solid var(--border);border-radius:8px;padding:16px;margin-bottom:16px">
      <h3 style="margin:0 0 8px;color:#f59e0b">📐 Surface Goals</h3>
      <ul class="text-dim" style="font-size:13px;margin:0 0 8px;padding-left:20px">
        <li>Individual or <strong>groups of surfaces</strong></li>
        <li>Enabled/Disabled faces — faces of disabled components</li>
        <li>Component Selection — decompose to individual faces</li>
        <li>Filter Selection — remove out-of-domain, outer, or fluid-contacting faces</li>
      </ul>
      <div style="font-size:12px;color:var(--accent);margin-bottom:4px"><strong>Typical Applications:</strong></div>
      <ul class="text-dim" style="font-size:12px;margin:0;padding-left:20px">
        <li>Inlet/Outlet Pressures</li><li>Fan Flow Rate/Pressure</li>
        <li>Heat Transfer Rate (Convected)</li><li>Surface Temperatures</li><li>Surface Force/Torque</li>
      </ul>
    </div>
    <div style="background:var(--bg-card);border:1px solid var(--border);border-radius:8px;padding:12px;margin-bottom:16px">
      <div style="font-weight:600;margin-bottom:8px;font-size:13px">🔍 Filter Faces</div>
      <div style="display:flex;gap:16px;flex-wrap:wrap;font-size:12px">
        <label><input type="checkbox" id="fglSfFilterDomain"> Remove out of domain faces</label>
        <label><input type="checkbox" id="fglSfFilterOuter"> Remove outer faces</label>
        <label><input type="checkbox" id="fglSfFilterFluid"> Remove fluid-contacting faces</label>
        <label><input type="checkbox" id="fglSfFilterKeep"> Keep outer and fluid-contacting faces</label>
      </div>
    </div>
    ${_fglGoalTable(goals, "surface")}
    <h3 style="margin:16px 0 8px;font-size:14px;color:var(--accent)">Add Surface Goal</h3>
    ${_fglAddForm("surface")}
  `;
}

/* ─── Volume Goals ────────────────────────────────────────────────── */
function _fglVolume() {
  const goals = (fglSummary.by_type || {}).volume || [];
  return `
    <div style="background:var(--bg-card);border:1px solid var(--border);border-radius:8px;padding:16px;margin-bottom:16px">
      <h3 style="margin:0 0 8px;color:#8b5cf6">📦 Volume Goals</h3>
      <ul class="text-dim" style="font-size:13px;margin:0 0 12px;padding-left:20px">
        <li>Individual or <strong>groups of bodies</strong></li>
        <li>Enabled/Disabled bodies — Dummy Volumes</li>
        <li>Typical: Max Temperature (Junction Temperatures), Concentrations in specific locations</li>
      </ul>
    </div>
    ${_fglGoalTable(goals, "volume")}
    <h3 style="margin:16px 0 8px;font-size:14px;color:var(--accent)">Add Volume Goal</h3>
    ${_fglAddForm("volume")}
  `;
}

/* ─── Equation Goals ──────────────────────────────────────────────── */
function _fglEquation() {
  const goals = (fglSummary.by_type || {}).equation || [];
  // Available parameters for the equation builder
  const eqParams = [
    "Pressure", "Temperature", "Velocity in X direction", "Velocity in Y direction",
    "Velocity in Z direction", "Turbulence intensity", "Turbulence length",
    "Initial solid temperature", "Heat transfer coefficient", "External fluid temperature"
  ];
  return `
    <div style="background:var(--bg-card);border:1px solid var(--border);border-radius:8px;padding:16px;margin-bottom:16px">
      <h3 style="margin:0 0 8px;color:#ef4444">📊 Equation Goals</h3>
      <ul class="text-dim" style="font-size:13px;margin:0 0 12px;padding-left:20px">
        <li>Utilise other goals to form required parameter — at-a-glance values</li>
        <li>Select "Input Data" to select project parameters</li>
        <li>Typical: Pressure Drop (Delta P), Reynolds Number, Lift/Drag Coefficients, Pump Efficiency</li>
      </ul>
    </div>
    ${_fglGoalTable(goals, "equation")}
    <h3 style="margin:16px 0 8px;font-size:14px;color:var(--accent)">Add Equation Goal</h3>
    <div style="display:flex;gap:12px;flex-wrap:wrap;align-items:flex-start">
      <div style="flex:1;min-width:300px">
        <div class="form-section" style="margin:0 0 8px">
          <label>Name</label>
          <input type="text" id="fglEqName" value="EG ${goals.length + 1}">
        </div>
        <div class="form-section" style="margin:0 0 8px">
          <label>Expression</label>
          <textarea id="fglEqExpr" rows="3" style="width:100%;font-family:monospace;font-size:12px;background:var(--bg-input);border:1px solid var(--border);color:var(--fg);padding:6px;border-radius:4px" placeholder="e.g. {SG Pressure 1} - {SG Pressure 2}"></textarea>
        </div>
        <div style="display:flex;gap:4px;flex-wrap:wrap;margin-bottom:8px">
          ${["7","8","9","+","(","log"].map(b => `<button class="btn" style="width:36px;height:30px;font-size:12px" onclick="fglEqInsert('${b}')">${b}</button>`).join("")}
        </div>
        <div style="display:flex;gap:4px;flex-wrap:wrap;margin-bottom:8px">
          ${["4","5","6","-",")","cos"].map(b => `<button class="btn" style="width:36px;height:30px;font-size:12px" onclick="fglEqInsert('${b}')">${b}</button>`).join("")}
        </div>
        <div style="display:flex;gap:4px;flex-wrap:wrap;margin-bottom:8px">
          ${["1","2","3","*","^","sin"].map(b => `<button class="btn" style="width:36px;height:30px;font-size:12px" onclick="fglEqInsert('${b}')">${b}</button>`).join("")}
        </div>
        <div style="display:flex;gap:4px;flex-wrap:wrap;margin-bottom:8px">
          ${["0","E",".","/","exp","tan"].map(b => `<button class="btn" style="width:36px;height:30px;font-size:12px" onclick="fglEqInsert('${b}')">${b}</button>`).join("")}
        </div>
        <div style="display:flex;gap:8px;align-items:flex-end;margin-bottom:8px">
          <div class="form-section" style="flex:1;margin:0">
            <label>Dimensionality</label>
            <select id="fglEqDim">
              <option>No units</option><option>Pa</option><option>K</option><option>°C</option>
              <option>m/s</option><option>W</option><option>W/m²</option><option>N</option><option>N·m</option>
            </select>
          </div>
          <label style="font-size:12px;white-space:nowrap"><input type="checkbox" id="fglEqConv" checked> Use for convergence</label>
        </div>
        <div style="display:flex;gap:8px">
          <button class="btn" onclick="fglEqClear()">Clear</button>
          <button class="btn btn-accent" onclick="fglAddEquation()">➕ Add Equation Goal</button>
        </div>
      </div>
      <div style="width:180px">
        <div style="font-weight:600;font-size:12px;margin-bottom:4px">Parameter list</div>
        <select id="fglEqParamList" size="10" style="width:100%;font-size:11px;background:var(--bg-input);border:1px solid var(--border);color:var(--fg)" ondblclick="fglEqInsertParam()">
          ${eqParams.map(p => `<option value="${p}">${p}</option>`).join("")}
        </select>
      </div>
    </div>
  `;
}

/* ─── Parameters Matrix ───────────────────────────────────────────── */
function _fglParamsTab() {
  if (!fglParams.length) return '<p class="text-dim">Loading parameters…</p>';
  // Split into two columns like the slide
  const mid = Math.ceil(fglParams.length / 2);
  const left = fglParams.slice(0, mid);
  const right = fglParams.slice(mid);
  const mkTable = (items) => `
    <table class="data-table" style="font-size:11px">
      <thead><tr><th style="min-width:140px">Parameter</th><th>Min</th><th>Av</th><th>Max</th><th>Bulk Av</th><th>Use for Conv.</th></tr></thead>
      <tbody>${items.map(p => `<tr>
        <td>${p.name}</td>
        <td style="text-align:center"><input type="checkbox" ${p.global || p.surface ? "" : "disabled"}></td>
        <td style="text-align:center"><input type="checkbox" ${p.global || p.surface ? "" : "disabled"}></td>
        <td style="text-align:center"><input type="checkbox" ${p.global || p.surface ? "" : "disabled"}></td>
        <td style="text-align:center"><input type="checkbox" ${p.volume ? "" : "disabled"}></td>
        <td style="text-align:center"><input type="checkbox" checked disabled></td>
      </tr>`).join("")}</tbody>
    </table>
  `;
  return `
    <div style="background:var(--bg-card);border:1px solid var(--border);border-radius:8px;padding:16px;margin-bottom:16px">
      <h3 style="margin:0 0 8px;color:var(--accent)">Goal Parameters</h3>
      <p class="text-dim" style="font-size:12px;margin:0">
        Each parameter can be tracked with Min, Av (Average), Max, and Bulk Average criteria.
        "Use for Conv." marks it for solver convergence control.
      </p>
    </div>
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px">
      <div>${mkTable(left)}</div>
      <div>${mkTable(right)}</div>
    </div>
  `;
}

/* ─── Associated Goals ────────────────────────────────────────────── */
function _fglAssociated() {
  const a = fglAssoc;
  const mkRow = (label, key) =>
    `<tr><td style="padding-left:24px;font-size:12px">${label}</td>
     <td style="text-align:center"><input type="checkbox" data-assoc="${key}" ${a[key] ? "checked" : ""}></td></tr>`;
  return `
    <div style="background:var(--bg-card);border:1px solid var(--border);border-radius:8px;padding:16px;margin-bottom:16px">
      <h3 style="margin:0 0 8px;color:var(--accent)">Associated Goals</h3>
      <ul class="text-dim" style="font-size:13px;margin:0 0 8px;padding-left:20px">
        <li>Many FloEFD features have associated goals option</li>
        <li>Automatic creation of goals based on FloEFD feature</li>
        <li>Typical: Inlet flow rate → Av Static Pressure, Outlet Pressure → Volume Flow Rate,
            Volume Source → Max Solid Temperature, Fans → Volume Flow Rate</li>
      </ul>
      <label style="font-size:14px;font-weight:600">
        <input type="checkbox" id="fglAssocMaster" ${a.create_associated_goals ? "checked" : ""}
               onchange="fglAssoc.create_associated_goals=this.checked"> Create associated goals
      </label>
    </div>
    <table class="data-table" style="font-size:12px">
      <thead><tr><th>Parameter</th><th style="width:60px">Enabled</th></tr></thead>
      <tbody>
        <tr><td colspan="2" style="font-weight:600;background:var(--bg-input)">📂 Boundary Condition</td></tr>
        ${mkRow("Inlet Mass Flow", "bc_inlet_mass_flow")}
        ${mkRow("Inlet Volume Flow", "bc_inlet_volume_flow")}
        ${mkRow("Inlet Velocity", "bc_inlet_velocity")}
        ${mkRow("Inlet Mach Number", "bc_inlet_mach_number")}
        ${mkRow("Outlet Mass Flow", "bc_outlet_mass_flow")}
        ${mkRow("Outlet Volume Flow", "bc_outlet_volume_flow")}
        ${mkRow("Outlet Velocity", "bc_outlet_velocity")}
        ${mkRow("Outlet Mach Number", "bc_outlet_mach_number")}
        ${mkRow("Static Pressure", "bc_static_pressure")}
        ${mkRow("Environment Pressure", "bc_environment_pressure")}
        ${mkRow("Real Wall", "bc_real_wall")}
        ${mkRow("Outer Wall", "bc_outer_wall")}
        ${mkRow("Ideal Wall", "bc_ideal_wall")}
        <tr><td colspan="2" style="font-weight:600;background:var(--bg-input)">📂 Surface Source</td></tr>
        ${mkRow("Heat Transfer Rate", "ss_heat_transfer_rate")}
        ${mkRow("Heat Generation Rate", "ss_heat_generation_rate")}
        ${mkRow("Surface heat generation rate", "ss_surface_heat_generation_rate")}
        <tr><td colspan="2" style="font-weight:600;background:var(--bg-input)">📂 Volume Source</td></tr>
        ${mkRow("Volumetric Heat Generation Rate", "vs_volumetric_heat_generation_rate")}
        ${mkRow("Temperature", "vs_temperature")}
        ${mkRow("Heat Generation Rate", "vs_heat_generation_rate")}
        <tr><td colspan="2" style="font-weight:600;background:var(--bg-input)">📂 Radiative Surface</td></tr>
        ${mkRow("Wall", "rs_wall")}
        ${mkRow("Symmetry", "rs_symmetry")}
        ${mkRow("Wall to ambient", "rs_wall_to_ambient")}
        ${mkRow("Non-radiating wall (no rays)", "rs_non_radiating_wall")}
        <tr><td colspan="2" style="font-weight:600;background:var(--bg-input)">📂 Fans</td></tr>
        ${mkRow("External Inlet Fan", "fan_external_inlet")}
        ${mkRow("External Outlet Fan", "fan_external_outlet")}
        ${mkRow("Internal Fan", "fan_internal")}
        <tr><td colspan="2" style="font-weight:600;background:var(--bg-input)">📂 Other</td></tr>
        ${mkRow("Two-Resistor Components", "other_two_resistor")}
      </tbody>
    </table>
    <button class="btn btn-accent" style="margin-top:12px" onclick="fglSaveAssociated()">💾 Save Associated Goals Config</button>
  `;
}

/* ─── Finish Conditions ───────────────────────────────────────────── */
function _fglFinishCond() {
  const f = fglFinish;
  const goalRows = fglList.filter(g => g.use_for_convergence).map(g => `
    <tr>
      <td>${g.name}</td>
      <td style="text-align:center"><input type="checkbox" checked disabled></td>
      <td>${g.convergence_mode || "Auto"}</td>
      <td>${g.tolerance_value || "Auto"}</td>
    </tr>
  `).join("") || '<tr><td colspan="4" class="text-dim">No goals marked for convergence.</td></tr>';

  return `
    <div style="background:var(--bg-card);border:1px solid var(--border);border-radius:8px;padding:16px;margin-bottom:16px">
      <h3 style="margin:0 0 8px;color:var(--accent)">Finish Conditions</h3>
      <p class="text-dim" style="font-size:13px;margin:0">
        Defines when solver will finish. Default: Min Refinement = 0, Max Travels = 4, Goals Convergence = On.
      </p>
    </div>
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:16px">
      <div>
        <h4 style="margin:0 0 12px;font-size:13px">Finish Conditions</h4>
        <table class="data-table" style="font-size:12px">
          <thead><tr><th>Parameter</th><th style="width:50px">On/Off</th><th style="width:80px">Value</th></tr></thead>
          <tbody>
            <tr>
              <td>Minimum refinement number</td>
              <td style="text-align:center"><input type="checkbox" id="fcMinRefEn" ${f.min_refinement_enabled ? "checked" : ""}></td>
              <td><input type="number" id="fcMinRef" value="${f.min_refinement_number || 0}" min="0" style="width:60px"></td>
            </tr>
            <tr>
              <td>Maximum iterations</td>
              <td style="text-align:center"><input type="checkbox" id="fcMaxIterEn" ${f.max_iterations_enabled ? "checked" : ""}></td>
              <td><input type="number" id="fcMaxIter" value="${f.max_iterations || 100}" min="1" style="width:60px"></td>
            </tr>
            <tr>
              <td>Maximum calculation time</td>
              <td style="text-align:center"><input type="checkbox" id="fcMaxTimeEn" ${f.max_calculation_time_enabled ? "checked" : ""}></td>
              <td><input type="number" id="fcMaxTime" value="${f.max_calculation_time || 36000}" step="100" style="width:60px"> s</td>
            </tr>
            <tr>
              <td>Maximum travels</td>
              <td style="text-align:center"><input type="checkbox" id="fcMaxTravEn" ${f.max_travels_enabled ? "checked" : ""}></td>
              <td>
                <select id="fcTravMode" style="width:50px"><option ${f.max_travels_mode==="auto"?"selected":""}>Auto</option><option ${f.max_travels_mode==="manual"?"selected":""}>Manual</option></select>
                <input type="number" id="fcMaxTrav" value="${f.max_travels || 4}" min="1" style="width:40px">
              </td>
            </tr>
          </tbody>
        </table>
      </div>
      <div>
        <h4 style="margin:0 0 12px;font-size:13px">Goals Convergence</h4>
        <label style="font-size:13px;margin-bottom:8px;display:block">
          <input type="checkbox" id="fcGoalsConv" ${f.goals_convergence_enabled ? "checked" : ""}> Goals Convergence
        </label>
        <div class="form-section" style="margin:0 0 8px">
          <label>Analysis interval (travels)</label>
          <div style="display:flex;gap:4px;align-items:center">
            <select id="fcIntMode" style="width:60px"><option ${f.analysis_interval_mode==="auto"?"selected":""}>Auto</option><option ${f.analysis_interval_mode==="manual"?"selected":""}>Manual</option></select>
            <input type="number" id="fcIntVal" value="${f.analysis_interval || 0.5}" step="0.1" min="0.1" style="width:60px">
          </div>
        </div>
        <h4 style="margin:12px 0 8px;font-size:13px">Goals Criteria</h4>
        <table class="data-table" style="font-size:11px">
          <thead><tr><th>Goal</th><th>On</th><th>Mode</th><th>Value</th></tr></thead>
          <tbody>${goalRows}</tbody>
        </table>
      </div>
    </div>
    <button class="btn btn-accent" style="margin-top:12px" onclick="fglSaveFinish()">💾 Save Finish Conditions</button>
  `;
}

/* ─── Name Templates ──────────────────────────────────────────────── */
function _fglNameTemplates() {
  const templates = [
    { prefix: "GG", label: "Global Goal", example: "GG <Parameter> <Number>" },
    { prefix: "PG", label: "Point Goal", example: "PG <Parameter> <Number>" },
    { prefix: "SG", label: "Surface Goal", example: "SG <Parameter> <Number>" },
    { prefix: "VG", label: "Volume Goal", example: "VG <Parameter> <Number>" },
  ];
  const placeholders = ["&lt;Inlet&gt;", "&lt;Outlet&gt;", "&lt;Parameter&gt;", "&lt;Number&gt;"];
  return `
    <div style="background:var(--bg-card);border:1px solid var(--border);border-radius:8px;padding:16px;margin-bottom:16px">
      <h3 style="margin:0 0 8px;color:var(--accent)">Name Template</h3>
      <p class="text-dim" style="font-size:13px;margin:0 0 8px">
        Configure automatic naming for goals using placeholder tokens.
      </p>
      <div style="font-size:12px;margin-bottom:12px">
        <strong>Available Placeholders:</strong> ${placeholders.map(p =>
          `<code style="background:var(--bg-input);padding:2px 6px;border-radius:3px;margin:0 2px">${p}</code>`
        ).join(" ")}
      </div>
    </div>
    ${templates.map(t => `
      <div style="display:flex;gap:8px;align-items:center;margin-bottom:8px">
        <div style="width:120px;font-weight:600;font-size:13px">${t.prefix} — ${t.label}</div>
        <input type="text" id="fglTpl_${t.prefix}" value="${t.example}"
               style="flex:1;max-width:300px;font-family:monospace">
        <div style="display:flex;gap:2px">
          <button class="btn" style="font-size:10px;padding:2px 6px" onclick="fglTplInsert('${t.prefix}','<Inlet>')">&lt;▸&gt;</button>
          <button class="btn" style="font-size:10px;padding:2px 6px" onclick="fglTplInsert('${t.prefix}','<Outlet>')">&lt;|▸&gt;</button>
          <button class="btn" style="font-size:10px;padding:2px 6px" onclick="fglTplInsert('${t.prefix}','<Parameter>')">&lt;×&gt;</button>
          <button class="btn" style="font-size:10px;padding:2px 6px" onclick="fglTplInsert('${t.prefix}','<Number>')">&lt;#&gt;</button>
        </div>
      </div>
    `).join("")}
  `;
}

/* ─── Shared: Goal Table ──────────────────────────────────────────── */
function _fglGoalTable(goals, goalType) {
  if (!goals.length) return `<p class="text-dim" style="font-size:12px">No ${goalType} goals yet.</p>`;
  const isPoint = goalType === "point";
  const isEq = goalType === "equation";
  const rows = goals.map(g => `<tr>
    <td>${g.name}</td>
    <td>${g.parameter}</td>
    ${isPoint ? `<td>(${g.point_x}, ${g.point_y}, ${g.point_z})</td>` : ""}
    ${isEq ? `<td style="font-family:monospace;font-size:11px">${g.expression || "—"}</td>` : ""}
    <td style="text-align:center"><input type="checkbox" ${g.use_min ? "checked" : ""} disabled title="Min"></td>
    <td style="text-align:center"><input type="checkbox" ${g.use_av ? "checked" : ""} disabled title="Av"></td>
    <td style="text-align:center"><input type="checkbox" ${g.use_max ? "checked" : ""} disabled title="Max"></td>
    <td style="text-align:center"><input type="checkbox" ${g.use_bulk_av ? "checked" : ""} disabled title="Bulk Av"></td>
    <td style="text-align:center"><input type="checkbox" ${g.use_for_convergence ? "checked" : ""} disabled title="Conv"></td>
    <td style="text-align:center">${g.is_converged ? "✅" : "⏳"}</td>
    <td><button class="btn" style="padding:2px 8px;font-size:11px;color:var(--red)" onclick="fglDelete('${g.id}')">✕</button></td>
  </tr>`).join("");
  return `
    <table class="data-table" style="font-size:12px">
      <thead><tr>
        <th>Name</th><th>Parameter</th>
        ${isPoint ? "<th>Coords</th>" : ""}${isEq ? "<th>Expression</th>" : ""}
        <th>Min</th><th>Av</th><th>Max</th><th>Bulk Av</th><th>Conv</th><th>Status</th><th></th>
      </tr></thead>
      <tbody>${rows}</tbody>
    </table>
  `;
}

/* ─── Shared: Parameter Select ────────────────────────────────────── */
function _fglParamSelect(id, goalType) {
  const opts = fglParams.filter(p => p[goalType] !== false).map(p =>
    `<option value="${p.name}">${p.name}</option>`
  ).join("");
  return `<select id="${id}">${opts || '<option value="temperature">Temperature</option><option value="pressure">Pressure</option><option value="velocity">Velocity</option>'}</select>`;
}

/* ─── Shared: Add Form (Global/Surface/Volume) ────────────────────── */
function _fglAddForm(goalType) {
  const prefix = goalType === "global" ? "GG" : goalType === "surface" ? "SG" : "VG";
  const count = ((fglSummary.by_type || {})[goalType] || []).length;
  return `
    <div style="display:flex;gap:8px;flex-wrap:wrap;align-items:flex-end">
      <div class="form-section" style="flex:1;min-width:140px;margin:0">
        <label>Name</label>
        <input type="text" id="fglAddName_${goalType}" value="${prefix} ${count + 1}">
      </div>
      <div class="form-section" style="width:160px;margin:0">
        <label>Parameter</label>
        ${_fglParamSelect("fglAddParam_" + goalType, goalType)}
      </div>
      <div style="display:flex;gap:8px;font-size:12px;align-items:center">
        <label><input type="checkbox" id="fglAddMin_${goalType}"> Min</label>
        <label><input type="checkbox" id="fglAddAv_${goalType}"> Av</label>
        <label><input type="checkbox" id="fglAddMax_${goalType}"> Max</label>
        <label><input type="checkbox" id="fglAddBulk_${goalType}"> Bulk Av</label>
        <label><input type="checkbox" id="fglAddConv_${goalType}" checked> Conv</label>
      </div>
      <button class="btn btn-accent" onclick="fglAddTyped('${goalType}')" style="height:34px">➕ Add</button>
    </div>
  `;
}

/* ─── Actions ─────────────────────────────────────────────────────── */
async function fglAddTyped(goalType) {
  const body = {
    name: ($(`#fglAddName_${goalType}`)?.value || "").trim() || "Goal",
    goal_type: goalType,
    parameter: $(`#fglAddParam_${goalType}`)?.value || "Temperature",
    use_min: $(`#fglAddMin_${goalType}`)?.checked || false,
    use_av: $(`#fglAddAv_${goalType}`)?.checked || false,
    use_max: $(`#fglAddMax_${goalType}`)?.checked || false,
    use_bulk_av: $(`#fglAddBulk_${goalType}`)?.checked || false,
    use_for_convergence: $(`#fglAddConv_${goalType}`)?.checked ?? true,
  };
  const d = await apiPost("/api/floefd/goals", body);
  if (d) { toast("✅ Goal added"); await fglLoad(); fglRender(); }
}

async function fglAddPoint() {
  const body = {
    name: ($("#fglPtName")?.value || "").trim() || "PG",
    goal_type: "point",
    parameter: $("#fglPtParam")?.value || "Temperature",
    point_method: $("#fglPtMethod")?.value || "coordinates",
    point_x: parseFloat($("#fglPtX")?.value || 0),
    point_y: parseFloat($("#fglPtY")?.value || 0),
    point_z: parseFloat($("#fglPtZ")?.value || 0),
    use_for_convergence: true,
  };
  const d = await apiPost("/api/floefd/goals", body);
  if (d) { toast("✅ Point Goal added"); await fglLoad(); fglRender(); }
}

async function fglAddEquation() {
  const body = {
    name: ($("#fglEqName")?.value || "").trim() || "EG",
    goal_type: "equation",
    parameter: "equation",
    expression: $("#fglEqExpr")?.value || "",
    dimensionality: $("#fglEqDim")?.value || "No units",
    use_for_convergence: $("#fglEqConv")?.checked ?? true,
  };
  const d = await apiPost("/api/floefd/goals", body);
  if (d) { toast("✅ Equation Goal added"); await fglLoad(); fglRender(); }
}

function fglEqInsert(txt) {
  const ta = $("#fglEqExpr");
  if (ta) { ta.value += txt; ta.focus(); }
}
function fglEqInsertParam() {
  const sel = $("#fglEqParamList");
  if (sel && sel.value) fglEqInsert(`{${sel.value}}`);
}
function fglEqClear() {
  const ta = $("#fglEqExpr");
  if (ta) ta.value = "";
}
function fglTplInsert(prefix, token) {
  const inp = $(`#fglTpl_${prefix}`);
  if (inp) { inp.value += ` ${token}`; }
}

async function fglDelete(id) {
  const d = await apiFetch(`/api/floefd/goals/${id}`, { method: "DELETE" });
  if (d && d.success) { toast("🗑 Goal removed"); await fglLoad(); fglRender(); }
}

async function fglSaveFinish() {
  const body = {
    min_refinement_number: parseInt($("#fcMinRef")?.value || 0),
    min_refinement_enabled: $("#fcMinRefEn")?.checked || false,
    max_iterations: parseInt($("#fcMaxIter")?.value || 100),
    max_iterations_enabled: $("#fcMaxIterEn")?.checked || false,
    max_calculation_time: parseFloat($("#fcMaxTime")?.value || 36000),
    max_calculation_time_enabled: $("#fcMaxTimeEn")?.checked || false,
    max_travels: parseInt($("#fcMaxTrav")?.value || 4),
    max_travels_mode: ($("#fcTravMode")?.value || "Auto").toLowerCase(),
    max_travels_enabled: $("#fcMaxTravEn")?.checked || false,
    goals_convergence_enabled: $("#fcGoalsConv")?.checked || false,
    analysis_interval: parseFloat($("#fcIntVal")?.value || 0.5),
    analysis_interval_mode: ($("#fcIntMode")?.value || "Auto").toLowerCase(),
  };
  const d = await apiPut("/api/floefd/goals/finish-conditions", body);
  if (d) { toast("✅ Finish conditions saved"); fglFinish = d; }
}

async function fglSaveAssociated() {
  const body = { create_associated_goals: $("#fglAssocMaster")?.checked || false };
  document.querySelectorAll("[data-assoc]").forEach(cb => {
    body[cb.dataset.assoc] = cb.checked;
  });
  const d = await apiPut("/api/floefd/goals/associated-config", body);
  if (d) { toast("✅ Associated goals config saved"); fglAssoc = d; }
}

// Legacy compat alias
async function fglAdd() { fglAddTyped("surface"); }


// ═══════════════════════════════════════════════════════════════════════════
//  fslv* — L6: FloEFD Solve & Monitor
// ═══════════════════════════════════════════════════════════════════════════

let fslvConfig = {};
let fslvHistory = [];
let fslvChart = null;
let fslvGoalChart = null;
let fslvPollingId = null;

async function fslvLoad() {
  fslvConfig = await apiFetch("/api/floefd/solver") || {};
  fslvHistory = await apiFetch("/api/floefd/solver/history") || [];
}

function fslvRender() {
  const sc = fslvConfig;
  const statusClass = sc.convergence_status === "converged" ? "text-green" :
                      sc.convergence_status === "diverging" ? "text-red" :
                      sc.convergence_status === "converging" ? "text-yellow" : "text-dim";

  $("#pageContent").innerHTML = `
    <div class="page-header">📈 Solve & Monitor</div>

    <div style="display:grid;grid-template-columns:1fr 1fr;gap:20px">
      <div>
        <h3 style="margin:0 0 12px;font-size:14px;color:var(--accent)">Solver Configuration</h3>
        <div class="form-section">
          <label>Turbulence Model</label>
          <select id="fslvTurbModel">
            <option value="k-epsilon" ${sc.turbulence_model === "k-epsilon" ? "selected" : ""}>k-ε (FloEFD Modified)</option>
            <option value="k-omega" ${sc.turbulence_model === "k-omega" ? "selected" : ""}>k-ω SST</option>
            <option value="laminar" ${sc.turbulence_model === "laminar" ? "selected" : ""}>Laminar Only</option>
          </select>
        </div>
        <div class="form-section">
          <label>Wall Function</label>
          <select id="fslvWallFunc">
            <option value="modified" ${sc.wall_function === "modified" ? "selected" : ""}>Modified (FloEFD)</option>
            <option value="standard" ${sc.wall_function === "standard" ? "selected" : ""}>Standard</option>
          </select>
        </div>
        <div class="form-section">
          <label>Max Iterations</label>
          <input type="number" id="fslvMaxIter" value="${sc.max_iterations || 200}" min="1" max="10000">
        </div>
        <div class="form-section">
          <label>Finish Condition</label>
          <select id="fslvFinish">
            <option value="goals" ${sc.finish_conditions === "goals" ? "selected" : ""}>Goals Converged</option>
            <option value="iterations" ${sc.finish_conditions === "iterations" ? "selected" : ""}>Max Iterations</option>
            <option value="both" ${sc.finish_conditions === "both" ? "selected" : ""}>Goals OR Iterations</option>
          </select>
        </div>
        <div class="checkbox-row mb-8">
          <input type="checkbox" id="fslvAutoConv" ${sc.auto_convergence !== false ? "checked" : ""}>
          <span>Automatic convergence control</span>
        </div>

        <div class="btn-row">
          <button class="btn btn-accent" onclick="fslvSaveConfig()">💾 Save</button>
          <button class="btn btn-green" onclick="fslvRun(50)">▶ Run 50 Iterations</button>
          <button class="btn btn-green" onclick="fslvRun(200)">▶ Run All</button>
          <button class="btn btn-red" onclick="fslvReset()">⏹ Reset</button>
        </div>
      </div>

      <div>
        <h3 style="margin:0 0 12px;font-size:14px;color:var(--accent)">Status</h3>
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-bottom:12px">
          <div class="stat-card"><div class="stat-value">${sc.current_iteration || 0}</div><div class="stat-label">Iteration</div></div>
          <div class="stat-card"><div class="stat-value ${statusClass}">${(sc.convergence_status || 'not_started').replace('_', ' ')}</div><div class="stat-label">Status</div></div>
        </div>

        <h3 style="margin:12px 0 8px;font-size:14px;color:var(--fg-dim)">Goal Values</h3>
        <div id="fslvGoalTable"></div>
      </div>
    </div>

    <h3 style="margin:20px 0 12px;font-size:14px;color:var(--accent)">Residual Plot</h3>
    <div style="height:250px;position:relative;background:var(--bg);border:1px solid var(--border);border-radius:var(--radius);padding:8px">
      <canvas id="fslvResidualChart"></canvas>
    </div>

    <h3 style="margin:20px 0 12px;font-size:14px;color:var(--accent)">Goal Convergence Plot</h3>
    <div style="height:220px;position:relative;background:var(--bg);border:1px solid var(--border);border-radius:var(--radius);padding:8px">
      <canvas id="fslvGoalChart"></canvas>
    </div>
  `;

  fslvInitCharts();
  fslvUpdateFromHistory();
  fslvRenderGoalTable();
}

function fslvInitCharts() {
  const rc = $("#fslvResidualChart");
  if (rc && typeof Chart !== "undefined") {
    fslvChart = new Chart(rc, {
      type: "line",
      data: { labels: [], datasets: [] },
      options: {
        responsive: true, maintainAspectRatio: false, animation: false,
        scales: {
          y: { type: "logarithmic", title: { display: true, text: "Residual", color: "#6c7086" },
               ticks: { color: "#6c7086" }, grid: { color: "#313244" } },
          x: { title: { display: true, text: "Iteration", color: "#6c7086" },
               ticks: { color: "#6c7086" }, grid: { color: "#313244" } },
        },
        plugins: { legend: { labels: { color: "#cdd6f4", font: { size: 11 } } } },
      },
    });
  }

  const gc = $("#fslvGoalChart");
  if (gc && typeof Chart !== "undefined") {
    fslvGoalChart = new Chart(gc, {
      type: "line",
      data: { labels: [], datasets: [] },
      options: {
        responsive: true, maintainAspectRatio: false, animation: false,
        scales: {
          y: { title: { display: true, text: "Goal Value", color: "#6c7086" },
               ticks: { color: "#6c7086" }, grid: { color: "#313244" } },
          x: { title: { display: true, text: "Iteration", color: "#6c7086" },
               ticks: { color: "#6c7086" }, grid: { color: "#313244" } },
        },
        plugins: { legend: { labels: { color: "#cdd6f4", font: { size: 11 } } } },
      },
    });
  }
}

function fslvUpdateFromHistory() {
  if (!fslvChart || !fslvHistory.length) return;

  const labels = fslvHistory.map(h => h.iteration);
  const residualFields = Object.keys(fslvHistory[0]?.residuals || {});
  const goalFields = Object.keys(fslvHistory[0]?.goals || {});

  // Update residual chart
  fslvChart.data.labels = labels;
  fslvChart.data.datasets = residualFields.map((f, i) => ({
    label: f,
    data: fslvHistory.map(h => h.residuals[f]),
    borderColor: _CHART_COLORS[i % _CHART_COLORS.length],
    backgroundColor: "transparent",
    borderWidth: 1.5, pointRadius: 0,
  }));
  fslvChart.update();

  // Update goal chart
  if (fslvGoalChart && goalFields.length) {
    fslvGoalChart.data.labels = labels;
    fslvGoalChart.data.datasets = goalFields.map((f, i) => ({
      label: f,
      data: fslvHistory.map(h => h.goals[f]),
      borderColor: _CHART_COLORS[(i + 3) % _CHART_COLORS.length],
      backgroundColor: "transparent",
      borderWidth: 2, pointRadius: 0,
    }));
    fslvGoalChart.update();
  }
}

async function fslvRenderGoalTable() {
  const goals = await apiFetch("/api/floefd/goals") || [];
  const el = $("#fslvGoalTable");
  if (!el) return;
  if (!goals.length) {
    el.innerHTML = '<div class="text-dim" style="font-size:12px">No goals defined. Add them in the Goals page.</div>';
    return;
  }
  const rows = goals.map(g => `
    <tr>
      <td>${g.name}</td>
      <td>${g.parameter}</td>
      <td>${g.current_value ? g.current_value.toFixed(4) : '—'}</td>
      <td>${g.min_value ? g.min_value.toFixed(4) : '—'}</td>
      <td>${g.max_value ? g.max_value.toFixed(4) : '—'}</td>
      <td>${g.averaged_value ? g.averaged_value.toFixed(4) : '—'}</td>
      <td style="text-align:center">${g.is_converged ? '✅' : '⏳'}</td>
    </tr>
  `).join("");
  el.innerHTML = `<table class="data-table" style="font-size:12px">
    <thead><tr><th>Goal</th><th>Param</th><th>Current</th><th>Min</th><th>Max</th><th>Avg</th><th>Conv</th></tr></thead>
    <tbody>${rows}</tbody>
  </table>`;
}

async function fslvSaveConfig() {
  const body = {
    turbulence_model: $("#fslvTurbModel")?.value || "k-epsilon",
    wall_function: $("#fslvWallFunc")?.value || "modified",
    max_iterations: parseInt($("#fslvMaxIter")?.value || 200),
    finish_conditions: $("#fslvFinish")?.value || "goals",
    auto_convergence: !!$("#fslvAutoConv")?.checked,
  };
  const d = await apiPut("/api/floefd/solver", body);
  if (d && d.success) toast("✅ Solver config saved");
}

async function fslvRun(n) {
  toast(`⏳ Running ${n} iterations…`);
  await fslvSaveConfig();
  const d = await apiPost("/api/floefd/solver/run", { iterations: n });
  if (d) {
    toast(`✅ Completed ${d.iterations_run} iterations — ${d.status}`);
    fslvConfig.current_iteration = d.current_iteration;
    fslvConfig.convergence_status = d.status;
    fslvHistory = await apiFetch("/api/floefd/solver/history") || [];
    fslvRender();
  }
}

async function fslvReset() {
  await apiPost("/api/floefd/solver/reset", {});
  fslvConfig.current_iteration = 0;
  fslvConfig.convergence_status = "not_started";
  fslvHistory = [];
  toast("⏹ Solver reset");
  fslvRender();
}


// ═══════════════════════════════════════════════════════════════════════════
//  pp* — L7: Post Processing
// ═══════════════════════════════════════════════════════════════════════════

let ppCutPlots = [];
let ppSurfPlots = [];

async function ppLoad() {
  ppCutPlots = await apiFetch("/api/floefd/post/cut-plots") || [];
  ppSurfPlots = await apiFetch("/api/floefd/post/surface-plots") || [];
}

function ppRender() {
  const cutRows = ppCutPlots.map(p => `
    <tr><td>${p.name}</td><td>${p.parameter}</td><td>${p.plane}</td><td>${p.offset} m</td><td>${p.color_map}</td></tr>
  `).join("") || '<tr><td colspan="5" class="text-dim">No cut plots.</td></tr>';

  const surfRows = ppSurfPlots.map(p => `
    <tr><td>${p.name}</td><td>${p.parameter}</td><td>${p.surface_name || '—'}</td><td>${p.color_map}</td></tr>
  `).join("") || '<tr><td colspan="4" class="text-dim">No surface plots.</td></tr>';

  $("#pageContent").innerHTML = `
    <div class="page-header">🖼️ Post Processing</div>
    <p class="text-dim mb-8">
      Visualize simulation results with cut plots, surface plots, flow trajectories, and XY plots.
      Export results to MS Office or standalone reports.
    </p>

    <div style="display:grid;grid-template-columns:1fr 1fr;gap:20px">
      <div>
        <h3 style="margin:0 0 12px;font-size:14px;color:var(--accent)">Cut Plots</h3>
        <table class="data-table mb-8">
          <thead><tr><th>Name</th><th>Parameter</th><th>Plane</th><th>Offset</th><th>Colors</th></tr></thead>
          <tbody>${cutRows}</tbody>
        </table>

        <h3 style="margin:12px 0 8px;font-size:13px;color:var(--fg-dim)">Add Cut Plot</h3>
        <div style="display:flex;gap:6px;flex-wrap:wrap;align-items:flex-end">
          <div class="form-section" style="flex:1;min-width:140px;margin:0">
            <label>Name</label>
            <input type="text" id="ppCutName" value="Cut Plot ${ppCutPlots.length + 1}">
          </div>
          <div class="form-section" style="width:130px;margin:0">
            <label>Parameter</label>
            <select id="ppCutParam">
              <option value="temperature">Temperature</option>
              <option value="pressure">Pressure</option>
              <option value="velocity">Velocity</option>
              <option value="density">Density</option>
            </select>
          </div>
          <div class="form-section" style="width:80px;margin:0">
            <label>Plane</label>
            <select id="ppCutPlane">
              <option value="XY">XY</option>
              <option value="XZ">XZ</option>
              <option value="YZ">YZ</option>
            </select>
          </div>
          <div class="form-section" style="width:90px;margin:0">
            <label>Offset (m)</label>
            <input type="number" id="ppCutOffset" value="0" step="0.01">
          </div>
          <button class="btn btn-accent" onclick="ppAddCut()" style="height:34px">➕</button>
        </div>
      </div>

      <div>
        <h3 style="margin:0 0 12px;font-size:14px;color:var(--accent)">Surface Plots</h3>
        <table class="data-table mb-8">
          <thead><tr><th>Name</th><th>Parameter</th><th>Surface</th><th>Colors</th></tr></thead>
          <tbody>${surfRows}</tbody>
        </table>

        <h3 style="margin:12px 0 8px;font-size:13px;color:var(--fg-dim)">Add Surface Plot</h3>
        <div style="display:flex;gap:6px;flex-wrap:wrap;align-items:flex-end">
          <div class="form-section" style="flex:1;min-width:140px;margin:0">
            <label>Name</label>
            <input type="text" id="ppSurfName" value="Surface Plot ${ppSurfPlots.length + 1}">
          </div>
          <div class="form-section" style="width:130px;margin:0">
            <label>Parameter</label>
            <select id="ppSurfParam">
              <option value="temperature">Temperature</option>
              <option value="pressure">Pressure</option>
              <option value="heat_flux">Heat Flux</option>
            </select>
          </div>
          <button class="btn btn-accent" onclick="ppAddSurf()" style="height:34px">➕</button>
        </div>

        <h3 style="margin:20px 0 12px;font-size:14px;color:var(--accent)">Visualization Options</h3>
        <div class="checkbox-row"><input type="checkbox" checked><span>Show contours</span></div>
        <div class="checkbox-row"><input type="checkbox"><span>Show isolines</span></div>
        <div class="checkbox-row"><input type="checkbox"><span>Show flow vectors</span></div>
        <div class="checkbox-row"><input type="checkbox"><span>Show streamlines</span></div>
        <div class="form-section mt-8">
          <label>Color Map</label>
          <select>
            <option value="rainbow">Rainbow</option>
            <option value="thermal">Thermal (blue→red)</option>
            <option value="grayscale">Grayscale</option>
            <option value="diverging">Diverging</option>
          </select>
        </div>
      </div>
    </div>

    <h3 style="margin:20px 0 12px;font-size:14px;color:var(--accent)">3D Visualization Preview</h3>
    <div style="height:200px;background:#181825;border:1px solid var(--border);border-radius:var(--radius);
                display:flex;align-items:center;justify-content:center;color:var(--fg-dim)">
      <div style="text-align:center">
        🖼️ 3D Result Visualization<br>
        <small>(WebGL / Three.js — coming soon)</small>
      </div>
    </div>
  `;
}

async function ppAddCut() {
  const body = {
    name: ($("#ppCutName")?.value || "").trim() || "Cut Plot",
    parameter: $("#ppCutParam")?.value || "temperature",
    plane: $("#ppCutPlane")?.value || "XY",
    offset: parseFloat($("#ppCutOffset")?.value || 0),
  };
  const d = await apiPost("/api/floefd/post/cut-plots", body);
  if (d) { toast("✅ Cut plot added"); await ppLoad(); ppRender(); }
}

async function ppAddSurf() {
  const body = {
    name: ($("#ppSurfName")?.value || "").trim() || "Surface Plot",
    parameter: $("#ppSurfParam")?.value || "temperature",
  };
  const d = await apiPost("/api/floefd/post/surface-plots", body);
  if (d) { toast("✅ Surface plot added"); await ppLoad(); ppRender(); }
}


// ═══════════════════════════════════════════════════════════════════════════
//  pst* — L8: Parametric Study ("What-if" Analysis)
// ═══════════════════════════════════════════════════════════════════════════

let pstStudies = [];

async function pstLoad() {
  pstStudies = await apiFetch("/api/floefd/parametric") || [];
}

function pstRender() {
  let studyHtml = "";
  if (pstStudies.length === 0) {
    studyHtml = '<div class="text-dim mb-8">No parametric studies. Create one below.</div>';
  } else {
    for (const study of pstStudies) {
      const variantRows = (study.variants || []).map(v => `
        <tr>
          <td>${v.name}</td>
          <td>${Object.entries(v.parameters || {}).map(([k,val]) => `${k}=${val}`).join(', ') || '—'}</td>
          <td><span class="${v.status === 'converged' ? 'text-green' : v.status === 'running' ? 'text-yellow' : ''}">${v.status}</span></td>
          <td>${Object.entries(v.goals_results || {}).map(([k,val]) => `${k}: ${val}`).join(', ') || '—'}</td>
          <td>
            <button class="btn" style="padding:2px 6px;font-size:11px" onclick="pstClone('${study.id}','${v.id}')">📋 Clone</button>
          </td>
        </tr>
      `).join("") || '<tr><td colspan="5" class="text-dim">No variants</td></tr>';

      studyHtml += `
        <div style="border:1px solid var(--border);border-radius:var(--radius);padding:12px;margin-bottom:12px">
          <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px">
            <h3 style="margin:0;font-size:14px;color:var(--accent)">${study.name}</h3>
            <div style="display:flex;gap:6px">
              <button class="btn" style="padding:3px 10px;font-size:11px" onclick="pstAddVariant('${study.id}')">➕ Variant</button>
              <button class="btn btn-green" style="padding:3px 10px;font-size:11px" onclick="pstRunStudy('${study.id}')">▶ Run All</button>
            </div>
          </div>
          <div style="font-size:12px;color:var(--fg-dim);margin-bottom:8px">
            Parameters: ${(study.parameters || []).map(p => p.name).join(', ') || 'None defined'}
          </div>
          <table class="data-table">
            <thead><tr><th>Variant</th><th>Parameters</th><th>Status</th><th>Goal Results</th><th></th></tr></thead>
            <tbody>${variantRows}</tbody>
          </table>
        </div>
      `;
    }
  }

  $("#pageContent").innerHTML = `
    <div class="page-header">🔬 Parametric Study</div>
    <p class="text-dim mb-8">
      Run multiple "what-if" design variants to find the optimum design. FloEFD supports cloning,
      auto-mesh, and batch execution of design variants. Modify design → auto-mesh → execute!
    </p>

    ${studyHtml}

    <h3 style="margin:16px 0 12px;font-size:14px;color:var(--accent)">Create New Study</h3>
    <div style="display:flex;gap:8px;align-items:flex-end">
      <div class="form-section" style="flex:1;margin:0">
        <label>Study Name</label>
        <input type="text" id="pstName" value="Parametric Study ${pstStudies.length + 1}">
      </div>
      <button class="btn btn-accent" onclick="pstCreate()" style="height:34px">➕ Create Study</button>
    </div>

    <h3 style="margin:20px 0 12px;font-size:14px;color:var(--accent)">Study Parameters</h3>
    <p class="text-dim" style="font-size:12px;margin-bottom:8px">
      Define which parameters to vary across design variants (e.g., inlet velocity, heat source power, fan flow rate).
    </p>
    <div style="display:flex;gap:8px;flex-wrap:wrap;align-items:flex-end">
      <div class="form-section" style="width:160px;margin:0">
        <label>Parameter Name</label>
        <input type="text" id="pstParamName" value="inlet_velocity">
      </div>
      <div class="form-section" style="width:100px;margin:0">
        <label>Min</label>
        <input type="number" id="pstParamMin" value="1" step="any">
      </div>
      <div class="form-section" style="width:100px;margin:0">
        <label>Max</label>
        <input type="number" id="pstParamMax" value="10" step="any">
      </div>
      <div class="form-section" style="width:80px;margin:0">
        <label>Steps</label>
        <input type="number" id="pstParamSteps" value="5" min="2">
      </div>
    </div>

    <h3 style="margin:20px 0 12px;font-size:14px;color:var(--fg-dim)">Comparison Table</h3>
    <div class="info-box">
      Run variants to see goal comparison results across all design variants. Multiple "what-if" simulations
      result in optimum design — saving CFD specialist resources for only the most critical analyses.
    </div>
  `;
}

async function pstCreate() {
  const name = ($("#pstName")?.value || "").trim() || "Parametric Study";
  const d = await apiPost("/api/floefd/parametric", { name });
  if (d) { toast("✅ Parametric study created"); await pstLoad(); pstRender(); }
}

async function pstAddVariant(studyId) {
  const idx = pstStudies.find(s => s.id === studyId)?.variants?.length || 0;
  const name = `Variant ${idx + 1}`;
  const paramName = $("#pstParamName")?.value || "inlet_velocity";
  const min = parseFloat($("#pstParamMin")?.value || 1);
  const max = parseFloat($("#pstParamMax")?.value || 10);
  const steps = parseInt($("#pstParamSteps")?.value || 5);
  const value = min + (max - min) * (idx / Math.max(steps - 1, 1));

  const d = await apiPost(`/api/floefd/parametric/${studyId}/variant`, {
    name,
    parameters: { [paramName]: Math.round(value * 100) / 100 },
  });
  if (d) { toast("✅ Variant added"); await pstLoad(); pstRender(); }
}

async function pstClone(studyId, variantId) {
  const d = await apiPost(`/api/floefd/parametric/${studyId}/clone`, {
    variant_id: variantId,
    name: "Clone",
  });
  if (d) { toast("📋 Variant cloned"); await pstLoad(); pstRender(); }
}

async function pstRunStudy(studyId) {
  toast("⏳ Running all variants…");
  const d = await apiPost(`/api/floefd/parametric/${studyId}/run`, {});
  if (d) { toast("✅ All variants completed"); await pstLoad(); pstRender(); }
}


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
