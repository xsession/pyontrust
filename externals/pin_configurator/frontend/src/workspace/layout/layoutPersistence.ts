import type { WorkspaceLayoutPresetId } from "./workspaceShellPreferences";

export const WORKSPACE_DOCK_LAYOUT_STORAGE_KEY_PREFIX = "pin-configurator.workspace-dock-layout";

export interface WorkspaceDockLayoutDocument {
  version: 1;
  savedAt: string;
  layout: object;
}

export function getWorkspaceDockLayoutStorageKey(layoutPresetId: WorkspaceLayoutPresetId = "bring-up") {
  return `${WORKSPACE_DOCK_LAYOUT_STORAGE_KEY_PREFIX}.${layoutPresetId}.v1`;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === "object" && !Array.isArray(value);
}

function resolveStorage(storage?: Pick<Storage, "getItem" | "setItem" | "removeItem"> | null) {
  if (storage !== undefined) {
    return storage;
  }

  if (typeof window === "undefined") {
    return null;
  }

  return window.localStorage;
}

export function loadWorkspaceDockLayout(
  layoutPresetId: WorkspaceLayoutPresetId = "bring-up",
  storage?: Pick<Storage, "getItem" | "setItem" | "removeItem"> | null,
): WorkspaceDockLayoutDocument | null {
  const resolvedStorage = resolveStorage(storage);
  if (!resolvedStorage) {
    return null;
  }

  const storageKey = getWorkspaceDockLayoutStorageKey(layoutPresetId);
  const rawValue = resolvedStorage.getItem(storageKey);
  if (!rawValue) {
    return null;
  }

  try {
    const parsed = JSON.parse(rawValue) as unknown;
    if (!isRecord(parsed) || parsed.version !== 1 || !isRecord(parsed.layout)) {
      resolvedStorage.removeItem(storageKey);
      return null;
    }

    return {
      version: 1,
      savedAt: typeof parsed.savedAt === "string" ? parsed.savedAt : "",
      layout: parsed.layout,
    };
  } catch {
    resolvedStorage.removeItem(storageKey);
    return null;
  }
}

export function saveWorkspaceDockLayout(
  layout: object,
  layoutPresetId: WorkspaceLayoutPresetId = "bring-up",
  storage?: Pick<Storage, "getItem" | "setItem" | "removeItem"> | null,
) {
  const resolvedStorage = resolveStorage(storage);
  if (!resolvedStorage) {
    return;
  }

  const payload: WorkspaceDockLayoutDocument = {
    version: 1,
    savedAt: new Date().toISOString(),
    layout,
  };

  resolvedStorage.setItem(getWorkspaceDockLayoutStorageKey(layoutPresetId), JSON.stringify(payload));
}

export function clearWorkspaceDockLayout(
  layoutPresetId: WorkspaceLayoutPresetId = "bring-up",
  storage?: Pick<Storage, "getItem" | "setItem" | "removeItem"> | null,
) {
  const resolvedStorage = resolveStorage(storage);
  if (!resolvedStorage) {
    return;
  }

  resolvedStorage.removeItem(getWorkspaceDockLayoutStorageKey(layoutPresetId));
}
