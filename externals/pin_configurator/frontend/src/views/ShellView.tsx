import { useCallback, useEffect, useMemo, useState } from "react";
import type { ShellViewModel } from "../presenters/useShellPresenter";
import { CommandSurfaceDialog } from "../shared/ui/commands/CommandSurfaceDialog";
import { ShortcutHint } from "../shared/ui/commands/ShortcutHint";
import { EmptyState } from "../shared/ui/feedback/EmptyState";
import { GeneratedSymbolPreview } from "../shared/ui/inspectors/GeneratedSymbolPreview";
import { InspectorNotice } from "../shared/ui/inspectors/InspectorNotice";
import { InspectorSection } from "../shared/ui/inspectors/InspectorSection";
import {
  ShellBottomStrip,
  ShellContentRegion,
  ShellFrame,
  ShellLeftRail,
  ShellMainGrid,
  ShellRightInspector,
  ShellStatusBar,
  ShellTopBar,
} from "../shared/ui/ShellLayout";
import { WorkspacePanel } from "../shared/ui/WorkspacePanel";
import { VirtualizedTreeList } from "../shared/ui/virtualized/VirtualizedTreeList";
import { buildCommandPaletteItems, buildPaletteSections, buildVisiblePaletteItems, type ShellPaletteItem } from "../workspace/commands/shellPalette";
import { getWorkspaceShortcutAction } from "../workspace/commands/shortcutBindings";
import { buildBoardQuickOpenItems, buildLayoutPresetQuickOpenItems, buildOutputQuickOpenItems, buildPanelQuickOpenItems } from "../workspace/navigation/quickOpenItems";
import { WorkspaceNavigationRail } from "../workspace/navigation/WorkspaceNavigationRail";
import { WorkspaceOutputZone } from "../workspace/output/WorkspaceOutputZone";
import { buildArtifactReviewDocuments } from "../project/artifactReview";
import { buildLegacyCutoverSummary } from "../domains/legacy/legacyDomainRetirementPlan";
import {
  applyWorkspaceDensityMode,
  getWorkspaceLayoutPreset,
  loadWorkspaceShellPreferences,
  saveWorkspaceShellPreferences,
  type WorkspaceDensityMode,
  type WorkspaceLayoutPresetId,
} from "../workspace/layout/workspaceShellPreferences";
import { workspaceDockPanelDefinitions } from "../workspace/panels/dockPanelDefinitions";
import { WorkspaceCommandBar } from "../workspace/shell/WorkspaceCommandBar";
import { WorkspaceStatusBar } from "../workspace/shell/WorkspaceStatusBar";
import { StatusChip } from "../shared/ui/StatusChip";
import { PinAssignmentsPanel } from "./PinAssignmentsPanel";
import { ProtocolEditorPanel } from "./ProtocolEditorPanel";
import { RenodeProfileEditor } from "./RenodeProfileEditor";
import { VirtualBoardList } from "./VirtualBoardList";
import { WorkspaceDock, type WorkspaceDockFocusRequest } from "../workspace/WorkspaceDock";

export function ShellView({
  boards,
  activeBoard,
  loading,
  error,
  metrics,
  commands,
  statusBarItems,
  outputChannels,
  executionWorkbench,
  projectDocument,
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
  hydratedPinStates,
  canUndoProjectDocument,
  canRedoProjectDocument,
  projectFilePath,
  projectStatus,
  projectBusy,
  setProjectFilePath,
  selectBoard,
  updateRenodeField,
  addProtocolEntry,
  selectProtocolEntry,
  removeProtocolEntry,
  toggleProtocolEntry,
  updateProtocolEntryValue,
  updateGeneratedOverlay,
  updateGeneratedConf,
  clearPinAssignment,
  assignPinAltFunction,
  updatePinBooleanProperty,
}: ShellViewModel) {
  const [shellPreferences, setShellPreferences] = useState(() => loadWorkspaceShellPreferences());
  const [commandPaletteOpen, setCommandPaletteOpen] = useState(false);
  const [commandQuery, setCommandQuery] = useState("");
  const [activeOutputChannelId, setActiveOutputChannelId] = useState<string>(() => loadWorkspaceShellPreferences().activeOutputChannelId);
  const [outputSeverityFilter, setOutputSeverityFilter] = useState<"all" | "info" | "success" | "warning" | "error">("all");
  const [followOutput, setFollowOutput] = useState(true);
  const [recentPaletteItemIds, setRecentPaletteItemIds] = useState<string[]>([]);
  const [dockFocusRequest, setDockFocusRequest] = useState<WorkspaceDockFocusRequest | null>(() => {
    const preferences = loadWorkspaceShellPreferences();
    return preferences.focusedPanelId
      ? {
          panelId: preferences.focusedPanelId,
          nonce: 1,
        }
      : null;
  });
  const [focusedPanelId, setFocusedPanelId] = useState<string | null>(() => loadWorkspaceShellPreferences().focusedPanelId);
  const [actionsDialogRequestKey, setActionsDialogRequestKey] = useState(0);
  const activeBoardLabel = activeBoard ? `${activeBoard.name} (${activeBoard.package})` : "Not selected";
  const activeLayoutPreset = useMemo(() => getWorkspaceLayoutPreset(shellPreferences.layoutPresetId), [shellPreferences.layoutPresetId]);
  const resolvedPinsLabel = `${pinAssignments.summary.resolvedCount}/${Math.max(pinAssignments.summary.savedCount, 1)}`;
  const activeOutputChannel = useMemo(
    () => outputChannels.find((channel) => channel.id === activeOutputChannelId) ?? outputChannels[0] ?? null,
    [activeOutputChannelId, outputChannels],
  );
  const artifactDocuments = useMemo(
    () => buildArtifactReviewDocuments({
      activeBoard,
      projectDocument,
      unresolvedPinCount: pinAssignments.summary.unresolvedCount,
    }),
    [activeBoard, pinAssignments.summary.unresolvedCount, projectDocument],
  );
  const editableArtifactDocuments = useMemo(() => artifactDocuments.filter((document) => document.editable), [artifactDocuments]);
  const derivedArtifactDocuments = useMemo(() => artifactDocuments.filter((document) => !document.editable), [artifactDocuments]);
  const staleArtifactDocuments = useMemo(
    () => artifactDocuments.filter((document) => document.freshnessState === "stale"),
    [artifactDocuments],
  );
  const legacyCutover = useMemo(() => buildLegacyCutoverSummary(), []);
  const commandPaletteItems = useMemo<ShellPaletteItem[]>(() => {
    return buildCommandPaletteItems(commands);
  }, [commands]);
  const boardPaletteItems = useMemo<ShellPaletteItem[]>(() => buildBoardQuickOpenItems(boards, loading, selectBoard), [boards, loading, selectBoard]);
  const focusPanel = useCallback((panelId: string, target?: { lineNumber?: number; column?: number }) => {
    setFocusedPanelId(panelId);
    setDockFocusRequest((current) => ({ panelId, lineNumber: target?.lineNumber, column: target?.column, nonce: (current?.nonce ?? 0) + 1 }));
  }, []);
  const applyLayoutPreset = useCallback((presetId: WorkspaceLayoutPresetId) => {
    const preset = getWorkspaceLayoutPreset(presetId);

    setShellPreferences((current) => ({
      ...current,
      layoutPresetId: presetId,
    }));
    setActiveOutputChannelId(preset.outputChannelId);
    setOutputSeverityFilter("all");
    focusPanel(preset.panelId);
  }, [focusPanel]);
  const presetPaletteItems = useMemo<ShellPaletteItem[]>(() => buildLayoutPresetQuickOpenItems(shellPreferences.layoutPresetId, applyLayoutPreset), [applyLayoutPreset, shellPreferences.layoutPresetId]);
  const panelPaletteItems = useMemo<ShellPaletteItem[]>(() => {
    return buildPanelQuickOpenItems((panelId) => {
      focusPanel(panelId);
    });
  }, [focusPanel]);
  const outputPaletteItems = useMemo<ShellPaletteItem[]>(() => buildOutputQuickOpenItems(outputChannels, setActiveOutputChannelId), [outputChannels]);
  const paletteItems = useMemo<ShellPaletteItem[]>(() => {
    return [...commandPaletteItems, ...boardPaletteItems, ...presetPaletteItems, ...panelPaletteItems, ...outputPaletteItems];
  }, [boardPaletteItems, commandPaletteItems, outputPaletteItems, panelPaletteItems, presetPaletteItems]);
  const paletteItemsById = useMemo(() => new Map(paletteItems.map((item) => [item.id, item])), [paletteItems]);
  const visiblePaletteItems = useMemo(
    () => buildVisiblePaletteItems(paletteItems, recentPaletteItemIds, commandQuery),
    [commandQuery, paletteItems, recentPaletteItemIds],
  );
  const paletteSections = useMemo(
    () => buildPaletteSections(visiblePaletteItems, recentPaletteItemIds, commandQuery),
    [commandQuery, recentPaletteItemIds, visiblePaletteItems],
  );

  const executePaletteItem = useCallback((item: ShellPaletteItem, options?: { closePalette?: boolean }) => {
    if (item.disabled) {
      return;
    }

    item.run();
    setRecentPaletteItemIds((current) => [item.id, ...current.filter((entryId) => entryId !== item.id)].slice(0, 6));
    if (options?.closePalette ?? true) {
      setCommandPaletteOpen(false);
    }
  }, []);

  const runCommandById = useCallback((commandId: string, options?: { closePalette?: boolean }) => {
    const item = paletteItemsById.get(commandId);
    if (!item) {
      return;
    }

    executePaletteItem(item, options);
  }, [executePaletteItem, paletteItemsById]);

  useEffect(() => {
    function handleWindowKeyDown(event: KeyboardEvent) {
      const shortcutAction = getWorkspaceShortcutAction(event);
      if (!shortcutAction) {
        return;
      }

      if (shortcutAction.kind === "panel.focus") {
        const panelDefinition = workspaceDockPanelDefinitions.find((panel) => panel.id === shortcutAction.panelId);
        if (!panelDefinition) {
          return;
        }

        event.preventDefault();
        const item = paletteItemsById.get(`panel.${panelDefinition.id}`);
        if (item) {
          executePaletteItem(item, { closePalette: false });
        }
        return;
      }

      if (shortcutAction.kind === "actions.open") {
        event.preventDefault();
        setActionsDialogRequestKey((current) => current + 1);
        return;
      }

      if (shortcutAction.kind === "palette.open") {
        event.preventDefault();
        setCommandPaletteOpen(true);
        return;
      }

      if (shortcutAction.kind === "command.run") {
        event.preventDefault();
        runCommandById(shortcutAction.commandId, { closePalette: false });
      }
    }

    window.addEventListener("keydown", handleWindowKeyDown);

    return () => {
      window.removeEventListener("keydown", handleWindowKeyDown);
    };
  }, [executePaletteItem, paletteItemsById, runCommandById]);

  useEffect(() => {
    if (!commandPaletteOpen) {
      setCommandQuery("");
    }
  }, [commandPaletteOpen]);

  useEffect(() => {
    applyWorkspaceDensityMode(shellPreferences.density);
    saveWorkspaceShellPreferences({
      density: shellPreferences.density,
      layoutPresetId: shellPreferences.layoutPresetId,
      focusedPanelId: focusedPanelId ?? getWorkspaceLayoutPreset(shellPreferences.layoutPresetId).panelId,
      activeOutputChannelId: (activeOutputChannelId as "build" | "simulation" | "diagnostics" | "tests") ?? getWorkspaceLayoutPreset(shellPreferences.layoutPresetId).outputChannelId,
    });
  }, [activeOutputChannelId, focusedPanelId, shellPreferences.density, shellPreferences.layoutPresetId]);

  useEffect(() => {
    if (!outputChannels.some((channel) => channel.id === activeOutputChannelId)) {
      setActiveOutputChannelId(outputChannels[0]?.id ?? "build");
    }
  }, [activeOutputChannelId, outputChannels]);

  const updateDensityMode = useCallback((density: WorkspaceDensityMode) => {
    setShellPreferences((current) => ({
      ...current,
      density,
    }));
  }, []);

  const workflowStages = useMemo(
    () => [
      {
        id: "navigate",
        label: "Navigate",
        summary: `${boards.length} boards · ${activeLayoutPreset.label}`,
        detail: activeBoard ? `Board focus is ${activeBoard.name}.` : "Select a board and layout preset from the rail.",
      },
      {
        id: "configure",
        label: "Configure",
        summary: focusedPanelId ? workspaceDockPanelDefinitions.find((panel) => panel.id === focusedPanelId)?.title ?? "Dock panel active" : "Workspace dock idle",
        detail: focusedPanelId
          ? `Primary dock focus is ${workspaceDockPanelDefinitions.find((panel) => panel.id === focusedPanelId)?.title ?? focusedPanelId}.`
          : "Focus a workspace dock panel to edit artifacts, pins, or simulation state.",
        actionLabel: "Focus workspace",
        action: () => {
          focusPanel(focusedPanelId ?? activeLayoutPreset.panelId);
        },
      },
      {
        id: "inspect",
        label: "Inspect",
        summary: projectStatus.message,
        detail: `${projectDocument.protocol_editor.entries.length} protocol entries · ${Object.keys(projectDocument.generated_fragments).length} fragment groups.`,
        actionLabel: "Open overlay",
        action: () => {
          focusPanel("workspace-generated-overlay");
        },
      },
      {
        id: "verify",
        label: "Verify",
        summary: activeOutputChannel ? activeOutputChannel.label : "No output channel",
        detail: activeOutputChannel
          ? `${activeOutputChannel.entries.length} entries · ${activeOutputChannel.badge || "0"} highlighted.`
          : "Route build, simulation, or diagnostics output into the bottom strip.",
        actionLabel: "Open outputs",
        action: () => {
          setActiveOutputChannelId(activeOutputChannel?.id ?? activeLayoutPreset.outputChannelId);
        },
      },
    ],
    [
      activeBoard,
      activeLayoutPreset.label,
      activeLayoutPreset.outputChannelId,
      activeLayoutPreset.panelId,
      activeOutputChannel,
      boards.length,
      focusPanel,
      focusedPanelId,
      projectDocument.generated_fragments,
      projectDocument.protocol_editor.entries.length,
      projectStatus.message,
    ],
  );

  const copyVisibleOutputEntries = useCallback(() => {
    if (typeof navigator === "undefined" || !navigator.clipboard || !activeOutputChannel) {
      return;
    }

    const visibleEntries = activeOutputChannel.entries.filter(
      (entry) => outputSeverityFilter === "all" || entry.severity === outputSeverityFilter,
    );
    const payload = visibleEntries.map((entry) => `${entry.timestamp} ${entry.summary}\n${entry.detail}`).join("\n\n");
    void navigator.clipboard.writeText(payload);
  }, [activeOutputChannel, outputSeverityFilter]);

  const artifactFocusActions = [
    { label: "Open Generated Overlay", action: () => focusPanel("workspace-generated-overlay") },
    { label: "Open Generated Config", action: () => focusPanel("workspace-generated-config") },
    { label: "Open Generated Fragments", action: () => focusPanel("workspace-generated-fragments") },
    { label: "Open Generated Header", action: () => focusPanel("workspace-generated-header") },
    { label: "Open Generated Source", action: () => focusPanel("workspace-generated-source") },
    { label: "Open Renode RESC", action: () => focusPanel("workspace-renode-resc") },
    { label: "Open Robot Tests", action: () => focusPanel("workspace-renode-robot") },
  ];

  const reviewRouteActions = [
    { label: "Review Build Output", action: () => setActiveOutputChannelId("build") },
    { label: "Review Diagnostics", action: () => setActiveOutputChannelId("diagnostics") },
    { label: "Review Test Output", action: () => setActiveOutputChannelId("tests") },
    { label: "Focus Renode Profile", action: () => focusPanel("workspace-renode-profile") },
  ];

  return (
    <ShellFrame>
      <ShellTopBar>
        <WorkspaceCommandBar
          activeBoardLabel={activeBoardLabel}
          activeLayoutPresetId={shellPreferences.layoutPresetId}
          activeLayoutPresetLabel={activeLayoutPreset.label}
          densityMode={shellPreferences.density}
          projectFilePath={projectFilePath}
          resolvedPinsLabel={resolvedPinsLabel}
          projectStatusMessage={projectStatus.message}
          projectBusy={projectBusy}
          canUndoProjectDocument={canUndoProjectDocument}
          canRedoProjectDocument={canRedoProjectDocument}
          commandPaletteOpen={commandPaletteOpen}
          actionsDialogRequestKey={actionsDialogRequestKey}
          metrics={metrics}
          onOpenPalette={() => setCommandPaletteOpen(true)}
          onRunCommandById={runCommandById}
          onSelectDensityMode={updateDensityMode}
          onSelectLayoutPreset={applyLayoutPreset}
        />
      </ShellTopBar>

      <ShellMainGrid>
        <ShellLeftRail>
          <div className="workspace-rail-stack">
            <WorkspacePanel
              eyebrow="Navigator"
              title="Workspace navigator"
              detail="Use the left rail to switch workflow presets, jump between panels, and route the active output channel without leaving the shell."
            >
              <WorkspaceNavigationRail
                activeLayoutPresetId={shellPreferences.layoutPresetId}
                activeOutputChannelId={activeOutputChannelId}
                focusedPanelId={focusedPanelId}
                onSelectLayoutPreset={applyLayoutPreset}
                onFocusPanel={focusPanel}
                outputChannels={outputChannels}
                onSelectOutputChannel={setActiveOutputChannelId}
              />
            </WorkspacePanel>

            <WorkspacePanel
              eyebrow="Navigator"
              title="Board inventory"
              detail="Pick the active board here, then keep the dock focused on configuration, artifact review, and validation work."
            >
              {loading ? <EmptyState title="Loading board inventory" detail="Wait for board metadata to load, then choose the target board from this list to unlock pin, artifact, and simulation workflows." compact /> : null}
              {!loading && error ? <EmptyState title="Board inventory failed" detail={`${error} Check the backend board route, then use Load Project or refresh the workspace once board metadata is available.`} tone="error" compact /> : null}
              {!loading && !error ? (
                <VirtualBoardList
                  boards={boards}
                  selectedBoardId={projectDocument.board_id}
                  onSelectBoard={selectBoard}
                />
              ) : null}
            </WorkspacePanel>

            <WorkspacePanel
              eyebrow="Session"
              title="Workspace signals"
              detail="Use these status readouts to confirm the active board, saved pin coverage, protocol count, and whether the workspace is blocked or idle."
            >
              <dl className="shell-key-values">
                <div>
                  <dt>Board ID</dt>
                  <dd>{projectDocument.board_id || "None"}</dd>
                </div>
                <div>
                  <dt>Resolved pins</dt>
                  <dd>{resolvedPinsLabel}</dd>
                </div>
                <div>
                  <dt>Protocol entries</dt>
                  <dd>{projectDocument.protocol_editor.entries.length}</dd>
                </div>
                <div>
                  <dt>Busy state</dt>
                  <dd>{projectBusy ? "Busy" : "Idle"}</dd>
                </div>
              </dl>
            </WorkspacePanel>
          </div>
        </ShellLeftRail>

        <ShellContentRegion>
          <div className="workspace-center-stack">
            <section className="workspace-workflow-map" aria-label="Workspace workflow map">
              {workflowStages.map((stage, index) => (
                <div key={stage.id} className="workspace-workflow-map__stage">
                  <div className="workspace-workflow-map__header">
                    <span className="workspace-workflow-map__index">0{index + 1}</span>
                    <div>
                      <strong>{stage.label}</strong>
                      <p>{stage.summary}</p>
                    </div>
                  </div>
                  <span className="workspace-workflow-map__detail">{stage.detail}</span>
                  {stage.actionLabel && stage.action ? (
                    <button type="button" className="shell-button shell-button--ghost workspace-workflow-map__action" onClick={stage.action}>
                      {stage.actionLabel}
                    </button>
                  ) : null}
                </div>
              ))}
            </section>

            <WorkspacePanel
              eyebrow="Workspace"
              title="Engineering workspace"
              detail="Keep the active editor, generated outputs, and diagnostics in the dock while the left rail and inspector handle navigation and review."
            >
              <WorkspaceDock
                key={shellPreferences.layoutPresetId}
                boards={boards}
                activeBoard={activeBoard}
                projectDocument={projectDocument}
                hydratedPinStates={hydratedPinStates}
                pinAssignments={pinAssignments}
                peripheralConfigurator={peripheralConfigurator}
                moduleConfigurator={moduleConfigurator}
                clockConfigurator={clockConfigurator}
                lvglLayout={lvglLayout}
                boardEditor={boardEditor}
                interruptConfigurator={interruptConfigurator}
                sensorParser={sensorParser}
                packageManager={packageManager}
                zephyrCatalog={zephyrCatalog}
                clearPinAssignment={clearPinAssignment}
                assignPinAltFunction={assignPinAltFunction}
                updatePinBooleanProperty={updatePinBooleanProperty}
                updateRenodeField={updateRenodeField}
                updateGeneratedOverlay={updateGeneratedOverlay}
                updateGeneratedConf={updateGeneratedConf}
                addProtocolEntry={addProtocolEntry}
                selectProtocolEntry={selectProtocolEntry}
                removeProtocolEntry={removeProtocolEntry}
                toggleProtocolEntry={toggleProtocolEntry}
                updateProtocolEntryValue={updateProtocolEntryValue}
                loading={loading}
                error={error}
                layoutPresetId={shellPreferences.layoutPresetId}
                focusRequest={dockFocusRequest}
              />
            </WorkspacePanel>
          </div>
        </ShellContentRegion>

        <ShellRightInspector>
          <div className="workspace-inspector-stack">
            <WorkspacePanel
              eyebrow="Inspector"
              title="Project controls"
              detail="Persistence and export stay visible at the top of the inspector while the shell keeps one canonical project path and status channel."
            >
              <div className="project-flow">
                <InspectorSection title="Project state" summary="Persistence, target identity, and artifact mutation controls stay at the top of the inspector stack.">
                  <label className="project-flow__field">
                    <span>Project file path</span>
                    <input
                      type="text"
                      value={projectFilePath}
                      onChange={(event) => setProjectFilePath(event.target.value)}
                      placeholder="C:/tmp/pin-configurator-shell.zpinproj"
                    />
                  </label>
                  <div className={`project-flow__status project-flow__status--${projectStatus.tone}`} role="status" aria-live="polite" aria-atomic="true">
                    {projectStatus.message}
                  </div>
                  <dl className="shell-key-values shell-key-values--compact">
                    <div>
                      <dt>Active board</dt>
                      <dd>{activeBoardLabel}</dd>
                    </div>
                    <div>
                      <dt>Renode platform</dt>
                      <dd>{projectDocument.renode.platform || "Pending board-specific defaults"}</dd>
                    </div>
                    <div>
                      <dt>Busy</dt>
                      <dd>{projectBusy ? "Yes" : "No"}</dd>
                    </div>
                  </dl>
                  <div className="project-flow__actions">
                    <button
                      type="button"
                      className="shell-button"
                      onClick={() => runCommandById("artifacts.seed", { closePalette: false })}
                      disabled={projectBusy}
                    >
                      Seed Overlay
                    </button>
                    <button
                      type="button"
                      className="shell-button shell-button--danger"
                      onClick={() => runCommandById("artifacts.clear", { closePalette: false })}
                      disabled={projectBusy}
                    >
                      Clear Artifacts
                    </button>
                  </div>
                </InspectorSection>

                <InspectorSection title="Artifact review" summary="Generated and saved artifacts stay grouped under one review grammar so users can jump directly to the right dock panel.">
                  <InspectorNotice
                    title="Generated vs editable ownership"
                    detail="Overlay, config, RESC, and Robot scripts are saved artifacts. Fragments, generated headers, and generated source stay derived and read-only in their dedicated Monaco panels."
                    actions={
                      <>
                        <button
                          type="button"
                          className="shell-button"
                          onClick={() => runCommandById("artifacts.seed", { closePalette: false })}
                          disabled={projectBusy}
                        >
                          <span className="shell-button__label">Seed Overlay</span>
                          <ShortcutHint shortcut="Alt+Shift+S" />
                        </button>
                        <button
                          type="button"
                          className="shell-button shell-button--danger"
                          onClick={() => runCommandById("artifacts.clear", { closePalette: false })}
                          disabled={projectBusy}
                        >
                          <span className="shell-button__label">Clear Artifacts</span>
                          <ShortcutHint shortcut="Alt+Shift+X" />
                        </button>
                      </>
                    }
                  />
                  <GeneratedSymbolPreview
                    title="Generated symbols"
                    symbols={[
                      `${projectDocument.board_id || "project"}.generated_overlay`,
                      `${projectDocument.board_id || "project"}.generated_conf`,
                      `${projectDocument.board_id || "project"}.generated_fragments`,
                      `${projectDocument.board_id || "project"}_protocols.generated.h`,
                      `${projectDocument.board_id || "project"}_protocols.generated.c`,
                    ]}
                  />
                  {staleArtifactDocuments.length ? (
                    <InspectorNotice
                      title="Review customized or stale artifacts before export"
                      detail={staleArtifactDocuments.map((document) => `${document.title}: ${document.changeSummary}`).join(" ")}
                      tone="warning"
                    />
                  ) : null}
                  <div className="artifact-review-groups">
                    <section className="artifact-review-group" aria-label="Editable project assets">
                      <div className="artifact-review-group__header">
                        <strong>Editable project assets</strong>
                        <StatusChip label={`${editableArtifactDocuments.length} tracked`} tone="info" />
                      </div>
                      <ul className="artifact-review-group__list">
                        {editableArtifactDocuments.map((document) => (
                          <li key={document.id}>
                            <strong>{document.title}</strong>
                            <span>{document.freshnessDetail}</span>
                          </li>
                        ))}
                      </ul>
                    </section>
                    <section className="artifact-review-group" aria-label="Derived outputs">
                      <div className="artifact-review-group__header">
                        <strong>Derived outputs</strong>
                        <StatusChip label={`${derivedArtifactDocuments.length} tracked`} tone="neutral" />
                      </div>
                      <ul className="artifact-review-group__list">
                        {derivedArtifactDocuments.map((document) => (
                          <li key={document.id}>
                            <strong>{document.title}</strong>
                            <span>{document.freshnessDetail}</span>
                          </li>
                        ))}
                      </ul>
                    </section>
                  </div>
                  <div className="artifact-review-links">
                    {artifactFocusActions.map((item) => (
                      <button
                        key={item.label}
                        type="button"
                        className={`shell-button${item.label.includes("Header") || item.label.includes("Source") || item.label.includes("RESC") || item.label.includes("Robot") ? " shell-button--ghost" : ""}`}
                        onClick={item.action}
                      >
                        {item.label}
                      </button>
                    ))}
                  </div>
                  <InspectorNotice
                    title="Export routes stay explicit"
                    detail="Export Artifacts packages the generated overlay, generated config, and fragments metadata. Export Renode Bundle packages the RESC script, Robot suite, and the simulation handoff files derived from the current project document."
                    tone="info"
                  />
                  <dl className="shell-key-values shell-key-values--compact">
                    <div>
                      <dt>Overlay lines</dt>
                      <dd>{projectDocument.generated_overlay.split("\n").filter(Boolean).length || 0}</dd>
                    </div>
                    <div>
                      <dt>Config lines</dt>
                      <dd>{projectDocument.generated_conf.split("\n").filter(Boolean).length || 0}</dd>
                    </div>
                    <div>
                      <dt>Fragment groups</dt>
                      <dd>{Object.keys(projectDocument.generated_fragments).length}</dd>
                    </div>
                    <div>
                      <dt>Robot target</dt>
                      <dd>{projectDocument.renode.robot_target || "Pending"}</dd>
                    </div>
                  </dl>
                </InspectorSection>

                <InspectorSection title="Review routes" summary="The inspector can now send users directly into output review or simulation follow-up without leaving the current shell context.">
                  <div className="project-flow__actions">
                    {reviewRouteActions.map((item) => (
                      <button key={item.label} type="button" className="shell-button shell-button--ghost" onClick={item.action}>
                        {item.label}
                      </button>
                    ))}
                  </div>
                </InspectorSection>
              </div>
            </WorkspacePanel>

            <WorkspacePanel
              eyebrow="Editors"
              title="Pin and protocol inspector"
              detail="Inspector modules stay stacked and dense so users can move from pin issues to Renode and protocol data without losing workspace context."
            >
              <div className="project-flow">
                <InspectorSection title="Pin assignments" summary="Conflict handling, alternate-function ownership, and pin property edits stay visible as one inspector section.">
                  <PinAssignmentsPanel
                    pinAssignments={pinAssignments}
                    onClearPinAssignment={clearPinAssignment}
                    onAssignPinAltFunction={assignPinAltFunction}
                    onUpdatePinBooleanProperty={updatePinBooleanProperty}
                  />
                </InspectorSection>
                <InspectorSection title="Renode profile" summary="Simulation platform, RESC, and Robot targets stay editable in the same right-rail grammar as other inspector domains.">
                  <RenodeProfileEditor
                    renode={projectDocument.renode}
                    disabled={projectBusy}
                    onFieldChange={updateRenodeField}
                  />
                </InspectorSection>
                <InspectorSection title="Protocol editor" summary="Protocol composition stays paired with generated review so interface work does not fragment across separate shells.">
                  <ProtocolEditorPanel
                    document={projectDocument.protocol_editor}
                    disabled={projectBusy}
                    onAddEntry={addProtocolEntry}
                    onSelectEntry={selectProtocolEntry}
                    onRemoveEntry={removeProtocolEntry}
                    onToggleEntry={toggleProtocolEntry}
                    onUpdateEntryValue={updateProtocolEntryValue}
                  />
                </InspectorSection>
              </div>
            </WorkspacePanel>
          </div>
        </ShellRightInspector>

      </ShellMainGrid>

      <ShellBottomStrip>
        <WorkspacePanel
          eyebrow="Output Zone"
          title="Execution output and diagnostics"
          detail="Build, simulation, diagnostics, and test-readiness signals now have a dedicated bottom-zone home instead of being scattered across inspectors and dock panels."
        >
          <WorkspaceOutputZone
            outputChannels={outputChannels}
            activeOutputChannel={activeOutputChannel}
            executionWorkbench={executionWorkbench}
            followOutput={followOutput}
            severityFilter={outputSeverityFilter}
            projectStatus={projectStatus}
            projectBusy={projectBusy}
            projectFilePath={projectFilePath}
            projectDocument={projectDocument}
            pinAssignments={pinAssignments}
            onSelectChannel={setActiveOutputChannelId}
            onSelectSeverityFilter={setOutputSeverityFilter}
            onToggleFollow={() => setFollowOutput((current) => !current)}
            onCopyVisibleEntries={copyVisibleOutputEntries}
            onResetView={() => {
              setActiveOutputChannelId(activeLayoutPreset.outputChannelId);
              setOutputSeverityFilter("all");
            }}
            onNavigateEntry={(entry) => {
              if (!entry.navigation) {
                return;
              }

              focusPanel(entry.navigation.panelId, { lineNumber: entry.navigation.lineNumber, column: entry.navigation.column });
            }}
            onSelectRenodeMachine={(value) => updateRenodeField("platform", value)}
            onSeedArtifacts={() => runCommandById("artifacts.seed", { closePalette: false })}
            onExportArtifacts={() => runCommandById("export.artifacts", { closePalette: false })}
            onExportRenodeBundle={() => runCommandById("export.renode", { closePalette: false })}
            onOpenRenodeProfile={() => focusPanel("workspace-renode-profile")}
            onOpenRenodeResc={() => focusPanel("workspace-renode-resc")}
            onOpenRobotTests={() => focusPanel("workspace-renode-robot")}
          />
        </WorkspacePanel>

        <WorkspacePanel
          eyebrow="Architecture"
          title="Frontend boundaries"
          detail="These ownership and cutover lines stay visible because the React shell is now the canonical workstation surface and legacy drift would be expensive."
        >
          <InspectorNotice
            title={legacyCutover.canonicalShellLabel}
            detail={`${legacyCutover.canonicalShellDetail} ${legacyCutover.legacySupportDetail}`}
            tone={legacyCutover.cutoverThresholdMet ? "success" : "warning"}
          />
          <dl className="boundary-list">
            <div>
              <dt>Contracts</dt>
              <dd>src/contracts owns typed API shapes.</dd>
            </div>
            <div>
              <dt>Services</dt>
              <dd>src/services owns HTTP transport and endpoint adapters.</dd>
            </div>
            <div>
              <dt>Presenters</dt>
              <dd>src/presenters prepares the view model and async orchestration.</dd>
            </div>
            <div>
              <dt>Views</dt>
              <dd>src/views stays presentational and layout-focused.</dd>
            </div>
            <div>
              <dt>Legacy support</dt>
              <dd>{legacyCutover.legacySupportLabel}</dd>
            </div>
            <div>
              <dt>Cutover threshold</dt>
              <dd>{legacyCutover.cutoverThresholdLabel}</dd>
            </div>
          </dl>
          <div className="artifact-review-groups" aria-label="Legacy cutover alignment">
            <section className="artifact-review-group" aria-label="Legacy-only workflow support">
              <div className="artifact-review-group__header">
                <strong>Legacy-only workflow support</strong>
                <StatusChip
                  label={legacyCutover.remainingLegacyWorkflows.length ? `${legacyCutover.remainingLegacyWorkflows.length} tracked` : "0 tracked"}
                  tone={legacyCutover.remainingLegacyWorkflows.length ? "warning" : "success"}
                />
              </div>
              {legacyCutover.remainingLegacyWorkflows.length ? (
                <ul className="artifact-review-group__list">
                  {legacyCutover.remainingLegacyWorkflows.map((entry) => (
                    <li key={entry.id}>
                      <strong>{entry.label}</strong>
                      <span>{entry.retirementGoal}</span>
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="workspace-empty">Every tracked workstation workflow is now owned by typed React presenters.</p>
              )}
            </section>
            <section className="artifact-review-group" aria-label="Legacy cutover rules">
              <div className="artifact-review-group__header">
                <strong>Legacy cutover rules</strong>
                <StatusChip label={legacyCutover.cutoverThresholdMet ? "Threshold met" : "Threshold pending"} tone={legacyCutover.cutoverThresholdMet ? "success" : "warning"} />
              </div>
              <ul className="artifact-review-group__list">
                <li>
                  <strong>Porting rule</strong>
                  <span>{legacyCutover.portingRule}</span>
                </li>
                <li>
                  <strong>{legacyCutover.cutoverThresholdLabel}</strong>
                  <span>{legacyCutover.cutoverThresholdDetail}</span>
                </li>
              </ul>
            </section>
          </div>
        </WorkspacePanel>
      </ShellBottomStrip>

      <ShellStatusBar>
        <WorkspaceStatusBar statusBarItems={statusBarItems} />
      </ShellStatusBar>

      <CommandSurfaceDialog
        open={commandPaletteOpen}
        onOpenChange={setCommandPaletteOpen}
        title="Command palette"
        description="Search commands, boards, panels, generated files, and output routes from one quick-open surface."
        className="command-palette"
      >
          <div className="command-palette__search">
            <input
              type="text"
              value={commandQuery}
              onChange={(event) => setCommandQuery(event.target.value)}
              placeholder="Search commands, boards, panels, generated files, diagnostics, and recent actions"
              autoFocus
            />
          </div>

          <VirtualizedTreeList
            ariaLabel="Command palette results"
            sections={paletteSections}
            getItemId={(item) => item.id}
            estimatedRowHeight={92}
            overscan={6}
            viewportClassName="command-palette__results"
            emptyState={visiblePaletteItems.length ? null : (
              <EmptyState
                title="No quick-open items match"
                detail="Change the query or try a board name, command, panel title, generated artifact, or output channel to move to the next workspace action."
                compact
              />
            )}
            renderItem={({ item, section }) => (
              <button
                type="button"
                className="command-palette__item"
                onClick={() => executePaletteItem(item)}
                disabled={item.disabled}
              >
                <span className="command-palette__item-main">
                  <span className="command-palette__item-title">{item.label}</span>
                  <span className="command-palette__item-description">{item.description}</span>
                </span>
                <span className="command-palette__item-meta">
                  <span className="command-palette__item-group">{section.id === "recent" ? `Recent · ${item.group}` : item.group}</span>
                  {item.shortcut ? <ShortcutHint shortcut={item.shortcut} className="command-palette__item-shortcut" /> : null}
                </span>
              </button>
            )}
          />
      </CommandSurfaceDialog>
    </ShellFrame>
  );
}