import { isEditableTarget } from "./shellPalette";
import { workspaceDockPanelDefinitions } from "../panels/dockPanelDefinitions";

export interface WorkspaceShortcutReference {
  id: string;
  label: string;
  shortcut: string;
  scope: "global" | "panel";
}

export type WorkspaceShortcutAction =
  | { kind: "palette.open" }
  | { kind: "actions.open" }
  | { kind: "command.run"; commandId: string }
  | { kind: "panel.focus"; panelId: string };

export const workspaceShortcutReferences: WorkspaceShortcutReference[] = [
  { id: "palette.open", label: "Open command palette", shortcut: "Ctrl+K / Ctrl+P / Ctrl+F", scope: "global" },
  { id: "actions.open", label: "Open keyboard map", shortcut: "Shift+?", scope: "global" },
  { id: "project.save", label: "Save project", shortcut: "Ctrl+S", scope: "global" },
  { id: "project.load", label: "Load project", shortcut: "Ctrl+O", scope: "global" },
  { id: "export.artifacts", label: "Export artifacts", shortcut: "Ctrl+E", scope: "global" },
  { id: "export.renode", label: "Export Renode bundle", shortcut: "Ctrl+Shift+E", scope: "global" },
  ...workspaceDockPanelDefinitions
    .filter((panel) => panel.shortcut !== "Palette")
    .map((panel) => ({
      id: `panel.${panel.id}`,
      label: `Focus ${panel.title}`,
      shortcut: panel.shortcut,
      scope: "panel" as const,
    })),
];

function matchesPanelShortcut(shortcut: string, event: KeyboardEvent): boolean {
  if (shortcut === "Palette") {
    return false;
  }

  const parts = shortcut.toLowerCase().split("+");
  const key = parts[parts.length - 1];
  const requiresAlt = parts.includes("alt");
  const requiresShift = parts.includes("shift");
  const requiresCtrl = parts.includes("ctrl") || parts.includes("control");
  const requiresMeta = parts.includes("meta") || parts.includes("cmd");
  const normalizedKey = event.key.toLowerCase();

  return (
    normalizedKey === key &&
    event.altKey === requiresAlt &&
    event.shiftKey === requiresShift &&
    event.ctrlKey === requiresCtrl &&
    event.metaKey === requiresMeta
  );
}

export function getWorkspaceShortcutAction(event: KeyboardEvent): WorkspaceShortcutAction | null {
  const normalizedKey = event.key.toLowerCase();
  const primaryModifier = event.ctrlKey || event.metaKey;

  if ((event.shiftKey && normalizedKey === "?") || (event.shiftKey && normalizedKey === "/")) {
    return { kind: "actions.open" };
  }

  const panelShortcut = workspaceDockPanelDefinitions.find((panel) => matchesPanelShortcut(panel.shortcut, event));
  if (panelShortcut) {
    return { kind: "panel.focus", panelId: panelShortcut.id };
  }

  if (!primaryModifier) {
    return null;
  }

  if (normalizedKey === "k" || normalizedKey === "p" || (normalizedKey === "f" && !isEditableTarget(event.target))) {
    return { kind: "palette.open" };
  }

  if (normalizedKey === "s") {
    return { kind: "command.run", commandId: "project.save" };
  }

  if (normalizedKey === "o") {
    return { kind: "command.run", commandId: "project.load" };
  }

  if (normalizedKey === "e") {
    return { kind: "command.run", commandId: event.shiftKey ? "export.renode" : "export.artifacts" };
  }

  return null;
}