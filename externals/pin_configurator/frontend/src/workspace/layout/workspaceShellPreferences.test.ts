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

    saveWorkspaceShellPreferences({ density: "compact", layoutPresetId: "renode-validation" }, storage);

    expect(loadWorkspaceShellPreferences(storage)).toMatchObject({
      density: "compact",
      layoutPresetId: "renode-validation",
      version: 1,
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