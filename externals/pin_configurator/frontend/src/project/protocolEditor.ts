export type ProtocolFieldType = "text" | "number" | "select" | "textarea" | "checkbox";

export interface ProtocolTemplateOption {
  value: string;
  label: string;
}

export interface ProtocolTemplateField {
  key: string;
  label: string;
  type: ProtocolFieldType;
  min?: number;
  step?: number;
  options?: ProtocolTemplateOption[];
}

export type ProtocolFieldValue = string | number | boolean;

export interface ProtocolEntry {
  id: string;
  templateId: string;
  enabled: boolean;
  values: Record<string, ProtocolFieldValue>;
}

export type ProtocolPreviewTab = "overlay" | "prj_conf" | "header" | "code" | "integration";

export interface ProtocolEditorDocument {
  selectedTemplateId: string;
  selectedEntryId: string;
  previewTab: ProtocolPreviewTab;
  entries: ProtocolEntry[];
}

export interface ProtocolTemplate {
  id: string;
  label: string;
  family: string;
  transport: string;
  summary: string;
  defaults: Record<string, ProtocolFieldValue>;
  fields: ProtocolTemplateField[];
}

export const PROTOCOL_EDITOR_TEMPLATES: ProtocolTemplate[] = [
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
      vendorId: "0x2FE3",
      productId: "0x0001",
      productString: "Zephyr CDC ACM",
      console: true,
      rxBufferSize: 512,
      txBufferSize: 512,
    },
    fields: [
      { key: "instanceName", label: "Instance Name", type: "text" },
      { key: "vendorId", label: "Vendor ID", type: "text" },
      { key: "productId", label: "Product ID", type: "text" },
      { key: "productString", label: "Product String", type: "text" },
      { key: "console", label: "Route Console / Shell", type: "checkbox" },
      { key: "rxBufferSize", label: "RX Buffer", type: "number", min: 64, step: 64 },
      { key: "txBufferSize", label: "TX Buffer", type: "number", min: 64, step: 64 },
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
      { key: "uartNode", label: "UART Node", type: "text" },
      { key: "baudRate", label: "Baud Rate", type: "number", min: 9600, step: 1200 },
      { key: "shellPrompt", label: "Shell Prompt", type: "text" },
      { key: "lineMode", label: "Line Mode", type: "checkbox" },
    ],
  },
];

function protocolTemplate(templateId?: string | null): ProtocolTemplate {
  return PROTOCOL_EDITOR_TEMPLATES.find((template) => template.id === templateId) ?? PROTOCOL_EDITOR_TEMPLATES[0];
}

function instantiateProtocolEntry(templateId: string, count: number): ProtocolEntry {
  const template = protocolTemplate(templateId);
  const values = { ...template.defaults };
  if (typeof values.instanceName === "string" && values.instanceName) {
    values.instanceName = `${values.instanceName}_${count}`;
  }

  return {
    id: `proto_${template.id}_${count}`,
    templateId: template.id,
    enabled: true,
    values,
  };
}

export function createDefaultProtocolEditorDocument(): ProtocolEditorDocument {
  const initialEntry = instantiateProtocolEntry("bluetooth_le_peripheral", 1);

  return {
    selectedTemplateId: initialEntry.templateId,
    selectedEntryId: initialEntry.id,
    previewTab: "prj_conf",
    entries: [initialEntry],
  };
}

export function normalizeProtocolEditorDocument(document?: Partial<ProtocolEditorDocument> | null): ProtocolEditorDocument {
  const source = document ?? {};
  const base = createDefaultProtocolEditorDocument();
  const entries = Array.isArray(source.entries)
    ? source.entries
        .filter((entry): entry is ProtocolEntry => Boolean(entry && typeof entry === "object"))
        .map((entry) => {
          const template = protocolTemplate(entry.templateId);
          return {
            id: String(entry.id || instantiateProtocolEntry(template.id, 1).id),
            templateId: template.id,
            enabled: entry.enabled !== false,
            values: {
              ...template.defaults,
              ...(entry.values ?? {}),
            },
          };
        })
    : base.entries;

  const selectedTemplateId = protocolTemplate(String(source.selectedTemplateId ?? base.selectedTemplateId)).id;
  const selectedEntryId = entries.find((entry) => entry.id === source.selectedEntryId)?.id ?? entries[0]?.id ?? "";
  const previewTab = ["overlay", "prj_conf", "header", "code", "integration"].includes(String(source.previewTab))
    ? (String(source.previewTab) as ProtocolPreviewTab)
    : base.previewTab;

  return {
    selectedTemplateId,
    selectedEntryId,
    previewTab,
    entries,
  };
}

export function selectedProtocolEntry(document: ProtocolEditorDocument): ProtocolEntry | null {
  return document.entries.find((entry) => entry.id === document.selectedEntryId) ?? document.entries[0] ?? null;
}

export function addProtocolEntry(document: ProtocolEditorDocument, templateId: string): ProtocolEditorDocument {
  const next = normalizeProtocolEditorDocument(document);
  const count = next.entries.filter((entry) => entry.templateId === templateId).length + 1;
  const entry = instantiateProtocolEntry(templateId, count);

  return {
    ...next,
    selectedTemplateId: templateId,
    selectedEntryId: entry.id,
    entries: [...next.entries, entry],
  };
}

export function removeProtocolEntry(document: ProtocolEditorDocument, entryId: string): ProtocolEditorDocument {
  const nextEntries = document.entries.filter((entry) => entry.id !== entryId);
  const selectedEntryId = nextEntries.find((entry) => entry.id === document.selectedEntryId)?.id ?? nextEntries[0]?.id ?? "";

  return normalizeProtocolEditorDocument({
    ...document,
    selectedEntryId,
    entries: nextEntries,
  });
}

export function selectProtocolEntry(document: ProtocolEditorDocument, entryId: string): ProtocolEditorDocument {
  return normalizeProtocolEditorDocument({
    ...document,
    selectedEntryId: entryId,
  });
}

export function updateProtocolEntryValue(
  document: ProtocolEditorDocument,
  entryId: string,
  fieldKey: string,
  value: ProtocolFieldValue,
): ProtocolEditorDocument {
  return normalizeProtocolEditorDocument({
    ...document,
    entries: document.entries.map((entry) =>
      entry.id === entryId
        ? {
            ...entry,
            values: {
              ...entry.values,
              [fieldKey]: value,
            },
          }
        : entry,
    ),
  });
}

export function toggleProtocolEntry(document: ProtocolEditorDocument, entryId: string, enabled: boolean): ProtocolEditorDocument {
  return normalizeProtocolEditorDocument({
    ...document,
    entries: document.entries.map((entry) => (entry.id === entryId ? { ...entry, enabled } : entry)),
  });
}

export function protocolTemplateById(templateId?: string | null): ProtocolTemplate {
  return protocolTemplate(templateId);
}
