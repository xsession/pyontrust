import type { BoardDefinition } from "../contracts/api";

export interface ProjectStatus {
  tone: "neutral" | "success" | "error";
  message: string;
}

export interface ProjectWorkspaceState {
  activeBoardDefinition: BoardDefinition | null;
  projectFilePath: string;
  projectStatus: ProjectStatus;
  projectBusy: boolean;
}

export interface ProjectWorkspacePersistenceSnapshot {
  projectFilePath: string;
}

export function createDefaultProjectWorkspaceState(): ProjectWorkspaceState {
  return {
    activeBoardDefinition: null,
    projectFilePath: "C:/tmp/pin-configurator-shell.zpinproj",
    projectStatus: {
      tone: "neutral",
      message: "Select a board, then save or load a typed .zpinproj document through the new React shell.",
    },
    projectBusy: false,
  };
}

export function serializeProjectWorkspaceState(state: ProjectWorkspaceState): ProjectWorkspacePersistenceSnapshot {
  return {
    projectFilePath: state.projectFilePath,
  };
}

export function normalizeProjectWorkspacePersistenceSnapshot(snapshot?: Partial<ProjectWorkspacePersistenceSnapshot> | null): ProjectWorkspacePersistenceSnapshot {
  return {
    projectFilePath: typeof snapshot?.projectFilePath === "string"
      ? snapshot.projectFilePath
      : createDefaultProjectWorkspaceState().projectFilePath,
  };
}

export function applyProjectWorkspacePersistenceSnapshot(
  state: ProjectWorkspaceState,
  snapshot?: Partial<ProjectWorkspacePersistenceSnapshot> | null,
): ProjectWorkspaceState {
  const normalizedSnapshot = normalizeProjectWorkspacePersistenceSnapshot(snapshot);

  return {
    ...state,
    projectFilePath: normalizedSnapshot.projectFilePath,
  };
}