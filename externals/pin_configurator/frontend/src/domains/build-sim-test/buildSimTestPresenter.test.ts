import { createBuildSimTestPresenter } from "./buildSimTestPresenter";
import { createEmptyProjectDocument } from "../../contracts/api";
import { buildGeneratedConfFromBoard, buildGeneratedFragmentsFromBoard, buildGeneratedOverlayFromBoard } from "../../project/generatedArtifacts";

const activeBoard = {
  id: "mspm0g3507",
  name: "MSPM0G3507",
  board: "lp_mspm0g3507",
  package: "QFP-48",
  pin_count: 48,
} as const;

describe("createBuildSimTestPresenter", () => {
  it("derives simulation and diagnostics channels from the canonical project document", () => {
    const projectDocument = createEmptyProjectDocument();
    projectDocument.renode.enabled = true;
    projectDocument.renode.platform = "platforms/boards/ti/lp_mspm0g3507.repl";
    projectDocument.renode.appbench_target = "appbench";
    projectDocument.renode.robot_target = "";
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
      activeBoard,
      projectDocument,
      projectBusy: false,
      projectStatus: { tone: "neutral", message: "Workspace ready." },
      pinAssignments: {
        summary: {
          resolvedCount: 2,
          savedCount: 2,
          unresolvedCount: 0,
        },
        issuesByPinNumber: {
          "12": [
            {
              id: "pin:12:drive-clash",
              title: "UART0_TX electrical defaults conflict",
              summary: "Pull-up and pull-down are both enabled on the same route.",
            },
          ],
        },
      },
      clockWarnings: ["pll0 configuration requires board review"],
    });

    expect(presenter.outputChannels.map((channel) => channel.id)).toEqual(["build", "simulation", "diagnostics", "tests"]);
    expect(presenter.outputChannels[1]).toMatchObject({
      id: "simulation",
      badge: "Ready",
      tone: "success",
    });
    expect(presenter.outputChannels[0]).toMatchObject({
      id: "build",
      badge: "Blocked",
      tone: "warning",
    });
    expect(presenter.outputChannels[2]).toMatchObject({
      id: "diagnostics",
      badge: "7 issues",
      tone: "warning",
    });
    expect(presenter.outputChannels[3]).toMatchObject({
      id: "tests",
      badge: "Target",
      tone: "warning",
    });
    expect(presenter.outputChannels[2]?.entries.some((entry) => Boolean(entry.navigation))).toBe(true);
    expect(presenter.outputChannels[2]?.entries.some((entry) => entry.summary.includes("pin conflict"))).toBe(true);
    expect(presenter.outputChannels[2]?.entries.some((entry) => entry.summary.includes("clock validation"))).toBe(true);
    expect(presenter.outputChannels[3]?.entries[0]?.detail).toContain("uart_shell_1");
    expect(presenter.executionWorkbench.selectedMachine).toBe("platforms/boards/ti/lp_mspm0g3507.repl");
    expect(presenter.executionWorkbench.machineOptions.some((option) => option.recommended)).toBe(true);
    expect(presenter.executionWorkbench.support.tone).toBe("warning");
    expect(presenter.executionWorkbench.tasks.map((task) => task.id)).toEqual(["build", "simulation", "tests"]);
    expect(presenter.executionWorkbench.tasks[1]).toMatchObject({
      id: "simulation",
      status: "ready",
    });
  });

  it("updates readiness and diagnostics badges when representative blockers are cleared", () => {
    const blockedProject = createEmptyProjectDocument();
    blockedProject.board_id = "lp_mspm0g3507";
    blockedProject.renode.enabled = true;
    blockedProject.renode.platform = "";
    blockedProject.protocol_editor.entries = [];

    const blockedPresenter = createBuildSimTestPresenter({
      activeBoard,
      projectDocument: blockedProject,
      projectBusy: false,
      projectStatus: { tone: "neutral", message: "Workspace ready." },
      pinAssignments: {
        summary: {
          resolvedCount: 0,
          savedCount: 1,
          unresolvedCount: 1,
        },
        issuesByPinNumber: {
          "12": [
            {
              id: "pin:12:drive-clash",
              title: "UART0_TX electrical defaults conflict",
              summary: "Pull-up and pull-down are both enabled on the same route.",
            },
          ],
        },
      },
      clockWarnings: ["pll0 configuration requires board review"],
    });

    const readyProject = createEmptyProjectDocument();
    readyProject.board_id = "lp_mspm0g3507";
    readyProject.generated_overlay = buildGeneratedOverlayFromBoard(activeBoard);
    readyProject.generated_conf = buildGeneratedConfFromBoard(activeBoard);
    readyProject.generated_fragments = buildGeneratedFragmentsFromBoard(activeBoard);
    readyProject.renode.enabled = true;
    readyProject.renode.platform = "platforms/boards/ti/lp_mspm0g3507.repl";
    readyProject.renode.appbench_target = "appbench";
    readyProject.renode.robot_target = "robotbench";
    readyProject.renode.resc = [
      "mach create",
      "machine LoadPlatformDescription @platforms/boards/ti/lp_mspm0g3507.repl",
      "showAnalyzer sysbus.uart0",
      "start",
    ].join("\n");
    readyProject.renode.robot = [
      "*** Settings ***",
      "Suite Setup    Log    lp_mspm0g3507 ready for robotbench",
      "",
      "*** Test Cases ***",
      "Smoke Boot",
      "    Log    Open analyzer for sysbus.uart0",
    ].join("\n");
    readyProject.protocol_editor.entries = [
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

    const readyPresenter = createBuildSimTestPresenter({
      activeBoard,
      projectDocument: readyProject,
      projectBusy: false,
      projectStatus: { tone: "success", message: "Workspace ready." },
      pinAssignments: {
        summary: {
          resolvedCount: 1,
          savedCount: 1,
          unresolvedCount: 0,
        },
        issuesByPinNumber: {},
      },
      clockWarnings: [],
    });

    expect(blockedPresenter.outputChannels.find((channel) => channel.id === "build")).toMatchObject({
      badge: "Blocked",
      tone: "warning",
    });
    expect(blockedPresenter.outputChannels.find((channel) => channel.id === "simulation")).toMatchObject({
      badge: "Target",
      tone: "warning",
    });
    expect(blockedPresenter.outputChannels.find((channel) => channel.id === "diagnostics")).toMatchObject({
      tone: "warning",
    });
    expect(blockedPresenter.outputChannels.find((channel) => channel.id === "diagnostics")?.badge).not.toBe("Passing");
    expect(blockedPresenter.outputChannels.find((channel) => channel.id === "tests")).toMatchObject({
      badge: "Idle",
      tone: "warning",
    });

    expect(readyPresenter.outputChannels.find((channel) => channel.id === "build")).toMatchObject({
      badge: "Ready",
      tone: "success",
    });
    expect(readyPresenter.outputChannels.find((channel) => channel.id === "simulation")).toMatchObject({
      badge: "Ready",
      tone: "success",
    });
    expect(readyPresenter.outputChannels.find((channel) => channel.id === "diagnostics")).toMatchObject({
      badge: "Passing",
      tone: "success",
    });
    expect(readyPresenter.outputChannels.find((channel) => channel.id === "tests")).toMatchObject({
      badge: "Ready",
      tone: "success",
    });
  });
});