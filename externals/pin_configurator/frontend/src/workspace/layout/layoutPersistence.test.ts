import {
  clearWorkspaceDockLayout,
  getWorkspaceDockLayoutStorageKey,
  loadWorkspaceDockLayout,
  saveWorkspaceDockLayout,
} from "./layoutPersistence";

describe("layoutPersistence", () => {
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

  it("persists dock layouts under preset-specific storage keys", () => {
    const storage = createStorage();

    saveWorkspaceDockLayout({ grid: { views: [] } }, "codegen-review", storage);

    expect(loadWorkspaceDockLayout("bring-up", storage)).toBeNull();
    expect(loadWorkspaceDockLayout("codegen-review", storage)).toMatchObject({
      version: 1,
      layout: { grid: { views: [] } },
    });
    expect(getWorkspaceDockLayoutStorageKey("codegen-review")).toContain("codegen-review");
  });

  it("clears only the targeted preset layout", () => {
    const storage = createStorage();

    saveWorkspaceDockLayout({ grid: { views: [1] } }, "bring-up", storage);
    saveWorkspaceDockLayout({ grid: { views: [2] } }, "renode-validation", storage);

    clearWorkspaceDockLayout("bring-up", storage);

    expect(loadWorkspaceDockLayout("bring-up", storage)).toBeNull();
    expect(loadWorkspaceDockLayout("renode-validation", storage)).toMatchObject({
      layout: { grid: { views: [2] } },
    });
  });
});