import type { ProtocolEditorDocument } from "./protocolEditor";
import type {
  ExternalDeviceSelectionStateMap,
  LegacyPinStateMap,
  PeripheralCoreStateMap,
  PeripheralEnabledStateMap,
} from "./legacyHardwareState";

export interface RenodeProfile {
  enabled: boolean;
  platform: string;
  resc: string;
  robot: string;
  uart: string;
  boot_line: string;
  appbench_target: string;
  robot_target: string;
}

export interface ProjectDocument {
  version: number;
  board_id: string;
  pin_states: LegacyPinStateMap;
  periph_states: PeripheralEnabledStateMap;
  periph_core_states: PeripheralCoreStateMap;
  external_device_states: ExternalDeviceSelectionStateMap;
  protocol_editor: ProtocolEditorDocument;
  lvgl_layout: Record<string, unknown>;
  generated_overlay: string;
  generated_conf: string;
  generated_fragments: Record<string, unknown>;
  sensor_jobs: unknown[];
  sensor_selected: string;
  mcu_jobs: unknown[];
  mcu_selected: string;
  renode: RenodeProfile;
  tabs: Record<string, unknown>;
}

export interface ProjectDocumentInput {
  version?: unknown;
  board_id?: unknown;
  pin_states?: unknown;
  periph_states?: unknown;
  periph_core_states?: unknown;
  external_device_states?: unknown;
  protocol_editor?: Partial<ProtocolEditorDocument> | null;
  lvgl_layout?: unknown;
  generated_overlay?: unknown;
  generated_conf?: unknown;
  generated_fragments?: unknown;
  sensor_jobs?: unknown;
  sensor_selected?: unknown;
  mcu_jobs?: unknown;
  mcu_selected?: unknown;
  renode?: unknown;
  tabs?: unknown;
}

export const PROJECT_FILE_VERSION = 1;