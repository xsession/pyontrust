import { createEmptyProjectDocument } from "../../contracts/api";
import { buildWorkspaceStatusBarItems } from "./buildWorkspaceStatusBarItems";

describe("buildWorkspaceStatusBarItems", () => {
  it("surfaces readiness, artifact authority, and integrity warnings in the status bar", () => {
    const projectDocument = createEmptyProjectDocument();
    projectDocument.board_id = "lp_mspm0g3507";
    projectDocument.renode.enabled = true;
    projectDocument.renode.platform = "";
    projectDocument.protocol_editor.entries = [];
    projectDocument.generated_overlay = "/ { chosen { zephyr,console = &uart0; }; };";
    projectDocument.generated_fragments = {
      board: { id: "lp_mspm0g3107" },
      outputs: { overlay: "/ { chosen { zephyr,console = &uart0; }; };" },
    };

    const items = buildWorkspaceStatusBarItems({
      activeBoard: {
        id: "mspm0g3507",
        name: "MSPM0G3507",
        board: "lp_mspm0g3507",
        package: "QFP-48",
        pin_count: 48,
      },
      projectDocument,
      projectFilePath: "C:/tmp/demo.zpinproj",
      canUndoProjectDocument: true,
      projectBusy: false,
      projectStatus: { tone: "neutral", message: "Shell project state ready." },
    });

    expect(items.find((item) => item.id === "readiness")).toMatchObject({
      label: "Readiness",
      value: "2/4 Ready",
      tone: "neutral",
    });
    expect(items.find((item) => item.id === "artifacts")).toMatchObject({
      label: "Artifacts",
      value: "Stale",
      tone: "warning",
    });
    expect(items.find((item) => item.id === "integrity")).toMatchObject({
      label: "Integrity",
      value: "3 warnings",
      tone: "warning",
    });
  });

  it("marks a fully prepared workspace as passing", () => {
    const projectDocument = createEmptyProjectDocument();
    projectDocument.board_id = "lp_mspm0g3507";
    projectDocument.renode.enabled = true;
    projectDocument.renode.platform = "platforms/boards/ti/lp_mspm0g3507.repl";
    projectDocument.generated_overlay = "/ { chosen { zephyr,console = &uart0; }; };";
    projectDocument.generated_conf = "CONFIG_SERIAL=y";
    projectDocument.generated_fragments = {
      board: { id: "lp_mspm0g3507" },
      outputs: {
        overlay: "/ { chosen { zephyr,console = &uart0; }; };",
        config: "CONFIG_SERIAL=y",
      },
      protocols: {
        uart_shell_bridge: true,
      },
    };
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

    const items = buildWorkspaceStatusBarItems({
      activeBoard: {
        id: "mspm0g3507",
        name: "MSPM0G3507",
        board: "lp_mspm0g3507",
        package: "QFP-48",
        pin_count: 48,
      },
      projectDocument,
      projectFilePath: "C:/tmp/demo.zpinproj",
      canUndoProjectDocument: false,
      projectBusy: false,
      projectStatus: { tone: "success", message: "Workspace ready." },
    });

    expect(items.find((item) => item.id === "readiness")).toMatchObject({
      value: "4/4 Ready",
      tone: "success",
    });
    expect(items.find((item) => item.id === "artifacts")).toMatchObject({
      value: "Authoritative",
      tone: "success",
    });
    expect(items.find((item) => item.id === "integrity")).toMatchObject({
      value: "Passing",
      tone: "success",
    });
  });
});