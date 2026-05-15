import { useEffect, useMemo, useState } from "react";
import type { ShellMetric } from "../../presenters/useShellPresenter";
import { CommandSurfaceDialog } from "../../shared/ui/commands/CommandSurfaceDialog";
import { ShortcutHint } from "../../shared/ui/commands/ShortcutHint";
import { SplitButton } from "../../shared/ui/components/SplitButton";
import { ToolbarGroup } from "../../shared/ui/components/ToolbarGroup";
import { EmptyState } from "../../shared/ui/feedback/EmptyState";
import { MetricCard } from "../../shared/ui/MetricCard";
import { StatusChip } from "../../shared/ui/StatusChip";
import { workspaceLayoutPresets, type WorkspaceDensityMode, type WorkspaceLayoutPresetId } from "../layout/workspaceShellPreferences";
import { workspaceShortcutReferences } from "../commands/shortcutBindings";

interface WorkspaceCommandBarProps {
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
  metrics: ShellMetric[];
  onOpenPalette: () => void;
  onRunCommandById: (commandId: string, options?: { closePalette?: boolean }) => void;
  onSelectDensityMode: (densityMode: WorkspaceDensityMode) => void;
  onSelectLayoutPreset: (presetId: WorkspaceLayoutPresetId) => void;
}

export function WorkspaceCommandBar({
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
  metrics,
  onOpenPalette,
  onRunCommandById,
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

  return (
    <>
      <section className="workspace-command-bar">
        <div className="workspace-command-bar__identity">
          <StatusChip label="Professional Workspace Shell" tone="success" />
          <h1>Pin Configurator workspace</h1>
          <p>
            Project actions, workflow presets, outputs, and simulation review now share one dense command surface.
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
          <ToolbarGroup label="Power" className="workspace-command-bar__action-group">
            <button
              type="button"
              className="shell-button shell-button--ghost"
              aria-keyshortcuts="Shift+?"
              onClick={() => setActionsDialogOpen(true)}
            >
              <span className="shell-button__label">Keyboard Map</span>
              <ShortcutHint shortcut="Shift+?" />
            </button>
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
            <button
              type="button"
              className="shell-button"
              aria-keyshortcuts="Control+O"
              onClick={() => onRunCommandById("project.load", { closePalette: false })}
              disabled={projectBusy}
            >
              <span className="shell-button__label">Load Project</span>
              <ShortcutHint shortcut="Ctrl+O" />
            </button>
          </ToolbarGroup>
          <ToolbarGroup label="History" className="workspace-command-bar__action-group">
            <button
              type="button"
              className="shell-button"
              aria-keyshortcuts="Control+Z"
              onClick={() => onRunCommandById("history.undo", { closePalette: false })}
              disabled={projectBusy || !canUndoProjectDocument}
            >
              <span className="shell-button__label">Undo Change</span>
              <ShortcutHint shortcut="Ctrl+Z" />
            </button>
            <button
              type="button"
              className="shell-button"
              aria-keyshortcuts="Control+Shift+Z"
              onClick={() => onRunCommandById("history.redo", { closePalette: false })}
              disabled={projectBusy || !canRedoProjectDocument}
            >
              <span className="shell-button__label">Redo Change</span>
              <ShortcutHint shortcut="Ctrl+Shift+Z" />
            </button>
          </ToolbarGroup>
          <ToolbarGroup label="Execution" className="workspace-command-bar__action-group">
            <button
              type="button"
              className="shell-button"
              onClick={() => onRunCommandById("output.build", { closePalette: false })}
            >
              <span className="shell-button__label">Build</span>
            </button>
            <button
              type="button"
              className="shell-button"
              onClick={() => onRunCommandById("output.simulation", { closePalette: false })}
            >
              <span className="shell-button__label">Simulate</span>
            </button>
            <button
              type="button"
              className="shell-button"
              onClick={() => onRunCommandById("output.tests", { closePalette: false })}
            >
              <span className="shell-button__label">Test</span>
            </button>
          </ToolbarGroup>
          <ToolbarGroup label="Export" className="workspace-command-bar__action-group">
            <button
              type="button"
              className="shell-button"
              aria-keyshortcuts="Control+E"
              onClick={() => onRunCommandById("export.artifacts", { closePalette: false })}
              disabled={projectBusy}
            >
              <span className="shell-button__label">Export Artifacts</span>
              <ShortcutHint shortcut="Ctrl+E" />
            </button>
            <button
              type="button"
              className="shell-button"
              aria-keyshortcuts="Control+Shift+E"
              onClick={() => onRunCommandById("export.renode", { closePalette: false })}
              disabled={projectBusy}
            >
              <span className="shell-button__label">Export Renode Bundle</span>
              <ShortcutHint shortcut="Ctrl+Shift+E" />
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
      </section>

      <CommandSurfaceDialog
        open={actionsDialogOpen}
        onOpenChange={setActionsDialogOpen}
        title="Workspace actions"
        description="Save, load, export, and upcoming execution flows use one dialog pattern so toolbar buttons, menus, and shortcuts stay aligned."
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
              title="Execution launchers remain shell-owned"
              detail="Build, simulation, and test readiness now have dedicated shell actions even while backend execution still flows through the presenter status channels."
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

      <section className="workspace-shell__metrics" aria-label="Workspace metrics">
        {metrics.map((metric) => (
          <MetricCard
            key={metric.label}
            label={metric.label}
            value={metric.value}
            detail={metric.detail}
            accent={metric.accent}
            icon={metric.label === "Board Surface" ? "◌" : metric.label === "Package Coverage" ? "▦" : "◍"}
          />
        ))}
      </section>
    </>
  );
}
