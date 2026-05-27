import type { DockviewApi } from "dockview";
import { workspaceDockPanelDefinitions } from "../panels/dockPanelDefinitions";
import type { WorkspaceDockPanelParams } from "../panels/dockPanelParams";
import { getWorkspaceLayoutPreset, type WorkspaceLayoutPresetId } from "./workspaceShellPreferences";

const defaultWorkspaceDockPanelIdsByPreset: Record<WorkspaceLayoutPresetId, readonly string[]> = {
  "bring-up": ["workspace-pin-assignments"],
  "protocol-integration": [
    "workspace-protocol-editor",
    "workspace-pin-assignments",
    "workspace-generated-header",
    "workspace-generated-source",
  ],
  "codegen-review": [
    "workspace-generated-overlay",
    "workspace-generated-config",
    "workspace-generated-fragments",
    "workspace-generated-header",
    "workspace-generated-source",
  ],
  "renode-validation": [
    "workspace-renode-profile",
    "workspace-renode-resc",
    "workspace-renode-robot",
    "workspace-overview",
  ],
};

export function getDefaultWorkspaceDockPanels(layoutPresetId: WorkspaceLayoutPresetId = "bring-up") {
  const anchorPanelId = getWorkspaceLayoutPreset(layoutPresetId).panelId;
  const presetPanelIds = defaultWorkspaceDockPanelIdsByPreset[layoutPresetId] ?? defaultWorkspaceDockPanelIdsByPreset["bring-up"];
  const orderedPanelIds = [anchorPanelId, ...presetPanelIds.filter((panelId) => panelId !== anchorPanelId)];
  const panels = orderedPanelIds
    .map((panelId) => workspaceDockPanelDefinitions.find((panel) => panel.id === panelId))
    .filter((panel): panel is (typeof workspaceDockPanelDefinitions)[number] => Boolean(panel));

  return panels.length ? panels : [...workspaceDockPanelDefinitions];
}

export function populateDefaultWorkspaceDock(
  dockApi: Pick<DockviewApi, "addPanel">,
  panelParams: WorkspaceDockPanelParams,
  layoutPresetId: WorkspaceLayoutPresetId = "bring-up",
) {
  getDefaultWorkspaceDockPanels(layoutPresetId).forEach(({ id, title, component }) => {
    dockApi.addPanel({
      id,
      title,
      component,
      params: panelParams,
    });
  });
}

export function restoreOrPopulateWorkspaceDock(
  dockApi: Pick<DockviewApi, "addPanel" | "fromJSON">,
  panelParams: WorkspaceDockPanelParams,
  persistedLayout?: object | null,
  layoutPresetId: WorkspaceLayoutPresetId = "bring-up",
) {
  if (persistedLayout && layoutPresetId !== "bring-up") {
    try {
      dockApi.fromJSON(persistedLayout as never);
      return true;
    } catch {
      // Fall through to the known-good default layout when persisted JSON is stale.
    }
  }

  populateDefaultWorkspaceDock(dockApi, panelParams, layoutPresetId);
  return false;
}
