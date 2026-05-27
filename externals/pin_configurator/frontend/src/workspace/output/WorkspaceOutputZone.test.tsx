import { fireEvent, render, screen } from "@testing-library/react";
import { useState } from "react";
import { createEmptyProjectDocument } from "../../contracts/api";
import type { ExecutionWorkbenchViewModel } from "../../domains/build-sim-test/buildSimTestPresenter";
import type { ShellOutputChannelViewModel } from "../../presenters/useShellPresenter";
import { WorkspaceOutputZone } from "./WorkspaceOutputZone";

const emptyPinAssignments = {
  summary: {
    resolvedCount: 0,
    savedCount: 0,
    unresolvedCount: 0,
  },
  rows: [],
  issuesByPinNumber: {},
  propertyValuesByPinNumber: {},
  altFunctionOptionsByPinNumber: {},
};

const outputChannels: ShellOutputChannelViewModel[] = [
  {
    id: "build",
    label: "Build Output",
    badge: "Blocked",
    tone: "warning",
    entries: [
      {
        id: "build-1",
        timestamp: "now",
        summary: "Build pipeline shell channel is idle.",
        detail: "Build output is waiting for the next action.",
        severity: "info",
      },
    ],
  },
  {
    id: "diagnostics",
    label: "Diagnostics",
    badge: "1 issue",
    tone: "warning",
    entries: [
      {
        id: "diag-1",
        timestamp: "now",
        summary: "Diagnostics restored.",
        detail: "1 clock validation warning remains.",
        severity: "warning",
      },
    ],
  },
];

const executionWorkbench: ExecutionWorkbenchViewModel = {
  selectedMachine: "",
  machineOptions: [
    {
      value: "",
      label: "No machine selected",
      detail: "",
      recommended: false,
    },
  ],
  support: {
    tone: "info",
    title: "Support pending",
    detail: "",
  },
  tasks: [
    {
      id: "build",
      label: "Build Console",
      status: "idle",
      detail: "",
      latestLog: "Build output is idle.",
    },
    {
      id: "simulation",
      label: "Simulation Console",
      status: "idle",
      detail: "",
      latestLog: "Simulation output is idle.",
    },
    {
      id: "tests",
      label: "Test Console",
      status: "idle",
      detail: "",
      latestLog: "Test output is idle.",
    },
  ],
};

function CompactHarness() {
  const [activeChannelId, setActiveChannelId] = useState("build");
  const activeOutputChannel = outputChannels.find((channel) => channel.id === activeChannelId) ?? outputChannels[0] ?? null;

  return (
    <WorkspaceOutputZone
      outputChannels={outputChannels}
      activeOutputChannel={activeOutputChannel}
      compact
      executionWorkbench={executionWorkbench}
      followOutput
      severityFilter="all"
      projectStatus={{ tone: "success", message: "Shell project state ready." }}
      projectBusy={false}
      projectFilePath="C:/tmp/demo.zpinproj"
      projectDocument={createEmptyProjectDocument()}
      pinAssignments={emptyPinAssignments}
      onSelectChannel={setActiveChannelId}
      onSelectSeverityFilter={() => undefined}
      onToggleFollow={() => undefined}
      onCopyVisibleEntries={() => undefined}
      onResetView={() => undefined}
      onNavigateEntry={() => undefined}
      onSelectRenodeMachine={() => undefined}
      onSeedArtifacts={() => undefined}
      onExportArtifacts={() => undefined}
      onExportRenodeBundle={() => undefined}
      onOpenRenodeProfile={() => undefined}
      onOpenRenodeResc={() => undefined}
      onOpenRobotTests={() => undefined}
    />
  );
}

describe("WorkspaceOutputZone", () => {
  it("renders a compact channel selector in bring-up mode", () => {
    render(<CompactHarness />);

    expect(screen.queryByText("Execution workbench")).not.toBeInTheDocument();
    expect(screen.queryByRole("tablist", { name: "Execution output channels" })).not.toBeInTheDocument();
    const channelSelector = screen.getByRole("combobox", { name: "Execution output channel" });
    expect(channelSelector).toHaveValue("build");
    expect(screen.getByRole("log", { name: "Build Output entries" })).toBeInTheDocument();

    fireEvent.change(channelSelector, { target: { value: "diagnostics" } });

    expect(screen.getByRole("log", { name: "Diagnostics entries" })).toBeInTheDocument();
    expect(screen.getByText("1 clock validation warning remains.")).toBeInTheDocument();
  });
});