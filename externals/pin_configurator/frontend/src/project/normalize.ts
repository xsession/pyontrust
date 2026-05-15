import { createDefaultProtocolEditorDocument, normalizeProtocolEditorDocument } from "./protocolEditor";
import {
  normalizeExternalDeviceStates,
  normalizePeripheralCoreStates,
  normalizePeripheralEnabledStates,
  normalizePinStates,
} from "./legacyHardwareState";
import type { PersistedProjectDocumentDto, ProjectFileLoadResponseDto } from "./dto";
import { PROJECT_FILE_VERSION, type ProjectDocument, type ProjectDocumentInput, type RenodeProfile } from "./types";

function asRecord(value: unknown): Record<string, unknown> {
  return value && typeof value === "object" && !Array.isArray(value) ? (value as Record<string, unknown>) : {};
}

function normalizeText(value: unknown, fallback = ""): string {
  if (typeof value === "string") {
    return value;
  }

  if (typeof value === "number" || typeof value === "boolean" || typeof value === "bigint") {
    return String(value);
  }

  return fallback;
}

function normalizeUnknownList(value: unknown): unknown[] {
  return Array.isArray(value) ? Array.from(value as readonly unknown[]) : [];
}

function normalizeVersion(value: unknown): number {
  const numericVersion = Number(value);
  if (!Number.isFinite(numericVersion) || numericVersion < 1) {
    return PROJECT_FILE_VERSION;
  }

  return Math.trunc(numericVersion);
}

const renodeDefaultsByBoard: Record<string, Pick<RenodeProfile, "enabled" | "platform" | "uart">> = {
  lp_mspm0g3507: {
    enabled: true,
    platform: "platforms/boards/ti/lp_mspm0g3507.repl",
    uart: "sysbus.uart0",
  },
  rpi_pico: {
    enabled: true,
    platform: "platforms/cpus/raspberrypi/rp2040.repl",
    uart: "sysbus.uart0",
  },
};

export function defaultRenodeProfile(boardId: string): RenodeProfile {
  const defaults = renodeDefaultsByBoard[boardId] ?? {
    enabled: false,
    platform: "",
    uart: "sysbus.uart0",
  };

  return {
    enabled: defaults.enabled,
    platform: defaults.platform,
    resc: "",
    robot: "",
    uart: defaults.uart,
    boot_line: "Pin Configurator demo boot",
    appbench_target: "appbench",
    robot_target: "robotbench",
  };
}

export function createEmptyProjectDocument(): ProjectDocument {
  return {
    version: PROJECT_FILE_VERSION,
    board_id: "",
    pin_states: {},
    periph_states: {},
    periph_core_states: {},
    external_device_states: {},
    protocol_editor: createDefaultProtocolEditorDocument(),
    lvgl_layout: {},
    generated_overlay: "",
    generated_conf: "",
    generated_fragments: {},
    sensor_jobs: [],
    sensor_selected: "",
    mcu_jobs: [],
    mcu_selected: "",
    renode: defaultRenodeProfile(""),
    tabs: {},
  };
}

export function migrateProjectDocumentInput(document?: ProjectDocumentInput | PersistedProjectDocumentDto | null): ProjectDocumentInput {
  const source: ProjectDocumentInput | PersistedProjectDocumentDto = document ?? {};

  return {
    ...source,
    version: normalizeVersion(source.version),
  };
}

export function normalizeProjectDocument(document?: ProjectDocumentInput | PersistedProjectDocumentDto | null): ProjectDocument {
  const source = migrateProjectDocumentInput(document);
  const base = createEmptyProjectDocument();
  const boardId = normalizeText(source.board_id, base.board_id);
  const renodeDefaults = defaultRenodeProfile(boardId);
  const renodeSource = asRecord(source.renode);

  return {
    version: normalizeVersion(source.version ?? base.version),
    board_id: boardId,
    pin_states: normalizePinStates(source.pin_states ?? base.pin_states),
    periph_states: normalizePeripheralEnabledStates(source.periph_states ?? base.periph_states),
    periph_core_states: normalizePeripheralCoreStates(source.periph_core_states ?? base.periph_core_states),
    external_device_states: normalizeExternalDeviceStates(source.external_device_states ?? base.external_device_states),
    protocol_editor: normalizeProtocolEditorDocument(source.protocol_editor),
    lvgl_layout: { ...asRecord(source.lvgl_layout ?? base.lvgl_layout) },
    generated_overlay: normalizeText(source.generated_overlay, base.generated_overlay),
    generated_conf: normalizeText(source.generated_conf, base.generated_conf),
    generated_fragments: { ...asRecord(source.generated_fragments ?? base.generated_fragments) },
    sensor_jobs: normalizeUnknownList(source.sensor_jobs ?? base.sensor_jobs),
    sensor_selected: normalizeText(source.sensor_selected, base.sensor_selected),
    mcu_jobs: normalizeUnknownList(source.mcu_jobs ?? base.mcu_jobs),
    mcu_selected: normalizeText(source.mcu_selected, base.mcu_selected),
    renode: {
      ...renodeDefaults,
      enabled: renodeSource.enabled === undefined ? renodeDefaults.enabled : Boolean(renodeSource.enabled),
      platform: normalizeText(renodeSource.platform, renodeDefaults.platform),
      resc: normalizeText(renodeSource.resc, base.renode.resc),
      robot: normalizeText(renodeSource.robot, base.renode.robot),
      uart: normalizeText(renodeSource.uart, renodeDefaults.uart),
      boot_line: normalizeText(renodeSource.boot_line, base.renode.boot_line),
      appbench_target: normalizeText(renodeSource.appbench_target, base.renode.appbench_target),
      robot_target: normalizeText(renodeSource.robot_target, base.renode.robot_target),
    },
    tabs: { ...asRecord(source.tabs ?? base.tabs) },
  };
}

export function applyBoardToProjectDocument(project: ProjectDocument, boardId: string): ProjectDocument {
  const defaults = defaultRenodeProfile(boardId);

  return {
    ...project,
    board_id: boardId,
    renode: {
      ...defaults,
      resc: project.renode.resc,
      robot: project.renode.robot,
    },
  };
}

export function parseProjectFileLoadResponse(response: ProjectFileLoadResponseDto): ProjectDocument {
  return normalizeProjectDocument(response);
}