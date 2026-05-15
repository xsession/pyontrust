let interruptViewState = { selectedId: "" };

const INTERRUPT_PRIORITY_CANDIDATES = {
  uart: ["CONFIG_SERIAL_INIT_PRIORITY"],
  spi: ["CONFIG_SPI_INIT_PRIORITY"],
  i2c: ["CONFIG_I2C_INIT_PRIORITY"],
  gpio: ["CONFIG_GPIO_INIT_PRIORITY"],
  can: ["CONFIG_CAN_INIT_PRIORITY"],
  adc: ["CONFIG_ADC_INIT_PRIORITY"],
  dac: ["CONFIG_DAC_INIT_PRIORITY"],
  dma: ["CONFIG_DMA_INIT_PRIORITY"],
  usb: ["CONFIG_USB_DEVICE_INIT_PRIORITY", "CONFIG_USB_NRFX_INIT_PRIORITY", "CONFIG_USB_DC_STM32_PRIORITY"],
  system: ["CONFIG_SYSTEM_CLOCK_INIT_PRIORITY"],
};

function interruptIsVisible() {
  return document.querySelector('.tab-content[data-app-content="interrupts"]')?.classList.contains("active");
}

function interruptRefreshIfVisible() {
  if (interruptIsVisible()) {
    interruptRender();
  }
}

function interruptFamilyFromName(name = "") {
  const value = String(name || "").toLowerCase();
  if (value.startsWith("uart") || value.includes("serial")) return "uart";
  if (value.startsWith("spi")) return "spi";
  if (value.startsWith("i2c")) return "i2c";
  if (value.startsWith("gpio")) return "gpio";
  if (value.startsWith("can")) return "can";
  if (value.startsWith("adc")) return "adc";
  if (value.startsWith("dac")) return "dac";
  if (value.startsWith("dma")) return "dma";
  if (value.startsWith("usb")) return "usb";
  return "system";
}

function interruptModuleOptionByKey(key) {
  const wanted = String(key || "");
  for (const mod of modModules || []) {
    for (const cat of mod.categories || []) {
      for (const opt of cat.options || []) {
        if (opt.key !== wanted) continue;
        return {
          moduleId: mod.id,
          moduleName: mod.name,
          option: opt,
          current: modValuesMap?.[mod.id]?.[opt.key] ?? opt.default,
          defaultValue: modDefaultsMap?.[mod.id]?.[opt.key] ?? opt.default,
          enabled: !!modEnabled?.[mod.id],
        };
      }
    }
  }
  return null;
}

function interruptPriorityRecord(family) {
  const candidates = INTERRUPT_PRIORITY_CANDIDATES[family] || [];
  for (const key of candidates) {
    const found = interruptModuleOptionByKey(key);
    if (found) {
      return {
        key,
        current: found.current,
        defaultValue: found.defaultValue,
        moduleName: found.moduleName,
        enabled: found.enabled,
      };
    }
  }
  return candidates[0] ? {
    key: candidates[0],
    current: null,
    defaultValue: null,
    moduleName: "",
    enabled: false,
  } : null;
}

function interruptPriorityLabel(record) {
  if (!record) return "No mapped init priority";
  if (record.current === null || record.current === undefined || record.current === "") {
    return `${record.key} (driver default)`;
  }
  const suffix = String(record.current) !== String(record.defaultValue)
    ? `, default ${record.defaultValue}`
    : "";
  return `${record.key}=${record.current}${suffix}`;
}

function interruptSeverity(score) {
  if (score >= 3) return { label: "Needs attention", className: "attention" };
  if (score >= 2) return { label: "Moderate impact", className: "moderate" };
  return { label: "Lower impact", className: "stable" };
}

function interruptPushItem(items, item) {
  if (!item || !item.id) return;
  items.push(item);
}

function interruptBoolValue(value) {
  return value === true || value === "y" || value === "Y" || value === 1 || value === "1";
}

function interruptProtocolItems() {
  const items = [];
  protocolActiveEntries().forEach(entry => {
    const template = protocolTemplate(entry.templateId);
    const name = protocolEntryName(entry, template);
    if (entry.templateId === "uart_shell_bridge") {
      const priority = interruptPriorityRecord("uart");
      interruptPushItem(items, {
        id: `protocol:${entry.id}`,
        title: name,
        category: "Protocol",
        source: `${template.label} on ${entry.values.uartNode || "uart0"}`,
        reason: "Interrupt-driven UART shell backend is enabled.",
        priority,
        impact: "RX/TX shell traffic can add latency during bursts and compete with application serial traffic.",
        details: [
          "Generated protocol stack enables CONFIG_UART_INTERRUPT_DRIVEN and CONFIG_SHELL_BACKEND_SERIAL.",
          `Configured baud rate: ${Math.max(9600, Number(entry.values.baudRate) || 115200)}.`,
        ],
        score: 3,
      });
    } else if (entry.templateId.startsWith("usb_")) {
      const priority = interruptPriorityRecord("usb");
      const node = protocolSelectedNodeRef(entry, template);
      interruptPushItem(items, {
        id: `protocol:${entry.id}`,
        title: name,
        category: "Protocol",
        source: `${template.label}${node ? ` on ${node}` : ""}`,
        reason: node
          ? "USB device endpoints typically rely on controller interrupt service routines."
          : "USB stack selected, but the current board model does not expose a matching USB controller.",
        priority,
        impact: node
          ? "USB traffic can create bursty endpoint servicing and timing sensitivity during enumeration or transfers."
          : "Configuration is incomplete until the board model exposes a compatible USB controller.",
        details: [
          `Generated protocol type: ${template.label}.`,
          node ? `Bound controller: ${node}.` : "No controller node available on the active board model.",
        ],
        score: node ? 2 : 3,
      });
    } else if (entry.templateId.startsWith("bluetooth_")) {
      interruptPushItem(items, {
        id: `protocol:${entry.id}`,
        title: name,
        category: "Protocol",
        source: template.label,
        reason: "Bluetooth host/controller activity depends on time-sensitive radio events and stack callbacks.",
        priority: null,
        impact: "Connection intervals, scan windows, and advertising cadence can affect responsiveness and power.",
        details: [
          entry.templateId === "bluetooth_le_peripheral"
            ? `Advertising interval: ${Math.max(20, Number(entry.values.advertisingIntervalMs) || 100)} ms.`
            : `Scan interval/window: ${Math.max(10, Number(entry.values.scanIntervalMs) || 80)} / ${Math.max(10, Number(entry.values.scanWindowMs) || 60)} ms.`,
          "Exact IRQ priorities depend on the controller and board support package.",
        ],
        score: 2,
      });
    }
  });
  return items;
}

function interruptPeripheralConfigItems() {
  const items = [];
  (pcfgInstances || []).forEach(inst => {
    const values = pcfgValues?.[inst.instance] || {};
    const family = interruptFamilyFromName(inst.instance || inst.template || inst.display || "");
    const priority = interruptPriorityRecord(family);
    (inst.groups || []).forEach(group => {
      (group.props || []).forEach(prop => {
        const matchInterrupt = /(interrupt|irq|async)/i.test(`${prop.key} ${prop.label} ${prop.help || ""}`);
        const matchPriority = /_INIT_PRIORITY$/i.test(prop.key);
        if (!matchInterrupt && !matchPriority) return;
        const current = values[prop.key] ?? prop.default;
        const enabled = prop.type === "bool" ? interruptBoolValue(current) : String(current ?? "") !== "";
        const changed = String(current) !== String(prop.default);
        if (matchInterrupt && !enabled) return;
        if (matchPriority && !changed) return;
        interruptPushItem(items, {
          id: `pcfg:${inst.instance}:${prop.key}`,
          title: `${inst.display} - ${prop.label || prop.key}`,
          category: "Peripheral",
          source: inst.instance,
          reason: matchPriority
            ? `Priority override detected: ${prop.key}=${current}.`
            : `${prop.label || prop.key} is enabled for this peripheral instance.`,
          priority,
          impact: matchPriority
            ? "Changing init priority can alter startup order relative to other drivers and services."
            : "Interrupt or async mode can increase ISR or deferred-work load during peripheral activity.",
          details: [
            prop.help || "No extra help text is available for this setting.",
            `Current value: ${current}`,
            `Default value: ${prop.default}`,
          ],
          score: matchPriority ? 2 : 3,
        });
      });
    });
  });
  return items;
}

function interruptModuleItems() {
  const items = [];
  for (const mod of modModules || []) {
    const values = modValuesMap?.[mod.id] || {};
    const defaults = modDefaultsMap?.[mod.id] || {};
    for (const cat of mod.categories || []) {
      for (const opt of cat.options || []) {
        const matchInterrupt = /(interrupt|irq)/i.test(`${opt.key} ${opt.label || ""} ${opt.help || ""}`);
        const matchPriority = /_INIT_PRIORITY$/i.test(opt.key);
        if (!matchInterrupt && !matchPriority) continue;
        const current = values[opt.key] ?? opt.default;
        const defaultValue = defaults[opt.key] ?? opt.default;
        const enabled = opt.type === "bool" ? interruptBoolValue(current) : String(current ?? "") !== "";
        const changed = String(current) !== String(defaultValue);
        if (matchInterrupt && !enabled) continue;
        if (matchPriority && !changed) continue;
        interruptPushItem(items, {
          id: `module:${mod.id}:${opt.key}`,
          title: `${mod.name} - ${opt.label || opt.key}`,
          category: "Module",
          source: mod.id,
          reason: matchPriority
            ? `Priority override detected: ${opt.key}=${current}.`
            : `${opt.label || opt.key} is enabled in module configuration.`,
          priority: matchPriority ? {
            key: opt.key,
            current,
            defaultValue,
            moduleName: mod.name,
            enabled: !!modEnabled?.[mod.id],
          } : null,
          impact: matchPriority
            ? "Initialization order may shift relative to subsystems with lower or higher priorities."
            : "Interrupt-related module behavior is enabled and may affect scheduling or driver callbacks.",
          details: [
            opt.help || "No extra help text is available for this setting.",
            `Current value: ${current}`,
            `Default value: ${defaultValue}`,
            `Module enabled for generation: ${modEnabled?.[mod.id] ? "yes" : "no"}`,
          ],
          score: matchPriority ? 2 : 3,
        });
      }
    }
  }
  return items;
}

function interruptEnabledPeripheralRows() {
  if (!boardData?.peripherals) return [];
  return boardData.peripherals
    .filter(peripheral => periphStates?.[peripheral.name])
    .map(peripheral => {
      const family = interruptFamilyFromName(peripheral.name || peripheral.display || "");
      const priority = interruptPriorityRecord(family);
      return {
        peripheral,
        family,
        priority,
      };
    })
    .sort((left, right) => String(left.peripheral.display || left.peripheral.name).localeCompare(String(right.peripheral.display || right.peripheral.name)));
}

function interruptPriorityOverrides() {
  const rows = [];
  for (const mod of modModules || []) {
    for (const cat of mod.categories || []) {
      for (const opt of cat.options || []) {
        if (!/_INIT_PRIORITY$/i.test(opt.key)) continue;
        const current = modValuesMap?.[mod.id]?.[opt.key] ?? opt.default;
        const defaultValue = modDefaultsMap?.[mod.id]?.[opt.key] ?? opt.default;
        if (String(current) === String(defaultValue)) continue;
        rows.push({
          key: opt.key,
          current,
          defaultValue,
          moduleName: mod.name,
          enabled: !!modEnabled?.[mod.id],
        });
      }
    }
  }
  return rows.sort((left, right) => String(left.current).localeCompare(String(right.current), undefined, { numeric: true }));
}

function interruptBuildSnapshot() {
  const items = [
    ...interruptProtocolItems(),
    ...interruptPeripheralConfigItems(),
    ...interruptModuleItems(),
  ];
  const enabledPeripherals = interruptEnabledPeripheralRows();
  const priorityOverrides = interruptPriorityOverrides();
  const notes = [];

  if (!boardData) {
    notes.push("Load a board to inspect enabled peripherals and derived interrupt-sensitive paths.");
  }
  if (!items.length && boardData) {
    notes.push("No explicit interrupt-driven features or priority overrides are currently detected in the loaded frontend state.");
  }
  if (items.some(item => item.reason.includes("USB") || item.source.toLowerCase().includes("usb"))) {
    notes.push("USB enumeration and transfer traffic can arrive in bursts, so watch endpoint processing latency under load.");
  }
  if (items.some(item => item.reason.includes("UART shell backend") || item.reason.includes("UART API"))) {
    notes.push("Shell or console traffic on UART can hide latency spikes if logs or command bursts arrive during application work.");
  }
  if (priorityOverrides.length > 1) {
    notes.push("Multiple explicit init-priority overrides are active. Review whether the intended startup order still matches dependency order.");
  }

  const totalScore = items.reduce((sum, item) => sum + item.score, 0);
  const severity = interruptSeverity(totalScore >= 8 ? 3 : totalScore >= 4 ? 2 : 1);
  const selectedId = items.some(item => item.id === interruptViewState.selectedId)
    ? interruptViewState.selectedId
    : items[0]?.id || "";
  interruptViewState.selectedId = selectedId;

  return {
    board: boardData?.board || "",
    soc: boardData?.soc || "",
    items,
    enabledPeripherals,
    priorityOverrides,
    notes,
    selected: items.find(item => item.id === selectedId) || null,
    severity,
  };
}

function interruptRenderList(snapshot) {
  const list = $("#irqSourceList");
  if (!list) return;
  if (!snapshot.items.length) {
    list.innerHTML = '<div class="irq-editor-empty">No interrupt-sensitive sources are currently detected from protocol, peripheral, or module state.</div>';
    return;
  }
  list.innerHTML = snapshot.items.map(item => {
    const severity = interruptSeverity(item.score);
    return `
      <div class="irq-editor-item${item.id === interruptViewState.selectedId ? " active" : ""}" data-irq-item="${escapeHtml(item.id)}">
        <div class="irq-editor-item-top">
          <div>
            <div class="irq-editor-item-title">${escapeHtml(item.title)}</div>
            <div class="irq-editor-item-meta">${escapeHtml(item.category)} • ${escapeHtml(item.source)}</div>
          </div>
          <span class="irq-editor-badge ${severity.className}">${severity.label}</span>
        </div>
        <div class="irq-editor-item-meta">${escapeHtml(item.reason)}</div>
      </div>`;
  }).join("");
  list.querySelectorAll("[data-irq-item]").forEach(node => {
    node.addEventListener("click", () => {
      interruptViewState.selectedId = node.dataset.irqItem;
      interruptRender();
    });
  });
}

function interruptRenderMain(snapshot) {
  const summary = $("#irqSummaryMeta");
  const main = $("#irqMainReport");
  if (!main) return;
  if (summary) {
    summary.textContent = snapshot.board
      ? `${snapshot.board} • ${snapshot.items.length} active interrupt-sensitive source${snapshot.items.length === 1 ? "" : "s"} • ${snapshot.priorityOverrides.length} explicit priority override${snapshot.priorityOverrides.length === 1 ? "" : "s"}`
      : "No board loaded.";
  }
  if (!snapshot.board) {
    main.innerHTML = '<div class="irq-editor-empty">Select a board to build an interrupt-impact summary.</div>';
    return;
  }

  const enabledRows = snapshot.enabledPeripherals.slice(0, 10).map(row => `
    <tr>
      <td>${escapeHtml(row.peripheral.display || row.peripheral.name)}</td>
      <td>${escapeHtml(row.family.toUpperCase())}</td>
      <td>${escapeHtml(interruptPriorityLabel(row.priority))}</td>
      <td>${escapeHtml(periphCoreStates?.[row.peripheral.name] || row.peripheral.core_id || "-")}</td>
    </tr>`).join("");

  const overrideRows = snapshot.priorityOverrides.length
    ? snapshot.priorityOverrides.map(row => `
      <tr>
        <td>${escapeHtml(row.key)}</td>
        <td>${escapeHtml(String(row.current))}</td>
        <td>${escapeHtml(String(row.defaultValue))}</td>
        <td>${escapeHtml(row.moduleName)}${row.enabled ? "" : " (module not enabled)"}</td>
      </tr>`).join("")
    : '<tr><td colspan="4">No explicit init-priority overrides detected.</td></tr>';

  const noteRows = snapshot.notes.length
    ? snapshot.notes.map(note => `<div>${escapeHtml(note)}</div>`).join("")
    : '<div>No additional interrupt-impact notes for the current configuration.</div>';

  main.innerHTML = `
    <div class="irq-editor-grid">
      <div class="irq-editor-card">
        <div class="irq-editor-card-title">System Attention</div>
        <div class="irq-editor-card-meta">Derived from active interrupt-sensitive paths and explicit overrides.</div>
        <div class="irq-editor-card-value">${escapeHtml(snapshot.severity.label)}</div>
        <div class="irq-editor-card-hint">This is a heuristic, not a raw IRQ analyzer.</div>
      </div>
      <div class="irq-editor-card">
        <div class="irq-editor-card-title">Enabled Peripherals</div>
        <div class="irq-editor-card-meta">Board peripherals currently enabled in the pin configurator.</div>
        <div class="irq-editor-card-value">${snapshot.enabledPeripherals.length}</div>
        <div class="irq-editor-card-hint">Each enabled driver can still use default init priorities if no override is present.</div>
      </div>
      <div class="irq-editor-card">
        <div class="irq-editor-card-title">Priority Overrides</div>
        <div class="irq-editor-card-meta">Only explicit non-default init-priority changes are counted here.</div>
        <div class="irq-editor-card-value">${snapshot.priorityOverrides.length}</div>
        <div class="irq-editor-card-hint">Review overrides together so dependencies still initialize in the intended order.</div>
      </div>
    </div>

    <div class="irq-editor-section">
      <h3>Enabled Peripheral Order</h3>
      <div class="irq-editor-card">
        <table class="irq-editor-table">
          <thead>
            <tr>
              <th>Peripheral</th>
              <th>Family</th>
              <th>Priority Mapping</th>
              <th>Core</th>
            </tr>
          </thead>
          <tbody>${enabledRows || '<tr><td colspan="4">No enabled peripherals on the active board.</td></tr>'}</tbody>
        </table>
      </div>
    </div>

    <div class="irq-editor-section">
      <h3>Explicit Priority Overrides</h3>
      <div class="irq-editor-card">
        <table class="irq-editor-table">
          <thead>
            <tr>
              <th>Kconfig</th>
              <th>Current</th>
              <th>Default</th>
              <th>Module</th>
            </tr>
          </thead>
          <tbody>${overrideRows}</tbody>
        </table>
      </div>
    </div>

    <div class="irq-editor-section">
      <h3>Impact Notes</h3>
      <div class="irq-editor-note-card">
        <div class="irq-editor-list-inline">${noteRows}</div>
      </div>
    </div>`;
}

function interruptRenderDetail(snapshot) {
  const panel = $("#irqDetailPanel");
  if (!panel) return;
  const item = snapshot.selected;
  if (!item) {
    panel.className = "irq-editor-empty";
    panel.textContent = "Select an interrupt-sensitive source to inspect its priority and likely system impact.";
    return;
  }
  const severity = interruptSeverity(item.score);
  panel.className = "irq-editor-detail";
  panel.innerHTML = `
    <div class="irq-editor-detail-head">
      <div>
        <div class="irq-editor-detail-title">${escapeHtml(item.title)}</div>
        <div class="irq-editor-detail-meta">${escapeHtml(item.category)} • ${escapeHtml(item.source)}</div>
      </div>
      <span class="irq-editor-badge ${severity.className}">${severity.label}</span>
    </div>
    <div class="irq-editor-list-inline">
      <div><strong>Reason:</strong> ${escapeHtml(item.reason)}</div>
      <div><strong>Priority:</strong> ${escapeHtml(interruptPriorityLabel(item.priority))}</div>
      <div><strong>Impact:</strong> ${escapeHtml(item.impact)}</div>
    </div>
    <div class="irq-editor-section" style="margin-top:12px;">
      <h3>Details</h3>
      <div class="irq-editor-list-inline">
        ${(item.details || []).map(detail => `<div>${escapeHtml(detail)}</div>`).join("")}
      </div>
    </div>`;
}

function interruptRender() {
  const snapshot = interruptBuildSnapshot();
  interruptRenderList(snapshot);
  interruptRenderMain(snapshot);
  interruptRenderDetail(snapshot);
}
