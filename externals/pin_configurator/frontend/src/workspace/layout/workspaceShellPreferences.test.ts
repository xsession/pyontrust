import {
  applyWorkspaceDensityMode,
  createDefaultWorkspaceShellPreferences,
  getWorkspaceLayoutPreset,
  loadWorkspaceShellPreferences,
  saveWorkspaceShellPreferences,
} from "./workspaceShellPreferences";

describe("workspaceShellPreferences", () => {
  function createStorage() {
    const values = new Map<string, string>();

    return {
      getItem: (key: string) => values.get(key) ?? null,
      setItem: (key: string, value: string) => {
        values.set(key, value);
      },
      removeItem: (key: string) => {
        values.delete(key);
      },
    };
  }

  it("returns the default preferences when no persisted shell preferences exist", () => {
    expect(loadWorkspaceShellPreferences(createStorage())).toEqual(createDefaultWorkspaceShellPreferences());
  });

  it("persists density and layout preset selections", () => {
    const storage = createStorage();

    saveWorkspaceShellPreferences({
      density: "compact",
      layoutPresetId: "renode-validation",
      focusedPanelId: "workspace-renode-profile",
      activeOutputChannelId: "simulation",
    }, storage);

    expect(loadWorkspaceShellPreferences(storage)).toMatchObject({
      density: "compact",
      layoutPresetId: "renode-validation",
      focusedPanelId: "workspace-renode-profile",
      activeOutputChannelId: "simulation",
      version: 1,
    });
  });

  it("falls back safely when persisted focused panel or output channel are invalid", () => {
    const storage = createStorage();

    storage.setItem(
      "pin-configurator.workspace-shell-preferences.v1",
      JSON.stringify({
        version: 1,
        savedAt: "2026-05-17T00:00:00.000Z",
        density: "regular",
        layoutPresetId: "bring-up",
        focusedPanelId: "workspace-missing-panel",
        activeOutputChannelId: "missing-output",
      }),
    );

    expect(loadWorkspaceShellPreferences(storage)).toMatchObject({
      focusedPanelId: "workspace-overview",
      activeOutputChannelId: "build",
    });
  });

  it("applies the selected density mode to the target root element", () => {
    const root = document.createElement("div");

    applyWorkspaceDensityMode("spacious", root);

    expect(root.dataset.density).toBe("spacious");
  });

  it("resolves known layout presets and falls back safely", () => {
    expect(getWorkspaceLayoutPreset("protocol-integration")).toMatchObject({
      panelId: "workspace-protocol-editor",
      outputChannelId: "diagnostics",
    });
  });
});