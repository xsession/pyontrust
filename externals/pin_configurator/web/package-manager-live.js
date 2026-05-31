window.pkgGeneratedArtifacts = Array.isArray(window.pkgGeneratedArtifacts) ? window.pkgGeneratedArtifacts : [];

if (typeof detectGeneratedFileLanguage === "function") {
  const baseDetectGeneratedFileLanguage = detectGeneratedFileLanguage;
  detectGeneratedFileLanguage = function(path) {
    const lowerPath = String(path || "").toLowerCase();
    if (lowerPath.endsWith(".kicad_mod")) return "kicad footprint";
    if (lowerPath.endsWith(".wrl")) return "vrml";
    return baseDetectGeneratedFileLanguage(path);
  };
}

(function installGeneratedArtifactPreview() {
  if (window.__pkgPreviewInstalled || window.__codeReviewPreviewInstalled) return;
  if (typeof ensureCodeReviewPanel !== "function" || typeof drawCodeReviewPanel !== "function" || typeof selectedCodeReviewFile !== "function") {
    return;
  }
  window.__pkgPreviewInstalled = true;

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

  function codeReviewPreviewKind(path) {
    const lower = String(path || "").toLowerCase();
    if (lower.endsWith(".kicad_mod")) return "footprint";
    if (lower.endsWith(".wrl")) return "model";
    return "";
  }

  function escapePreview(value) {
    return String(value || "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/\"/g, "&quot;");
  }

  function parseFootprint(content) {
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
          const ex = Number(circleMatch[3]);
          const ey = Number(circleMatch[4]);
          circles.push({
            cx,
            cy,
            r: Math.hypot(ex - cx, ey - cy),
          });
        }
      }
    }
    return { pads, segments, circles };
  }

  function boxFaces(center, size, palette) {
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

  function buildFootprintScene(content) {
    const parsed = parseFootprint(content);
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
      ...boxFaces({ x: center.x, y: center.y, z: 0 }, { x: width, y: height, z: boardThickness }, {
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
      faces.push(...boxFaces({ x: pad.x, y: pad.y, z: boardThickness / 2 + padHeight / 2 }, {
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
    const scene = buildFootprintScene(content);
    if (!scene) {
      return {
        title: "Footprint Preview",
        meta: "No drawable geometry found",
        note: "The footprint source is present, but this preview renderer could not detect pads or silkscreen primitives.",
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
      faces: boxFaces({ x: 0, y: 0, z: 0 }, { x: sizeX, y: sizeY, z: sizeZ }, {
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

  function buildPreview(file) {
    const kind = codeReviewPreviewKind(file?.path);
    if (kind === "footprint") return renderFootprintPreview(file?.content || "");
    if (kind === "model") return renderModelPreview(file?.content || "");
    return null;
  }

  function rotatePoint(point, yaw, pitch) {
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

  function projectPoint(point, view, canvas) {
    const rotated = rotatePoint(point, view.yaw, view.pitch);
    const distance = Math.max(view.extent * 3.2, 6);
    const perspective = distance / Math.max(distance * 0.35, rotated.z + distance);
    const scale = (Math.min(canvas.width, canvas.height) / Math.max(view.extent * 2.7, 8)) * view.zoom;
    return {
      x: canvas.width / 2 + view.panX + rotated.x * scale * perspective,
      y: canvas.height / 2 + view.panY - rotated.y * scale * perspective,
      z: rotated.z,
      perspective,
    };
  }

  function drawInteractivePreview(stage, preview, cacheKey) {
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
      ctx.save();
      ctx.fillStyle = "rgba(11,18,32,0.55)";
      ctx.beginPath();
      ctx.ellipse(canvas.width / 2, canvas.height * 0.78, canvas.width * 0.28, canvas.height * 0.08, 0, 0, Math.PI * 2);
      ctx.fill();

      const faces = (preview.faces || []).map((face) => {
        const projected = face.points.map((point) => projectPoint(point, view, canvas));
        const depth = face.points.reduce((sum, point) => sum + rotatePoint(point, view.yaw, view.pitch).z, 0) / Math.max(face.points.length, 1);
        return { face, projected, depth };
      }).sort((left, right) => left.depth - right.depth);

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
          const p0 = projectPoint(overlay.points[0], view, canvas);
          const p1 = projectPoint(overlay.points[1], view, canvas);
          ctx.beginPath();
          ctx.moveTo(p0.x, p0.y);
          ctx.lineTo(p1.x, p1.y);
          ctx.stroke();
        } else if (overlay.kind === "circle") {
          const samples = [];
          for (let index = 0; index <= 24; index += 1) {
            const angle = (index / 24) * Math.PI * 2;
            samples.push(projectPoint({
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
          const point = projectPoint(overlay.point, view, canvas);
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
      ctx.restore();
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

  const originalEnsureCodeReviewPanel = ensureCodeReviewPanel;
  ensureCodeReviewPanel = function(panelId) {
    const state = originalEnsureCodeReviewPanel(panelId);
    if (!state?.fallback) return state;
    let preview = state.root.querySelector("[data-code-review-preview]");
    if (!preview) {
      preview = document.createElement("div");
      preview.className = "output-files-preview";
      preview.setAttribute("data-code-review-preview", "true");
      state.fallback.parentNode.insertBefore(preview, state.fallback);
    }
    state.preview = preview;
    return state;
  };

  const originalDrawCodeReviewPanel = drawCodeReviewPanel;
  drawCodeReviewPanel = function(state) {
    originalDrawCodeReviewPanel(state);
    if (!state?.preview) return;
    const selected = selectedCodeReviewFile(state);
    const preview = buildPreview(selected);
    if (!preview) {
      state.preview.classList.remove("active");
      state.preview.innerHTML = "";
      return;
    }
    state.preview.classList.add("active");
    state.preview.innerHTML = `
      <div class="output-files-preview-header">
        <div class="output-files-preview-title">${escapePreview(preview.title)}</div>
        <div class="output-files-preview-meta">${escapePreview(preview.meta || "")}</div>
      </div>
      <div class="output-files-preview-stage">${preview.svg || ""}</div>
      <div class="output-files-preview-note">${escapePreview(preview.note || "")}</div>
      ${Array.isArray(preview.legendItems) && preview.legendItems.length ? `<div class="output-files-preview-pins">${preview.legendItems.map((item) => `<div class="output-files-preview-pin"><span class="output-files-preview-pin-num">${escapePreview(item.number)}</span><span class="output-files-preview-pin-name">${escapePreview(item.label)}</span></div>`).join("")}</div>` : ""}
    `;
    if (preview.type === "interactive") {
      const stage = state.preview.querySelector(".output-files-preview-stage");
      drawInteractivePreview(stage, preview, selected?.id || selected?.path || preview.title);
    }
  };

  window.ensureCodeReviewPanel = ensureCodeReviewPanel;
  window.drawCodeReviewPanel = drawCodeReviewPanel;
})();

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
    <div class="hint">Upload an MCU datasheet PDF here to generate peripheral driver sets,<br>
      KiCad footprints, and 3D models for parsed MCU packages.</div>
    <div class="hint" data-pkg-ui-version="20260531r">MCU-only Package Manager workflow active.</div>
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

window.setTimeout(() => {
  if (typeof snsRenderDetail === "function") {
    snsRenderDetail = function(job) {
      const r = job.result;
      const s = r.summary;
      const regs = r.register_map.registers;
      const addr = r.address;
      const main = $("#snsMain");
      const packageInfo = (r.package && typeof r.package === "object") ? r.package : {};
      const packageName = packageInfo.name || s.part_number || "sensor-package";
      const packageType = packageInfo.package_type || packageName;
      const pinCount = packageInfo.pin_count || (Array.isArray(packageInfo.pins) ? packageInfo.pins.length : 0);

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

      let bodyHTML = `<div class="sns-detail-body">`;

      if (s.description) {
        bodyHTML += `<div class="sns-section">
          <h3>Description</h3>
          <p style="font-size:12px;line-height:1.6;color:var(--fg);">${snsEsc(s.description)}</p>
        </div>`;
      }

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

      bodyHTML += `<div class="sns-section">
        <h3>C Register Header</h3>
        <div class="sns-code-actions">
          <button class="btn" id="snsGenHeader">Generate Header</button>
          <button class="btn" id="snsGenDriver">Generate Driver + CAD</button>
        </div>
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

      bodyHTML += `<div class="sns-section" id="snsDriverSection" style="display:none;">
        <h3>Generated Sensor Driver and CAD Bundle</h3>
        ${codeReviewPanelMarkup("snsDriverReview", "Generate the sensor driver, footprint, and 3D model to review them here.")}
      </div>`;

      bodyHTML += `</div>`;
      main.innerHTML = headerHTML + bodyHTML;

      $("#snsGenHeader")?.addEventListener("click", () => snsGenerateHeader(job.job_id));
      $("#snsGenDriver")?.addEventListener("click", () => snsGenerateDriver(job.job_id));
    };
  }

  if (typeof snsGenerateDriver === "function") {
    snsGenerateDriver = async function(jobId) {
      const btn = $("#snsGenDriver");
      const customTemplateInput = $("#snsCustomDriverTemplate");
      const customTemplatePathInput = $("#snsCustomTemplatePath");
      if (btn) {
        btn.disabled = true;
        btn.textContent = "Generating...";
      }

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
        if (section) section.style.display = "block";

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
        section?.scrollIntoView({ behavior: "smooth", block: "start" });
      } catch (err) {
        toast("Error: " + err.message);
      } finally {
        if (btn) {
          btn.disabled = false;
          btn.textContent = "Generate Driver + CAD";
        }
      }
    };
  }
}, 0);

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
