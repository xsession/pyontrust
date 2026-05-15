import type { BoardSummary } from "../../contracts/api";
import { defaultRenodeProfile } from "../../project/projectDocument";
import { buildArtifactDiagnosticEntries, buildArtifactReviewDocuments } from "../../project/artifactReview";
import { protocolTemplateById } from "../../project/protocolEditor";
import { selectProjectArtifactStatus, selectProjectIntegrityLabel, selectProjectIntegrityStatus, selectProjectReadinessLabel } from "../../project/selectors";
import type { ProjectShellController } from "../../project/useProjectShellController";
import type { PinAssignmentsViewModel } from "../../shared/viewModels/pinAssignments";
import type { ShellOutputChannelViewModel, ShellOutputEntryViewModel } from "../../presenters/useShellPresenter";

export interface BuildSimTestPresenter {
  outputChannels: ShellOutputChannelViewModel[];
  executionWorkbench: ExecutionWorkbenchViewModel;
}

export interface ExecutionWorkbenchViewModel {
  tasks: ExecutionTaskViewModel[];
  machineOptions: ExecutionMachineOptionViewModel[];
  selectedMachine: string;
  support: {
    tone: "info" | "success" | "warning";
    title: string;
    detail: string;
  };
}

export interface ExecutionTaskViewModel {
  id: "build" | "simulation" | "tests";
  label: string;
  status: "idle" | "ready" | "blocked" | "running";
  detail: string;
  latestLog: string;
}

export interface ExecutionMachineOptionViewModel {
  value: string;
  label: string;
  detail: string;
  recommended: boolean;
}

type BuildSimTestPresenterInput = Pick<ProjectShellController, "projectDocument" | "projectBusy" | "projectStatus"> & {
  activeBoard: BoardSummary | null;
  pinAssignments: Pick<PinAssignmentsViewModel, "summary">;
};

export function createBuildSimTestPresenter({ activeBoard, projectDocument, projectBusy, projectStatus, pinAssignments }: BuildSimTestPresenterInput): BuildSimTestPresenter {
  const artifacts = selectProjectArtifactStatus(projectDocument);
  const readinessLabel = selectProjectReadinessLabel(projectDocument);
  const integrity = selectProjectIntegrityStatus(projectDocument);
  const integrityLabel = selectProjectIntegrityLabel(projectDocument);
  const enabledProtocols = projectDocument.protocol_editor.entries.filter((entry) => entry.enabled !== false);
  const unresolvedPins = Math.max(pinAssignments.summary.unresolvedCount, 0);
  const recommendedRenodeProfile = defaultRenodeProfile(activeBoard?.board ?? activeBoard?.id ?? "");
  const recommendedMachine = recommendedRenodeProfile.platform.trim();
  const currentMachine = projectDocument.renode.platform.trim();
  const protocolLabels = enabledProtocols.map((entry) => {
    const instanceName = entry.values.instanceName;
    if (typeof instanceName === "string" && instanceName.trim().length > 0) {
      return instanceName.trim();
    }

    return protocolTemplateById(entry.templateId).label;
  });
  const artifactDiagnostics = buildArtifactDiagnosticEntries(
    buildArtifactReviewDocuments({
      activeBoard,
      projectDocument,
      unresolvedPinCount: pinAssignments.summary.unresolvedCount,
    }),
  );

  const buildEntries: ShellOutputEntryViewModel[] = [
    {
      id: "build-summary",
      timestamp: "now",
      summary: projectBusy ? "Workspace actions are running." : "Build pipeline shell channel is idle.",
      detail: projectBusy
        ? "Persistence or export actions are active in the shell controller."
        : `${readinessLabel}. ${artifacts.enabledProtocolEntryCount} enabled protocol entries are currently staged for code generation.`,
      severity: projectBusy ? "warning" : "info",
    },
    {
      id: "build-artifacts",
      timestamp: "generated",
      summary: artifacts.authorityState === "authoritative" ? "Generated outputs are authoritative." : "Generated outputs still need attention.",
      detail: artifacts.authorityReason,
      severity: artifacts.authorityState === "authoritative" ? "success" : artifacts.authorityState === "stale" ? "warning" : "info",
    },
  ];

  const simulationEntries: ShellOutputEntryViewModel[] = [
    {
      id: "sim-target",
      timestamp: "renode",
      summary: projectDocument.renode.enabled ? "Renode profile is enabled." : "Renode profile is disabled.",
      detail: projectDocument.renode.platform.trim() || "No Renode platform target is configured yet.",
      severity: projectDocument.renode.enabled && projectDocument.renode.platform.trim() ? "success" : projectDocument.renode.enabled ? "warning" : "info",
    },
    {
      id: "sim-handshake",
      timestamp: "appbench",
      summary: projectDocument.renode.appbench_target.trim() ? "Simulation handoff target is present." : "Simulation handoff target is pending.",
      detail: projectDocument.renode.appbench_target.trim() || "AppBench target not configured.",
      severity: projectDocument.renode.appbench_target.trim() ? "info" : "warning",
    },
  ];

  const diagnosticsEntries: ShellOutputEntryViewModel[] = [
    {
      id: "diag-integrity",
      timestamp: "integrity",
      summary: integrity.warningCount ? "Project integrity warnings require attention." : "Project integrity checks are passing.",
      detail: integrity.warningCount ? integrity.issues.join("; ") : integrityLabel,
      severity: integrity.warningCount ? "warning" : "success",
    },
    {
      id: "diag-pins",
      timestamp: "pins",
      summary: unresolvedPins ? `${unresolvedPins} unresolved pin assignments remain.` : "Pin assignment set is fully resolved for the saved state.",
      detail: unresolvedPins
        ? "Resolve pin mismatches before treating generated artifacts as final."
        : `${pinAssignments.summary.resolvedCount} resolved selections are currently reflected in the shell.`,
      severity: unresolvedPins ? "warning" : "success",
    },
    ...artifactDiagnostics.slice(0, 6).map((entry) => ({
      id: `artifact-${entry.id}`,
      timestamp: "codegen",
      summary: entry.summary,
      detail: entry.detail,
      severity: entry.severity,
      navigation: entry.navigation,
    })),
  ];

  const testEntries: ShellOutputEntryViewModel[] = [
    {
      id: "test-protocols",
      timestamp: "protocol",
      summary: enabledProtocols.length ? `${enabledProtocols.length} protocol entries are enabled for validation.` : "No enabled protocol entries are available for validation.",
      detail: enabledProtocols.length
        ? protocolLabels.join(", ")
        : "Enable at least one protocol entry before build and simulation validation.",
      severity: enabledProtocols.length ? "info" : "warning",
    },
    {
      id: "test-shell",
      timestamp: "workspace",
      summary: projectStatus.tone === "error" ? "Workspace shell reported a blocking status." : "Workspace shell is ready for the next validation action.",
      detail: projectStatus.message,
      severity: projectStatus.tone === "error" ? "error" : projectBusy ? "warning" : "success",
    },
  ];

  const machineOptions = buildMachineOptions({
    activeBoard,
    currentMachine,
    recommendedMachine,
  });
  const support = buildSimulationSupport({
    activeBoard,
    currentMachine,
    projectDocument,
  });
  const tasks: ExecutionTaskViewModel[] = [
    {
      id: "build",
      label: "Build Console",
      status: projectBusy
        ? "running"
        : integrity.warningCount > 0 || unresolvedPins > 0
          ? "blocked"
          : artifacts.enabledProtocolEntryCount > 0 || artifacts.authorityState === "authoritative"
            ? "ready"
            : "idle",
      detail: projectBusy
        ? "The workspace controller is currently running a save, load, or export action."
        : integrity.warningCount > 0
          ? `Resolve ${integrity.warningCount} project integrity warning${integrity.warningCount === 1 ? "" : "s"} before treating build outputs as final.`
          : unresolvedPins > 0
            ? `Resolve ${unresolvedPins} pin assignment issue${unresolvedPins === 1 ? "" : "s"} before build handoff.`
            : `${artifacts.enabledProtocolEntryCount} enabled protocol entr${artifacts.enabledProtocolEntryCount === 1 ? "y is" : "ies are"} staged for code generation and export.`,
      latestLog: buildEntries[0]?.summary ?? "Build console is awaiting the next action.",
    },
    {
      id: "simulation",
      label: "Simulation Console",
      status: projectBusy ? "running" : projectDocument.renode.enabled && currentMachine ? "ready" : projectDocument.renode.enabled ? "blocked" : "idle",
      detail: projectDocument.renode.enabled
        ? currentMachine
          ? `Machine target ${currentMachine} is selected for Renode export.`
          : "Choose a Renode machine target before exporting a simulation bundle."
        : "Enable Renode when you are ready to stage simulation handoff from the workspace.",
      latestLog: simulationEntries[0]?.summary ?? "Simulation console is awaiting a machine target.",
    },
    {
      id: "tests",
      label: "Test Console",
      status: projectBusy
        ? "running"
        : enabledProtocols.length > 0 && projectDocument.renode.robot_target.trim()
          ? "ready"
          : enabledProtocols.length > 0
            ? "blocked"
            : "idle",
      detail: enabledProtocols.length > 0
        ? projectDocument.renode.robot_target.trim()
          ? `Robot target ${projectDocument.renode.robot_target.trim()} is ready for validation follow-up.`
          : "Populate a Robot target before treating tests as launch-ready."
        : "Enable at least one protocol entry before moving into workspace test review.",
      latestLog: testEntries[0]?.summary ?? "Test console is awaiting validation setup.",
    },
  ];

  return {
    executionWorkbench: {
      tasks,
      machineOptions,
      selectedMachine: currentMachine,
      support,
    },
    outputChannels: [
      {
        id: "build",
        label: "Build Output",
        badge: String(buildEntries.length),
        tone: artifacts.authorityState === "authoritative" ? "success" : "warning",
        entries: buildEntries,
      },
      {
        id: "simulation",
        label: "Simulation Output",
        badge: String(simulationEntries.length),
        tone: projectDocument.renode.enabled && projectDocument.renode.platform.trim() ? "success" : "warning",
        entries: simulationEntries,
      },
      {
        id: "diagnostics",
        label: "Diagnostics",
        badge: String(diagnosticsEntries.length),
        tone: integrity.warningCount ? "warning" : "success",
        entries: diagnosticsEntries,
      },
      {
        id: "tests",
        label: "Test Readiness",
        badge: String(testEntries.length),
        tone: enabledProtocols.length ? "neutral" : "warning",
        entries: testEntries,
      },
    ],
  };
}

function buildMachineOptions({
  activeBoard,
  currentMachine,
  recommendedMachine,
}: {
  activeBoard: BoardSummary | null;
  currentMachine: string;
  recommendedMachine: string;
}): ExecutionMachineOptionViewModel[] {
  const options = new Map<string, ExecutionMachineOptionViewModel>();

  options.set("", {
    value: "",
    label: "No machine selected",
    detail: "Leave simulation disabled until a Renode machine target is chosen.",
    recommended: false,
  });

  if (recommendedMachine) {
    options.set(recommendedMachine, {
      value: recommendedMachine,
      label: activeBoard ? `${activeBoard.name} recommended machine` : "Recommended machine",
      detail: activeBoard
        ? `Use the default Renode platform for ${activeBoard.name} (${activeBoard.package}).`
        : "Use the current board default Renode machine.",
      recommended: true,
    });
  }

  if (currentMachine && !options.has(currentMachine)) {
    options.set(currentMachine, {
      value: currentMachine,
      label: "Custom machine target",
      detail: "Preserve the custom Renode platform currently stored in the project document.",
      recommended: false,
    });
  }

  return [...options.values()];
}

function buildSimulationSupport({
  activeBoard,
  currentMachine,
  projectDocument,
}: {
  activeBoard: BoardSummary | null;
  currentMachine: string;
  projectDocument: BuildSimTestPresenterInput["projectDocument"];
}): ExecutionWorkbenchViewModel["support"] {
  if (!projectDocument.renode.enabled) {
    return {
      tone: "info",
      title: "Simulation handoff is idle",
      detail: "Enable Renode when you are ready to stage a machine target, scripts, and automation bundle from the workspace.",
    };
  }

  if (!currentMachine) {
    return {
      tone: "warning",
      title: "Machine target required",
      detail: activeBoard
        ? `Select a Renode machine for ${activeBoard.name} before exporting the demo bundle.`
        : "Select a Renode machine before exporting the demo bundle.",
    };
  }

  if (!projectDocument.renode.appbench_target.trim() || !projectDocument.renode.robot_target.trim()) {
    return {
      tone: "warning",
      title: "Automation targets need review",
      detail: "AppBench and Robot targets should both be populated before handing the workspace off to simulation and test review.",
    };
  }

  return {
    tone: "success",
    title: "Simulation bundle is staged",
    detail: `Renode machine, AppBench target, and Robot target are aligned for ${currentMachine}.`,
  };
}