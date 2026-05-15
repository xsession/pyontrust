import { createBuildSimTestPresenter } from "./buildSimTestPresenter";
import { createEmptyProjectDocument } from "../../contracts/api";

describe("createBuildSimTestPresenter", () => {
  it("derives simulation and diagnostics channels from the canonical project document", () => {
    const projectDocument = createEmptyProjectDocument();
    projectDocument.renode.enabled = true;
    projectDocument.renode.platform = "platforms/boards/ti/lp_mspm0g3507.repl";
    projectDocument.renode.appbench_target = "appbench";
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

    const presenter = createBuildSimTestPresenter({
      activeBoard: {
        id: "mspm0g3507",
        name: "MSPM0G3507",
        board: "lp_mspm0g3507",
        package: "QFP-48",
        pin_count: 48,
      },
      projectDocument,
      projectBusy: false,
      projectStatus: { tone: "neutral", message: "Workspace ready." },
      pinAssignments: {
        summary: {
          resolvedCount: 2,
          savedCount: 2,
          unresolvedCount: 0,
        },
      },
    });

    expect(presenter.outputChannels.map((channel) => channel.id)).toEqual(["build", "simulation", "diagnostics", "tests"]);
    expect(presenter.outputChannels[1]).toMatchObject({
      id: "simulation",
      tone: "success",
    });
    expect(presenter.outputChannels[2]?.entries.some((entry) => Boolean(entry.navigation))).toBe(true);
    expect(presenter.outputChannels[3]?.entries[0]?.detail).toContain("uart_shell_1");
    expect(presenter.executionWorkbench.selectedMachine).toBe("platforms/boards/ti/lp_mspm0g3507.repl");
    expect(presenter.executionWorkbench.machineOptions.some((option) => option.recommended)).toBe(true);
    expect(presenter.executionWorkbench.support.tone).toBe("success");
    expect(presenter.executionWorkbench.tasks.map((task) => task.id)).toEqual(["build", "simulation", "tests"]);
    expect(presenter.executionWorkbench.tasks[1]).toMatchObject({
      id: "simulation",
      status: "ready",
    });
  });
});