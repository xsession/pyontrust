import { useCallback, useEffect, useMemo, useState } from "react";
import type { ShellViewModel } from "../presenters/useShellPresenter";
import { CommandSurfaceDialog } from "../shared/ui/commands/CommandSurfaceDialog";
import { ShortcutHint } from "../shared/ui/commands/ShortcutHint";
import { EmptyState } from "../shared/ui/feedback/EmptyState";
import { GeneratedSymbolPreview } from "../shared/ui/inspectors/GeneratedSymbolPreview";
import { InspectorNotice } from "../shared/ui/inspectors/InspectorNotice";
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
  const [activeOutputChannelId, setActiveOutputChannelId] = useState<string>(getWorkspaceLayoutPreset(loadWorkspaceShellPreferences().layoutPresetId).outputChannelId);
  const [outputSeverityFilter, setOutputSeverityFilter] = useState<"all" | "info" | "success" | "warning" | "error">("all");
  const [followOutput, setFollowOutput] = useState(true);
  const [recentPaletteItemIds, setRecentPaletteItemIds] = useState<string[]>([]);
  const [dockFocusRequest, setDockFocusRequest] = useState<WorkspaceDockFocusRequest | null>(null);
  const [focusedPanelId, setFocusedPanelId] = useState<string | null>(getWorkspaceLayoutPreset(loadWorkspaceShellPreferences().layoutPresetId).panelId);
  const [actionsDialogRequestKey, setActionsDialogRequestKey] = useState(0);
  const activeBoardLabel = activeBoard ? `${activeBoard.name} (${activeBoard.package})` : "Not selected";
  const activeLayoutPreset = useMemo(() => getWorkspaceLayoutPreset(shellPreferences.layoutPresetId), [shellPreferences.layoutPresetId]);
  const resolvedPinsLabel = `${pinAssignments.summary.resolvedCount}/${Math.max(pinAssignments.summary.savedCount, 1)}`;
  const activeOutputChannel = useMemo(
    () => outputChannels.find((channel) => channel.id === activeOutputChannelId) ?? outputChannels[0] ?? null,
    [activeOutputChannelId, outputChannels],
  );
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
        const panelDefinition = workspaceDockPanelDefinitions[shortcutAction.panelIndex];
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
    saveWorkspaceShellPreferences({ density: shellPreferences.density, layoutPresetId: shellPreferences.layoutPresetId });
  }, [shellPreferences.density, shellPreferences.layoutPresetId]);

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
              detail="Domain navigation, preset switching, and output routing now live in the left rail instead of relying on implementation knowledge."
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
              detail="Typed board discovery stays in the left rail so package and family switching remains one click away while the center dock stays focused on the active workspace."
            >
              {loading ? <EmptyState title="Loading board inventory" detail="Discovering board families and package variants for the active workspace." compact /> : null}
              {!loading && error ? <EmptyState title="Board inventory failed" detail={error} tone="error" compact /> : null}
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
              detail="Compact status readouts replace the old marketing copy so the shell always exposes the current project context."
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
            <section className="workspace-context-strip" aria-label="Active workspace context">
              <span>{activeBoard ? activeBoard.name : "Choose a board to begin"}</span>
              <span>{projectDocument.renode.platform || "Renode platform pending"}</span>
              <span>{projectStatus.message}</span>
              <span>React workspace only</span>
            </section>

            <WorkspacePanel
              eyebrow="Workspace"
              title="Engineering workspace"
              detail="Docked editors, generated artifacts, and board diagnostics now sit inside a denser application frame instead of a hero-led scaffold."
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
              </div>
            </WorkspacePanel>

            <WorkspacePanel
              eyebrow="Artifacts"
              title="Artifact review surfaces"
              detail="Monaco-backed overlay, config, code, header, RESC, and Robot review now lives in the dock so diagnostics and diffs can focus the real artifact panels."
            >
              <div className="project-flow">
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
                <div className="artifact-review-links">
                  <button type="button" className="shell-button" onClick={() => focusPanel("workspace-generated-overlay")}>
                    Open Generated Overlay
                  </button>
                  <button type="button" className="shell-button" onClick={() => focusPanel("workspace-generated-config")}>
                    Open Generated Config
                  </button>
                  <button type="button" className="shell-button" onClick={() => focusPanel("workspace-generated-fragments")}>
                    Open Generated Fragments
                  </button>
                  <button type="button" className="shell-button shell-button--ghost" onClick={() => focusPanel("workspace-generated-header")}>
                    Open Generated Header
                  </button>
                  <button type="button" className="shell-button shell-button--ghost" onClick={() => focusPanel("workspace-generated-source")}>
                    Open Generated Source
                  </button>
                  <button type="button" className="shell-button shell-button--ghost" onClick={() => focusPanel("workspace-renode-resc")}>
                    Open Renode RESC
                  </button>
                  <button type="button" className="shell-button shell-button--ghost" onClick={() => focusPanel("workspace-renode-robot")}>
                    Open Robot Tests
                  </button>
                </div>
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
              </div>
            </WorkspacePanel>

            <WorkspacePanel
              eyebrow="Editors"
              title="Pin and protocol inspector"
              detail="Inspector modules stay stacked and dense so users can move from pin issues to Renode and protocol data without losing workspace context."
            >
              <div className="project-flow">
                <div className="project-flow__section">
                  <div className="project-flow__section-title">Pin assignments</div>
                  <PinAssignmentsPanel
                    pinAssignments={pinAssignments}
                    onClearPinAssignment={clearPinAssignment}
                    onAssignPinAltFunction={assignPinAltFunction}
                    onUpdatePinBooleanProperty={updatePinBooleanProperty}
                  />
                </div>
                <div className="project-flow__section">
                  <div className="project-flow__section-title">Renode profile</div>
                  <RenodeProfileEditor
                    renode={projectDocument.renode}
                    disabled={projectBusy}
                    onFieldChange={updateRenodeField}
                  />
                </div>
                <div className="project-flow__section">
                  <div className="project-flow__section-title">Protocol editor</div>
                  <ProtocolEditorPanel
                    document={projectDocument.protocol_editor}
                    disabled={projectBusy}
                    onAddEntry={addProtocolEntry}
                    onSelectEntry={selectProtocolEntry}
                    onRemoveEntry={removeProtocolEntry}
                    onToggleEntry={toggleProtocolEntry}
                    onUpdateEntryValue={updateProtocolEntryValue}
                  />
                </div>
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
          detail="These ownership lines stay visible because the shell is now dense enough that layering mistakes become expensive quickly."
        >
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
          </dl>
        </WorkspacePanel>
      </ShellBottomStrip>

      <ShellStatusBar>
        <WorkspaceStatusBar statusBarItems={statusBarItems} />
      </ShellStatusBar>

      <CommandSurfaceDialog
        open={commandPaletteOpen}
        onOpenChange={setCommandPaletteOpen}
        title="Command palette"
        description="Commands, boards, panels, generated files, diagnostics, and recent actions share one quick-open surface."
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
                detail="Try a board name, command, panel title, output channel, or recent action keyword."
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