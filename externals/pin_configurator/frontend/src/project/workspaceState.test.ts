import {
  applyProjectWorkspacePersistenceSnapshot,
  createDefaultProjectWorkspaceState,
  normalizeProjectWorkspacePersistenceSnapshot,
  serializeProjectWorkspaceState,
} from "./workspaceState";

describe("workspace state persistence boundaries", () => {
  it("serializes only workspace-only persistence fields separately from the project document", () => {
    const state = createDefaultProjectWorkspaceState();
    state.projectFilePath = "C:/tmp/custom.zpinproj";
    state.projectBusy = true;
    state.projectStatus = { tone: "error", message: "busy" };

    const result = serializeProjectWorkspaceState(state);

    expect(result).toEqual({ projectFilePath: "C:/tmp/custom.zpinproj" });
  });

  it("normalizes and reapplies workspace snapshots without restoring transient status or busy state", () => {
    const state = createDefaultProjectWorkspaceState();
    const snapshot = normalizeProjectWorkspacePersistenceSnapshot({ projectFilePath: "C:/tmp/restored.zpinproj" });
    const result = applyProjectWorkspacePersistenceSnapshot(state, snapshot);

    expect(result.projectFilePath).toBe("C:/tmp/restored.zpinproj");
    expect(result.projectBusy).toBe(false);
    expect(result.projectStatus.message).toContain("typed .zpinproj");
  });
});