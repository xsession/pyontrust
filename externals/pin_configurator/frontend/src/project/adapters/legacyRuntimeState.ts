import type { PersistedProjectDocumentDto } from "../dto";
import { normalizeProjectDocument } from "../normalize";
import { serializeProjectDocument } from "../serialize";
import type { ProjectDocument, ProjectDocumentInput } from "../types";

export interface LegacyRuntimeProjectState extends ProjectDocumentInput {
  boardId?: unknown;
}

export function adaptLegacyRuntimeStateToProjectDocument(state?: LegacyRuntimeProjectState | null): ProjectDocument {
  const source = state ?? {};

  return normalizeProjectDocument({
    ...source,
    board_id: source.board_id ?? source.boardId,
  });
}

export function adaptProjectDocumentToLegacyRuntimeState(document: ProjectDocument): PersistedProjectDocumentDto {
  return serializeProjectDocument(document);
}