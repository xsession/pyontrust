import type { DockviewApi } from "dockview";
import { workspaceDockPanelDefinitions } from "../panels/dockPanelDefinitions";
import type { WorkspaceDockPanelParams } from "../panels/dockPanelParams";
import { getWorkspaceLayoutPreset, type WorkspaceLayoutPresetId } from "./workspaceShellPreferences";

export function getDefaultWorkspaceDockPanels(layoutPresetId: WorkspaceLayoutPresetId = "bring-up") {
  const anchorPanelId = getWorkspaceLayoutPreset(layoutPresetId).panelId;
  const anchorPanel = workspaceDockPanelDefinitions.find((panel) => panel.id === anchorPanelId);
  const remainingPanels = workspaceDockPanelDefinitions.filter((panel) => panel.id !== anchorPanelId);

  return anchorPanel ? [anchorPanel, ...remainingPanels] : [...workspaceDockPanelDefinitions];
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
  if (persistedLayout) {
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
