import type { WorkspaceLayoutPresetId } from "../../workspace/layout/workspaceShellPreferences";

export interface PenpotSelectOption<TValue extends string = string> {
  value: TValue;
  label: string;
}

export interface PenpotLegacyAction {
  id: string;
  label: string;
  disabled?: boolean;
  tone?: "default" | "primary";
  onPress: () => void;
}

interface PenpotLegacyTopStripProps {
  brand: string;
  sectionLabel: string;
  sectionValue: WorkspaceLayoutPresetId;
  sectionOptions: readonly PenpotSelectOption<WorkspaceLayoutPresetId>[];
  onSelectSection: (value: WorkspaceLayoutPresetId) => void;
  boardValue: string;
  boardOptions: readonly PenpotSelectOption[];
  onSelectBoard: (value: string) => void;
  boardChipLabel: string;
  runtimeSummary: string;
  actions: readonly PenpotLegacyAction[];
}

export function PenpotLegacyTopStrip({
  brand,
  sectionLabel,
  sectionValue,
  sectionOptions,
  onSelectSection,
  boardValue,
  boardOptions,
  onSelectBoard,
  boardChipLabel,
  runtimeSummary,
  actions,
}: PenpotLegacyTopStripProps) {
  return (
    <div className="workspace-command-bar__legacy-shell" aria-hidden="true">
      <div className="workspace-command-bar__legacy-brand">{brand}</div>
      <div className="workspace-command-bar__legacy-toprow">
        <label className="workspace-command-bar__legacy-field workspace-command-bar__legacy-field--section">
          <span>{sectionLabel}</span>
          <select value={sectionValue} onChange={(event) => onSelectSection(event.target.value as WorkspaceLayoutPresetId)}>
            {sectionOptions.map((option) => (
              <option key={option.value} value={option.value}>{option.label}</option>
            ))}
          </select>
        </label>
      </div>
      <div className="workspace-command-bar__legacy-toolbar">
        <div className="workspace-command-bar__legacy-board-cluster">
          <select className="workspace-command-bar__legacy-board-select" value={boardValue} onChange={(event) => onSelectBoard(event.target.value)}>
            {boardOptions.map((option) => (
              <option key={option.value} value={option.value}>{option.label}</option>
            ))}
          </select>
          <span className="workspace-command-bar__legacy-board-chip">{boardChipLabel}</span>
        </div>
        <div className="workspace-command-bar__legacy-stats">{runtimeSummary}</div>
        <div className="workspace-command-bar__legacy-actions">
          {actions.map((action) => (
            <button
              key={action.id}
              type="button"
              className={action.tone === "primary" ? "workspace-command-bar__legacy-button workspace-command-bar__legacy-button--primary" : "workspace-command-bar__legacy-button"}
              onClick={action.onPress}
              disabled={action.disabled}
            >
              {action.label}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}