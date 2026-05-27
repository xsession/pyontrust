import type { WorkspaceLayoutPresetId } from "./workspaceShellPreferences";

export const WORKSPACE_DOCK_LAYOUT_STORAGE_KEY_PREFIX = "pin-configurator.workspace-dock-layout";
const WORKSPACE_DOCK_LAYOUT_STORAGE_VERSION = 5;

export interface WorkspaceDockLayoutDocument {
  version: 5;
  savedAt: string;
  layout: object;
}

export function getWorkspaceDockLayoutStorageKey(layoutPresetId: WorkspaceLayoutPresetId = "bring-up") {
  return `${WORKSPACE_DOCK_LAYOUT_STORAGE_KEY_PREFIX}.${layoutPresetId}.v${WORKSPACE_DOCK_LAYOUT_STORAGE_VERSION}`;
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
    if (!isRecord(parsed) || parsed.version !== WORKSPACE_DOCK_LAYOUT_STORAGE_VERSION || !isRecord(parsed.layout)) {
      resolvedStorage.removeItem(storageKey);
      return null;
    }

    return {
      version: WORKSPACE_DOCK_LAYOUT_STORAGE_VERSION,
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
    version: WORKSPACE_DOCK_LAYOUT_STORAGE_VERSION,
    savedAt: new Date().toISOString(),
    layout,
  };

  const storageKey = getWorkspaceDockLayoutStorageKey(layoutPresetId);

  try {
    resolvedStorage.setItem(storageKey, JSON.stringify(payload));
  } catch {
    try {
      resolvedStorage.removeItem(storageKey);
    } catch {
      // Ignore storage cleanup failures. The shell can continue without persisted dock layout.
    }
  }
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
