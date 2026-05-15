import { createEmptyProjectDocument } from "../contracts/api";
import {
  applyProjectDocumentHistoryCommand,
  canRedoProjectDocumentHistory,
  canUndoProjectDocumentHistory,
  createProjectDocumentHistory,
  redoProjectDocumentHistory,
  replaceProjectDocumentHistory,
  undoProjectDocumentHistory,
} from "./history";

describe("project history", () => {
  it("tracks persistent command history and supports undo and redo", () => {
    const initial = createProjectDocumentHistory(createEmptyProjectDocument());
    const withBoard = applyProjectDocumentHistoryCommand(initial, {
      type: "apply-board-selection",
      boardId: "lp_mspm0g3507",
    });
    const withOverlay = applyProjectDocumentHistoryCommand(withBoard, {
      type: "update-generated-overlay",
      value: "/dts-v1/;",
    });
    const undone = undoProjectDocumentHistory(withOverlay);
    const redone = redoProjectDocumentHistory(undone);

    expect(canUndoProjectDocumentHistory(initial)).toBe(false);
    expect(canUndoProjectDocumentHistory(withBoard)).toBe(true);
    expect(withOverlay.present.generated_overlay).toBe("/dts-v1/;");
    expect(undone.present.generated_overlay).toBe("");
    expect(canRedoProjectDocumentHistory(undone)).toBe(true);
    expect(redone.present.generated_overlay).toBe("/dts-v1/;");
  });

  it("resets history when replacing the active project document", () => {
    const history = applyProjectDocumentHistoryCommand(
      createProjectDocumentHistory(createEmptyProjectDocument()),
      {
        type: "update-generated-conf",
        value: "CONFIG_GPIO=y",
      },
    );
    const replaced = replaceProjectDocumentHistory(
      createEmptyProjectDocument(),
    );

    expect(history.past).toHaveLength(1);
    expect(replaced.past).toHaveLength(0);
    expect(replaced.future).toHaveLength(0);
    expect(replaced.present.generated_conf).toBe("");
  });
});