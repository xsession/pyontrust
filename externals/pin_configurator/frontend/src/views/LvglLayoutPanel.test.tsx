import { render, screen } from "@testing-library/react";
import { LvglLayoutPanel } from "./LvglLayoutPanel";
import type { LvglLayoutPresenter } from "../domains/lvgl/lvglLayoutPresenter";

function createPresenter(): LvglLayoutPresenter {
  return {
    layout: {
      preset: "phone",
      startupScreenId: "screen_root",
      simulation: { log: ["Simulation is idle."] },
      sharedStyles: [{ id: "style_primary", name: "Primary", values: { bg: "#111827" } }],
      screens: [
        {
          id: "screen_root",
          name: "Home",
          text: "Home",
          w: 320,
          h: 240,
          bg: "#0f172a",
          nodes: [{ id: "title", name: "Title", type: "label", x: 32, y: 30, w: 120, h: 32, styleRefs: ["style_primary"] }],
        },
      ],
    },
    summary: { preset: "phone", screenCount: 1, widgetCount: 1, startupScreenId: "screen_root" },
    draftText: "{}",
    importSourceKind: "json",
    importSourceValue: "",
    exportFilePath: "C:/tmp/layout",
    status: "LVGL layout ready.",
    error: "",
    setDraftText: () => undefined,
    applyDraftText: () => undefined,
    setImportSourceKind: () => undefined,
    setImportSourceValue: () => undefined,
    importLayout: () => undefined,
    setExportFilePath: () => undefined,
    exportLayout: () => undefined,
  };
}

describe("LvglLayoutPanel", () => {
  it("renders the stage, hierarchy, and validation companions", () => {
    render(<LvglLayoutPanel presenter={createPresenter()} />);

    expect(screen.getByLabelText("Scene viewport controls")).toBeInTheDocument();
    expect(screen.getByLabelText("LVGL stage")).toBeInTheDocument();
    expect(screen.getByText("Hierarchy")).toBeInTheDocument();
    expect(screen.getByText("Simulation log")).toBeInTheDocument();
  });
});