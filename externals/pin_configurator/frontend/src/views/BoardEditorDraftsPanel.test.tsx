import { render, screen } from "@testing-library/react";
import { BoardEditorDraftsPanel } from "./BoardEditorDraftsPanel";
import type { BoardEditorPresenter } from "../domains/board-editor/boardEditorPresenter";

function createPresenter(): BoardEditorPresenter {
  return {
    drafts: [{ filename: "demo_board.json", size: 1200, updatedAt: "2026-05-15" }],
    draftFilename: "demo_board.json",
    draftText: JSON.stringify({ board: "demo_board", package: "QFP-48", pins: [{ number: 1, name: "PA0" }], external_devices: [{ id: "imu0", display: "IMU", bus: "i2c0" }] }, null, 2),
    status: "Loaded board-editor draft demo_board.json.",
    error: "",
    setDraftFilename: () => undefined,
    setDraftText: () => undefined,
    refreshDrafts: () => undefined,
    loadDraft: () => undefined,
    saveDraft: () => undefined,
    deleteDraft: () => undefined,
    seedFromActiveBoard: () => undefined,
  };
}

describe("BoardEditorDraftsPanel", () => {
  it("renders the layered board scene beside the JSON editor", () => {
    render(<BoardEditorDraftsPanel presenter={createPresenter()} />);

    expect(screen.getByLabelText("Scene viewport controls")).toBeInTheDocument();
    expect(screen.getByLabelText("Board editor scene")).toBeInTheDocument();
    expect(screen.getByText("Board scene")).toBeInTheDocument();
  });
});