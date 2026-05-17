import { createEmptyProjectDocument, type BoardSummary } from "../contracts/api";
import { buildArtifactDiagnosticEntries, buildArtifactReviewDocuments } from "./artifactReview";

describe("artifactReview", () => {
  const board: BoardSummary = {
    id: "mspm0g3507",
    name: "MSPM0G3507",
    board: "lp_mspm0g3507",
    package: "QFP-48",
    pin_count: 48,
  };

  it("builds the Phase 8 artifact surface set with navigation-ready diagnostics", () => {
    const projectDocument = createEmptyProjectDocument();
    projectDocument.board_id = board.board;
    projectDocument.generated_overlay = "/custom-overlay { zephyr,console = &uart0; };";
    projectDocument.protocol_editor.entries = [
      {
        id: "proto_uart_shell_bridge_1",
        templateId: "uart_shell_bridge",
        enabled: true,
        values: {
          instanceName: "uart_shell_1",
          uartNode: "uart0",
          baudRate: 115200,
          shellPrompt: "shell:~$",
          lineMode: true,
        },
      },
    ];

    const documents = buildArtifactReviewDocuments({
      activeBoard: board,
      projectDocument,
      unresolvedPinCount: 2,
    });
    const diagnostics = buildArtifactDiagnosticEntries(documents);

    expect(documents.map((document) => document.panelId)).toEqual([
      "workspace-generated-overlay",
      "workspace-generated-config",
      "workspace-generated-fragments",
      "workspace-generated-header",
      "workspace-generated-source",
      "workspace-renode-resc",
      "workspace-renode-robot",
    ]);
    expect(documents.find((document) => document.id === "header")?.content).toContain("uart_shell_1_init");
    expect(documents.find((document) => document.id === "overlay")).toMatchObject({
      sourceKind: "editable-project-asset",
      freshnessState: "stale",
    });
    expect(documents.find((document) => document.id === "fragments")).toMatchObject({
      sourceKind: "derived-output",
      exportSummary: expect.stringContaining("workspace Export Artifacts"),
    });
    expect(documents.find((document) => document.id === "header")?.freshnessLabel).toBe("Derived");
    expect(diagnostics.some((entry) => entry.navigation.panelId === "workspace-generated-overlay")).toBe(true);
  });
});