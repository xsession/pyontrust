import type { ProjectDocument } from "./projectDocument";

function asRecord(value: unknown): Record<string, unknown> {
  return value && typeof value === "object" && !Array.isArray(value) ? (value as Record<string, unknown>) : {};
}

export interface GeneratedArtifactExportFile {
  fileName: string;
  content: string;
  mimeType: string;
}

export interface GeneratedArtifactExportBundle {
  baseName: string;
  files: GeneratedArtifactExportFile[];
}

function resolveGeneratedArtifactFileName(project: ProjectDocument, kind: "overlay" | "config" | "fragments"): string {
  const outputs = asRecord(project.generated_fragments.outputs);
  const boardId = project.board_id.trim() || "pin-configurator";

  if (kind === "overlay") {
    const overlayName = typeof outputs.overlay === "string" ? outputs.overlay.trim() : "";
    return overlayName || `${boardId}.overlay`;
  }

  if (kind === "config") {
    const configName = typeof outputs.config === "string" ? outputs.config.trim() : "";
    return configName || `${boardId}.conf`;
  }

  return `${boardId}.generated-fragments.json`;
}

export function buildGeneratedArtifactExportBundle(project: ProjectDocument): GeneratedArtifactExportBundle {
  const files: GeneratedArtifactExportFile[] = [];

  if (project.generated_overlay.trim()) {
    files.push({
      fileName: resolveGeneratedArtifactFileName(project, "overlay"),
      content: project.generated_overlay,
      mimeType: "text/plain;charset=utf-8",
    });
  }

  if (project.generated_conf.trim()) {
    files.push({
      fileName: resolveGeneratedArtifactFileName(project, "config"),
      content: project.generated_conf,
      mimeType: "text/plain;charset=utf-8",
    });
  }

  if (Object.keys(project.generated_fragments).length > 0) {
    files.push({
      fileName: resolveGeneratedArtifactFileName(project, "fragments"),
      content: JSON.stringify(project.generated_fragments, null, 2),
      mimeType: "application/json;charset=utf-8",
    });
  }

  return {
    baseName: project.board_id.trim() || "pin-configurator",
    files,
  };
}

export type GeneratedArtifactFileDownloader = (file: GeneratedArtifactExportFile) => void;

export function downloadGeneratedArtifactFile(file: GeneratedArtifactExportFile): void {
  const blob = new Blob([file.content], { type: file.mimeType });
  const objectUrl = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = objectUrl;
  anchor.download = file.fileName;
  anchor.click();
  URL.revokeObjectURL(objectUrl);
}

export function downloadGeneratedArtifactBundle(
  bundle: GeneratedArtifactExportBundle,
  downloadFile: GeneratedArtifactFileDownloader = downloadGeneratedArtifactFile,
): number {
  bundle.files.forEach((file) => downloadFile(file));
  return bundle.files.length;
}