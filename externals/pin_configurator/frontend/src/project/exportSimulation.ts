import type { ProjectDocument } from "./projectDocument";
import {
  buildGeneratedArtifactExportBundle,
  downloadGeneratedArtifactBundle,
  type GeneratedArtifactExportBundle,
  type GeneratedArtifactExportFile,
  type GeneratedArtifactFileDownloader,
} from "./exportArtifacts";

export interface RenodeSimulationExportBundle extends GeneratedArtifactExportBundle {
  manifest: {
    boardId: string;
    renodeEnabled: boolean;
    platform: string;
    uart: string;
    bootLine: string;
    appbenchTarget: string;
    robotTarget: string;
  };
}

function resolveBaseName(project: ProjectDocument): string {
  return project.board_id.trim() || "pin-configurator";
}

export function buildRenodeSimulationExportBundle(project: ProjectDocument): RenodeSimulationExportBundle {
  const baseName = resolveBaseName(project);
  const artifactBundle = buildGeneratedArtifactExportBundle(project);
  const files: GeneratedArtifactExportFile[] = [...artifactBundle.files];

  if (project.renode.resc.trim()) {
    files.push({
      fileName: `${baseName}.resc`,
      content: project.renode.resc,
      mimeType: "text/plain;charset=utf-8",
    });
  }

  if (project.renode.robot.trim()) {
    files.push({
      fileName: `${baseName}.robot`,
      content: project.renode.robot,
      mimeType: "text/plain;charset=utf-8",
    });
  }

  const manifest = {
    boardId: project.board_id,
    renodeEnabled: project.renode.enabled,
    platform: project.renode.platform,
    uart: project.renode.uart,
    bootLine: project.renode.boot_line,
    appbenchTarget: project.renode.appbench_target,
    robotTarget: project.renode.robot_target,
  };

  files.push({
    fileName: `${baseName}.simulation.json`,
    content: JSON.stringify(manifest, null, 2),
    mimeType: "application/json;charset=utf-8",
  });

  return {
    baseName,
    files,
    manifest,
  };
}

export function downloadRenodeSimulationExportBundle(
  bundle: RenodeSimulationExportBundle,
  downloadFile?: GeneratedArtifactFileDownloader,
): number {
  return downloadGeneratedArtifactBundle(bundle, downloadFile);
}