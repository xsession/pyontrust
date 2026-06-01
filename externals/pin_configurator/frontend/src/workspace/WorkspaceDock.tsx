import { useEffect, useMemo, useState } from "react";
import type { BoardDefinition, BoardSummary, ProtocolFieldValue } from "../contracts/api";
import type { ClockConfiguratorPresenter } from "../domains/clock/clockConfiguratorPresenter";
import type { BoardEditorPresenter } from "../domains/board-editor/boardEditorPresenter";
import type { InterruptConfiguratorPresenter } from "../domains/interrupts/interruptConfiguratorPresenter";
import type { LvglLayoutPresenter } from "../domains/lvgl/lvglLayoutPresenter";
import type { ModuleConfiguratorPresenter } from "../domains/modules/moduleConfiguratorPresenter";
import type { ZephyrCatalogPresenter } from "../domains/catalog/zephyrCatalogPresenter";
import type { PackageManagerPresenter } from "../domains/packages/packageManagerPresenter";
import type { PeripheralConfiguratorPresenter } from "../domains/peripherals/peripheralConfiguratorPresenter";
import type { SensorParserPresenter } from "../domains/sensors/sensorParserPresenter";
import type { RehydratedPinStateMap } from "../project/legacyHardwareState";
import type { ProjectDocument } from "../project/projectDocument";
import { selectProjectArtifactStatus, selectProjectIntegrityLabel, selectProjectIntegrityStatus, selectProjectReadinessLabel } from "../project/selectors";
import { getDefaultWorkspaceDockPanels } from "./layout/workspaceDockLayout";
import { getWorkspaceLayoutPreset, type WorkspaceLayoutPresetId } from "./layout/workspaceShellPreferences";
import { workspaceDockPanelDefinitions } from "./panels/dockPanelDefinitions";
import { buildWorkspaceDockPanelParams, type WorkspaceDockPanelParams } from "./panels/dockPanelParams";
import { ArtifactReviewPanel } from "./panels/ArtifactReviewPanel";
import { PinAssignmentsPanel } from "../views/PinAssignmentsPanel";
import { ProtocolEditorPanel } from "../views/ProtocolEditorPanel";
import { PeripheralConfiguratorPanel } from "../views/PeripheralConfiguratorPanel";
import { ModuleConfiguratorPanel } from "../views/ModuleConfiguratorPanel";
import { ClockConfiguratorPanel } from "../views/ClockConfiguratorPanel";
import { LvglLayoutPanel } from "../views/LvglLayoutPanel";
import { BoardEditorDraftsPanel } from "../views/BoardEditorDraftsPanel";
import { InterruptConfiguratorPanel } from "../views/InterruptConfiguratorPanel";
import { RenodeProfileEditor, type RenodeFieldUpdater } from "../views/RenodeProfileEditor";
import { DomainJobPanel } from "../views/DomainJobPanel";
import { ZephyrCatalogPanel } from "../views/ZephyrCatalogPanel";
import type { PinAssignmentAltFunctionOptionViewModel, PinAssignmentsViewModel } from "../shared/viewModels/pinAssignments";

export interface WorkspaceDockFocusRequest {
  panelId: string;
  nonce: number;
  lineNumber?: number;
  column?: number;
}

interface WorkspaceDockProps {
  boards: BoardSummary[];
  activeBoard: BoardSummary | null;
  activeBoardDefinition?: BoardDefinition | null;
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
  addProtocolEntry: (templateId: string) => void;
  selectProtocolEntry: (entryId: string) => void;
  removeProtocolEntry: (entryId: string) => void;
  toggleProtocolEntry: (entryId: string, enabled: boolean) => void;
  updateProtocolEntryValue: (entryId: string, fieldKey: string, value: ProtocolFieldValue) => void;
  loading: boolean;
  error: string;
  layoutPresetId?: WorkspaceLayoutPresetId;
  focusRequest?: WorkspaceDockFocusRequest | null;
}

interface WorkspaceDockPanelContentProps {
  params: WorkspaceDockPanelParams;
}

function OverviewPanel({ params }: WorkspaceDockPanelContentProps) {
  const { boards, activeBoard, loading, error, projectDocument } = params;
  const previewBoard = activeBoard ?? boards[0];
  const artifacts = selectProjectArtifactStatus(projectDocument);
  const readinessLabel = selectProjectReadinessLabel(projectDocument);
  const integrity = selectProjectIntegrityStatus(projectDocument);
  const integrityLabel = selectProjectIntegrityLabel(projectDocument);

  return (
    <div className="dock-panel dock-panel--stack">
      <div className="dock-callout">
        <strong>Workspace signal</strong>
        <span>Dockview is now the active center-region layout manager for the React shell.</span>
      </div>
      {loading ? <p className="dock-empty">Loading board inventory through the presenter service...</p> : null}
      {!loading && error ? <p className="dock-error">{error}</p> : null}
      {!loading && !error ? (
        <>
          <dl className="dock-stats">
            <div>
              <dt>Project Board</dt>
              <dd>{projectDocument.board_id || "Pending"}</dd>
            </div>
            <div>
              <dt>Package</dt>
              <dd>{previewBoard?.package ?? "Pending"}</dd>
            </div>
            <div>
              <dt>Renode Platform</dt>
              <dd>{projectDocument.renode.platform || "Pending"}</dd>
            </div>
          </dl>
          <ul className="dock-list">
            <li>
              <strong>{previewBoard?.name ?? "No active board"}</strong>
              <span>{previewBoard?.board ?? "Project board will appear here after selection."}</span>
            </li>
            <li>
              <strong>Overlay payload</strong>
              <span>{artifacts.overlayReady ? `${params.generatedOverlay.split("\n").length} lines prepared` : "No generated overlay text yet."}</span>
            </li>
            <li>
              <strong>Fragment groups</strong>
              <span>{`${artifacts.fragmentGroupCount} typed groups tracked in the project document.`}</span>
            </li>
            <li>
              <strong>Artifact authority</strong>
              <span>{artifacts.authorityReason}</span>
            </li>
            <li>
              <strong>Project readiness</strong>
              <span>{`${readinessLabel}. ${integrityLabel}. ${boards.length} board records are still available to the shell.`}</span>
            </li>
            <li>
              <strong>Integrity warnings</strong>
              <span>{integrity.warningCount ? integrity.issues.join("; ") : "No project integrity warnings."}</span>
            </li>
          </ul>
        </>
      ) : null}
    </div>
  );
}

function EditorPanel({ params }: WorkspaceDockPanelContentProps) {
  const document = params.artifactDocuments.find((entry) => entry.id === "overlay");

  if (!document) {
    return null;
  }

  return (
    <ArtifactReviewPanel document={document} focusRequest={params.focusRequest} onSave={params.updateGeneratedOverlay} />
  );
}

function ConfigPanel({ params }: WorkspaceDockPanelContentProps) {
  const document = params.artifactDocuments.find((entry) => entry.id === "config");

  if (!document) {
    return null;
  }

  return (
    <ArtifactReviewPanel document={document} focusRequest={params.focusRequest} onSave={params.updateGeneratedConf} />
  );
}

function FragmentsPanel({ params }: WorkspaceDockPanelContentProps) {
  const document = params.artifactDocuments.find((entry) => entry.id === "fragments");

  if (!document) {
    return null;
  }

  return (
    <ArtifactReviewPanel document={document} focusRequest={params.focusRequest} />
  );
}

function GeneratedHeaderPanel({ params }: WorkspaceDockPanelContentProps) {
  const document = params.artifactDocuments.find((entry) => entry.id === "header");

  if (!document) {
    return null;
  }

  return <ArtifactReviewPanel document={document} focusRequest={params.focusRequest} />;
}

function GeneratedSourcePanel({ params }: WorkspaceDockPanelContentProps) {
  const document = params.artifactDocuments.find((entry) => entry.id === "source");

  if (!document) {
    return null;
  }

  return <ArtifactReviewPanel document={document} focusRequest={params.focusRequest} />;
}

function RenodeRescPanel({ params }: WorkspaceDockPanelContentProps) {
  const document = params.artifactDocuments.find((entry) => entry.id === "resc");

  if (!document) {
    return null;
  }

  return <ArtifactReviewPanel document={document} focusRequest={params.focusRequest} onSave={(value) => params.updateRenodeField("resc", value)} />;
}

function RenodeRobotPanel({ params }: WorkspaceDockPanelContentProps) {
  const document = params.artifactDocuments.find((entry) => entry.id === "robot");

  if (!document) {
    return null;
  }

  return <ArtifactReviewPanel document={document} focusRequest={params.focusRequest} onSave={(value) => params.updateRenodeField("robot", value)} />;
}

function TransportPanel({ params }: WorkspaceDockPanelContentProps) {
  const { boards, loading, projectDocument } = params;

  return (
    <div className="dock-panel dock-panel--stack">
      <ul className="transport-list">
        <li>
          <strong>Dev transport</strong>
          <span>Vite proxies `/api/*` to the configured backend target during local development.</span>
        </li>
        <li>
          <strong>Production transport</strong>
          <span>Flask serves both `/api/*` and `/app/*`, so the built shell runs same-origin.</span>
        </li>
        <li>
          <strong>Project persistence</strong>
          <span>{projectDocument.board_id ? `Shell save/load is operating on ${projectDocument.board_id}.` : "Shell save/load is waiting for an initialized project board."}</span>
        </li>
        <li>
          <strong>Current signal</strong>
          <span>{loading ? "Waiting for board inventory..." : `${boards.length} board records resolved through the shared contract.`}</span>
        </li>
      </ul>
    </div>
  );
}

function RenodePanel({ params }: WorkspaceDockPanelContentProps) {
  return (
    <div className="dock-panel dock-panel--stack">
      <div className="dock-callout">
        <strong>Renode Profile</strong>
        <span>The first migrated domain panel now edits the typed project document directly.</span>
      </div>
      <RenodeProfileEditor renode={params.projectDocument.renode} onFieldChange={params.updateRenodeField} />
    </div>
  );
}

function ProtocolPanel({ params }: WorkspaceDockPanelContentProps) {
  return (
    <div className="dock-panel dock-panel--stack">
      <div className="dock-callout">
        <strong>Protocol Editor</strong>
        <span>The second migrated domain panel now edits the persisted protocol composition model.</span>
      </div>
      <ProtocolEditorPanel
        document={params.projectDocument.protocol_editor}
        onAddEntry={params.addProtocolEntry}
        onSelectEntry={params.selectProtocolEntry}
        onRemoveEntry={params.removeProtocolEntry}
        onToggleEntry={params.toggleProtocolEntry}
        onUpdateEntryValue={params.updateProtocolEntryValue}
      />
    </div>
  );
}

function PeripheralPanel({ params }: WorkspaceDockPanelContentProps) {
  return (
    <div className="dock-panel dock-panel--stack">
      <div className="dock-callout">
        <strong>Peripheral Configurator</strong>
        <span>Peripheral enablement, core routing, and external device selections now read and write typed project state.</span>
      </div>
      <PeripheralConfiguratorPanel presenter={params.peripheralConfigurator} />
    </div>
  );
}

function ModulePanel({ params }: WorkspaceDockPanelContentProps) {
  return (
    <div className="dock-panel dock-panel--stack">
      <div className="dock-callout">
        <strong>Module Configurator</strong>
        <span>Module definitions and generation requests now flow through a typed presenter rather than legacy option globals.</span>
      </div>
      <ModuleConfiguratorPanel presenter={params.moduleConfigurator} />
    </div>
  );
}

function ClockPanel({ params }: WorkspaceDockPanelContentProps) {
  return (
    <div className="dock-panel dock-panel--stack">
      <div className="dock-callout">
        <strong>Clock Configurator</strong>
        <span>Clock-tree selection, derived frequencies, and generated outputs now stay inside the presenter-owned shell workflow.</span>
      </div>
      <ClockConfiguratorPanel presenter={params.clockConfigurator} />
    </div>
  );
}

function LvglPanel({ params }: WorkspaceDockPanelContentProps) {
  return (
    <div className="dock-panel dock-panel--stack">
      <div className="dock-callout">
        <strong>LVGL Layout</strong>
        <span>Layout import/export and canonical document mutation now stay docked in the React shell.</span>
      </div>
      <LvglLayoutPanel presenter={params.lvglLayout} />
    </div>
  );
}

function BoardEditorPanel({ params }: WorkspaceDockPanelContentProps) {
  return (
    <div className="dock-panel dock-panel--stack">
      <div className="dock-callout">
        <strong>Board Editor</strong>
        <span>Draft CRUD now moves through typed board-editor endpoints and presenter-owned JSON state.</span>
      </div>
      <BoardEditorDraftsPanel presenter={params.boardEditor} />
    </div>
  );
}

function InterruptPanel({ params }: WorkspaceDockPanelContentProps) {
  return (
    <div className="dock-panel dock-panel--stack">
      <div className="dock-callout">
        <strong>Interrupt Configurator</strong>
        <span>Interrupt-sensitive workflow summaries are now composed from typed protocol, module, and clock presenters.</span>
      </div>
      <InterruptConfiguratorPanel presenter={params.interruptConfigurator} />
    </div>
  );
}

function SensorJobsPanel({ params }: WorkspaceDockPanelContentProps) {
  return (
    <div className="dock-panel dock-panel--stack">
      <div className="dock-callout">
        <strong>Sensor Parser</strong>
        <span>Persisted sensor jobs are now inspectable through a domain presenter instead of legacy tab globals.</span>
      </div>
      <DomainJobPanel
        title="Sensor parser jobs"
        summary="Catalog sensor imports and parser results stay in the canonical project document."
        jobs={params.sensorParser.jobs}
        selectedJobId={params.sensorParser.selectedJobId}
        selectedJob={params.sensorParser.selectedJob}
        onSelectJob={params.sensorParser.selectJob}
        onRemoveJob={params.sensorParser.removeJob}
      />
    </div>
  );
}

function PackageJobsPanel({ params }: WorkspaceDockPanelContentProps) {
  return (
    <div className="dock-panel dock-panel--stack">
      <div className="dock-callout">
        <strong>Package Manager</strong>
        <span>Persisted MCU/package jobs now live behind a typed presenter that can accept Zephyr catalog imports.</span>
      </div>
      <DomainJobPanel
        title="Package manager jobs"
        summary="MCU lookup and package manager jobs stay docked and inspectable inside the React workspace."
        jobs={params.packageManager.jobs}
        selectedJobId={params.packageManager.selectedJobId}
        selectedJob={params.packageManager.selectedJob}
        onSelectJob={params.packageManager.selectJob}
        onRemoveJob={params.packageManager.removeJob}
      />
    </div>
  );
}

function ZephyrCatalogDockPanel({ params }: WorkspaceDockPanelContentProps) {
  return (
    <div className="dock-panel dock-panel--stack">
      <div className="dock-callout">
        <strong>Zephyr Catalog</strong>
        <span>MCU and sensor discovery now flows through the typed API layer and presenter-owned selection state.</span>
      </div>
      <ZephyrCatalogPanel presenter={params.zephyrCatalog} />
    </div>
  );
}

function PinAssignmentsDockPanel({ params }: WorkspaceDockPanelContentProps) {
  return (
    <div className="dock-panel dock-panel--stack">
      <PinAssignmentsPanel
        activeBoard={params.activeBoard}
        activeBoardDefinition={params.activeBoardDefinition}
        pinAssignments={params.pinAssignments}
        onClearPinAssignment={params.clearPinAssignment}
        onAssignPinAltFunction={params.assignPinAltFunction}
        onUpdatePinBooleanProperty={params.updatePinBooleanProperty}
      />
    </div>
  );
}

const dockComponents: Record<string, React.FunctionComponent<WorkspaceDockPanelContentProps>> = {
  overview: OverviewPanel,
  editor: EditorPanel,
  config: ConfigPanel,
  fragments: FragmentsPanel,
  "generated-header": GeneratedHeaderPanel,
  "generated-source": GeneratedSourcePanel,
  "renode-resc": RenodeRescPanel,
  "renode-robot": RenodeRobotPanel,
  pins: PinAssignmentsDockPanel,
  peripherals: PeripheralPanel,
  modules: ModulePanel,
  clock: ClockPanel,
  lvgl: LvglPanel,
  "board-editor": BoardEditorPanel,
  interrupts: InterruptPanel,
  "sensor-jobs": SensorJobsPanel,
  "package-jobs": PackageJobsPanel,
  protocol: ProtocolPanel,
  renode: RenodePanel,
  transport: TransportPanel,
  "zephyr-catalog": ZephyrCatalogDockPanel,
};

export function WorkspaceDock({ boards, activeBoard, activeBoardDefinition, projectDocument, hydratedPinStates, pinAssignments, peripheralConfigurator, moduleConfigurator, clockConfigurator, lvglLayout, boardEditor, interruptConfigurator, sensorParser, packageManager, zephyrCatalog, clearPinAssignment, assignPinAltFunction, updatePinBooleanProperty, updateRenodeField, updateGeneratedOverlay, updateGeneratedConf, addProtocolEntry, selectProtocolEntry, removeProtocolEntry, toggleProtocolEntry, updateProtocolEntryValue, loading, error, layoutPresetId = "bring-up", focusRequest = null }: WorkspaceDockProps) {
  const layoutPreset = useMemo(() => getWorkspaceLayoutPreset(layoutPresetId), [layoutPresetId]);
  const defaultPanels = useMemo(
    () => getDefaultWorkspaceDockPanels(layoutPresetId),
    [layoutPresetId],
  );
  const [openPanelIds, setOpenPanelIds] = useState<string[]>(() => defaultPanels.map((panel) => panel.id));
  const [activePanelId, setActivePanelId] = useState<string>(() => layoutPreset.panelId);

  const panelParams = useMemo<WorkspaceDockPanelParams>(
    () => buildWorkspaceDockPanelParams({
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
      updateRenodeField,
      updateGeneratedOverlay,
      updateGeneratedConf,
      focusRequest,
      addProtocolEntry,
      selectProtocolEntry,
      removeProtocolEntry,
      toggleProtocolEntry,
      updateProtocolEntryValue,
    }),
    [activeBoard, activeBoardDefinition, assignPinAltFunction, boardEditor, boards, clearPinAssignment, clockConfigurator, error, focusRequest, hydratedPinStates, interruptConfigurator, loading, lvglLayout, moduleConfigurator, packageManager, peripheralConfigurator, pinAssignments, projectDocument, sensorParser, updateGeneratedConf, updateGeneratedOverlay, updatePinBooleanProperty, updateRenodeField, zephyrCatalog, addProtocolEntry, selectProtocolEntry, removeProtocolEntry, toggleProtocolEntry, updateProtocolEntryValue],
  );

  useEffect(() => {
    const nextOpenPanelIds = defaultPanels.map((panel) => panel.id);
    setOpenPanelIds(nextOpenPanelIds);
    setActivePanelId(nextOpenPanelIds.includes(layoutPreset.panelId) ? layoutPreset.panelId : nextOpenPanelIds[0] ?? layoutPreset.panelId);
  }, [defaultPanels, layoutPreset.panelId]);

  useEffect(() => {
    if (!openPanelIds.length) {
      setActivePanelId(layoutPreset.panelId);
      return;
    }

    if (!openPanelIds.includes(activePanelId)) {
      setActivePanelId(openPanelIds[0] ?? layoutPreset.panelId);
    }
  }, [activePanelId, layoutPreset.panelId, openPanelIds]);

  useEffect(() => {
    if (!focusRequest) {
      return;
    }

    const panelDefinition = workspaceDockPanelDefinitions.find(({ id }) => id === focusRequest.panelId);
    if (!panelDefinition) {
      return;
    }

    setOpenPanelIds((current) => (current.includes(panelDefinition.id) ? current : [...current, panelDefinition.id]));
    setActivePanelId(panelDefinition.id);
  }, [focusRequest]);

  const visiblePanels = openPanelIds
    .map((panelId) => workspaceDockPanelDefinitions.find((panel) => panel.id === panelId))
    .filter((panel): panel is (typeof workspaceDockPanelDefinitions)[number] => Boolean(panel));
  const activePanelDefinition = visiblePanels.find((panel) => panel.id === activePanelId)
    ?? defaultPanels[0]
    ?? workspaceDockPanelDefinitions[0];

  return (
    <div className="workspace-dock" data-testid="workspace-dock">
      <div className="workspace-dock__tablist" role="tablist" aria-label="Workspace tabs">
        {visiblePanels.map((panel) => {
          const isActive = panel.id === activePanelId;
          return (
            <button
              key={panel.id}
              id={`workspace-dock-tab-${panel.id}`}
              type="button"
              role="tab"
              aria-selected={isActive}
              aria-controls={`workspace-dock-panel-${panel.id}`}
              tabIndex={isActive ? 0 : -1}
              title={panel.description}
              onClick={() => setActivePanelId(panel.id)}
            >
              {panel.title}
            </button>
          );
        })}
      </div>
      {visiblePanels.length ? (
        visiblePanels.map((panel) => {
          const PanelComponent = dockComponents[panel.component];
          const isActive = panel.id === activePanelDefinition.id;
          if (!PanelComponent) {
            return null;
          }

          return (
            <div
              key={panel.id}
              id={`workspace-dock-panel-${panel.id}`}
              className={isActive ? "workspace-dock__panel workspace-dock__panel--active" : "workspace-dock__panel workspace-dock__panel--hidden"}
              role="tabpanel"
              aria-labelledby={`workspace-dock-tab-${panel.id}`}
              hidden={!isActive}
            >
              <PanelComponent params={panelParams} />
            </div>
          );
        })
      ) : (
        <div className="dock-fallback" data-testid="workspace-dock-fallback">
          <strong>Workspace panel unavailable</strong>
          <span>No dock panel is currently available for this workspace preset.</span>
        </div>
      )}
    </div>
  );
}
