import { useCallback, useEffect, useMemo, useState } from "react";
import {
  type BoardDefinition,
  createEmptyProjectDocument,
  protocolTemplateById,
  type BoardAltFunction,
  type BoardSummary,
  type ProtocolFieldValue,
} from "../contracts/api";
import type { ProjectDocument, RenodeProfile } from "./projectDocument";
import { pinConfiguratorApi } from "../services/pinConfiguratorApi";
import {
  buildGeneratedConfFromBoard,
  buildGeneratedFragmentsFromBoard,
  buildGeneratedOverlayFromBoard,
} from "./generatedArtifacts";
import { buildGeneratedArtifactExportBundle, downloadGeneratedArtifactBundle } from "./exportArtifacts";
import { buildRenodeSimulationExportBundle, downloadRenodeSimulationExportBundle } from "./exportSimulation";
import {
  canRedoProjectDocumentHistory,
  canUndoProjectDocumentHistory,
  createProjectDocumentHistory,
  applyProjectDocumentHistoryCommand,
  redoProjectDocumentHistory,
  replaceProjectDocumentHistory,
  undoProjectDocumentHistory,
} from "./history";
import { rehydratePinStatesForBoard, type RehydratedPinStateMap } from "./legacyHardwareState";
import type { ProjectDocumentCommand } from "./commands";
import { selectProjectIntegrityStatus } from "./selectors";
import { createDefaultProjectWorkspaceState, type ProjectStatus } from "./workspaceState";
import { describeError } from "../shared/errors/apiError";
export type { ProjectStatus } from "./workspaceState";

export interface ProjectShellController {
  activeBoard: BoardSummary | null;
  activeBoardDefinition: BoardDefinition | null;
  hydratedPinStates: RehydratedPinStateMap;
  projectDocument: ProjectDocument;
  canUndoProjectDocument: boolean;
  canRedoProjectDocument: boolean;
  projectFilePath: string;
  projectStatus: ProjectStatus;
  projectBusy: boolean;
  setProjectFilePath: (value: string) => void;
  selectBoard: (boardId: string) => void;
  updateRenodeField: <K extends keyof RenodeProfile>(field: K, value: RenodeProfile[K]) => void;
  addProtocolEntry: (templateId: string) => void;
  selectProtocolEntry: (entryId: string) => void;
  removeProtocolEntry: (entryId: string) => void;
  toggleProtocolEntry: (entryId: string, enabled: boolean) => void;
  updateProtocolEntryValue: (entryId: string, fieldKey: string, value: ProtocolFieldValue) => void;
  updateGeneratedOverlay: (value: string) => void;
  updateGeneratedConf: (value: string) => void;
  updateLvglLayout: (layout: Record<string, unknown>) => void;
  clearPinAssignment: (pinNumber: string) => void;
  updatePinAltFunction: (pinNumber: string, altFunction: BoardAltFunction) => void;
  updatePinBooleanProperty: (pinNumber: string, propertyKey: string, value: boolean) => void;
  setPeripheralEnabled: (peripheral: string, enabled: boolean) => void;
  setPeripheralCore: (peripheral: string, coreId: string) => void;
  setExternalDeviceSelected: (deviceId: string, selected: boolean) => void;
  setExternalDeviceBus: (deviceId: string, bus: string) => void;
  upsertSensorJob: (job: Record<string, unknown>, options?: { select?: boolean }) => void;
  removeSensorJob: (jobId: string) => void;
  selectSensorJob: (jobId: string) => void;
  upsertMcuJob: (job: Record<string, unknown>, options?: { select?: boolean }) => void;
  removeMcuJob: (jobId: string) => void;
  selectMcuJob: (jobId: string) => void;
  undoProjectDocument: () => void;
  redoProjectDocument: () => void;
  exportGeneratedArtifacts: () => void;
  exportRenodeSimulation: () => void;
  seedGeneratedArtifacts: () => void;
  clearGeneratedArtifacts: () => void;
  saveProjectFile: () => void;
  loadProjectFile: () => void;
}

export function useProjectShellController(boards: BoardSummary[]): ProjectShellController {
  const [projectHistory, setProjectHistory] = useState(() => createProjectDocumentHistory(createEmptyProjectDocument()));
  const [workspaceState, setWorkspaceState] = useState(createDefaultProjectWorkspaceState);
  const projectDocument = projectHistory.present;
  const canUndoProjectDocument = canUndoProjectDocumentHistory(projectHistory);
  const canRedoProjectDocument = canRedoProjectDocumentHistory(projectHistory);

  const activeBoard = useMemo(
    () => boards.find((board) => board.board === projectDocument.board_id) ?? null,
    [boards, projectDocument.board_id],
  );
  const hydratedPinStates = useMemo(
    () => rehydratePinStatesForBoard(projectDocument.pin_states, workspaceState.activeBoardDefinition),
    [projectDocument.pin_states, workspaceState.activeBoardDefinition],
  );

  const updateWorkspaceState = useCallback((updater: (current: ReturnType<typeof createDefaultProjectWorkspaceState>) => ReturnType<typeof createDefaultProjectWorkspaceState>) => {
    setWorkspaceState(updater);
  }, []);

  const setWorkspaceStatus = useCallback((status: ProjectStatus) => {
    updateWorkspaceState((current) => ({
      ...current,
      projectStatus: status,
    }));
  }, [updateWorkspaceState]);

  const setWorkspaceBusy = useCallback((projectBusy: boolean) => {
    updateWorkspaceState((current) => ({
      ...current,
      projectBusy,
    }));
  }, [updateWorkspaceState]);

  const setWorkspaceBoardDefinition = useCallback((activeBoardDefinition: BoardDefinition | null) => {
    updateWorkspaceState((current) => ({
      ...current,
      activeBoardDefinition,
    }));
  }, [updateWorkspaceState]);

  const setProjectFilePath = useCallback((value: string) => {
    updateWorkspaceState((current) => ({
      ...current,
      projectFilePath: value,
    }));
  }, [updateWorkspaceState]);

  const dispatchProjectCommand = useCallback((
    command: ProjectDocumentCommand,
    status?: ProjectStatus,
  ) => {
    setProjectHistory((current) => applyProjectDocumentHistoryCommand(current, command));

    if (status) {
      setWorkspaceStatus(status);
    }
  }, [setWorkspaceStatus]);

  function undoProjectDocument() {
    setProjectHistory((current) => undoProjectDocumentHistory(current));
    setWorkspaceStatus({
      tone: "neutral",
      message: "Reverted the last persistent project change.",
    });
  }

  function redoProjectDocument() {
    setProjectHistory((current) => redoProjectDocumentHistory(current));
    setWorkspaceStatus({
      tone: "neutral",
      message: "Reapplied the next persistent project change.",
    });
  }

  useEffect(() => {
    if (!projectDocument.board_id) {
      setWorkspaceBoardDefinition(null);
      return;
    }

    const boardDefinitionId = activeBoard?.id ?? projectDocument.board_id;

    let active = true;

    void pinConfiguratorApi
      .getBoard(boardDefinitionId)
      .then((boardDefinition) => {
        if (!active) {
          return;
        }

        setWorkspaceBoardDefinition(boardDefinition);
      })
      .catch(() => {
        if (!active) {
          return;
        }

        setWorkspaceBoardDefinition(null);
      });

    return () => {
      active = false;
    };
  }, [activeBoard?.id, projectDocument.board_id, setWorkspaceBoardDefinition]);

  useEffect(() => {
    if (!boards.length || projectDocument.board_id) {
      return;
    }

    const initialBoard = boards[0];
    if (!initialBoard) {
      return;
    }

    dispatchProjectCommand(
      {
        type: "apply-board-selection",
        boardId: initialBoard.board,
      },
      {
        tone: "neutral",
        message: `Initialized typed project state for ${initialBoard.name}.`,
      },
    );
  }, [boards, dispatchProjectCommand, projectDocument.board_id]);

  function selectBoard(boardId: string) {
    const board = boards.find((candidate) => candidate.board === boardId || candidate.id === boardId);
    setWorkspaceBoardDefinition(null);
    const shouldSeedArtifacts = !projectDocument.generated_overlay.trim();
    const hasGeneratedFragments = Object.keys(projectDocument.generated_fragments).length > 0;

    dispatchProjectCommand(
      {
        type: "apply-board-selection",
        boardId,
        seededArtifacts: shouldSeedArtifacts
          ? {
              overlay: buildGeneratedOverlayFromBoard(board),
              conf: projectDocument.generated_conf.trim() ? projectDocument.generated_conf : buildGeneratedConfFromBoard(board),
              fragments: hasGeneratedFragments ? projectDocument.generated_fragments : buildGeneratedFragmentsFromBoard(board),
            }
          : undefined,
      },
      {
        tone: "neutral",
        message: board
          ? `Project board set to ${board.name} (${board.package}).`
          : `Project board set to ${boardId}.`,
      },
    );
  }

  function updateRenodeField<K extends keyof RenodeProfile>(field: K, value: RenodeProfile[K]) {
    dispatchProjectCommand(
      {
        type: "update-renode-field",
        field,
        value,
      },
      {
        tone: "neutral",
        message: `Updated Renode ${String(field).replace(/_/g, " ")}.`,
      },
    );
  }

  function handleAddProtocolEntry(templateId: string) {
    dispatchProjectCommand(
      {
        type: "add-protocol-entry",
        templateId,
      },
      {
        tone: "neutral",
        message: `Added protocol entry for ${protocolTemplateById(templateId).label}.`,
      },
    );
  }

  function handleSelectProtocolEntry(entryId: string) {
    dispatchProjectCommand({
      type: "select-protocol-entry",
      entryId,
    });
  }

  function handleRemoveProtocolEntry(entryId: string) {
    dispatchProjectCommand(
      {
        type: "remove-protocol-entry",
        entryId,
      },
      {
        tone: "neutral",
        message: "Removed protocol entry from the typed project document.",
      },
    );
  }

  function handleToggleProtocolEntry(entryId: string, enabled: boolean) {
    dispatchProjectCommand(
      {
        type: "toggle-protocol-entry",
        entryId,
        enabled,
      },
      {
        tone: "neutral",
        message: enabled ? "Enabled protocol entry." : "Disabled protocol entry.",
      },
    );
  }

  function handleUpdateProtocolEntryValue(entryId: string, fieldKey: string, value: ProtocolFieldValue) {
    dispatchProjectCommand(
      {
        type: "update-protocol-entry-value",
        entryId,
        fieldKey,
        value,
      },
      {
        tone: "neutral",
        message: `Updated protocol field ${fieldKey}.`,
      },
    );
  }

  function updateGeneratedOverlay(value: string) {
    dispatchProjectCommand(
      {
        type: "update-generated-overlay",
        value,
      },
      {
        tone: "neutral",
        message: "Edited generated overlay text inside the project controller.",
      },
    );
  }

  function updateGeneratedConf(value: string) {
    dispatchProjectCommand(
      {
        type: "update-generated-conf",
        value,
      },
      {
        tone: "neutral",
        message: "Edited generated config text inside the project controller.",
      },
    );
  }

  function updateLvglLayout(layout: Record<string, unknown>) {
    dispatchProjectCommand(
      {
        type: "replace-lvgl-layout",
        layout,
      },
      {
        tone: "neutral",
        message: "Updated LVGL layout state inside the canonical project document.",
      },
    );
  }

  function clearPinAssignment(pinNumber: string) {
    dispatchProjectCommand(
      {
        type: "clear-pin-assignment",
        pinNumber,
      },
      {
        tone: "neutral",
        message: `Removed saved pin assignment for pin ${pinNumber}.`,
      },
    );
  }

  function updatePinAltFunction(pinNumber: string, altFunction: BoardAltFunction) {
    dispatchProjectCommand(
      {
        type: "assign-pin-alt-function",
        pinNumber,
        altFunction,
      },
      {
        tone: "neutral",
        message: `Assigned ${altFunction.name} to pin ${pinNumber}.`,
      },
    );
  }

  function updatePinBooleanProperty(pinNumber: string, propertyKey: string, value: boolean) {
    dispatchProjectCommand(
      {
        type: "update-pin-boolean-property",
        pinNumber,
        propertyKey,
        value,
      },
      {
        tone: "neutral",
        message: `${value ? "Enabled" : "Disabled"} ${propertyKey.replace(/_/g, " ")} on pin ${pinNumber}.`,
      },
    );
  }

  function setPeripheralEnabled(peripheral: string, enabled: boolean) {
    dispatchProjectCommand(
      {
        type: "set-peripheral-enabled",
        peripheral,
        enabled,
      },
      {
        tone: "neutral",
        message: `${enabled ? "Enabled" : "Disabled"} ${peripheral} in the canonical peripheral state map.`,
      },
    );
  }

  function setPeripheralCore(peripheral: string, coreId: string) {
    dispatchProjectCommand(
      {
        type: "set-peripheral-core",
        peripheral,
        coreId,
      },
      {
        tone: "neutral",
        message: coreId
          ? `Assigned ${peripheral} to core ${coreId}.`
          : `Cleared the explicit core assignment for ${peripheral}.`,
      },
    );
  }

  function setExternalDeviceSelected(deviceId: string, selected: boolean) {
    dispatchProjectCommand(
      {
        type: "set-external-device-selected",
        deviceId,
        selected,
      },
      {
        tone: "neutral",
        message: `${selected ? "Enabled" : "Disabled"} external device ${deviceId}.`,
      },
    );
  }

  function setExternalDeviceBus(deviceId: string, bus: string) {
    dispatchProjectCommand(
      {
        type: "set-external-device-bus",
        deviceId,
        bus,
      },
      {
        tone: "neutral",
        message: bus
          ? `Routed external device ${deviceId} to ${bus}.`
          : `Cleared the bus selection for external device ${deviceId}.`,
      },
    );
  }

  function upsertSensorJob(job: Record<string, unknown>, options?: { select?: boolean }) {
    const rawJobId = job.job_id;
    const jobId = typeof rawJobId === "string"
      ? rawJobId
      : typeof rawJobId === "number" || typeof rawJobId === "boolean" || typeof rawJobId === "bigint"
        ? String(rawJobId)
        : "";

    dispatchProjectCommand(
      {
        type: "upsert-sensor-job",
        job,
        select: options?.select,
      },
      {
        tone: "neutral",
        message: jobId ? `Updated sensor job ${jobId}.` : "Updated sensor parser job state.",
      },
    );
  }

  function removeSensorJob(jobId: string) {
    dispatchProjectCommand(
      {
        type: "remove-sensor-job",
        jobId,
      },
      {
        tone: "neutral",
        message: `Removed sensor job ${jobId}.`,
      },
    );
  }

  function selectSensorJob(jobId: string) {
    dispatchProjectCommand(
      {
        type: "select-sensor-job",
        jobId,
      },
      {
        tone: "neutral",
        message: `Focused sensor job ${jobId}.`,
      },
    );
  }

  function upsertMcuJob(job: Record<string, unknown>, options?: { select?: boolean }) {
    const rawJobId = job.job_id;
    const jobId = typeof rawJobId === "string"
      ? rawJobId
      : typeof rawJobId === "number" || typeof rawJobId === "boolean" || typeof rawJobId === "bigint"
        ? String(rawJobId)
        : "";

    dispatchProjectCommand(
      {
        type: "upsert-mcu-job",
        job,
        select: options?.select,
      },
      {
        tone: "neutral",
        message: jobId ? `Updated package manager job ${jobId}.` : "Updated package manager job state.",
      },
    );
  }

  function removeMcuJob(jobId: string) {
    dispatchProjectCommand(
      {
        type: "remove-mcu-job",
        jobId,
      },
      {
        tone: "neutral",
        message: `Removed package manager job ${jobId}.`,
      },
    );
  }

  function selectMcuJob(jobId: string) {
    dispatchProjectCommand(
      {
        type: "select-mcu-job",
        jobId,
      },
      {
        tone: "neutral",
        message: `Focused package manager job ${jobId}.`,
      },
    );
  }

  function seedGeneratedArtifacts() {
    const board = activeBoard ?? boards[0] ?? null;
    const overlay = buildGeneratedOverlayFromBoard(board);
    const conf = buildGeneratedConfFromBoard(board);
    const fragments = buildGeneratedFragmentsFromBoard(board);

    dispatchProjectCommand(
      {
        type: "seed-generated-artifacts",
        overlay,
        conf,
        fragments,
      },
      {
        tone: "success",
        message: board
          ? `Generated project artifacts for ${board.name}.`
          : "Generated placeholder project artifacts.",
      },
    );
  }

  function clearGeneratedArtifacts() {
    dispatchProjectCommand(
      {
        type: "clear-generated-artifacts",
      },
      {
        tone: "neutral",
        message: "Cleared generated artifact state from the typed project document.",
      },
    );
  }

  function exportGeneratedArtifacts() {
    const integrity = selectProjectIntegrityStatus(projectDocument);
    if (integrity.warningCount > 0) {
      setWorkspaceStatus({
        tone: "error",
        message: `Resolve project integrity warnings before exporting: ${integrity.issues.join("; ")}`,
      });
      return;
    }

    const bundle = buildGeneratedArtifactExportBundle(projectDocument);
    if (bundle.files.length === 0) {
      setWorkspaceStatus({
        tone: "error",
        message: "Generate overlay, config, or fragment artifacts before exporting.",
      });
      return;
    }

    const exportedFileCount = downloadGeneratedArtifactBundle(bundle);
    setWorkspaceStatus({
      tone: "success",
      message: `Exported ${exportedFileCount} generated artifact file${exportedFileCount === 1 ? "" : "s"} from the canonical project document.`,
    });
  }

  function exportRenodeSimulation() {
    const integrity = selectProjectIntegrityStatus(projectDocument);
    if (integrity.warningCount > 0) {
      setWorkspaceStatus({
        tone: "error",
        message: `Resolve project integrity warnings before exporting: ${integrity.issues.join("; ")}`,
      });
      return;
    }

    if (!projectDocument.renode.enabled || !projectDocument.renode.platform.trim()) {
      setWorkspaceStatus({
        tone: "error",
        message: "Enable Renode and choose a platform before exporting a simulation bundle.",
      });
      return;
    }

    const bundle = buildRenodeSimulationExportBundle(projectDocument);
    const exportedFileCount = downloadRenodeSimulationExportBundle(bundle);
    setWorkspaceStatus({
      tone: "success",
      message: `Exported ${exportedFileCount} Renode simulation file${exportedFileCount === 1 ? "" : "s"} from the canonical project document.`,
    });
  }

  function saveProjectFile() {
    if (!workspaceState.projectFilePath.trim()) {
      setWorkspaceStatus({ tone: "error", message: "Enter a project file path before saving." });
      return;
    }

    const integrity = selectProjectIntegrityStatus(projectDocument);
    if (integrity.warningCount > 0) {
      setWorkspaceStatus({
        tone: "error",
        message: `Resolve project integrity warnings before saving: ${integrity.issues.join("; ")}`,
      });
      return;
    }

    setWorkspaceBusy(true);
    void pinConfiguratorApi
      .saveProjectFile({
        ...projectDocument,
        file_path: workspaceState.projectFilePath.trim(),
      })
      .then((result) => {
        setWorkspaceStatus({
          tone: "success",
          message: `Saved typed project document to ${result.file_path}.`,
        });
      })
      .catch((saveError) => {
        setWorkspaceStatus({
          tone: "error",
          message: describeError(saveError, "Failed to save project file."),
        });
      })
      .finally(() => {
        setWorkspaceBusy(false);
      });
  }

  function loadProjectFile() {
    if (!workspaceState.projectFilePath.trim()) {
      setWorkspaceStatus({ tone: "error", message: "Enter a project file path before loading." });
      return;
    }

    setWorkspaceBusy(true);
    void pinConfiguratorApi
      .loadProjectFile({ file_path: workspaceState.projectFilePath.trim() })
      .then(async (result) => {
        const boardDefinition = result.board_id ? await pinConfiguratorApi.getBoard(result.board_id) : null;
        const resolvedPinStates = rehydratePinStatesForBoard(result.pin_states, boardDefinition);

        setWorkspaceBoardDefinition(boardDefinition);
        setProjectHistory(replaceProjectDocumentHistory(result));
        setWorkspaceStatus({
          tone: "success",
          message: result.board_id
            ? `Loaded typed project document for ${result.board_id} and resolved ${Object.keys(resolvedPinStates).length} pin assignments against the live board definition.`
            : "Loaded typed project document for an unassigned board.",
        });
      })
      .catch((loadError) => {
        setWorkspaceStatus({
          tone: "error",
          message: describeError(loadError, "Failed to load project file."),
        });
      })
      .finally(() => {
        setWorkspaceBusy(false);
      });
  }

  return {
    activeBoard,
    activeBoardDefinition: workspaceState.activeBoardDefinition,
    hydratedPinStates,
    projectDocument,
    canUndoProjectDocument,
    canRedoProjectDocument,
    projectFilePath: workspaceState.projectFilePath,
    projectStatus: workspaceState.projectStatus,
    projectBusy: workspaceState.projectBusy,
    setProjectFilePath,
    selectBoard,
    updateRenodeField,
    addProtocolEntry: handleAddProtocolEntry,
    selectProtocolEntry: handleSelectProtocolEntry,
    removeProtocolEntry: handleRemoveProtocolEntry,
    toggleProtocolEntry: handleToggleProtocolEntry,
    updateProtocolEntryValue: handleUpdateProtocolEntryValue,
    updateGeneratedOverlay,
    updateGeneratedConf,
    updateLvglLayout,
    clearPinAssignment,
    updatePinAltFunction,
    updatePinBooleanProperty,
    setPeripheralEnabled,
    setPeripheralCore,
    setExternalDeviceSelected,
    setExternalDeviceBus,
    upsertSensorJob,
    removeSensorJob,
    selectSensorJob,
    upsertMcuJob,
    removeMcuJob,
    selectMcuJob,
    undoProjectDocument,
    redoProjectDocument,
    exportGeneratedArtifacts,
    exportRenodeSimulation,
    seedGeneratedArtifacts,
    clearGeneratedArtifacts,
    saveProjectFile,
    loadProjectFile,
  };
}