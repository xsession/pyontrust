import type { BoardSummary } from "../../contracts/api";
import type { ShellOutputChannelViewModel } from "../../presenters/useShellPresenter";
import type { ShellPaletteItem } from "../commands/shellPalette";
import { workspaceLayoutPresets, type WorkspaceLayoutPresetId } from "../layout/workspaceShellPreferences";
import { workspaceDockPanelDefinitions } from "../panels/dockPanelDefinitions";

const outputChannelLabels = {
  build: "Build Output",
  simulation: "Simulation Output",
  diagnostics: "Diagnostics",
  tests: "Test Output",
} as const;

export function buildBoardQuickOpenItems(
  boards: BoardSummary[],
  loading: boolean,
  selectBoard: (boardId: string) => void,
): ShellPaletteItem[] {
  return boards.map((board) => ({
    id: `board.${board.id}`,
    label: `Open Board ${board.name}`,
    description: `Select ${board.board} in ${board.package} and repopulate the canonical project context.`,
    shortcut: "",
    group: "Boards",
    disabled: loading,
    keywords: [board.id, board.board, board.name, board.package, "board", "quick open"],
    run: () => selectBoard(board.id),
  }));
}

export function buildPanelQuickOpenItems(onFocusPanel: (panelId: string) => void): ShellPaletteItem[] {
  return workspaceDockPanelDefinitions.map((panel) => ({
    id: `panel.${panel.id}`,
    label: `Focus ${panel.title}`,
    description: panel.description,
    shortcut: panel.shortcut,
    group: "Panels",
    disabled: false,
    keywords: panel.keywords,
    run: () => onFocusPanel(panel.id),
  }));
}

export function buildOutputQuickOpenItems(
  outputChannels: ShellOutputChannelViewModel[],
  selectOutputChannel: (channelId: string) => void,
): ShellPaletteItem[] {
  return outputChannels.map((channel) => ({
    id: `output.${channel.id}`,
    label: `Open ${channel.label}`,
    description: `Show the ${channel.label.toLowerCase()} channel in the bottom execution zone.`,
    shortcut: "",
    group: "Outputs",
    disabled: false,
    keywords: [channel.id, channel.label, "diagnostics", "output", "tests"],
    run: () => selectOutputChannel(channel.id),
  }));
}

export function buildLayoutPresetQuickOpenItems(
  activePresetId: WorkspaceLayoutPresetId,
  selectLayoutPreset: (presetId: WorkspaceLayoutPresetId) => void,
): ShellPaletteItem[] {
  return workspaceLayoutPresets.map((preset) => ({
    id: `preset.${preset.id}`,
    label: `Apply ${preset.label}`,
    description: `${preset.description} Focus ${workspaceDockPanelDefinitions.find((panel) => panel.id === preset.panelId)?.title ?? preset.panelId} and route ${outputChannelLabels[preset.outputChannelId]}.`,
    shortcut: "",
    group: "Presets",
    disabled: preset.id === activePresetId,
    keywords: [...preset.keywords, "preset", "layout", "workspace"],
    run: () => selectLayoutPreset(preset.id),
  }));
}
