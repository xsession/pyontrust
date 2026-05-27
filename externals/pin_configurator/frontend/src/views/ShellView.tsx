import { useCallback, useEffect, useMemo, useState } from "react";
import { PenpotEditableShell, PenpotWorkspacePanel } from "../generated/penpot";
import { PenpotHealthBanner } from "../generated/penpot/PenpotHealthBanner";
import type { ShellViewModel } from "../presenters/useShellPresenter";
import { selectProjectIntegrityStatus } from "../project/selectors";
import { CommandSurfaceDialog } from "../shared/ui/commands/CommandSurfaceDialog";
import { ShortcutHint } from "../shared/ui/commands/ShortcutHint";
import { EmptyState } from "../shared/ui/feedback/EmptyState";
import { VirtualizedTreeList } from "../shared/ui/virtualized/VirtualizedTreeList";
import { buildCommandPaletteItems, buildPaletteSections, buildVisiblePaletteItems, type ShellPaletteItem } from "../workspace/commands/shellPalette";
import { getWorkspaceShortcutAction } from "../workspace/commands/shortcutBindings";
import {
  applyWorkspaceDensityMode,
  getWorkspaceLayoutPreset,
  loadWorkspaceShellPreferences,
  saveWorkspaceShellPreferences,
  type WorkspaceDensityMode,
  type WorkspaceLayoutPresetId,
} from "../workspace/layout/workspaceShellPreferences";
import { buildBoardQuickOpenItems, buildLayoutPresetQuickOpenItems, buildOutputQuickOpenItems, buildPanelQuickOpenItems } from "../workspace/navigation/quickOpenItems";
import { WorkspaceOutputZone } from "../workspace/output/WorkspaceOutputZone";
import { workspaceDockPanelDefinitions } from "../workspace/panels/dockPanelDefinitions";
import { WorkspaceCommandBar } from "../workspace/shell/WorkspaceCommandBar";
import { WorkspaceStatusBar } from "../workspace/shell/WorkspaceStatusBar";
import { WorkspaceDock, type WorkspaceDockFocusRequest } from "../workspace/WorkspaceDock";

export function ShellView({
  boards,
  activeBoard,
  activeBoardDefinition,
  loading,
  error,
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
  const [selectedExternalDeviceId, setSelectedExternalDeviceId] = useState("");
  const projectIntegrity = useMemo(() => selectProjectIntegrityStatus(projectDocument), [projectDocument]);
  const totalPinIssueCount = useMemo(
    () => Object.values(pinAssignments.issuesByPinNumber).reduce((count, issues) => count + issues.length, 0),
    [pinAssignments.issuesByPinNumber],
  );
  const healthTone = projectIntegrity.warningCount || pinAssignments.summary.unresolvedCount || totalPinIssueCount ? "warning" : "success";
  const healthSummary = healthTone === "success"
    ? "No blocking issues are currently detected across pins, peripherals, and selected external devices."
    : [
        pinAssignments.summary.unresolvedCount ? `${pinAssignments.summary.unresolvedCount} unresolved pin selection${pinAssignments.summary.unresolvedCount === 1 ? "" : "s"}` : "",
        totalPinIssueCount ? `${totalPinIssueCount} pin issue${totalPinIssueCount === 1 ? "" : "s"}` : "",
        projectIntegrity.warningCount ? `${projectIntegrity.warningCount} integrity warning${projectIntegrity.warningCount === 1 ? "" : "s"}` : "",
      ].filter(Boolean).join(" · ");
  const peripheralGroups = useMemo(() => {
    const groups = new Map<string, typeof peripheralConfigurator.peripherals>();

    peripheralConfigurator.peripherals.forEach((peripheral) => {
      const groupLabel = peripheral.display.split(" ")[0] || "Peripherals";
      const entries = groups.get(groupLabel) ?? [];
      entries.push(peripheral);
      groups.set(groupLabel, entries);
    });

    return [...groups.entries()];
  }, [peripheralConfigurator.peripherals]);
  const selectedExternalDevice = useMemo(
    () => peripheralConfigurator.externalDevices.find((device) => device.id === selectedExternalDeviceId) ?? peripheralConfigurator.externalDevices[0] ?? null,
    [peripheralConfigurator.externalDevices, selectedExternalDeviceId],
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

  useEffect(() => {
    setSelectedExternalDeviceId((current) => (
      peripheralConfigurator.externalDevices.some((device) => device.id === current)
        ? current
        : peripheralConfigurator.externalDevices[0]?.id ?? ""
    ));
  }, [peripheralConfigurator.externalDevices]);

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
    <PenpotEditableShell
      topBar={(
        <WorkspaceCommandBar
          boards={boards}
          activeBoardId={activeBoard?.id ?? null}
          activeBoardDefinition={activeBoardDefinition}
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
          onOpenPalette={() => setCommandPaletteOpen(true)}
          onRunCommandById={runCommandById}
          onSelectBoard={selectBoard}
          onSelectDensityMode={updateDensityMode}
          onSelectLayoutPreset={applyLayoutPreset}
        />
      )}
      healthBanner={(
        <PenpotHealthBanner
          title="Configuration Health"
          summary={healthSummary}
          tone={healthTone}
          statusLabel={healthTone === "success" ? "Clean" : "Review"}
        />
      )}
      leftRail={(
        <div className="workspace-legacy-sidebar">
          <PenpotWorkspacePanel
            eyebrow="Peripherals"
            title="Peripheral enablement"
            detail="Use the same typed presenter state, but keep the shell visually anchored on the peripheral rail again."
          >
            {loading ? <EmptyState title="Loading peripherals" detail="Wait for board metadata before enabling buses and routed blocks." compact /> : null}
            {!loading && error ? <EmptyState title="Peripheral data unavailable" detail={error} tone="error" compact /> : null}
            {!loading && !error ? (
              <div className="legacy-peripheral-groups">
                {peripheralGroups.map(([groupLabel, peripherals]) => (
                  <section key={groupLabel} className="legacy-peripheral-group" aria-label={groupLabel}>
                    <h3>{groupLabel}</h3>
                    <ul className="legacy-peripheral-list">
                      {peripherals.map((peripheral) => (
                        <li key={peripheral.name} className={peripheral.enabled ? "legacy-peripheral-item legacy-peripheral-item--enabled" : "legacy-peripheral-item"}>
                          <button type="button" className="legacy-peripheral-item__select" onClick={() => focusPanel("workspace-peripheral-configurator")}>
                            <span className="legacy-peripheral-item__dot" aria-hidden="true" />
                            <div>
                              <strong>{peripheral.display}</strong>
                              <span>{`${peripheral.signals.slice(0, 4).join(" | ") || peripheral.compatible}`}</span>
                            </div>
                          </button>
                          <label className={peripheral.enabled ? "legacy-toggle legacy-toggle--on" : "legacy-toggle"}>
                            <input
                              type="checkbox"
                              checked={peripheral.enabled}
                              onChange={(event) => peripheralConfigurator.setPeripheralEnabled(peripheral.name, event.target.checked)}
                            />
                            <span />
                          </label>
                        </li>
                      ))}
                    </ul>
                  </section>
                ))}
              </div>
            ) : null}
          </PenpotWorkspacePanel>
        </div>
      )}
      contentRegion={(
        <div className="workspace-center-stack workspace-center-stack--legacy">
          <PenpotWorkspacePanel
            eyebrow="Workspace"
            title="Pin workspace"
            detail="Keep the typed pin surface and generated artifact tabs centered like the legacy shell while the React dock still owns the active editors."
          >
            <WorkspaceDock
              key={shellPreferences.layoutPresetId}
              boards={boards}
              activeBoard={activeBoard}
              activeBoardDefinition={activeBoardDefinition}
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
          </PenpotWorkspacePanel>
        </div>
      )}
      rightInspector={(
        <div className="workspace-legacy-sidebar workspace-legacy-sidebar--devices">
          <PenpotWorkspacePanel
            eyebrow="External devices"
            title="Bus and device routing"
            detail="Keep the external-device card stack visible again while routing still writes into the canonical React project document."
          >
            <div className="legacy-external-device-stack">
              {peripheralConfigurator.externalDevices.length ? peripheralConfigurator.externalDevices.map((device) => (
                <article key={device.id} className={device.id === selectedExternalDevice?.id ? "legacy-device-card legacy-device-card--selected" : "legacy-device-card"}>
                  <div className="legacy-device-card__header">
                    <label className="legacy-device-card__toggle">
                      <input
                        type="checkbox"
                        checked={device.selected}
                        onChange={(event) => peripheralConfigurator.setExternalDeviceSelected(device.id, event.target.checked)}
                      />
                      <span />
                    </label>
                    <button type="button" className="legacy-device-card__select" onClick={() => setSelectedExternalDeviceId(device.id)}>
                      <strong>{device.display}</strong>
                      <span>{device.category}</span>
                    </button>
                  </div>
                  <p>{device.compatible}</p>
                  <span>{device.notes || device.frameworks.join(", ") || "No notes"}</span>
                  <label className="project-flow__field legacy-device-card__field">
                    <span>Bus</span>
                    <select value={device.bus} onChange={(event) => peripheralConfigurator.setExternalDeviceBus(device.id, event.target.value)}>
                      {device.busOptions.map((option) => (
                        <option key={option} value={option}>{option}</option>
                      ))}
                    </select>
                  </label>
                </article>
              )) : (
                <div className="legacy-devices-empty">
                  <p className="legacy-devices-empty__hint">Click a pin to configure</p>
                  <p className="legacy-devices-empty__hint">or enable a peripheral on the left</p>
                  <EmptyState title="No external devices" detail="Imported or board-native devices will appear here once available." compact />
                </div>
              )}
            </div>
          </PenpotWorkspacePanel>
        </div>
      )}
      bottomStrip={(
        <PenpotWorkspacePanel
          eyebrow="Output Zone"
          title="Execution output and diagnostics"
          detail="Build, simulation, diagnostics, and test-readiness signals now have a dedicated bottom-zone home instead of being scattered across inspectors and dock panels."
        >
          <WorkspaceOutputZone
            outputChannels={outputChannels}
            activeOutputChannel={activeOutputChannel}
            compact={shellPreferences.layoutPresetId === "bring-up"}
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
        </PenpotWorkspacePanel>
      )}
      statusBar={<WorkspaceStatusBar statusBarItems={statusBarItems} />}
    >
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
          <ShortcutHint shortcut="Ctrl+K Ctrl+P" />
        </div>

        <div className="command-palette__content">
          <VirtualizedTreeList
            ariaLabel="Command palette results"
            sections={paletteSections}
            getItemId={(item) => item.id}
            estimatedRowHeight={72}
            overscan={4}
            emptyState={(
              <EmptyState
                title="No quick-open items match"
                detail="Change the query or try a board name, command, panel title, generated artifact, or output channel to move to the next workspace action."
                compact
              />
            )}
            renderItem={({ item: paletteItem }) => (
              <button
                type="button"
                className="command-palette__item"
                onClick={() => executePaletteItem(paletteItem)}
                disabled={paletteItem.disabled}
              >
                <div className="command-palette__item-main">
                  <strong>{paletteItem.label}</strong>
                  <span>{paletteItem.description}</span>
                </div>
                <div className="command-palette__item-meta">
                  <small>{paletteItem.shortcut || paletteItem.group}</small>
                </div>
              </button>
            )}
          />
        </div>
      </CommandSurfaceDialog>
    </PenpotEditableShell>
  );
}
