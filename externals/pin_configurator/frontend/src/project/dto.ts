import type { ProtocolEditorDocument } from "./protocolEditor";
import type { RenodeProfile } from "./types";

export interface PersistedProjectDocumentDto {
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
  renode?: Partial<RenodeProfile> | Record<string, unknown> | null;
  tabs?: unknown;
}

export interface ProjectFileReferenceDto {
  file_path: string;
}

export type ProjectFileLoadRequestDto = ProjectFileReferenceDto;
export type ProjectFileLoadResponseDto = PersistedProjectDocumentDto;
export type ProjectFileSaveRequestDto = ProjectFileReferenceDto & PersistedProjectDocumentDto;

export interface ProjectFileSaveResponseDto extends ProjectFileReferenceDto {
  saved: boolean;
}