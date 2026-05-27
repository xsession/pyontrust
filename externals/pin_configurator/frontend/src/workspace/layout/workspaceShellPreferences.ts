import { workspaceDockPanelDefinitions } from "../panels/dockPanelDefinitions";

export type WorkspaceDensityMode = "compact" | "regular" | "spacious";
export type WorkspaceOutputChannelId = "build" | "simulation" | "diagnostics" | "tests";

export type WorkspaceLayoutPresetId =
  | "bring-up"
  | "protocol-integration"
  | "codegen-review"
  | "renode-validation";

export interface WorkspaceLayoutPresetDefinition {
  id: WorkspaceLayoutPresetId;
  label: string;
  description: string;
  panelId: string;
  outputChannelId: WorkspaceOutputChannelId;
  keywords: string[];
}

export interface WorkspaceShellPreferencesDocument {
  version: 2;
  savedAt: string;
  density: WorkspaceDensityMode;
  layoutPresetId: WorkspaceLayoutPresetId;
  focusedPanelId: string;
  activeOutputChannelId: WorkspaceOutputChannelId;
}

export const WORKSPACE_SHELL_PREFERENCES_STORAGE_KEY = "pin-configurator.workspace-shell-preferences.v2";

export const workspaceLayoutPresets: readonly WorkspaceLayoutPresetDefinition[] = [
  {
    id: "bring-up",
    label: "Board Bring-up",
    description: "Start with the pin workspace, peripheral context, and build readiness in view.",
    panelId: "workspace-pin-assignments",
    outputChannelId: "build",
    keywords: ["board", "bring-up", "pins", "build"],
  },
  {
    id: "protocol-integration",
    label: "Protocol Integration",
    description: "Focus interface composition, diagnostics, and pin assignment follow-up.",
    panelId: "workspace-protocol-editor",
    outputChannelId: "diagnostics",
    keywords: ["protocol", "integration", "pins", "diagnostics"],
  },
  {
    id: "codegen-review",
    label: "Codegen Review",
    description: "Review generated overlay, config, and test readiness without leaving the shell.",
    panelId: "workspace-generated-overlay",
    outputChannelId: "tests",
    keywords: ["codegen", "generated", "overlay", "tests"],
  },
  {
    id: "renode-validation",
    label: "Renode Validation",
    description: "Jump to the Renode profile and simulation output channel for handoff checks.",
    panelId: "workspace-renode-profile",
    outputChannelId: "simulation",
    keywords: ["renode", "simulation", "validation", "appbench"],
  },
] as const;

const defaultWorkspaceShellPreferences: WorkspaceShellPreferencesDocument = {
  version: 2,
  savedAt: "",
  density: "regular",
  layoutPresetId: "bring-up",
  focusedPanelId: "workspace-pin-assignments",
  activeOutputChannelId: "build",
};

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

function isWorkspaceDensityMode(value: unknown): value is WorkspaceDensityMode {
  return value === "compact" || value === "regular" || value === "spacious";
}

function isWorkspaceLayoutPresetId(value: unknown): value is WorkspaceLayoutPresetId {
  return workspaceLayoutPresets.some((preset) => preset.id === value);
}

function isWorkspaceOutputChannelId(value: unknown): value is WorkspaceOutputChannelId {
  return value === "build" || value === "simulation" || value === "diagnostics" || value === "tests";
}

function isWorkspaceDockPanelId(value: unknown): value is string {
  return typeof value === "string" && workspaceDockPanelDefinitions.some((panel) => panel.id === value);
}

function normalizeFocusedPanelId(layoutPresetId: WorkspaceLayoutPresetId, focusedPanelId: unknown): string {
  if (layoutPresetId === "bring-up") {
    return defaultWorkspaceShellPreferences.focusedPanelId;
  }

  return isWorkspaceDockPanelId(focusedPanelId) ? focusedPanelId : defaultWorkspaceShellPreferences.focusedPanelId;
}

export function createDefaultWorkspaceShellPreferences(): WorkspaceShellPreferencesDocument {
  return { ...defaultWorkspaceShellPreferences };
}

export function loadWorkspaceShellPreferences(
  storage?: Pick<Storage, "getItem" | "setItem" | "removeItem"> | null,
): WorkspaceShellPreferencesDocument {
  const resolvedStorage = resolveStorage(storage);
  if (!resolvedStorage) {
    return createDefaultWorkspaceShellPreferences();
  }

  const rawValue = resolvedStorage.getItem(WORKSPACE_SHELL_PREFERENCES_STORAGE_KEY);
  if (!rawValue) {
    return createDefaultWorkspaceShellPreferences();
  }

  try {
    const parsed = JSON.parse(rawValue) as unknown;
    if (!isRecord(parsed) || parsed.version !== 2) {
      resolvedStorage.removeItem(WORKSPACE_SHELL_PREFERENCES_STORAGE_KEY);
      return createDefaultWorkspaceShellPreferences();
    }

    return {
      version: 2,
      savedAt: typeof parsed.savedAt === "string" ? parsed.savedAt : "",
      density: isWorkspaceDensityMode(parsed.density) ? parsed.density : defaultWorkspaceShellPreferences.density,
      layoutPresetId: isWorkspaceLayoutPresetId(parsed.layoutPresetId) ? parsed.layoutPresetId : defaultWorkspaceShellPreferences.layoutPresetId,
      focusedPanelId: normalizeFocusedPanelId(
        isWorkspaceLayoutPresetId(parsed.layoutPresetId) ? parsed.layoutPresetId : defaultWorkspaceShellPreferences.layoutPresetId,
        parsed.focusedPanelId,
      ),
      activeOutputChannelId: isWorkspaceOutputChannelId(parsed.activeOutputChannelId)
        ? parsed.activeOutputChannelId
        : defaultWorkspaceShellPreferences.activeOutputChannelId,
    };
  } catch {
    resolvedStorage.removeItem(WORKSPACE_SHELL_PREFERENCES_STORAGE_KEY);
    return createDefaultWorkspaceShellPreferences();
  }
}

export function saveWorkspaceShellPreferences(
  preferences: Pick<WorkspaceShellPreferencesDocument, "density" | "layoutPresetId" | "focusedPanelId" | "activeOutputChannelId">,
  storage?: Pick<Storage, "getItem" | "setItem" | "removeItem"> | null,
) {
  const resolvedStorage = resolveStorage(storage);
  if (!resolvedStorage) {
    return;
  }

  const payload: WorkspaceShellPreferencesDocument = {
    version: 2,
    savedAt: new Date().toISOString(),
    density: preferences.density,
    layoutPresetId: preferences.layoutPresetId,
    focusedPanelId: normalizeFocusedPanelId(preferences.layoutPresetId, preferences.focusedPanelId),
    activeOutputChannelId: preferences.activeOutputChannelId,
  };

  resolvedStorage.setItem(WORKSPACE_SHELL_PREFERENCES_STORAGE_KEY, JSON.stringify(payload));
}

export function applyWorkspaceDensityMode(density: WorkspaceDensityMode, root?: HTMLElement | null) {
  const target = root ?? (typeof document === "undefined" ? null : document.documentElement);
  if (!target) {
    return;
  }

  target.dataset.density = density;
}

export function getWorkspaceLayoutPreset(presetId: WorkspaceLayoutPresetId) {
  return workspaceLayoutPresets.find((preset) => preset.id === presetId) ?? workspaceLayoutPresets[0];
}