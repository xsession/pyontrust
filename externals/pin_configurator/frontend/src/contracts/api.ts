export {
  applyBoardToProjectDocument,
  createEmptyProjectDocument,
  defaultRenodeProfile,
  normalizeProjectDocument,
  PROJECT_FILE_VERSION,
} from "../project/projectDocument";
export type { ProjectDocument, RenodeProfile } from "../project/projectDocument";
export type {
  PersistedProjectDocumentDto,
  ProjectFileReferenceDto as ProjectFileReference,
  ProjectFileLoadResponseDto,
  ProjectFileSaveRequestDto as ProjectFileSaveRequest,
  ProjectFileSaveResponseDto as ProjectFileSaveResponse,
} from "../project/dto";
export {
  addProtocolEntry,
  createDefaultProtocolEditorDocument,
  normalizeProtocolEditorDocument,
  protocolTemplateById,
  removeProtocolEntry,
  selectProtocolEntry,
  selectedProtocolEntry,
  toggleProtocolEntry,
  updateProtocolEntryValue,
  PROTOCOL_EDITOR_TEMPLATES,
} from "../project/protocolEditor";
export type { ProtocolEditorDocument, ProtocolEntry, ProtocolFieldValue, ProtocolTemplate } from "../project/protocolEditor";

export interface BoardSummary {
  id: string;
  name: string;
  board: string;
  package: string;
  pin_count: number;
}

export interface BoardCore {
  id: string;
  name: string;
  arch: string;
  role: string;
  clock_hz: number;
  default: boolean;
}

export interface BoardOutputTarget {
  kind: string;
  label: string;
  file_suffixes: string[];
}

export interface BoardAltFunction {
  function_id: number;
  pincm: number | string;
  name: string;
  peripheral: string;
  signal: string;
  direction: string;
  zephyr_pinmux: string;
}

export interface BoardPin {
  number: number;
  name: string;
  port: string;
  gpio_num: number;
  kind: string;
  side: string;
  default_function: string;
  alt_functions: BoardAltFunction[];
}

export interface BoardPeripheral {
  name: string;
  display: string;
  compatible: string;
  signals: string[];
  dts_node: string;
  enabled: boolean;
  core_id: string;
  available_cores: string[];
}

export interface BoardExternalDevice {
  id: string;
  display: string;
  category: string;
  bus: string;
  compatible: string;
  address: string;
  required_signals: string[];
  frameworks: string[];
  notes: string;
}

export interface BoardDefinition {
  soc: string;
  board: string;
  vendor: string;
  package: string;
  pin_count: number;
  flash_size_kb: number;
  sram_size_kb: number;
  clock_hz: number;
  cores: BoardCore[];
  output_targets: BoardOutputTarget[];
  pins: BoardPin[];
  peripherals: BoardPeripheral[];
  external_devices: BoardExternalDevice[];
}

export interface ZephyrCatalogSummary {
  mcu_count: number;
  sensor_count: number;
}

export interface ZephyrCatalogParameter {
  name: string;
  type: string;
  required: boolean;
  default?: unknown;
  enum?: unknown[];
  description: string;
}

export interface ZephyrCatalogMcuItem {
  key: string;
  kind: "mcu";
  name: string;
  label: string;
  vendor: string;
  socs: string[];
  board_path: string;
  directory: string;
  parameters: Record<string, unknown>;
}

export interface ZephyrCatalogSensorItem {
  key: string;
  kind: "sensor";
  name: string;
  label: string;
  vendor: string;
  compatible: string;
  buses: string[];
  properties: ZephyrCatalogParameter[];
  binding_paths: string[];
  description: string;
  parameters: Record<string, unknown>;
}

export type ZephyrCatalogItem = ZephyrCatalogMcuItem | ZephyrCatalogSensorItem;

export interface ZephyrCatalogResponse {
  root: string;
  summary: ZephyrCatalogSummary;
  mcus: ZephyrCatalogMcuItem[];
  sensors: ZephyrCatalogSensorItem[];
}

export type ConfigPrimitive = string | number | boolean;

export interface ModuleOptionDefinition {
  key: string;
  label?: string;
  help?: string;
  type: "bool" | "int" | "choice" | "string";
  default: ConfigPrimitive;
  choices?: Array<string | number>;
  kconfig?: boolean;
  dts?: boolean;
}

export interface ModuleCategoryDefinition {
  id: string;
  title: string;
  options: ModuleOptionDefinition[];
}

export interface ModuleDefinition {
  id: string;
  name: string;
  version?: string;
  desc?: string;
  icon?: string;
  categories: ModuleCategoryDefinition[];
}

export interface ModuleConfigGenerationResponse {
  prj_conf: string;
  overlay_conf: string;
}

export interface ClockTreeSummary {
  id: string;
  name: string;
  node_count: number;
  soc?: string;
}

export interface ClockTreeNodeProperty {
  key: string;
  label?: string;
  help?: string;
  type: "bool" | "int" | "choice" | "string";
  default: ConfigPrimitive;
  choices?: Array<string | number>;
  min?: number;
  max?: number;
}

export interface ClockTreeNode {
  id: string;
  name: string;
  type: string;
  icon: string;
  props?: ClockTreeNodeProperty[];
}

export interface ClockTreeDefinition {
  id: string;
  name: string;
  soc?: string;
  nodes: ClockTreeNode[];
  peripheral_clocks?: Record<string, string>;
}

export interface ClockFrequencyResponse {
  frequencies: Record<string, number>;
  warnings?: string[];
}

export interface ClockConfigGenerationResponse extends ClockFrequencyResponse {
  overlay: string;
  prj_conf: string;
}

export interface BoardEditorDraftMetadata {
  filename: string;
  size: number;
  updated_at: string;
}

export interface BoardEditorDraftListResponse {
  drafts: BoardEditorDraftMetadata[];
}

export interface BoardEditorDraftLoadResponse {
  filename: string;
  board: Record<string, unknown>;
}

export interface BoardEditorDraftSaveResponse {
  filename: string;
}

export type LvglImportSourceKind = "json" | "zephyr" | "pdf" | "display-pdf";

export interface LvglImportResponse {
  source: string;
  layout: Record<string, unknown>;
}

export interface LvglExportResponse {
  saved: boolean;
  file_path: string;
}

export interface ProjectMetadata {
  file_path: string;
  board_id: string;
  version: number;
  dirty: boolean;
  updated_at: string | null;
}

export interface BackendHealthStatus {
  state: "unknown" | "ready" | "degraded" | "error";
  reachable: boolean;
  api_base_path: string;
  detail: string;
}
