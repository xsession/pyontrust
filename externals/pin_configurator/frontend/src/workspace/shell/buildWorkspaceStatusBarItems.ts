import type { BoardSummary, ProjectDocument } from "../../contracts/api";
import { selectProjectArtifactStatus, selectProjectIntegrityStatus, selectProjectReadinessStatus } from "../../project/selectors";
import type { ProjectStatus } from "../../project/workspaceState";

export interface WorkspaceStatusBarItemDescriptor {
  id: string;
  label: string;
  value: string;
  detail: string;
  tone: "neutral" | "success" | "warning";
}

interface BuildWorkspaceStatusBarItemsInput {
  activeBoard: BoardSummary | null;
  projectDocument: ProjectDocument;
  projectFilePath: string;
  canUndoProjectDocument: boolean;
  projectBusy: boolean;
  projectStatus: ProjectStatus;
}

export function buildWorkspaceStatusBarItems({
  activeBoard,
  projectDocument,
  projectFilePath,
  canUndoProjectDocument,
  projectBusy,
  projectStatus,
}: BuildWorkspaceStatusBarItemsInput): WorkspaceStatusBarItemDescriptor[] {
  const artifacts = selectProjectArtifactStatus(projectDocument);
  const readiness = selectProjectReadinessStatus(projectDocument);
  const integrity = selectProjectIntegrityStatus(projectDocument);
  const boardLabel = activeBoard ? `${activeBoard.name} (${activeBoard.package})` : "Board pending";
  const workspaceProfile = projectFilePath.trim() ? "Project-backed" : "Scratch session";
  const dirtyState = canUndoProjectDocument ? "Unsaved changes" : "Clean";
  const readinessValue = `${readiness.readySectionCount}/4 Ready`;
  const readinessDetail = [
    readiness.hasBoard ? "Board assigned" : "Board pending",
    readiness.hasGeneratedArtifacts ? "Artifacts present" : "Artifacts pending",
    readiness.hasRenodeTarget ? "Renode target ready" : "Renode target pending",
    readiness.hasProtocolEntries ? `${artifacts.enabledProtocolEntryCount} enabled protocol${artifacts.enabledProtocolEntryCount === 1 ? "" : "s"}` : "No enabled protocols",
  ].join(" · ");
  const artifactValue =
    artifacts.authorityState === "authoritative"
      ? "Authoritative"
      : artifacts.authorityState === "stale"
        ? "Stale"
        : "Missing";
  const integrityValue = integrity.warningCount ? `${integrity.warningCount} warning${integrity.warningCount === 1 ? "" : "s"}` : "Passing";
  const integrityDetail = integrity.warningCount ? integrity.issues.slice(0, 2).join(" · ") : projectStatus.message;

  return [
    {
      id: "board",
      label: "Board",
      value: boardLabel,
      detail: projectDocument.board_id || "Select a board.",
      tone: activeBoard ? "success" : "warning",
    },
    {
      id: "profile",
      label: "Workspace Profile",
      value: workspaceProfile,
      detail: projectFilePath || "Project path pending.",
      tone: projectFilePath.trim() ? "neutral" : "warning",
    },
    {
      id: "dirty",
      label: "Dirty State",
      value: dirtyState,
      detail: canUndoProjectDocument ? "Undo stack pending." : "Session clean.",
      tone: canUndoProjectDocument ? "warning" : "success",
    },
    {
      id: "readiness",
      label: "Readiness",
      value: readinessValue,
      detail: readinessDetail,
      tone: readiness.readySectionCount === 4 ? "success" : readiness.readySectionCount <= 1 ? "warning" : "neutral",
    },
    {
      id: "artifacts",
      label: "Artifacts",
      value: artifactValue,
      detail: artifacts.authorityReason,
      tone: artifacts.authorityState === "authoritative" ? "success" : artifacts.authorityState === "stale" ? "warning" : "neutral",
    },
    {
      id: "integrity",
      label: "Integrity",
      value: projectBusy ? `${integrityValue} · Busy` : integrityValue,
      detail: integrityDetail,
      tone: integrity.warningCount || projectStatus.tone === "error" || projectBusy ? "warning" : "success",
    },
  ];
}