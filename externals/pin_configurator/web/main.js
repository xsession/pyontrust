/* PINCFG_MARKER_20260531E */
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
window.pkgGeneratedArtifacts = Array.isArray(window.pkgGeneratedArtifacts) ? window.pkgGeneratedArtifacts : [];

pkgResultIsUsable = function(result) {
  return !!(result && (
    (Array.isArray(result.packages) && result.packages.length > 0) ||
    !!result.device
  ));
};

pkgEmptyStateMarkup = function() {
  return `<div class="pkg-empty">
    <div class="icon">&#128230;</div>
    <div>MCU Package Generator</div>
    <div class="hint">Upload an MCU datasheet PDF here to generate board, overlay,<br>
      KiCad footprint, and 3D model artifacts for parsed MCU packages.</div>
    <div class="hint" data-pkg-ui-version="20260531zc">MCU-only Package Manager workflow active.</div>
  </div>`;
};

pkgJobKind = function(job) {
  return "mcu";
};

pkgJobPackages = function(job) {
  const result = job?.result || {};
  if (Array.isArray(result.packages)) return result.packages;
  return [];
};

pkgJobTitle = function(job) {
  const result = job?.result || {};
  return result.device?.soc || job?.filename || "MCU";
};

pkgJobSearchText = function(job) {
  const result = job?.result || {};
  const packages = pkgJobPackages(job).map(pkg => pkg?.name || "").join(" ");
  return `${job?.filename || ""} ${result.device?.soc || ""} ${packages}`.toLowerCase();
};

pkgMergeJobs = function(incomingJobs) {
  const merged = new Map(pkgJobs.map(job => [job.job_id, job]));
  (Array.isArray(incomingJobs) ? incomingJobs : []).forEach(job => {
    if (job?.job_id && pkgJobKind(job) === "mcu" && pkgResultIsUsable(job?.result)) {
      merged.set(job.job_id, job);
    }
  });
  pkgJobs = [...merged.values()];
  if (pkgSelectedJob && !pkgJobs.some(job => job.job_id === pkgSelectedJob)) {
    pkgSelectedJob = pkgJobs.length ? pkgJobs[0].job_id : null;
  }
};

pkgSaveToStorage = function() {
  try {
    const data = pkgJobs.map(j => ({
      job_id: j.job_id,
      kind: j.kind,
      filename: j.filename,
      result: j.result,
    }));
    localStorage.setItem("zpincfg_pkg_jobs", JSON.stringify(data));
    localStorage.setItem("zpincfg_pkg_selected", pkgSelectedJob || "");
  } catch (e) {
    console.warn("pkgSaveToStorage:", e);
  }
};

pkgLoadFromStorage = function() {
  try {
    const raw = localStorage.getItem("zpincfg_pkg_jobs");
    if (raw) {
      const data = JSON.parse(raw);
      if (Array.isArray(data) && data.length) {
        pkgJobs = data.filter(job => pkgJobKind(job) === "mcu" && pkgResultIsUsable(job?.result));
        pkgSelectedJob = localStorage.getItem("zpincfg_pkg_selected") || null;
        if (pkgSelectedJob && !pkgJobs.some(job => job.job_id === pkgSelectedJob)) {
          pkgSelectedJob = pkgJobs.length ? pkgJobs[0].job_id : null;
        }
        if (pkgJobs.length !== data.length) {
          pkgSaveToStorage();
        }
        if (!pkgJobs.length) {
          return false;
        }
        return true;
      }
    }
  } catch (e) {
    console.warn("pkgLoadFromStorage:", e);
  }
  return false;
};

pkgRemoveJob = function(jobId) {
  pkgJobs = pkgJobs.filter(j => j.job_id !== jobId);
  if (pkgSelectedJob === jobId) {
    pkgSelectedJob = pkgJobs.length ? pkgJobs[0].job_id : null;
  }
  window.pkgGeneratedArtifacts = [];
  pkgSaveToStorage();
  pkgRenderJobList();
  if (pkgSelectedJob) pkgSelectJob(pkgSelectedJob);
  else $("#pkgMain").innerHTML = pkgEmptyStateMarkup();
};

pkgLoadServerJobs = async function() {
  const incoming = [];
  let loadedFromServer = false;

  try {
    const res = await fetch("/api/parse-jobs");
    const jobs = await res.json();
    if (res.ok && Array.isArray(jobs)) {
      loadedFromServer = true;
      jobs.forEach(job => {
        if (job?.result) incoming.push({
          job_id: job.job_id,
          kind: job.kind || "mcu",
          filename: job.filename,
          result: job.result,
        });
      });
    }
  } catch (_err) {
  }

  if (loadedFromServer) {
    pkgJobs = incoming.filter(job => pkgJobKind(job) === "mcu" && pkgResultIsUsable(job?.result));
    if (pkgSelectedJob && !pkgJobs.some(job => job.job_id === pkgSelectedJob)) {
      pkgSelectedJob = pkgJobs.length ? pkgJobs[0].job_id : null;
    }
    pkgSaveToStorage();
    pkgRenderJobList();
    if (pkgSelectedJob) {
      pkgRenderDetail();
    } else {
      $("#pkgMain").innerHTML = pkgEmptyStateMarkup();
    }
    return;
  }

  if (incoming.length) {
    pkgMergeJobs(incoming);
    pkgSaveToStorage();
    pkgRenderJobList();
    if (pkgSelectedJob) {
      pkgRenderDetail();
    }
  }
};

pkgInit = function() {
  const uploadArea = $("#pdfUploadArea");
  const fileInput = $("#pdfFileInput");
  const jobSearch = $("#pkgJobSearch");

  uploadArea.addEventListener("click", () => fileInput.click());

  fileInput.addEventListener("change", () => {
    if (fileInput.files.length) {
      pkgUploadPdf(fileInput.files[0]);
      fileInput.value = "";
    }
  });

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

  pkgLoadExisting();

  if (pkgLoadFromStorage()) {
    pkgRenderJobList();
    if (pkgSelectedJob) {
      pkgSelectJob(pkgSelectedJob);
    }
  } else {
    $("#pkgMain").innerHTML = pkgEmptyStateMarkup();
  }

  void pkgLoadServerJobs();

  jobSearch?.addEventListener("input", () => {
    pkgRenderJobList();
  });
};

pkgUploadPdf = async function(file) {
  const uploadArea = $("#pdfUploadArea");
  const origHTML = uploadArea.innerHTML;

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

    pkgMergeJobs([{
      job_id: data.job_id,
      kind: "mcu",
      filename: data.filename,
      result: data.result,
    }]);
    window.pkgGeneratedArtifacts = [];

    pkgSaveToStorage();
    pkgRenderJobList();
    pkgSelectJob(data.job_id);
    toast(`Parsed ${data.filename}: ${data.result.packages.length} package(s) found`);
  } catch (err) {
    toast(`Upload failed: ${err.message}`);
  }

  uploadArea.innerHTML = origHTML;
};

pkgRenderJobList = function() {
  const list = $("#pkgJobList");
  const filter = resolveThresholdSearch("pkgJobSearch", pkgJobs.length);

  if (pkgJobs.length === 0) {
    list.innerHTML = `<div class="empty-state" style="padding:20px;">
      <div>No datasheets parsed yet</div>
      <div class="hint">Upload a PDF above</div>
    </div>`;
    return;
  }

  const filteredJobs = pkgJobs.filter((job) => {
    return !filter || pkgJobSearchText(job).includes(filter);
  });

  if (!filteredJobs.length) {
    list.innerHTML = `<div class="empty-state" style="padding:20px;">
      <div>No parsed datasheets match the current search</div>
      <div class="hint">Try another filename, SoC, or package name</div>
    </div>`;
    return;
  }

  list.innerHTML = filteredJobs.map(job => {
    const r = job.result;
    const isSelected = pkgSelectedJob === job.job_id;
    const packages = pkgJobPackages(job);
    const pkgNames = packages.map(p => p.name).filter(Boolean).join(", ") || "No packages";
    const kind = pkgJobKind(job);
    const title = kind === "sensor" ? (r.summary?.part_number || job.filename) : (r.device?.soc || job.filename);
    const meta = kind === "sensor"
      ? `${r.summary?.sensor_type || "sensor"} · ${r.register_map?.register_count || 0} registers · ${r.address?.protocol || "unknown bus"}`
      : `${packages.length} package(s): ${pkgNames} · ${r.pin_mux_count || 0} pins, ${r.pin_mux_total_funcs || 0} alt-funcs`;
    return `
      <div class="pkg-job-item ${isSelected ? "selected" : ""}"
           data-job-id="${job.job_id}">
        <button class="job-remove-btn" data-remove-id="${job.job_id}" title="Remove">&times;</button>
        <div class="job-filename">
          ${job.filename}
          <span class="soc-badge">${kind === "sensor" ? "SENSOR" : "MCU"}</span>
          ${title && title !== job.filename ? `<span class="soc-badge">${title}</span>` : ""}
        </div>
        <div class="job-meta">
          ${meta}
        </div>
      </div>
    `;
  }).join("");

  list.querySelectorAll(".pkg-job-item").forEach(el => {
    el.addEventListener("click", (e) => {
      if (e.target.closest(".job-remove-btn")) return;
      pkgSelectJob(el.dataset.jobId);
    });
  });

  list.querySelectorAll(".job-remove-btn").forEach(btn => {
    btn.addEventListener("click", (e) => {
      e.stopPropagation();
      pkgRemoveJob(btn.dataset.removeId);
    });
  });
};

pkgSelectJob = function(jobId) {
  pkgSelectedJob = jobId;
  pkgSelectedPkgs = new Set();
  window.pkgGeneratedArtifacts = [];
  pkgSaveToStorage();
  pkgRenderJobList();
  pkgRenderDetail();
};

pkgRenderDetail = function() {
  const main = $("#pkgMain");
  const job = pkgJobs.find(j => j.job_id === pkgSelectedJob);

  if (!job) {
    main.innerHTML = pkgEmptyStateMarkup();
    return;
  }

  const r = job.result;
  const kind = pkgJobKind(job);
  const packages = pkgJobPackages(job);
  const device = r.device || {};
  const summary = r.summary || {};
  const address = r.address || {};
  const registerMap = r.register_map || {};

  if (pkgSelectedPkgs.size === 0 && packages.length) {
    packages.forEach(pkg => {
      if (pkg?.name) pkgSelectedPkgs.add(pkg.name);
    });
  }

  const canGenerate = kind === "sensor" ? true : pkgSelectedPkgs.size > 0;
  const title = kind === "sensor" ? (summary.part_number || job.filename) : (device.soc || job.filename);
  const headerSpecs = kind === "sensor"
    ? `
      <span>&#128204; Vendor: ${summary.vendor_name || summary.vendor || "?"}</span>
      <span>&#129514; Type: ${summary.sensor_type || "?"}</span>
      <span>&#128421; Bus: ${address.protocol || "?"}</span>
      <span>&#128209; Registers: ${registerMap.register_count || 0}</span>
    `
    : `
      <span>&#128190; Flash: ${device.flash_size_kb ? device.flash_size_kb + ' KB' : '?'}</span>
      <span>&#128200; SRAM: ${device.sram_size_kb ? device.sram_size_kb + ' KB' : '?'}</span>
      <span>&#9201; Clock: ${device.clock_hz ? (device.clock_hz / 1e6).toFixed(0) + ' MHz' : '?'}</span>
      <span>&#128204; Vendor: ${device.vendor || '?'}</span>
    `;

  const packageCards = packages.length ? `
    <div class="pkg-section">
      <h3>Packages Found (${packages.length})</h3>
      <div class="pkg-card-grid">
        ${packages.map(pkg => {
          const sel = pkg.name ? pkgSelectedPkgs.has(pkg.name) : false;
          const pins = Array.isArray(pkg.pins) ? pkg.pins : [];
          const ioPins = pins.filter(p => p.kind === 'io').length;
          const pwrPins = pins.filter(p => p.kind === 'power' || p.kind === 'ground').length;
          const specPins = pins.filter(p => p.kind === 'special').length;
          return `
            <div class="pkg-card ${sel ? 'selected' : ''}" data-pkg="${pkg.name || ''}">
              <div class="pkg-card-check">${sel ? '&#10003;' : ''}</div>
              <div class="pkg-card-name">${pkg.name || 'Package Override'}</div>
              <div class="pkg-card-meta">
                ${(pkg.pin_count || pins.length || 0)} pins &middot;
                ${ioPins} I/O, ${pwrPins} pwr/gnd, ${specPins} special
              </div>
            </div>`;
        }).join("")}
      </div>
    </div>`
    : `
    <div class="pkg-section">
      <h3>Packages</h3>
      <div class="empty-state">No package geometry was parsed. Use the geometry overrides below to generate CAD output.</div>
    </div>`;

  const previewSection = kind === "sensor"
    ? `
      <div class="pkg-section">
        <h3>Register Preview (${registerMap.register_count || 0} registers)</h3>
        ${Array.isArray(registerMap.registers) && registerMap.registers.length ? `
          <table class="mux-table">
            <thead>
              <tr>
                <th>Address</th>
                <th>Name</th>
                <th>Access</th>
                <th>Reset</th>
              </tr>
            </thead>
            <tbody>
              ${registerMap.registers.slice(0, 8).map(reg => `
                <tr>
                  <td>${reg.address || `0x${Number(reg.address_int || 0).toString(16).toUpperCase()}`}</td>
                  <td>${reg.name || ''}</td>
                  <td>${reg.access || ''}</td>
                  <td>${reg.reset_value || ''}</td>
                </tr>`).join("")}
            </tbody>
          </table>
          ${registerMap.registers.length > 8 ? `<div style="font-size:11px;color:var(--fg-dim);margin-top:6px;">Showing first 8 registers of ${registerMap.registers.length}</div>` : ''}
        ` : '<div class="empty-state">No register-map data extracted</div>'}
      </div>`
    : `
      <div class="pkg-section">
        <h3>Pin-Mux Preview (${r.pin_mux_count || 0} pins, ${r.pin_mux_total_funcs || 0} functions)</h3>
        ${Object.keys(r.pin_mux_sample || {}).length > 0 ? `
          <table class="mux-table">
            <thead>
              <tr>
                <th>Pin</th>
                <th>Peripheral</th>
                <th>Signal</th>
                <th>Dir</th>
              </tr>
            </thead>
            <tbody>
              ${Object.entries(r.pin_mux_sample).map(([pin, funcs]) =>
                funcs.map((f, i) => `
                  <tr>
                    ${i === 0 ? `<td rowspan="${funcs.length}" style="font-weight:600;">${pin}</td>` : ''}
                    <td>${f.peripheral}</td>
                    <td>${f.signal}</td>
                    <td style="color:var(--fg-dim);">${f.direction}</td>
                  </tr>`)
              ).join("")}
            </tbody>
          </table>
          ${r.pin_mux_count > 5 ? `<div style="font-size:11px;color:var(--fg-dim);margin-top:6px;">Showing first 5 pins of ${r.pin_mux_count}</div>` : ''}
        ` : '<div class="empty-state">No pin-mux data extracted</div>'}
      </div>`;

  const geometrySource = packages[0] || {};

  main.innerHTML = `
    <div class="pkg-detail-header">
      <h2>${title}</h2>
      <div class="device-specs">
        ${headerSpecs}
      </div>
    </div>

    <div class="pkg-detail-body">
      ${packageCards}
      ${previewSection}

      <div class="pkg-section">
        <h3>Generation Options</h3>
        <div class="pkg-overrides">
          ${kind === "sensor" ? `
            <label>Driver Name</label>
            <input id="pkgDriverName" placeholder="${(summary.part_number || 'sensor').toLowerCase().replace(/[^a-z0-9]+/g, '_')}" value="">
            <label>Compatible</label>
            <input id="pkgCompatible" placeholder="${summary.vendor || 'vendor'},${(summary.part_number || 'sensor').toLowerCase()}" value="">
            <label>Bus</label>
            <input id="pkgBus" placeholder="${address.protocol || 'i2c'}" value="">
            <label>Custom Template Path</label>
            <input id="pkgCustomTemplatePath" placeholder="custom/${(summary.part_number || 'sensor').toLowerCase()}.txt" value="">
            <label>Custom Template</label>
            <textarea id="pkgCustomTemplate" placeholder="Optional custom template with [[driver_name]] style tokens"></textarea>
          ` : `
            <label>Board Name</label>
            <input id="pkgBoardName" placeholder="lp_${(device.soc || 'custom').toLowerCase()}" value="">
            <label>DTS SOC Include</label>
            <input id="pkgDtsSoc" placeholder="auto-detect" value="">
            <label>DTS Pinctrl Include</label>
            <input id="pkgDtsPinctrl" placeholder="auto-detect" value="">
            <label>Pinctrl Header</label>
            <input id="pkgPinctrlHeader" placeholder="mspm0-pinctrl.h" value="">
            <label>External Devices</label>
            <textarea id="pkgExternalDevices" placeholder='[\n  {\n    "id": "eeprom_24lc32",\n    "display": "24LC32 EEPROM",\n    "category": "memory",\n    "bus": "i2c0",\n    "compatible": "microchip,24lc32",\n    "address": "0x50",\n    "required_signals": ["scl", "sda"],\n    "frameworks": ["zephyr", "arduino"]\n  }\n]'></textarea>
          `}
          <label>Package Name Override</label>
          <input id="pkgPackageName" placeholder="${geometrySource.name || 'auto-detect'}" value="">
          <label>Package Type Override</label>
          <input id="pkgPackageType" placeholder="${geometrySource.package_type || geometrySource.name || 'QFN'}" value="">
          <label>Package Width (mm)</label>
          <input id="pkgWidthMm" type="number" step="0.01" placeholder="${geometrySource.width_mm || ''}" value="">
          <label>Package Height (mm)</label>
          <input id="pkgHeightMm" type="number" step="0.01" placeholder="${geometrySource.height_mm || ''}" value="">
          <label>Pin Pitch (mm)</label>
          <input id="pkgPitchMm" type="number" step="0.01" placeholder="${geometrySource.pitch_mm || ''}" value="">
          <label>Package Thickness (mm)</label>
          <input id="pkgThicknessMm" type="number" step="0.01" placeholder="1.0" value="">
        </div>
      </div>

      <div class="pkg-section">
        <h3>Generated Artifact Bundle</h3>
        ${codeReviewPanelMarkup("pkgGeneratedReview", "Generate package output to review the driver, board, footprint, and 3D files here.")}
      </div>
    </div>

    <div class="pkg-actions">
      <span class="pkg-status" id="pkgStatus">${kind === "sensor" ? "Generate a sensor artifact bundle" : `${pkgSelectedPkgs.size} of ${packages.length} package(s) selected`}</span>
      <span class="spacer"></span>
      <button class="btn" id="pkgBtnSelectAll" ${packages.length ? '' : 'disabled'}>Select All</button>
      <button class="btn btn-accent" id="pkgBtnGenerate" ${canGenerate ? '' : 'disabled'}>
        ${kind === "sensor" ? 'Generate Driver + CAD Bundle' : `Generate ${pkgSelectedPkgs.size} Artifact Bundle(s)`}
      </button>
    </div>
  `;

  renderCodeReviewPanel("pkgGeneratedReview", window.pkgGeneratedArtifacts, {
    emptyMessage: "Generate package output to review the driver, board, footprint, and 3D files here.",
    preferredSelection: window.pkgGeneratedArtifacts[0]?.id,
  });

  main.querySelectorAll(".pkg-card").forEach(card => {
    card.addEventListener("click", () => {
      const name = card.dataset.pkg;
      if (!name) return;
      if (pkgSelectedPkgs.has(name)) {
        pkgSelectedPkgs.delete(name);
      } else {
        pkgSelectedPkgs.add(name);
      }
      pkgRenderDetail();
    });
  });

  const btnAll = main.querySelector("#pkgBtnSelectAll");
  if (btnAll) {
    btnAll.addEventListener("click", () => {
      packages.forEach(p => p?.name && pkgSelectedPkgs.add(p.name));
      pkgRenderDetail();
    });
  }

  const btnGen = main.querySelector("#pkgBtnGenerate");
  if (btnGen) {
    btnGen.addEventListener("click", () => pkgGenerate());
  }
};

pkgGenerate = async function() {
  const job = pkgJobs.find(j => j.job_id === pkgSelectedJob);
  if (!job) return;
  const kind = pkgJobKind(job);

  const statusEl = $("#pkgStatus");
  const btnGen = $("#pkgBtnGenerate");

  if (btnGen) {
    btnGen.disabled = true;
    btnGen.innerHTML = '<span class="spinner" style="width:12px;height:12px;border-width:1.5px;"></span> Generating...';
  }
  if (statusEl) statusEl.textContent = "Generating artifact bundle...";

  let externalDevices;
  const externalDevicesRaw = $("#pkgExternalDevices")?.value.trim() || "";
  if (kind === "mcu" && externalDevicesRaw) {
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
        btnGen.innerHTML = `Generate ${pkgSelectedPkgs.size} Artifact Bundle(s)`;
      }
      return;
    }
  }

  const packageOverrides = {
    package_name: $("#pkgPackageName")?.value.trim() || undefined,
    package_type: $("#pkgPackageType")?.value.trim() || undefined,
    width_mm: $("#pkgWidthMm")?.value.trim() || undefined,
    height_mm: $("#pkgHeightMm")?.value.trim() || undefined,
    pitch_mm: $("#pkgPitchMm")?.value.trim() || undefined,
    thickness_mm: $("#pkgThicknessMm")?.value.trim() || undefined,
  };
  Object.keys(packageOverrides).forEach(k => packageOverrides[k] === undefined && delete packageOverrides[k]);

  const body = {
    job_id: job.job_id,
    packages: [...pkgSelectedPkgs],
    board_name: $("#pkgBoardName")?.value.trim() || undefined,
    dts_soc_include: $("#pkgDtsSoc")?.value.trim() || undefined,
    dts_pinctrl_include: $("#pkgDtsPinctrl")?.value.trim() || undefined,
    pinctrl_header: $("#pkgPinctrlHeader")?.value.trim() || undefined,
    external_devices: externalDevices,
    register: true,
    driver_name: $("#pkgDriverName")?.value.trim() || undefined,
    compatible: $("#pkgCompatible")?.value.trim() || undefined,
    bus: $("#pkgBus")?.value.trim() || undefined,
    custom_template_path: $("#pkgCustomTemplatePath")?.value.trim() || undefined,
    custom_template: $("#pkgCustomTemplate")?.value || undefined,
    package_overrides: Object.keys(packageOverrides).length ? packageOverrides : undefined,
  };

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
      const names = Array.isArray(data.files) ? data.files.map(f => f.filename).join(", ") : "";
      window.pkgGeneratedArtifacts = Array.isArray(data.artifacts) ? data.artifacts : [];
      renderCodeReviewPanel("pkgGeneratedReview", window.pkgGeneratedArtifacts, {
        emptyMessage: "Generate package output to review the driver, board, footprint, and 3D files here.",
        preferredSelection: window.pkgGeneratedArtifacts[0]?.id,
      });
      const summary = names || `${window.pkgGeneratedArtifacts.length} generated artifact(s)`;
      toast(`Generated: ${summary}`);
      if (statusEl) statusEl.textContent = `✓ Generated: ${summary}`;

      if (kind === "mcu") {
        pkgLoadExisting();
        loadBoardList();
      }
    }
  } catch (err) {
    toast(`Failed: ${err.message}`);
    if (statusEl) statusEl.textContent = `Failed: ${err.message}`;
  }

  if (btnGen) {
    btnGen.disabled = false;
    btnGen.innerHTML = kind === "sensor"
      ? "Generate Driver + CAD Bundle"
      : `Generate ${pkgSelectedPkgs.size} Artifact Bundle(s)`;
  }
};

pkgLoadExisting = async function() {
  try {
    const res = await fetch("/api/generated-packages");
    const files = await res.json();
    const list = $("#existingPkgList");

    if (files.length === 0) {
      list.innerHTML = '<li style="color:var(--fg-dim);font-size:12px;padding:8px 10px;">No board files yet</li>';
      return;
    }

    list.innerHTML = files.map(f => {
      const parts = f.module.split("_");
      let soc = "", pkg = "";
      const pkgRe = /^(lqfp|qfp|ufbga|wlcsp|bga|qfn|csp|lga|ssop|tssop|soic)\d*$/i;
      for (let i = parts.length - 1; i >= 0; i--) {
        if (pkgRe.test(parts[i])) {
          pkg = parts.slice(i).join("_").toUpperCase();
          soc = parts.slice(0, i).join("_").toUpperCase();
          break;
        }
      }
      if (!soc) soc = f.module.toUpperCase();
      const label = pkg ? `${soc} - ${pkg}` : soc;

      return `
      <li class="pkg-board-link" data-module="${f.module}" title="Click to open in Pin Configurator">
        <span class="file-icon">&#128196;</span>
        <span>${label}</span>
        <span class="file-size">${(f.size / 1024).toFixed(1)} KB</span>
      </li>`;
    }).join("");

    list.querySelectorAll(".pkg-board-link").forEach(li => {
      li.style.cursor = "pointer";
      li.addEventListener("click", () => {
        const mod = li.dataset.module;
        const opts = [...boardSelect.options];
        const match = opts.find(o => o.value === mod || o.value.includes(mod));
        if (match) {
          boardSelect.value = match.value;
          loadBoard(match.value);
          activateAppTab("configurator");
          toast(`Loaded ${mod} in Pin Configurator`);
        } else {
          toast(`Board "${mod}" not found in selector`);
        }
      });
    });
  } catch (err) {
    console.warn("Failed to load existing packages", err);
  }
};

// ══════════════════════════════════════════════════════════════════════
// Module Configurator  (dynamic – all Zephyr modules)
// ══════════════════════════════════════════════════════════════════════
let pinStates    = {};     // { pin_number: { af, props } }
let periphStates = {};     // { periph_name: enabled }
let periphCoreStates = {}; // { periph_name: core_id }
let externalDeviceStates = {}; // { device_id: { selected, bus } }
let availableBoards = [];  // Loaded board summaries from /api/boards
let boardData = null;      // Active board definition from /api/board/<id>
let selectedPin  = null;   // Currently selected pin number
let highlightedPeripheral = ""; // Peripheral currently highlighted on the chip
let highlightedPeripheralSignal = ""; // Specific signal currently highlighted on the chip
let boardEditorDrafts = [];

let generatedOverlay = "";
let generatedConf    = "";
let generatedTargets = {};
let generatedFragments = {
  pin: { overlay: "", prj_conf: "" },
  modules: { overlay: "", prj_conf: "" },
  peripherals: { overlay: "", prj_conf: "" },
  clock: { overlay: "", prj_conf: "" },
  protocols: { overlay: "", prj_conf: "", code: "", header: "", integration: "" },
  lvgl: { overlay: "", prj_conf: "", code: "", header: "", hooksHeader: "", hooks: "", integration: "" },
};
const LVGL_LAYOUT_PRESETS = {
  phone: { width: 360, height: 640, label: "Phone 360 x 640" },
  dashboard: { width: 480, height: 272, label: "Dashboard 480 x 272" },
  watch: { width: 240, height: 240, label: "Watch 240 x 240" },
  panel: { width: 800, height: 480, label: "Panel 800 x 480" },
};
const LVGL_SCREEN_TRANSITIONS = {
  none: { label: "No animation", anim: "LV_SCR_LOAD_ANIM_NONE" },
  move_left: { label: "Move left", anim: "LV_SCR_LOAD_ANIM_MOVE_LEFT" },
  move_right: { label: "Move right", anim: "LV_SCR_LOAD_ANIM_MOVE_RIGHT" },
  move_top: { label: "Move up", anim: "LV_SCR_LOAD_ANIM_MOVE_TOP" },
  move_bottom: { label: "Move down", anim: "LV_SCR_LOAD_ANIM_MOVE_BOTTOM" },
  fade_in: { label: "Fade in", anim: "LV_SCR_LOAD_ANIM_FADE_IN" },
  fade_on: { label: "Fade on", anim: "LV_SCR_LOAD_ANIM_FADE_ON" },
  over_left: { label: "Over left", anim: "LV_SCR_LOAD_ANIM_OVER_LEFT" },
  over_right: { label: "Over right", anim: "LV_SCR_LOAD_ANIM_OVER_RIGHT" },
};
let lvglLayoutState = null;
let lvglLayoutDrag = null;
let lvglLayoutNextId = 1;
window.LVGL_LAYOUT_PRESETS = LVGL_LAYOUT_PRESETS;
window.LVGL_SCREEN_TRANSITIONS = LVGL_SCREEN_TRANSITIONS;
Object.defineProperty(window, "lvglLayoutState", {
  get() { return lvglLayoutState; },
  set(value) { lvglLayoutState = value; },
});
Object.defineProperty(window, "lvglLayoutDrag", {
  get() { return lvglLayoutDrag; },
  set(value) { lvglLayoutDrag = value; },
});
Object.defineProperty(window, "lvglLayoutNextId", {
  get() { return lvglLayoutNextId; },
  set(value) { lvglLayoutNextId = value; },
});
let activeTab        = "overlay";
let boardEditorPendingDelete = "";
let boardEditorPreviewBoard = null;
let boardEditorCanvasStart = null;
let boardEditorCanvasDrag = null;
let boardEditorWireHandleDrag = null;
let boardEditorPreviewTimer = null;
let boardEditorDeviceLibrary = [];
let boardEditorCanvasZoom = 1.0;
let boardEditorCanvasFitMode = true;
let boardEditorCanvasResizeObserver = null;
let clkOverviewResizeObserver = null;
let chipAreaResizeObserver = null;
let zephyrCatalogExternalDevices = [];
let zephyrCatalogBoardEditorEntries = [];
let zephyrCatalogItems = [];
let zephyrCatalogRoot = "";
let zephyrCatalogActiveKey = "";
let zephyrCatalogFilter = "all";
let zephyrCatalogSearch = "";
let zephyrCatalogSummary = { mcu_count: 0, sensor_count: 0, display_count: 0 };
let arduinoWorkspaceState = createArduinoWorkspaceState();
let monacoLoadPromise = null;
let generatedFilesOverviewSelection = "";
let generatedFilesEditor = null;
let generatedFilesEditorFailed = false;
let generatedFilesFilter = "";
const generatedFilesModels = new Map();
const LARGE_LIST_SEARCH_THRESHOLD = 5;

// Zoom state
let chipZoom = 1.0;
let chipZoomMode = "fit";
let pinSummaryOverlayState = {
  left: 12,
  top: 12,
  width: null,
  height: null,
  initialized: false,
};
let pinSummaryOverlayPointerState = null;
let pinSummarySortState = {
  key: "pinNumber",
  direction: "asc",
};
let sidePanelLayoutState = {
  leftWidth: 240,
  rightWidth: 320,
  leftCollapsed: false,
  rightCollapsed: false,
};
let sidePanelResizeState = null;
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
window.$ = $;

const boardSelect  = $("#boardSelect");
const chipLabel    = $("#chipLabel");
const statsLabel   = $("#statsLabel");
const mainLayout   = $("#mainLayout");
const chipArea     = $("#chipArea");
const chipContainer= $("#chipContainer");
const periphPanel  = $("#periphPanel");
const periphResizeHandle = $("#periphResizeHandle");
const periphPanelToggle = $("#periphPanelToggle");
const configPanel  = $("#configPanel");
const configResizeHandle = $("#configResizeHandle");
const configPanelToggle = $("#configPanelToggle");
const pinSummaryOverlay = $("#pinSummaryOverlay");
const pinSummaryHeader = $("#pinSummaryHeader");
const pinSummaryCount = $("#pinSummaryCount");
const pinSummaryBody = $("#pinSummaryBody");
const pinSummaryEmpty = $("#pinSummaryEmpty");
const pinSummaryExportFormat = $("#pinSummaryExportFormat");
const pinSummaryExportBtn = $("#pinSummaryExportBtn");
const pinSummaryResizeHandle = $("#pinSummaryResizeHandle");
const outputBar    = $("#outputBar");
const outputTabs   = $("#outputBar .output-tabs");
const outputPre    = $("#outputPre");
const outputFilesView = $("#outputFilesView");
const outputFilesSearch = $("#outputFilesSearch");
const outputFilesList = $("#outputFilesList");
const outputFilesEditorHost = $("#outputFilesEditor");
const outputFilesFallback = $("#outputFilesFallback");
const outputFilesCurrentPath = $("#outputFilesCurrentPath");
const outputFilesCopyBtn = $("#outputFilesCopyBtn");
const outputFilesDownloadBtn = $("#outputFilesDownloadBtn");

// ── Helpers ──────────────────────────────────────────────────────────

function toast(msg) {
  const el = $("#toast");
  el.textContent = msg;
  el.classList.add("show");
  setTimeout(() => el.classList.remove("show"), 2500);
}

async function requestPathDialog({ dialogKind, title = "", initialPath = "", fileTypes = [], defaultExtension = "" }) {
  const res = await fetch("/api/path-dialog", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      dialog_kind: dialogKind,
      title,
      initial_path: initialPath,
      filetypes: fileTypes,
      default_extension: defaultExtension,
    }),
  });
  const payload = await res.json();
  if (!res.ok) {
    throw new Error(payload.error || "Failed to open native path dialog");
  }
  return payload;
}

function bindPathBrowseButton(buttonSelector, inputSelector, resolveOptions, onSelected) {
  const button = $(buttonSelector);
  const input = $(inputSelector);
  if (!button || !input) return;

  button.addEventListener("click", async () => {
    try {
      const options = typeof resolveOptions === "function"
        ? resolveOptions(input)
        : (resolveOptions || {});
      const result = await requestPathDialog({
        ...options,
        initialPath: input.value.trim(),
      });
      if (result.cancelled || !result.path) return;
      input.value = result.path;
      input.dispatchEvent(new Event("change", { bubbles: true }));
      if (typeof onSelected === "function") {
        await onSelected(input, result);
      }
    } catch (err) {
      toast(err.message || "Failed to open path browser");
    }
  });
}

function lvglImportBrowseDialogOptions() {
  const mode = lvglCurrentImportMode();
  if (mode === "zephyr") {
    return {
      dialogKind: "directory",
      title: "Select Zephyr project directory",
    };
  }
  if (mode === "display-pdf") {
    return {
      dialogKind: "open-file",
      title: "Select display datasheet PDF",
      fileTypes: [
        { name: "PDF files", patterns: ["*.pdf"] },
        { name: "All files", patterns: ["*.*"] },
      ],
    };
  }
  return {
    dialogKind: "open-file",
    title: "Select LVGL layout source",
    fileTypes: [
      { name: "Layout files", patterns: ["*.json", "*.lvgl", "*.zpinproj"] },
      { name: "All files", patterns: ["*.*"] },
    ],
  };
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

function escapeXml(value) {
  return String(value ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&apos;");
}

function downloadTextFile(filename, content, mimeType = "text/plain;charset=utf-8") {
  const blob = new Blob([content], { type: mimeType });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  window.setTimeout(() => URL.revokeObjectURL(url), 0);
}

function createArduinoWorkspaceState() {
  return {
    projectPath: "",
    outputPath: "",
    validationPath: "",
    sketchName: "",
    scannedFiles: [],
    importPreview: null,
    generatedFiles: {},
    activeFile: "",
  };
}

function normalizeArduinoScannedFile(file) {
  const source = file && typeof file === "object" ? file : {};
  return {
    path: String(source.path || ""),
    relative: String(source.relative || source.name || ""),
    name: String(source.name || ""),
    type: String(source.type || ""),
    size: Number(source.size || 0),
    content: String(source.content || ""),
    selected: !!(source.selected || source._selected),
  };
}

function arduinoSerializeState() {
  return {
    project_path: arduinoWorkspaceState.projectPath,
    output_path: arduinoWorkspaceState.outputPath,
    validation_path: arduinoWorkspaceState.validationPath,
    sketch_name: arduinoWorkspaceState.sketchName,
    scanned_files: arduinoWorkspaceState.scannedFiles.map((file) => ({
      path: file.path,
      relative: file.relative,
      name: file.name,
      type: file.type,
      size: file.size,
      content: file.content,
      selected: !!file.selected,
    })),
    import_preview: arduinoWorkspaceState.importPreview || null,
    generated_files: { ...(arduinoWorkspaceState.generatedFiles || {}) },
    active_file: arduinoWorkspaceState.activeFile || "",
  };
}

function arduinoEnsureActiveFile() {
  const filenames = Object.keys(arduinoWorkspaceState.generatedFiles || {}).sort();
  if (!filenames.length) {
    arduinoWorkspaceState.activeFile = "";
    return;
  }
  if (!filenames.includes(arduinoWorkspaceState.activeFile)) {
    arduinoWorkspaceState.activeFile = filenames[0];
  }
}

function arduinoSelectedImportText(type) {
  return arduinoWorkspaceState.scannedFiles
    .filter((file) => file.selected && file.type === type)
    .map((file) => file.content)
    .join("\n");
}

function arduinoAutoSelectScannedFiles() {
  let overlaySelected = false;
  let confSelected = false;
  arduinoWorkspaceState.scannedFiles.forEach((file) => {
    file.selected = false;
  });
  arduinoWorkspaceState.scannedFiles.forEach((file) => {
    if (file.type === "overlay" && !overlaySelected) {
      file.selected = true;
      overlaySelected = true;
      return;
    }
    if (file.type === "conf" && !confSelected) {
      file.selected = true;
      confSelected = true;
    }
  });
}

function arduinoRenderScannedFiles() {
  const list = $("#arduinoProjectFiles");
  if (!list) return;
  if (!arduinoWorkspaceState.scannedFiles.length) {
    list.innerHTML = '<div class="zcatalog-empty">No Zephyr project scanned yet.</div>';
    return;
  }
  list.innerHTML = arduinoWorkspaceState.scannedFiles.map((file, index) => `
    <button class="zcatalog-item${file.selected ? " active" : ""}" data-arduino-scan-index="${index}">
      <strong>${escapeHtml(file.relative || file.name || `file-${index + 1}`)}</strong>
      <span class="zcatalog-item-meta">${escapeHtml(file.type || "file")} • ${Math.max(0, file.size / 1024).toFixed(1)} KB</span>
    </button>
  `).join("");
  list.querySelectorAll("[data-arduino-scan-index]").forEach((button) => {
    button.addEventListener("click", async () => {
      const index = Number(button.dataset.arduinoScanIndex);
      const file = arduinoWorkspaceState.scannedFiles[index];
      if (!file) return;
      file.selected = !file.selected;
      arduinoRenderScannedFiles();
      await arduinoPreviewImport();
    });
  });
}

function arduinoRenderImportPreview() {
  const preview = $("#arduinoImportPreview");
  const summary = $("#arduinoImportSummary");
  if (!preview || !summary) return;
  if (!arduinoWorkspaceState.importPreview) {
    preview.className = "zcatalog-note";
    preview.innerHTML = "Select a Zephyr project or click Preview Import after choosing files to inspect what will be applied to the current board.";
    summary.textContent = arduinoWorkspaceState.projectPath
      ? `Project: ${arduinoWorkspaceState.projectPath}`
      : "Scan a Zephyr project to pull in its overlay and prj.conf, then regenerate the matching Arduino sketch from the current board.";
    return;
  }
  const data = arduinoWorkspaceState.importPreview;
  const pins = data.pins || [];
  const peripherals = data.peripherals || [];
  const warnings = data.warnings || [];
  summary.textContent = `${pins.length} pin assignment(s) • ${peripherals.length} peripheral(s) • ${warnings.length} warning(s)`;
  preview.className = "zcatalog-note";
  preview.innerHTML = `
    <div><strong>Pins:</strong> ${pins.length ? pins.map((pin) => `${escapeHtml(pin.pin_name || pin.node_label || "pin")} → ${escapeHtml(`${pin.peripheral}.${pin.signal}`)}`).join("<br>") : "None detected"}</div>
    <div style="margin-top:8px;"><strong>Peripherals:</strong> ${peripherals.length ? peripherals.map((peripheral) => escapeHtml(peripheral.name)).join(", ") : "None detected"}</div>
    ${warnings.length ? `<div style="margin-top:8px;"><strong>Warnings:</strong><br>${warnings.map((warning) => escapeHtml(warning)).join("<br>")}</div>` : ""}
  `;
}

function arduinoRenderGeneratedFiles() {
  const filenames = Object.keys(arduinoWorkspaceState.generatedFiles || {}).sort();
  arduinoEnsureActiveFile();
  renderCodeReviewPanel("arduinoGeneratedReview", filenames.map((filename) => ({
    id: filename,
    label: filename,
    path: `arduino/${filename}`,
    group: "Arduino Importer",
    content: arduinoWorkspaceState.generatedFiles[filename] || "",
  })), {
    emptyMessage: "Generate output to preview the Arduino sketch and helper files for the active board.",
    preferredSelection: arduinoWorkspaceState.activeFile || filenames[0] || "",
    onSelect: (file) => {
      arduinoWorkspaceState.activeFile = file.id;
    },
  });
}

function arduinoRenderModulePreview() {
  const pre = $("#arduinoModulePreview");
  if (!pre) return;
  pre.textContent = generatedFragments.modules?.prj_conf || "No module fragment generated yet.";
}

function formatAsciiBoardSummary(board) {
  if (!board) return "No board loaded.";
  const boardName = String(board.board || "board n/a").trim() || "board n/a";
  const socName = String(board.soc || "soc n/a").trim() || "soc n/a";
  const packageName = String(board.package || "package n/a").trim() || "package n/a";
  return `${boardName} - ${socName} - ${packageName}`;
}

function arduinoRender() {
  const pathInput = $("#arduinoProjectPath");
  if (pathInput) pathInput.value = arduinoWorkspaceState.projectPath || "";
  const outputInput = $("#arduinoOutputPath");
  if (outputInput) outputInput.value = arduinoWorkspaceState.outputPath || "";
  const validationInput = $("#arduinoValidationPath");
  if (validationInput) validationInput.value = arduinoWorkspaceState.validationPath || "";
  const sketchInput = $("#arduinoSketchName");
  if (sketchInput) sketchInput.value = arduinoWorkspaceState.sketchName || "";
  const boardSummary = $("#arduinoBoardSummary");
  if (boardSummary) boardSummary.textContent = formatAsciiBoardSummary(boardData);
  arduinoRenderScannedFiles();
  arduinoRenderImportPreview();
  arduinoRenderGeneratedFiles();
  arduinoRenderModulePreview();
}

function arduinoRestoreState(state) {
  const source = state && typeof state === "object" ? state : {};
  arduinoWorkspaceState = createArduinoWorkspaceState();
  arduinoWorkspaceState.projectPath = String(source.project_path || "");
  arduinoWorkspaceState.outputPath = String(source.output_path || "");
  arduinoWorkspaceState.validationPath = String(source.validation_path || "");
  arduinoWorkspaceState.sketchName = String(source.sketch_name || "");
  arduinoWorkspaceState.scannedFiles = Array.isArray(source.scanned_files)
    ? source.scanned_files.map(normalizeArduinoScannedFile)
    : [];
  arduinoWorkspaceState.importPreview = source.import_preview && typeof source.import_preview === "object"
    ? source.import_preview
    : null;
  arduinoWorkspaceState.generatedFiles = source.generated_files && typeof source.generated_files === "object"
    ? { ...source.generated_files }
    : {};
  arduinoWorkspaceState.activeFile = String(source.active_file || "");
  arduinoEnsureActiveFile();
  arduinoRender();
}

function arduinoHandleBoardChanged() {
  arduinoWorkspaceState.importPreview = null;
  arduinoWorkspaceState.generatedFiles = {};
  arduinoWorkspaceState.activeFile = "";
  if (!arduinoWorkspaceState.sketchName && boardData?.board) {
    arduinoWorkspaceState.sketchName = boardData.board;
  }
  arduinoRender();
}

async function arduinoPreviewImport() {
  const overlay = arduinoSelectedImportText("overlay");
  const conf = arduinoSelectedImportText("conf");
  if (!overlay && !conf) {
    arduinoWorkspaceState.importPreview = null;
    arduinoRenderImportPreview();
    return;
  }
  try {
    const res = await fetch("/api/import-config", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        overlay,
        conf,
        board_name: boardData?.board || "",
      }),
    });
    const data = await res.json();
    if (!res.ok) {
      toast(`Parse error: ${data.error || "Failed to preview import"}`);
      return;
    }
    arduinoWorkspaceState.importPreview = data;
    arduinoRenderImportPreview();
  } catch (err) {
    toast(`Parse failed: ${err.message}`);
  }
}

async function arduinoScanProject() {
  const path = $("#arduinoProjectPath")?.value.trim() || arduinoWorkspaceState.projectPath || "";
  if (!path) {
    toast("Enter a Zephyr project directory path");
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
    arduinoWorkspaceState.projectPath = path;
    arduinoWorkspaceState.scannedFiles = Array.isArray(data.files)
      ? data.files.map(normalizeArduinoScannedFile)
      : [];
    arduinoAutoSelectScannedFiles();
    arduinoRenderScannedFiles();
    await arduinoPreviewImport();
    toast(arduinoWorkspaceState.scannedFiles.length
      ? `Found ${arduinoWorkspaceState.scannedFiles.length} file(s)`
      : "No .overlay or .conf files found");
  } catch (err) {
    toast(`Scan failed: ${err.message}`);
  }
}

async function arduinoLoadRealBlinkyDemo() {
  try {
    const res = await fetch("/api/demo-app/real-blinky-sample");
    const data = await res.json();
    if (!res.ok) {
      toast(data.error || "Failed to locate the real blinky demo");
      return;
    }
    if (!data.exists || !data.project_path) {
      toast("Real blinky demo is not available in this workspace");
      return;
    }
    arduinoWorkspaceState.projectPath = data.project_path;
    const input = $("#arduinoProjectPath");
    if (input) input.value = data.project_path;
    toast(`Loaded ${data.name} for ${data.board_id}`);
    await arduinoScanProject();
  } catch (err) {
    toast(err.message || "Failed to load the real blinky demo");
  }
}

function applyImportedConfig(data) {
  if (!data || !boardData) {
    toast("No parsed data to apply");
    return null;
  }

  let applied = 0;

  for (const pp of (data.pins || [])) {
    const boardPin = boardData.pins.find((pin) =>
      pin.name.toUpperCase() === (pp.pin_name || "").toUpperCase()
    );
    if (!boardPin) continue;

    const af = boardPin.alt_functions.find((entry) =>
      entry.pincm === pp.pincm && entry.function_id === pp.function_id
    ) || boardPin.alt_functions.find((entry) =>
      entry.peripheral === pp.peripheral && entry.signal === pp.signal
    );

    if (!af) continue;
    pinStates[boardPin.number] = {
      af,
      props: {
        bias_pull_up: pp.bias_pull_up || false,
        bias_pull_down: pp.bias_pull_down || false,
        drive_open_drain: pp.drive_open_drain || false,
        input_enable: pp.input_enable || false,
      },
    };
    applied += 1;
  }

  for (const peripheral of (data.peripherals || [])) {
    if (peripheral.name in periphStates) {
      periphStates[peripheral.name] = peripheral.enabled;
    }
  }

  renderPeripherals();
  renderChip();
  renderConfigPanel();
  interruptRender();

  return {
    appliedPins: applied,
    peripheralCount: (data.peripherals || []).length,
  };
}

function arduinoApplyImport() {
  const applied = applyImportedConfig(arduinoWorkspaceState.importPreview);
  if (!applied) return;
  toast(`Imported ${applied.appliedPins} pin(s), ${applied.peripheralCount} peripheral(s)`);
  arduinoRender();
}

async function arduinoGenerateFromCurrentBoard() {
  const generated = await requestGenerateOutput();
  if (!generated) return;
  arduinoWorkspaceState.generatedFiles = { ...(generatedTargets.arduino || {}) };
  arduinoEnsureActiveFile();
  arduinoRenderGeneratedFiles();
  arduinoRenderModulePreview();
}

async function arduinoExportProject() {
  const files = arduinoWorkspaceState.generatedFiles || {};
  if (!Object.keys(files).length) {
    toast("Generate Arduino output before exporting a project");
    return;
  }

  const outputPath = $("#arduinoOutputPath")?.value.trim() || arduinoWorkspaceState.outputPath || "";
  if (!outputPath) {
    toast("Choose an Arduino project directory first");
    return;
  }

  const sketchName = $("#arduinoSketchName")?.value.trim() || arduinoWorkspaceState.sketchName || "";
  arduinoWorkspaceState.outputPath = outputPath;
  arduinoWorkspaceState.sketchName = sketchName;

  try {
    const res = await fetch("/api/save-arduino-project", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        output_dir: outputPath,
        sketch_name: sketchName,
        files,
      }),
    });
    const data = await res.json();
    if (!res.ok) {
      toast(data.error || "Failed to export Arduino project");
      return;
    }
    toast(`Arduino project exported to ${data.output_dir}`);
  } catch (err) {
    toast(err.message || "Failed to export Arduino project");
  }
}

async function arduinoExportValidationBundle() {
  if (!generatedOverlay && !generatedConf) {
    toast("Generate output before exporting a Renode validation bundle");
    return;
  }

  const outputPath = $("#arduinoValidationPath")?.value.trim() || arduinoWorkspaceState.validationPath || "";
  if (!outputPath) {
    toast("Choose a validation bundle directory first");
    return;
  }

  arduinoWorkspaceState.validationPath = outputPath;

  try {
    const res = await fetch("/api/demo-app/export", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        output_dir: outputPath,
        overwrite: true,
        board_id: boardData?.board || "",
        pin_states: cloneJson(pinStates),
        periph_states: cloneJson(periphStates),
        periph_core_states: cloneJson(periphCoreStates),
        external_device_states: cloneJson(externalDeviceStates),
        generated_overlay: generatedOverlay,
        generated_conf: generatedConf,
        generated_fragments: cloneJson(generatedFragments),
      }),
    });
    const data = await res.json();
    if (!res.ok) {
      toast(data.error || "Failed to export Renode validation bundle");
      return;
    }
    toast(`Renode validation bundle exported to ${data.output_dir}`);
  } catch (err) {
    toast(err.message || "Failed to export Renode validation bundle");
  }
}

function arduinoInit() {
  if (!$("#arduinoProjectFiles")) return;
  $("#arduinoBtnScanProject")?.addEventListener("click", () => {
    void arduinoScanProject();
  });
  $("#arduinoBtnLoadRealBlinky")?.addEventListener("click", () => {
    void arduinoLoadRealBlinkyDemo();
  });
  $("#arduinoBtnPreviewImport")?.addEventListener("click", () => {
    void arduinoPreviewImport();
  });
  $("#arduinoBtnApplyImport")?.addEventListener("click", arduinoApplyImport);
  $("#arduinoBtnGenerate")?.addEventListener("click", () => {
    void arduinoGenerateFromCurrentBoard();
  });
  $("#arduinoBtnExportProject")?.addEventListener("click", () => {
    void arduinoExportProject();
  });
  $("#arduinoBtnExportValidation")?.addEventListener("click", () => {
    void arduinoExportValidationBundle();
  });
  $("#arduinoBtnOpenModules")?.addEventListener("click", () => {
    void openAppTab("modules");
  });
  $("#arduinoProjectPath")?.addEventListener("change", (event) => {
    arduinoWorkspaceState.projectPath = event.target.value.trim();
  });
  $("#arduinoOutputPath")?.addEventListener("change", (event) => {
    arduinoWorkspaceState.outputPath = event.target.value.trim();
  });
  $("#arduinoValidationPath")?.addEventListener("change", (event) => {
    arduinoWorkspaceState.validationPath = event.target.value.trim();
  });
  $("#arduinoSketchName")?.addEventListener("change", (event) => {
    arduinoWorkspaceState.sketchName = event.target.value.trim();
  });
  arduinoRender();
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

function resolveThresholdSearch(inputId, totalCount, incomingFilter = null) {
  const input = document.getElementById(inputId);
  const normalizedIncoming = typeof incomingFilter === "string"
    ? incomingFilter.trim().toLowerCase()
    : null;
  if (!input) return normalizedIncoming || "";

  const visible = totalCount > LARGE_LIST_SEARCH_THRESHOLD;
  input.hidden = !visible;
  if (!visible) {
    if (input.value) input.value = "";
    return "";
  }

  if (normalizedIncoming !== null && input.value.trim().toLowerCase() !== normalizedIncoming) {
    input.value = normalizedIncoming;
  }
  return normalizedIncoming !== null ? normalizedIncoming : input.value.trim().toLowerCase();
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
  [...DEFAULT_EXTERNAL_DEVICE_CATALOG, ...zephyrCatalogExternalDevices, ...(boardData?.external_devices || [])]
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

function peripheralRecord(peripheralName) {
  return boardData?.peripherals?.find(peripheral => peripheral.name === peripheralName) || null;
}

function normalizeSignalToken(value) {
  return String(value || "")
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "");
}

function signalAliasTokens(signal) {
  const token = normalizeSignalToken(signal);
  if (!token) return [];

  const aliases = new Set([token]);
  const aliasMap = {
    copi: ["mosi"],
    pico: ["mosi"],
    mosi: ["copi", "pico"],
    cipo: ["miso"],
    poci: ["miso"],
    miso: ["cipo", "poci"],
    sclk: ["sck", "clk"],
    clk: ["sck", "sclk"],
    sck: ["sclk", "clk"],
    nss: ["cs", "ss", "cs0", "cs1", "cs2", "cs3"],
    ss: ["cs", "nss", "cs0", "cs1", "cs2", "cs3"],
    chipselect: ["cs", "cs0", "cs1", "cs2", "cs3"],
    cs: ["ss", "nss", "chipselect", "cs0", "cs1", "cs2", "cs3"],
    cs0: ["cs", "ss", "nss", "chipselect", "cs1", "cs2", "cs3"],
    cs1: ["cs", "ss", "nss", "chipselect", "cs0", "cs2", "cs3"],
    cs2: ["cs", "ss", "nss", "chipselect", "cs0", "cs1", "cs3"],
    cs3: ["cs", "ss", "nss", "chipselect", "cs0", "cs1", "cs2"],
    tx: ["txd"],
    txd: ["tx"],
    rx: ["rxd"],
    rxd: ["rx"],
  };
  (aliasMap[token] || []).forEach((alias) => aliases.add(alias));
  return [...aliases];
}

function assignedSignalsByPeripheral() {
  const assigned = {};
  Object.values(pinStates || {}).forEach((state) => {
    const peripheral = state?.af?.peripheral;
    if (!peripheral) return;
    if (!assigned[peripheral]) assigned[peripheral] = new Set();
    signalAliasTokens(state.af.signal || state.af.name || state.af.function_id).forEach((token) => {
      assigned[peripheral].add(token);
    });
  });
  return assigned;
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

function assignedPinsByPeripheral() {
  const assigned = {};
  Object.entries(pinStates || {}).forEach(([pinNum, state]) => {
    const af = state?.af;
    if (!af?.peripheral) return;
    if (!assigned[af.peripheral]) assigned[af.peripheral] = {};
    const tokens = signalAliasTokens(af.signal || af.name || af.function_id);
    tokens.forEach((token) => {
      if (!token) return;
      if (!(token in assigned[af.peripheral])) {
        assigned[af.peripheral][token] = Number(pinNum);
      }
    });
  });
  return assigned;
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
      renderConfigPanel();
    });
  });
}

function collectOutputViews() {
  const views = [
    { id: "overlay", label: ".overlay", content: generatedOverlay },
    { id: "conf", label: "prj.conf", content: generatedConf },
  ];

  if (collectGeneratedFileEntries().length) {
    views.push({ id: "files", label: "Files", content: "" });
  }

  return views.filter(view => view.id === "files" || view.content);
}

function collectGeneratedFileEntries() {
  const files = [
    { id: "generated:.overlay", label: ".overlay", path: ".overlay", content: generatedOverlay },
    { id: "generated:prj.conf", label: "prj.conf", path: "prj.conf", content: generatedConf },
  ];

  const optionalFragments = [
    [generatedFragments.protocols?.code, "protocols/protocol_stack.c"],
    [generatedFragments.protocols?.header, "protocols/protocol_stack.h"],
    [generatedFragments.protocols?.integration, "protocols/protocol_stack_integration.md"],
    [generatedFragments.lvgl?.code, "lvgl/ui_layout.c"],
    [generatedFragments.lvgl?.header, "lvgl/ui_layout.h"],
    [generatedFragments.lvgl?.hooksHeader, "lvgl/ui_layout_hooks.h"],
    [generatedFragments.lvgl?.hooks, "lvgl/ui_layout_hooks.template.c"],
    [generatedFragments.lvgl?.integration, "lvgl/ui_layout_integration.md"],
    [generatedFragments.lvgl?.validation, "lvgl/ui_layout_validation.md"],
    [generatedFragments.lvgl?.styleSchema, "lvgl/style_schema.json"],
  ];

  optionalFragments.forEach(([content, path]) => {
    if (!content) return;
    files.push({
      id: `generated:${path}`,
      label: path,
      path,
      content,
    });
  });

  for (const target of ["arduino", "baremetal"]) {
    const targetFiles = generatedTargets[target] || {};
    Object.keys(targetFiles).sort().forEach((filename) => {
      files.push({
        id: `generated:${target}/${filename}`,
        label: `${target}/${filename}`,
        path: `${target}/${filename}`,
        content: targetFiles[filename],
      });
    });
  }

  return files.filter((file) => file.content);
}

function detectGeneratedFileLanguage(path) {
  const lowerPath = String(path || "").toLowerCase();
  if (lowerPath.endsWith(".c") || lowerPath.endsWith(".h")) return "c";
  if (lowerPath.endsWith(".md")) return "markdown";
  if (lowerPath.endsWith(".json")) return "json";
  if (lowerPath.endsWith(".yaml") || lowerPath.endsWith(".yml")) return "yaml";
  if (lowerPath.endsWith(".conf") || lowerPath.endsWith("prj.conf")) return "ini";
  if (lowerPath.endsWith(".kicad_mod")) return "kicad footprint";
  if (lowerPath.endsWith(".wrl")) return "vrml";
  if (lowerPath.endsWith(".overlay") || lowerPath.endsWith(".dts") || lowerPath.endsWith(".dtsi")) return "plaintext";
  return "plaintext";
}

function generatedFileGroupLabel(path) {
  const normalized = String(path || "");
  if (normalized === ".overlay" || normalized === "prj.conf") return "Zephyr";
  if (normalized.startsWith("protocols/")) return "Protocol Editor";
  if (normalized.startsWith("lvgl/")) return "LVGL Layout";
  if (normalized.startsWith("arduino/")) return "Arduino";
  if (normalized.startsWith("baremetal/")) return "Bare Metal";
  return "Generated";
}

const codeReviewPanels = new Map();
let codeReviewPreviewStylesInstalled = false;

function ensureCodeReviewPreviewStyles() {
  if (codeReviewPreviewStylesInstalled) return;
  const style = document.createElement("style");
  style.textContent = `
    .output-files-preview {
      display: none;
      margin: 10px 0 0;
      border: 1px solid var(--border);
      border-radius: 10px;
      background: linear-gradient(180deg, rgba(255,255,255,0.03), rgba(0,0,0,0.06));
      overflow: hidden;
    }
    .output-files-preview.active {
      display: block;
    }
    .output-files-preview-header {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 10px;
      padding: 10px 12px;
      border-bottom: 1px solid var(--border);
      font-size: 11px;
      color: var(--fg-dim);
    }
    .output-files-preview-title {
      font-weight: 700;
      color: var(--fg);
    }
    .output-files-preview-meta {
      font-family: Consolas, monospace;
    }
    .output-files-preview-stage {
      display: grid;
      place-items: center;
      min-height: 220px;
      padding: 14px;
      background:
        linear-gradient(180deg, rgba(255,255,255,0.02), rgba(0,0,0,0.04)),
        linear-gradient(90deg, rgba(255,255,255,0.025) 1px, transparent 1px),
        linear-gradient(rgba(255,255,255,0.025) 1px, transparent 1px);
      background-size: auto, 20px 20px, 20px 20px;
      background-position: 0 0, center center, center center;
    }
    .output-files-preview-stage svg {
      width: min(100%, 440px);
      height: auto;
      max-height: 320px;
    }
    .output-files-preview-stage canvas {
      width: min(100%, 440px);
      height: auto;
      max-height: 320px;
      touch-action: none;
      cursor: grab;
    }
    .output-files-preview-stage canvas.is-dragging {
      cursor: grabbing;
    }
    .output-files-preview-note {
      padding: 0 12px 12px;
      font-size: 11px;
      line-height: 1.5;
      color: var(--fg-dim);
    }
    .output-files-preview-pins {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));
      gap: 6px;
      padding: 0 12px 12px;
    }
    .output-files-preview-pin {
      display: flex;
      align-items: center;
      gap: 8px;
      padding: 6px 8px;
      border: 1px solid rgba(148,163,184,0.18);
      border-radius: 8px;
      background: rgba(15,23,42,0.35);
      font-size: 11px;
      line-height: 1.4;
    }
    .output-files-preview-pin-num {
      min-width: 20px;
      font-family: Consolas, monospace;
      color: var(--fg-dim);
    }
    .output-files-preview-pin-name {
      color: var(--fg);
    }
  `;
  document.head.appendChild(style);
  codeReviewPreviewStylesInstalled = true;
  window.__codeReviewPreviewInstalled = true;
}

function codeReviewPreviewKind(path) {
  const lower = String(path || "").toLowerCase();
  if (lower.endsWith(".kicad_mod")) return "footprint";
  if (lower.endsWith(".wrl")) return "model";
  return "";
}

function parseFootprintPreview(content) {
  const lines = String(content || "").split(/\r?\n/);
  const pads = [];
  const segments = [];
  const circles = [];
  for (const line of lines) {
    const trimmed = line.trim();
    if (trimmed.startsWith("(pad ")) {
      const padMatch = trimmed.match(/^\(pad\s+"?([^"\s)]+)"?\s+\S+\s+(\S+)\s+\(at\s+([-\d.]+)\s+([-\d.]+)/);
      const sizeMatch = trimmed.match(/\(size\s+([-\d.]+)\s+([-\d.]+)\)/);
      const functionMatch = trimmed.match(/\(pinfunction\s+"([^"]+)"\)/);
      if (padMatch && sizeMatch) {
        pads.push({
          name: padMatch[1],
          label: functionMatch ? functionMatch[1] : padMatch[1],
          shape: padMatch[2],
          x: Number(padMatch[3]),
          y: Number(padMatch[4]),
          w: Number(sizeMatch[1]),
          h: Number(sizeMatch[2]),
        });
      }
      continue;
    }
    if (trimmed.startsWith("(fp_line ")) {
      const lineMatch = trimmed.match(/\(start\s+([-\d.]+)\s+([-\d.]+)\)\s+\(end\s+([-\d.]+)\s+([-\d.]+)\)/);
      if (lineMatch) {
        segments.push({
          x1: Number(lineMatch[1]),
          y1: Number(lineMatch[2]),
          x2: Number(lineMatch[3]),
          y2: Number(lineMatch[4]),
        });
      }
      continue;
    }
    if (trimmed.startsWith("(fp_circle ")) {
      const circleMatch = trimmed.match(/\(center\s+([-\d.]+)\s+([-\d.]+)\)\s+\(end\s+([-\d.]+)\s+([-\d.]+)\)/);
      if (circleMatch) {
        const cx = Number(circleMatch[1]);
        const cy = Number(circleMatch[2]);
        circles.push({
          cx,
          cy,
          r: Math.hypot(Number(circleMatch[3]) - cx, Number(circleMatch[4]) - cy),
        });
      }
    }
  }
  return { pads, segments, circles };
}

function boxPreviewFaces(center, size, palette) {
  const hx = size.x / 2;
  const hy = size.y / 2;
  const hz = size.z / 2;
  const points = {
    nnn: { x: center.x - hx, y: center.y - hy, z: center.z - hz },
    nnp: { x: center.x - hx, y: center.y - hy, z: center.z + hz },
    npn: { x: center.x - hx, y: center.y + hy, z: center.z - hz },
    npp: { x: center.x - hx, y: center.y + hy, z: center.z + hz },
    pnn: { x: center.x + hx, y: center.y - hy, z: center.z - hz },
    pnp: { x: center.x + hx, y: center.y - hy, z: center.z + hz },
    ppn: { x: center.x + hx, y: center.y + hy, z: center.z - hz },
    ppp: { x: center.x + hx, y: center.y + hy, z: center.z + hz },
  };
  return [
    { fill: palette.top, stroke: palette.stroke, points: [points.nnp, points.pnp, points.ppp, points.npp] },
    { fill: palette.left, stroke: palette.stroke, points: [points.nnn, points.nnp, points.npp, points.npn] },
    { fill: palette.right, stroke: palette.stroke, points: [points.pnn, points.pnp, points.ppp, points.ppn] },
    { fill: palette.front, stroke: palette.stroke, points: [points.npn, points.npp, points.ppp, points.ppn] },
    { fill: palette.back, stroke: palette.stroke, points: [points.nnn, points.nnp, points.pnp, points.pnn] },
    { fill: palette.bottom, stroke: palette.stroke, points: [points.nnn, points.pnn, points.ppn, points.npn] },
  ];
}

function buildFootprintPreviewScene(content) {
  const parsed = parseFootprintPreview(content);
  const extents = [];
  parsed.pads.forEach((pad) => {
    extents.push([pad.x - pad.w / 2, pad.y - pad.h / 2], [pad.x + pad.w / 2, pad.y + pad.h / 2]);
  });
  parsed.segments.forEach((seg) => extents.push([seg.x1, seg.y1], [seg.x2, seg.y2]));
  parsed.circles.forEach((circle) => extents.push([circle.cx - circle.r, circle.cy - circle.r], [circle.cx + circle.r, circle.cy + circle.r]));

  if (!extents.length) {
    return null;
  }

  const minX = Math.min(...extents.map((item) => item[0])) - 1.5;
  const minY = Math.min(...extents.map((item) => item[1])) - 1.5;
  const maxX = Math.max(...extents.map((item) => item[0])) + 1.5;
  const maxY = Math.max(...extents.map((item) => item[1])) + 1.5;
  const width = Math.max(1, maxX - minX);
  const height = Math.max(1, maxY - minY);
  const center = { x: (minX + maxX) / 2, y: (minY + maxY) / 2 };
  const boardThickness = Math.max(0.16, Math.min(width, height) * 0.04);
  const padHeight = Math.max(0.06, boardThickness * 0.4);
  const faces = [
    ...boxPreviewFaces({ x: center.x, y: center.y, z: 0 }, { x: width, y: height, z: boardThickness }, {
      top: "#0f766e",
      left: "#115e59",
      right: "#134e4a",
      front: "#0d9488",
      back: "#134e4a",
      bottom: "#0b3b38",
      stroke: "rgba(226,232,240,0.22)",
    }),
  ];
  parsed.pads.forEach((pad) => {
    faces.push(...boxPreviewFaces({ x: pad.x, y: pad.y, z: boardThickness / 2 + padHeight / 2 }, {
      x: pad.w,
      y: pad.h,
      z: padHeight,
    }, {
      top: "#f59e0b",
      left: "#b45309",
      right: "#d97706",
      front: "#fbbf24",
      back: "#b45309",
      bottom: "#78350f",
      stroke: "rgba(17,24,39,0.28)",
    }));
  });
  const overlays = [
    ...parsed.segments.map((seg) => ({ kind: "line", color: "#e2e8f0", width: 1.3, points: [
      { x: seg.x1, y: seg.y1, z: boardThickness / 2 + 0.03 },
      { x: seg.x2, y: seg.y2, z: boardThickness / 2 + 0.03 },
    ] })),
    ...parsed.circles.map((circle) => ({ kind: "circle", color: "#38bdf8", width: 1.2, center: { x: circle.cx, y: circle.cy, z: boardThickness / 2 + 0.03 }, radius: circle.r })),
    ...parsed.pads.filter((pad) => pad.label).map((pad) => ({
      kind: "label",
      text: pad.label,
      color: "#f8fafc",
      point: { x: pad.x, y: pad.y, z: boardThickness / 2 + padHeight + 0.06 },
    })),
  ];
  const legendItems = parsed.pads
    .filter((pad) => pad.label && pad.label !== pad.name)
    .map((pad) => ({ number: pad.name, label: pad.label }));
  return {
    type: "interactive",
    title: "Footprint Preview",
    meta: `${parsed.pads.length} pad(s)`,
    note: "Drag to orbit, scroll to zoom. The footprint is rendered as a low-profile 3D board with pads and silkscreen.",
    view: { yaw: -0.72, pitch: 0.92, zoom: 1.08 },
    extent: Math.max(width, height, boardThickness + padHeight),
    faces,
    overlays,
    legendItems,
  };
}

function renderFootprintPreview(content) {
  const scene = buildFootprintPreviewScene(content);
  if (!scene) {
    return {
      title: "Footprint Preview",
      meta: "No drawable geometry found",
      note: "The footprint source is present, but the preview renderer could not detect pads or silkscreen primitives.",
      svg: `<svg viewBox="0 0 420 240" xmlns="http://www.w3.org/2000/svg"><text x="210" y="120" fill="currentColor" text-anchor="middle" font-family="Consolas, monospace" font-size="14">No footprint geometry parsed</text></svg>`,
    };
  }
  return scene;
}

function renderModelPreview(content) {
  const match = String(content || "").match(/Box\s*\{\s*size\s+([-\d.eE+]+)\s+([-\d.eE+]+)\s+([-\d.eE+]+)\s*\}/);
  const sizeX = match ? Number(match[1]) * 1000 : 5;
  const sizeY = match ? Number(match[2]) * 1000 : 5;
  const sizeZ = match ? Number(match[3]) * 1000 : 1;
  return {
    type: "interactive",
    title: "3D Model Preview",
    meta: `${sizeX.toFixed(2)} x ${sizeY.toFixed(2)} x ${sizeZ.toFixed(2)} mm`,
    note: "Drag to orbit, scroll to zoom. The WRL preview uses the VRML Box geometry exported for the KiCad 3D component.",
    view: { yaw: -0.68, pitch: 0.78, zoom: 1.05 },
    extent: Math.max(sizeX, sizeY, sizeZ),
    faces: boxPreviewFaces({ x: 0, y: 0, z: 0 }, { x: sizeX, y: sizeY, z: sizeZ }, {
      top: "#94a3b8",
      left: "#475569",
      right: "#64748b",
      front: "#1e293b",
      back: "#334155",
      bottom: "#0f172a",
      stroke: "rgba(248,250,252,0.24)",
    }),
    overlays: [],
  };
}

function buildCodeReviewPreview(file) {
  const kind = codeReviewPreviewKind(file?.path);
  if (kind === "footprint") return renderFootprintPreview(file?.content || "");
  if (kind === "model") return renderModelPreview(file?.content || "");
  return null;
}

function rotatePreviewPoint(point, yaw, pitch) {
  const cosY = Math.cos(yaw);
  const sinY = Math.sin(yaw);
  const cosP = Math.cos(pitch);
  const sinP = Math.sin(pitch);
  const x1 = point.x * cosY - point.z * sinY;
  const z1 = point.x * sinY + point.z * cosY;
  const y2 = point.y * cosP - z1 * sinP;
  const z2 = point.y * sinP + z1 * cosP;
  return { x: x1, y: y2, z: z2 };
}

function projectPreviewPoint(point, view, canvas) {
  const rotated = rotatePreviewPoint(point, view.yaw, view.pitch);
  const distance = Math.max(view.extent * 3.2, 6);
  const perspective = distance / Math.max(distance * 0.35, rotated.z + distance);
  const scale = (Math.min(canvas.width, canvas.height) / Math.max(view.extent * 2.7, 8)) * view.zoom;
  return {
    x: canvas.width / 2 + view.panX + rotated.x * scale * perspective,
    y: canvas.height / 2 + view.panY - rotated.y * scale * perspective,
    z: rotated.z,
  };
}

function drawInteractiveCodeReviewPreview(stage, preview, cacheKey) {
  let canvas = stage.querySelector("canvas");
  if (!canvas) {
    canvas = document.createElement("canvas");
    canvas.width = 440;
    canvas.height = 300;
    canvas.setAttribute("aria-label", `${preview.title} interactive preview`);
    stage.appendChild(canvas);
  }
  const ctx = canvas.getContext("2d");
  const store = stage.__previewStore || (stage.__previewStore = { views: {} });
  const view = store.views[cacheKey] || {
    yaw: preview.view?.yaw ?? -0.68,
    pitch: preview.view?.pitch ?? 0.8,
    zoom: preview.view?.zoom ?? 1,
    panX: 0,
    panY: 0,
    extent: preview.extent || 8,
  };
  store.views[cacheKey] = view;

  function renderScene() {
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    ctx.fillStyle = "rgba(11,18,32,0.55)";
    ctx.beginPath();
    ctx.ellipse(canvas.width / 2, canvas.height * 0.78, canvas.width * 0.28, canvas.height * 0.08, 0, 0, Math.PI * 2);
    ctx.fill();

    const faces = (preview.faces || []).map((face) => ({
      face,
      projected: face.points.map((point) => projectPreviewPoint(point, view, canvas)),
      depth: face.points.reduce((sum, point) => sum + rotatePreviewPoint(point, view.yaw, view.pitch).z, 0) / Math.max(face.points.length, 1),
    })).sort((left, right) => left.depth - right.depth);

    faces.forEach(({ face, projected }) => {
      ctx.beginPath();
      projected.forEach((point, index) => {
        if (index === 0) ctx.moveTo(point.x, point.y);
        else ctx.lineTo(point.x, point.y);
      });
      ctx.closePath();
      ctx.fillStyle = face.fill;
      ctx.strokeStyle = face.stroke || "rgba(255,255,255,0.15)";
      ctx.lineWidth = 1;
      ctx.fill();
      ctx.stroke();
    });

    (preview.overlays || []).forEach((overlay) => {
      ctx.strokeStyle = overlay.color || "#e2e8f0";
      ctx.lineWidth = overlay.width || 1.2;
      if (overlay.kind === "line") {
        const p0 = projectPreviewPoint(overlay.points[0], view, canvas);
        const p1 = projectPreviewPoint(overlay.points[1], view, canvas);
        ctx.beginPath();
        ctx.moveTo(p0.x, p0.y);
        ctx.lineTo(p1.x, p1.y);
        ctx.stroke();
      } else if (overlay.kind === "circle") {
        const samples = [];
        for (let index = 0; index <= 24; index += 1) {
          const angle = (index / 24) * Math.PI * 2;
          samples.push(projectPreviewPoint({
            x: overlay.center.x + Math.cos(angle) * overlay.radius,
            y: overlay.center.y + Math.sin(angle) * overlay.radius,
            z: overlay.center.z,
          }, view, canvas));
        }
        ctx.beginPath();
        samples.forEach((point, index) => {
          if (index === 0) ctx.moveTo(point.x, point.y);
          else ctx.lineTo(point.x, point.y);
        });
        ctx.stroke();
      } else if (overlay.kind === "label") {
        const point = projectPreviewPoint(overlay.point, view, canvas);
        ctx.font = "11px 'Segoe UI', sans-serif";
        ctx.textAlign = "center";
        ctx.textBaseline = "bottom";
        ctx.fillStyle = "rgba(2,6,23,0.72)";
        const width = Math.max(26, ctx.measureText(overlay.text).width + 8);
        ctx.fillRect(point.x - width / 2, point.y - 16, width, 14);
        ctx.fillStyle = overlay.color || "#f8fafc";
        ctx.fillText(overlay.text, point.x, point.y - 4);
      }
    });
  }

  if (canvas.dataset.previewBound !== "true") {
    let dragging = false;
    let lastX = 0;
    let lastY = 0;
    canvas.addEventListener("pointerdown", (event) => {
      dragging = true;
      lastX = event.clientX;
      lastY = event.clientY;
      canvas.classList.add("is-dragging");
      canvas.setPointerCapture(event.pointerId);
    });
    canvas.addEventListener("pointermove", (event) => {
      if (!dragging) return;
      const dx = event.clientX - lastX;
      const dy = event.clientY - lastY;
      lastX = event.clientX;
      lastY = event.clientY;
      view.yaw += dx * 0.012;
      view.pitch = Math.max(-1.35, Math.min(1.35, view.pitch + dy * 0.012));
      renderScene();
    });
    const stopDragging = (event) => {
      dragging = false;
      canvas.classList.remove("is-dragging");
      if (event?.pointerId !== undefined) {
        try {
          canvas.releasePointerCapture(event.pointerId);
        } catch (_err) {
        }
      }
    };
    canvas.addEventListener("pointerup", stopDragging);
    canvas.addEventListener("pointercancel", stopDragging);
    canvas.addEventListener("wheel", (event) => {
      event.preventDefault();
      view.zoom = Math.max(0.45, Math.min(2.4, view.zoom * (event.deltaY > 0 ? 0.92 : 1.08)));
      renderScene();
    }, { passive: false });
    canvas.dataset.previewBound = "true";
  }

  renderScene();
}

function renderCodeReviewPreview(state, file) {
  if (!state?.preview) return;
  const preview = buildCodeReviewPreview(file);
  if (!preview) {
    state.preview.classList.remove("active");
    state.preview.innerHTML = "";
    return;
  }
  state.preview.classList.add("active");
  state.preview.innerHTML = `
    <div class="output-files-preview-header">
      <div class="output-files-preview-title">${escapeHtml(preview.title)}</div>
      <div class="output-files-preview-meta">${escapeHtml(preview.meta || "")}</div>
    </div>
    <div class="output-files-preview-stage">${preview.svg || ""}</div>
    <div class="output-files-preview-note">${escapeHtml(preview.note || "")}</div>
    ${Array.isArray(preview.legendItems) && preview.legendItems.length ? `<div class="output-files-preview-pins">${preview.legendItems.map((item) => `<div class="output-files-preview-pin"><span class="output-files-preview-pin-num">${escapeHtml(item.number)}</span><span class="output-files-preview-pin-name">${escapeHtml(item.label)}</span></div>`).join("")}</div>` : ""}
  `;
  if (preview.type === "interactive") {
    const stage = state.preview.querySelector(".output-files-preview-stage");
    drawInteractiveCodeReviewPreview(stage, preview, file?.id || file?.path || preview.title);
  }
}

function codeReviewPanelMarkup(panelId, emptyMessage = "No generated files yet.") {
  return `
    <div class="reviewable-generated-code" data-code-review-panel="${escapeHtmlAttr(panelId)}">
      <div class="output-files-view">
        <div class="output-files-sidebar">
          <input class="output-files-search" data-code-review-search type="search" placeholder="Filter generated files">
          <div data-code-review-list></div>
        </div>
        <div class="output-files-editor-shell">
          <div class="output-files-current-path">
            <div class="output-files-current-path-text" data-code-review-path>No file selected</div>
            <div class="output-files-current-actions">
              <button class="output-files-action" data-code-review-copy type="button">Copy</button>
              <button class="output-files-action" data-code-review-download type="button">Download</button>
            </div>
          </div>
          <pre class="output-files-fallback" data-code-review-fallback>${escapeHtml(emptyMessage)}</pre>
        </div>
      </div>
    </div>`;
}

function normalizeCodeReviewFiles(files) {
  return (Array.isArray(files) ? files : []).map((file, index) => ({
    id: String(file?.id || `file_${index + 1}`),
    label: String(file?.label || file?.path || `file_${index + 1}`),
    path: String(file?.path || file?.label || `file_${index + 1}`),
    group: String(file?.group || generatedFileGroupLabel(file?.path || file?.label || "")),
    content: String(file?.content || ""),
  })).filter((file) => file.content);
}

function ensureCodeReviewPanel(panelId) {
  const root = document.querySelector(`[data-code-review-panel="${panelId}"]`);
  if (!root) return null;
  ensureCodeReviewPreviewStyles();

  let state = codeReviewPanels.get(panelId);
  if (!state) {
    state = {
      id: panelId,
      filter: "",
      selection: "",
      files: [],
      emptyMessage: "No generated files yet.",
      onSelect: null,
    };
    codeReviewPanels.set(panelId, state);
  }

  state.root = root;
  state.searchInput = root.querySelector("[data-code-review-search]");
  state.list = root.querySelector("[data-code-review-list]");
  state.path = root.querySelector("[data-code-review-path]");
  state.copyBtn = root.querySelector("[data-code-review-copy]");
  state.downloadBtn = root.querySelector("[data-code-review-download]");
  state.fallback = root.querySelector("[data-code-review-fallback]");
  state.preview = root.querySelector("[data-code-review-preview]");

  if (!state.preview && state.fallback?.parentNode) {
    state.preview = document.createElement("div");
    state.preview.className = "output-files-preview";
    state.preview.setAttribute("data-code-review-preview", "true");
    state.fallback.parentNode.insertBefore(state.preview, state.fallback);
  }

  if (root.dataset.codeReviewBound !== "true") {
    state.searchInput?.addEventListener("input", () => {
      state.filter = String(state.searchInput?.value || "").trim().toLowerCase();
      drawCodeReviewPanel(state);
    });
    state.copyBtn?.addEventListener("click", async () => {
      const selected = selectedCodeReviewFile(state);
      if (!selected) return;
      try {
        await navigator.clipboard.writeText(selected.content);
        toast(`Copied ${selected.label}`);
      } catch (err) {
        toast(`Copy failed: ${err.message}`);
      }
    });
    state.downloadBtn?.addEventListener("click", () => {
      const selected = selectedCodeReviewFile(state);
      if (!selected) return;
      const blob = new Blob([selected.content], { type: "text/plain;charset=utf-8" });
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = selected.path.split("/").pop() || selected.label;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      URL.revokeObjectURL(url);
    });
    root.dataset.codeReviewBound = "true";
  }

  return state;
}

function matchesCodeReviewFileFilter(file, filterText) {
  if (!filterText) return true;
  const haystack = [file.label, file.path, file.group, detectGeneratedFileLanguage(file.path)]
    .join(" ")
    .toLowerCase();
  return haystack.includes(filterText);
}

function selectedCodeReviewFile(state) {
  const visible = state.files.filter((file) => matchesCodeReviewFileFilter(file, state.filter));
  return visible.find((file) => file.id === state.selection) || visible[0] || null;
}

function setCodeReviewSelection(state, fileId) {
  state.selection = String(fileId || "");
  const selected = selectedCodeReviewFile(state);
  if (selected && typeof state.onSelect === "function") {
    state.onSelect(selected);
  }
  drawCodeReviewPanel(state);
}

function drawCodeReviewPanel(state) {
  if (!state?.list || !state?.fallback || !state?.path) return;
  if (state.searchInput && state.searchInput.value !== state.filter) {
    state.searchInput.value = state.filter;
  }

  const files = state.files.filter((file) => matchesCodeReviewFileFilter(file, state.filter));
  state.list.innerHTML = "";

  if (!state.files.length) {
    state.path.textContent = "No generated files yet";
    state.fallback.textContent = state.emptyMessage;
    renderCodeReviewPreview(state, null);
    return;
  }

  if (!files.length) {
    state.path.textContent = `${state.files.length} generated file(s)`;
    state.fallback.textContent = `No generated files match "${state.filter}".`;
    renderCodeReviewPreview(state, null);
    return;
  }

  if (!files.some((file) => file.id === state.selection)) {
    state.selection = files[0].id;
  }

  let currentGroup = "";
  files.forEach((file) => {
    if (file.group !== currentGroup) {
      currentGroup = file.group;
      const heading = document.createElement("div");
      heading.className = "generated-file-group";
      heading.textContent = currentGroup;
      state.list.appendChild(heading);
    }

    const item = document.createElement("button");
    item.type = "button";
    item.className = "generated-file-item" + (file.id === state.selection ? " active" : "");
    item.dataset.fileId = file.id;
    item.innerHTML = `
      <span class="generated-file-name">${escapeHtml(file.label)}</span>
      <span class="generated-file-meta">${escapeHtml(detectGeneratedFileLanguage(file.path))}</span>
    `;
    item.addEventListener("click", () => setCodeReviewSelection(state, file.id));
    state.list.appendChild(item);
  });

  const selected = selectedCodeReviewFile(state);
  state.path.textContent = selected ? `${selected.path} | ${detectGeneratedFileLanguage(selected.path)}` : "No file selected";
  state.fallback.textContent = selected?.content || state.emptyMessage;
  renderCodeReviewPreview(state, selected);
}

function renderCodeReviewPanel(panelId, files, options = {}) {
  const state = ensureCodeReviewPanel(panelId);
  if (!state) return;
  state.files = normalizeCodeReviewFiles(files);
  state.emptyMessage = String(options.emptyMessage || state.emptyMessage || "No generated files yet.");
  state.onSelect = typeof options.onSelect === "function" ? options.onSelect : null;
  if (options.resetFilter) {
    state.filter = "";
  }
  if (options.preferredSelection && state.files.some((file) => file.id === options.preferredSelection)) {
    state.selection = options.preferredSelection;
  }
  drawCodeReviewPanel(state);
}

window.codeReviewPanelMarkup = codeReviewPanelMarkup;
window.renderCodeReviewPanel = renderCodeReviewPanel;

function matchesGeneratedFileFilter(file, filterText) {
  if (!filterText) return true;
  const haystack = [file.label, file.path, detectGeneratedFileLanguage(file.path), generatedFileGroupLabel(file.path)]
    .join(" ")
    .toLowerCase();
  return haystack.includes(filterText);
}

function escapeHtmlAttr(value) {
  return String(value || "")
    .replace(/&/g, "&amp;")
    .replace(/"/g, "&quot;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}

function ensureMonacoLoader() {
  if (window.monaco?.editor) return Promise.resolve(window.monaco);
  if (monacoLoadPromise) return monacoLoadPromise;

  const baseUrl = "https://cdnjs.cloudflare.com/ajax/libs/monaco-editor/0.52.2/min/";
  monacoLoadPromise = new Promise((resolve, reject) => {
    const loadMonaco = () => {
      if (!window.require?.config) {
        reject(new Error("Monaco loader unavailable"));
        return;
      }
      window.MonacoEnvironment = {
        getWorkerUrl() {
          const workerSource = [
            `self.MonacoEnvironment = { baseUrl: '${baseUrl}' };`,
            `importScripts('${baseUrl}vs/base/worker/workerMain.js');`,
          ].join("\n");
          return `data:text/javascript;charset=utf-8,${encodeURIComponent(workerSource)}`;
        },
      };
      window.require.config({ paths: { vs: `${baseUrl}vs` } });
      window.require(["vs/editor/editor.main"], () => resolve(window.monaco), reject);
    };

    if (window.require?.config) {
      loadMonaco();
      return;
    }

    let loaderScript = document.querySelector('script[data-monaco-loader="true"]');
    if (!loaderScript) {
      loaderScript = document.createElement("script");
      loaderScript.src = `${baseUrl}vs/loader.min.js`;
      loaderScript.async = true;
      loaderScript.dataset.monacoLoader = "true";
      document.head.appendChild(loaderScript);
    }

    loaderScript.addEventListener("load", loadMonaco, { once: true });
    loaderScript.addEventListener("error", () => reject(new Error("Failed to load Monaco editor assets")), { once: true });
  }).catch((error) => {
    monacoLoadPromise = null;
    throw error;
  });

  return monacoLoadPromise;
}

function ensureGeneratedFilesEditor() {
  if (generatedFilesEditor || generatedFilesEditorFailed || !outputFilesEditorHost) return Promise.resolve(generatedFilesEditor);
  return ensureMonacoLoader().then((monaco) => {
    if (generatedFilesEditor) return generatedFilesEditor;
    generatedFilesEditor = monaco.editor.create(outputFilesEditorHost, {
      value: "",
      language: "plaintext",
      theme: "vs-dark",
      readOnly: true,
      automaticLayout: true,
      minimap: { enabled: false },
      scrollBeyondLastLine: false,
      renderLineHighlight: "none",
      wordWrap: "off",
      tabSize: 2,
    });
    return generatedFilesEditor;
  }).catch((error) => {
    generatedFilesEditorFailed = true;
    if (outputFilesFallback) {
      outputFilesFallback.hidden = false;
      outputFilesFallback.textContent = `Monaco editor unavailable. ${error.message}`;
    }
    return null;
  });
}

function setGeneratedFilesOverviewSelection(fileId) {
  const files = collectGeneratedFileEntries();
  const current = files.find((file) => file.id === fileId) || files[0] || null;
  generatedFilesOverviewSelection = current?.id || "";

  if (outputFilesList) {
    outputFilesList.querySelectorAll(".generated-file-item").forEach((item) => {
      item.classList.toggle("active", item.dataset.fileId === generatedFilesOverviewSelection);
    });
  }

  if (!current) {
    if (outputFilesFallback) outputFilesFallback.textContent = "No generated files yet.";
    if (outputFilesCurrentPath) outputFilesCurrentPath.textContent = "No file selected";
    return;
  }

  if (outputFilesCurrentPath) {
    outputFilesCurrentPath.textContent = `${current.path} | ${detectGeneratedFileLanguage(current.path)}`;
  }
  if (outputFilesFallback) outputFilesFallback.textContent = current.content || "";
  if (!generatedFilesEditor || !window.monaco?.editor) return;

  let model = generatedFilesModels.get(current.id);
  if (!model) {
    model = window.monaco.editor.createModel(
      current.content,
      detectGeneratedFileLanguage(current.path),
      window.monaco.Uri.parse(`inmemory://generated/${encodeURIComponent(current.path)}`)
    );
    generatedFilesModels.set(current.id, model);
  } else if (model.getValue() !== current.content) {
    model.setValue(current.content);
  }
  window.monaco.editor.setModelLanguage(model, detectGeneratedFileLanguage(current.path));
  generatedFilesEditor.setModel(model);
  generatedFilesEditor.setScrollPosition({ scrollTop: 0, scrollLeft: 0 });
}

function selectedGeneratedFileEntry() {
  const files = collectGeneratedFileEntries();
  return files.find((file) => file.id === generatedFilesOverviewSelection) || files[0] || null;
}

function renderGeneratedFilesOverview() {
  if (!outputFilesView || !outputFilesList || !outputFilesFallback) return;
  const allFiles = collectGeneratedFileEntries();
  const filterText = generatedFilesFilter.trim().toLowerCase();
  const files = allFiles.filter((file) => matchesGeneratedFileFilter(file, filterText));
  outputFilesList.innerHTML = "";

  if (outputFilesSearch && outputFilesSearch.value !== generatedFilesFilter) {
    outputFilesSearch.value = generatedFilesFilter;
  }

  if (!allFiles.length) {
    outputFilesFallback.hidden = false;
    outputFilesFallback.textContent = 'Click "Generate" to populate the generated files overview.';
    if (outputFilesEditorHost) outputFilesEditorHost.hidden = true;
    if (outputFilesCurrentPath) outputFilesCurrentPath.textContent = "No generated files yet";
    return;
  }

  if (!files.length) {
    outputFilesFallback.hidden = false;
    outputFilesFallback.textContent = `No generated files match "${generatedFilesFilter}".`;
    if (outputFilesEditorHost) outputFilesEditorHost.hidden = true;
    if (outputFilesCurrentPath) outputFilesCurrentPath.textContent = `${allFiles.length} generated file(s)`;
    return;
  }

  if (!files.some((file) => file.id === generatedFilesOverviewSelection)) {
    generatedFilesOverviewSelection = files[0].id;
  }

  let currentGroup = "";
  files.forEach((file) => {
    const group = generatedFileGroupLabel(file.path);
    if (group !== currentGroup) {
      currentGroup = group;
      const heading = document.createElement("div");
      heading.className = "generated-file-group";
      heading.textContent = group;
      outputFilesList.appendChild(heading);
    }

    const item = document.createElement("button");
    item.type = "button";
    item.className = "generated-file-item" + (file.id === generatedFilesOverviewSelection ? " active" : "");
    item.dataset.fileId = file.id;
    item.title = file.path;
    item.innerHTML = `
      <span class="generated-file-name">${escapeHtml(file.label)}</span>
      <span class="generated-file-meta">${escapeHtml(detectGeneratedFileLanguage(file.path))}</span>
    `;
    item.addEventListener("click", () => setGeneratedFilesOverviewSelection(file.id));
    outputFilesList.appendChild(item);
  });

  outputFilesFallback.hidden = generatedFilesEditor && !generatedFilesEditorFailed;
  if (outputFilesEditorHost) outputFilesEditorHost.hidden = generatedFilesEditorFailed;

  ensureGeneratedFilesEditor().then(() => {
    if (outputFilesEditorHost) outputFilesEditorHost.hidden = !generatedFilesEditor;
    outputFilesFallback.hidden = !!generatedFilesEditor;
    setGeneratedFilesOverviewSelection(generatedFilesOverviewSelection);
  });

  if (!generatedFilesEditor) {
    outputFilesFallback.hidden = false;
    setGeneratedFilesOverviewSelection(generatedFilesOverviewSelection);
  }
}

function aggregateGeneratedText(sections, options = {}) {
  const {
    commentPrefix = "#",
    title = "Generated by Zephyr Pin Configurator",
  } = options;

  const nonEmpty = sections
    .map(section => ({
      title: section.title,
      content: String(section.content || "").trim(),
    }))
    .filter(section => section.content);

  if (!nonEmpty.length) return "";

  const lines = [
    `${commentPrefix} ${title}`,
    "",
  ];

  nonEmpty.forEach((section, index) => {
    lines.push(`${commentPrefix} -- ${section.title} ${"-".repeat(Math.max(1, 56 - section.title.length))}`);
    lines.push(section.content);
    if (index < nonEmpty.length - 1) {
      lines.push("");
    }
  });

  return lines.join("\n").trim();
}

function refreshGeneratedOutputs() {
  generatedOverlay = aggregateGeneratedText([
    { title: "Pin Configurator", content: generatedFragments.pin.overlay },
    { title: "Peripheral Configurator", content: generatedFragments.peripherals.overlay },
    { title: "Protocol Editor", content: generatedFragments.protocols.overlay },
    { title: "Clock Configurator", content: generatedFragments.clock.overlay },
  ], {
    title: "Aggregated Zephyr overlay",
  });

  generatedConf = aggregateGeneratedText([
    { title: "Pin Configurator", content: generatedFragments.pin.prj_conf },
    { title: "Module Configurator", content: generatedFragments.modules.prj_conf },
    { title: "Peripheral Configurator", content: generatedFragments.peripherals.prj_conf },
    { title: "Protocol Editor", content: generatedFragments.protocols.prj_conf },
    { title: "Clock Configurator", content: generatedFragments.clock.prj_conf },
    { title: "LVGL Layout Editor", content: generatedFragments.lvgl.prj_conf },
  ], {
    title: "Aggregated Zephyr project configuration",
  });

  renderOutputTabs();
  if (generatedOverlay || generatedConf) {
    showOutput(activeTab);
  }
}

function zephyrCatalogStorageRoot() {
  return localStorage.getItem("zpincfg_zephyr_catalog_root") || "";
}

function zephyrCatalogSaveRoot(root) {
  if (root) {
    localStorage.setItem("zpincfg_zephyr_catalog_root", root);
  }
}

function zephyrCatalogInferPart(item) {
  if (item.kind === "mcu") {
    return item.socs?.[0] || item.name;
  }
  const compatible = String(item.compatible || "");
  return compatible.includes(",") ? compatible.split(",", 2)[1].toUpperCase() : (item.name || item.label || compatible);
}

function zephyrCatalogResolveBoardId(item) {
  if (!item || item.kind !== "mcu") return "";
  const tokens = new Set([
    item.name,
    item.label,
    ...(item.socs || []),
  ].map((value) => normalizeSearchToken(value)).filter(Boolean));

  const exactBoard = availableBoards.find((board) => tokens.has(normalizeSearchToken(board.board)));
  if (exactBoard) return exactBoard.id;

  const exactId = availableBoards.find((board) => tokens.has(normalizeSearchToken(board.id)));
  if (exactId) return exactId.id;

  const exactSoc = availableBoards.find((board) => tokens.has(normalizeSearchToken(board.name)));
  if (exactSoc) return exactSoc.id;

  const loose = availableBoards.find((board) => {
    const searchFields = [board.id, board.board, board.name].map((value) => normalizeSearchToken(value));
    return [...tokens].some((token) => searchFields.some((field) => field && (field.includes(token) || token.includes(field))));
  });
  return loose?.id || "";
}

function zephyrCatalogBindingSummary(item) {
  const propNames = (item.properties || []).slice(0, 6).map((prop) => prop.name);
  const propSuffix = propNames.length ? ` Properties: ${propNames.join(", ")}.` : "";
  const pathSuffix = item.binding_paths?.length ? ` Binding: ${item.binding_paths[0]}.` : "";
  return `${item.description || `Imported from Zephyr binding ${item.compatible || item.name}.`}${propSuffix}${pathSuffix}`.trim();
}

function zephyrCatalogSensorDevice(item) {
  const compatible = String(item.compatible || item.name || "sensor");
  const busFamily = item.buses?.[0] || "i2c";
  return normalizeExternalDevice({
    id: `zephyr_${compatible.replace(/[^a-zA-Z0-9]+/g, "_").toLowerCase()}`,
    display: item.label || item.name || compatible,
    category: "sensor",
    bus_family: busFamily,
    bus: `${busFamily}0`,
    compatible,
    address: "",
    required_signals: boardEditorSignalsForBus(busFamily),
    frameworks: ["zephyr"],
    notes: zephyrCatalogBindingSummary(item),
  });
}

function zephyrCatalogDisplayDevice(item) {
  const compatible = String(item.compatible || item.name || "display");
  const busFamily = item.buses?.[0] || "spi";
  const resolution = item.display?.width && item.display?.height
    ? `${item.display.width}x${item.display.height}`
    : "";
  return normalizeExternalDevice({
    id: `zephyr_${compatible.replace(/[^a-zA-Z0-9]+/g, "_").toLowerCase()}`,
    display: item.label || item.name || compatible,
    category: "display",
    bus_family: busFamily,
    bus: `${busFamily}0`,
    compatible,
    required_signals: boardEditorSignalsForBus(busFamily),
    frameworks: ["zephyr"],
    notes: [zephyrCatalogBindingSummary(item), resolution ? `Resolution: ${resolution}.` : ""].filter(Boolean).join(" "),
  });
}

function zephyrCatalogMcuModuleDevice(item) {
  const socs = Array.isArray(item.socs) && item.socs.length ? item.socs : [item.name || item.label || "MCU"];
  return normalizeBoardEditorDevice({
    id: `zephyr_${slugifyBoardEditorToken(item.name || item.label || socs[0])}`,
    display: item.label || item.name || socs[0],
    category: "mcu",
    compatible: item.name || socs[0],
    notes: [`Imported from Zephyr board catalog ${item.board_path || item.directory || item.name}.`, socs.length > 1 ? `SoCs: ${socs.join(", ")}.` : ""].filter(Boolean).join(" "),
    required_signals: ["VCC", "GND", "RESET", "UART_TX", "UART_RX"],
    pins: ["VCC", "GND", "RESET", "UART_TX", "UART_RX"],
  }, 0);
}

function zephyrCatalogBoardLibraryEntry(item) {
  const device = item.kind === "display"
    ? zephyrCatalogDisplayDevice(item)
    : item.kind === "mcu"
      ? zephyrCatalogMcuModuleDevice(item)
      : zephyrCatalogSensorDevice(item);
  return {
    key: `zephyr:${device.id}`,
    source: "zephyr-catalog",
    kind: item.kind || device.category,
    label: `${device.display} [zephyr ${item.kind || device.category}]`,
    device,
  };
}

function zephyrCatalogUpsertBoardLibraryEntry(entry) {
  const existing = zephyrCatalogBoardEditorEntries.findIndex((item) => item.key === entry.key);
  if (existing >= 0) {
    zephyrCatalogBoardEditorEntries.splice(existing, 1, entry);
  } else {
    zephyrCatalogBoardEditorEntries.push(entry);
  }
}

function zephyrCatalogUpsertExternalDevice(device) {
  const existing = zephyrCatalogExternalDevices.findIndex((item) => item.id === device.id);
  if (existing >= 0) {
    zephyrCatalogExternalDevices.splice(existing, 1, device);
  } else {
    zephyrCatalogExternalDevices.push(device);
  }
  const busOptions = getPeripheralOptionsForBusFamily(device.bus_family);
  externalDeviceStates[device.id] = {
    selected: true,
    bus: busOptions[0]?.name || device.bus || "",
  };
}

function zephyrCatalogVisibleItems() {
  const search = zephyrCatalogSearch.trim().toLowerCase();
  return zephyrCatalogItems.filter((item) => {
    if (zephyrCatalogFilter !== "all" && item.kind !== zephyrCatalogFilter) {
      return false;
    }
    if (!search) {
      return true;
    }
    const haystack = [
      item.label,
      item.name,
      item.vendor,
      item.compatible,
      ...(item.socs || []),
      ...(item.buses || []),
    ].join(" ").toLowerCase();
    return haystack.includes(search);
  });
}

function zephyrCatalogDisplayResolution(item) {
  const width = Number(item?.display?.width || item?.parameters?.display?.width || 0);
  const height = Number(item?.display?.height || item?.parameters?.display?.height || 0);
  return width > 0 && height > 0 ? { width, height } : null;
}

function zephyrCatalogDisplaySummary(item) {
  const resolution = zephyrCatalogDisplayResolution(item);
  if (resolution) {
    return `${resolution.width} x ${resolution.height}`;
  }
  return item?.buses?.length ? item.buses.join(", ") : "properties only";
}

function lvglPresetForResolution(width, height) {
  if (width <= 260 && height <= 260) return "watch";
  if (width >= 760) return "panel";
  if (width <= 380 && height >= 500) return "phone";
  return "dashboard";
}

function lvglApplyZephyrCatalogDisplay(item) {
  const nextState = cloneJson(lvglSerializeState() || lvglDefaultState());
  const resolution = zephyrCatalogDisplayResolution(item);
  nextState.importMeta = {
    source: `Zephyr catalog: ${item.label || item.compatible || item.name || "display"}`,
    kind: "zephyr-display",
    display: {
      label: String(item.label || item.name || item.compatible || "Display"),
      compatible: String(item.compatible || ""),
      width: resolution?.width || null,
      height: resolution?.height || null,
      buses: Array.isArray(item.buses) ? [...item.buses] : [],
      bindingPaths: Array.isArray(item.binding_paths) ? [...item.binding_paths] : [],
      properties: Array.isArray(item.properties) ? cloneJson(item.properties) : [],
    },
  };
  if (resolution) {
    nextState.preset = lvglPresetForResolution(resolution.width, resolution.height);
    nextState.screens = (nextState.screens || []).map((screen) => {
      const resizedScreen = { ...screen, w: resolution.width, h: resolution.height };
      resizedScreen.nodes = (screen.nodes || []).map((node) => {
        const cloned = cloneJson(node);
        lvglClampNode(cloned, resizedScreen);
        return cloned;
      });
      return resizedScreen;
    });
  }
  lvglRestoreState(nextState, {
    logMessage: resolution
      ? `Applied display profile ${item.label || item.compatible} (${resolution.width} x ${resolution.height})`
      : `Applied display profile ${item.label || item.compatible}`,
  });
}

function zephyrCatalogSelectedItem() {
  return zephyrCatalogItems.find((item) => item.key === zephyrCatalogActiveKey) || null;
}

function zephyrCatalogRenderList() {
  const list = $("#zephyrCatalogList");
  if (!list) return;
  const visible = zephyrCatalogVisibleItems();
  if (!visible.length) {
    list.innerHTML = '<div class="zcatalog-empty">No catalog items match the current filter.</div>';
    return;
  }
  list.innerHTML = visible.map((item) => `
    <button class="zcatalog-item${item.key === zephyrCatalogActiveKey ? " active" : ""}" data-zcatalog-key="${escapeHtml(item.key)}">
      <strong>${escapeHtml(item.label || item.name)}</strong>
      <span class="zcatalog-item-meta">${escapeHtml(item.kind === "mcu"
        ? `${item.vendor || "vendor"} - ${item.name}`
        : item.kind === "display"
          ? `${item.compatible} - ${zephyrCatalogDisplaySummary(item)}`
          : `${item.compatible} - ${item.buses?.join(", ") || "bus n/a"}`)}</span>
    </button>
  `).join("");
  list.querySelectorAll("[data-zcatalog-key]").forEach((button) => {
    button.addEventListener("click", () => {
      zephyrCatalogActiveKey = button.dataset.zcatalogKey;
      zephyrCatalogRender();
    });
  });
}

function zephyrCatalogDetailActions(item) {
  if (item.kind === "mcu") {
    return `
      <div class="zcatalog-actions">
        <button class="btn btn-accent" data-zcatalog-action="use-mcu-configurator">Use In Pin Configurator</button>
        <button class="btn" data-zcatalog-action="use-mcu-package">Use In Package Manager</button>
      </div>
    `;
  }
  if (item.kind === "display") {
    return `
      <div class="zcatalog-actions">
        <button class="btn btn-accent" data-zcatalog-action="use-display-lvgl">Use In LVGL Layout</button>
      </div>
    `;
  }
  return `
    <div class="zcatalog-actions">
      <button class="btn btn-accent" data-zcatalog-action="use-sensor-configurator">Add To Pin Configurator</button>
      <button class="btn" data-zcatalog-action="use-sensor-parser">Use In Sensor Parser</button>
      <button class="btn" data-zcatalog-action="use-sensor-board-editor">Add To Board Editor</button>
    </div>
  `;
}

function zephyrCatalogRenderDetail() {
  const detail = $("#zephyrCatalogDetail");
  if (!detail) return;
  const item = zephyrCatalogSelectedItem();
  if (!item) {
    detail.innerHTML = '<div class="zcatalog-empty">Select an MCU board or sensor binding to inspect its Zephyr parameters and send it into the current workflow.</div>';
    return;
  }

  const chips = item.kind === "mcu"
    ? (item.socs || []).map((soc) => `<span class="zcatalog-chip">${escapeHtml(soc)}</span>`).join("")
    : item.kind === "display"
      ? [
          zephyrCatalogDisplayResolution(item) ? `<span class="zcatalog-chip">${escapeHtml(zephyrCatalogDisplaySummary(item))}</span>` : "",
          ...(item.buses || []).map((bus) => `<span class="zcatalog-chip">${escapeHtml(bus)}</span>`),
        ].filter(Boolean).join("")
    : (item.buses || []).map((bus) => `<span class="zcatalog-chip">${escapeHtml(bus)}</span>`).join("");

  const parameterRows = item.kind === "mcu"
    ? `
      <tr><th>Board</th><td>${escapeHtml(item.name)}</td></tr>
      <tr><th>Vendor</th><td>${escapeHtml(item.vendor || "-")}</td></tr>
      <tr><th>Board File</th><td>${escapeHtml(item.board_path || "-")}</td></tr>
      <tr><th>SoCs / Variants</th><td>${escapeHtml((item.socs || []).join(", ") || "-")}</td></tr>
    `
    : item.kind === "display"
      ? `
      <tr><th>Compatible</th><td>${escapeHtml(item.compatible || "-")}</td></tr>
      <tr><th>Vendor</th><td>${escapeHtml(item.vendor || "-")}</td></tr>
      <tr><th>Resolution</th><td>${escapeHtml(zephyrCatalogDisplaySummary(item))}</td></tr>
      <tr><th>Bus</th><td>${escapeHtml((item.buses || []).join(", ") || "-")}</td></tr>
      <tr><th>Properties</th><td>${escapeHtml(String((item.properties || []).length))}</td></tr>
    `
    : (item.properties || []).slice(0, 18).map((prop) => `
      <tr>
        <th>${escapeHtml(prop.name)}</th>
        <td>${escapeHtml(prop.type)}${prop.required ? ' - required' : ''}${prop.description ? `<div class="zcatalog-detail-meta">${escapeHtml(prop.description)}</div>` : ''}</td>
      </tr>
    `).join("");

  detail.innerHTML = `
    <div class="zcatalog-detail">
      <div class="zcatalog-detail-head">
        <div>
          <h2>${escapeHtml(item.label || item.name)}</h2>
          <div class="zcatalog-detail-meta">${escapeHtml(item.kind === "mcu" ? item.directory || item.board_path || "" : item.compatible || "")}</div>
        </div>
        <div class="zcatalog-chip-row">${chips || '<span class="zcatalog-chip">No parameters</span>'}</div>
      </div>
      ${zephyrCatalogDetailActions(item)}
      ${item.description ? `<div class="zcatalog-note">${escapeHtml(item.description)}</div>` : ""}
      <div class="zcatalog-detail-section">
        <h3>${item.kind === "mcu" ? "Board Parameters" : item.kind === "display" ? "Display Parameters" : "Binding Parameters"}</h3>
        <table class="zcatalog-prop-table"><tbody>${parameterRows}</tbody></table>
      </div>
      ${item.kind !== "mcu" && item.binding_paths?.length ? `<div class="zcatalog-detail-section"><h3>Bindings</h3><div class="zcatalog-note">${item.binding_paths.map((path) => escapeHtml(path)).join('<br>')}</div></div>` : ""}
      ${item.kind === "display" && item.properties?.length ? `<div class="zcatalog-detail-section"><h3>Binding Properties</h3><table class="zcatalog-prop-table"><tbody>${item.properties.slice(0, 18).map((prop) => `
        <tr>
          <th>${escapeHtml(prop.name)}</th>
          <td>${escapeHtml(prop.type)}${prop.required ? ' - required' : ''}${prop.default !== undefined && prop.default !== null && prop.default !== '' ? `<div class="zcatalog-detail-meta">Default: ${escapeHtml(String(prop.default))}</div>` : ''}${prop.description ? `<div class="zcatalog-detail-meta">${escapeHtml(prop.description)}</div>` : ''}</td>
        </tr>
      `).join('')}</tbody></table></div>` : ""}
    </div>
  `;

  detail.querySelectorAll("[data-zcatalog-action]").forEach((button) => {
    button.addEventListener("click", () => void zephyrCatalogHandleAction(button.dataset.zcatalogAction, item));
  });
}

function zephyrCatalogRenderSummary() {
  const summary = $("#zephyrCatalogSummary");
  if (!summary) return;
  summary.textContent = zephyrCatalogItems.length
    ? `Root: ${zephyrCatalogRoot} - ${zephyrCatalogSummary.mcu_count} MCU boards - ${zephyrCatalogSummary.sensor_count} sensors - ${zephyrCatalogSummary.display_count || 0} displays`
    : "Load the local Zephyr tree to browse supported boards and sensor bindings.";
}

function zephyrCatalogRender() {
  zephyrCatalogRenderSummary();
  zephyrCatalogRenderList();
  zephyrCatalogRenderDetail();
}

function updateAppTabOverflowState() {
  const tabStrip = document.querySelector(".app-tabs");
  if (!tabStrip) return;
  const maxScroll = Math.max(0, tabStrip.scrollWidth - tabStrip.clientWidth);
  const epsilon = 4;
  tabStrip.classList.toggle("can-scroll-left", tabStrip.scrollLeft > epsilon);
  tabStrip.classList.toggle("can-scroll-right", maxScroll - tabStrip.scrollLeft > epsilon);
}

function activateAppTab(target) {
  $$(".app-tab").forEach((tab) => tab.classList.toggle("active", tab.dataset.appTab === target));
  $$(".tab-content").forEach((content) => content.classList.toggle("active", content.dataset.appContent === target));
  const selector = document.getElementById("appTabSelect");
  if (selector && selector.value !== target) selector.value = target;
  const activeTabButton = document.querySelector(`.app-tab[data-app-tab="${target}"]`);
  activeTabButton?.scrollIntoView({ behavior: "smooth", block: "nearest", inline: "center" });
  window.setTimeout(updateAppTabOverflowState, 220);
}

async function openAppTab(target) {
  activateAppTab(target);

  if (target === "packages") {
    pkgLoadExisting();
  }
  if (target === "arduino-workspace") {
    arduinoRender();
  }
  if (target === "board-editor") {
    updateBoardEditorMeta();
    loadBoardEditorDrafts();
    loadBoardEditorDeviceLibrary();
  }
  if (target === "peripherals") {
    pcfgLoadBoards();
  }
  if (target === "lvgl-layout") {
    lvglRender();
  }
  if (target === "protocols") {
    protocolRender();
  }
  if (target === "interrupts") {
    interruptRender();
  }
  if (target === "clock") {
    try {
      await boardLoadPromise;
    } catch {
      // Keep the tab responsive even if the board load failed.
    }
    await clkLoadTrees();
  }
  if (target === "sensors") {
    snsLoadJobs();
  }
  if (target === "zephyr-catalog") {
    void zephyrCatalogLoad();
  }
}

async function zephyrCatalogUseMcuInConfigurator(item) {
  const boardId = zephyrCatalogResolveBoardId(item);
  activateAppTab("configurator");
  if (boardId) {
    await loadBoard(boardId);
    const matchedBoard = availableBoards.find((board) => board.id === boardId);
    toast(`Loaded board ${(matchedBoard?.board || matchedBoard?.name || boardId)} from the Zephyr catalog.`);
    return;
  }
  toast(`No local board matched ${item.name}. Copied part into Package Manager instead.`);
  await zephyrCatalogUseMcuInPackage(item);
}

async function zephyrCatalogUseMcuInPackage(item) {
  activateAppTab("packages");
  const input = $("#mcuPartInput");
  if (input) {
    input.value = zephyrCatalogInferPart(item);
    await mcuLookup();
  }
}

async function zephyrCatalogUseSensorInParser(item) {
  activateAppTab("sensors");
  const input = $("#snsPartInput");
  if (input) {
    input.value = zephyrCatalogInferPart(item);
    await snsIdentifySensor();
  }
}

async function zephyrCatalogUseSensorInConfigurator(item) {
  const device = zephyrCatalogSensorDevice(item);
  zephyrCatalogUpsertExternalDevice(device);
  activateAppTab("configurator");
  renderConfigPanel();
  toast(`Added ${device.display} to the Pin Configurator device catalog.`);
}

async function zephyrCatalogUseSensorInBoardEditor(item) {
  const entry = zephyrCatalogBoardLibraryEntry(item);
  zephyrCatalogUpsertBoardLibraryEntry(entry);
  activateAppTab("board-editor");
  loadBoardEditorDeviceLibrary();
  const select = $("#boardEditorDeviceLibrary");
  if (select) {
    select.value = entry.key;
  }
  addBoardEditorLibraryDevice();
}

async function zephyrCatalogUseDisplayInLvgl(item) {
  activateAppTab("lvgl-layout");
  lvglApplyZephyrCatalogDisplay(item);
  lvglRender();
  const resolution = zephyrCatalogDisplayResolution(item);
  toast(
    resolution
      ? `Applied ${item.label || item.compatible} to LVGL (${resolution.width} x ${resolution.height}).`
      : `Applied ${item.label || item.compatible} display properties to LVGL.`
  );
}

async function zephyrCatalogHandleAction(action, item) {
  try {
    if (action === "use-mcu-configurator") {
      await zephyrCatalogUseMcuInConfigurator(item);
      return;
    }
    if (action === "use-mcu-package") {
      await zephyrCatalogUseMcuInPackage(item);
      return;
    }
    if (action === "use-sensor-configurator") {
      await zephyrCatalogUseSensorInConfigurator(item);
      return;
    }
    if (action === "use-sensor-parser") {
      await zephyrCatalogUseSensorInParser(item);
      return;
    }
    if (action === "use-sensor-board-editor") {
      await zephyrCatalogUseSensorInBoardEditor(item);
      return;
    }
    if (action === "use-display-lvgl") {
      await zephyrCatalogUseDisplayInLvgl(item);
      return;
    }
  } catch (error) {
    toast(`Zephyr catalog action failed: ${error.message}`);
  }
}

async function zephyrCatalogReadResponse(response) {
  const contentType = (response.headers.get("content-type") || "").toLowerCase();
  const rawText = await response.text();
  if (contentType.includes("application/json")) {
    try {
      return { payload: JSON.parse(rawText), rawText, contentType };
    } catch {
      return { payload: null, rawText, contentType };
    }
  }
  return { payload: null, rawText, contentType };
}

function zephyrCatalogResponseError(response, parsed) {
  const origin = `${window.location.protocol}//${window.location.host}`;
  const snippet = String(parsed?.rawText || "")
    .replace(/\s+/g, " ")
    .trim()
    .slice(0, 80);

  if (!response.ok && parsed?.contentType.includes("text/html")) {
    return new Error(
      `Catalog endpoint is unavailable on ${origin} (HTTP ${response.status}). This usually means the page is connected to an older server instance that does not expose /api/zephyr/catalog.`
    );
  }
  if (!response.ok) {
    return new Error(parsed?.payload?.error || `Unable to load catalog (HTTP ${response.status}).`);
  }
  if (!parsed?.payload) {
    return new Error(
      `Catalog endpoint on ${origin} did not return JSON. Received ${parsed?.contentType || "unknown content"}${snippet ? `: ${snippet}` : ""}`
    );
  }
  return null;
}

async function zephyrCatalogLoad(options = {}) {
  const { refresh = false } = options;
  const rootInput = $("#zephyrCatalogRoot");
  const root = rootInput?.value.trim() || zephyrCatalogStorageRoot();
  const summary = $("#zephyrCatalogSummary");
  if (summary) {
    summary.textContent = "Loading Zephyr MCU and sensor catalog...";
  }

  const params = new URLSearchParams();
  if (root) params.set("zephyr_root", root);
  if (refresh) params.set("refresh", "1");

  try {
    const response = await fetch(`/api/zephyr/catalog?${params.toString()}`);
    const parsed = await zephyrCatalogReadResponse(response);
    const responseError = zephyrCatalogResponseError(response, parsed);
    if (responseError) {
      throw responseError;
    }
    const payload = parsed.payload;
    zephyrCatalogRoot = payload.root || root;
    zephyrCatalogSummary = payload.summary || { mcu_count: 0, sensor_count: 0, display_count: 0 };
    zephyrCatalogItems = [
      ...(payload.mcus || []),
      ...(payload.sensors || []),
      ...(payload.displays || []),
    ];
    if (rootInput) {
      rootInput.value = zephyrCatalogRoot;
    }
    zephyrCatalogSaveRoot(zephyrCatalogRoot);
    if (!zephyrCatalogItems.some((item) => item.key === zephyrCatalogActiveKey)) {
      zephyrCatalogActiveKey = zephyrCatalogItems[0]?.key || "";
    }
    zephyrCatalogRender();
  } catch (error) {
    zephyrCatalogItems = [];
    zephyrCatalogActiveKey = "";
    zephyrCatalogSummary = { mcu_count: 0, sensor_count: 0, display_count: 0 };
    zephyrCatalogRender();
    const detail = $("#zephyrCatalogDetail");
    if (detail) {
      detail.innerHTML = `<div class="zcatalog-empty">${escapeHtml(error.message)}</div>`;
    }
  }
}

function zephyrCatalogInit() {
  const rootInput = $("#zephyrCatalogRoot");
  const refreshButton = $("#zephyrCatalogRefresh");
  const kindSelect = $("#zephyrCatalogKind");
  const searchInput = $("#zephyrCatalogSearch");
  if (!rootInput || !refreshButton || !kindSelect || !searchInput) {
    return;
  }

  rootInput.value = zephyrCatalogStorageRoot();
  refreshButton.addEventListener("click", () => void zephyrCatalogLoad({ refresh: true }));
  rootInput.addEventListener("change", () => void zephyrCatalogLoad({ refresh: true }));
  kindSelect.addEventListener("change", () => {
    zephyrCatalogFilter = kindSelect.value;
    zephyrCatalogRender();
  });
  searchInput.addEventListener("input", () => {
    zephyrCatalogSearch = searchInput.value;
    zephyrCatalogRender();
  });
}

function lvglPreset(presetKey) {
  return window.LvglModel?.preset(presetKey) || LVGL_LAYOUT_PRESETS[presetKey] || LVGL_LAYOUT_PRESETS.phone;
}

function lvglScreenNodeForPreset(presetKey, id = "screen_root", name = "screen_main") {
  return window.LvglModel?.createScreenNode(presetKey, id, name) || {
    id,
    type: "screen",
    name,
    text: "Main Screen",
    x: 0,
    y: 0,
    w: lvglPreset(presetKey).width,
    h: lvglPreset(presetKey).height,
    bg: "#0f172a",
    color: "#f8fafc",
    radius: 24,
  };
}

function lvglDefaultState() {
  return window.LvglModel?.defaultState() || {
    preset: "phone",
    currentScreenId: "screen_root",
    startupScreenId: "screen_root",
    selectedId: "screen_root",
    code: "",
    simulation: {
      running: false,
      activeScreenId: "screen_root",
      log: ["Simulation is idle."],
    },
    screens: [{
      ...lvglScreenNodeForPreset("phone"),
      nodes: [],
    }],
  };
}

function lvglEnsureState() {
  lvglLayoutState = window.LvglModel?.normalizeState(lvglLayoutState, {
    cloneJson,
  }) || lvglLayoutState || lvglDefaultState();
  return lvglLayoutState;
}

function lvglWidgetSupportsAction(type) {
  return window.LvglRegistry?.widgetSupportsAction(type) || (type && type !== "screen");
}

function lvglTransition(key) {
  return LVGL_SCREEN_TRANSITIONS[key] || LVGL_SCREEN_TRANSITIONS.move_left;
}

function lvglCodeSymbol(name, fallback = "node") {
  const raw = String(name || fallback)
    .trim()
    .replace(/[^a-zA-Z0-9_]+/g, "_")
    .replace(/^_+/, "");
  const normalized = raw || fallback;
  return /^[A-Za-z_]/.test(normalized) ? normalized : `_${normalized}`;
}

function lvglNodeEventType(node) {
  return window.LvglRegistry?.nodeEventType(node) || "";
}

function lvglNodeHookName(screenSymbol, node) {
  return `ui_on_${screenSymbol}_${lvglCodeSymbol(node.name, node.type)}_event`;
}

function lvglBuildPrjConf() {
  return window.LvglBuild?.buildPrjConf(lvglEnsureState()) || "CONFIG_DISPLAY=y\nCONFIG_LVGL=y";
}

function lvglBuildHeader() {
  return window.LvglBuild?.buildHeader(lvglEnsureState()) || "";
}

function lvglBuildHooksHeader() {
  return window.LvglBuild?.buildHooksHeader(lvglEnsureState()) || "";
}

function lvglBuildHooksSource() {
  return window.LvglBuild?.buildHooksSource(lvglEnsureState()) || "";
}

function lvglBuildIntegrationGuide() {
  const state = lvglEnsureState();
  const issues = window.LvglModel?.validateState(state) || [];
  return window.LvglBuild?.buildIntegrationGuide(state, issues) || "";
}

function lvglSyncGeneratedOutputs(rebuildCode = false) {
  const state = lvglEnsureState();
  if (rebuildCode || !state.code) {
    state.code = lvglBuildCode();
  }
  const artifacts = window.LvglBuild?.buildArtifacts(state) || {
    overlay: "",
    prj_conf: lvglBuildPrjConf(),
    code: state.code || "",
    header: lvglBuildHeader(),
    hooksHeader: lvglBuildHooksHeader(),
    hooks: lvglBuildHooksSource(),
    integration: lvglBuildIntegrationGuide(),
    validation: "",
    styleSchema: "",
  };
  generatedFragments.lvgl = {
    ...artifacts,
    code: state.code || artifacts.code || "",
  };
  refreshGeneratedOutputs();
}

function lvglActivateSimulationScreen(screenId, reason = "") {
  const state = lvglEnsureState();
  const target = lvglFindScreen(screenId);
  if (!target) return;
  state.simulation.activeScreenId = target.id;
  if (reason) {
    lvglAddLog(`${reason} -> ${target.name}`);
  }
  if (target.entryActionName) {
    lvglAddLog(`Enter ${target.name}: ${target.entryActionName}()`);
  }
}

function lvglFindScreen(screenId) {
  const state = lvglEnsureState();
  return state.screens.find(screen => screen.id === screenId) || state.screens[0] || null;
}

function lvglCurrentScreen() {
  const state = lvglEnsureState();
  const targetId = state.simulation.running
    ? (state.simulation.activeScreenId || state.currentScreenId)
    : state.currentScreenId;
  return lvglFindScreen(targetId);
}

function lvglCurrentDesignScreen() {
  const state = lvglEnsureState();
  return lvglFindScreen(state.currentScreenId);
}

function lvglFindNode(nodeId) {
  const state = lvglEnsureState();
  for (const screen of state.screens) {
    if (screen.id === nodeId) {
      return { screen, node: screen, isScreen: true };
    }
    const node = (screen.nodes || []).find(entry => entry.id === nodeId);
    if (node) {
      return { screen, node, isScreen: false };
    }
  }
  const fallback = state.screens[0] || null;
  return fallback ? { screen: fallback, node: fallback, isScreen: true } : null;
}

function lvglSelectedNode() {
  const found = lvglFindNode(lvglEnsureState().selectedId);
  return found ? found.node : null;
}

function lvglClampNode(node, screen = null) {
  const targetScreen = screen || lvglCurrentDesignScreen();
  if (!node || node.type === "screen" || !targetScreen) return;
  node.w = Math.max(36, Number(node.w) || 120);
  node.h = Math.max(24, Number(node.h) || 48);
  node.x = Math.max(0, Math.min(targetScreen.w - node.w, Number(node.x) || 0));
  node.y = Math.max(0, Math.min(targetScreen.h - node.h, Number(node.y) || 0));
}

function lvglAllocateNodeId(prefix) {
  const id = `${prefix}_${lvglLayoutNextId}`;
  lvglLayoutNextId += 1;
  return id;
}

function lvglCreateNode(type) {
  const state = lvglEnsureState();
  const screen = lvglCurrentDesignScreen();
  const base = window.LvglRegistry?.createNode(type, {
    screen,
    presetKey: state.preset,
    allocateNodeId: lvglAllocateNodeId,
    createScreenNode: lvglScreenNodeForPreset,
  }) || {
    id: lvglAllocateNodeId(type),
    type,
    name: `${type}_${(screen?.nodes?.length || 0) + 1}`,
    text: type.charAt(0).toUpperCase() + type.slice(1),
    x: 16,
    y: 16,
    w: 160,
    h: 56,
    bg: "#334155",
    color: "#f8fafc",
    radius: 14,
    action: "none",
    targetScreenId: "",
    transition: "move_left",
    transitionDuration: 220,
  };
  lvglClampNode(base, screen);
  return base;
}

function lvglAddLog(message) {
  return window.LvglUi?.addLog(message);
}

function lvglRenderSimLog() {
  return window.LvglUi?.renderSimLog();
}

function lvglRenderTree() {
  return window.LvglUi?.renderTree();
}

function lvglNodeLabel(node) {
  return escapeHtml(window.LvglRegistry?.nodeLabel(node) || node.name);
}

function lvglRenderStage() {
  return window.LvglUi?.renderStage();
}

function lvglRenderProps() {
  return window.LvglUi?.renderProps();
}

function lvglBuildCode() {
  return window.LvglBuild?.buildCode(lvglEnsureState()) || "";
}

function lvglRender() {
  return window.LvglUi?.render();
}

function lvglResetLayout() {
  return window.LvglUi?.resetLayout();
}

function lvglApplyPreset(presetKey) {
  return window.LvglUi?.applyPreset(presetKey);
}

function lvglAddWidget(type) {
  return window.LvglUi?.addWidget(type);
}

function lvglSerializeState() {
  return window.LvglUi?.serializeState() || cloneJson(lvglEnsureState());
}

function lvglRestoreState(nextState, options = {}) {
  return window.LvglUi?.restoreState(nextState, options);
}

function lvglInit() {
  return window.LvglUi?.init();
}

let lvglPendingImportLayout = null;
let lvglPendingImportSource = "";

const LVGL_IMPORT_MODES = {
  json: {
    sourceKind: "json",
    sourcePlaceholder: "C:\\GIT\\layouts\\ui_layout.lvgl.json or https://example.com/ui_layout.json",
    sourceButton: "Load Source",
    pasteLabel: "Paste JSON",
    pastePlaceholder: "Paste a saved GUI JSON document or a .zpinproj payload here...",
    pasteButton: "Preview Pasted JSON",
    fileAccept: ".json,.zpinproj,.lvgl",
    fileHint: "Choose JSON",
    previewEmpty: "Load a file, URL, or pasted JSON to preview the imported GUI.",
    allowPaste: true,
  },
  zephyr: {
    sourceKind: "zephyr",
    sourcePlaceholder: "C:\\GIT\\app, C:\\GIT\\app\\prj.conf, board.overlay, or a raw Zephyr config snippet",
    sourceButton: "Load Zephyr Source",
    pasteLabel: "Paste Zephyr Config",
    pastePlaceholder: "Paste prj.conf, LVGL Kconfig, or display devicetree text with width/height or LVGL resolution settings...",
    pasteButton: "Preview Zephyr Display",
    fileAccept: ".conf,.overlay,.dts,.dtsi,.txt,.config",
    fileHint: "Choose Zephyr File",
    previewEmpty: "Load a Zephyr project directory, Kconfig file, or devicetree text to infer the LVGL display size.",
    allowPaste: true,
  },
  "display-pdf": {
    sourceKind: "display-pdf",
    sourcePlaceholder: "C:\\GIT\\displays\\panel.pdf or https://vendor.example/display.pdf",
    sourceButton: "Load PDF Source",
    pasteLabel: "Paste PDF",
    pastePlaceholder: "Display PDF import works from a local file, file path, or URL.",
    pasteButton: "Preview PDF",
    fileAccept: ".pdf,application/pdf",
    fileHint: "Choose PDF",
    previewEmpty: "Load a display datasheet PDF to infer the panel resolution and seed the LVGL canvas.",
    allowPaste: false,
  },
};

function lvglCurrentImportMode() {
  return $("#lvglImportMode")?.value || "json";
}

function lvglImportModeConfig(mode = lvglCurrentImportMode()) {
  return LVGL_IMPORT_MODES[mode] || LVGL_IMPORT_MODES.json;
}

function lvglImportSourcePayload(source, mode = lvglCurrentImportMode()) {
  const payload = /^https?:\/\//i.test(source)
    ? { url: source }
    : { file_path: source };
  return {
    ...payload,
    source_kind: lvglImportModeConfig(mode).sourceKind,
  };
}

function lvglPreviewEmptyMessage(mode = lvglCurrentImportMode()) {
  return lvglImportModeConfig(mode).previewEmpty;
}

function lvglUpdateImportModeUi(mode = lvglCurrentImportMode()) {
  const config = lvglImportModeConfig(mode);
  const source = $("#lvglImportSource");
  const sourceBtn = $("#lvglBtnPreviewSource");
  const browseBtn = $("#lvglBtnBrowseImportSource");
  const pasteLabel = $("#lvglImportJsonLabel");
  const pasteInput = $("#lvglImportJson");
  const pasteBtn = $("#lvglBtnPreviewJson");
  const fileInput = $("#lvglImportFile");
  const fileLabel = $("#lvglImportFileTrigger");
  if (source) source.placeholder = config.sourcePlaceholder;
  if (sourceBtn) sourceBtn.textContent = config.sourceButton;
  if (browseBtn) browseBtn.textContent = mode === "zephyr" ? "Browse Folder" : "Browse File";
  if (pasteLabel) pasteLabel.textContent = config.pasteLabel;
  if (pasteInput) {
    pasteInput.placeholder = config.pastePlaceholder;
    pasteInput.disabled = !config.allowPaste;
    pasteInput.hidden = !config.allowPaste;
  }
  if (pasteBtn) {
    pasteBtn.textContent = config.pasteButton;
    pasteBtn.disabled = !config.allowPaste;
    pasteBtn.hidden = !config.allowPaste;
  }
  if (fileInput) fileInput.setAttribute("accept", config.fileAccept);
  if (fileLabel) fileLabel.textContent = config.fileHint;
  lvglClearImportPreview(mode);
}

function lvglClearImportPreview(mode = lvglCurrentImportMode()) {
  lvglPendingImportLayout = null;
  lvglPendingImportSource = "";
  const preview = $("#lvglImportPreview");
  if (preview) {
    preview.className = "lvgl-layout-empty compact";
    preview.textContent = lvglPreviewEmptyMessage(mode);
  }
  const applyBtn = $("#lvglBtnApplyImport");
  if (applyBtn) applyBtn.disabled = true;
}

function lvglRenderImportPreview(layout, sourceLabel = "external source") {
  const preview = $("#lvglImportPreview");
  if (!preview) return;
  const normalized = window.LvglModel?.normalizeState(layout, { cloneJson }) || layout;
  const issues = window.LvglModel?.validateState(normalized) || [];
  const widgetCount = (normalized.screens || []).reduce((total, screen) => total + ((screen.nodes || []).length), 0);
  const primaryScreen = normalized.screens?.[0] || null;
  preview.className = "";
  preview.innerHTML = `
    <div class="lvgl-layout-section">
      <div class="lvgl-layout-section-title">Import Preview</div>
      <div class="lvgl-layout-form">
        <div class="lvgl-layout-field full">
          <label>Source</label>
          <input value="${escapeHtml(sourceLabel)}" disabled>
        </div>
        <div class="lvgl-layout-field">
          <label>Screens</label>
          <input value="${normalized.screens?.length || 0}" disabled>
        </div>
        <div class="lvgl-layout-field">
          <label>Widgets</label>
          <input value="${widgetCount}" disabled>
        </div>
        <div class="lvgl-layout-field">
          <label>Shared Styles</label>
          <input value="${normalized.sharedStyles?.length || 0}" disabled>
        </div>
        <div class="lvgl-layout-field">
          <label>Display</label>
          <input value="${primaryScreen ? `${primaryScreen.w || 0} x ${primaryScreen.h || 0}` : "Unknown"}" disabled>
        </div>
        <div class="lvgl-layout-field">
          <label>Issues</label>
          <input value="${issues.length}" disabled>
        </div>
        <div class="lvgl-layout-field full">
          <label>Startup Screen</label>
          <input value="${escapeHtml(normalized.startupScreenId || normalized.currentScreenId || "screen_root")}" disabled>
        </div>
      </div>
    </div>
  `;
}

async function lvglPreviewImport(payload) {
  const res = await fetch("/api/lvgl/import", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  const result = await res.json();
  if (!res.ok) {
    throw new Error(result.error || "Failed to import GUI layout");
  }
  lvglPendingImportLayout = result.layout || null;
  lvglPendingImportSource = result.source || "external source";
  lvglRenderImportPreview(lvglPendingImportLayout, lvglPendingImportSource);
  const applyBtn = $("#lvglBtnApplyImport");
  if (applyBtn) applyBtn.disabled = !lvglPendingImportLayout;
  return result;
}

function lvglResetImportModal() {
  $("#lvglImportMode") && ($("#lvglImportMode").value = "json");
  $("#lvglImportSource") && ($("#lvglImportSource").value = "");
  $("#lvglImportJson") && ($("#lvglImportJson").value = "");
  $("#lvglImportFileName") && ($("#lvglImportFileName").textContent = "No file selected");
  $("#lvglImportFile") && ($("#lvglImportFile").value = "");
  lvglUpdateImportModeUi("json");
}

async function lvglReadSelectedFile(file, mode = lvglCurrentImportMode()) {
  if (mode === "display-pdf") {
    const buffer = await file.arrayBuffer();
    const bytes = new Uint8Array(buffer);
    let binary = "";
    const chunkSize = 0x8000;
    for (let index = 0; index < bytes.length; index += chunkSize) {
      binary += String.fromCharCode(...bytes.subarray(index, index + chunkSize));
    }
    return {
      source_kind: lvglImportModeConfig(mode).sourceKind,
      binary_base64: btoa(binary),
      filename: file.name,
    };
  }
  return await file.text();
}

async function lvglImportFromPending() {
  if (!lvglPendingImportLayout) {
    toast("Preview a GUI layout before importing it");
    return;
  }
  lvglRestoreState(lvglPendingImportLayout, {
    logMessage: `Imported layout from ${lvglPendingImportSource}`,
  });
  $("#lvglImportModal")?.classList.remove("show");
  toast(`Imported GUI from ${lvglPendingImportSource}`);
}

async function lvglSaveLayoutFile(filePath) {
  const res = await fetch("/api/lvgl/export", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      file_path: filePath,
      layout: lvglSerializeState(),
    }),
  });
  const result = await res.json();
  if (result.saved) {
    toast(`GUI saved to ${result.file_path}`);
  } else {
    toast(`Error: ${result.error}`);
  }
}

// Protocol and interrupt features are loaded from dedicated scripts.

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

let boardLoadPromise = Promise.resolve();

async function loadBoardList() {
  const res = await fetch("/api/boards");
  const boards = await res.json();
  availableBoards = Array.isArray(boards) ? boards : [];
  boardSelect.innerHTML = "";
  availableBoards.forEach(b => {
    const opt = document.createElement("option");
    opt.value = b.id;
    const pkg = b.package ? ` - ${b.package}` : "";
    opt.textContent = `${b.name}${pkg}`;
    boardSelect.appendChild(opt);
  });
  if (availableBoards.length) {
    await loadBoard(availableBoards[0].id);
  }
}

async function performBoardLoad(name) {
  const res = await fetch(`/api/board/${name}`);
  const match = [...boardSelect.options].find(opt => opt.value === name);
  if (match) {
    boardSelect.value = match.value;
  }
  await applyBoardDefinition(await res.json(), { syncEditor: true });
}

function loadBoard(name) {
  boardLoadPromise = performBoardLoad(name).catch(err => {
    console.error("Failed to load board:", err);
    throw err;
  });
  return boardLoadPromise;
}

async function applyBoardDefinition(nextBoard, options = {}) {
  const { syncEditor = false } = options;

  boardData = nextBoard;
  pinStates = {};
  periphStates = {};
  periphCoreStates = {};
  externalDeviceStates = {};
  selectedPin = null;
  highlightedPeripheral = "";
  highlightedPeripheralSignal = "";
  generatedOverlay = "";
  generatedConf = "";
  generatedTargets = {};
  generatedFragments = {
    pin: { overlay: "", prj_conf: "" },
    modules: { overlay: "", prj_conf: "" },
    peripherals: { overlay: "", prj_conf: "" },
    clock: { overlay: "", prj_conf: "" },
    protocols: { overlay: "", prj_conf: "", code: "", header: "", integration: "" },
    lvgl: { overlay: "", prj_conf: "", code: "", header: "", hooksHeader: "", hooks: "", integration: "" },
  };
  renderOutputTabs();
  protocolSyncGeneratedOutputs();
  lvglSyncGeneratedOutputs(false);

  chipLabel.textContent = boardData.soc;
  statsLabel.textContent =
    `Flash: ${boardData.flash_size_kb}KB | SRAM: ${boardData.sram_size_kb}KB | Clock: ${(boardData.clock_hz/1e6).toFixed(0)}MHz`;

  boardData.peripherals.forEach(p => {
    periphStates[p.name] = p.enabled || false;
    periphCoreStates[p.name] = p.core_id || (p.available_cores && p.available_cores[0]) || "";
  });

  initExternalDeviceStates();
  updateBoardEditorMeta();
  arduinoHandleBoardChanged();
  if (syncEditor) {
    setBoardEditorText(boardData);
    setBoardEditorStatus("Loaded current board into the editor.", "ok");
  }

  renderPeripherals();
  renderChip();
  renderConfigPanel();
  interruptRender();
  clkAutoSelectTreeForBoard().catch(err => {
    console.error("Failed to sync clock tree for board:", err);
  });
}

function currentBoardForEditor() {
  if (!boardData) return null;
  const board = cloneJson(boardData);
  const assignedPeripheralEndpoints = {};
  Object.entries(pinStates || {}).forEach(([pinNumber, state]) => {
    const af = state?.af;
    const peripheralName = String(af?.peripheral || "").trim();
    if (!peripheralName) return;
    const signalName = String(af?.signal || af?.name || `PIN_${pinNumber}`).trim();
    if (!signalName) return;
    if (!assignedPeripheralEndpoints[peripheralName]) {
      assignedPeripheralEndpoints[peripheralName] = [];
    }
    if (!assignedPeripheralEndpoints[peripheralName].some((entry) => entry.signal === signalName)) {
      assignedPeripheralEndpoints[peripheralName].push({ signal: signalName, pin: Number(pinNumber) });
    }
  });

  const selectedDevices = selectedExternalDevices().map((device, index) => normalizeBoardEditorDevice({
    ...device,
    id: device.id,
    pins: Array.isArray(device.required_signals) && device.required_signals.length
      ? device.required_signals
      : boardEditorSignalsForBus(device.bus_family || inferDeviceBusFamily(device)),
  }, index));
  const inferredDevices = selectedDevices.length
    ? []
    : Object.entries(assignedPeripheralEndpoints)
      .filter(([peripheralName, endpoints]) => periphStates[peripheralName] && endpoints.length)
      .map(([peripheralName, endpoints], index) => {
        const peripheral = peripheralRecord(peripheralName);
        return normalizeBoardEditorDevice({
          id: `active_${slugifyBoardEditorToken(peripheralName)}`,
          display: peripheral?.display || peripheralName.toUpperCase(),
          category: "peripheral",
          bus: peripheralName,
          compatible: peripheral?.compatible || peripheralName,
          required_signals: endpoints.map((entry) => entry.signal),
          pins: endpoints.map((entry) => entry.signal),
          board_editor_endpoints: endpoints,
          notes: `Synthesized from active ${peripheralName} assignments on the current board.`,
        }, selectedDevices.length + index);
      });
  const canvasDevices = [...selectedDevices, ...inferredDevices];
  const assignedPins = assignedPinsByPeripheral();
  const manualConnections = [];

  canvasDevices.forEach((device) => {
    if (Array.isArray(device.board_editor_endpoints) && device.board_editor_endpoints.length) {
      device.board_editor_endpoints.forEach((entry) => {
        if (!Number.isFinite(entry?.pin)) return;
        manualConnections.push({
          board_pin: Number(entry.pin),
          device_id: device.id,
          device_pin: String(entry.signal),
        });
      });
      return;
    }

    const busName = String(device.bus || "").trim();
    const peripheralPins = assignedPins[busName] || {};
    const requiredSignals = Array.isArray(device.required_signals) && device.required_signals.length
      ? device.required_signals
      : device.pins;

    requiredSignals.forEach((signalName) => {
      const aliases = signalAliasTokens(signalName);
      const boardPin = aliases.map((token) => peripheralPins[token]).find((pinNumber) => Number.isFinite(pinNumber));
      if (!Number.isFinite(boardPin)) return;
      manualConnections.push({
        board_pin: Number(boardPin),
        device_id: device.id,
        device_pin: String(signalName),
      });
    });
  });

  board.external_devices = canvasDevices;
  board.manual_connections = manualConnections;
  board.pin_states = cloneJson(pinStates);
  board.periph_states = cloneJson(periphStates);
  board.external_device_states = cloneJson(externalDeviceStates);
  return board;
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
  const filter = resolveThresholdSearch("boardEditorDraftSearch", boardEditorDrafts.length);
  if (!boardEditorDrafts.length) {
    list.innerHTML = '<div class="empty-state" style="padding: 18px 12px;">No saved board drafts yet.</div>';
    return;
  }

  const drafts = boardEditorDrafts.filter((draft) => {
    if (!filter) return true;
    const haystack = `${draft.filename} ${draft.updated_at || ""} ${draft.size || ""}`.toLowerCase();
    return haystack.includes(filter);
  });

  if (!drafts.length) {
    list.innerHTML = '<div class="empty-state" style="padding: 18px 12px;">No saved board drafts match the current search.</div>';
    return;
  }

  list.innerHTML = drafts.map(draft => `
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
    const socCount = Array.isArray(activeBoard.socs) && activeBoard.socs.length
      ? activeBoard.socs.length
      : (activeBoard.soc ? 1 : 0);
    countsLabel.textContent = `${activeBoard.pins?.length || 0} pins / ${activeBoard.peripherals?.length || 0} peripherals / ${socCount} SoC${socCount === 1 ? "" : "s"}`;
  }
}

function boardEditorCanvasDevices(board) {
  return [...(Array.isArray(board?.mcu_modules) ? board.mcu_modules : []), ...(Array.isArray(board?.external_devices) ? board.external_devices : [])];
}

function boardEditorFindCanvasDevice(board, deviceId) {
  return boardEditorCanvasDevices(board).find((entry) => entry.id === deviceId) || null;
}

function boardEditorPushCanvasDevice(board, device, bucket = "external_devices") {
  if (bucket === "mcu_modules") {
    board.mcu_modules = Array.isArray(board.mcu_modules) ? board.mcu_modules : [];
    board.mcu_modules.push(device);
    return;
  }
  board.external_devices = Array.isArray(board.external_devices) ? board.external_devices : [];
  board.external_devices.push(device);
}

function boardEditorRemoveCanvasDevice(board, deviceId) {
  const removeFrom = (items) => Array.isArray(items) ? items.filter((device) => device.id !== deviceId) : [];
  const before = boardEditorCanvasDevices(board).length;
  board.mcu_modules = removeFrom(board.mcu_modules);
  board.external_devices = removeFrom(board.external_devices);
  return boardEditorCanvasDevices(board).length !== before;
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
    entry.source || "library",
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
  boardEditorCanvasFitMode = false;
  boardEditorCanvasZoom = Math.min(ZOOM_MAX, boardEditorCanvasZoom + ZOOM_STEP);
  applyBoardEditorCanvasZoom();
}

function boardEditorCanvasZoomOut() {
  boardEditorCanvasFitMode = false;
  boardEditorCanvasZoom = Math.max(ZOOM_MIN, boardEditorCanvasZoom - ZOOM_STEP);
  applyBoardEditorCanvasZoom();
}

function boardEditorCanvasFit() {
  const shell = $("#boardEditorCanvasShell");
  if (!shell) return;
  boardEditorCanvasFitMode = true;
  const areaW = Math.max(200, shell.clientWidth - 32);
  const areaH = Math.max(180, shell.clientHeight - 32);
  boardEditorCanvasZoom = Math.min(areaW / BOARD_EDITOR_CANVAS_WIDTH, areaH / BOARD_EDITOR_CANVAS_HEIGHT);
  boardEditorCanvasZoom = Math.max(ZOOM_MIN, Math.min(ZOOM_MAX, boardEditorCanvasZoom));
  applyBoardEditorCanvasZoom();
}

function bindBoardEditorCanvasAutoFit() {
  const shell = $("#boardEditorCanvasShell");
  if (!shell || typeof ResizeObserver !== "function") return;
  if (!boardEditorCanvasResizeObserver) {
    boardEditorCanvasResizeObserver = new ResizeObserver(() => {
      if (!boardEditorCanvasFitMode) return;
      boardEditorCanvasFit();
    });
  }
  boardEditorCanvasResizeObserver.disconnect();
  boardEditorCanvasResizeObserver.observe(shell);
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
    kind: "sensor",
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

function buildBoardEditorParsedMcuLibraryEntry(job) {
  const result = job.result || {};
  const device = result.device || {};
  const packages = Array.isArray(result.packages) ? result.packages : [];
  const primaryPackage = packages[0] || null;
  const soc = String(device.soc || job.soc || job.filename || "MCU").trim();
  const packageNames = packages.map((pkg) => String(pkg.name || "").trim()).filter(Boolean);
  const packageInfo = primaryPackage ? {
    name: primaryPackage.name,
    pin_count: primaryPackage.pin_count,
    pins: Array.isArray(primaryPackage.pins) ? primaryPackage.pins : [],
  } : null;

  return {
    key: `parsed-pdf:${job.job_id}`,
    source: "parsed-pdf",
    kind: "mcu",
    label: `${soc} [parsed MCU PDF]`,
    device: {
      id: `parsed_${slugifyBoardEditorToken(soc)}_${String(job.job_id || "mcu")}`,
      display: soc,
      category: "mcu",
      compatible: soc,
      package: primaryPackage?.name || packageNames[0] || "",
      package_info: packageInfo,
      required_signals: ["VCC", "GND", "RESET", "UART_TX", "UART_RX"],
      pins: ["VCC", "GND", "RESET", "UART_TX", "UART_RX"],
      frameworks: [],
      notes: [
        `Imported from parsed MCU PDF ${job.filename || job.job_id}.`,
        packageNames.length ? `Packages: ${packageNames.join(", ")}.` : "",
        Number(result.pin_mux_count || job.pin_count || 0) > 0 ? `Pin mux entries: ${Number(result.pin_mux_count || job.pin_count || 0)}.` : "",
      ].filter(Boolean).join(" "),
    },
  };
}

function renderBoardEditorDeviceLibrary() {
  const select = $("#boardEditorDeviceLibrary");
  if (!select) return;
  const searchInput = $("#boardEditorDeviceLibrarySearch");
  if (searchInput) searchInput.hidden = false;
  const filter = String(searchInput?.value || "").trim().toLowerCase();
  const kindFilter = String($("#boardEditorDeviceLibraryFilter")?.value || "all");

  const placeholder = '<option value="">Zephyr catalog and parsed PDFs</option>';
  if (!boardEditorDeviceLibrary.length) {
    select.innerHTML = `${placeholder}<option value="" disabled>No library devices available</option>`;
    return;
  }

  const filteredEntries = boardEditorDeviceLibrary.filter((entry) => {
    if (kindFilter === "zephyr" && entry.source !== "zephyr-catalog") return false;
    if (kindFilter === "parsed" && entry.source !== "sensor" && entry.source !== "parsed-pdf") return false;
    if (kindFilter !== "all" && kindFilter !== "zephyr" && kindFilter !== "parsed") {
      const category = String(entry.kind || entry.device?.category || "").toLowerCase();
      if (category !== kindFilter) return false;
    }
    if (!filter) return true;
    const haystack = [
      entry.label,
      entry.device?.display,
      entry.device?.compatible,
      entry.device?.package,
      entry.device?.notes,
      entry.source,
      entry.kind,
    ].filter(Boolean).join(" ").toLowerCase();
    return haystack.includes(filter);
  });

  select.innerHTML = [
    placeholder,
    ...filteredEntries.map((entry) => (
      `<option value="${escapeHtml(entry.key)}">${escapeHtml(entry.label)}</option>`
    )),
  ].join("");

  if (!filteredEntries.length) {
    select.innerHTML = `${placeholder}<option value="" disabled>No library devices match the current search</option>`;
  }
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

  zephyrCatalogBoardEditorEntries.forEach((entry) => {
    entries.push(cloneJson(entry));
  });

  if (!pkgJobs.length) {
    pkgLoadFromStorage();
  }
  pkgJobs.forEach((job) => {
    if (pkgResultIsUsable(job?.result)) {
      entries.push(buildBoardEditorParsedMcuLibraryEntry(job));
    }
  });

  try {
    const catalogRes = await fetch("/api/zephyr/catalog");
    const catalog = await catalogRes.json();
    if (catalogRes.ok) {
      [...(catalog.sensors || []), ...(catalog.displays || []), ...(catalog.mcus || [])].forEach((item) => {
        entries.push(zephyrCatalogBoardLibraryEntry(item));
      });
    }
  } catch (_err) {
    // Keep the built-in catalog when the Zephyr catalog is unavailable.
  }

  try {
    const parseRes = await fetch("/api/parse-jobs");
    const parseJobs = await parseRes.json();
    if (parseRes.ok && Array.isArray(parseJobs)) {
      parseJobs.forEach((job) => {
        if (!entries.some((entry) => entry.key === `parsed-pdf:${job.job_id}`)) {
          entries.push(buildBoardEditorParsedMcuLibraryEntry(job));
        }
      });
    }
  } catch (_err) {
    // Keep local parsed MCU jobs when the live parse-job endpoint is unavailable.
  }

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
    route_points: Array.isArray(connection.route_points)
      ? connection.route_points.map(normalizeBoardEditorRoutePoint).filter(Boolean)
      : [],
  };
  if (!Number.isFinite(normalized.board_pin) || !normalized.device_id || !normalized.device_pin) {
    return null;
  }
  return normalized;
}

function normalizeBoardEditorRoutePoint(point) {
  if (!point || typeof point !== "object") return null;
  const normalized = {
    x: Number(point.x),
    y: Number(point.y),
  };
  if (!Number.isFinite(normalized.x) || !Number.isFinite(normalized.y)) {
    return null;
  }
  return normalized;
}

function boardEditorAlternateLaneOffset(index) {
  if (!Number.isInteger(index) || index <= 0) return 0;
  const step = Math.ceil(index / 2);
  return index % 2 === 1 ? step : -step;
}

function boardEditorClampCanvasPoint(point) {
  return {
    x: Math.max(32, Math.min(BOARD_EDITOR_CANVAS_WIDTH - 32, Number(point.x) || 0)),
    y: Math.max(32, Math.min(BOARD_EDITOR_CANVAS_HEIGHT - 32, Number(point.y) || 0)),
  };
}

function boardEditorNormalizeRect(rect) {
  return {
    id: String(rect.id || "rect"),
    x: Number(rect.x),
    y: Number(rect.y),
    width: Number(rect.width),
    height: Number(rect.height),
  };
}

function boardEditorExpandedRect(rect, margin = 14) {
  const normalized = boardEditorNormalizeRect(rect);
  return {
    ...normalized,
    x: normalized.x - margin,
    y: normalized.y - margin,
    width: normalized.width + margin * 2,
    height: normalized.height + margin * 2,
  };
}

function boardEditorEndpointSide(point, rect, preferredSide = "") {
  const side = String(preferredSide || "").toLowerCase();
  if (side === "left" || side === "right" || side === "top" || side === "bottom") {
    return side;
  }
  const distances = [
    { side: "left", value: Math.abs(Number(point.x) - Number(rect.x)) },
    { side: "right", value: Math.abs(Number(point.x) - (Number(rect.x) + Number(rect.width))) },
    { side: "top", value: Math.abs(Number(point.y) - Number(rect.y)) },
    { side: "bottom", value: Math.abs(Number(point.y) - (Number(rect.y) + Number(rect.height))) },
  ].sort((left, right) => left.value - right.value);
  return distances[0]?.side || "left";
}

function boardEditorEscapePoint(anchor, rect, side, margin = 36) {
  switch (side) {
    case "right":
      return boardEditorClampCanvasPoint({ x: Number(rect.x) + Number(rect.width) + margin, y: Number(anchor.y) });
    case "top":
      return boardEditorClampCanvasPoint({ x: Number(anchor.x), y: Number(rect.y) - margin });
    case "bottom":
      return boardEditorClampCanvasPoint({ x: Number(anchor.x), y: Number(rect.y) + Number(rect.height) + margin });
    case "left":
    default:
      return boardEditorClampCanvasPoint({ x: Number(rect.x) - margin, y: Number(anchor.y) });
  }
}

function boardEditorRectIntersectsHorizontal(rect, y, x1, x2) {
  const minX = Math.min(x1, x2);
  const maxX = Math.max(x1, x2);
  return Number(y) > Number(rect.y)
    && Number(y) < Number(rect.y) + Number(rect.height)
    && maxX > Number(rect.x)
    && minX < Number(rect.x) + Number(rect.width);
}

function boardEditorRectIntersectsVertical(rect, x, y1, y2) {
  const minY = Math.min(y1, y2);
  const maxY = Math.max(y1, y2);
  return Number(x) > Number(rect.x)
    && Number(x) < Number(rect.x) + Number(rect.width)
    && maxY > Number(rect.y)
    && minY < Number(rect.y) + Number(rect.height);
}

function boardEditorPathPoints(points) {
  const simplified = [];
  points.forEach((point) => {
    const clamped = boardEditorClampCanvasPoint(point);
    const previous = simplified[simplified.length - 1];
    if (previous && previous.x === clamped.x && previous.y === clamped.y) {
      return;
    }
    simplified.push(clamped);
  });
  return simplified.filter((point, index, list) => {
    if (index === 0 || index === list.length - 1) return true;
    const prev = list[index - 1];
    const next = list[index + 1];
    const sameX = prev.x === point.x && point.x === next.x;
    const sameY = prev.y === point.y && point.y === next.y;
    return !(sameX || sameY);
  });
}

function boardEditorPathPenalty(points, obstacles, sourceObstacleId, targetObstacleId) {
  let penalty = 0;
  for (let index = 0; index < points.length - 1; index += 1) {
    const start = points[index];
    const end = points[index + 1];
    const horizontal = start.y === end.y;
    const vertical = start.x === end.x;
    if (!horizontal && !vertical) {
      penalty += 1000;
      continue;
    }
    obstacles.forEach((obstacle) => {
      if (index === 0 && obstacle.id === sourceObstacleId) return;
      if (index === points.length - 2 && obstacle.id === targetObstacleId) return;
      const intersects = horizontal
        ? boardEditorRectIntersectsHorizontal(obstacle, start.y, start.x, end.x)
        : boardEditorRectIntersectsVertical(obstacle, start.x, start.y, end.y);
      if (intersects) {
        penalty += 100;
      }
    });
    penalty += Math.abs(Number(end.x) - Number(start.x)) + Math.abs(Number(end.y) - Number(start.y));
  }
  penalty += Math.max(0, points.length - 2) * 6;
  return penalty;
}

function boardEditorLaneCandidates(obstacles, axis, start, end, laneIndex) {
  const offset = boardEditorAlternateLaneOffset(laneIndex) * 26;
  const low = axis === "x" ? 80 : 60;
  const high = axis === "x" ? BOARD_EDITOR_CANVAS_WIDTH - 80 : BOARD_EDITOR_CANVAS_HEIGHT - 60;
  const values = [
    Number(start),
    Number(end),
    (Number(start) + Number(end)) / 2,
  ];
  obstacles.forEach((obstacle) => {
    if (axis === "x") {
      values.push(Number(obstacle.x) - 28, Number(obstacle.x) + Number(obstacle.width) + 28);
    } else {
      values.push(Number(obstacle.y) - 28, Number(obstacle.y) + Number(obstacle.height) + 28);
    }
  });
  values.push(low + 10, high - 10);
  return [...new Set(values.map((value) => Math.max(low, Math.min(high, Math.round(value + offset)))) )];
}

function boardEditorObstacleRects(packageLayout, deviceLayouts, sourceDeviceId, targetDeviceId) {
  const obstacles = [boardEditorExpandedRect({
    id: "mcu",
    x: packageLayout.bodyX,
    y: packageLayout.bodyY,
    width: packageLayout.bodyW,
    height: packageLayout.bodyH,
  })];

  deviceLayouts.forEach((layout) => {
    const rect = layout.type === "package-device"
      ? { id: `device:${layout.device.id}`, x: layout.bodyX, y: layout.bodyY, width: layout.bodyW, height: layout.bodyH }
      : { id: `device:${layout.device.id}`, x: layout.x, y: layout.y, width: layout.width, height: layout.height };
    if (layout.device.id === sourceDeviceId || layout.device.id === targetDeviceId) {
      obstacles.push(boardEditorExpandedRect(rect, 8));
      return;
    }
    obstacles.push(boardEditorExpandedRect(rect, 14));
  });

  return obstacles;
}

function boardEditorEndpointInfo(endpoint, rect, preferredSide, obstacleId) {
  const anchor = { x: Number(endpoint.anchorX), y: Number(endpoint.anchorY) };
  const side = boardEditorEndpointSide(anchor, rect, preferredSide);
  return {
    obstacleId,
    rect,
    side,
    anchor,
    escape: boardEditorEscapePoint(anchor, rect, side),
  };
}

function boardEditorAutoRoutePoints(boardPin, devicePin, laneIndex, packageLayout, deviceLayouts, connection) {
  const targetLayout = deviceLayouts.find((layout) => layout.device.id === connection.device_id);
  const sourceRect = {
    x: packageLayout.bodyX,
    y: packageLayout.bodyY,
    width: packageLayout.bodyW,
    height: packageLayout.bodyH,
  };
  const targetRect = targetLayout
    ? (targetLayout.type === "package-device"
      ? { x: targetLayout.bodyX, y: targetLayout.bodyY, width: targetLayout.bodyW, height: targetLayout.bodyH }
      : { x: targetLayout.x, y: targetLayout.y, width: targetLayout.width, height: targetLayout.height })
    : { x: Number(devicePin.anchorX), y: Number(devicePin.anchorY), width: 1, height: 1 };

  const sourceInfo = boardEditorEndpointInfo(boardPin, sourceRect, boardPin.side, "mcu");
  const targetInfo = boardEditorEndpointInfo(devicePin, targetRect, devicePin.side || devicePin.anchorSide, `device:${connection.device_id}`);
  const obstacles = boardEditorObstacleRects(packageLayout, deviceLayouts, "", connection.device_id);

  const candidates = [];
  boardEditorLaneCandidates(obstacles, "x", sourceInfo.escape.x, targetInfo.escape.x, laneIndex).forEach((laneX) => {
    candidates.push(boardEditorPathPoints([
      sourceInfo.anchor,
      sourceInfo.escape,
      { x: laneX, y: sourceInfo.escape.y },
      { x: laneX, y: targetInfo.escape.y },
      targetInfo.escape,
      targetInfo.anchor,
    ]));
  });
  boardEditorLaneCandidates(obstacles, "y", sourceInfo.escape.y, targetInfo.escape.y, laneIndex).forEach((laneY) => {
    candidates.push(boardEditorPathPoints([
      sourceInfo.anchor,
      sourceInfo.escape,
      { x: sourceInfo.escape.x, y: laneY },
      { x: targetInfo.escape.x, y: laneY },
      targetInfo.escape,
      targetInfo.anchor,
    ]));
  });

  const scored = candidates
    .map((points) => ({
      points,
      penalty: boardEditorPathPenalty(points, obstacles, sourceInfo.obstacleId, targetInfo.obstacleId),
    }))
    .sort((left, right) => left.penalty - right.penalty);

  const best = scored[0]?.points || [sourceInfo.anchor, sourceInfo.escape, targetInfo.escape, targetInfo.anchor];
  return best.slice(1, -1);
}

function boardEditorBuildWirePath(points) {
  if (!Array.isArray(points) || points.length < 2) return "";
  return points
    .map((point, index) => `${index === 0 ? "M" : "L"} ${Number(point.x)} ${Number(point.y)}`)
    .join(" ");
}

function boardEditorResetBadgePosition(routePoints) {
  if (!Array.isArray(routePoints) || !routePoints.length) return null;
  const total = routePoints.reduce((acc, point) => ({
    x: acc.x + Number(point.x),
    y: acc.y + Number(point.y),
  }), { x: 0, y: 0 });
  return boardEditorClampCanvasPoint({
    x: total.x / routePoints.length,
    y: total.y / routePoints.length - 22,
  });
}

function boardEditorResolvedRoutePoints(connection, boardPin, devicePin, laneIndex) {
  const packageLayout = connection.__routePackageLayout;
  const deviceLayouts = connection.__routeDeviceLayouts;
  const explicit = Array.isArray(connection.route_points)
    ? connection.route_points.map(normalizeBoardEditorRoutePoint).filter(Boolean)
    : [];
  if (explicit.length) {
    return explicit.map(boardEditorClampCanvasPoint);
  }
  return boardEditorAutoRoutePoints(boardPin, devicePin, laneIndex, packageLayout, deviceLayouts, connection);
}

function boardEditorConnectionLayouts(board, boardPins, devicePins, packageLayout, deviceLayouts) {
  const entries = board.manual_connections
    .map((connection, index) => {
      const boardPin = boardPins.get(Number(connection.board_pin));
      const devicePin = devicePins.get(`${connection.device_id}:${connection.device_pin}`);
      if (!boardPin || !devicePin) return null;
      return {
        index,
        connection: {
          ...connection,
          __routePackageLayout: packageLayout,
          __routeDeviceLayouts: deviceLayouts,
        },
        boardPin,
        devicePin,
      };
    })
    .filter(Boolean)
    .sort((left, right) => {
      const leftScore = (Number(left.boardPin.anchorY) + Number(left.devicePin.anchorY)) / 2;
      const rightScore = (Number(right.boardPin.anchorY) + Number(right.devicePin.anchorY)) / 2;
      return leftScore - rightScore || left.index - right.index;
    });

  return entries.map((entry, laneIndex) => {
    const explicitRoutePoints = Array.isArray(entry.connection.route_points)
      ? entry.connection.route_points.map(normalizeBoardEditorRoutePoint).filter(Boolean)
      : [];
    entry.connection.__packageLayout = board.__packageLayout;
    entry.connection.__deviceLayouts = board.__deviceLayouts;
    const routePoints = boardEditorResolvedRoutePoints(entry.connection, entry.boardPin, entry.devicePin, laneIndex);
    return {
      ...entry,
      hasCustomRoute: explicitRoutePoints.length > 0,
      routePoints,
      resetBadge: explicitRoutePoints.length > 0 ? boardEditorResetBadgePosition(routePoints) : null,
      path: boardEditorBuildWirePath([
        { x: entry.boardPin.anchorX, y: entry.boardPin.anchorY },
        ...routePoints,
        { x: entry.devicePin.anchorX, y: entry.devicePin.anchorY },
      ]),
    };
  });
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
  normalized.socs = Array.isArray(normalized.socs)
    ? normalized.socs.map((value) => String(value || "").trim()).filter(Boolean)
    : [normalized.soc];
  if (!normalized.socs.length) {
    normalized.socs = [normalized.soc];
  }
  normalized.soc = normalized.socs[0] || normalized.soc;
  normalized.vendor = String(normalized.vendor || "custom");
  normalized.package = String(normalized.package || "Custom");
  normalized.pins = Array.isArray(normalized.pins) ? normalized.pins : [];
  normalized.peripherals = Array.isArray(normalized.peripherals) ? normalized.peripherals : [];
  normalized.mcu_modules = Array.isArray(normalized.mcu_modules)
    ? normalized.mcu_modules.map((device, index) => normalizeBoardEditorDevice({ ...device, category: device?.category || "mcu" }, index))
    : [];
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
  const deviceLayouts = boardEditorCanvasDevices(board).map(buildBoardEditorDeviceLayout);
  const { boardPins, devicePins } = boardEditorConnectionMaps(packageLayout, deviceLayouts);
  const connectionLayouts = boardEditorConnectionLayouts(board, boardPins, devicePins, packageLayout, deviceLayouts);
  const parts = [];
  parts.push(`<svg class="board-editor-canvas-svg" viewBox="0 0 ${BOARD_EDITOR_CANVAS_WIDTH} ${BOARD_EDITOR_CANVAS_HEIGHT}" xmlns="http://www.w3.org/2000/svg">`);
  parts.push(`<text x="46" y="44" class="board-editor-mcu-label" font-size="18">${escapeHtml(board.socs?.join(" + ") || board.soc || board.board)}</text>`);
  parts.push(`<text x="46" y="66" class="board-editor-mcu-subtitle" font-size="12">${escapeHtml(board.package)} wiring canvas</text>`);

  connectionLayouts.forEach((layout) => {
    parts.push(`<path class="board-editor-wire" data-wire-index="${layout.index}" d="${layout.path}" />`);
    layout.routePoints.forEach((point, pointIndex) => {
      parts.push(`<circle class="board-editor-wire-handle" data-wire-index="${layout.index}" data-wire-point-index="${pointIndex}" cx="${point.x}" cy="${point.y}" r="6" />`);
    });
    if (layout.hasCustomRoute && layout.resetBadge) {
      parts.push(`<g class="board-editor-wire-reset" data-wire-reset-index="${layout.index}" transform="translate(${layout.resetBadge.x} ${layout.resetBadge.y})">`);
      parts.push(`<rect class="board-editor-wire-reset-chip" x="-18" y="-10" width="36" height="20" rx="10" />`);
      parts.push('<text class="board-editor-wire-reset-label" x="0" y="4" text-anchor="middle">reset</text>');
      parts.push("</g>");
    }
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
  if (boardEditorCanvasFitMode) {
    boardEditorCanvasFit();
  } else {
    applyBoardEditorCanvasZoom();
  }

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

  svg.querySelectorAll("[data-wire-point-index]").forEach((element) => {
    element.addEventListener("pointerdown", (event) => {
      startBoardEditorWireHandleDrag(
        Number(element.dataset.wireIndex),
        Number(element.dataset.wirePointIndex),
        event,
        svg,
      );
    });
  });

  svg.querySelectorAll("[data-wire-reset-index]").forEach((element) => {
    element.addEventListener("click", (event) => {
      event.stopPropagation();
      resetBoardEditorConnectionRoute(Number(element.dataset.wireResetIndex));
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

function resetBoardEditorConnectionRoute(index) {
  const board = boardEditorPreviewBoard || syncBoardEditorPreview();
  if (!board || !Number.isInteger(index) || index < 0 || index >= board.manual_connections.length) return;
  const connection = board.manual_connections[index];
  if (!connection || !Array.isArray(connection.route_points) || !connection.route_points.length) return;
  connection.route_points = [];
  boardEditorCanvasStart = null;
  writeBoardEditorFromCanvas(board, `Reset the route for MCU pin ${connection.board_pin} to ${connection.device_id}.${connection.device_pin}.`);
}

function nextBoardEditorDeviceId(board, label) {
  const base = slugifyBoardEditorToken(label);
  const known = new Set(boardEditorCanvasDevices(board).map(device => device.id));
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
  }, boardEditorCanvasDevices(board).length);
  boardEditorPushCanvasDevice(board, device, "external_devices");
  boardEditorCanvasStart = null;
  writeBoardEditorFromCanvas(board, `Added ${device.display} to the canvas. Drag it into place, then route wires with the node handles.`);
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
  }, boardEditorCanvasDevices(board).length);
  const targetBucket = (entry.kind || template.category) === "mcu" ? "mcu_modules" : "external_devices";
  boardEditorPushCanvasDevice(board, device, targetBucket);
  boardEditorCanvasStart = null;
  writeBoardEditorFromCanvas(board, `Added ${device.display} from the device library.`);
  if (select) select.value = "";
}

function removeBoardEditorCanvasDevice(deviceId) {
  const board = boardEditorPreviewBoard || syncBoardEditorPreview();
  if (!board || !deviceId) return;
  if (!boardEditorRemoveCanvasDevice(board, deviceId)) return;
  board.manual_connections = board.manual_connections.filter(connection => connection.device_id !== deviceId);
  if (boardEditorCanvasStart?.type === "device" && boardEditorCanvasStart.deviceId === deviceId) {
    boardEditorCanvasStart = null;
  }
  writeBoardEditorFromCanvas(board, `Removed ${deviceId} from the canvas.`);
}

function autoLayoutBoardEditorDevices() {
  const board = boardEditorPreviewBoard || syncBoardEditorPreview();
  if (!board) return;
  boardEditorCanvasDevices(board).forEach((device, index) => {
    device.x = 860 + (index % 2) * 260;
    device.y = 140 + Math.floor(index / 2) * 190;
  });
  writeBoardEditorFromCanvas(board, "Arranged board devices around the package.");
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
  const device = boardEditorFindCanvasDevice(boardEditorPreviewBoard, deviceId);
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
    const activeDevice = boardEditorFindCanvasDevice(boardEditorPreviewBoard, boardEditorCanvasDrag.deviceId);
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
    const activeDevice = boardEditorFindCanvasDevice(boardEditorPreviewBoard, boardEditorCanvasDrag.deviceId);
    boardEditorCanvasDrag = null;
    writeBoardEditorFromCanvas(boardEditorPreviewBoard, activeDevice ? `Placed ${activeDevice.display} on the canvas.` : "Updated canvas layout.");
  };

  document.addEventListener("pointermove", onMove);
  document.addEventListener("pointerup", onUp);
}

function startBoardEditorWireHandleDrag(wireIndex, pointIndex, event, svg) {
  if (!boardEditorPreviewBoard || !Number.isInteger(wireIndex) || !Number.isInteger(pointIndex)) return;
  event.preventDefault();
  event.stopPropagation();

  const connection = boardEditorPreviewBoard.manual_connections[wireIndex];
  if (!connection) return;

  const { boardPins, devicePins } = boardEditorConnectionMaps(
    buildBoardEditorPackageLayout(boardEditorPreviewBoard),
    boardEditorCanvasDevices(boardEditorPreviewBoard).map(buildBoardEditorDeviceLayout),
  );
  const connectionLayouts = boardEditorConnectionLayouts(boardEditorPreviewBoard, boardPins, devicePins);
  const layout = connectionLayouts.find((entry) => entry.index === wireIndex);
  if (!layout || !layout.routePoints[pointIndex]) return;

  connection.route_points = layout.routePoints.map((point) => ({ x: point.x, y: point.y }));
  boardEditorWireHandleDrag = { wireIndex, pointIndex };

  const onMove = (moveEvent) => {
    if (!boardEditorWireHandleDrag || !boardEditorPreviewBoard) return;
    const currentSvg = $("#boardEditorCanvasShell svg");
    if (!currentSvg) return;
    const nextPoint = boardEditorClampCanvasPoint(boardEditorSvgPoint(currentSvg, moveEvent.clientX, moveEvent.clientY));
    const activeConnection = boardEditorPreviewBoard.manual_connections[boardEditorWireHandleDrag.wireIndex];
    if (!activeConnection || !Array.isArray(activeConnection.route_points)) return;
    activeConnection.route_points[boardEditorWireHandleDrag.pointIndex] = nextPoint;
    renderBoardEditorCanvas(boardEditorPreviewBoard);
    setBoardEditorCanvasStatus("Dragging a wire node. Release to keep the updated route.");
  };

  const onUp = () => {
    document.removeEventListener("pointermove", onMove);
    document.removeEventListener("pointerup", onUp);
    if (!boardEditorPreviewBoard || !boardEditorWireHandleDrag) {
      boardEditorWireHandleDrag = null;
      return;
    }
    const activeConnection = boardEditorPreviewBoard.manual_connections[boardEditorWireHandleDrag.wireIndex];
    boardEditorWireHandleDrag = null;
    if (!activeConnection) return;
    writeBoardEditorFromCanvas(
      boardEditorPreviewBoard,
      `Updated the route for MCU pin ${activeConnection.board_pin} to ${activeConnection.device_id}.${activeConnection.device_pin}.`,
    );
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
  const importFolderBtn = $("#boardEditorBtnImportFolder");
  const fileInput = $("#boardEditorFileInput");
  const librarySelect = $("#boardEditorDeviceLibrary");
  const librarySearch = $("#boardEditorDeviceLibrarySearch");
  const libraryFilter = $("#boardEditorDeviceLibraryFilter");
  const addLibraryBtn = $("#boardEditorBtnAddLibrary");
  const addDeviceBtn = $("#boardEditorBtnAddDevice");
  const autoLayoutBtn = $("#boardEditorBtnAutoLayout");
  const clearLinksBtn = $("#boardEditorBtnClearLinks");
  const zoomOutBtn = $("#boardEditorZoomOut");
  const zoomInBtn = $("#boardEditorZoomIn");
  const zoomFitBtn = $("#boardEditorZoomFit");
  const draftSearch = $("#boardEditorDraftSearch");
  const editor = $("#boardEditorJson");

  if (!loadBtn || !validateBtn || !formatBtn || !applyBtn || !saveRepoBtn || !exportBtn || !importBtn || !importFolderBtn || !fileInput || !librarySelect || !addLibraryBtn || !addDeviceBtn || !autoLayoutBtn || !clearLinksBtn || !zoomOutBtn || !zoomInBtn || !zoomFitBtn || !editor) {
    return;
  }

  draftSearch?.addEventListener("input", () => {
    renderBoardEditorDrafts();
  });

  loadBtn.addEventListener("click", () => {
    if (!boardData) {
      setBoardEditorStatus("No board is currently loaded.", "error");
      return;
    }
    boardEditorCanvasStart = null;
    setBoardEditorText(currentBoardForEditor());
    setBoardEditorCanvasStatus(`Loaded ${boardData.board} into the canvas. Click pins to wire them, then drag wire nodes to clean up routes.`, "ok");
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

  importFolderBtn.addEventListener("click", async () => {
    try {
      const dialogRes = await fetch("/api/path-dialog", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ dialog_kind: "directory", title: "Select Zephyr board folder" }),
      });
      const dialogData = await dialogRes.json();
      if (!dialogRes.ok) {
        throw new Error(dialogData.error || "Failed to choose a board folder.");
      }
      if (dialogData.cancelled || !dialogData.path) {
        return;
      }

      const importRes = await fetch("/api/board-editor/import-zephyr-folder", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ path: dialogData.path }),
      });
      const importData = await importRes.json();
      if (!importRes.ok) {
        throw new Error(importData.error || "Failed to import the Zephyr board folder.");
      }
      setBoardEditorText(importData.board);
      boardEditorCanvasStart = null;
      setBoardEditorStatus(`Imported Zephyr board folder for ${importData.board.board}.`, "ok");
      setBoardEditorCanvasStatus(`Imported ${importData.board.zephyr_board_descriptor?.files?.length || 0} descriptor files from ${importData.board.board}.`, "ok");
    } catch (err) {
      setBoardEditorStatus(err.message, "error");
    }
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

  librarySearch?.addEventListener("input", () => {
    renderBoardEditorDeviceLibrary();
  });

  libraryFilter?.addEventListener("change", () => {
    renderBoardEditorDeviceLibrary();
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
  bindBoardEditorCanvasAutoFit();
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
      const signalSummary = peripheralSignalSummary(p.name);
      const signalEntries = peripheralSignalEntries(p.name);
      const row = document.createElement("div");
      row.className = "periph-item"
        + (periphStates[p.name] ? " enabled" : "")
        + (highlightedPeripheral === p.name ? " active" : "");
      row.dataset.periph = p.name;

      row.innerHTML = `
        <span class="dot"></span>
        <span class="periph-copy">
          <span class="periph-label">${p.display}</span>
          ${signalSummary ? `<span class="periph-signals">${escapeHtml(signalSummary)}</span>` : ""}
          ${signalEntries.length ? `
            <span class="periph-signal-chips">
              ${signalEntries.map(({ signal, pins }) => `
                <button
                  type="button"
                  class="periph-signal-chip${highlightedPeripheral === p.name && highlightedPeripheralSignal === signal ? " active" : ""}"
                  data-periph-signal="${escapeHtml(signal)}"
                  title="${escapeHtml(`${signal}: ${pins.join(", ")}`)}"
                >${escapeHtml(signal)}</button>
              `).join("")}
            </span>
          ` : ""}
        </span>
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
          renderConfigPanel();
          interruptRefreshIfVisible();
        });
      }

      row.querySelectorAll("[data-periph-signal]").forEach((button) => {
        button.addEventListener("click", (event) => {
          event.stopPropagation();
          const signal = button.dataset.periphSignal || "";
          const isSameSelection = highlightedPeripheral === p.name && highlightedPeripheralSignal === signal;
          highlightedPeripheral = isSameSelection ? "" : p.name;
          highlightedPeripheralSignal = isSameSelection ? "" : signal;
          renderPeripherals();
          renderChip();
        });
      });

      row.addEventListener("click", () => {
        const isSameSelection = highlightedPeripheral === p.name && !highlightedPeripheralSignal;
        highlightedPeripheral = isSameSelection ? "" : p.name;
        highlightedPeripheralSignal = "";
        renderPeripherals();
        renderChip();
      });

      const toggle = row.querySelector(".periph-toggle");
      toggle.addEventListener("click", (e) => {
        e.stopPropagation();
        periphStates[p.name] = !periphStates[p.name];
        toggle.classList.toggle("on", periphStates[p.name]);
        row.classList.toggle("enabled", periphStates[p.name]);
        updatePinVisuals();
        renderConfigPanel();
        interruptRefreshIfVisible();
      });

      panel.appendChild(row);
    });
  }
}

function pinSupportsPeripheral(pin, peripheralName) {
  if (!pin || !peripheralName) return false;
  return Array.isArray(pin.alt_functions)
    && pin.alt_functions.some((altFunction) => altFunction.peripheral === peripheralName);
}

function pinSupportsPeripheralSignal(pin, peripheralName, signalName) {
  if (!pin || !peripheralName || !signalName) return false;
  const wanted = new Set(signalAliasTokens(signalName));
  return Array.isArray(pin.alt_functions)
    && pin.alt_functions.some((altFunction) => {
      if (altFunction.peripheral !== peripheralName) return false;
      return signalAliasTokens(altFunction.signal || altFunction.name || altFunction.function_id)
        .some((token) => wanted.has(token));
    });
}

function peripheralSignalMap(peripheralName) {
  const signals = new Map();
  if (!boardData || !peripheralName) return signals;

  (boardData.pins || []).forEach((pin) => {
    (pin.alt_functions || []).forEach((altFunction) => {
      if (altFunction.peripheral !== peripheralName) return;
      const signalName = String(altFunction.signal || altFunction.name || `F${altFunction.function_id || "?"}`)
        .trim()
        .toUpperCase();
      if (!signals.has(signalName)) signals.set(signalName, []);
      const pins = signals.get(signalName);
      if (!pins.includes(pin.name)) {
        pins.push(pin.name);
      }
    });
  });

  return signals;
}

function peripheralSignalSummary(peripheralName) {
  const signals = [...peripheralSignalMap(peripheralName).entries()]
    .sort((left, right) => left[0].localeCompare(right[0]));

  if (!signals.length) return "";

  return signals
    .slice(0, 4)
    .map(([signal, pins]) => `${signal}: ${pins.slice(0, 3).join(", ")}${pins.length > 3 ? ", ..." : ""}`)
    .join(" | ");
}

function peripheralSignalEntries(peripheralName) {
  return [...peripheralSignalMap(peripheralName).entries()]
    .sort((left, right) => left[0].localeCompare(right[0]))
    .map(([signal, pins]) => ({ signal, pins }));
}

function addPinConflict(conflictMap, pinNum, conflict) {
  const key = String(pinNum);
  if (!conflictMap[key]) conflictMap[key] = [];
  conflictMap[key].push(conflict);
}

function addConfigurationIssue(issues, issue) {
  issues.push({
    severity: "error",
    affected: [],
    ...issue,
  });
}

function pinConflictSignalKey(af) {
  if (!af || !af.peripheral || af.peripheral === "gpio") return "";
  const signal = String(af.signal || af.name || af.function_id || "").trim();
  if (!signal) return "";
  return `${af.peripheral}::${signal}`;
}

function collectConfigurationHealth() {
  const issues = [];
  const signalClaims = {};
  const assignedSignals = assignedSignalsByPeripheral();

  for (const [pinNum, state] of Object.entries(pinStates || {})) {
    if (!state?.af) continue;
    const props = state.props || {};

    if (state.af.peripheral !== "gpio" && !periphStates[state.af.peripheral]) {
      addConfigurationIssue(issues, {
        id: `pin:${pinNum}:peripheral-disabled`,
        type: "peripheral-disabled",
        scope: "pin",
        pinNum: Number(pinNum),
        peripheral: state.af.peripheral,
        signal: state.af.signal || state.af.name || "",
        title: `Peripheral ${state.af.peripheral} is disabled`,
        summary: `This pin is configured for ${state.af.peripheral}${state.af.signal ? ` (${state.af.signal})` : ""}, but that peripheral is currently off.`,
        affected: [
          `Pin: ${pinLabelForConflict(pinNum)}`,
          `Peripheral toggle: ${state.af.peripheral}`,
        ],
      });
    }

    if (props.bias_pull_up && props.bias_pull_down) {
      addConfigurationIssue(issues, {
        id: `pin:${pinNum}:pull-clash`,
        type: "pull-clash",
        scope: "pin",
        pinNum: Number(pinNum),
        title: "Pull-up and pull-down are both enabled",
        summary: "The current bias properties request opposite electrical defaults on the same pad.",
        affected: [
          `Pin: ${pinLabelForConflict(pinNum)}`,
          "bias_pull_up = true",
          "bias_pull_down = true",
        ],
      });
    }

    const signalKey = pinConflictSignalKey(state.af);
    if (!signalKey) continue;
    if (!signalClaims[signalKey]) signalClaims[signalKey] = [];
    signalClaims[signalKey].push({
      pinNum: Number(pinNum),
      peripheral: state.af.peripheral,
      signal: state.af.signal || state.af.name || `F${state.af.function_id}`,
    });
  }

  Object.values(signalClaims).forEach((claims) => {
    if (!Array.isArray(claims) || claims.length < 2) return;
    claims.forEach((claim) => {
      addConfigurationIssue(issues, {
        id: `pin:${claim.pinNum}:duplicate-signal:${claim.peripheral}:${claim.signal}`,
        type: "duplicate-signal",
        scope: "pin",
        pinNum: claim.pinNum,
        peripheral: claim.peripheral,
        signal: claim.signal,
        otherPins: claims
          .map((entry) => entry.pinNum)
          .filter((pinNum) => pinNum !== claim.pinNum),
        title: `${claim.peripheral}.${claim.signal} is assigned more than once`,
        summary: `Only one pin assignment should drive ${claim.peripheral}.${claim.signal}.`,
        affected: claims.map((entry) => `Claimed on ${pinLabelForConflict(entry.pinNum)}`),
      });
    });
  });

  (boardData?.peripherals || []).forEach((peripheral) => {
    const availableCores = Array.isArray(peripheral.available_cores)
      ? peripheral.available_cores.filter(Boolean)
      : [];
    if (!availableCores.length) return;
    const selectedCore = String(periphCoreStates[peripheral.name] || "").trim();
    if (!selectedCore || availableCores.includes(selectedCore)) return;
    addConfigurationIssue(issues, {
      id: `peripheral:${peripheral.name}:invalid-core`,
      type: "invalid-core",
      scope: "peripheral",
      peripheral: peripheral.name,
      selectedCore,
      availableCores,
      title: `${peripheral.display || peripheral.name} is mapped to an unavailable core`,
      summary: `The selected core ${selectedCore} is not listed for ${peripheral.display || peripheral.name}.`,
      affected: [
        `Peripheral: ${peripheral.display || peripheral.name}`,
        `Selected core: ${selectedCore}`,
        `Available cores: ${availableCores.join(", ")}`,
      ],
    });
  });

  getExternalDeviceCatalog().forEach((device) => {
    const state = externalDeviceStates[device.id];
    if (!state?.selected) return;
    const bus = String(state.bus || device.bus || "").trim();
    if (!bus) {
      addConfigurationIssue(issues, {
        id: `device:${device.id}:missing-bus`,
        type: "device-missing-bus",
        scope: "device",
        deviceId: device.id,
        title: `${device.display} has no selected bus`,
        summary: "Choose a concrete board peripheral before generating output for this device.",
        affected: [`Device: ${device.display}`],
      });
      return;
    }

    if (!periphStates[bus]) {
      addConfigurationIssue(issues, {
        id: `device:${device.id}:bus-disabled`,
        type: "device-bus-disabled",
        scope: "device",
        deviceId: device.id,
        peripheral: bus,
        title: `${device.display} is bound to a disabled bus`,
        summary: `${bus} is selected for this device, but the peripheral is currently off.`,
        affected: [
          `Device: ${device.display}`,
          `Selected bus: ${bus}`,
        ],
      });
    }

    const missingSignals = (device.required_signals || []).filter((requiredSignal) => {
      const aliases = signalAliasTokens(requiredSignal);
      const assigned = assignedSignals[bus];
      return !aliases.length || !assigned || !aliases.some((token) => assigned.has(token));
    });
    if (missingSignals.length) {
      addConfigurationIssue(issues, {
        id: `device:${device.id}:missing-signals`,
        type: "device-missing-signals",
        scope: "device",
        deviceId: device.id,
        peripheral: bus,
        missingSignals,
        title: `${device.display} is missing required bus signals`,
        summary: `The selected bus ${bus} does not yet have all signals assigned for this device.`,
        affected: [
          `Device: ${device.display}`,
          `Selected bus: ${bus}`,
          `Missing: ${missingSignals.join(", ")}`,
        ],
      });
    }
  });

  const byPin = {};
  issues
    .filter((issue) => issue.scope === "pin" && Number.isFinite(Number(issue.pinNum)))
    .forEach((issue) => addPinConflict(byPin, issue.pinNum, issue));

  return {
    issues,
    byPin,
    blockerCount: issues.length,
    pinIssueCount: issues.filter((issue) => issue.scope === "pin").length,
    deviceIssueCount: issues.filter((issue) => issue.scope === "device").length,
    peripheralIssueCount: issues.filter((issue) => issue.scope === "peripheral").length,
  };
}

function collectPinConflicts() {
  return collectConfigurationHealth().byPin;
}

function pinConflictsFor(pinNum, conflictMap = collectPinConflicts()) {
  return conflictMap[String(pinNum)] || [];
}

function pinCustomName(state) {
  return String(state?.custom_name || "").trim();
}

function pinDisplayName(pin, state = pinStates?.[pin?.number]) {
  return pinCustomName(state) || pin.name;
}

function pinChipLabel(pin, state = pinStates?.[pin?.number], side = "any") {
  const displayName = pinDisplayName(pin, state);
  const maxLength = side === "top" || side === "bottom" ? 6 : 8;
  if (displayName.length <= maxLength) return displayName;
  if (maxLength <= 3) return displayName.slice(0, maxLength);
  return `${displayName.slice(0, maxLength - 3)}...`;
}

function normalizeChipText(value) {
  return String(value || "")
    .trim()
    .toUpperCase()
    .replace(/[^A-Z0-9]+/g, "");
}

function pinChipFunctionLabel(pin, state = pinStates?.[pin?.number]) {
  if (state?.af) return state.af.name || "";
  if (pin.kind === "power" || pin.kind === "ground") return "";
  if (pin.kind !== "io") {
    const funcLabel = pin.default_function || "";
    const displayName = pinDisplayName(pin, state);
    if (normalizeChipText(funcLabel) === normalizeChipText(displayName)) return "";
    if (normalizeChipText(funcLabel) === normalizeChipText(pin.name)) return "";
    return funcLabel;
  }
  return "";
}

function pinSummaryRows() {
  if (!boardData?.pins) return [];

  return boardData.pins
    .map((pin) => {
      const state = pinStates?.[pin.number];
      const customName = pinCustomName(state);
      if (!state?.af && !customName) return null;

      let signal = "Custom label only";
      if (state?.af) {
        const signalParts = [];
        if (state.af.peripheral) signalParts.push(String(state.af.peripheral).toUpperCase());
        if (state.af.signal) signalParts.push(state.af.signal);
        else if (state.af.name) signalParts.push(state.af.name);
        signal = signalParts.join(" / ") || state.af.name || "Assigned";
      }

      return {
        pinNumber: pin.number,
        pinName: pin.name,
        pinLabel: `${pin.number} • ${pin.name}`,
        signal,
        customName,
      };
    })
    .filter(Boolean)
    .sort((left, right) => comparePinSummaryRows(left, right, pinSummarySortState));
}

function comparePinSummaryRows(left, right, sortState = pinSummarySortState) {
  const direction = sortState?.direction === "desc" ? -1 : 1;
  let result = 0;

  if (sortState?.key === "signal") {
    result = String(left.signal || "").localeCompare(String(right.signal || ""), undefined, { sensitivity: "base" });
  } else if (sortState?.key === "customName") {
    result = String(left.customName || "").localeCompare(String(right.customName || ""), undefined, { sensitivity: "base" });
  } else {
    result = Number(left.pinNumber) - Number(right.pinNumber);
  }

  if (result === 0) {
    result = Number(left.pinNumber) - Number(right.pinNumber);
  }
  return result * direction;
}

function renderPinSummarySortHeaders() {
  const headers = document.querySelectorAll(".pin-summary-table th[data-sort-key]");
  headers.forEach((header) => {
    const key = header.dataset.sortKey || "";
    const isActive = key === pinSummarySortState.key;
    const direction = isActive ? pinSummarySortState.direction : "none";
    const arrow = direction === "asc" ? " ▲" : direction === "desc" ? " ▼" : "";
    const label = header.dataset.label || header.textContent.replace(/[▲▼]/g, "").trim();
    header.dataset.label = label;
    header.textContent = `${label}${arrow}`;
    header.setAttribute("aria-sort", direction === "none" ? "none" : direction === "asc" ? "ascending" : "descending");
  });
}

function togglePinSummarySort(key) {
  if (!key) return;
  if (pinSummarySortState.key === key) {
    pinSummarySortState.direction = pinSummarySortState.direction === "asc" ? "desc" : "asc";
  } else {
    pinSummarySortState = { key, direction: "asc" };
  }
  renderPinSummaryOverlay();
}

function renderPinSummaryOverlay() {
  if (!pinSummaryBody || !pinSummaryEmpty || !pinSummaryCount) return;
  const rows = pinSummaryRows();
  pinSummaryCount.textContent = `${rows.length} configured pin(s)`;
  pinSummaryBody.innerHTML = rows.map((row) => `
    <tr>
      <td>${escapeHtml(row.pinLabel)}</td>
      <td>${escapeHtml(row.signal)}</td>
      <td>${escapeHtml(row.customName || "-")}</td>
    </tr>
  `).join("");
  pinSummaryEmpty.hidden = rows.length > 0;
  renderPinSummarySortHeaders();
}

function pinSummaryOverlayBounds(width, height) {
  const areaRect = chipArea?.getBoundingClientRect();
  const padding = 12;
  const maxWidth = Math.max(260, (areaRect?.width || 0) - padding * 2);
  const maxHeight = Math.max(160, (areaRect?.height || 0) - padding * 2);
  return {
    padding,
    maxWidth,
    maxHeight,
    width: Math.max(260, Math.min(width ?? 420, maxWidth)),
    height: Math.max(160, Math.min(height ?? Math.min(320, maxHeight), maxHeight)),
  };
}

function applyPinSummaryOverlayLayout() {
  if (!pinSummaryOverlay || !chipArea) return;
  if (!pinSummaryOverlayState.initialized) {
    const rect = pinSummaryOverlay.getBoundingClientRect();
    const bounds = pinSummaryOverlayBounds(rect.width || 420, rect.height || 240);
    pinSummaryOverlayState = {
      ...pinSummaryOverlayState,
      left: 12,
      top: 12,
      width: bounds.width,
      height: bounds.height,
      initialized: true,
    };
  }

  const bounds = pinSummaryOverlayBounds(pinSummaryOverlayState.width, pinSummaryOverlayState.height);
  const clampedLeft = Math.max(bounds.padding, Math.min(pinSummaryOverlayState.left, bounds.maxWidth + bounds.padding - bounds.width));
  const clampedTop = Math.max(bounds.padding, Math.min(pinSummaryOverlayState.top, bounds.maxHeight + bounds.padding - bounds.height));

  pinSummaryOverlayState.left = clampedLeft;
  pinSummaryOverlayState.top = clampedTop;
  pinSummaryOverlayState.width = bounds.width;
  pinSummaryOverlayState.height = bounds.height;

  pinSummaryOverlay.style.left = `${clampedLeft}px`;
  pinSummaryOverlay.style.top = `${clampedTop}px`;
  pinSummaryOverlay.style.width = `${bounds.width}px`;
  pinSummaryOverlay.style.height = `${bounds.height}px`;
}

function beginPinSummaryOverlayPointer(mode, event) {
  if (!pinSummaryOverlay || !chipArea) return;
  const overlayRect = pinSummaryOverlay.getBoundingClientRect();
  const areaRect = chipArea.getBoundingClientRect();
  pinSummaryOverlayPointerState = {
    mode,
    pointerId: typeof event.pointerId === "number" ? event.pointerId : null,
    startClientX: event.clientX,
    startClientY: event.clientY,
    startLeft: overlayRect.left - areaRect.left,
    startTop: overlayRect.top - areaRect.top,
    startWidth: overlayRect.width,
    startHeight: overlayRect.height,
  };
  pinSummaryOverlay.classList.toggle("is-dragging", mode === "drag");
  pinSummaryOverlay.classList.toggle("is-resizing", mode === "resize");
}

function updatePinSummaryOverlayPointer(event) {
  if (!pinSummaryOverlayPointerState) return;
  if (pinSummaryOverlayPointerState.pointerId !== null && typeof event.pointerId === "number" && event.pointerId !== pinSummaryOverlayPointerState.pointerId) return;
  const deltaX = event.clientX - pinSummaryOverlayPointerState.startClientX;
  const deltaY = event.clientY - pinSummaryOverlayPointerState.startClientY;

  if (pinSummaryOverlayPointerState.mode === "drag") {
    pinSummaryOverlayState.left = pinSummaryOverlayPointerState.startLeft + deltaX;
    pinSummaryOverlayState.top = pinSummaryOverlayPointerState.startTop + deltaY;
  } else {
    pinSummaryOverlayState.width = pinSummaryOverlayPointerState.startWidth + deltaX;
    pinSummaryOverlayState.height = pinSummaryOverlayPointerState.startHeight + deltaY;
  }

  applyPinSummaryOverlayLayout();
}

function endPinSummaryOverlayPointer(event) {
  if (!pinSummaryOverlayPointerState) return;
  if (event && pinSummaryOverlayPointerState.pointerId !== null && typeof event.pointerId === "number" && event.pointerId !== pinSummaryOverlayPointerState.pointerId) return;
  pinSummaryOverlayPointerState = null;
  pinSummaryOverlay?.classList.remove("is-dragging", "is-resizing");
}

function ensurePinSummaryOverlayInteractions() {
  if (!pinSummaryOverlay || !pinSummaryHeader || !pinSummaryResizeHandle || pinSummaryOverlay.dataset.interactiveReady === "true") {
    applyPinSummaryOverlayLayout();
    renderPinSummarySortHeaders();
    return;
  }

  pinSummaryHeader.addEventListener("pointerdown", (event) => {
    if (event.button !== 0) return;
    if (event.target.closest("select,button")) return;
    event.preventDefault();
    beginPinSummaryOverlayPointer("drag", event);
  });

  pinSummaryHeader.addEventListener("mousedown", (event) => {
    if (event.button !== 0) return;
    if (event.target.closest("select,button")) return;
    event.preventDefault();
    beginPinSummaryOverlayPointer("drag", event);
  });

  pinSummaryResizeHandle.addEventListener("pointerdown", (event) => {
    if (event.button !== 0) return;
    event.preventDefault();
    beginPinSummaryOverlayPointer("resize", event);
  });

  pinSummaryResizeHandle.addEventListener("mousedown", (event) => {
    if (event.button !== 0) return;
    event.preventDefault();
    beginPinSummaryOverlayPointer("resize", event);
  });

  document.querySelectorAll(".pin-summary-table th[data-sort-key]").forEach((header) => {
    header.addEventListener("click", () => togglePinSummarySort(header.dataset.sortKey || ""));
  });

  window.addEventListener("pointermove", updatePinSummaryOverlayPointer);
  window.addEventListener("pointerup", endPinSummaryOverlayPointer);
  window.addEventListener("pointercancel", endPinSummaryOverlayPointer);
  window.addEventListener("mousemove", updatePinSummaryOverlayPointer);
  window.addEventListener("mouseup", endPinSummaryOverlayPointer);
  pinSummaryOverlay.dataset.interactiveReady = "true";
  renderPinSummarySortHeaders();
  applyPinSummaryOverlayLayout();
}

function sidePanelLayoutMetrics() {
  const totalWidth = mainLayout?.clientWidth || 0;
  const handleWidth = (periphResizeHandle?.offsetWidth || 0) + (configResizeHandle?.offsetWidth || 0);
  return {
    minPanelWidth: 180,
    minCenterWidth: 320,
    totalWidth,
    handleWidth,
    maxPanelWidth: Math.max(180, totalWidth - handleWidth - 320),
  };
}

function clampSidePanelWidth(width) {
  const metrics = sidePanelLayoutMetrics();
  return Math.max(metrics.minPanelWidth, Math.min(width, metrics.maxPanelWidth));
}

function refreshSidePanelLayout() {
  if (!periphPanel || !configPanel || !periphResizeHandle || !configResizeHandle) return;

  if (!sidePanelLayoutState.leftCollapsed) {
    sidePanelLayoutState.leftWidth = clampSidePanelWidth(sidePanelLayoutState.leftWidth || periphPanel.offsetWidth || 240);
  }
  if (!sidePanelLayoutState.rightCollapsed) {
    sidePanelLayoutState.rightWidth = clampSidePanelWidth(sidePanelLayoutState.rightWidth || configPanel.offsetWidth || 320);
  }

  periphPanel.classList.toggle("panel-collapsed", sidePanelLayoutState.leftCollapsed);
  configPanel.classList.toggle("panel-collapsed", sidePanelLayoutState.rightCollapsed);
  periphResizeHandle.classList.toggle("is-collapsed", sidePanelLayoutState.leftCollapsed);
  configResizeHandle.classList.toggle("is-collapsed", sidePanelLayoutState.rightCollapsed);

  periphPanel.style.width = sidePanelLayoutState.leftCollapsed ? "0px" : `${sidePanelLayoutState.leftWidth}px`;
  configPanel.style.width = sidePanelLayoutState.rightCollapsed ? "0px" : `${sidePanelLayoutState.rightWidth}px`;

  periphPanelToggle?.setAttribute("aria-expanded", String(!sidePanelLayoutState.leftCollapsed));
  configPanelToggle?.setAttribute("aria-expanded", String(!sidePanelLayoutState.rightCollapsed));
  periphResizeHandle?.setAttribute("aria-label", sidePanelLayoutState.leftCollapsed ? "Show peripherals panel" : "Resize peripherals panel");
  configResizeHandle?.setAttribute("aria-label", sidePanelLayoutState.rightCollapsed ? "Show pin configuration panel" : "Resize pin configuration panel");

  applyPinSummaryOverlayLayout();
  if (chipZoomMode === "fit" && chipContainer.querySelector("svg.chip-svg")) {
    zoomFit();
  }
}

function beginSidePanelResize(side, event) {
  if (!mainLayout) return;
  sidePanelResizeState = {
    side,
    pointerId: typeof event.pointerId === "number" ? event.pointerId : null,
    startClientX: event.clientX,
    startLeftWidth: periphPanel?.offsetWidth || sidePanelLayoutState.leftWidth || 240,
    startRightWidth: configPanel?.offsetWidth || sidePanelLayoutState.rightWidth || 320,
  };
  document.body.classList.add("is-resizing-panels");
}

function updateSidePanelResize(event) {
  if (!sidePanelResizeState) return;
  if (sidePanelResizeState.pointerId !== null && typeof event.pointerId === "number" && event.pointerId !== sidePanelResizeState.pointerId) return;

  const deltaX = event.clientX - sidePanelResizeState.startClientX;
  if (sidePanelResizeState.side === "left") {
    sidePanelLayoutState.leftCollapsed = false;
    sidePanelLayoutState.leftWidth = clampSidePanelWidth(sidePanelResizeState.startLeftWidth + deltaX);
  } else {
    sidePanelLayoutState.rightCollapsed = false;
    sidePanelLayoutState.rightWidth = clampSidePanelWidth(sidePanelResizeState.startRightWidth - deltaX);
  }
  refreshSidePanelLayout();
}

function endSidePanelResize(event) {
  if (!sidePanelResizeState) return;
  if (event && sidePanelResizeState.pointerId !== null && typeof event.pointerId === "number" && event.pointerId !== sidePanelResizeState.pointerId) return;
  sidePanelResizeState = null;
  document.body.classList.remove("is-resizing-panels");
}

function toggleSidePanel(side) {
  if (side === "left") {
    if (!sidePanelLayoutState.leftCollapsed) {
      sidePanelLayoutState.leftWidth = Math.max(180, periphPanel?.offsetWidth || sidePanelLayoutState.leftWidth || 240);
    }
    sidePanelLayoutState.leftCollapsed = !sidePanelLayoutState.leftCollapsed;
  } else {
    if (!sidePanelLayoutState.rightCollapsed) {
      sidePanelLayoutState.rightWidth = Math.max(180, configPanel?.offsetWidth || sidePanelLayoutState.rightWidth || 320);
    }
    sidePanelLayoutState.rightCollapsed = !sidePanelLayoutState.rightCollapsed;
  }
  refreshSidePanelLayout();
}

function ensureSidePanelInteractions() {
  if (!mainLayout || !periphPanel || !configPanel || !periphResizeHandle || !configResizeHandle) return;
  if (mainLayout.dataset.sidePanelsReady === "true") {
    refreshSidePanelLayout();
    return;
  }

  sidePanelLayoutState.leftWidth = periphPanel.offsetWidth || sidePanelLayoutState.leftWidth;
  sidePanelLayoutState.rightWidth = configPanel.offsetWidth || sidePanelLayoutState.rightWidth;

  const bindResizeHandle = (handle, side) => {
    if (!handle) return;
    handle.addEventListener("pointerdown", (event) => {
      if (event.button !== 0) return;
      if (event.target.closest("button")) return;
      event.preventDefault();
      beginSidePanelResize(side, event);
    });
    handle.addEventListener("mousedown", (event) => {
      if (event.button !== 0) return;
      if (event.target.closest("button")) return;
      event.preventDefault();
      beginSidePanelResize(side, event);
    });
  };

  bindResizeHandle(periphResizeHandle, "left");
  bindResizeHandle(configResizeHandle, "right");
  periphPanelToggle?.addEventListener("click", () => toggleSidePanel("left"));
  configPanelToggle?.addEventListener("click", () => toggleSidePanel("right"));
  window.addEventListener("pointermove", updateSidePanelResize);
  window.addEventListener("pointerup", endSidePanelResize);
  window.addEventListener("pointercancel", endSidePanelResize);
  window.addEventListener("mousemove", updateSidePanelResize);
  window.addEventListener("mouseup", endSidePanelResize);
  window.addEventListener("resize", refreshSidePanelLayout);

  mainLayout.dataset.sidePanelsReady = "true";
  refreshSidePanelLayout();
}

function pinSummaryCsv(rows) {
  const escapeCsv = (value) => {
    const text = String(value ?? "");
    return /[",\n]/.test(text) ? `"${text.replace(/"/g, '""')}"` : text;
  };
  return [
    ["Pin", "Signal", "User Name"].map(escapeCsv).join(","),
    ...rows.map((row) => [row.pinLabel, row.signal, row.customName || ""].map(escapeCsv).join(",")),
  ].join("\n");
}

function pinSummaryMarkdown(rows) {
  const escapeMd = (value) => String(value ?? "").replace(/\|/g, "\\|");
  return [
    "| Pin | Signal | User Name |",
    "| --- | --- | --- |",
    ...rows.map((row) => `| ${escapeMd(row.pinLabel)} | ${escapeMd(row.signal)} | ${escapeMd(row.customName || "-")} |`),
  ].join("\n");
}

function pinSummaryExcel(rows) {
  const makeCell = (value) => `<Cell><Data ss:Type="String">${escapeXml(value)}</Data></Cell>`;
  const bodyRows = rows.map((row) => `
    <Row>${makeCell(row.pinLabel)}${makeCell(row.signal)}${makeCell(row.customName || "")}</Row>`).join("");
  return `<?xml version="1.0"?>
<Workbook xmlns="urn:schemas-microsoft-com:office:spreadsheet"
 xmlns:o="urn:schemas-microsoft-com:office:office"
 xmlns:x="urn:schemas-microsoft-com:office:excel"
 xmlns:ss="urn:schemas-microsoft-com:office:spreadsheet">
  <Worksheet ss:Name="Pin Summary">
    <Table>
      <Row>${makeCell("Pin")}${makeCell("Signal")}${makeCell("User Name")}</Row>${bodyRows}
    </Table>
  </Worksheet>
</Workbook>`;
}

function pinSummarySvg(rows) {
  const columns = [110, 190, 120];
  const rowHeight = 28;
  const headerHeight = 30;
  const width = columns.reduce((sum, value) => sum + value, 0);
  const height = headerHeight + Math.max(rows.length, 1) * rowHeight;
  const headers = ["Pin", "Signal", "User Name"];

  const xPositions = columns.reduce((positions, widthValue, index) => {
    positions.push(index === 0 ? 0 : positions[index - 1] + columns[index - 1]);
    return positions;
  }, []);

  const headerCells = headers.map((header, index) => `
    <rect x="${xPositions[index]}" y="0" width="${columns[index]}" height="${headerHeight}" fill="#1f2430" stroke="#444c60" />
    <text x="${xPositions[index] + 8}" y="20" font-size="12" font-family="Segoe UI, Arial" fill="#d9dde7">${escapeXml(header)}</text>`).join("");

  const body = (rows.length ? rows : [{ pinLabel: "No configured pins", signal: "", customName: "" }]).map((row, rowIndex) => {
    const y = headerHeight + rowIndex * rowHeight;
    const values = [row.pinLabel, row.signal, row.customName || "-"];
    return values.map((value, index) => `
      <rect x="${xPositions[index]}" y="${y}" width="${columns[index]}" height="${rowHeight}" fill="#292d3a" stroke="#444c60" />
      <text x="${xPositions[index] + 8}" y="${y + 18}" font-size="11" font-family="Segoe UI, Arial" fill="#f1f4fb">${escapeXml(value)}</text>`).join("");
  }).join("");

  return `<svg xmlns="http://www.w3.org/2000/svg" width="${width}" height="${height}" viewBox="0 0 ${width} ${height}">${headerCells}${body}</svg>`;
}

function pinSummaryDrawio(rows) {
  const rowHeight = 28;
  const widths = [120, 220, 140];
  const headers = ["Pin", "Signal", "User Name"];
  const cells = [
    '<mxCell id="0"/>',
    '<mxCell id="1" parent="0"/>',
  ];

  const addCell = (id, value, x, y, width, height, style) => {
    cells.push(`<mxCell id="${id}" value="${escapeXml(value)}" style="${style}" vertex="1" parent="1"><mxGeometry x="${x}" y="${y}" width="${width}" height="${height}" as="geometry"/></mxCell>`);
  };

  let id = 2;
  let x = 0;
  headers.forEach((header, index) => {
    addCell(id++, header, x, 0, widths[index], rowHeight, "rounded=0;whiteSpace=wrap;html=1;fillColor=#1f2430;strokeColor=#444c60;fontColor=#d9dde7;fontStyle=1;");
    x += widths[index];
  });

  (rows.length ? rows : [{ pinLabel: "No configured pins", signal: "", customName: "" }]).forEach((row, rowIndex) => {
    const values = [row.pinLabel, row.signal, row.customName || "-"];
    let cellX = 0;
    values.forEach((value, index) => {
      addCell(id++, value, cellX, rowHeight * (rowIndex + 1), widths[index], rowHeight, "rounded=0;whiteSpace=wrap;html=1;fillColor=#292d3a;strokeColor=#444c60;fontColor=#f1f4fb;");
      cellX += widths[index];
    });
  });

  return `<?xml version="1.0" encoding="UTF-8"?>
<mxfile host="app.diagrams.net">
  <diagram id="pin-summary" name="Pin Summary">
    <mxGraphModel dx="1200" dy="800" grid="1" gridSize="10" guides="1" tooltips="1" connect="0" arrows="0" fold="1" page="1" pageScale="1" pageWidth="1169" pageHeight="827">
      <root>${cells.join("")}</root>
    </mxGraphModel>
  </diagram>
</mxfile>`;
}

function exportPinSummaryAsPng(rows) {
  const svg = pinSummarySvg(rows);
  const blob = new Blob([svg], { type: "image/svg+xml;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const image = new Image();
  image.onload = () => {
    const canvas = document.createElement("canvas");
    canvas.width = image.width;
    canvas.height = image.height;
    const context = canvas.getContext("2d");
    context.fillStyle = "#202330";
    context.fillRect(0, 0, canvas.width, canvas.height);
    context.drawImage(image, 0, 0);
    canvas.toBlob((pngBlob) => {
      if (!pngBlob) {
        toast("Failed to export PNG");
        URL.revokeObjectURL(url);
        return;
      }
      const pngUrl = URL.createObjectURL(pngBlob);
      const link = document.createElement("a");
      link.href = pngUrl;
      link.download = "pin-summary.png";
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.setTimeout(() => URL.revokeObjectURL(pngUrl), 0);
      URL.revokeObjectURL(url);
    }, "image/png");
  };
  image.onerror = () => {
    URL.revokeObjectURL(url);
    toast("Failed to export PNG");
  };
  image.src = url;
}

function exportPinSummary() {
  const rows = pinSummaryRows();
  const format = pinSummaryExportFormat?.value || "md";
  if (format === "md") return downloadTextFile("pin-summary.md", pinSummaryMarkdown(rows), "text/markdown;charset=utf-8");
  if (format === "csv") return downloadTextFile("pin-summary.csv", pinSummaryCsv(rows), "text/csv;charset=utf-8");
  if (format === "excel") return downloadTextFile("pin-summary.xls", pinSummaryExcel(rows), "application/vnd.ms-excel");
  if (format === "svg") return downloadTextFile("pin-summary.svg", pinSummarySvg(rows), "image/svg+xml;charset=utf-8");
  if (format === "drawio") return downloadTextFile("pin-summary.drawio", pinSummaryDrawio(rows), "application/xml;charset=utf-8");
  if (format === "png") return exportPinSummaryAsPng(rows);
}

function pinLabelForConflict(pinNum) {
  const pin = boardData?.pins?.find((entry) => entry.number === Number(pinNum));
  if (!pin) return `Pin ${pinNum}`;
  return `${pinDisplayName(pin)} (Pin ${pin.number})`;
}

function pinConflictHeadline(conflict) {
  return conflict.title || "Configuration warning";
}

function pinConflictSummary(conflict) {
  return conflict.summary || "Review this pin before generating output.";
}

function pinConflictAffectedItems(conflict) {
  return Array.isArray(conflict.affected) ? conflict.affected : [];
}

function renderPinConflictActions(pinNum, conflict) {
  switch (conflict.type) {
    case "peripheral-disabled":
      return `
        <button class="btn" data-pin-fix="enable-peripheral" data-pin-num="${pinNum}" data-peripheral="${escapeHtml(conflict.peripheral)}">Enable ${escapeHtml(conflict.peripheral)}</button>
        <button class="btn" data-pin-fix="clear-pin" data-pin-num="${pinNum}">Clear assignment</button>`;
    case "duplicate-signal":
      return `
        <button class="btn" data-pin-fix="clear-other-pins" data-pin-num="${pinNum}" data-other-pins="${(conflict.otherPins || []).join(",")}">Keep this pin</button>
        <button class="btn" data-pin-fix="clear-pin" data-pin-num="${pinNum}">Clear this pin</button>`;
    case "pull-clash":
      return `
        <button class="btn" data-pin-fix="clear-pull-up" data-pin-num="${pinNum}">Disable pull-up</button>
        <button class="btn" data-pin-fix="clear-pull-down" data-pin-num="${pinNum}">Disable pull-down</button>`;
    default:
      return "";
  }
}

function renderPinConflictSection(pinNum, conflicts) {
  if (!Array.isArray(conflicts) || !conflicts.length) return "";
  return `
    <div class="config-section pin-conflict-section">
      <label>Configuration Health</label>
      <div class="pin-conflict-summary">${conflicts.length} warning${conflicts.length === 1 ? "" : "s"} detected for this pin.</div>
      ${conflicts.map((conflict) => `
        <div class="pin-conflict-card">
          <div class="pin-conflict-title">${escapeHtml(pinConflictHeadline(conflict))}</div>
          <div class="pin-conflict-copy">${escapeHtml(pinConflictSummary(conflict))}</div>
          <div class="pin-conflict-affected">
            ${(pinConflictAffectedItems(conflict) || []).map((item) => `<div>${escapeHtml(item)}</div>`).join("")}
          </div>
          <div class="pin-conflict-actions">
            ${renderPinConflictActions(pinNum, conflict)}
          </div>
        </div>`).join("")}
    </div>`;
}

function applyPinConflictFix(action, pinNum, dataset = {}) {
  const key = String(pinNum);
  switch (action) {
    case "enable-peripheral":
      if (dataset.peripheral in periphStates) {
        periphStates[dataset.peripheral] = true;
        toast(`Enabled ${dataset.peripheral}`);
      }
      break;
    case "clear-pin":
      delete pinStates[key];
      toast(`Cleared ${pinLabelForConflict(pinNum)}`);
      break;
    case "clear-other-pins":
      String(dataset.otherPins || "")
        .split(",")
        .map((value) => Number(value))
        .filter((value) => Number.isFinite(value))
        .forEach((otherPinNum) => {
          delete pinStates[String(otherPinNum)];
        });
      toast(`Kept ${pinLabelForConflict(pinNum)} and cleared duplicate signal assignments`);
      break;
    case "clear-pull-up":
      if (!pinStates[key]) pinStates[key] = { af: null, props: {} };
      if (!pinStates[key].props) pinStates[key].props = {};
      pinStates[key].props.bias_pull_up = false;
      toast(`Disabled pull-up on ${pinLabelForConflict(pinNum)}`);
      break;
    case "clear-pull-down":
      if (!pinStates[key]) pinStates[key] = { af: null, props: {} };
      if (!pinStates[key].props) pinStates[key].props = {};
      pinStates[key].props.bias_pull_down = false;
      toast(`Disabled pull-down on ${pinLabelForConflict(pinNum)}`);
      break;
    default:
      return;
  }

  renderPeripherals();
  renderChip();
  renderConfigPanel();
  interruptRefreshIfVisible();
}

function renderHealthIssueActions(issue) {
  if (!issue) return "";
  if (issue.scope === "pin" && Number.isFinite(Number(issue.pinNum))) {
    return `<button class="btn" data-health-action="open-pin" data-pin-num="${Number(issue.pinNum)}">Open pin</button>`;
  }
  if (issue.type === "invalid-core") {
    const fallbackCore = issue.availableCores?.[0] || "";
    return `<button class="btn" data-health-action="reset-core" data-peripheral="${escapeHtml(issue.peripheral || "")}" data-core="${escapeHtml(fallbackCore)}">Reset core</button>`;
  }
  if (issue.type === "device-bus-disabled") {
    return `<button class="btn" data-health-action="enable-peripheral" data-peripheral="${escapeHtml(issue.peripheral || "")}">Enable bus</button>`;
  }
  return "";
}

function applyHealthAction(action, dataset = {}) {
  switch (action) {
    case "open-pin":
      if (Number.isFinite(Number(dataset.pinNum))) {
        selectPin(Number(dataset.pinNum));
      }
      return;
    case "reset-core":
      if (dataset.peripheral && dataset.core) {
        periphCoreStates[dataset.peripheral] = dataset.core;
        toast(`Reset ${dataset.peripheral} to ${dataset.core}`);
      }
      break;
    case "enable-peripheral":
      if (dataset.peripheral in periphStates) {
        periphStates[dataset.peripheral] = true;
        toast(`Enabled ${dataset.peripheral}`);
      }
      break;
    default:
      return;
  }

  renderPeripherals();
  renderChip();
  renderConfigPanel();
  interruptRefreshIfVisible();
}

function renderConfiguratorHealth(snapshot = collectConfigurationHealth()) {
  const panel = $("#configHealthPanel");
  if (!panel) return;

  if (!boardData) {
    panel.innerHTML = "";
    return;
  }

  if (!snapshot.issues.length) {
    panel.innerHTML = `
      <div class="config-health-card ok">
        <div class="config-health-head">
          <div>
            <div class="config-health-title">Configuration Health</div>
            <div class="config-health-copy">No blocking issues are currently detected across pins, peripherals, and selected external devices.</div>
          </div>
          <span class="config-health-pill ok">Clean</span>
        </div>
      </div>`;
    return;
  }

  const previewIssues = snapshot.issues.slice(0, 6);
  panel.innerHTML = `
    <div class="config-health-card alert">
      <div class="config-health-head">
        <div>
          <div class="config-health-title">Configuration Health</div>
          <div class="config-health-copy">${snapshot.blockerCount} blocking issue${snapshot.blockerCount === 1 ? "" : "s"} detected. Generate is blocked until you resolve them or explicitly continue.</div>
        </div>
        <span class="config-health-pill alert">Blocked</span>
      </div>
      <div class="config-health-stats">
        <div class="config-health-stat"><strong>${snapshot.pinIssueCount}</strong><span>Pin issues</span></div>
        <div class="config-health-stat"><strong>${snapshot.deviceIssueCount}</strong><span>Device issues</span></div>
        <div class="config-health-stat"><strong>${snapshot.peripheralIssueCount}</strong><span>Peripheral issues</span></div>
      </div>
      <div class="config-health-list">
        ${previewIssues.map((issue) => `
          <div class="config-health-item">
            <div class="config-health-item-title">${escapeHtml(issue.title || "Configuration issue")}</div>
            <div class="config-health-item-copy">${escapeHtml(issue.summary || "")}</div>
            <div class="config-health-item-meta">${(issue.affected || []).map((item) => `<div>${escapeHtml(item)}</div>`).join("")}</div>
            <div class="config-health-actions">${renderHealthIssueActions(issue)}</div>
              </div>`).join("")}
      </div>
      <div class="config-health-footer">
        <button class="btn" id="btnGenerateAnyway">Generate Anyway</button>
      </div>
    </div>`;

  panel.querySelectorAll("[data-health-action]").forEach((button) => {
    button.addEventListener("click", () => applyHealthAction(button.dataset.healthAction, button.dataset));
  });
  panel.querySelector("#btnGenerateAnyway")?.addEventListener("click", () => {
    requestGenerateOutput(true);
  });
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

  if (chipZoomMode === "fit") {
    requestAnimationFrame(() => zoomFit());
  } else {
    applyZoom();
  }

  renderPinSummaryOverlay();
}

// ── QFP / LQFP / QFN renderer (4-sided) ─────────────────────────────

function renderChipQfp() {
  const pinCount = boardData.pin_count;
  const conflictMap = collectPinConflicts();

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
    renderQfpPin(svg, pin, px, py, PAD_W, PAD_H, "left", i);
  });

  // BOTTOM: pins go left to right, pads extend below body
  sides.bottom.forEach((pin, i) => {
    const px = bodyX + 10 + i * (PAD_H + PAD_GAP);
    const py = bodyY + bodyH + BODY_PAD;
    renderQfpPin(svg, pin, px, py, PAD_H, PAD_W, "bottom", i);
  });

  // RIGHT: pins go bottom to top, pads extend right from body
  sides.right.forEach((pin, i) => {
    const px = bodyX + bodyW + BODY_PAD;
    const py = bodyY + bodyH - 10 - PAD_H - i * (PAD_H + PAD_GAP);
    renderQfpPin(svg, pin, px, py, PAD_W, PAD_H, "right", i);
  });

  // TOP: pins go right to left, pads extend above body
  sides.top.forEach((pin, i) => {
    const px = bodyX + bodyW - 10 - PAD_H - i * (PAD_H + PAD_GAP);
    const py = bodyY - BODY_PAD - PAD_W;
    renderQfpPin(svg, pin, px, py, PAD_H, PAD_W, "top", i);
  });

  function renderQfpPin(svg_, pin, x, y, w, h, side, sideIndex = 0) {
    const state = pinStates[pin.number];
    const displayName = pinDisplayName(pin, state);
    const chipLabel = pinChipLabel(pin, state, side);
    const isSelected = selectedPin === pin.number;
    const hasConflict = pinConflictsFor(pin.number, conflictMap).length > 0;
    const isPeripheralMatch = highlightedPeripheralSignal
      ? pinSupportsPeripheralSignal(pin, highlightedPeripheral, highlightedPeripheralSignal)
      : pinSupportsPeripheral(pin, highlightedPeripheral);

    let cls = "pin-pad";
    if (pin.kind === "power")  cls += " power";
    else if (pin.kind === "ground") cls += " ground";
    else if (pin.kind === "special") cls += " special";
    else if (state && state.af) cls += " assigned " + periphColor(state.af.peripheral);
    if (isPeripheralMatch) cls += " peripheral-match " + periphColor(highlightedPeripheral);
    if (hasConflict) cls += " conflicted";
    if (isSelected) cls += " selected";

    svg += `<rect class="${cls}" x="${x}" y="${y}" width="${w}" height="${h}" rx="3"
                  data-pin="${pin.number}"/>`;

    let numX, numY, nameX, nameY, funcX, funcY;
    let numAnchor = "middle", nameAnchor = "middle";
    let nameTransform = "";
    let funcTransform = "";

    if (side === "left") {
      numX  = x + w + 4;  numY  = y + h/2 + 3;  numAnchor = "start";
      nameX = x - 6;      nameY = y + h/2 + 3;  nameAnchor = "end";
      funcX = x - 44;     funcY = y + h/2 + 3;
    } else if (side === "right") {
      numX  = x - 4;       numY  = y + h/2 + 3;  numAnchor = "end";
      nameX = x + w + 6;   nameY = y + h/2 + 3;  nameAnchor = "start";
      funcX = x + w + 44;  funcY = y + h/2 + 3;
    } else if (side === "bottom") {
      const laneOffset = (sideIndex % 2) * 8;
      numX  = x + w/2;     numY  = y - 4;         numAnchor = "middle";
      nameX = x + w/2;     nameY = y + h + 6 + laneOffset;    nameAnchor = "middle";
      funcX = x + w/2;     funcY = y + h + 36 + laneOffset;
      nameTransform = ` transform="rotate(-90 ${nameX} ${nameY})"`;
      funcTransform = ` transform="rotate(-90 ${funcX} ${funcY})"`;
    } else { // top
      const laneOffset = (sideIndex % 2) * 8;
      numX  = x + w/2;     numY  = y + h + 12;    numAnchor = "middle";
      nameX = x + w/2;     nameY = y + 2 - laneOffset;         nameAnchor = "middle";
      funcX = x + w/2;     funcY = y - 28 - laneOffset;
      nameTransform = ` transform="rotate(-90 ${nameX} ${nameY})"`;
      funcTransform = ` transform="rotate(-90 ${funcX} ${funcY})"`;
    }

    svg += `<text class="pin-num" x="${numX}" y="${numY}" text-anchor="${numAnchor}">${pin.number}</text>`;
    svg += `<text class="pin-name" x="${nameX}" y="${nameY}" text-anchor="${nameAnchor}" aria-label="${escapeHtml(displayName)}"${nameTransform}>${escapeHtml(chipLabel)}</text>`;

    const funcLabel = pinChipFunctionLabel(pin, state);
    if (funcLabel) {
      const fanchor = (side === "left") ? "end" : (side === "right") ? "start" : "middle";
      const funcClass = state?.af ? "pin-func-assigned" : "pin-func-default";
      svg += `<text class="pin-func ${funcClass}" x="${funcX}" y="${funcY}" text-anchor="${fanchor}"${funcTransform}>${escapeHtml(funcLabel)}</text>`;
    }
  }

  svg += `</svg>`;
  chipContainer.innerHTML = svg;
}

// ── BGA / WLCSP / UFBGA renderer (grid layout) ──────────────────────

function renderChipBga() {
  const pins = boardData.pins;
  const pinCount = boardData.pin_count;
  const conflictMap = collectPinConflicts();

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
      const displayName = pinDisplayName(pin, state);
      const isSelected = selectedPin === pin.number;
      const hasConflict = pinConflictsFor(pin.number, conflictMap).length > 0;
      const isPeripheralMatch = highlightedPeripheralSignal
        ? pinSupportsPeripheralSignal(pin, highlightedPeripheral, highlightedPeripheralSignal)
        : pinSupportsPeripheral(pin, highlightedPeripheral);

      let cls = "pin-pad bga-ball";
      if (pin.kind === "power")  cls += " power";
      else if (pin.kind === "ground") cls += " ground";
      else if (pin.kind === "special") cls += " special";
      else if (state && state.af) cls += " assigned " + periphColor(state.af.peripheral);
      if (isPeripheralMatch) cls += " peripheral-match " + periphColor(highlightedPeripheral);
      if (hasConflict) cls += " conflicted";
      if (isSelected) cls += " selected";

      // Ball (circle inside cell)
      const bcx = x + CELL / 2;
      const bcy = y + CELL / 2;
      const br = BALL_SIZE / 2;
      svg += `<circle class="${cls}" cx="${bcx}" cy="${bcy}" r="${br}" data-pin="${pin.number}"/>`;

      // Pin name inside or below ball
      const shortName = pinChipLabel(pin, state, "grid");
      svg += `<text class="bga-label" x="${bcx}" y="${bcy + 3}" text-anchor="middle" font-size="7" font-family="Consolas" fill="var(--fg)">${escapeHtml(shortName)}<title>${escapeHtml(displayName)}</title></text>`;

      // Show assigned function as tooltip title
      const funcLabel = state && state.af ? state.af.name : (pin.kind !== "io" ? pin.default_function : "");
      if (funcLabel) {
        svg += `<title>${escapeHtml(displayName)}: ${escapeHtml(funcLabel)}</title>`;
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
  const healthSnapshot = collectConfigurationHealth();
  renderConfiguratorHealth(healthSnapshot);

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

  const state = pinStates[pin.number] || {};
  const customName = pinCustomName(state);
  const displayName = customName || pin.name;

  if (pin.kind !== "io") {
    panel.innerHTML = `<h3><span class="pin-badge">${escapeHtml(displayName)}</span> ${pinLabel}</h3>
      ${customName ? `<div class="config-section" style="font-size:11px;color:var(--fg-dim);">Physical pin: ${escapeHtml(pin.name)}</div>` : ""}
      <div class="config-section"><label for="pinCustomName">Custom Pin Name</label>
        <input id="pinCustomName" type="text" class="input" placeholder="Optional alias" value="${escapeHtml(customName)}">
      </div>
      <div class="empty-state">${pin.kind === 'power' ? 'Power pin' : pin.kind === 'ground' ? 'Ground pin' : 'Special pin'}<br>${pin.default_function}</div>${deviceSection}`;

    const customNameInput = panel.querySelector("#pinCustomName");
    if (customNameInput) {
      customNameInput.addEventListener("change", () => {
        const nextCustomName = String(customNameInput.value || "").trim();
        if (nextCustomName) {
          pinStates[pin.number] = {
            af: null,
            props: {},
            custom_name: nextCustomName,
          };
        } else {
          delete pinStates[pin.number];
        }
        renderChip();
        renderConfigPanel();
      });
    }

    wireExternalDeviceControls(panel);
    return;
  }

  const conflictMap = healthSnapshot.byPin;
  const conflicts = pinConflictsFor(pin.number, conflictMap);

  let html = `<h3><span class="pin-badge">${escapeHtml(displayName)}</span> ${pinLabel}</h3>`;
  if (customName) {
    html += `<div class="config-section" style="font-size:11px;color:var(--fg-dim);">Physical pin: ${escapeHtml(pin.name)}</div>`;
  }

  // Reset button
  html += `<div style="margin-bottom:12px;">
    <button class="btn" id="btnResetPin" style="font-size:11px;">Reset to Default</button>
  </div>`;

  html += `<div class="config-section"><label for="pinCustomName">Custom Pin Name</label>
    <input id="pinCustomName" type="text" class="input" placeholder="Optional alias" value="${escapeHtml(customName)}">
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
  html += renderPinConflictSection(pin.number, conflicts);

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
          custom_name: pinCustomName(pinStates[pin.number]),
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

  panel.querySelectorAll("[data-pin-fix]").forEach((button) => {
    button.addEventListener("click", () => {
      applyPinConflictFix(button.dataset.pinFix, Number(button.dataset.pinNum || pin.number), button.dataset);
    });
  });

  const customNameInput = panel.querySelector("#pinCustomName");
  if (customNameInput) {
    customNameInput.addEventListener("change", () => {
      const nextCustomName = String(customNameInput.value || "").trim();
      const nextState = {
        af: pinStates[pin.number]?.af || null,
        props: { ...(pinStates[pin.number]?.props || {}) },
      };
      if (nextCustomName) {
        nextState.custom_name = nextCustomName;
      }
      if (nextState.af || Object.keys(nextState.props).length || nextState.custom_name) {
        pinStates[pin.number] = nextState;
      } else {
        delete pinStates[pin.number];
      }
      renderChip();
      renderConfigPanel();
    });
  }

  // Property checkboxes
  ["propPullUp", "propPullDown", "propOpenDrain", "propInputEn"].forEach(id => {
    const el = panel.querySelector(`#${id}`);
    if (el) {
      el.addEventListener("change", () => {
        if (!pinStates[pin.number]) {
          pinStates[pin.number] = { af: null, props: {}, custom_name: customName };
        }
        const propKey = {
          propPullUp: "bias_pull_up",
          propPullDown: "bias_pull_down",
          propOpenDrain: "drive_open_drain",
          propInputEn: "input_enable",
        }[id];
        if (!pinStates[pin.number].props) pinStates[pin.number].props = {};
        pinStates[pin.number].props[propKey] = el.checked;
        renderConfigPanel();
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

async function requestGenerateOutput(force = false) {
  const health = collectConfigurationHealth();
  renderConfiguratorHealth(health);
  if (health.blockerCount && !force) {
    toast(`Resolve ${health.blockerCount} configuration issue${health.blockerCount === 1 ? "" : "s"} before generating, or use Generate Anyway.`);
    return false;
  }
  await generateOutput();
  return true;
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
      custom_name:     pinCustomName(state),
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
  generatedFragments.pin.overlay = result.overlay || "";
  generatedFragments.pin.prj_conf = result.prj_conf || "";
  generatedTargets = result.targets || {};

  refreshGeneratedOutputs();
  arduinoWorkspaceState.generatedFiles = { ...(generatedTargets.arduino || {}) };
  arduinoEnsureActiveFile();
  arduinoRenderGeneratedFiles();
  arduinoRenderModulePreview();

  showOutput(activeTab);
  outputBar.classList.remove("collapsed");
  toast("Generated Zephyr, Arduino, and bare-metal outputs");
}

// ── Output bar ───────────────────────────────────────────────────────

function showOutput(tab) {
  const views = collectOutputViews();
  const normalizedTab = views.some((view) => view.id === tab)
    ? tab
    : (tab && tab.includes(":"))
      ? "files"
      : tab;
  const current = views.find(view => view.id === normalizedTab) || views[0] || { id: "overlay", content: generatedOverlay };
  activeTab = current.id;
  const isFilesTab = current.id === "files";
  outputPre.hidden = isFilesTab;
  if (outputFilesView) outputFilesView.hidden = !isFilesTab;
  if (isFilesTab) {
    renderGeneratedFilesOverview();
  } else {
    outputPre.textContent = current.content || "";
  }
  $$(".output-tab").forEach(t => t.classList.toggle("active", t.dataset.tab === current.id));
}

function wireGeneratedFilesOverviewControls() {
  if (!outputFilesSearch || outputFilesSearch.dataset.wired === "true") return;
  outputFilesSearch.dataset.wired = "true";
  outputFilesSearch.addEventListener("input", () => {
    generatedFilesFilter = outputFilesSearch.value.trim();
    renderGeneratedFilesOverview();
  });

  outputFilesCopyBtn?.addEventListener("click", async () => {
    const current = selectedGeneratedFileEntry();
    if (!current) {
      toast("No generated file selected");
      return;
    }
    try {
      await navigator.clipboard.writeText(current.content || "");
      toast(`Copied ${current.path}`);
    } catch {
      toast("Failed to copy file contents");
    }
  });

  outputFilesDownloadBtn?.addEventListener("click", () => {
    const current = selectedGeneratedFileEntry();
    if (!current) {
      toast("No generated file selected");
      return;
    }
    const blob = new Blob([current.content || ""], { type: "text/plain;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = current.path.split("/").pop() || "generated.txt";
    document.body.appendChild(link);
    link.click();
    link.remove();
    window.setTimeout(() => URL.revokeObjectURL(url), 0);
  });
}

// ── Save to project ──────────────────────────────────────────────────

async function saveToProject(projectPath) {
  if (!generatedOverlay) {
    const generated = await requestGenerateOutput();
    if (!generated) return;
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
  chipZoomMode = "manual";
  chipZoom = Math.min(ZOOM_MAX, chipZoom + ZOOM_STEP);
  applyZoom();
}

function zoomOut() {
  chipZoomMode = "manual";
  chipZoom = Math.max(ZOOM_MIN, chipZoom - ZOOM_STEP);
  applyZoom();
}

function zoomReset() {
  chipZoomMode = "manual";
  chipZoom = 1.0;
  applyZoom();
}

function zoomFit() {
  chipZoomMode = "fit";
  const svg = chipContainer.querySelector("svg.chip-svg");
  if (!svg || !chipArea) return;
  const areaW = chipArea.clientWidth - 24;
  const areaH = chipArea.clientHeight - 24;
  const svgW = svg.getAttribute("width");
  const svgH = svg.getAttribute("height");
  if (!svgW || !svgH) return;
  chipZoom = Math.min(areaW / parseFloat(svgW), areaH / parseFloat(svgH));
  chipZoom = Math.max(ZOOM_MIN, Math.min(ZOOM_MAX, chipZoom));
  applyZoom();
}

function ensureChipAreaFitObserver() {
  if (!chipArea || typeof ResizeObserver !== "function") return;
  if (!chipAreaResizeObserver) {
    chipAreaResizeObserver = new ResizeObserver(() => {
      applyPinSummaryOverlayLayout();
      if (chipZoomMode === "fit" && chipContainer.querySelector("svg.chip-svg")) {
        zoomFit();
      }
    });
  }
  chipAreaResizeObserver.disconnect();
  chipAreaResizeObserver.observe(chipArea);
  applyPinSummaryOverlayLayout();
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
    if (pinCustomName(state)) {
      entry.custom_name = pinCustomName(state);
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
      protocol_editor: protocolSerializeState(),
      lvgl_layout: lvglSerializeState(),
      generated_overlay: generatedOverlay,
      generated_conf: generatedConf,
      generated_fragments: generatedFragments,
      sensor_jobs: snsJobsData,
      sensor_selected: snsSelectedJob || "",
      mcu_jobs: pkgJobsData,
      mcu_selected: pkgSelectedJob || "",
      arduino_workspace: arduinoSerializeState(),
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
    if (pinCustomName(state)) {
      entry.custom_name = pinCustomName(state);
    }
    if (entry.af || entry.props || entry.custom_name) {
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
  generatedFragments = {
    pin: { overlay: "", prj_conf: "" },
    modules: { overlay: "", prj_conf: "" },
    peripherals: { overlay: "", prj_conf: "" },
    clock: { overlay: "", prj_conf: "" },
    protocols: { overlay: "", prj_conf: "", code: "", header: "", integration: "" },
    lvgl: { overlay: "", prj_conf: "", code: "", header: "", hooksHeader: "", hooks: "", integration: "" },
    ...(project.generated_fragments || {}),
  };
  generatedOverlay = project.generated_overlay || "";
  generatedConf = project.generated_conf || "";
  generatedTargets = {};
  refreshGeneratedOutputs();
  if (generatedOverlay || generatedConf) {
    showOutput(activeTab);
    outputBar.classList.remove("collapsed");
  }

  if (project.lvgl_layout) {
    lvglRestoreState(project.lvgl_layout);
  }
  if (project.protocol_editor) {
    protocolRestoreState(project.protocol_editor);
  } else {
    protocolSyncGeneratedOutputs();
    protocolRender();
  }
  arduinoRestoreState(project.arduino_workspace || null);

  // Re-render everything
  renderPeripherals();
  renderChip();
  renderConfigPanel();
  interruptRender();

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
  lvglInit();
  protocolInit();
  zephyrCatalogInit();
  arduinoInit();
  const appTabStrip = document.querySelector(".app-tabs");
  const appTabSelect = document.getElementById("appTabSelect");
  appTabStrip?.addEventListener("scroll", updateAppTabOverflowState, { passive: true });
  window.addEventListener("resize", updateAppTabOverflowState);
  updateAppTabOverflowState();
  appTabSelect?.addEventListener("change", async () => {
    await openAppTab(appTabSelect.value);
  });

  boardSelect.addEventListener("change", () => loadBoard(boardSelect.value));

  $("#btnGenerate").addEventListener("click", () => requestGenerateOutput());

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

  // ── LVGL import / save modal ───────────────────────────────────
  $("#lvglBtnImportGui")?.addEventListener("click", () => {
    lvglResetImportModal();
    $("#lvglImportModal")?.classList.add("show");
  });
  $("#lvglBtnCancelImport")?.addEventListener("click", () => {
    $("#lvglImportModal")?.classList.remove("show");
  });
  $("#lvglImportModal")?.addEventListener("click", (e) => {
    if (e.target === e.currentTarget) {
      $("#lvglImportModal").classList.remove("show");
    }
  });
  $("#lvglBtnPreviewSource")?.addEventListener("click", async () => {
    const source = $("#lvglImportSource")?.value.trim();
    if (!source) {
      toast("Enter a file path or URL first");
      return;
    }
    try {
      await lvglPreviewImport(lvglImportSourcePayload(source));
    } catch (err) {
      lvglClearImportPreview();
      toast(err.message || "Failed to preview GUI import");
    }
  });
  $("#lvglBtnPreviewJson")?.addEventListener("click", async () => {
    const text = $("#lvglImportJson")?.value.trim();
    if (!text) {
      toast("Paste Zephyr or LVGL content first");
      return;
    }
    try {
      await lvglPreviewImport({ text, source_kind: lvglImportModeConfig().sourceKind });
    } catch (err) {
      lvglClearImportPreview();
      toast(err.message || "Failed to preview GUI import");
    }
  });
  $("#lvglImportFile")?.addEventListener("change", async (event) => {
    const file = event.target.files?.[0];
    if (!file) return;
    $("#lvglImportFileName").textContent = file.name;
    try {
      const mode = lvglCurrentImportMode();
      const result = await lvglReadSelectedFile(file, mode);
      if (typeof result === "string") {
        $("#lvglImportJson").value = result;
        await lvglPreviewImport({ text: result, source_kind: lvglImportModeConfig(mode).sourceKind });
      } else {
        await lvglPreviewImport(result);
      }
    } catch (err) {
      lvglClearImportPreview();
      toast(err.message || "Failed to read GUI file");
    }
  });
  $("#lvglImportMode")?.addEventListener("change", (event) => {
    lvglUpdateImportModeUi(event.target.value);
  });
  $("#lvglBtnApplyImport")?.addEventListener("click", lvglImportFromPending);

  bindPathBrowseButton("#btnBrowseZephyrCatalogRoot", "#zephyrCatalogRoot", {
    dialogKind: "directory",
    title: "Select Zephyr root directory",
  }, async () => {
    await zephyrCatalogLoad({ refresh: true });
  });
  bindPathBrowseButton("#btnBrowseProjectPath", "#projectPath", {
    dialogKind: "directory",
    title: "Select Zephyr project directory",
  });
  bindPathBrowseButton("#btnBrowseProjectFilePath", "#projectFilePath", {
    dialogKind: "save-file",
    title: "Save project file",
    defaultExtension: ".zpinproj",
    fileTypes: [
      { name: "Pin Config Project", patterns: ["*.zpinproj"] },
      { name: "All files", patterns: ["*.*"] },
    ],
  });
  bindPathBrowseButton("#btnBrowseLoadProjectFilePath", "#loadProjectFilePath", {
    dialogKind: "open-file",
    title: "Open project file",
    fileTypes: [
      { name: "Pin Config Project", patterns: ["*.zpinproj"] },
      { name: "All files", patterns: ["*.*"] },
    ],
  });
  bindPathBrowseButton("#impBtnBrowseProjectPath", "#impProjectPath", {
    dialogKind: "directory",
    title: "Select Zephyr project directory",
  }, async () => {
    await impScanProject();
  });
  bindPathBrowseButton("#arduinoBtnBrowseProjectPath", "#arduinoProjectPath", {
    dialogKind: "directory",
    title: "Select Zephyr project directory",
  }, async (input) => {
    arduinoWorkspaceState.projectPath = input.value.trim();
    await arduinoScanProject();
  });
  bindPathBrowseButton("#arduinoBtnBrowseOutputPath", "#arduinoOutputPath", {
    dialogKind: "directory",
    title: "Select Arduino sketch directory",
  }, async (input) => {
    arduinoWorkspaceState.outputPath = input.value.trim();
  });
  bindPathBrowseButton("#arduinoBtnBrowseValidationPath", "#arduinoValidationPath", {
    dialogKind: "directory",
    title: "Select Renode validation bundle directory",
  }, async (input) => {
    arduinoWorkspaceState.validationPath = input.value.trim();
  });
  bindPathBrowseButton("#lvglBtnBrowseImportSource", "#lvglImportSource", () => lvglImportBrowseDialogOptions(), async (input) => {
    const source = input.value.trim();
    if (!source) return;
    try {
      await lvglPreviewImport(lvglImportSourcePayload(source));
    } catch (err) {
      lvglClearImportPreview();
      toast(err.message || "Failed to preview GUI import");
    }
  });
  bindPathBrowseButton("#lvglBtnBrowseSaveFilePath", "#lvglSaveFilePath", {
    dialogKind: "save-file",
    title: "Save LVGL layout",
    defaultExtension: ".json",
    fileTypes: [
      { name: "JSON files", patterns: ["*.json"] },
      { name: "LVGL layout files", patterns: ["*.lvgl.json", "*.lvgl"] },
      { name: "All files", patterns: ["*.*"] },
    ],
  });

  $("#lvglBtnSaveGui")?.addEventListener("click", () => {
    $("#lvglSaveFilePath").value = $("#lvglSaveFilePath").value || "ui_layout.lvgl.json";
    $("#lvglSaveModal")?.classList.add("show");
  });
  $("#lvglBtnCancelSaveGui")?.addEventListener("click", () => {
    $("#lvglSaveModal")?.classList.remove("show");
  });
  $("#lvglSaveModal")?.addEventListener("click", (e) => {
    if (e.target === e.currentTarget) {
      $("#lvglSaveModal").classList.remove("show");
    }
  });
  $("#lvglBtnConfirmSaveGui")?.addEventListener("click", async () => {
    const path = $("#lvglSaveFilePath")?.value.trim();
    if (!path) {
      toast("Enter a destination path for the GUI file");
      return;
    }
    await lvglSaveLayoutFile(path);
    $("#lvglSaveModal")?.classList.remove("show");
  });

  // ── Zoom controls ─────────────────────────────────────────────────
  $("#zoomIn").addEventListener("click", zoomIn);
  $("#zoomOut").addEventListener("click", zoomOut);
  $("#zoomReset").addEventListener("click", zoomReset);
  $("#zoomFit").addEventListener("click", zoomFit);
  pinSummaryExportBtn?.addEventListener("click", exportPinSummary);
  ensureChipAreaFitObserver();
  ensurePinSummaryOverlayInteractions();
  ensureSidePanelInteractions();
  wireGeneratedFilesOverviewControls();

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
      requestGenerateOutput();
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
    tab.addEventListener("click", async () => {
      await openAppTab(tab.dataset.appTab);
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
let pkgGeneratedArtifacts = [];

function pkgResultIsUsable(result) {
  return !!(result && (
    (Array.isArray(result.packages) && result.packages.length > 0) ||
    !!result.device
  ));
}

function pkgEmptyStateMarkup() {
  return `<div class="pkg-empty">
    <div class="icon">&#128230;</div>
    <div>MCU Package Generator</div>
    <div class="hint">Upload an MCU datasheet PDF here to generate board, overlay,<br>
      KiCad footprint, and 3D model artifacts for parsed MCU packages.</div>
    <div class="hint" data-pkg-ui-version="20260531zc">MCU-only Package Manager workflow active.</div>
  </div>`;
}

function pkgJobKind(job) {
  return "mcu";
}

function pkgJobPackages(job) {
  const result = job?.result || {};
  if (Array.isArray(result.packages)) return result.packages;
  return [];
}

function pkgJobTitle(job) {
  const result = job?.result || {};
  return result.device?.soc || job?.filename || "MCU";
}

function pkgJobSearchText(job) {
  const result = job?.result || {};
  const packages = pkgJobPackages(job).map(pkg => pkg?.name || "").join(" ");
  return `${job?.filename || ""} ${result.device?.soc || ""} ${packages}`.toLowerCase();
}

function pkgMergeJobs(incomingJobs) {
  const merged = new Map(pkgJobs.map(job => [job.job_id, job]));
  (Array.isArray(incomingJobs) ? incomingJobs : []).forEach(job => {
    if (job?.job_id && pkgJobKind(job) === "mcu" && pkgResultIsUsable(job?.result)) {
      merged.set(job.job_id, job);
    }
  });
  pkgJobs = [...merged.values()];
  if (pkgSelectedJob && !pkgJobs.some(job => job.job_id === pkgSelectedJob)) {
    pkgSelectedJob = pkgJobs.length ? pkgJobs[0].job_id : null;
  }
}

// ── LocalStorage persistence helpers ─────────────────────────────────

function pkgSaveToStorage() {
  try {
    const data = pkgJobs.map(j => ({
      job_id: j.job_id,
      kind: j.kind,
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
        pkgJobs = data.filter(job => pkgJobKind(job) === "mcu" && pkgResultIsUsable(job?.result));
        pkgSelectedJob = localStorage.getItem("zpincfg_pkg_selected") || null;
        if (pkgSelectedJob && !pkgJobs.some(job => job.job_id === pkgSelectedJob)) {
          pkgSelectedJob = pkgJobs.length ? pkgJobs[0].job_id : null;
        }
        if (pkgJobs.length !== data.length) {
          pkgSaveToStorage();
        }
        if (!pkgJobs.length) {
          return false;
        }
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
  pkgGeneratedArtifacts = [];
  pkgSaveToStorage();
  pkgRenderJobList();
  if (pkgSelectedJob) pkgSelectJob(pkgSelectedJob);
  else $("#pkgMain").innerHTML = pkgEmptyStateMarkup();
}

async function pkgLoadServerJobs() {
  const incoming = [];
  let loadedFromServer = false;

  try {
    const res = await fetch("/api/parse-jobs");
    const jobs = await res.json();
    if (res.ok && Array.isArray(jobs)) {
      loadedFromServer = true;
      jobs.forEach(job => {
        if (job?.result) incoming.push({
          job_id: job.job_id,
          kind: job.kind || "mcu",
          filename: job.filename,
          result: job.result,
        });
      });
    }
  } catch (_err) {
    // Keep local MCU jobs if the live endpoint is unavailable.
  }

  if (loadedFromServer) {
    pkgJobs = incoming.filter(job => pkgJobKind(job) === "mcu" && pkgResultIsUsable(job?.result));
    if (pkgSelectedJob && !pkgJobs.some(job => job.job_id === pkgSelectedJob)) {
      pkgSelectedJob = pkgJobs.length ? pkgJobs[0].job_id : null;
    }
    pkgSaveToStorage();
    pkgRenderJobList();
    if (pkgSelectedJob) {
      pkgRenderDetail();
    } else {
      $("#pkgMain").innerHTML = pkgEmptyStateMarkup();
    }
    return;
  }

  if (incoming.length) {
    pkgMergeJobs(incoming);
    pkgSaveToStorage();
    pkgRenderJobList();
    if (pkgSelectedJob) {
      pkgRenderDetail();
    }
  }
}

function pkgInit() {
  const uploadArea = $("#pdfUploadArea");
  const fileInput  = $("#pdfFileInput");
  const jobSearch = $("#pkgJobSearch");

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
  } else {
    $("#pkgMain").innerHTML = pkgEmptyStateMarkup();
  }

  void pkgLoadServerJobs();

  jobSearch?.addEventListener("input", () => {
    pkgRenderJobList();
  });
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
    pkgMergeJobs([{
      job_id: data.job_id,
      kind: "mcu",
      filename: data.filename,
      result: data.result,
    }]);
    pkgGeneratedArtifacts = [];

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
  const filter = resolveThresholdSearch("pkgJobSearch", pkgJobs.length);

  if (pkgJobs.length === 0) {
    list.innerHTML = `<div class="empty-state" style="padding:20px;">
      <div>No datasheets parsed yet</div>
      <div class="hint">Upload a PDF above</div>
    </div>`;
    return;
  }

  const filteredJobs = pkgJobs.filter((job) => {
    return !filter || pkgJobSearchText(job).includes(filter);
  });

  if (!filteredJobs.length) {
    list.innerHTML = `<div class="empty-state" style="padding:20px;">
      <div>No parsed datasheets match the current search</div>
      <div class="hint">Try another filename, SoC, or package name</div>
    </div>`;
    return;
  }

  list.innerHTML = filteredJobs.map(job => {
    const r = job.result;
    const isSelected = pkgSelectedJob === job.job_id;
    const packages = pkgJobPackages(job);
    const pkgNames = packages.map(p => p.name).filter(Boolean).join(", ") || "No packages";
    const kind = pkgJobKind(job);
    const title = kind === "sensor" ? (r.summary?.part_number || job.filename) : (r.device?.soc || job.filename);
    const meta = kind === "sensor"
      ? `${r.summary?.sensor_type || "sensor"} · ${r.register_map?.register_count || 0} registers · ${r.address?.protocol || "unknown bus"}`
      : `${packages.length} package(s): ${pkgNames} · ${r.pin_mux_count || 0} pins, ${r.pin_mux_total_funcs || 0} alt-funcs`;
    return `
      <div class="pkg-job-item ${isSelected ? 'selected' : ''}"
           data-job-id="${job.job_id}">
        <button class="job-remove-btn" data-remove-id="${job.job_id}" title="Remove">&times;</button>
        <div class="job-filename">
          ${job.filename}
          <span class="soc-badge">${kind === "sensor" ? "SENSOR" : "MCU"}</span>
          ${title && title !== job.filename ? `<span class="soc-badge">${title}</span>` : ''}
        </div>
        <div class="job-meta">
          ${meta}
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
  pkgGeneratedArtifacts = [];
  pkgSaveToStorage();
  pkgRenderJobList();
  pkgRenderDetail();
}


function pkgRenderDetail() {
  const main = $("#pkgMain");
  const job = pkgJobs.find(j => j.job_id === pkgSelectedJob);

  if (!job) {
    main.innerHTML = pkgEmptyStateMarkup();
    return;
  }

  const r = job.result;
  const kind = pkgJobKind(job);
  const packages = pkgJobPackages(job);
  const device = r.device || {};
  const summary = r.summary || {};
  const address = r.address || {};
  const registerMap = r.register_map || {};

  // Select all packages by default
  if (pkgSelectedPkgs.size === 0 && packages.length) {
    packages.forEach(pkg => {
      if (pkg?.name) pkgSelectedPkgs.add(pkg.name);
    });
  }

  const canGenerate = kind === "sensor" ? true : pkgSelectedPkgs.size > 0;
  const title = kind === "sensor" ? (summary.part_number || job.filename) : (device.soc || job.filename);
  const headerSpecs = kind === "sensor"
    ? `
      <span>&#128204; Vendor: ${summary.vendor_name || summary.vendor || "?"}</span>
      <span>&#129514; Type: ${summary.sensor_type || "?"}</span>
      <span>&#128421; Bus: ${address.protocol || "?"}</span>
      <span>&#128209; Registers: ${registerMap.register_count || 0}</span>
    `
    : `
      <span>&#128190; Flash: ${device.flash_size_kb ? device.flash_size_kb + ' KB' : '?'}</span>
      <span>&#128200; SRAM: ${device.sram_size_kb ? device.sram_size_kb + ' KB' : '?'}</span>
      <span>&#9201; Clock: ${device.clock_hz ? (device.clock_hz / 1e6).toFixed(0) + ' MHz' : '?'}</span>
      <span>&#128204; Vendor: ${device.vendor || '?'}</span>
    `;

  const packageCards = packages.length ? `
    <div class="pkg-section">
      <h3>Packages Found (${packages.length})</h3>
      <div class="pkg-card-grid">
        ${packages.map(pkg => {
          const sel = pkg.name ? pkgSelectedPkgs.has(pkg.name) : false;
          const pins = Array.isArray(pkg.pins) ? pkg.pins : [];
          const ioPins = pins.filter(p => p.kind === 'io').length;
          const pwrPins = pins.filter(p => p.kind === 'power' || p.kind === 'ground').length;
          const specPins = pins.filter(p => p.kind === 'special').length;
          return `
            <div class="pkg-card ${sel ? 'selected' : ''}" data-pkg="${pkg.name || ''}">
              <div class="pkg-card-check">${sel ? '&#10003;' : ''}</div>
              <div class="pkg-card-name">${pkg.name || 'Package Override'}</div>
              <div class="pkg-card-meta">
                ${(pkg.pin_count || pins.length || 0)} pins &middot;
                ${ioPins} I/O, ${pwrPins} pwr/gnd, ${specPins} special
              </div>
            </div>`;
        }).join("")}
      </div>
    </div>`
    : `
    <div class="pkg-section">
      <h3>Packages</h3>
      <div class="empty-state">No package geometry was parsed. Use the geometry overrides below to generate CAD output.</div>
    </div>`;

  const previewSection = kind === "sensor"
    ? `
      <div class="pkg-section">
        <h3>Register Preview (${registerMap.register_count || 0} registers)</h3>
        ${Array.isArray(registerMap.registers) && registerMap.registers.length ? `
          <table class="mux-table">
            <thead>
              <tr>
                <th>Address</th>
                <th>Name</th>
                <th>Access</th>
                <th>Reset</th>
              </tr>
            </thead>
            <tbody>
              ${registerMap.registers.slice(0, 8).map(reg => `
                <tr>
                  <td>${reg.address || `0x${Number(reg.address_int || 0).toString(16).toUpperCase()}`}</td>
                  <td>${reg.name || ''}</td>
                  <td>${reg.access || ''}</td>
                  <td>${reg.reset_value || ''}</td>
                </tr>`).join("")}
            </tbody>
          </table>
          ${registerMap.registers.length > 8 ? `<div style="font-size:11px;color:var(--fg-dim);margin-top:6px;">Showing first 8 registers of ${registerMap.registers.length}</div>` : ''}
        ` : '<div class="empty-state">No register-map data extracted</div>'}
      </div>`
    : `
      <div class="pkg-section">
        <h3>Pin-Mux Preview (${r.pin_mux_count || 0} pins, ${r.pin_mux_total_funcs || 0} functions)</h3>
        ${Object.keys(r.pin_mux_sample || {}).length > 0 ? `
          <table class="mux-table">
            <thead>
              <tr>
                <th>Pin</th>
                <th>Peripheral</th>
                <th>Signal</th>
                <th>Dir</th>
              </tr>
            </thead>
            <tbody>
              ${Object.entries(r.pin_mux_sample).map(([pin, funcs]) =>
                funcs.map((f, i) => `
                  <tr>
                    ${i === 0 ? `<td rowspan="${funcs.length}" style="font-weight:600;">${pin}</td>` : ''}
                    <td>${f.peripheral}</td>
                    <td>${f.signal}</td>
                    <td style="color:var(--fg-dim);">${f.direction}</td>
                  </tr>`)
              ).join("")}
            </tbody>
          </table>
          ${r.pin_mux_count > 5 ? `<div style="font-size:11px;color:var(--fg-dim);margin-top:6px;">Showing first 5 pins of ${r.pin_mux_count}</div>` : ''}
        ` : '<div class="empty-state">No pin-mux data extracted</div>'}
      </div>`;

  const geometrySource = packages[0] || {};

  let html = `
    <div class="pkg-detail-header">
      <h2>${title}</h2>
      <div class="device-specs">
        ${headerSpecs}
      </div>
    </div>

    <div class="pkg-detail-body">
      ${packageCards}
      ${previewSection}

      <div class="pkg-section">
        <h3>Generation Options</h3>
        <div class="pkg-overrides">
          ${kind === "sensor" ? `
            <label>Driver Name</label>
            <input id="pkgDriverName" placeholder="${(summary.part_number || 'sensor').toLowerCase().replace(/[^a-z0-9]+/g, '_')}" value="">
            <label>Compatible</label>
            <input id="pkgCompatible" placeholder="${summary.vendor || 'vendor'},${(summary.part_number || 'sensor').toLowerCase()}" value="">
            <label>Bus</label>
            <input id="pkgBus" placeholder="${address.protocol || 'i2c'}" value="">
            <label>Custom Template Path</label>
            <input id="pkgCustomTemplatePath" placeholder="custom/${(summary.part_number || 'sensor').toLowerCase()}.txt" value="">
            <label>Custom Template</label>
            <textarea id="pkgCustomTemplate" placeholder="Optional custom template with [[driver_name]] style tokens"></textarea>
          ` : `
            <label>Board Name</label>
            <input id="pkgBoardName" placeholder="lp_${(device.soc || 'custom').toLowerCase()}" value="">
            <label>DTS SOC Include</label>
            <input id="pkgDtsSoc" placeholder="auto-detect" value="">
            <label>DTS Pinctrl Include</label>
            <input id="pkgDtsPinctrl" placeholder="auto-detect" value="">
            <label>Pinctrl Header</label>
            <input id="pkgPinctrlHeader" placeholder="mspm0-pinctrl.h" value="">
            <label>External Devices</label>
            <textarea id="pkgExternalDevices" placeholder='[\n  {\n    "id": "eeprom_24lc32",\n    "display": "24LC32 EEPROM",\n    "category": "memory",\n    "bus": "i2c0",\n    "compatible": "microchip,24lc32",\n    "address": "0x50",\n    "required_signals": ["scl", "sda"],\n    "frameworks": ["zephyr", "arduino"]\n  }\n]'></textarea>
          `}
          <label>Package Name Override</label>
          <input id="pkgPackageName" placeholder="${geometrySource.name || 'auto-detect'}" value="">
          <label>Package Type Override</label>
          <input id="pkgPackageType" placeholder="${geometrySource.package_type || geometrySource.name || 'QFN'}" value="">
          <label>Package Width (mm)</label>
          <input id="pkgWidthMm" type="number" step="0.01" placeholder="${geometrySource.width_mm || ''}" value="">
          <label>Package Height (mm)</label>
          <input id="pkgHeightMm" type="number" step="0.01" placeholder="${geometrySource.height_mm || ''}" value="">
          <label>Pin Pitch (mm)</label>
          <input id="pkgPitchMm" type="number" step="0.01" placeholder="${geometrySource.pitch_mm || ''}" value="">
          <label>Package Thickness (mm)</label>
          <input id="pkgThicknessMm" type="number" step="0.01" placeholder="1.0" value="">
        </div>
      </div>

      <div class="pkg-section">
        <h3>Generated Artifact Bundle</h3>
        ${codeReviewPanelMarkup("pkgGeneratedReview", "Generate package output to review the driver, board, footprint, and 3D files here.")}
      </div>
    </div>

    <div class="pkg-actions">
      <span class="pkg-status" id="pkgStatus">${kind === "sensor" ? "Generate a sensor artifact bundle" : `${pkgSelectedPkgs.size} of ${packages.length} package(s) selected`}</span>
      <span class="spacer"></span>
      <button class="btn" id="pkgBtnSelectAll" ${packages.length ? '' : 'disabled'}>Select All</button>
      <button class="btn btn-accent" id="pkgBtnGenerate" ${canGenerate ? '' : 'disabled'}>
        ${kind === "sensor" ? 'Generate Driver + CAD Bundle' : `Generate ${pkgSelectedPkgs.size} Artifact Bundle(s)`}
      </button>
    </div>
  `;

  main.innerHTML = html;
  renderCodeReviewPanel("pkgGeneratedReview", pkgGeneratedArtifacts, {
    emptyMessage: "Generate package output to review the driver, board, footprint, and 3D files here.",
    preferredSelection: pkgGeneratedArtifacts[0]?.id,
  });

  // Wire up package card toggles
  main.querySelectorAll(".pkg-card").forEach(card => {
    card.addEventListener("click", () => {
      const name = card.dataset.pkg;
      if (!name) return;
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
      packages.forEach(p => p?.name && pkgSelectedPkgs.add(p.name));
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
  const kind = pkgJobKind(job);

  const statusEl = $("#pkgStatus");
  const btnGen = $("#pkgBtnGenerate");

  if (btnGen) {
    btnGen.disabled = true;
    btnGen.innerHTML = '<span class="spinner" style="width:12px;height:12px;border-width:1.5px;"></span> Generating...';
  }
  if (statusEl) statusEl.textContent = "Generating artifact bundle...";

  let externalDevices;
  const externalDevicesRaw = $("#pkgExternalDevices")?.value.trim() || "";
  if (kind === "mcu" && externalDevicesRaw) {
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

  const packageOverrides = {
    package_name: $("#pkgPackageName")?.value.trim() || undefined,
    package_type: $("#pkgPackageType")?.value.trim() || undefined,
    width_mm: $("#pkgWidthMm")?.value.trim() || undefined,
    height_mm: $("#pkgHeightMm")?.value.trim() || undefined,
    pitch_mm: $("#pkgPitchMm")?.value.trim() || undefined,
    thickness_mm: $("#pkgThicknessMm")?.value.trim() || undefined,
  };
  Object.keys(packageOverrides).forEach(k => packageOverrides[k] === undefined && delete packageOverrides[k]);

  const body = {
    job_id: job.job_id,
    packages: [...pkgSelectedPkgs],
    board_name: $("#pkgBoardName")?.value.trim() || undefined,
    dts_soc_include: $("#pkgDtsSoc")?.value.trim() || undefined,
    dts_pinctrl_include: $("#pkgDtsPinctrl")?.value.trim() || undefined,
    pinctrl_header: $("#pkgPinctrlHeader")?.value.trim() || undefined,
    external_devices: externalDevices,
    register: true,
    driver_name: $("#pkgDriverName")?.value.trim() || undefined,
    compatible: $("#pkgCompatible")?.value.trim() || undefined,
    bus: $("#pkgBus")?.value.trim() || undefined,
    custom_template_path: $("#pkgCustomTemplatePath")?.value.trim() || undefined,
    custom_template: $("#pkgCustomTemplate")?.value || undefined,
    package_overrides: Object.keys(packageOverrides).length ? packageOverrides : undefined,
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
      pkgGeneratedArtifacts = Array.isArray(data.artifacts) ? data.artifacts : [];
      renderCodeReviewPanel("pkgGeneratedReview", pkgGeneratedArtifacts, {
        emptyMessage: "Generate package output to review the driver, board, footprint, and 3D files here.",
        preferredSelection: pkgGeneratedArtifacts[0]?.id,
      });
      const summary = names || `${pkgGeneratedArtifacts.length} generated artifact(s)`;
      toast(`Generated: ${summary}`);
      if (statusEl) statusEl.textContent = `✓ Generated: ${summary}`;

      // Reload existing packages list
      if (kind === "mcu") {
        pkgLoadExisting();

        // Reload board list in the Pin Configurator tab
        loadBoardList();
      }
    }
  } catch (err) {
    toast(`Failed: ${err.message}`);
    if (statusEl) statusEl.textContent = `Failed: ${err.message}`;
  }

  if (btnGen) {
    btnGen.disabled = false;
    btnGen.innerHTML = kind === "sensor"
      ? "Generate Driver + CAD Bundle"
      : `Generate ${pkgSelectedPkgs.size} Artifact Bundle(s)`;
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
      const label = pkg ? `${soc} - ${pkg}` : soc;

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
          activateAppTab("configurator");
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
      search.addEventListener("input", () => modRenderSidebar());
    }
    interruptRefreshIfVisible();
  } catch (err) {
    console.error("Failed to load modules", err);
  }
}

function modRenderSidebar(filter = "") {
  const list = document.getElementById("modModuleList");
  if (!list) return;
  filter = resolveThresholdSearch("modSearch", modModules.length, filter);

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
      interruptRefreshIfVisible();
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
    </div>
    <div class="modcfg-output" id="modOutput" style="display:none">
      ${codeReviewPanelMarkup("modGeneratedReview", "Generate module fragments to review them here.")}
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
      interruptRefreshIfVisible();
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
  const fullOverlay = document.getElementById("modFullOverlay")?.checked;

  // Build multi-module payload
  const modulesPayload = {};
  for (const [id, en] of Object.entries(modEnabled)) {
    if (en) modulesPayload[id] = modValuesMap[id] || {};
  }

  if (Object.keys(modulesPayload).length === 0) {
    if (outEl) outEl.style.display = "";
    renderCodeReviewPanel("modGeneratedReview", [], {
      emptyMessage: "No modules enabled. Check the boxes next to modules in the sidebar.",
    });
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

    generatedFragments.modules.prj_conf = data.prj_conf || "";
    outEl.style.display = "";
    renderCodeReviewPanel("modGeneratedReview", [
      {
        id: "prj_conf",
        label: "prj.conf",
        path: "modules/prj.conf",
        group: "Module Configurator",
        content: data.prj_conf || "",
      },
      {
        id: "full_overlay_conf",
        label: "full_overlay.conf",
        path: "modules/full_overlay.conf",
        group: "Module Configurator",
        content: data.overlay_conf || "",
      },
    ], {
      emptyMessage: "Generate module fragments to review them here.",
      preferredSelection: fullOverlay ? "full_overlay_conf" : "prj_conf",
    });
    refreshGeneratedOutputs();
  } catch (err) {
    outEl.style.display = "";
    renderCodeReviewPanel("modGeneratedReview", [{
      id: "error",
      label: "error.txt",
      path: "modules/error.txt",
      group: "Module Configurator",
      content: `ERROR: ${err.message}`,
    }], {
      preferredSelection: "error",
    });
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
    search.addEventListener("input", () => pcfgRenderSidebar());
  }

  const clkSearch = document.getElementById("clkSearch");
  if (clkSearch) {
    clkSearch.addEventListener("input", () => clkRenderSidebar());
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
    interruptRefreshIfVisible();
  } catch (err) {
    console.error("Failed to load peripheral instances", err);
  }
}

function pcfgRenderSidebar(filter = "") {
  const list = document.getElementById("pcfgInstanceList");
  if (!list) return;
  filter = resolveThresholdSearch("pcfgSearch", pcfgInstances.length, filter);

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
      <button class="btn btn-accent" id="pcfgGenerateBtn">Generate Config</button>
    </div>
    <div class="pcfg-output" id="pcfgOutput" style="display:none">
      ${codeReviewPanelMarkup("pcfgOutputReview", "Generate peripheral output to review it here.")}
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
  });

  // Generate button
  document.getElementById("pcfgGenerateBtn").addEventListener("click", () => pcfgGenerate());
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
      interruptRefreshIfVisible();
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
    outEl.style.display = "";
    renderCodeReviewPanel("pcfgOutputReview", [], {
      emptyMessage: "No peripheral configuration changes to generate.",
    });
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

    generatedFragments.peripherals.overlay = data.overlay || "";
    generatedFragments.peripherals.prj_conf = data.prj_conf || "";
    outEl.style.display = "";
    renderCodeReviewPanel("pcfgOutputReview", [
      {
        id: "overlay",
        label: ".overlay",
        path: "peripherals/peripherals.overlay",
        group: "Peripheral Configurator",
        content: data.overlay || "",
      },
      {
        id: "prjconf",
        label: "prj.conf",
        path: "peripherals/prj.conf",
        group: "Peripheral Configurator",
        content: data.prj_conf || "",
      },
    ], {
      emptyMessage: "Generate peripheral output to review it here.",
      preferredSelection: pcfgOutputTab,
      onSelect: (file) => {
        pcfgOutputTab = file.id;
      },
    });
    refreshGeneratedOutputs();
    toast("Peripheral config generated");
  } catch (err) {
    outEl.style.display = "";
    renderCodeReviewPanel("pcfgOutputReview", [{
      id: "error",
      label: "error.txt",
      path: "peripherals/error.txt",
      group: "Peripheral Configurator",
      content: `ERROR: ${err.message}`,
    }], {
      preferredSelection: "error",
    });
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
let clkWarnings = [];       // validation / clamp warnings for current values
let clkOutputTab = "overlay";
let clkTreesLoaded = false;
let clkViewMode = "all";

function clkNormalizeToken(value) {
  return String(value || "").toLowerCase().replace(/[^a-z0-9]+/g, "");
}

function clkScoreTreeForBoard(tree, board) {
  if (!tree || !board) return 0;
  const soc = clkNormalizeToken(board.soc);
  if (!soc) return 0;
  const keys = [tree.id, tree.soc, tree.name].map(clkNormalizeToken).filter(Boolean);
  if (keys.includes(soc)) return 100;
  if (keys.some(key => key.includes(soc) || soc.includes(key))) return 80;
  if (soc.includes("stm32") && tree.id === "stm32_generic") return 60;
  if ((soc.includes("nrf52") || soc.includes("nrf528")) && tree.id === "nrf52") return 60;
  if (soc.includes("mspm0") && tree.id === "mspm0g3507") return 60;
  return 0;
}

function clkBestTreeForBoard(board) {
  if (!Array.isArray(clkTrees) || !clkTrees.length || !board) return null;
  let best = null;
  let bestScore = 0;
  clkTrees.forEach(tree => {
    const score = clkScoreTreeForBoard(tree, board);
    if (score > bestScore) {
      best = tree;
      bestScore = score;
    }
  });
  return best;
}

function clkBoardContext() {
  if (boardData) return boardData;
  if (!boardSelect || !boardSelect.value) return null;
  const selected = boardSelect.selectedOptions && boardSelect.selectedOptions[0];
  return {
    soc: boardSelect.value,
    board: boardSelect.value,
    name: selected ? selected.textContent : boardSelect.value,
    package: selected ? selected.textContent : "",
  };
}

async function clkAutoSelectTreeForBoard() {
  const board = clkBoardContext();
  if (!board) return;
  if (!clkTreesLoaded) {
    await clkLoadTrees();
  }
  const best = clkBestTreeForBoard(board);
  if (!best) return;

  const sel = $("#clkTreeSelect");
  if (sel && sel.value !== best.id) {
    sel.value = best.id;
  }
  if (!clkCurrentTree || clkCurrentTree.id !== best.id) {
    await clkLoadTree(best.id);
  }
}

function clkInit() {
  const sel = $("#clkTreeSelect");
  if (sel) {
    sel.addEventListener("change", () => {
      const id = sel.value;
      if (id) clkLoadTree(id);
    });
  }

  const allBtn = $("#clkAllSettingsBtn");
  if (allBtn) {
    allBtn.addEventListener("click", () => clkShowAllSettings());
  }

  setTimeout(() => {
    clkLoadTrees().catch(err => {
      console.error("Failed to initialize clock trees:", err);
    });
  }, 0);
}

function clkSortedNodes() {
  if (!clkCurrentTree) return [];
  const typeOrder = ["source", "pll", "mux", "divider", "output"];
  return [...clkCurrentTree.nodes].sort((a, b) => {
    const left = typeOrder.indexOf(a.type);
    const right = typeOrder.indexOf(b.type);
    if (left !== right) return left - right;
    return a.name.localeCompare(b.name);
  });
}

function clkSyncModeButton() {
  const allBtn = $("#clkAllSettingsBtn");
  if (!allBtn) return;
  allBtn.classList.toggle("active", clkViewMode === "all");
}

function clkShowAllSettings() {
  if (!clkCurrentTree) return;
  clkViewMode = "all";
  clkSelectedNode = null;
  clkRenderSidebar();
  clkRenderBody();
}

async function clkLoadTrees() {
  if (clkTreesLoaded) {
    await clkAutoSelectTreeForBoard();
    const sel = $("#clkTreeSelect");
    const fallbackId = sel && sel.value ? sel.value : "";
    if ((!clkCurrentTree || !clkCurrentTree.id) && fallbackId) {
      await clkLoadTree(fallbackId);
    }
    return;
  }
  try {
    const res = await fetch("/api/clock-trees");
    clkTrees = await res.json();
    const sel = $("#clkTreeSelect");
    sel.innerHTML = '<option value="">- Select clock tree -</option>';
    clkTrees.forEach(t => {
      const opt = document.createElement("option");
      opt.value = t.id;
      opt.textContent = `${t.name} (${t.node_count} nodes)`;
      sel.appendChild(opt);
    });
    clkTreesLoaded = true;
    await clkAutoSelectTreeForBoard();
    const fallbackId = sel.value || (clkTrees[0] && clkTrees[0].id) || "";
    if ((!clkCurrentTree || !clkCurrentTree.id) && fallbackId) {
      if (sel.value !== fallbackId) {
        sel.value = fallbackId;
      }
      await clkLoadTree(fallbackId);
    }
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
    clkViewMode = "all";
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
    clkRenderBody();
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
    clkWarnings = Array.isArray(data.warnings) ? data.warnings : [];
  } catch (err) {
    console.error("Failed to compute frequencies:", err);
    clkWarnings = [];
  }
}

function clkFormatFreq(hz) {
  if (!hz || hz <= 0) return "OFF";
  if (hz >= 1_000_000) return `${(hz / 1_000_000).toFixed(2)} MHz`;
  if (hz >= 1_000) return `${(hz / 1_000).toFixed(2)} kHz`;
  return `${hz} Hz`;
}

function clkNodeBadge(node) {
  switch (node?.type) {
    case "source":
      return "SRC";
    case "pll":
      return "PLL";
    case "mux":
      return "MUX";
    case "divider":
      return "DIV";
    case "output":
      return "OUT";
    default:
      return "CLK";
  }
}

function clkRenderSidebar() {
  const list = $("#clkNodeList");
  if (!list || !clkCurrentTree) return;

  const sorted = clkSortedNodes();
  const filter = resolveThresholdSearch("clkSearch", sorted.length);
  const filtered = sorted.filter((node) => {
    if (!filter) return true;
    const haystack = `${node.id} ${node.name} ${node.type}`.toLowerCase();
    return haystack.includes(filter);
  });
  clkSyncModeButton();

  list.innerHTML = "";
  for (const node of filtered) {
    const item = document.createElement("div");
    item.className = "clkcfg-node-item" + (clkViewMode === "node" && node.id === clkSelectedNode ? " active" : "");
    const freq = clkFreqs[node.id] || 0;
    item.innerHTML = `
      <span class="node-icon">${clkNodeBadge(node)}</span>
      <span class="node-name">${node.name}</span>
      <span class="node-type t-${node.type}">${node.type}</span>
      <span class="node-freq">${clkFormatFreq(freq)}</span>
    `;
    item.addEventListener("click", () => clkSelectNode(node.id));
    list.appendChild(item);
  }

  if (!filtered.length) {
    list.innerHTML = '<div class="empty-state" style="padding:20px;font-size:12px;color:var(--fg-dim)">No clock nodes match the current search.</div>';
  }
}

function clkSelectNode(nodeId) {
  clkSelectedNode = nodeId;
  clkViewMode = "node";
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

function clkBuildPropertyRows(props) {
  let html = "";
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
  return html;
}

function clkBuildWarningsGroup() {
  if (!clkWarnings.length) return "";
  let html = `<div class="cfg-group"><div class="cfg-group-header" style="cursor:default;">
    <span class="toggle">⚠</span> Warnings
  </div><div class="cfg-group-body" style="display:block;">`;
  html += `<div style="padding:8px 0 2px 0;">`;
  clkWarnings.forEach(warning => {
    html += `<div style="font-size:12px;color:var(--yellow);margin-bottom:6px;">- ${escapeHtml(warning)}</div>`;
  });
  html += `</div></div></div>`;
  return html;
}

function clkBuildActions() {
  return `
    <div class="clkcfg-actions">
      <button class="btn btn-accent" id="clkGenerateBtn" onclick="clkGenerate()">Generate Config</button>
      <span class="spacer"></span>
      <span style="font-size:12px;color:var(--fg-dim);">
        Max SoC freq: ${clkFormatFreq(clkCurrentTree.max_freq)}
      </span>
    </div>
    <div class="clkcfg-output" id="clkOutput" style="display:none;">
      ${codeReviewPanelMarkup("clkOutputReview", "Generate clock output to review it here.")}
    </div>
  `;
}

function clkBindConfigInputs(main) {
  main.querySelectorAll("[data-clk-key]").forEach(el => {
    const key = el.dataset.clkKey;
    const evName = (el.type === "checkbox") ? "change" : "input";
    el.addEventListener(evName, async () => {
      if (el.type === "checkbox") {
        clkValues[key] = el.checked;
        const span = el.closest("label")?.querySelector("span:last-child");
        if (span) span.textContent = el.checked ? "Enabled" : "Disabled";
      } else if (el.type === "number") {
        clkValues[key] = parseInt(el.value) || 0;
      } else {
        const num = Number(el.value);
        clkValues[key] = isNaN(num) ? el.value : num;
      }
      await clkComputeFreqs();
      clkRenderSidebar();
      clkRenderBody();
    });
  });
}

function clkBindFocusButtons(main) {
  main.querySelectorAll("[data-clk-focus-node]").forEach(btn => {
    btn.addEventListener("click", () => {
      const nodeId = btn.dataset.clkFocusNode;
      if (nodeId) clkSelectNode(nodeId);
    });
  });
  main.querySelectorAll("[data-clk-node-card]").forEach(card => {
    card.addEventListener("click", () => {
      const nodeId = card.dataset.clkNodeCard;
      if (nodeId) clkSelectNode(nodeId);
    });
  });
}

function clkOverviewGraph() {
  const nodes = clkSortedNodes();
  const nodeMap = {};
  const incoming = {};
  const outgoing = {};
  nodes.forEach(node => {
    nodeMap[node.id] = node;
    incoming[node.id] = [];
    outgoing[node.id] = [];
  });

  (clkCurrentTree.connections || []).forEach(conn => {
    if (!nodeMap[conn.from] || !nodeMap[conn.to]) return;
    outgoing[conn.from].push(conn.to);
    incoming[conn.to].push(conn.from);
  });

  const indegree = {};
  nodes.forEach(node => {
    indegree[node.id] = incoming[node.id].length;
  });

  const queue = nodes.filter(node => indegree[node.id] === 0).map(node => node.id);
  const levels = {};
  queue.forEach(id => { levels[id] = 0; });

  while (queue.length) {
    const current = queue.shift();
    const currentLevel = levels[current] || 0;
    (outgoing[current] || []).forEach(nextId => {
      levels[nextId] = Math.max(levels[nextId] || 0, currentLevel + 1);
      indegree[nextId] -= 1;
      if (indegree[nextId] === 0) {
        queue.push(nextId);
      }
    });
  }

  nodes.forEach(node => {
    if (levels[node.id] === undefined) levels[node.id] = 0;
  });

  const columns = [];
  nodes.forEach(node => {
    const level = levels[node.id] || 0;
    if (!columns[level]) columns[level] = [];
    columns[level].push(node);
  });

  columns.forEach(column => {
    column.sort((left, right) => {
      const typeOrder = ["source", "pll", "mux", "divider", "output"];
      const l = typeOrder.indexOf(left.type);
      const r = typeOrder.indexOf(right.type);
      if (l !== r) return l - r;
      return left.name.localeCompare(right.name);
    });
  });

  return { columns, nodeMap, incoming, outgoing };
}

function clkBuildOverviewDiagram() {
  const { columns, nodeMap, incoming, outgoing } = clkOverviewGraph();
  const activeCount = clkSortedNodes().filter(node => (clkFreqs[node.id] || 0) > 0).length;
  let html = `<div class="cfg-group"><div class="cfg-group-header" style="cursor:default;">
    <span class="toggle">🕸</span> Clock Overview
  </div><div class="cfg-group-body" style="display:block;">`;

  html += `<div class="clkcfg-overview-shell" style="--clkcfg-overview-column-count:${Math.max(1, columns.length)}; --clkcfg-overview-gap:18px;">
    <div class="clkcfg-overview-canvas" id="clkOverviewCanvas">
      <svg class="clkcfg-overview-wires" aria-hidden="true"></svg>
      <div class="clkcfg-overview-columns">`;

  columns.forEach((column, index) => {
    html += `<div class="clkcfg-overview-column">
      <div class="clkcfg-overview-column-label">Stage ${index + 1}</div>`;
    column.forEach(node => {
      const freq = clkFreqs[node.id] || 0;
      const upstream = (incoming[node.id] || []).map(id => nodeMap[id]?.name).filter(Boolean).slice(0, 2);
      const downstream = (outgoing[node.id] || []).map(id => nodeMap[id]?.name).filter(Boolean).slice(0, 2);
      const propCount = (node.props || []).length;
      html += `
        <div class="clkcfg-overview-node" data-clk-diagram-node="${node.id}" data-clk-node-card="${node.id}">
          <div class="clkcfg-overview-top">
            <span class="clkcfg-overview-icon">${clkNodeBadge(node)}</span>
            <span class="clkcfg-overview-name">${node.name}</span>
            <span class="clkcfg-overview-type t-${node.type}">${node.type}</span>
          </div>
          <div class="clkcfg-overview-freq">${clkFormatFreq(freq)}</div>
          <div class="clkcfg-overview-copy">${escapeHtml(node.desc || "Clock node")}</div>
          <div class="clkcfg-overview-meta">
            <span>${propCount ? `${propCount} setting${propCount === 1 ? "" : "s"}` : "derived"}</span>
            ${upstream.length ? `<span>in: ${escapeHtml(upstream.join(", "))}</span>` : "<span>source</span>"}
            ${downstream.length ? `<span>out: ${escapeHtml(downstream.join(", "))}</span>` : "<span>sink</span>"}
          </div>
          <button class="clkcfg-overview-link" data-clk-focus-node="${node.id}">Edit Node</button>
        </div>
      `;
    });
    html += `</div>`;
  });

  html += `</div></div>
    <div class="clkcfg-overview-stats">
      <div class="clkcfg-overview-stat"><span>Active clocks</span><strong>${activeCount}</strong></div>
      <div class="clkcfg-overview-stat"><span>Total nodes</span><strong>${clkCurrentTree.nodes.length}</strong></div>
      <div class="clkcfg-overview-stat"><span>Configurable</span><strong>${clkCurrentTree.nodes.filter(node => (node.props || []).length).length}</strong></div>
      <div class="clkcfg-overview-stat"><span>Max SoC freq</span><strong>${clkFormatFreq(clkCurrentTree.max_freq)}</strong></div>
    </div>
  </div>`;

  html += `</div></div>`;
  return html;
}

function clkRenderOverviewWires(main) {
  const canvas = main.querySelector("#clkOverviewCanvas");
  const svg = canvas?.querySelector(".clkcfg-overview-wires");
  if (!canvas || !svg || !clkCurrentTree) return;

  const canvasRect = canvas.getBoundingClientRect();
  const width = Math.max(canvas.scrollWidth, canvasRect.width);
  const height = Math.max(canvas.scrollHeight, canvasRect.height);
  svg.setAttribute("viewBox", `0 0 ${width} ${height}`);
  svg.setAttribute("width", String(width));
  svg.setAttribute("height", String(height));

  let markup = `
    <defs>
      <marker id="clkArrowHead" markerWidth="10" markerHeight="10" refX="8" refY="5" orient="auto">
        <path d="M 0 0 L 10 5 L 0 10 z" fill="rgba(121, 162, 255, 0.9)"></path>
      </marker>
    </defs>
  `;

  (clkCurrentTree.connections || []).forEach(conn => {
    const fromEl = canvas.querySelector(`[data-clk-diagram-node="${conn.from}"]`);
    const toEl = canvas.querySelector(`[data-clk-diagram-node="${conn.to}"]`);
    if (!fromEl || !toEl) return;
    const fromRect = fromEl.getBoundingClientRect();
    const toRect = toEl.getBoundingClientRect();
    const x1 = fromRect.right - canvasRect.left;
    const y1 = fromRect.top - canvasRect.top + (fromRect.height / 2);
    const x2 = toRect.left - canvasRect.left;
    const y2 = toRect.top - canvasRect.top + (toRect.height / 2);
    const dx = Math.max(32, (x2 - x1) / 2);
    const path = `M ${x1} ${y1} C ${x1 + dx} ${y1}, ${x2 - dx} ${y2}, ${x2} ${y2}`;
    markup += `<path d="${path}" class="clkcfg-overview-wire"></path>`;
    markup += `<circle cx="${x1}" cy="${y1}" r="3" class="clkcfg-overview-junction"></circle>`;
  });

  svg.innerHTML = markup;
}

function clkBindOverviewResize(main) {
  const shell = main.querySelector(".clkcfg-overview-shell");
  if (!shell || typeof ResizeObserver !== "function") return;
  if (!clkOverviewResizeObserver) {
    clkOverviewResizeObserver = new ResizeObserver(() => {
      requestAnimationFrame(() => clkRenderOverviewWires(main));
    });
  }
  clkOverviewResizeObserver.disconnect();
  clkOverviewResizeObserver.observe(shell);
}

function clkRenderAllSettings(main) {
  const sorted = clkSortedNodes();
  const configurableNodes = sorted.filter(node => (node.props || []).length);
  let html = `
    <div class="clkcfg-header">
      <div class="clkcfg-title">
        <span>CLK</span>
        <span>${clkCurrentTree.name}</span>
        <span class="node-type t-mux" style="font-size:11px;padding:2px 8px;border-radius:6px;font-weight:600;text-transform:uppercase;">all settings</span>
      </div>
      <div class="clkcfg-desc">${clkCurrentTree.desc || "Configure all clock sources, PLLs, multiplexers, and outputs from one consolidated surface."}</div>
      <div class="clkcfg-freq-badge">${sorted.filter(node => (clkFreqs[node.id] || 0) > 0).length} active clocks</div>
    </div>
    <div class="clkcfg-body">
  `;

  html += clkBuildOverviewDiagram();

  html += clkBuildWarningsGroup();
  html = html.replace(/(<div class="clkcfg-title">\s*<span>)[^<]*(<\/span>)/, '$1CLK$2');

  configurableNodes.forEach(node => {
    html += `<div class="cfg-group"><div class="cfg-group-header" style="cursor:default;">
      <span class="toggle">${clkNodeBadge(node)}</span> ${node.name}
      <span class="group-count">${clkFormatFreq(clkFreqs[node.id] || 0)}</span>
    </div><div class="cfg-group-body" style="display:block;">`;
    html += `
      <div class="clkcfg-all-node-head">
        <div class="clkcfg-all-node-copy">
          <div class="clkcfg-all-node-title">
            <span>${clkNodeBadge(node)}</span>
            <span>${node.name}</span>
            <span class="node-type t-${node.type}" style="font-size:10px;padding:2px 6px;border-radius:4px;font-weight:600;text-transform:uppercase;">${node.type}</span>
          </div>
          <div class="clkcfg-all-node-meta">${escapeHtml(node.desc || "Clock node configuration")}</div>
        </div>
        <button class="clkcfg-link-btn" data-clk-focus-node="${node.id}">Node Detail</button>
      </div>
    `;
    html += clkBuildPropertyRows(node.props || []);
    html += `</div></div>`;
  });

  if (!configurableNodes.length) {
    html += `<div class="cfg-group"><div class="cfg-group-header" style="cursor:default;">
      <span class="toggle">ℹ</span> Info
    </div><div class="cfg-group-body" style="display:block;">
      <div style="padding:12px;color:var(--fg-dim);font-size:13px;">This clock tree has no editable properties.</div>
    </div></div>`;
  }

  html += `</div>`;
  html += clkBuildActions();
  main.innerHTML = html;
  clkBindConfigInputs(main);
  clkBindFocusButtons(main);
  clkBindOverviewResize(main);
  requestAnimationFrame(() => clkRenderOverviewWires(main));
}

function clkSanitizeAllSettingsTitle(main) {
  const title = main?.querySelector(".clkcfg-title span");
  if (title) {
    title.textContent = "CLK";
  }
}

function clkRenderBody() {
  const main = $("#clkMain");
  if (!main) return;
  if (!clkCurrentTree) { clkRenderEmpty(); return; }
  if (clkViewMode === "all" || !clkSelectedNode) {
    clkRenderAllSettings(main);
    clkSanitizeAllSettingsTitle(main);
    return;
  }

  const node = clkCurrentTree.nodes.find(n => n.id === clkSelectedNode);
  if (!node) { clkShowAllSettings(); return; }

  const freq = clkFreqs[node.id] || 0;
  const props = node.props || [];

  // ── Header ──
  let html = `
    <div class="clkcfg-header">
      <div class="clkcfg-title">
        <span>${clkNodeBadge(node)}</span>
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
      <span class="toggle">PATH</span> Clock Path
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
          <div class="tn-name">${un.name}</div>
          <div class="tn-freq">${clkFormatFreq(uf)}</div>
        </div>`;
      });
      html += `</div>`;
    }

    // Current node column
    html += `<div class="clkcfg-tree-column">
      <div class="clkcfg-tree-column-label">Current</div>
      <div class="clkcfg-tree-node active">
        <div class="tn-name">${node.name}</div>
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
          <div class="tn-name">${dn.name}</div>
          <div class="tn-freq">${clkFormatFreq(df)}</div>
        </div>`;
      });
      html += `</div>`;
    }

    html += `</div></div></div>`;
  }

  html += clkBuildWarningsGroup();

  if (props.length) {
    html += `<div class="cfg-group"><div class="cfg-group-header" style="cursor:default;">
      <span class="toggle">CFG</span> Configuration
    </div><div class="cfg-group-body" style="display:block;">`;
    html += clkBuildPropertyRows(props);

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
        <span class="toggle">PER</span> Peripheral Assignments
      </div><div class="cfg-group-body" style="display:block;">`;
      html += `<div style="display:flex;flex-wrap:wrap;gap:6px;padding:8px 0;">`;
      for (const [periph] of assignments) {
        html += `<span style="font-size:12px;background:var(--bg);color:var(--teal);padding:3px 10px;border-radius:8px;border:1px solid var(--border);">${periph}</span>`;
      }
      html += `</div></div></div>`;
    }
  }

  html += `</div>`; // close clkcfg-body

  html += clkBuildActions();

  main.innerHTML = html;

  clkBindConfigInputs(main);
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

    clkFreqs = data.frequencies || clkFreqs;
    clkWarnings = Array.isArray(data.warnings) ? data.warnings : clkWarnings;
    generatedFragments.clock.overlay = data.overlay || "";
    generatedFragments.clock.prj_conf = data.prj_conf || "";

    outEl.style.display = "";
    renderCodeReviewPanel("clkOutputReview", [
      {
        id: "overlay",
        label: ".overlay",
        path: "clock/clock.overlay",
        group: "Clock Configurator",
        content: data.overlay || "",
      },
      {
        id: "prj_conf",
        label: "prj.conf",
        path: "clock/prj.conf",
        group: "Clock Configurator",
        content: data.prj_conf || "",
      },
      {
        id: "freq",
        label: "frequencies.txt",
        path: "clock/frequencies.txt",
        group: "Clock Configurator",
        content: clkFormatFreqTable(data.frequencies),
      },
    ], {
      emptyMessage: "Generate clock output to review it here.",
      preferredSelection: clkOutputTab,
      onSelect: (file) => {
        clkOutputTab = file.id;
      },
    });
    refreshGeneratedOutputs();
    clkRenderSidebar();
    clkRenderBody();
    toast("Clock config generated");
  } catch (err) {
    outEl.style.display = "";
    renderCodeReviewPanel("clkOutputReview", [{
      id: "error",
      label: "error.txt",
      path: "clock/error.txt",
      group: "Clock Configurator",
      content: `ERROR: ${err.message}`,
    }], {
      preferredSelection: "error",
    });
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
  const applied = applyImportedConfig(impParsed);
  if (!applied) return;
  return snsAscii(str).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");

  // Close modal
  $("#importModal").classList.remove("show");
  toast(`Imported ${applied.appliedPins} pin(s), ${applied.peripheralCount} peripheral(s)`);
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

function mcuRenderSearchCandidates(candidates) {
  if (!Array.isArray(candidates) || !candidates.length) {
    return "";
  }

  let html = `<div style="padding:4px;">• Search results:</div>`;
  candidates.forEach((candidate, index) => {
    const label = candidate.kind || "result";
    html += `<div style="padding:4px 4px 6px 16px;border-left:1px solid var(--border);margin:4px 0;">
      <div style="font-size:10px;color:var(--fg-dim);text-transform:capitalize;">${label}</div>
      <a href="${candidate.url}" target="_blank" style="color:var(--accent);font-size:10px;word-break:break-all;display:block;">${candidate.url}</a>
      <button class="btn" data-search-candidate-index="${index}" style="font-size:10px;padding:3px 8px;margin-top:4px;">Use this URL</button>
    </div>`;
  });
  return html;
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

      html += mcuRenderSearchCandidates(idData.search_candidates);

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
      html += mcuRenderSearchCandidates(idData.search_candidates);
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

    resultEl.querySelectorAll("[data-search-candidate-index]").forEach((button) => {
      button.addEventListener("click", () => {
        const index = Number(button.getAttribute("data-search-candidate-index"));
        const candidate = idData.search_candidates?.[index];
        const inputEl = $("#mcuCustomUrl");
        if (candidate && inputEl) {
          inputEl.value = candidate.url;
        }
      });
    });

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
  const jobSearch = $("#snsJobSearch");

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

  jobSearch?.addEventListener("input", () => {
    snsRenderJobList();
  });
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
  const filter = resolveThresholdSearch("snsJobSearch", snsJobs.length);
  if (!snsJobs.length) {
    list.innerHTML = `<div class="empty-state" style="padding:20px;">
      <div>No sensors parsed yet</div>
      <div class="hint">Upload a PDF above</div>
    </div>`;
    return;
  }

  const filteredJobs = snsJobs.filter((j) => {
    if (!filter) return true;
    const s = j.result ? j.result.summary : j.summary;
    const pn = s ? (s.part_number || j.filename) : j.filename;
    const vendor = s ? (s.vendor_name || s.vendor || "") : "";
    const type = s ? (s.sensor_type || "") : "";
    const haystack = `${pn} ${vendor} ${type} ${j.filename}`.toLowerCase();
    return haystack.includes(filter);
  });

  if (!filteredJobs.length) {
    list.innerHTML = `<div class="empty-state" style="padding:20px;">
      <div>No parsed sensors match the current search</div>
      <div class="hint">Try another part number, vendor, or sensor type</div>
    </div>`;
    return;
  }

  list.innerHTML = filteredJobs.map(j => {
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
  const packageInfo = (r.package && typeof r.package === "object") ? r.package : {};
  const packageName = packageInfo.name || s.part_number || "sensor-package";
  const packageType = packageInfo.package_type || packageName;
  const pinCount = packageInfo.pin_count || (Array.isArray(packageInfo.pins) ? packageInfo.pins.length : 0);

  // Header
  let headerHTML = `<div class="sns-detail-header">
    <h2>${snsEsc(s.part_number || job.filename)}</h2>
    <div class="sns-specs">
      ${s.vendor_name ? `<span>Vendor: ${snsEsc(s.vendor_name)}</span>` : ""}
      ${s.sensor_type ? `<span>Type: ${snsEsc(s.sensor_type)}</span>` : ""}
      ${addr.protocol ? `<span>Bus: ${snsEsc(String(addr.protocol).toUpperCase())}</span>` : ""}
      ${addr.i2c_addresses && addr.i2c_addresses.length ? `<span>I2C: ${snsEsc(addr.i2c_addresses.join(", "))}</span>` : ""}
      ${addr.spi_max_freq_mhz ? `<span>SPI: ${snsEsc(String(addr.spi_max_freq_mhz))} MHz</span>` : ""}
      <span>Registers: ${regs.length}</span>
    </div>
  </div>`;

  // Body
  let bodyHTML = `<div class="sns-detail-body">`;

  // ─── Description ───
  if (s.description) {
    bodyHTML += `<div class="sns-section">
      <h3>Description</h3>
      <p style="font-size:12px;line-height:1.6;color:var(--fg);">${snsEsc(s.description)}</p>
    </div>`;
  }

  // ─── Address Info ───
  bodyHTML += `<div class="sns-section">
    <h3>Address / Interface</h3>
    <table class="sns-reg-table" style="max-width:500px;">
      <tr><th>Property</th><th>Value</th></tr>
      <tr><td>Protocol</td><td>${snsEsc(addr.protocol || "unknown")}</td></tr>
      ${addr.i2c_addresses && addr.i2c_addresses.length ? `<tr><td>I2C Addresses</td><td class="addr">${snsEsc(addr.i2c_addresses.join(", "))}</td></tr>` : ""}
      ${addr.spi_max_freq_mhz ? `<tr><td>SPI Max Freq</td><td>${snsEsc(String(addr.spi_max_freq_mhz))} MHz</td></tr>` : ""}
    </table>
  </div>`;

  bodyHTML += `<div class="sns-section">
    <h3>Package / CAD Source</h3>
    <table class="sns-reg-table" style="max-width:500px;">
      <tr><th>Property</th><th>Value</th></tr>
      <tr><td>Package</td><td>${snsEsc(packageName)}</td></tr>
      <tr><td>Type</td><td>${snsEsc(packageType)}</td></tr>
      <tr><td>Pin Count</td><td>${snsEsc(String(pinCount || 0))}</td></tr>
    </table>
  </div>`;

  // ─── Register Map ───
  if (regs.length) {
    bodyHTML += `<div class="sns-section">
      <h3>Register Map (${regs.length} registers)</h3>
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
      <button class="btn" id="snsGenDriver">Generate Driver + CAD</button>
    </div>
    <details class="sns-template-config" style="margin-top:10px;">
      <summary style="cursor:pointer;font-size:12px;color:var(--fg-dim);">Optional custom driver template</summary>
      <div style="display:grid;gap:8px;margin-top:10px;">
        <label style="font-size:12px;color:var(--fg-dim);">Output path</label>
        <input class="board-editor-canvas-input" id="snsCustomTemplatePath" type="text" placeholder="custom/my_sensor_driver.txt">
        <label style="font-size:12px;color:var(--fg-dim);">Template</label>
        <textarea id="snsCustomDriverTemplate" rows="8" style="width:100%;resize:vertical;">[[part_number]] driver template for [[driver_name]]
Bus: [[bus]]
Compatible: [[compatible]]

Paste your own template here to add a custom rendered file alongside the built-in Zephyr and Arduino outputs.</textarea>
        <div style="font-size:11px;color:var(--fg-dim);">Supported tokens: [[driver_name]], [[part_number]], [[vendor]], [[vendor_name]], [[sensor_type]], [[compatible]], [[bus]], [[description]], [[register_count]], [[i2c_addresses]], [[zephyr_source]], [[zephyr_header]], [[register_header]], [[register_defines]], [[arduino_header]], [[arduino_source]], [[arduino_example]]</div>
      </div>
    </details>
    <details class="sns-template-config" style="margin-top:10px;">
      <summary style="cursor:pointer;font-size:12px;color:var(--fg);">Optional custom driver template</summary>
      <div style="margin-top:10px;display:grid;gap:8px;">
        <label style="font-size:11px;color:var(--fg-dim);display:grid;gap:4px;">
          Output path
          <input class="board-editor-canvas-input" id="snsCustomTemplatePath" type="text" placeholder="custom/my_sensor_driver.txt">
        </label>
        <label style="font-size:11px;color:var(--fg-dim);display:grid;gap:4px;">
          Template
          <textarea id="snsCustomDriverTemplate" rows="8" style="width:100%;resize:vertical;">[[part_number]] driver template for [[driver_name]]
Bus=[[bus]]
Compatible=[[compatible]]
Registers=[[register_count]]</textarea>
        </label>
        <div style="font-size:10px;color:var(--fg-dim);line-height:1.5;">
          Supported tokens: [[driver_name]], [[part_number]], [[compatible]], [[bus]], [[vendor]], [[description]], [[register_count]], [[zephyr_source]], [[zephyr_header]], [[arduino_header]], [[arduino_source]], [[arduino_example]]
        </div>
      </div>
    </details>
    ${codeReviewPanelMarkup("snsHeaderReview", "Generate a header to review it here.")}
  </div>`;

  // ─── Driver Generation ───
  bodyHTML += `<div class="sns-section" id="snsDriverSection" style="display:none;">
    <h3>Generated Sensor Driver and CAD Bundle</h3>
    ${codeReviewPanelMarkup("snsDriverReview", "Generate the sensor driver, footprint, and 3D model to review them here.")}
  </div>`;

  bodyHTML += `</div>`;

  main.innerHTML = headerHTML + bodyHTML;

  // Wire header generation
  $("#snsGenHeader").addEventListener("click", () => snsGenerateHeader(job.job_id));
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

    renderCodeReviewPanel("snsHeaderReview", [{
      id: data.filename,
      label: data.filename,
      path: `sensor/${data.filename}`,
      group: "Sensor Parser",
      content: data.code,
    }], {
      emptyMessage: "Generate a header to review it here.",
      preferredSelection: data.filename,
    });

    toast(`Generated ${data.filename}`);
  } catch (err) {
    toast("Error: " + err.message);
  } finally {
    btn.disabled = false;
    btn.textContent = "Generate Header";
  }
}

// ── Generate Zephyr driver ───────────────────────────────────────────

async function snsGenerateDriver(jobId) {
  const btn = $("#snsGenDriver");
  const customTemplateInput = $("#snsCustomDriverTemplate");
  const customTemplatePathInput = $("#snsCustomTemplatePath");
  btn.disabled = true;
  btn.textContent = "Generating...";

  try {
    const res = await fetch(`/api/sensor-job/${jobId}/driver`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        custom_template: String(customTemplateInput?.value || "").trim(),
        custom_template_path: String(customTemplatePathInput?.value || "").trim(),
      }),
    });
    const data = await res.json();

    if (!res.ok) {
      toast(data.error || "Driver generation failed");
      return;
    }

    const section = $("#snsDriverSection");
    section.style.display = "block";

    const driverBaseName = String(data.driver_name || data.name || data.part_number || jobId || "sensor").trim() || "sensor";
    const fileEntries = [
      { label: "Driver Source", key: "source_c", path: `sensor/${driverBaseName}.c` },
      { label: "Public Header", key: "header_h", path: `sensor/${driverBaseName}.h` },
      { label: "Kconfig", key: "kconfig", path: "sensor/Kconfig" },
      { label: "CMakeLists", key: "cmake", path: "sensor/CMakeLists.txt" },
      { label: "Overlay Sample", key: "overlay_sample", path: "sensor/sample.overlay" },
      { label: "prj.conf Sample", key: "prj_conf_sample", path: "sensor/prj.conf" },
      { label: "README", key: "readme", path: "sensor/README.md" },
      { label: "Test Skeleton", key: "test_c", path: `sensor/${driverBaseName}_test.c` },
      { label: "Register Header", key: "register_header", path: "sensor/register_header.h" },
      { label: "Register Defines", key: "register_defines", path: "sensor/register_defines.h" },
      { label: "Arduino Header", key: "arduino_header", path: `arduino/${driverBaseName}.h` },
      { label: "Arduino Source", key: "arduino_source", path: `arduino/${driverBaseName}.cpp` },
      { label: "Arduino Example", key: "arduino_example", path: `arduino/${driverBaseName}.ino` },
      { label: "KiCad Footprint", key: "kicad_footprint", path: data.kicad_footprint_path || `cad/${driverBaseName}/${driverBaseName}.kicad_mod` },
      { label: "3D Model", key: "wrl_model", path: data.wrl_model_path || `cad/${driverBaseName}/${driverBaseName}.wrl` },
    ];
    if (data.custom_template_output) {
      fileEntries.push({
        label: "Custom Template",
        key: "custom_template_output",
        path: data.custom_template_path || `custom/${driverBaseName}_template.txt`,
      });
    }

    renderCodeReviewPanel("snsDriverReview", fileEntries.filter((entry) => data[entry.key]).map((entry) => ({
      id: entry.key,
      label: entry.label,
      path: entry.path,
      group: "Sensor Parser",
      content: data[entry.key] || "",
    })), {
      emptyMessage: "Generate the sensor driver, footprint, and 3D model to review them here.",
      preferredSelection: "source_c",
    });
    toast("Sensor driver, footprint, and 3D model generated successfully");
    section.scrollIntoView({ behavior: "smooth", block: "start" });
  } catch (err) {
    toast("Error: " + err.message);
  } finally {
    btn.disabled = false;
    btn.textContent = "Generate Driver + CAD";
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
  return snsAscii(str).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
}

function snsAscii(str) {
  if (!str) return "";
  let text = String(str);
  if (/[ÃÂâð€™]/.test(text)) {
    try {
      const repaired = decodeURIComponent(escape(text));
      const currentNoise = (text.match(/[ÃÂâð€™]/g) || []).length;
      const repairedNoise = (repaired.match(/[ÃÂâð€™]/g) || []).length;
      if (repairedNoise < currentNoise) {
        text = repaired;
      }
    } catch (_err) {
      // Keep the original text when browser-side repair fails.
    }
  }
  return text
    .replace(/[\u2013\u2014]/g, "-")
    .replace(/[\u2018\u2019]/g, "'")
    .replace(/[\u201C\u201D]/g, '"')
    .replace(/\u2022/g, "*")
    .replace(/\u2026/g, "...")
    .replace(/\u2192/g, "->")
    .replace(/\u00B0/g, " deg")
    .replace(/\u00B5/g, "u")
    .replace(/\u00D7/g, "x")
    .replace(/[^\x09\x0A\x0D\x20-\x7E]/g, "?");
}
