const PROTOCOL_EDITOR_TEMPLATES = [
  {
    id: "bluetooth_le_peripheral",
    label: "Bluetooth LE Peripheral",
    family: "Bluetooth",
    transport: "Wireless",
    summary: "Advertising GATT peripheral with configurable device name, MTU, and security.",
    defaults: {
      instanceName: "ble_peripheral",
      deviceName: "Zephyr Device",
      mtu: 247,
      security: "none",
      advertisingIntervalMs: 100,
      services: "Heart Rate, Battery Service",
    },
    fields: [
      { key: "instanceName", label: "Instance Name", type: "text" },
      { key: "deviceName", label: "Device Name", type: "text" },
      { key: "mtu", label: "ATT MTU", type: "number", min: 23, step: 1 },
      {
        key: "security",
        label: "Security",
        type: "select",
        options: [
          { value: "none", label: "Open" },
          { value: "pairing", label: "Pairing" },
          { value: "lesc", label: "LE Secure Connections" },
        ],
      },
      { key: "advertisingIntervalMs", label: "Advertising Interval (ms)", type: "number", min: 20, step: 5 },
      { key: "services", label: "Services", type: "textarea" },
    ],
  },
  {
    id: "bluetooth_central_scanner",
    label: "Bluetooth Central Scanner",
    family: "Bluetooth",
    transport: "Wireless",
    summary: "Central role starter for scanning and connecting to nearby BLE peripherals.",
    defaults: {
      instanceName: "ble_central",
      scanWindowMs: 60,
      scanIntervalMs: 80,
      maxConnections: 2,
      filterNamePrefix: "Sensor",
    },
    fields: [
      { key: "instanceName", label: "Instance Name", type: "text" },
      { key: "scanWindowMs", label: "Scan Window (ms)", type: "number", min: 10, step: 5 },
      { key: "scanIntervalMs", label: "Scan Interval (ms)", type: "number", min: 10, step: 5 },
      { key: "maxConnections", label: "Max Connections", type: "number", min: 1, step: 1 },
      { key: "filterNamePrefix", label: "Filter Name Prefix", type: "text" },
    ],
  },
  {
    id: "usb_cdc_acm",
    label: "USB CDC ACM",
    family: "USB",
    transport: "USB Device",
    summary: "Virtual COM port over USB for logs, shell, or app data channels.",
    defaults: {
      instanceName: "usb_cdc",
      usbNode: "",
      vendorId: "0x2FE3",
      productId: "0x0001",
      productString: "Zephyr CDC ACM",
      console: true,
      rxBufferSize: 512,
      txBufferSize: 512,
    },
    fields: [
      { key: "instanceName", label: "Instance Name", type: "text" },
      { key: "usbNode", label: "USB Controller", type: "select", optionsSource: "usb" },
      { key: "vendorId", label: "Vendor ID", type: "text" },
      { key: "productId", label: "Product ID", type: "text" },
      { key: "productString", label: "Product String", type: "text" },
      { key: "console", label: "Route Console / Shell", type: "checkbox" },
      { key: "rxBufferSize", label: "RX Buffer", type: "number", min: 64, step: 64 },
      { key: "txBufferSize", label: "TX Buffer", type: "number", min: 64, step: 64 },
    ],
  },
  {
    id: "usb_hid_keyboard",
    label: "USB HID Keyboard",
    family: "USB",
    transport: "USB Device",
    summary: "HID keyboard starter with configurable report rate and boot protocol support.",
    defaults: {
      instanceName: "usb_hid_kbd",
      usbNode: "",
      vendorId: "0x2FE3",
      productId: "0x0002",
      reportRateHz: 125,
      bootProtocol: true,
    },
    fields: [
      { key: "instanceName", label: "Instance Name", type: "text" },
      { key: "usbNode", label: "USB Controller", type: "select", optionsSource: "usb" },
      { key: "vendorId", label: "Vendor ID", type: "text" },
      { key: "productId", label: "Product ID", type: "text" },
      { key: "reportRateHz", label: "Report Rate (Hz)", type: "number", min: 1, step: 1 },
      { key: "bootProtocol", label: "Boot Protocol", type: "checkbox" },
    ],
  },
  {
    id: "usb_mass_storage",
    label: "USB Mass Storage",
    family: "USB",
    transport: "USB Device",
    summary: "Expose a disk backend such as RAM or flash as a USB mass-storage device.",
    defaults: {
      instanceName: "usb_msc",
      usbNode: "",
      diskPreset: "RAM",
      customDiskName: "RAM",
      inquiryVendorId: "ZEPHYR  ",
      inquiryProductId: "ZEPHYR USB DISK ",
      inquiryRevision: "0.01",
    },
    fields: [
      { key: "instanceName", label: "Instance Name", type: "text" },
      { key: "usbNode", label: "USB Controller", type: "select", optionsSource: "usb" },
      {
        key: "diskPreset",
        label: "Disk Backend",
        type: "select",
        options: [
          { value: "RAM", label: "RAM Disk" },
          { value: "FLASH", label: "Flash Disk" },
          { value: "SD", label: "SD Card" },
          { value: "SDMMC", label: "SDMMC" },
          { value: "custom", label: "Custom" },
        ],
      },
      { key: "customDiskName", label: "Custom Disk Name", type: "text", showWhen: { key: "diskPreset", equals: "custom" } },
      { key: "inquiryVendorId", label: "Inquiry Vendor ID", type: "text" },
      { key: "inquiryProductId", label: "Inquiry Product ID", type: "text" },
      { key: "inquiryRevision", label: "Inquiry Revision", type: "text" },
    ],
  },
  {
    id: "uart_shell_bridge",
    label: "UART Shell Bridge",
    family: "UART",
    transport: "Serial",
    summary: "Shell backend and line-oriented control channel over a UART instance.",
    defaults: {
      instanceName: "uart_shell",
      uartNode: "uart0",
      baudRate: 115200,
      shellPrompt: "device:~$",
      lineMode: true,
    },
    fields: [
      { key: "instanceName", label: "Instance Name", type: "text" },
      { key: "uartNode", label: "UART Node", type: "select", optionsSource: "uart" },
      { key: "baudRate", label: "Baud Rate", type: "number", min: 9600, step: 1200 },
      { key: "shellPrompt", label: "Shell Prompt", type: "text" },
      { key: "lineMode", label: "Line Mode", type: "checkbox" },
    ],
  },
];

let protocolEditorState = null;
let protocolEditorNextId = 1;

function protocolTemplate(templateId) {
  return PROTOCOL_EDITOR_TEMPLATES.find(template => template.id === templateId) || PROTOCOL_EDITOR_TEMPLATES[0];
}

function protocolInterfaceOptions(source) {
  if (!boardData || !Array.isArray(boardData.peripherals)) return [];
  const prefix = String(source || "").toLowerCase();
  return boardData.peripherals
    .filter(peripheral => String(peripheral.name || "").toLowerCase().startsWith(prefix))
    .map(peripheral => ({
      value: String(peripheral.name || ""),
      label: peripheral.display || peripheral.name || prefix,
      nodeRef: String(peripheral.dts_node || peripheral.name || ""),
      compatible: String(peripheral.compatible || ""),
    }))
    .filter(option => option.value)
    .sort((left, right) => left.label.localeCompare(right.label));
}

function protocolNormalizeEntry(entry, template) {
  const values = {
    ...cloneJson(template.defaults || {}),
    ...(entry.values || {}),
  };

  template.fields.forEach(field => {
    if (!field.optionsSource) return;
    const options = protocolInterfaceOptions(field.optionsSource);
    if (!options.length) {
      values[field.key] = "";
      return;
    }
    if (!options.some(option => option.value === values[field.key])) {
      values[field.key] = options[0].value;
    }
  });

  return {
    id: String(entry.id || protocolInstantiateEntry(template.id).id),
    templateId: template.id,
    enabled: entry.enabled !== false,
    values,
  };
}

function protocolSelectedInterface(field, values) {
  if (!field?.optionsSource) return null;
  return protocolInterfaceOptions(field.optionsSource).find(option => option.value === values?.[field.key]) || null;
}

function protocolSelectedNodeRef(entry, template) {
  const field = (template.fields || []).find(candidate => candidate.optionsSource);
  return protocolSelectedInterface(field, entry.values || {})?.nodeRef || "";
}

function protocolNodeLabel(nodeRef, fallback = "") {
  const raw = String(nodeRef || fallback || "").trim().replace(/^&/, "");
  const normalized = raw.replace(/[^A-Za-z0-9_]+/g, "_").replace(/^_+/, "");
  return normalized || lvglCodeSymbol(fallback || "node", "node");
}

function protocolNodeRef(nodeRef, fallback = "") {
  const label = protocolNodeLabel(nodeRef, fallback);
  return label ? `&${label}` : "";
}

function protocolMassStorageDiskName(values) {
  const preset = String(values?.diskPreset || "RAM").trim() || "RAM";
  if (preset === "custom") {
    return String(values?.customDiskName || "RAM").trim() || "RAM";
  }
  return preset;
}

function protocolInstantiateEntry(templateId, count = 1) {
  const template = protocolTemplate(templateId);
  const values = cloneJson(template.defaults || {});
  if (values.instanceName) {
    values.instanceName = `${values.instanceName}_${count}`;
  }
  return {
    id: `proto_${protocolEditorNextId++}`,
    templateId: template.id,
    enabled: true,
    values,
  };
}

function protocolDefaultState() {
  protocolEditorNextId = 1;
  const entry = protocolInstantiateEntry("bluetooth_le_peripheral", 1);
  return {
    selectedTemplateId: "bluetooth_le_peripheral",
    selectedEntryId: entry.id,
    previewTab: "prj_conf",
    entries: [entry],
  };
}

function protocolEnsureState() {
  if (!protocolEditorState || !Array.isArray(protocolEditorState.entries)) {
    protocolEditorState = protocolDefaultState();
  }

  const validPreviewTabs = new Set(["overlay", "prj_conf", "header", "code", "integration"]);
  const normalizedEntries = (protocolEditorState.entries || [])
    .filter(entry => entry && typeof entry === "object" && protocolTemplate(entry.templateId))
    .map(entry => protocolNormalizeEntry(entry, protocolTemplate(entry.templateId)));

  protocolEditorState = {
    selectedTemplateId: protocolTemplate(protocolEditorState.selectedTemplateId).id,
    selectedEntryId: protocolEditorState.selectedEntryId || normalizedEntries[0]?.id || "",
    previewTab: validPreviewTabs.has(protocolEditorState.previewTab) ? protocolEditorState.previewTab : "prj_conf",
    entries: normalizedEntries,
  };

  if (!protocolEditorState.entries.some(entry => entry.id === protocolEditorState.selectedEntryId)) {
    protocolEditorState.selectedEntryId = protocolEditorState.entries[0]?.id || "";
  }

  return protocolEditorState;
}

function protocolEntryRecord(entryId = "") {
  const state = protocolEnsureState();
  const entry = state.entries.find(item => item.id === (entryId || state.selectedEntryId)) || null;
  if (!entry) return null;
  return { entry, template: protocolTemplate(entry.templateId) };
}

function protocolEntryName(entry, template) {
  return String(entry?.values?.instanceName || template?.label || "protocol").trim();
}

function protocolActiveEntries() {
  return protocolEnsureState().entries.filter(entry => entry.enabled !== false);
}

function protocolBuildOverlay() {
  const activeEntries = protocolActiveEntries();
  const usbConsole = activeEntries.find(entry => entry.templateId === "usb_cdc_acm" && entry.values.console);
  const uartShell = protocolActiveEntries().find(entry => entry.templateId === "uart_shell_bridge");
  const blocks = [];
  const usbControllerBlocks = new Set();

  activeEntries
    .filter(entry => entry.templateId.startsWith("usb_"))
    .forEach(entry => {
      const template = protocolTemplate(entry.templateId);
      const controllerRef = protocolNodeRef(protocolSelectedNodeRef(entry, template), entry.values.usbNode || "usb0");
      if (!controllerRef) return;
      usbControllerBlocks.add(`${controllerRef} {\n  status = \"okay\";\n};`);
    });

  [...usbControllerBlocks].forEach(block => blocks.push(block));

  if (usbConsole) {
    const template = protocolTemplate(usbConsole.templateId);
    const nodeRef = protocolSelectedNodeRef(usbConsole, template);
    const controllerRef = protocolNodeRef(nodeRef, "usb0");
    blocks.push(`/* ${protocolEntryName(usbConsole, template)}: enable ${controllerRef || "the USB controller"} and route console and shell over CDC ACM. */\n/ {\n  chosen {\n    zephyr,console = &cdc_acm_uart0;\n    zephyr,shell-uart = &cdc_acm_uart0;\n  };\n};`);
  }
  if (uartShell) {
    const template = protocolTemplate(uartShell.templateId);
    const uartRef = protocolNodeRef(protocolSelectedNodeRef(uartShell, template), uartShell.values.uartNode || "uart0");
    blocks.push(`/* ${protocolEntryName(uartShell, template)}: bind shell backend to ${uartRef || "the selected UART"}. */\n/ {\n  chosen {\n    zephyr,shell-uart = ${uartRef || "&uart0"};\n  };\n};`);
  }

  return blocks.join("\n\n").trim();
}

function protocolPushUniqueLine(lines, seen, value) {
  if (!value || seen.has(value)) return;
  seen.add(value);
  lines.push(value);
}

function protocolBuildPrjConf() {
  const activeEntries = protocolActiveEntries();
  if (!activeEntries.length) return "";

  const lines = [];
  const seen = new Set();

  activeEntries.forEach(entry => {
    const values = entry.values || {};
    switch (entry.templateId) {
      case "bluetooth_le_peripheral":
        protocolPushUniqueLine(lines, seen, "CONFIG_BT=y");
        protocolPushUniqueLine(lines, seen, "CONFIG_BT_PERIPHERAL=y");
        protocolPushUniqueLine(lines, seen, "CONFIG_BT_DEVICE_NAME_DYNAMIC=y");
        protocolPushUniqueLine(lines, seen, `CONFIG_BT_DEVICE_NAME=${JSON.stringify(values.deviceName || "Zephyr Device")}`);
        protocolPushUniqueLine(lines, seen, `CONFIG_BT_L2CAP_TX_MTU=${Math.max(23, Number(values.mtu) || 247)}`);
        protocolPushUniqueLine(lines, seen, "CONFIG_BT_GATT_DYNAMIC_DB=y");
        if (values.security === "pairing" || values.security === "lesc") {
          protocolPushUniqueLine(lines, seen, "CONFIG_BT_SMP=y");
        }
        if (values.security === "lesc") {
          protocolPushUniqueLine(lines, seen, "CONFIG_BT_SIGNING=y");
        }
        break;
      case "bluetooth_central_scanner":
        protocolPushUniqueLine(lines, seen, "CONFIG_BT=y");
        protocolPushUniqueLine(lines, seen, "CONFIG_BT_CENTRAL=y");
        protocolPushUniqueLine(lines, seen, "CONFIG_BT_OBSERVER=y");
        protocolPushUniqueLine(lines, seen, `CONFIG_BT_MAX_CONN=${Math.max(1, Number(values.maxConnections) || 1)}`);
        break;
      case "usb_cdc_acm":
        protocolPushUniqueLine(lines, seen, "CONFIG_USB_DEVICE_STACK=y");
        protocolPushUniqueLine(lines, seen, "CONFIG_USB_CDC_ACM=y");
        protocolPushUniqueLine(lines, seen, "CONFIG_SERIAL=y");
        protocolPushUniqueLine(lines, seen, `CONFIG_USB_DEVICE_VID=${String(values.vendorId || "0x2FE3")}`);
        protocolPushUniqueLine(lines, seen, `CONFIG_USB_DEVICE_PID=${String(values.productId || "0x0001")}`);
        protocolPushUniqueLine(lines, seen, `CONFIG_USB_DEVICE_PRODUCT=${JSON.stringify(values.productString || "Zephyr CDC ACM")}`);
        protocolPushUniqueLine(lines, seen, `CONFIG_USB_CDC_ACM_RINGBUF_SIZE=${Math.max(64, Number(values.rxBufferSize) || 512)}`);
        if (values.console) {
          protocolPushUniqueLine(lines, seen, "CONFIG_UART_LINE_CTRL=y");
          protocolPushUniqueLine(lines, seen, "CONFIG_SHELL=y");
          protocolPushUniqueLine(lines, seen, "CONFIG_SHELL_BACKEND_SERIAL=y");
        }
        break;
      case "usb_hid_keyboard":
        protocolPushUniqueLine(lines, seen, "CONFIG_USB_DEVICE_STACK=y");
        protocolPushUniqueLine(lines, seen, "CONFIG_USB_HID_DEVICE=y");
        protocolPushUniqueLine(lines, seen, "CONFIG_INPUT=y");
        protocolPushUniqueLine(lines, seen, `CONFIG_USB_DEVICE_VID=${String(values.vendorId || "0x2FE3")}`);
        protocolPushUniqueLine(lines, seen, `CONFIG_USB_DEVICE_PID=${String(values.productId || "0x0002")}`);
        if (values.bootProtocol) {
          protocolPushUniqueLine(lines, seen, "CONFIG_USB_HID_BOOT_PROTOCOL=y");
        }
        break;
      case "usb_mass_storage": {
        const diskName = protocolMassStorageDiskName(values);
        protocolPushUniqueLine(lines, seen, "CONFIG_USB_DEVICE_STACK=y");
        protocolPushUniqueLine(lines, seen, "CONFIG_USB_MASS_STORAGE=y");
        protocolPushUniqueLine(lines, seen, "CONFIG_DISK_ACCESS=y");
        protocolPushUniqueLine(lines, seen, `CONFIG_MASS_STORAGE_DISK_NAME=${JSON.stringify(diskName)}`);
        protocolPushUniqueLine(lines, seen, `CONFIG_MASS_STORAGE_INQ_VENDOR_ID=${JSON.stringify(String(values.inquiryVendorId || "ZEPHYR  "))}`);
        protocolPushUniqueLine(lines, seen, `CONFIG_MASS_STORAGE_INQ_PRODUCT_ID=${JSON.stringify(String(values.inquiryProductId || "ZEPHYR USB DISK "))}`);
        protocolPushUniqueLine(lines, seen, `CONFIG_MASS_STORAGE_INQ_REVISION=${JSON.stringify(String(values.inquiryRevision || "0.01"))}`);
        break;
      }
      case "uart_shell_bridge":
        protocolPushUniqueLine(lines, seen, "CONFIG_SERIAL=y");
        protocolPushUniqueLine(lines, seen, "CONFIG_UART_INTERRUPT_DRIVEN=y");
        protocolPushUniqueLine(lines, seen, "CONFIG_SHELL=y");
        protocolPushUniqueLine(lines, seen, "CONFIG_SHELL_BACKEND_SERIAL=y");
        if (values.lineMode) {
          protocolPushUniqueLine(lines, seen, "CONFIG_SHELL_BACKEND_SERIAL_CHECK_DTR=y");
        }
        break;
      default:
        break;
    }
  });

  return lines.join("\n");
}

function protocolBuildHeader() {
  const activeEntries = protocolActiveEntries();
  if (!activeEntries.length) return "";
  const lines = [
    "// Generated by Zephyr Pin Configurator - Protocol Editor",
    "// Generated file: safe to overwrite when the protocol composition changes.",
    "#pragma once",
    "",
    "#include <zephyr/device.h>",
    "",
    "void protocol_stack_init(void);",
  ];

  activeEntries.forEach(entry => {
    lines.push(`void protocol_init_${lvglCodeSymbol(protocolEntryName(entry, protocolTemplate(entry.templateId)), "proto")}(void);`);
  });

  return lines.join("\n");
}

function protocolBuildCode() {
  const activeEntries = protocolActiveEntries();
  if (!activeEntries.length) return "";
  const lines = [
    "// Generated by Zephyr Pin Configurator - Protocol Editor",
    "// Generated file: safe to overwrite when the protocol composition changes.",
    "#include \"protocol_stack.h\"",
    "#include <zephyr/kernel.h>",
    "#include <zephyr/device.h>",
    "#include <zephyr/sys/printk.h>",
    "#include <zephyr/sys/util.h>",
    "",
  ];

  if (activeEntries.some(entry => entry.templateId.startsWith("bluetooth_"))) {
    lines.push("#include <zephyr/bluetooth/bluetooth.h>");
    lines.push("#include <zephyr/bluetooth/gap.h>");
  }
  if (activeEntries.some(entry => entry.templateId.startsWith("usb_"))) {
    lines.push("#include <zephyr/usb/usb_device.h>");
  }
  if (activeEntries.some(entry => entry.templateId === "uart_shell_bridge")) {
    lines.push("#include <zephyr/drivers/uart.h>");
  }
  if (lines[lines.length - 1] !== "") {
    lines.push("");
  }

  activeEntries.forEach(entry => {
    const template = protocolTemplate(entry.templateId);
    const values = entry.values || {};
    const symbol = lvglCodeSymbol(protocolEntryName(entry, template), "proto");
    const nodeRef = protocolSelectedNodeRef(entry, template);
    const nodeLabel = protocolNodeLabel(nodeRef, values.uartNode || values.usbNode || "proto");
    const diskName = entry.templateId === "usb_mass_storage" ? protocolMassStorageDiskName(values) : "";
    const summary = {
      bluetooth_le_peripheral: `Advertising ${values.deviceName || "device"} every ${Math.max(20, Number(values.advertisingIntervalMs) || 100)} ms with services: ${values.services || "custom GATT"}.`,
      bluetooth_central_scanner: `Scan interval ${Math.max(10, Number(values.scanIntervalMs) || 80)} ms, window ${Math.max(10, Number(values.scanWindowMs) || 60)} ms, max connections ${Math.max(1, Number(values.maxConnections) || 1)}.`,
      usb_cdc_acm: `Expose CDC ACM as ${values.productString || "Zephyr CDC ACM"} (${values.vendorId || "0x2FE3"}:${values.productId || "0x0001"}) on ${nodeRef || "the selected USB controller"}.`,
      usb_hid_keyboard: `Expose HID keyboard reports at ${Math.max(1, Number(values.reportRateHz) || 125)} Hz on ${nodeRef || "the selected USB controller"}.`,
      usb_mass_storage: `Expose disk backend ${diskName || "RAM"} as a USB mass-storage device on ${nodeRef || "the selected USB controller"}.`,
      uart_shell_bridge: `Route shell traffic over ${values.uartNode || "uart0"} at ${Math.max(9600, Number(values.baudRate) || 115200)} baud.`,
    }[entry.templateId] || template.summary;

    if (entry.templateId === "bluetooth_le_peripheral") {
      const advName = JSON.stringify(String(values.deviceName || "Zephyr Device"));
      lines.push(`static const struct bt_data ${symbol}_ad[] = {`);
      lines.push("    BT_DATA_BYTES(BT_DATA_FLAGS, (BT_LE_AD_GENERAL | BT_LE_AD_NO_BREDR)),");
      lines.push(`    BT_DATA(BT_DATA_NAME_COMPLETE, ${advName}, sizeof(${advName}) - 1),`);
      lines.push("};");
      lines.push("");
    }

    lines.push(`void protocol_init_${symbol}(void) {`);
    lines.push(`    /* ${summary} */`);
    if (entry.templateId === "bluetooth_le_peripheral") {
      lines.push("    int err = bt_enable(NULL);");
      lines.push("    if (err && err != -EALREADY) {");
      lines.push(`        printk(\"protocol: bt_enable failed for ${symbol} (%d)\\n\", err);`);
      lines.push("        return;");
      lines.push("    }");
      lines.push(`    (void)bt_set_name(${JSON.stringify(String(values.deviceName || "Zephyr Device"))});`);
      lines.push(`    static const struct bt_le_adv_param adv_param = BT_LE_ADV_PARAM_INIT(BT_LE_ADV_OPT_CONN, BT_GAP_MS_TO_ADV_INTERVAL(${Math.max(20, Number(values.advertisingIntervalMs) || 100)}), BT_GAP_MS_TO_ADV_INTERVAL(${Math.max(20, Number(values.advertisingIntervalMs) || 100)}), NULL);`);
      lines.push(`    err = bt_le_adv_start(&adv_param, ${symbol}_ad, ARRAY_SIZE(${symbol}_ad), NULL, 0);`);
      lines.push("    if (err) {");
      lines.push(`        printk(\"protocol: advertising start failed for ${symbol} (%d)\\n\", err);`);
      lines.push("    }");
    } else if (entry.templateId === "bluetooth_central_scanner") {
      lines.push("    int err = bt_enable(NULL);");
      lines.push("    if (err && err != -EALREADY) {");
      lines.push(`        printk(\"protocol: bt_enable failed for ${symbol} (%d)\\n\", err);`);
      lines.push("        return;");
      lines.push("    }");
      lines.push("    static const struct bt_le_scan_param scan_param = {");
      lines.push("        .type = BT_LE_SCAN_TYPE_ACTIVE,");
      lines.push("        .options = BT_LE_SCAN_OPT_NONE,");
      lines.push(`        .interval = BT_GAP_MS_TO_SCAN_INTERVAL(${Math.max(10, Number(values.scanIntervalMs) || 80)}),`);
      lines.push(`        .window = BT_GAP_MS_TO_SCAN_WINDOW(${Math.max(10, Number(values.scanWindowMs) || 60)}),`);
      lines.push("    };");
      lines.push("    err = bt_le_scan_start(&scan_param, NULL);");
      lines.push("    if (err) {");
      lines.push(`        printk(\"protocol: scan start failed for ${symbol} (%d)\\n\", err);`);
      lines.push("    }");
    } else if (entry.templateId.startsWith("usb_")) {
      if (!nodeRef) {
        lines.push("    /* No compatible USB controller was found on the active board. */");
        lines.push("    /* Select a board with a USB peripheral or extend the board definition before enabling this interface. */");
      } else {
        lines.push(`    const struct device *controller = DEVICE_DT_GET(DT_NODELABEL(${nodeLabel}));`);
        lines.push("    if (!device_is_ready(controller)) {");
        lines.push(`        printk(\"protocol: USB controller not ready for ${symbol}\\n\");`);
        lines.push("        return;");
        lines.push("    }");
        lines.push("    int err = usb_enable(NULL);");
        lines.push("    if (err && err != -EALREADY) {");
        lines.push(`        printk(\"protocol: usb_enable failed for ${symbol} (%d)\\n\", err);`);
        lines.push("        return;");
        lines.push("    }");
        if (entry.templateId === "usb_hid_keyboard") {
          lines.push(`        printk(\"protocol: HID keyboard ${symbol} ready at %d Hz\\n\", ${Math.max(1, Number(values.reportRateHz) || 125)});`);
        } else if (entry.templateId === "usb_mass_storage") {
          lines.push(`        printk(\"protocol: USB MSC ${symbol} ready with disk backend %s on ${nodeLabel}\\n\", ${JSON.stringify(diskName || "RAM")});`);
          lines.push("        /* TODO: mount and prepare the selected disk backend before exposing it to the host. */");
        } else {
          lines.push(`        printk(\"protocol: CDC ACM ${symbol} ready on ${nodeLabel}\\n\");`);
        }
      }
    } else if (entry.templateId === "uart_shell_bridge") {
      lines.push(`    const struct device *uart_dev = DEVICE_DT_GET(DT_NODELABEL(${nodeLabel}));`);
      lines.push("    if (!device_is_ready(uart_dev)) {");
      lines.push(`        printk(\"protocol: UART device not ready for ${symbol}\\n\");`);
      lines.push("        return;");
      lines.push("    }");
      lines.push("    struct uart_config config = {");
      lines.push(`        .baudrate = ${Math.max(9600, Number(values.baudRate) || 115200)},`);
      lines.push("        .parity = UART_CFG_PARITY_NONE,");
      lines.push("        .stop_bits = UART_CFG_STOP_BITS_1,");
      lines.push("        .data_bits = UART_CFG_DATA_BITS_8,");
      lines.push("        .flow_ctrl = UART_CFG_FLOW_CTRL_NONE,");
      lines.push("    };");
      lines.push("    int err = uart_configure(uart_dev, &config);");
      lines.push("    if (err) {");
      lines.push(`        printk(\"protocol: uart_configure failed for ${symbol} (%d)\\n\", err);`);
      lines.push("        return;");
      lines.push("    }");
      lines.push(`    printk(\"protocol: shell bridge ${symbol} ready on ${nodeLabel}\\n\");`);
    } else {
      lines.push("    /* TODO: add protocol-specific init here. */");
    }
    lines.push("}");
    lines.push("");
  });

  lines.push("void protocol_stack_init(void) {");
  activeEntries.forEach(entry => {
    lines.push(`    protocol_init_${lvglCodeSymbol(protocolEntryName(entry, protocolTemplate(entry.templateId)), "proto")}();`);
  });
  lines.push("}");

  return lines.join("\n");
}

function protocolBuildIntegrationGuide() {
  const activeEntries = protocolActiveEntries();
  if (!activeEntries.length) return "";
  const lines = [
    "# Protocol Stack Integration Guide",
    "",
    "## Generated Files",
    "",
    "- `protocol_stack.h`: public init entry points for the composed interfaces.",
    "- `protocol_stack.c`: starter init stubs for each enabled interface.",
    "",
    "## Selected Interfaces",
    "",
  ];

  activeEntries.forEach(entry => {
    const template = protocolTemplate(entry.templateId);
    const nodeRef = protocolSelectedNodeRef(entry, template);
    lines.push(`- \`${protocolEntryName(entry, template)}\` (${template.label}) via ${template.transport}${nodeRef ? ` on \`${nodeRef}\`` : ""}.`);
  });

  lines.push("");
  lines.push("## Build Integration");
  lines.push("");
  lines.push("```cmake");
  lines.push("target_sources(app PRIVATE src/protocol_stack.c)");
  lines.push("```");
  lines.push("");
  lines.push("## Startup");
  lines.push("");
  lines.push("```c");
  lines.push("#include \"protocol_stack.h\"");
  lines.push("");
  lines.push("void main(void)");
  lines.push("{");
  lines.push("    protocol_stack_init();");
  lines.push("}");
  lines.push("```");
  lines.push("");
  lines.push("## Notes");
  lines.push("");
  lines.push("- The generated code now emits Zephyr API starter calls for Bluetooth, USB, and UART bring-up; adapt callbacks and error handling for your application.");
  lines.push("- USB Mass Storage uses the Zephyr `USB_MASS_STORAGE` class with a selectable disk backend name such as `RAM` or a flash-backed drive.");
  lines.push("- USB and UART entries bind to real board peripheral instances selected in the editor, so verify the chosen DTS node labels match your board description.");
  return lines.join("\n");
}

function protocolSyncGeneratedOutputs() {
  generatedFragments.protocols = {
    overlay: protocolBuildOverlay(),
    prj_conf: protocolBuildPrjConf(),
    code: protocolBuildCode(),
    header: protocolBuildHeader(),
    integration: protocolBuildIntegrationGuide(),
  };
  refreshGeneratedOutputs();
}

function protocolPreviewContent() {
  const state = protocolEnsureState();
  switch (state.previewTab) {
    case "overlay":
      return generatedFragments.protocols.overlay || "Add USB console or UART shell interfaces to generate a device-tree snippet.";
    case "header":
      return generatedFragments.protocols.header || "Add an enabled interface to generate protocol stack declarations.";
    case "code":
      return generatedFragments.protocols.code || "Add an enabled interface to generate starter init code.";
    case "integration":
      return generatedFragments.protocols.integration || "Add an enabled interface to generate an integration guide.";
    case "prj_conf":
    default:
      return generatedFragments.protocols.prj_conf || "Add an enabled interface to generate Zephyr Kconfig settings.";
  }
}

function protocolRenderCatalog() {
  const state = protocolEnsureState();
  const catalog = $("#protoCatalog");
  if (!catalog) return;
  catalog.innerHTML = PROTOCOL_EDITOR_TEMPLATES.map(template => `
    <div class="proto-editor-card${state.selectedTemplateId === template.id ? " active" : ""}" data-proto-template="${template.id}">
      <div class="proto-editor-card-top">
        <div>
          <div class="proto-editor-card-title">${escapeHtml(template.label)}</div>
          <div class="proto-editor-card-meta">${escapeHtml(template.family)} • ${escapeHtml(template.transport)}</div>
        </div>
        <button class="btn proto-editor-card-btn" data-proto-add="${template.id}">Add</button>
      </div>
      <div class="proto-editor-card-summary">${escapeHtml(template.summary)}</div>
    </div>
  `).join("");

  catalog.querySelectorAll("[data-proto-template]").forEach(card => {
    card.addEventListener("click", event => {
      if (event.target.closest("[data-proto-add]")) return;
      state.selectedTemplateId = card.dataset.protoTemplate;
      protocolRenderCatalog();
    });
  });
  catalog.querySelectorAll("[data-proto-add]").forEach(button => {
    button.addEventListener("click", event => {
      event.stopPropagation();
      protocolAddEntry(button.dataset.protoAdd);
    });
  });
}

function protocolRenderComposer() {
  const state = protocolEnsureState();
  const composition = $("#protoComposition");
  const meta = $("#protoSummaryMeta");
  if (!composition) return;

  if (meta) {
    const enabledCount = protocolActiveEntries().length;
    meta.textContent = `${state.entries.length} interface${state.entries.length === 1 ? "" : "s"} in composition • ${enabledCount} enabled`;
  }

  if (!state.entries.length) {
    composition.innerHTML = '<div class="proto-editor-empty">Choose a protocol template from the library to start composing your communication stack.</div>';
    return;
  }

  composition.innerHTML = state.entries.map(entry => {
    const template = protocolTemplate(entry.templateId);
    return `
      <div class="proto-editor-instance${entry.id === state.selectedEntryId ? " active" : ""}" data-proto-entry="${entry.id}">
        <div class="proto-editor-instance-head">
          <div>
            <div class="proto-editor-instance-title">${escapeHtml(protocolEntryName(entry, template))}</div>
            <div class="proto-editor-instance-meta">${escapeHtml(template.label)} • ${escapeHtml(template.transport)}</div>
          </div>
          <label class="proto-editor-toggle">
            <input type="checkbox" data-proto-enabled="${entry.id}" ${entry.enabled ? "checked" : ""}>
            <span>${entry.enabled ? "Enabled" : "Disabled"}</span>
          </label>
        </div>
        <div class="proto-editor-instance-summary">${escapeHtml(template.summary)}</div>
        <div class="proto-editor-instance-actions">
          <button class="btn" data-proto-remove="${entry.id}">Remove</button>
        </div>
      </div>
    `;
  }).join("");

  composition.querySelectorAll("[data-proto-entry]").forEach(card => {
    card.addEventListener("click", event => {
      if (event.target.closest("button") || event.target.closest("input")) return;
      state.selectedEntryId = card.dataset.protoEntry;
      protocolRender();
    });
  });
  composition.querySelectorAll("[data-proto-enabled]").forEach(input => {
    input.addEventListener("change", event => {
      const record = protocolEntryRecord(event.target.dataset.protoEnabled);
      if (!record) return;
      record.entry.enabled = event.target.checked;
      protocolSyncGeneratedOutputs();
      protocolRender();
    });
  });
  composition.querySelectorAll("[data-proto-remove]").forEach(button => {
    button.addEventListener("click", event => {
      event.stopPropagation();
      protocolRemoveEntry(button.dataset.protoRemove);
    });
  });
}

function protocolRenderProps() {
  const panel = $("#protoPropsPanel");
  if (!panel) return;
  const record = protocolEntryRecord();
  if (!record) {
    panel.className = "proto-editor-empty";
    panel.textContent = "Select an interface instance to adjust transport-specific settings.";
    return;
  }

  const { entry, template } = record;
  panel.className = "";
  panel.innerHTML = `
    <div class="proto-editor-form">
      ${template.fields.map(field => {
        if (field.showWhen && entry.values?.[field.showWhen.key] !== field.showWhen.equals) {
          return "";
        }
        const value = entry.values[field.key];
        if (field.optionsSource) {
          const options = protocolInterfaceOptions(field.optionsSource);
          return `
            <div class="proto-editor-field full">
              <label>${escapeHtml(field.label)}</label>
              <select data-proto-field="${field.key}">
                ${options.length
                  ? options.map(option => `<option value="${escapeHtml(option.value)}" ${String(value) === String(option.value) ? "selected" : ""}>${escapeHtml(option.label)}${option.nodeRef ? ` (${escapeHtml(option.nodeRef)})` : ""}</option>`).join("")
                  : '<option value="">No compatible board peripheral found</option>'}
              </select>
              ${options.length ? "" : `<div class="proto-editor-note">The active board ${escapeHtml(boardData?.board || "") || ""} does not expose a compatible ${escapeHtml(field.label.toLowerCase())} peripheral in its board model.</div>`}
            </div>`;
        }
        if (field.type === "select") {
          return `
            <div class="proto-editor-field${field.type === "textarea" ? " full" : ""}">
              <label>${escapeHtml(field.label)}</label>
              <select data-proto-field="${field.key}">
                ${field.options.map(option => `<option value="${escapeHtml(option.value)}" ${String(value) === String(option.value) ? "selected" : ""}>${escapeHtml(option.label)}</option>`).join("")}
              </select>
            </div>`;
        }
        if (field.type === "textarea") {
          return `
            <div class="proto-editor-field full">
              <label>${escapeHtml(field.label)}</label>
              <textarea data-proto-field="${field.key}">${escapeHtml(value || "")}</textarea>
            </div>`;
        }
        if (field.type === "checkbox") {
          return `
            <div class="proto-editor-field full proto-editor-field-check">
              <label><input type="checkbox" data-proto-field="${field.key}" ${value ? "checked" : ""}> ${escapeHtml(field.label)}</label>
            </div>`;
        }
        return `
          <div class="proto-editor-field">
            <label>${escapeHtml(field.label)}</label>
            <input type="${field.type}" data-proto-field="${field.key}" value="${escapeHtml(value ?? "")}" ${field.min !== undefined ? `min="${field.min}"` : ""} ${field.step !== undefined ? `step="${field.step}"` : ""}>
          </div>`;
      }).join("")}
    </div>
  `;
}

function fieldEventName(input) {
  if (input.type === "checkbox" || input.tagName === "SELECT") return "change";
  return "input";
}

function protocolApplyFieldChange(input) {
  if (!input?.dataset?.protoField) return;
  const record = protocolEntryRecord();
  if (!record) return;
  const { entry, template } = record;
  const field = template.fields.find(item => item.key === input.dataset.protoField);
  if (!field) return;
  if (field.type === "checkbox") {
    entry.values[field.key] = !!input.checked;
  } else if (field.type === "number") {
    entry.values[field.key] = Number(input.value) || 0;
  } else {
    entry.values[field.key] = input.value;
  }
  protocolSyncGeneratedOutputs();
  protocolRender();
}

function protocolRenderPreview() {
  const state = protocolEnsureState();
  const tabs = $$("[data-proto-preview]");
  const pre = $("#protoPreviewPre");
  tabs.forEach(tab => tab.classList.toggle("active", tab.dataset.protoPreview === state.previewTab));
  if (pre) {
    pre.textContent = protocolPreviewContent();
  }
}

function protocolRender() {
  protocolEnsureState();
  protocolRenderCatalog();
  protocolRenderComposer();
  protocolRenderProps();
  protocolRenderPreview();
  interruptRefreshIfVisible();
}

function protocolAddEntry(templateId) {
  const state = protocolEnsureState();
  const count = state.entries.filter(entry => entry.templateId === templateId).length + 1;
  const entry = protocolInstantiateEntry(templateId, count);
  state.entries.push(entry);
  state.selectedTemplateId = templateId;
  state.selectedEntryId = entry.id;
  protocolSyncGeneratedOutputs();
  protocolRender();
}

function protocolRemoveEntry(entryId) {
  const state = protocolEnsureState();
  state.entries = state.entries.filter(entry => entry.id !== entryId);
  if (state.selectedEntryId === entryId) {
    state.selectedEntryId = state.entries[0]?.id || "";
  }
  protocolSyncGeneratedOutputs();
  protocolRender();
}

function protocolReset() {
  protocolEditorState = protocolDefaultState();
  protocolSyncGeneratedOutputs();
  protocolRender();
}

function protocolSerializeState() {
  return cloneJson(protocolEnsureState());
}

function protocolRestoreState(nextState) {
  protocolEditorState = cloneJson(nextState || protocolDefaultState());
  const ids = (protocolEditorState.entries || []).map(entry => {
    const match = String(entry.id || "").match(/_(\d+)$/);
    return match ? Number(match[1]) + 1 : 1;
  });
  protocolEditorNextId = Math.max(1, ...ids, 1);
  protocolSyncGeneratedOutputs();
  protocolRender();
}

function protocolInit() {
  if (!$("#protoCatalog")) return;
  $("#protoPropsPanel")?.addEventListener("input", event => {
    const input = event.target.closest("[data-proto-field]");
    if (!input || fieldEventName(input) !== "input") return;
    protocolApplyFieldChange(input);
  });
  $("#protoPropsPanel")?.addEventListener("change", event => {
    const input = event.target.closest("[data-proto-field]");
    if (!input || fieldEventName(input) !== "change") return;
    protocolApplyFieldChange(input);
  });
  $("#protoBtnGenerate")?.addEventListener("click", () => {
    protocolSyncGeneratedOutputs();
    protocolRenderPreview();
    toast("Generated protocol stack starter files");
  });
  $("#protoBtnReset")?.addEventListener("click", protocolReset);
  $$("[data-proto-preview]").forEach(button => {
    button.addEventListener("click", () => {
      const state = protocolEnsureState();
      state.previewTab = button.dataset.protoPreview;
      protocolRenderPreview();
    });
  });
  protocolEnsureState();
  protocolSyncGeneratedOutputs();
  protocolRender();
}
