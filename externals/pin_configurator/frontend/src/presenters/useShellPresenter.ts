import { startTransition, useEffect, useMemo, useState } from "react";
import type { BoardSummary } from "../contracts/api";
import { createBuildSimTestPresenter, type ExecutionWorkbenchViewModel } from "../domains/build-sim-test/buildSimTestPresenter";
import { useZephyrCatalogPresenter, type ZephyrCatalogPresenter } from "../domains/catalog/zephyrCatalogPresenter";
import { useClockConfiguratorPresenter, type ClockConfiguratorPresenter } from "../domains/clock/clockConfiguratorPresenter";
import { useBoardEditorPresenter, type BoardEditorPresenter } from "../domains/board-editor/boardEditorPresenter";
import { createGeneratedOutputPresenter } from "../domains/generated-output/generatedOutputPresenter";
import { createInterruptConfiguratorPresenter, type InterruptConfiguratorPresenter } from "../domains/interrupts/interruptConfiguratorPresenter";
import { useLvglLayoutPresenter, type LvglLayoutPresenter } from "../domains/lvgl/lvglLayoutPresenter";
import { useModuleConfiguratorPresenter, type ModuleConfiguratorPresenter } from "../domains/modules/moduleConfiguratorPresenter";
import { createPackageManagerPresenter, type PackageManagerPresenter } from "../domains/packages/packageManagerPresenter";
import { createPeripheralConfiguratorPresenter, type PeripheralConfiguratorPresenter } from "../domains/peripherals/peripheralConfiguratorPresenter";
import { createPinConfiguratorPresenter } from "../domains/pins/pinConfiguratorPresenter";
import { createProtocolEditorPresenter } from "../domains/protocols/protocolEditorPresenter";
import { createRenodeProfilePresenter } from "../domains/renode/renodeProfilePresenter";
import { createSensorParserPresenter, type SensorParserPresenter } from "../domains/sensors/sensorParserPresenter";
import type { RehydratedPinStateMap } from "../project/legacyHardwareState";
import { selectProjectArtifactStatus, selectProjectIntegrityLabel, selectProjectIntegrityStatus, selectProjectReadinessLabel } from "../project/selectors";
import { describeError } from "../shared/errors/apiError";
import { pinConfiguratorApi } from "../services/pinConfiguratorApi";
import { useProjectShellController } from "../project/useProjectShellController";
import type { ProjectStatus } from "../project/workspaceState";
import type { PinAssignmentAltFunctionOptionViewModel, PinAssignmentsViewModel } from "../shared/viewModels/pinAssignments";

export interface ShellMetric {
  label: string;
  value: string;
  detail: string;
  accent: "sun" | "mint" | "signal";
}

export interface ShellStatusItemViewModel {
  id: string;
  label: string;
  value: string;
  detail: string;
  tone: "neutral" | "success" | "warning";
}

export interface ShellOutputEntryViewModel {
  id: string;
  timestamp: string;
  summary: string;
  detail: string;
  severity: "info" | "success" | "warning" | "error";
  navigation?: {
    panelId: string;
    lineNumber?: number;
    column?: number;
    label: string;
  };
}

export interface ShellOutputChannelViewModel {
  id: string;
  label: string;
  badge: string;
  tone: "neutral" | "success" | "warning";
  entries: ShellOutputEntryViewModel[];
}

export interface ShellCommandViewModel {
  id: string;
  label: string;
  description: string;
  shortcut: string;
  group: "Project" | "History" | "Export" | "Artifacts";
  disabled: boolean;
  run: () => void;
}

export interface ShellViewModel {
  boards: BoardSummary[];
  activeBoard: BoardSummary | null;
  loading: boolean;
  error: string;
  metrics: ShellMetric[];
  commands: ShellCommandViewModel[];
  statusBarItems: ShellStatusItemViewModel[];
  outputChannels: ShellOutputChannelViewModel[];
  executionWorkbench: ExecutionWorkbenchViewModel;
  projectDocument: ReturnType<typeof useProjectShellController>["projectDocument"];
  generatedFragments: string;
  pinAssignments: PinAssignmentsViewModel;
  peripheralConfigurator: PeripheralConfiguratorPresenter;
  moduleConfigurator: ModuleConfiguratorPresenter;
  clockConfigurator: ClockConfiguratorPresenter;
  lvglLayout: LvglLayoutPresenter;
  boardEditor: BoardEditorPresenter;
  interruptConfigurator: InterruptConfiguratorPresenter;
  sensorParser: SensorParserPresenter;
  packageManager: PackageManagerPresenter;
  zephyrCatalog: ZephyrCatalogPresenter;
  hydratedPinStates: RehydratedPinStateMap;
  canUndoProjectDocument: boolean;
  canRedoProjectDocument: boolean;
  projectFilePath: string;
  projectStatus: ProjectStatus;
  projectBusy: boolean;
  setProjectFilePath: (value: string) => void;
  selectBoard: (boardId: string) => void;
  updateRenodeField: ReturnType<typeof useProjectShellController>["updateRenodeField"];
  addProtocolEntry: ReturnType<typeof useProjectShellController>["addProtocolEntry"];
  selectProtocolEntry: ReturnType<typeof useProjectShellController>["selectProtocolEntry"];
  removeProtocolEntry: ReturnType<typeof useProjectShellController>["removeProtocolEntry"];
  toggleProtocolEntry: ReturnType<typeof useProjectShellController>["toggleProtocolEntry"];
  updateProtocolEntryValue: ReturnType<typeof useProjectShellController>["updateProtocolEntryValue"];
  updateGeneratedOverlay: (value: string) => void;
  updateGeneratedConf: (value: string) => void;
  clearPinAssignment: (pinNumber: string) => void;
  assignPinAltFunction: (pinNumber: string, option: PinAssignmentAltFunctionOptionViewModel) => void;
  updatePinBooleanProperty: (pinNumber: string, propertyKey: string, value: boolean) => void;
  undoProjectDocument: () => void;
  redoProjectDocument: () => void;
  exportGeneratedArtifacts: () => void;
  exportRenodeSimulation: () => void;
  seedGeneratedArtifacts: () => void;
  clearGeneratedArtifacts: () => void;
  saveProjectFile: () => void;
  loadProjectFile: () => void;
}

export function useShellPresenter(): ShellViewModel {
  const [boards, setBoards] = useState<BoardSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const projectController = useProjectShellController(boards);

  useEffect(() => {
    let active = true;

    async function loadBoards() {
      try {
        const result = await pinConfiguratorApi.listBoards();
        if (!active) {
          return;
        }
        startTransition(() => {
          setBoards(result);
          setError("");
        });
      } catch (err) {
        if (!active) {
          return;
        }
        setError(describeError(err, "Failed to load boards."));
      } finally {
        if (active) {
          setLoading(false);
        }
      }
    }

    void loadBoards();

    return () => {
      active = false;
    };
  }, []);

  const pinConfigurator = useMemo(
    () => createPinConfiguratorPresenter(projectController),
    [projectController],
  );

  const protocolEditor = useMemo(
    () => createProtocolEditorPresenter(projectController),
    [projectController],
  );

  const renodeProfile = useMemo(
    () => createRenodeProfilePresenter(projectController),
    [projectController],
  );

  const peripheralConfigurator = useMemo(
    () => createPeripheralConfiguratorPresenter(projectController),
    [projectController],
  );

  const moduleConfigurator = useModuleConfiguratorPresenter();

  const clockConfigurator = useClockConfiguratorPresenter(projectController.activeBoardDefinition);

  const lvglLayout = useLvglLayoutPresenter(projectController);

  const boardEditor = useBoardEditorPresenter(projectController.activeBoardDefinition, projectController.activeBoard);

  const sensorParser = useMemo(
    () => createSensorParserPresenter(projectController),
    [projectController],
  );

  const packageManager = useMemo(
    () => createPackageManagerPresenter(projectController),
    [projectController],
  );

  const generatedOutput = useMemo(
    () => createGeneratedOutputPresenter(projectController),
    [projectController],
  );

  const zephyrCatalog = useZephyrCatalogPresenter({
    boards,
    selectBoard: projectController.selectBoard,
    peripheralConfigurator,
    sensorParser,
    packageManager,
  });

  const interruptConfigurator = useMemo(
    () => createInterruptConfiguratorPresenter(projectController.projectDocument, moduleConfigurator, clockConfigurator),
    [clockConfigurator, moduleConfigurator, projectController.projectDocument],
  );

  const generatedFragments = useMemo(
    () => generatedOutput.generatedFragments,
    [generatedOutput.generatedFragments],
  );

  const metrics = useMemo<ShellMetric[]>(() => {
    const boardPackages = new Set(boards.map((board) => board.package).filter(Boolean));
    const boardFamilies = new Set(boards.map((board) => board.name).filter(Boolean));
    const artifacts = selectProjectArtifactStatus(projectController.projectDocument);
    const readinessLabel = selectProjectReadinessLabel(projectController.projectDocument);
    const integrity = selectProjectIntegrityStatus(projectController.projectDocument);
    const integrityLabel = selectProjectIntegrityLabel(projectController.projectDocument);

    return [
      {
        label: "Board Surface",
        value: loading ? "Loading" : String(boards.length),
        detail: error || "Backend route contract loaded through the new typed service layer.",
        accent: "sun",
      },
      {
        label: "Package Coverage",
        value: String(boardPackages.size),
        detail: "Unique package shapes currently visible to the React shell.",
        accent: "mint",
      },
      {
        label: "Project Readiness",
        value: `${artifacts.enabledProtocolEntryCount}/${Math.max(artifacts.protocolEntryCount, 1)}`,
        detail: `${readinessLabel}. ${integrityLabel}. ${boardFamilies.size} SoC families currently surfaced by the API.`,
        accent: "signal",
      },
      {
        label: "Integrity Warnings",
        value: String(integrity.warningCount),
        detail: integrityLabel,
        accent: "signal",
      },
    ];
  }, [boards, error, loading, projectController.projectDocument]);

  const statusBarItems = useMemo<ShellStatusItemViewModel[]>(() => {
    const artifacts = selectProjectArtifactStatus(projectController.projectDocument);
    const integrity = selectProjectIntegrityStatus(projectController.projectDocument);
    const readinessLabel = selectProjectReadinessLabel(projectController.projectDocument);
    const boardLabel = projectController.activeBoard
      ? `${projectController.activeBoard.name} (${projectController.activeBoard.package})`
      : "Board pending";
    const workspaceProfile = projectController.projectFilePath.trim()
      ? "Project-backed"
      : "Scratch session";
    const dirtyState = projectController.canUndoProjectDocument ? "Unsaved changes" : "Clean";
    const generatorState =
      artifacts.authorityState === "authoritative"
        ? "Authoritative"
        : artifacts.authorityState === "stale"
          ? "Stale"
          : "Missing";
    const simulatorState = !projectController.projectDocument.renode.enabled
      ? "Disabled"
      : projectController.projectDocument.renode.platform.trim()
        ? "Ready"
        : "Target pending";
    const activityState = projectController.projectBusy
      ? "Busy"
      : projectController.projectStatus.tone === "error"
        ? "Blocked"
        : "Idle";

    return [
      {
        id: "board",
        label: "Board",
        value: boardLabel,
        detail: projectController.projectDocument.board_id || "Select a board.",
        tone: projectController.activeBoard ? "success" : "warning",
      },
      {
        id: "profile",
        label: "Workspace Profile",
        value: workspaceProfile,
        detail: projectController.projectFilePath || "Project path pending.",
        tone: projectController.projectFilePath.trim() ? "neutral" : "warning",
      },
      {
        id: "dirty",
        label: "Dirty State",
        value: dirtyState,
        detail: projectController.canUndoProjectDocument ? "Undo stack pending." : "Session clean.",
        tone: projectController.canUndoProjectDocument ? "warning" : "success",
      },
      {
        id: "generator",
        label: "Generator",
        value: generatorState,
        detail: `${readinessLabel}. ${artifacts.authorityReason}`,
        tone: artifacts.authorityState === "authoritative" ? "success" : artifacts.authorityState === "stale" ? "warning" : "neutral",
      },
      {
        id: "simulator",
        label: "Simulator",
        value: simulatorState,
        detail: projectController.projectDocument.renode.platform.trim() || projectController.projectDocument.renode.appbench_target || "Target pending.",
        tone: simulatorState === "Ready" ? "success" : simulatorState === "Target pending" ? "warning" : "neutral",
      },
      {
        id: "activity",
        label: "Activity",
        value: activityState,
        detail: integrity.warningCount ? `${projectController.projectStatus.message} ${integrity.warningCount} warnings.` : projectController.projectStatus.message,
        tone: projectController.projectBusy ? "warning" : projectController.projectStatus.tone === "error" ? "warning" : "neutral",
      },
    ];
  }, [
    projectController.activeBoard,
    projectController.canUndoProjectDocument,
    projectController.projectBusy,
    projectController.projectDocument,
    projectController.projectFilePath,
    projectController.projectStatus.message,
    projectController.projectStatus.tone,
  ]);

  const commands = useMemo<ShellCommandViewModel[]>(() => {
    return [
      {
        id: "project.save",
        label: "Save Project",
        description: "Persist the canonical project document to the current project path.",
        shortcut: "Ctrl+S",
        group: "Project",
        disabled: projectController.projectBusy,
        run: projectController.saveProjectFile,
      },
      {
        id: "project.load",
        label: "Load Project",
        description: "Load a project file into the canonical document and workspace shell.",
        shortcut: "Ctrl+O",
        group: "Project",
        disabled: projectController.projectBusy,
        run: projectController.loadProjectFile,
      },
      {
        id: "history.undo",
        label: "Undo Change",
        description: "Revert the last project-document command.",
        shortcut: "Ctrl+Z",
        group: "History",
        disabled: projectController.projectBusy || !projectController.canUndoProjectDocument,
        run: projectController.undoProjectDocument,
      },
      {
        id: "history.redo",
        label: "Redo Change",
        description: "Reapply the last reverted project-document command.",
        shortcut: "Ctrl+Shift+Z",
        group: "History",
        disabled: projectController.projectBusy || !projectController.canRedoProjectDocument,
        run: projectController.redoProjectDocument,
      },
      {
        id: "export.artifacts",
        label: "Export Artifacts",
        description: "Download generated overlay, config, and fragment outputs.",
        shortcut: "Ctrl+E",
        group: "Export",
        disabled: projectController.projectBusy,
        run: generatedOutput.exportArtifacts,
      },
      {
        id: "export.renode",
        label: "Export Renode Bundle",
        description: "Download the Renode simulation bundle from the project document.",
        shortcut: "Ctrl+Shift+E",
        group: "Export",
        disabled: projectController.projectBusy,
        run: renodeProfile.exportSimulation,
      },
      {
        id: "artifacts.seed",
        label: "Seed Overlay",
        description: "Seed generated artifact fields from the current project state.",
        shortcut: "Alt+Shift+S",
        group: "Artifacts",
        disabled: projectController.projectBusy,
        run: generatedOutput.seedArtifacts,
      },
      {
        id: "artifacts.clear",
        label: "Clear Artifacts",
        description: "Clear generated artifact fields while preserving the canonical project model.",
        shortcut: "Alt+Shift+X",
        group: "Artifacts",
        disabled: projectController.projectBusy,
        run: generatedOutput.clearArtifacts,
      },
    ];
  }, [
    projectController.canRedoProjectDocument,
    projectController.canUndoProjectDocument,
    projectController.loadProjectFile,
    projectController.projectBusy,
    projectController.redoProjectDocument,
    projectController.saveProjectFile,
    projectController.undoProjectDocument,
    generatedOutput.clearArtifacts,
    generatedOutput.exportArtifacts,
    generatedOutput.seedArtifacts,
    renodeProfile.exportSimulation,
  ]);

  const pinAssignments = useMemo<PinAssignmentsViewModel>(() => pinConfigurator.pinAssignments, [pinConfigurator.pinAssignments]);

  const buildSimTest = useMemo(
    () => createBuildSimTestPresenter({
      activeBoard: projectController.activeBoard,
      projectDocument: projectController.projectDocument,
      projectBusy: projectController.projectBusy,
      projectStatus: projectController.projectStatus,
      pinAssignments,
    }),
    [pinAssignments, projectController.activeBoard, projectController.projectBusy, projectController.projectDocument, projectController.projectStatus],
  );

  const outputChannels = useMemo<ShellOutputChannelViewModel[]>(() => buildSimTest.outputChannels, [buildSimTest.outputChannels]);

  return {
    boards,
    activeBoard: projectController.activeBoard,
    loading,
    error,
    metrics,
    commands,
    statusBarItems,
    outputChannels,
    executionWorkbench: buildSimTest.executionWorkbench,
    projectDocument: projectController.projectDocument,
    generatedFragments,
    pinAssignments,
    peripheralConfigurator,
    moduleConfigurator,
    clockConfigurator,
    lvglLayout,
    boardEditor,
    interruptConfigurator,
    sensorParser,
    packageManager,
    zephyrCatalog,
    hydratedPinStates: pinConfigurator.hydratedPinStates,
    canUndoProjectDocument: projectController.canUndoProjectDocument,
    canRedoProjectDocument: projectController.canRedoProjectDocument,
    projectFilePath: projectController.projectFilePath,
    projectStatus: projectController.projectStatus,
    projectBusy: projectController.projectBusy,
    setProjectFilePath: projectController.setProjectFilePath,
    selectBoard: projectController.selectBoard,
    updateRenodeField: renodeProfile.updateField,
    addProtocolEntry: protocolEditor.addEntry,
    selectProtocolEntry: protocolEditor.selectEntry,
    removeProtocolEntry: protocolEditor.removeEntry,
    toggleProtocolEntry: protocolEditor.toggleEntry,
    updateProtocolEntryValue: protocolEditor.updateEntryValue,
    updateGeneratedOverlay: generatedOutput.updateOverlay,
    updateGeneratedConf: generatedOutput.updateConf,
    clearPinAssignment: pinConfigurator.clearPinAssignment,
    assignPinAltFunction: pinConfigurator.assignPinAltFunction,
    updatePinBooleanProperty: pinConfigurator.updatePinBooleanProperty,
    undoProjectDocument: projectController.undoProjectDocument,
    redoProjectDocument: projectController.redoProjectDocument,
    exportGeneratedArtifacts: generatedOutput.exportArtifacts,
    exportRenodeSimulation: renodeProfile.exportSimulation,
    seedGeneratedArtifacts: generatedOutput.seedArtifacts,
    clearGeneratedArtifacts: generatedOutput.clearArtifacts,
    saveProjectFile: projectController.saveProjectFile,
    loadProjectFile: projectController.loadProjectFile,
  };
}