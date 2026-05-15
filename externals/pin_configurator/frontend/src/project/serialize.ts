import type { PersistedProjectDocumentDto, ProjectFileSaveRequestDto } from "./dto";
import type { ProjectDocument } from "./types";

export function serializeProjectDocument(document: ProjectDocument): PersistedProjectDocumentDto {
  return {
    version: document.version,
    board_id: document.board_id,
    pin_states: document.pin_states,
    periph_states: document.periph_states,
    periph_core_states: document.periph_core_states,
    external_device_states: document.external_device_states,
    protocol_editor: document.protocol_editor,
    lvgl_layout: document.lvgl_layout,
    generated_overlay: document.generated_overlay,
    generated_conf: document.generated_conf,
    generated_fragments: document.generated_fragments,
    sensor_jobs: document.sensor_jobs,
    sensor_selected: document.sensor_selected,
    mcu_jobs: document.mcu_jobs,
    mcu_selected: document.mcu_selected,
    renode: document.renode,
    tabs: document.tabs,
  };
}

export function buildProjectFileSaveRequest(document: ProjectDocument, filePath: string): ProjectFileSaveRequestDto {
  return {
    ...serializeProjectDocument(document),
    file_path: filePath,
  };
}