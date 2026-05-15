import { protocolTemplateById, type ProtocolEntry } from "../../project/protocolEditor";
import type { ProjectDocument } from "../../project/projectDocument";
import type { ClockConfiguratorPresenter } from "../clock/clockConfiguratorPresenter";
import type { ModuleConfiguratorPresenter } from "../modules/moduleConfiguratorPresenter";

export interface InterruptItemViewModel {
  id: string;
  title: string;
  category: "Protocol" | "Module" | "Clock";
  source: string;
  reason: string;
  impact: string;
  priorityLabel: string;
  severity: "stable" | "moderate" | "attention";
}

export interface InterruptConfiguratorPresenter {
  items: InterruptItemViewModel[];
  summary: string;
}

const INTERRUPT_PRIORITY_CANDIDATES: Record<string, string[]> = {
  uart: ["CONFIG_SERIAL_INIT_PRIORITY"],
  spi: ["CONFIG_SPI_INIT_PRIORITY"],
  i2c: ["CONFIG_I2C_INIT_PRIORITY"],
  gpio: ["CONFIG_GPIO_INIT_PRIORITY"],
  usb: ["CONFIG_USB_DEVICE_INIT_PRIORITY", "CONFIG_USB_NRFX_INIT_PRIORITY", "CONFIG_USB_DC_STM32_PRIORITY"],
  system: ["CONFIG_SYSTEM_CLOCK_INIT_PRIORITY"],
};

function interruptFamilyFromTemplate(entry: ProtocolEntry): string {
  if (entry.templateId === "uart_shell_bridge") {
    return "uart";
  }
  if (entry.templateId.startsWith("usb_")) {
    return "usb";
  }
  if (entry.templateId.startsWith("spi_")) {
    return "spi";
  }
  if (entry.templateId.startsWith("i2c_")) {
    return "i2c";
  }
  return "system";
}

function interruptSeverity(score: number): InterruptItemViewModel["severity"] {
  if (score >= 3) {
    return "attention";
  }
  if (score >= 2) {
    return "moderate";
  }
  return "stable";
}

function priorityLabelForFamily(family: string, modulePresenter: ModuleConfiguratorPresenter): string {
  const candidates = INTERRUPT_PRIORITY_CANDIDATES[family] ?? [];
  for (const key of candidates) {
    const matchedDefinition = modulePresenter.definitions.find((definition) => {
      return definition.categories.some((category) => category.options.some((option) => option.key === key));
    });
    if (!matchedDefinition) {
      continue;
    }

    const currentValue = modulePresenter.valuesById[matchedDefinition.id]?.[key];
    if (currentValue !== undefined) {
      return `${key}=${currentValue}`;
    }
    return key;
  }

  return "No mapped init priority";
}

function protocolInterruptItems(projectDocument: ProjectDocument, modulePresenter: ModuleConfiguratorPresenter): InterruptItemViewModel[] {
  return projectDocument.protocol_editor.entries
    .filter((entry) => entry.enabled !== false)
    .map((entry) => {
      const template = protocolTemplateById(entry.templateId);
      const instanceName = typeof entry.values.instanceName === "string" && entry.values.instanceName.trim()
        ? entry.values.instanceName.trim()
        : template.label;
      const family = interruptFamilyFromTemplate(entry);

      if (entry.templateId.startsWith("bluetooth_")) {
        return {
          id: `protocol:${entry.id}`,
          title: instanceName,
          category: "Protocol",
          source: template.label,
          reason: "Bluetooth traffic depends on time-sensitive radio events and controller callbacks.",
          impact: "Connection intervals and scan windows can affect responsiveness and power.",
          priorityLabel: "Controller-defined radio timing",
          severity: interruptSeverity(2),
        } satisfies InterruptItemViewModel;
      }

      return {
        id: `protocol:${entry.id}`,
        title: instanceName,
        category: "Protocol",
        source: template.label,
        reason: `${template.label} enables interrupt-driven communication paths for the active workspace.`,
        impact: "Driver interrupts can compete with other startup and runtime activity during bursts.",
        priorityLabel: priorityLabelForFamily(family, modulePresenter),
        severity: interruptSeverity(entry.templateId === "uart_shell_bridge" ? 3 : 2),
      } satisfies InterruptItemViewModel;
    });
}

function moduleInterruptItems(modulePresenter: ModuleConfiguratorPresenter): InterruptItemViewModel[] {
  return modulePresenter.definitions.flatMap((definition) => {
    const moduleValues = modulePresenter.valuesById[definition.id] ?? {};
    return definition.categories.flatMap((category) => {
      return category.options.flatMap((option) => {
        const text = `${option.key} ${option.label || ""} ${option.help || ""}`;
        const matchesInterrupt = /(interrupt|irq)/i.test(text);
        const matchesPriority = /_INIT_PRIORITY$/i.test(option.key);
        if (!matchesInterrupt && !matchesPriority) {
          return [];
        }

        const currentValue = moduleValues[option.key] ?? option.default;
        const changed = String(currentValue) !== String(option.default);
        const enabled = option.type === "bool" ? currentValue === true : String(currentValue).trim().length > 0;

        if (matchesInterrupt && !enabled) {
          return [];
        }
        if (matchesPriority && !changed) {
          return [];
        }

        return [{
          id: `module:${definition.id}:${option.key}`,
          title: `${definition.name} - ${option.label || option.key}`,
          category: "Module",
          source: definition.id,
          reason: matchesPriority
            ? `Priority override detected: ${option.key}=${currentValue}.`
            : `${option.label || option.key} is enabled in typed module configuration.`,
          impact: matchesPriority
            ? "Changing init priority can alter startup order relative to other drivers and services."
            : "Interrupt-oriented module features increase ISR or deferred-work activity when active.",
          priorityLabel: matchesPriority ? `${option.key}=${currentValue}` : "Module-controlled",
          severity: interruptSeverity(matchesPriority ? 2 : 3),
        } satisfies InterruptItemViewModel];
      });
    });
  });
}

function clockInterruptItems(clockPresenter: ClockConfiguratorPresenter): InterruptItemViewModel[] {
  return clockPresenter.warnings.map((warning, index) => ({
    id: `clock:${index}`,
    title: `Clock warning ${index + 1}`,
    category: "Clock",
    source: clockPresenter.currentTree?.name || "Clock tree",
    reason: warning,
    impact: "Clock-path warnings can affect interrupt cadence, timeout assumptions, and peripheral servicing stability.",
    priorityLabel: "Clock-derived timing",
    severity: interruptSeverity(2),
  }));
}

export function createInterruptConfiguratorPresenter(projectDocument: ProjectDocument, modulePresenter: ModuleConfiguratorPresenter, clockPresenter: ClockConfiguratorPresenter): InterruptConfiguratorPresenter {
  const items = [
    ...protocolInterruptItems(projectDocument, modulePresenter),
    ...moduleInterruptItems(modulePresenter),
    ...clockInterruptItems(clockPresenter),
  ].sort((left, right) => left.title.localeCompare(right.title));

  return {
    items,
    summary: items.length
      ? `${items.length} interrupt-sensitive workflow item${items.length === 1 ? "" : "s"} surfaced by typed presenters.`
      : "No interrupt-sensitive workflows are currently surfaced by the typed presenter set.",
  };
}