import type {
  BoardEditorDraftListResponse,
  BoardEditorDraftLoadResponse,
  BoardEditorDraftSaveResponse,
  BoardDefinition,
  BoardSummary,
  ClockConfigGenerationResponse,
  ClockFrequencyResponse,
  ClockTreeDefinition,
  ClockTreeSummary,
  LvglExportResponse,
  LvglImportResponse,
  LvglImportSourceKind,
  ModuleConfigGenerationResponse,
  ModuleDefinition,
  ProjectFileLoadResponseDto,
  ProjectFileReference,
  ProjectFileSaveRequest,
  ProjectFileSaveResponse,
  ZephyrCatalogResponse,
} from "../contracts/api";
import { type ProjectDocument } from "../project/projectDocument";
import { parseProjectFileLoadResponse } from "../project/normalize";
import { buildProjectFileSaveRequest } from "../project/serialize";
import { buildApiUrl } from "../shared/config/environment";
import { fetchJson } from "./http";

export interface PinConfiguratorApi {
  listBoards(): Promise<BoardSummary[]>;
  getBoard(boardId: string): Promise<BoardDefinition>;
  loadZephyrCatalog(options?: { zephyrRoot?: string; refresh?: boolean }): Promise<ZephyrCatalogResponse>;
  listModules(): Promise<ModuleDefinition[]>;
  generateModuleConfig(request: { modules: Record<string, Record<string, string | number | boolean>> }): Promise<ModuleConfigGenerationResponse>;
  listClockTrees(): Promise<ClockTreeSummary[]>;
  getClockTree(treeId: string): Promise<ClockTreeDefinition>;
  computeClockFrequencies(request: { tree: string; values: Record<string, string | number | boolean> }): Promise<ClockFrequencyResponse>;
  generateClockConfig(request: { tree: string; values: Record<string, string | number | boolean> }): Promise<ClockConfigGenerationResponse>;
  listBoardEditorDrafts(): Promise<BoardEditorDraftListResponse>;
  loadBoardEditorDraft(filename: string): Promise<BoardEditorDraftLoadResponse>;
  saveBoardEditorDraft(request: { board: Record<string, unknown>; filename?: string }): Promise<BoardEditorDraftSaveResponse>;
  deleteBoardEditorDraft(filename: string): Promise<BoardEditorDraftSaveResponse>;
  importLvglLayout(request: { sourceKind?: LvglImportSourceKind; text?: string; filePath?: string; url?: string }): Promise<LvglImportResponse>;
  exportLvglLayout(request: { filePath: string; layout: Record<string, unknown> }): Promise<LvglExportResponse>;
  saveProjectFile(request: ProjectFileSaveRequest): Promise<ProjectFileSaveResponse>;
  loadProjectFile(reference: ProjectFileReference): Promise<ProjectDocument>;
}

export const pinConfiguratorApi: PinConfiguratorApi = {
  listBoards() {
    return fetchJson<BoardSummary[]>(buildApiUrl("/boards"));
  },

  getBoard(boardId) {
    return fetchJson<BoardDefinition>(buildApiUrl(`/board/${encodeURIComponent(boardId)}`));
  },

  loadZephyrCatalog(options) {
    const params = new URLSearchParams();
    if (options?.zephyrRoot?.trim()) {
      params.set("zephyr_root", options.zephyrRoot.trim());
    }
    if (options?.refresh) {
      params.set("refresh", "1");
    }

    const query = params.toString();
    const url = buildApiUrl(`/zephyr/catalog${query ? `?${query}` : ""}`);
    return fetchJson<ZephyrCatalogResponse>(url);
  },

  listModules() {
    return fetchJson<ModuleDefinition[]>(buildApiUrl("/modules"));
  },

  generateModuleConfig(request) {
    return fetchJson<ModuleConfigGenerationResponse>(buildApiUrl("/generate-module-config"), {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(request),
    });
  },

  listClockTrees() {
    return fetchJson<ClockTreeSummary[]>(buildApiUrl("/clock-trees"));
  },

  getClockTree(treeId) {
    return fetchJson<ClockTreeDefinition>(buildApiUrl(`/clock-tree/${encodeURIComponent(treeId)}`));
  },

  computeClockFrequencies(request) {
    return fetchJson<ClockFrequencyResponse>(buildApiUrl("/clock-frequencies"), {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(request),
    });
  },

  generateClockConfig(request) {
    return fetchJson<ClockConfigGenerationResponse>(buildApiUrl("/generate-clock-config"), {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(request),
    });
  },

  listBoardEditorDrafts() {
    return fetchJson<BoardEditorDraftListResponse>(buildApiUrl("/board-editor/drafts"));
  },

  loadBoardEditorDraft(filename) {
    return fetchJson<BoardEditorDraftLoadResponse>(buildApiUrl(`/board-editor/draft/${encodeURIComponent(filename)}`));
  },

  saveBoardEditorDraft(request) {
    return fetchJson<BoardEditorDraftSaveResponse>(buildApiUrl("/board-editor/save"), {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        board: request.board,
        filename: request.filename,
      }),
    });
  },

  deleteBoardEditorDraft(filename) {
    return fetchJson<BoardEditorDraftSaveResponse>(buildApiUrl("/board-editor/delete"), {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ filename }),
    });
  },

  importLvglLayout(request) {
    return fetchJson<LvglImportResponse>(buildApiUrl("/lvgl/import"), {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        source_kind: request.sourceKind,
        text: request.text,
        file_path: request.filePath,
        url: request.url,
      }),
    });
  },

  exportLvglLayout(request) {
    return fetchJson<LvglExportResponse>(buildApiUrl("/lvgl/export"), {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        file_path: request.filePath,
        layout: request.layout,
      }),
    });
  },

  saveProjectFile(request) {
    return fetchJson<ProjectFileSaveResponse>(buildApiUrl("/project-file/save"), {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(buildProjectFileSaveRequest(parseProjectFileLoadResponse(request), request.file_path)),
    });
  },

  async loadProjectFile(reference) {
    const result = await fetchJson<ProjectFileLoadResponseDto>(buildApiUrl("/project-file/load"), {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(reference),
    });

    return parseProjectFileLoadResponse(result);
  },
};