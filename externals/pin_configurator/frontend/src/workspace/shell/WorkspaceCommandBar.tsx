import { useEffect, useMemo, useState } from "react";
import type { BoardDefinition, BoardSummary } from "../../contracts/api";
import { CommandSurfaceDialog } from "../../shared/ui/commands/CommandSurfaceDialog";
import { ShortcutHint } from "../../shared/ui/commands/ShortcutHint";
import { SplitButton } from "../../shared/ui/components/SplitButton";
import { ToolbarGroup } from "../../shared/ui/components/ToolbarGroup";
import { EmptyState } from "../../shared/ui/feedback/EmptyState";
import { StatusChip } from "../../shared/ui/StatusChip";
import { PenpotLegacyTopStrip, type PenpotLegacyAction, type PenpotSelectOption } from "../../generated/penpot/PenpotLegacyTopStrip";
import { workspaceLayoutPresets, type WorkspaceDensityMode, type WorkspaceLayoutPresetId } from "../layout/workspaceShellPreferences";
import { workspaceShortcutReferences } from "../commands/shortcutBindings";

interface WorkspaceCommandBarProps {
  boards: BoardSummary[];
  activeBoardId?: string | null;
  activeBoardDefinition?: BoardDefinition | null;
  activeBoardLabel: string;
  activeLayoutPresetId: WorkspaceLayoutPresetId;
  activeLayoutPresetLabel: string;
  densityMode: WorkspaceDensityMode;
  projectFilePath: string;
  resolvedPinsLabel: string;
  projectStatusMessage: string;
  projectBusy: boolean;
  canUndoProjectDocument: boolean;
  canRedoProjectDocument: boolean;
  commandPaletteOpen: boolean;
  actionsDialogRequestKey: number;
  onOpenPalette: () => void;
  onRunCommandById: (commandId: string, options?: { closePalette?: boolean }) => void;
  onSelectBoard: (boardId: string) => void;
  onSelectDensityMode: (densityMode: WorkspaceDensityMode) => void;
  onSelectLayoutPreset: (presetId: WorkspaceLayoutPresetId) => void;
}

export function WorkspaceCommandBar({
  boards = [],
  activeBoardId,
  activeBoardDefinition,
  activeBoardLabel,
  activeLayoutPresetId,
  activeLayoutPresetLabel,
  densityMode,
  projectFilePath,
  resolvedPinsLabel,
  projectStatusMessage,
  projectBusy,
  canUndoProjectDocument,
  canRedoProjectDocument,
  commandPaletteOpen,
  actionsDialogRequestKey,
  onOpenPalette,
  onRunCommandById,
  onSelectBoard,
  onSelectDensityMode,
  onSelectLayoutPreset,
}: WorkspaceCommandBarProps) {
  const [actionsDialogOpen, setActionsDialogOpen] = useState(false);
  useEffect(() => {
    if (actionsDialogRequestKey > 0) {
      setActionsDialogOpen(true);
    }
  }, [actionsDialogRequestKey]);

  const actionGroups = useMemo(
    () => [
      {
        label: "Project",
        items: [
          { id: "project.save", label: "Save Project", shortcut: "Ctrl+S" },
          { id: "project.load", label: "Load Project", shortcut: "Ctrl+O" },
        ],
      },
      {
        label: "History",
        items: [
          { id: "history.undo", label: "Undo Change", shortcut: "Ctrl+Z" },
          { id: "history.redo", label: "Redo Change", shortcut: "Ctrl+Shift+Z" },
        ],
      },
      {
        label: "Export",
        items: [
          { id: "export.artifacts", label: "Export Artifacts", shortcut: "Ctrl+E" },
          { id: "export.renode", label: "Export Renode Bundle", shortcut: "Ctrl+Shift+E" },
        ],
      },
      {
        label: "Execution",
        items: [
          { id: "output.build", label: "Build Readiness", shortcut: "" },
          { id: "output.simulation", label: "Simulation Output", shortcut: "" },
          { id: "output.tests", label: "Test Readiness", shortcut: "" },
        ],
      },
    ],
    [],
  );
  const sectionOptions = useMemo(
    () => [
      { id: "bring-up" as const, label: "Pin Configurator" },
      { id: "protocol-integration" as const, label: "Protocol Integration" },
      { id: "codegen-review" as const, label: "Code Review" },
      { id: "renode-validation" as const, label: "Renode Validation" },
    ],
    [],
  );
  const penpotSectionOptions = useMemo<readonly PenpotSelectOption<WorkspaceLayoutPresetId>[]>(
    () => sectionOptions.map((option) => ({ value: option.id, label: option.label })),
    [sectionOptions],
  );
  const selectedBoardId = activeBoardId ?? boards[0]?.id ?? "";
  const selectedBoard = boards.find((board) => board.id === selectedBoardId) ?? boards[0] ?? null;
  const penpotBoardOptions = useMemo<readonly PenpotSelectOption[]>(
    () => boards.map((board) => ({ value: board.id, label: `${board.name} — ${board.package}` })),
    [boards],
  );
  const boardRuntimeSummary = activeBoardDefinition
    ? `Flash: ${activeBoardDefinition.flash_size_kb}KB | SRAM: ${activeBoardDefinition.sram_size_kb}KB | Clock: ${Math.round(activeBoardDefinition.clock_hz / 1_000_000)}MHz`
    : selectedBoard
      ? `Package: ${selectedBoard.package} | Pins: ${selectedBoard.pin_count} | Status: ${projectBusy ? "Busy" : "Ready"}`
      : projectStatusMessage;
  const penpotActions = useMemo<readonly PenpotLegacyAction[]>(
    () => [
      {
        id: "project.load",
        label: "Load Project",
        disabled: projectBusy,
        onPress: () => onRunCommandById("project.load", { closePalette: false }),
      },
      {
        id: "workspace.import",
        label: "Import",
        disabled: projectBusy,
        onPress: onOpenPalette,
      },
      {
        id: "artifacts.seed",
        label: "Generate",
        disabled: projectBusy,
        onPress: () => onRunCommandById("artifacts.seed", { closePalette: false }),
      },
      {
        id: "project.save",
        label: "Save Project",
        disabled: projectBusy,
        onPress: () => onRunCommandById("project.save", { closePalette: false }),
      },
      {
        id: "project.save.primary",
        label: "Save to Project",
        disabled: projectBusy,
        tone: "primary",
        onPress: () => onRunCommandById("project.save", { closePalette: false }),
      },
    ],
    [onOpenPalette, onRunCommandById, projectBusy],
  );

  return (
    <>
      <section className="workspace-command-bar">
        <div className="workspace-command-bar__accessibility-strip">
          <div className="workspace-command-bar__identity">
            <StatusChip label="Workspace command bar" tone="success" />
            <h1>Pin Configurator workspace</h1>
            <p>
              Save or load the project, switch the layout preset, and route build, simulation, or test review from one control bar.
            </p>
            <div className="workspace-command-bar__chips">
              <StatusChip label={activeLayoutPresetLabel} tone="neutral" />
              <StatusChip label={`${densityMode} density`} tone="neutral" />
              <StatusChip label={projectBusy ? "Busy" : "Idle"} tone={projectBusy ? "warning" : "success"} />
            </div>
          </div>

          <dl className="workspace-command-bar__meta">
            <div>
              <dt>Active board</dt>
              <dd>{activeBoardLabel}</dd>
            </div>
            <div>
              <dt>Project file</dt>
              <dd>{projectFilePath || "Pending"}</dd>
            </div>
            <div>
              <dt>Pins resolved</dt>
              <dd>{resolvedPinsLabel}</dd>
            </div>
            <div>
              <dt>Status</dt>
              <dd>{projectStatusMessage}</dd>
            </div>
            <div>
              <dt>Layout preset</dt>
              <dd>{activeLayoutPresetLabel}</dd>
            </div>
          </dl>

          <div className="workspace-command-bar__controls">
            <ToolbarGroup label="Commands" className="workspace-command-bar__action-group">
              <SplitButton
                primaryLabel="Command Palette"
                primaryTone="command"
                primaryAriaExpanded={commandPaletteOpen}
                primaryHasPopup="dialog"
                primaryAriaKeyShortcuts="Control+K Control+P Control+F"
                menuLabel="More command palette actions"
                onPrimaryClick={onOpenPalette}
                menuItems={[
                  {
                    id: "workspace.actions",
                    label: "Workspace Actions",
                    onSelect: () => setActionsDialogOpen(true),
                  },
                  {
                    id: "workspace.keyboard-map",
                    label: "Keyboard Map",
                    shortcut: <ShortcutHint shortcut="Shift+?" />,
                    onSelect: () => setActionsDialogOpen(true),
                  },
                  {
                    id: "project.save",
                    label: "Save Project",
                    shortcut: <ShortcutHint shortcut="Ctrl+S" />,
                    disabled: projectBusy,
                    onSelect: () => onRunCommandById("project.save", { closePalette: false }),
                  },
                  {
                    id: "project.load",
                    label: "Load Project",
                    shortcut: <ShortcutHint shortcut="Ctrl+O" />,
                    disabled: projectBusy,
                    onSelect: () => onRunCommandById("project.load", { closePalette: false }),
                  },
                  {
                    id: "history.undo",
                    label: "Undo Change",
                    shortcut: <ShortcutHint shortcut="Ctrl+Z" />,
                    disabled: projectBusy || !canUndoProjectDocument,
                    onSelect: () => onRunCommandById("history.undo", { closePalette: false }),
                  },
                  {
                    id: "history.redo",
                    label: "Redo Change",
                    shortcut: <ShortcutHint shortcut="Ctrl+Shift+Z" />,
                    disabled: projectBusy || !canRedoProjectDocument,
                    onSelect: () => onRunCommandById("history.redo", { closePalette: false }),
                  },
                  {
                    id: "export.artifacts",
                    label: "Export Artifacts",
                    shortcut: <ShortcutHint shortcut="Ctrl+E" />,
                    disabled: projectBusy,
                    onSelect: () => onRunCommandById("export.artifacts", { closePalette: false }),
                  },
                  {
                    id: "export.renode",
                    label: "Export Renode Bundle",
                    shortcut: <ShortcutHint shortcut="Ctrl+Shift+E" />,
                    disabled: projectBusy,
                    onSelect: () => onRunCommandById("export.renode", { closePalette: false }),
                  },
                ]}
              />
            </ToolbarGroup>
            <ToolbarGroup label="Project" className="workspace-command-bar__action-group">
              <button
                type="button"
                className="shell-button shell-button--primary"
                aria-keyshortcuts="Control+S"
                onClick={() => onRunCommandById("project.save", { closePalette: false })}
                disabled={projectBusy}
              >
                <span className="shell-button__label">Save Project</span>
                <ShortcutHint shortcut="Ctrl+S" />
              </button>
            </ToolbarGroup>
            <ToolbarGroup label="Export" className="workspace-command-bar__action-group">
              <button
                type="button"
                className="shell-button"
                onClick={() => setActionsDialogOpen(true)}
              >
                <span className="shell-button__label">Actions</span>
              </button>
            </ToolbarGroup>
            <div className="workspace-command-bar__workspace-controls">
              <label className="workspace-command-bar__field">
                <span>Density</span>
                <select aria-label="Workspace density mode" value={densityMode} onChange={(event) => onSelectDensityMode(event.target.value as WorkspaceDensityMode)}>
                  <option value="compact">Compact</option>
                  <option value="regular">Regular</option>
                  <option value="spacious">Spacious</option>
                </select>
              </label>
              <label className="workspace-command-bar__field">
                <span>Layout preset</span>
                <select aria-label="Workspace layout preset" value={activeLayoutPresetId} onChange={(event) => onSelectLayoutPreset(event.target.value as WorkspaceLayoutPresetId)}>
                  {workspaceLayoutPresets.map((preset) => (
                    <option key={preset.id} value={preset.id}>
                      {preset.label}
                    </option>
                  ))}
                </select>
              </label>
            </div>
          </div>
        </div>

        <PenpotLegacyTopStrip
          brand="Zephyr Pin Configurator"
          sectionLabel="Section"
          sectionValue={activeLayoutPresetId}
          sectionOptions={penpotSectionOptions}
          onSelectSection={onSelectLayoutPreset}
          boardValue={selectedBoardId}
          boardOptions={penpotBoardOptions}
          onSelectBoard={onSelectBoard}
          boardChipLabel={selectedBoard?.name ?? "No board selected"}
          runtimeSummary={boardRuntimeSummary}
          actions={penpotActions}
        />
      </section>

      <CommandSurfaceDialog
        open={actionsDialogOpen}
        onOpenChange={setActionsDialogOpen}
        title="Workspace actions"
        description="Use the same action list for toolbar buttons, shortcuts, and output routing so project control stays consistent across the shell."
      >
        <div className="workspace-actions-dialog">
          {actionGroups.map((group) => (
            <section key={group.label} className="workspace-actions-dialog__group">
              <h3>{group.label}</h3>
              <div className="workspace-actions-dialog__cards">
                {group.items.map((item) => (
                  <button
                    key={item.id}
                    type="button"
                    className="workspace-actions-dialog__card"
                    onClick={() => {
                      onRunCommandById(item.id, { closePalette: false });
                      setActionsDialogOpen(false);
                    }}
                    disabled={projectBusy}
                  >
                    <span>{item.label}</span>
                    <ShortcutHint shortcut={item.shortcut} />
                  </button>
                ))}
              </div>
            </section>
          ))}

          <section className="workspace-actions-dialog__group">
            <h3>Execution</h3>
            <div className="workspace-actions-dialog__cards">
              {actionGroups
                .find((group) => group.label === "Execution")
                ?.items.map((item) => (
                  <button
                    key={item.id}
                    type="button"
                    className="workspace-actions-dialog__card"
                    onClick={() => {
                      onRunCommandById(item.id, { closePalette: false });
                      setActionsDialogOpen(false);
                    }}
                  >
                    <span>{item.label}</span>
                    {item.shortcut ? <ShortcutHint shortcut={item.shortcut} /> : <span>Output Zone</span>}
                  </button>
                ))}
            </div>
            <EmptyState
              title="Execution routes are ready"
              detail="Choose Build, Simulation, or Test here to jump into the matching output channel, then inspect readiness blockers in the bottom strip before exporting or validating."
              tone="info"
              compact
            />
          </section>

          <section className="workspace-actions-dialog__group">
            <h3>Keyboard map</h3>
            <dl className="workspace-actions-dialog__shortcuts">
              {workspaceShortcutReferences.map((shortcut) => (
                <div key={shortcut.id}>
                  <dt>{shortcut.label}</dt>
                  <dd>{shortcut.shortcut}</dd>
                </div>
              ))}
            </dl>
          </section>
        </div>
      </CommandSurfaceDialog>
    </>
  );
}
