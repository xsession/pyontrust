import type { BoardAltFunction, BoardDefinition } from "../contracts/api";
import type { LegacyPinState, LegacyPinStateMap, PeripheralEnabledStateMap, RehydratedPinStateMap } from "./legacyHardwareState";
import type { ProjectDocument } from "./projectDocument";
import type { PinAssignmentsViewModel } from "../shared/viewModels/pinAssignments";

export interface PinAssignmentSummary {
  resolvedCount: number;
  savedCount: number;
  unresolvedCount: number;
}

export interface PinAssignmentRow {
  pinNumber: string;
  savedLabel: string;
  resolvedLabel: string;
  resolvedRoute: string;
  propertyKeys: string[];
  resolution: "resolved" | "unresolved";
  selectedAltFunctionValue: string;
}

export interface PinAssignmentIssue {
  id: string;
  title: string;
  summary: string;
}

export interface ProjectArtifactStatus {
  overlayReady: boolean;
  configReady: boolean;
  fragmentGroupCount: number;
  protocolEntryCount: number;
  enabledProtocolEntryCount: number;
  hasArtifactPayload: boolean;
  authorityState: "missing" | "authoritative" | "stale";
  authorityReason: string;
  authoritative: boolean;
}

export interface ProjectReadinessStatus {
  hasBoard: boolean;
  hasRenodeTarget: boolean;
  hasGeneratedArtifacts: boolean;
  hasProtocolEntries: boolean;
  readySectionCount: number;
}

export interface ProjectIntegrityStatus {
  issues: string[];
  warningCount: number;
  staleArtifacts: boolean;
}

function comparePinNumbers(left: string, right: string): number {
  return Number(left) - Number(right);
}

function compareAltFunctions(left: BoardAltFunction, right: BoardAltFunction): number {
  return (
    left.function_id - right.function_id ||
    String(left.pincm).localeCompare(String(right.pincm)) ||
    left.name.localeCompare(right.name) ||
    left.peripheral.localeCompare(right.peripheral) ||
    left.signal.localeCompare(right.signal)
  );
}

function asRecord(value: unknown): Record<string, unknown> {
  return value && typeof value === "object" && !Array.isArray(value) ? (value as Record<string, unknown>) : {};
}

export function selectProjectArtifactStatus(project: ProjectDocument): ProjectArtifactStatus {
  const protocolEntries = project.protocol_editor.entries ?? [];
  const overlayReady = project.generated_overlay.trim().length > 0;
  const configReady = project.generated_conf.trim().length > 0;
  const fragments = project.generated_fragments;
  const fragmentGroupCount = Object.keys(fragments).length;
  const hasArtifactPayload = overlayReady || configReady || fragmentGroupCount > 0;
  const boardFragment = asRecord(fragments.board);
  const outputsFragment = asRecord(fragments.outputs);
  const hasProtocolsFragment = Object.prototype.hasOwnProperty.call(fragments, "protocols");
  const fragmentBoardId = typeof boardFragment.id === "string" ? boardFragment.id.trim() : "";
  const outputOverlay = typeof outputsFragment.overlay === "string" ? outputsFragment.overlay.trim() : "";
  const outputConfig = typeof outputsFragment.config === "string" ? outputsFragment.config.trim() : "";
  const boardContextMatches =
    !project.board_id.trim().length ||
    (fragmentBoardId.length > 0 && fragmentBoardId === project.board_id.trim());
  const outputsCoverPayload = (!overlayReady || outputOverlay.length > 0) && (!configReady || outputConfig.length > 0);
  const protocolsCoverPayload = protocolEntries.filter((entry) => entry.enabled !== false).length === 0 || hasProtocolsFragment;

  let authorityState: ProjectArtifactStatus["authorityState"] = "missing";
  let authorityReason = "No generated artifact payload is stored in the project document.";

  if (hasArtifactPayload) {
    if (!fragmentGroupCount) {
      authorityState = "stale";
      authorityReason = "Generated text exists without machine-readable fragments to describe it.";
    } else if (!boardContextMatches) {
      authorityState = "stale";
      authorityReason = "Generated fragments target a different board than the current project selection.";
    } else if (project.board_id.trim().length > 0 && !fragmentBoardId.length) {
      authorityState = "stale";
      authorityReason = "Generated fragments are missing the board identity needed to prove they match the current project.";
    } else if (!outputsCoverPayload) {
      authorityState = "stale";
      authorityReason = "Generated fragments are missing output descriptors for the stored overlay or config payload.";
    } else if (!protocolsCoverPayload) {
      authorityState = "stale";
      authorityReason = "Enabled protocol entries are not reflected in the generated fragments payload.";
    } else {
      authorityState = "authoritative";
      authorityReason = "Generated fragments fully describe the current overlay, config, and project context.";
    }
  }

  return {
    overlayReady,
    configReady,
    fragmentGroupCount,
    protocolEntryCount: protocolEntries.length,
    enabledProtocolEntryCount: protocolEntries.filter((entry) => entry.enabled !== false).length,
    hasArtifactPayload,
    authorityState,
    authorityReason,
    authoritative: authorityState === "authoritative",
  };
}

export function selectProjectReadinessStatus(project: ProjectDocument): ProjectReadinessStatus {
  const artifacts = selectProjectArtifactStatus(project);
  const hasBoard = project.board_id.trim().length > 0;
  const hasRenodeTarget = project.renode.enabled && project.renode.platform.trim().length > 0;
  const hasGeneratedArtifacts = artifacts.hasArtifactPayload;
  const hasProtocolEntries = artifacts.protocolEntryCount > 0;

  return {
    hasBoard,
    hasRenodeTarget,
    hasGeneratedArtifacts,
    hasProtocolEntries,
    readySectionCount: [hasBoard, hasRenodeTarget, hasGeneratedArtifacts, hasProtocolEntries].filter(Boolean).length,
  };
}

export function selectProjectReadinessLabel(project: ProjectDocument): string {
  const readiness = selectProjectReadinessStatus(project);

  if (!readiness.hasBoard) {
    return "Project board pending";
  }
  if (readiness.readySectionCount === 4) {
    return "Project shell ready";
  }
  if (!readiness.hasGeneratedArtifacts) {
    return "Artifacts pending generation";
  }

  return `${readiness.readySectionCount}/4 core sections ready`;
}

export function selectProjectIntegrityStatus(project: ProjectDocument): ProjectIntegrityStatus {
  const issues: string[] = [];
  const artifacts = selectProjectArtifactStatus(project);
  const staleArtifacts = artifacts.authorityState === "stale";

  if (!project.board_id.trim().length) {
    issues.push("Board assignment missing");
  }
  if (project.renode.enabled && !project.renode.platform.trim()) {
    issues.push("Renode enabled without a platform target");
  }
  if (artifacts.enabledProtocolEntryCount === 0) {
    issues.push("No enabled protocol entries");
  }
  if (staleArtifacts) {
    issues.push(`Generated artifacts appear stale: ${artifacts.authorityReason}`);
  }

  return {
    issues,
    warningCount: issues.length,
    staleArtifacts,
  };
}

export function selectProjectIntegrityLabel(project: ProjectDocument): string {
  const integrity = selectProjectIntegrityStatus(project);

  if (!integrity.warningCount) {
    return "Integrity checks passing";
  }
  if (integrity.staleArtifacts) {
    return `Integrity warnings: ${integrity.warningCount} including stale artifacts`;
  }

  return `Integrity warnings: ${integrity.warningCount}`;
}

export function selectPinAssignmentSummary(
  savedPinStates: LegacyPinStateMap,
  hydratedPinStates: RehydratedPinStateMap,
): PinAssignmentSummary {
  const savedCount = Object.keys(savedPinStates).length;
  const resolvedCount = Object.keys(hydratedPinStates).length;

  return {
    resolvedCount,
    savedCount,
    unresolvedCount: Math.max(savedCount - resolvedCount, 0),
  };
}

export function selectPinAssignmentRows(
  savedPinStates: LegacyPinStateMap,
  hydratedPinStates: RehydratedPinStateMap,
): PinAssignmentRow[] {
  return Object.entries(savedPinStates)
    .map(([pinNumber, savedState]) => {
      const hydratedState = hydratedPinStates[pinNumber];

      return {
        pinNumber,
        savedLabel: savedState.af?.name || "Manual properties only",
        resolvedLabel: hydratedState?.af?.name || "No live board match",
        resolvedRoute: hydratedState?.af
          ? `${hydratedState.af.peripheral}.${hydratedState.af.signal}`
          : "Unresolved",
        propertyKeys: Object.keys(savedState.props ?? {}).sort((left, right) => left.localeCompare(right)),
        resolution: hydratedState?.af ? "resolved" : "unresolved",
        selectedAltFunctionValue: savedState.af
          ? `${savedState.af.function_id}:${String(savedState.af.pincm)}:${savedState.af.name}`
          : "",
      } satisfies PinAssignmentRow;
    })
    .sort((left, right) => comparePinNumbers(left.pinNumber, right.pinNumber));
}

export function selectPinAssignmentAltFunctionOptions(
  savedPinStates: LegacyPinStateMap,
  boardDefinition: BoardDefinition | null | undefined,
): Record<string, BoardAltFunction[]> {
  if (!boardDefinition) {
    return {};
  }

  return Object.fromEntries(
    Object.keys(savedPinStates)
      .sort(comparePinNumbers)
      .map((pinNumber) => {
      const boardPin = boardDefinition.pins.find((candidate) => candidate.number === Number(pinNumber));
      return [pinNumber, [...(boardPin?.alt_functions ?? [])].sort(compareAltFunctions)];
    }),
  );
}

export function selectPinAssignmentIssues(
  pinNumber: string,
  pinState: LegacyPinState | null | undefined,
  peripheralEnabledStates: PeripheralEnabledStateMap = {},
  savedPinStates: LegacyPinStateMap = {},
): PinAssignmentIssue[] {
  const props = pinState?.props ?? {};
  const issues: PinAssignmentIssue[] = [];
  const assignedPeripheral = pinState?.af?.peripheral?.trim() ?? "";
  const assignedSignal = pinState?.af?.signal?.trim() || pinState?.af?.name?.trim() || "";

  if (props.bias_pull_up === true && props.bias_pull_down === true) {
    issues.push({
      id: `pin:${pinNumber}:pull-clash`,
      title: "Pull-up and pull-down are both enabled",
      summary: "The current bias properties request opposite electrical defaults on the same pad.",
    });
  }

  if (assignedPeripheral && peripheralEnabledStates[assignedPeripheral] === false) {
    issues.push({
      id: `pin:${pinNumber}:disabled-peripheral`,
      title: "Assigned peripheral is disabled",
      summary: `Pin ${pinNumber} is routed through ${assignedPeripheral}, but that peripheral is currently disabled in the canonical project state.`,
    });
  }

  if (assignedPeripheral && assignedSignal) {
    const conflictingPins = Object.entries(savedPinStates)
      .filter(([candidatePinNumber, candidateState]) => {
        if (candidatePinNumber === pinNumber) {
          return false;
        }

        const candidatePeripheral = candidateState.af?.peripheral?.trim() ?? "";
        const candidateSignal = candidateState.af?.signal?.trim() || candidateState.af?.name?.trim() || "";

        return candidatePeripheral === assignedPeripheral && candidateSignal === assignedSignal;
      })
      .map(([candidatePinNumber]) => candidatePinNumber)
      .sort((left, right) => Number(left) - Number(right));

    if (conflictingPins.length) {
      issues.push({
        id: `pin:${pinNumber}:duplicate-signal:${assignedPeripheral}:${assignedSignal}`,
        title: `${assignedPeripheral}.${assignedSignal} is assigned more than once`,
        summary: `Only one pin assignment should drive ${assignedPeripheral}.${assignedSignal}. Also claimed on pin${conflictingPins.length > 1 ? "s" : ""} ${conflictingPins.join(", ")}.`,
      });
    }
  }

  return issues.sort((left, right) => left.id.localeCompare(right.id));
}

export function selectPinAssignmentsViewModel(
  savedPinStates: LegacyPinStateMap,
  hydratedPinStates: RehydratedPinStateMap,
  boardDefinition: BoardDefinition | null | undefined,
  peripheralEnabledStates: PeripheralEnabledStateMap = {},
): PinAssignmentsViewModel {
  const pinNumbers = Object.keys(savedPinStates).sort(comparePinNumbers);
  const altFunctionOptions = selectPinAssignmentAltFunctionOptions(savedPinStates, boardDefinition);

  return {
    summary: selectPinAssignmentSummary(savedPinStates, hydratedPinStates),
    rows: selectPinAssignmentRows(savedPinStates, hydratedPinStates),
    issuesByPinNumber: Object.fromEntries(
      pinNumbers.map((pinNumber) => [
        pinNumber,
        selectPinAssignmentIssues(pinNumber, savedPinStates[pinNumber], peripheralEnabledStates, savedPinStates),
      ]),
    ),
    propertyValuesByPinNumber: Object.fromEntries(
      pinNumbers.map((pinNumber) => {
        const pinState = savedPinStates[pinNumber];
        const propertyValues = Object.fromEntries(
          Object.entries(pinState.props ?? {}).sort(([left], [right]) => left.localeCompare(right)),
        );

        return [pinNumber, propertyValues];
      }),
    ),
    altFunctionOptionsByPinNumber: Object.fromEntries(
      pinNumbers.map((pinNumber) => [
        pinNumber,
        (altFunctionOptions[pinNumber] ?? []).map((option) => ({
          value: `${option.function_id}:${String(option.pincm)}:${option.name}`,
          label: `F${option.function_id} ${option.name}`,
          detail: `${option.peripheral}.${option.signal} • PINCM ${option.pincm}`,
          functionId: option.function_id,
          pincm: option.pincm,
          name: option.name,
          peripheral: option.peripheral,
          signal: option.signal,
          direction: option.direction,
        })),
      ]),
    ),
  };
}