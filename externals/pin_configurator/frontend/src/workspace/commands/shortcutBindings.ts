import { isEditableTarget } from "./shellPalette";

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
  | { kind: "panel.focus"; panelIndex: number };

export const workspaceShortcutReferences: WorkspaceShortcutReference[] = [
  { id: "palette.open", label: "Open command palette", shortcut: "Ctrl+K / Ctrl+P / Ctrl+F", scope: "global" },
  { id: "actions.open", label: "Open keyboard map", shortcut: "Shift+?", scope: "global" },
  { id: "project.save", label: "Save project", shortcut: "Ctrl+S", scope: "global" },
  { id: "project.load", label: "Load project", shortcut: "Ctrl+O", scope: "global" },
  { id: "export.artifacts", label: "Export artifacts", shortcut: "Ctrl+E", scope: "global" },
  { id: "export.renode", label: "Export Renode bundle", shortcut: "Ctrl+Shift+E", scope: "global" },
  { id: "dock.focus", label: "Focus dock panels 1-8", shortcut: "Alt+1..8", scope: "panel" },
];

export function getWorkspaceShortcutAction(event: KeyboardEvent): WorkspaceShortcutAction | null {
  const normalizedKey = event.key.toLowerCase();
  const primaryModifier = event.ctrlKey || event.metaKey;

  if ((event.shiftKey && normalizedKey === "?") || (event.shiftKey && normalizedKey === "/")) {
    return { kind: "actions.open" };
  }

  if (event.altKey && /^\d$/.test(normalizedKey)) {
    return { kind: "panel.focus", panelIndex: Number.parseInt(normalizedKey, 10) - 1 };
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