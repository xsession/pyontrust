import { getWorkspaceShortcutAction, workspaceShortcutReferences } from "./shortcutBindings";

describe("workspace shortcut bindings", () => {
  it("maps explicit panel shortcuts to panel ids instead of definition order", () => {
    const action = getWorkspaceShortcutAction(
      new KeyboardEvent("keydown", {
        key: "2",
        altKey: true,
      }),
    );

    expect(action).toEqual({ kind: "panel.focus", panelId: "workspace-generated-overlay" });
  });

  it("publishes stable panel shortcut references for the keyboard map", () => {
    expect(workspaceShortcutReferences).toEqual(
      expect.arrayContaining([
        expect.objectContaining({ label: "Focus Board Inventory", shortcut: "Alt+1", scope: "panel" }),
        expect.objectContaining({ label: "Focus Generated Overlay", shortcut: "Alt+2", scope: "panel" }),
        expect.objectContaining({ label: "Focus Pin Assignments", shortcut: "Alt+5", scope: "panel" }),
        expect.objectContaining({ label: "Focus Renode Profile", shortcut: "Alt+7", scope: "panel" }),
      ]),
    );
  });
});