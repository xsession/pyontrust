import type { BoardDefinition, BoardSummary, ProtocolFieldValue } from "../../contracts/api";
import { buildArtifactDiagnosticEntries, buildArtifactReviewDocuments, type ArtifactDiagnosticEntry, type ArtifactReviewDocument } from "../../project/artifactReview";
import { formatGeneratedFragments } from "../../project/generatedArtifacts";
import type { RehydratedPinStateMap } from "../../project/legacyHardwareState";
import type { ProjectDocument } from "../../project/projectDocument";
import type { ZephyrCatalogPresenter } from "../../domains/catalog/zephyrCatalogPresenter";
import type { ClockConfiguratorPresenter } from "../../domains/clock/clockConfiguratorPresenter";
import type { BoardEditorPresenter } from "../../domains/board-editor/boardEditorPresenter";
import type { InterruptConfiguratorPresenter } from "../../domains/interrupts/interruptConfiguratorPresenter";
import type { LvglLayoutPresenter } from "../../domains/lvgl/lvglLayoutPresenter";
import type { ModuleConfiguratorPresenter } from "../../domains/modules/moduleConfiguratorPresenter";
import type { PackageManagerPresenter } from "../../domains/packages/packageManagerPresenter";
import type { PeripheralConfiguratorPresenter } from "../../domains/peripherals/peripheralConfiguratorPresenter";
import type { SensorParserPresenter } from "../../domains/sensors/sensorParserPresenter";
import type { PinAssignmentAltFunctionOptionViewModel, PinAssignmentsViewModel } from "../../shared/viewModels/pinAssignments";
import type { RenodeFieldUpdater } from "../../views/RenodeProfileEditor";

export interface WorkspaceDockPanelParams {
  boards: BoardSummary[];
  activeBoard: BoardSummary | null;
  activeBoardDefinition?: BoardDefinition | null;
  loading: boolean;
  error: string;
  projectDocument: ProjectDocument;
  hydratedPinStates: RehydratedPinStateMap;
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
  clearPinAssignment: (pinNumber: string) => void;
  assignPinAltFunction: (pinNumber: string, option: PinAssignmentAltFunctionOptionViewModel) => void;
  updatePinBooleanProperty: (pinNumber: string, propertyKey: string, value: boolean) => void;
  generatedConf: string;
  generatedFragments: string;
  generatedOverlay: string;
  artifactDocuments: ArtifactReviewDocument[];
  artifactDiagnostics: ArtifactDiagnosticEntry[];
  updateRenodeField: RenodeFieldUpdater;
  updateGeneratedOverlay: (value: string) => void;
  updateGeneratedConf: (value: string) => void;
  focusRequest: { panelId: string; nonce: number; lineNumber?: number; column?: number } | null;
  addProtocolEntry: (templateId: string) => void;
  selectProtocolEntry: (entryId: string) => void;
  removeProtocolEntry: (entryId: string) => void;
  toggleProtocolEntry: (entryId: string, enabled: boolean) => void;
  updateProtocolEntryValue: (entryId: string, fieldKey: string, value: ProtocolFieldValue) => void;
}

export interface WorkspaceDockPanelParamsInput {
  boards: BoardSummary[];
  activeBoard: BoardSummary | null;
  activeBoardDefinition?: BoardDefinition | null;
  loading: boolean;
  error: string;
  projectDocument: ProjectDocument;
  hydratedPinStates: RehydratedPinStateMap;
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
  clearPinAssignment: (pinNumber: string) => void;
  assignPinAltFunction: (pinNumber: string, option: PinAssignmentAltFunctionOptionViewModel) => void;
  updatePinBooleanProperty: (pinNumber: string, propertyKey: string, value: boolean) => void;
  updateRenodeField: RenodeFieldUpdater;
  updateGeneratedOverlay: (value: string) => void;
  updateGeneratedConf: (value: string) => void;
  focusRequest?: { panelId: string; nonce: number; lineNumber?: number; column?: number } | null;
  addProtocolEntry: (templateId: string) => void;
  selectProtocolEntry: (entryId: string) => void;
  removeProtocolEntry: (entryId: string) => void;
  toggleProtocolEntry: (entryId: string, enabled: boolean) => void;
  updateProtocolEntryValue: (entryId: string, fieldKey: string, value: ProtocolFieldValue) => void;
}

export function buildWorkspaceDockPanelParams({
  boards,
  activeBoard,
  activeBoardDefinition = null,
  loading,
  error,
  projectDocument,
  hydratedPinStates,
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
  clearPinAssignment,
  assignPinAltFunction,
  updatePinBooleanProperty,
  updateRenodeField,
  addProtocolEntry,
  selectProtocolEntry,
  removeProtocolEntry,
  toggleProtocolEntry,
  updateProtocolEntryValue,
  updateGeneratedOverlay,
  updateGeneratedConf,
  focusRequest = null,
}: WorkspaceDockPanelParamsInput): WorkspaceDockPanelParams {
  const artifactDocuments = buildArtifactReviewDocuments({
    activeBoard,
    projectDocument,
    unresolvedPinCount: pinAssignments.summary.unresolvedCount,
  });

  return {
    boards,
    activeBoard,
    activeBoardDefinition,
    loading,
    error,
    projectDocument,
    hydratedPinStates,
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
    clearPinAssignment,
    assignPinAltFunction,
    updatePinBooleanProperty,
    generatedConf: projectDocument.generated_conf,
    generatedFragments: formatGeneratedFragments(projectDocument.generated_fragments),
    generatedOverlay: projectDocument.generated_overlay,
    artifactDocuments,
    artifactDiagnostics: buildArtifactDiagnosticEntries(artifactDocuments),
    updateRenodeField,
    updateGeneratedOverlay,
    updateGeneratedConf,
    focusRequest,
    addProtocolEntry,
    selectProtocolEntry,
    removeProtocolEntry,
    toggleProtocolEntry,
    updateProtocolEntryValue,
  };
}
