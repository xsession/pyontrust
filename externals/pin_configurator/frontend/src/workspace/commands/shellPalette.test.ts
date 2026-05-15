import { describe, expect, it, vi } from "vitest";
import { buildPaletteSections, buildVisiblePaletteItems, type ShellPaletteItem } from "./shellPalette";

const items: ShellPaletteItem[] = [
  { id: "save", label: "Save Project", description: "Persist the project", shortcut: "Ctrl+S", group: "Project", disabled: false, keywords: ["command"], run: vi.fn() },
  { id: "board", label: "Open Board MSPM0G3507", description: "Select the active board", shortcut: "", group: "Boards", disabled: false, keywords: ["command", "board"], run: vi.fn() },
];

describe("shellPalette", () => {
  it("fuzzy filters command palette items", () => {
    expect(buildVisiblePaletteItems(items, [], "m0g35").map((item) => item.id)).toEqual(["board"]);
  });

  it("builds a recent section when the query is empty", () => {
    const sections = buildPaletteSections(items, ["save"], "");
    expect(sections[0]?.label).toBe("Recently used");
    expect(sections[0]?.items.map((item) => item.id)).toEqual(["save"]);
  });
});