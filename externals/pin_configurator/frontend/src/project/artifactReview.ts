import type { BoardSummary, ProtocolEntry } from "../contracts/api";
import { buildGeneratedConfFromBoard, buildGeneratedFragmentsFromBoard, buildGeneratedOverlayFromBoard, formatGeneratedFragments } from "./generatedArtifacts";
import type { ProjectDocument, RenodeProfile } from "./projectDocument";
import { protocolTemplateById, type ProtocolEditorDocument } from "./protocolEditor";

export type ArtifactReviewPanelId =
  | "workspace-generated-overlay"
  | "workspace-generated-config"
  | "workspace-generated-fragments"
  | "workspace-generated-header"
  | "workspace-generated-source"
  | "workspace-renode-resc"
  | "workspace-renode-robot";

export interface ArtifactMarker {
  severity: 1 | 2 | 4 | 8;
  message: string;
  lineNumber: number;
  column?: number;
  endLineNumber?: number;
  endColumn?: number;
}

export interface ArtifactReviewDocument {
  id: string;
  panelId: ArtifactReviewPanelId;
  title: string;
  fileName: string;
  language: string;
  content: string;
  baselineContent: string;
  editable: boolean;
  sourceKind: "editable-project-asset" | "derived-output";
  ownerLabel: string;
  description: string;
  freshnessState: "current" | "stale" | "pending";
  freshnessLabel: string;
  freshnessDetail: string;
  changeSummary: string;
  exportSummary: string;
  markers: ArtifactMarker[];
}

export interface ArtifactNavigationTarget {
  panelId: ArtifactReviewPanelId;
  lineNumber: number;
  column?: number;
  label: string;
}

export interface ArtifactDiagnosticEntry {
  id: string;
  summary: string;
  detail: string;
  severity: "info" | "success" | "warning" | "error";
  navigation: ArtifactNavigationTarget;
}

function countLines(value: string): number {
  return Math.max(value.split("\n").length, 1);
}

function countComparableLines(value: string): number {
  if (!value.trim()) {
    return 0;
  }

  return value.split("\n").length;
}

function buildLineChangeSummary(currentContent: string, baselineContent: string): string {
  const currentLineCount = countComparableLines(currentContent);
  const baselineLineCount = countComparableLines(baselineContent);

  if (!baselineContent.trim()) {
    return currentLineCount ? `${currentLineCount} current lines are staged in the review panel.` : "No lines are staged in the review panel yet.";
  }

  const currentLines = currentContent.split("\n");
  const baselineLines = baselineContent.split("\n");
  const comparableLineCount = Math.max(currentLines.length, baselineLines.length);
  let changedPositions = 0;

  for (let index = 0; index < comparableLineCount; index += 1) {
    if ((currentLines[index] ?? "") !== (baselineLines[index] ?? "")) {
      changedPositions += 1;
    }
  }

  if (!changedPositions) {
    return `${currentLineCount} current lines match the generated baseline.`;
  }

  return `${changedPositions} line position${changedPositions === 1 ? "" : "s"} differ across ${currentLineCount} current and ${baselineLineCount} baseline lines.`;
}

function buildArtifactExportSummary(documentId: string, fileName: string): string {
  switch (documentId) {
    case "overlay":
    case "config":
    case "fragments":
      return `Panel export downloads ${fileName}, and workspace Export Artifacts includes this file in the generated artifact bundle.`;
    case "resc":
    case "robot":
      return `Panel export downloads ${fileName}, and Export Renode Bundle includes this file in the simulation handoff bundle.`;
    default:
      return `Panel export downloads ${fileName} as a review snapshot from the current workspace state.`;
  }
}

function buildArtifactFreshness(input: {
  content: string;
  baselineContent: string;
  editable: boolean;
  sourceKind: ArtifactReviewDocument["sourceKind"];
}): Pick<ArtifactReviewDocument, "freshnessState" | "freshnessLabel" | "freshnessDetail" | "changeSummary"> {
  const { content, baselineContent, editable, sourceKind } = input;

  if (!content.trim()) {
    return {
      freshnessState: "pending",
      freshnessLabel: "Pending",
      freshnessDetail: editable
        ? "No saved artifact content is staged yet. Seed or edit this file before treating it as ready."
        : "No derived preview content is available yet for the current workspace state.",
      changeSummary: buildLineChangeSummary(content, baselineContent),
    };
  }

  if (!baselineContent.trim()) {
    return {
      freshnessState: "current",
      freshnessLabel: sourceKind === "derived-output" ? "Derived" : "Current",
      freshnessDetail: sourceKind === "derived-output"
        ? "This preview is derived directly from the current project state, so the dock is already showing the active generated output."
        : "This saved project asset has no generated comparison snapshot, so the current content is treated as the review source of truth.",
      changeSummary: buildLineChangeSummary(content, baselineContent),
    };
  }

  if (content === baselineContent) {
    return {
      freshnessState: "current",
      freshnessLabel: "Current",
      freshnessDetail: editable
        ? "This saved artifact matches the current generated suggestion for the active project state."
        : "This derived output matches the current generated baseline.",
      changeSummary: buildLineChangeSummary(content, baselineContent),
    };
  }

  return {
    freshnessState: "stale",
    freshnessLabel: editable ? "Customized" : "Stale",
    freshnessDetail: editable
      ? "This saved artifact now differs from the current generated suggestion. Review the quick diff before export or save handoff."
      : "This generated output differs from the current baseline and should be reviewed before export handoff.",
    changeSummary: buildLineChangeSummary(content, baselineContent),
  };
}

function findLineContaining(value: string, token: string): number {
  const lines = value.split("\n");
  const index = lines.findIndex((line) => line.includes(token));
  return index >= 0 ? index + 1 : 1;
}

function buildSuggestedResc(profile: RenodeProfile): string {
  const platform = profile.platform.trim() || "zephyr.repl";
  const uart = profile.uart.trim() || "sysbus.uart0";
  const bootLine = profile.boot_line.trim() || "showAnalyzer ${uart}";

  return [
    "mach create",
    `machine LoadPlatformDescription @${platform}`,
    `showAnalyzer ${uart}`,
    bootLine.includes("showAnalyzer") ? "start" : bootLine,
  ].join("\n");
}

function buildSuggestedRobot(profile: RenodeProfile, boardId: string): string {
  const robotTarget = profile.robot_target.trim() || "robotbench";
  const uart = profile.uart.trim() || "sysbus.uart0";

  return [
    "*** Settings ***",
    `Suite Setup    Log    ${boardId || "project"} ready for ${robotTarget}`,
    "",
    "*** Test Cases ***",
    "Smoke Boot",
    `    Log    Open analyzer for ${uart}`,
  ].join("\n");
}

function entryInstanceName(entry: ProtocolEntry): string {
  const value = entry.values.instanceName;
  return typeof value === "string" && value.trim() ? value.trim() : protocolTemplateById(entry.templateId).label.toLowerCase().replace(/[^a-z0-9]+/g, "_");
}

function protocolValueLiteral(value: string | number | boolean): string {
  if (typeof value === "boolean") {
    return value ? "true" : "false";
  }

  if (typeof value === "number") {
    return String(value);
  }

  return `"${String(value).replace(/"/g, '\\"')}"`;
}

function buildProtocolHeader(document: ProtocolEditorDocument): string {
  const enabledEntries = document.entries.filter((entry) => entry.enabled !== false);
  if (!enabledEntries.length) {
    return [
      "#pragma once",
      "",
      "// Enable at least one protocol entry to materialize generated integration headers.",
    ].join("\n");
  }

  return [
    "#pragma once",
    "",
    "#include <stdbool.h>",
    "#include <stdint.h>",
    "",
    ...enabledEntries.flatMap((entry) => {
      const template = protocolTemplateById(entry.templateId);
      const instanceName = entryInstanceName(entry);
      return [
        `// ${template.label}`,
        `bool ${instanceName}_init(void);`,
        `void ${instanceName}_attach(void);`,
        "",
      ];
    }),
  ].join("\n");
}

function buildProtocolSource(document: ProtocolEditorDocument): string {
  const enabledEntries = document.entries.filter((entry) => entry.enabled !== false);
  if (!enabledEntries.length) {
    return [
      '#include "protocols.generated.h"',
      "",
      "// No enabled protocol entries are available for generated integration source.",
    ].join("\n");
  }

  return [
    '#include "protocols.generated.h"',
    "",
    ...enabledEntries.flatMap((entry) => {
      const template = protocolTemplateById(entry.templateId);
      const instanceName = entryInstanceName(entry);
      const values = Object.entries(entry.values).map(([key, value]) => `// ${key}: ${protocolValueLiteral(value)}`);
      return [
        `// ${template.label}`,
        ...values,
        `bool ${instanceName}_init(void) {`,
        "  return true;",
        "}",
        "",
        `void ${instanceName}_attach(void) {`,
        "  // Hook generated protocol lifecycle into the runtime startup path.",
        "}",
        "",
      ];
    }),
  ].join("\n");
}

function buildOverlayMarkers(content: string, unresolvedPinCount: number): ArtifactMarker[] {
  const markers: ArtifactMarker[] = [];
  if (!content.trim()) {
    markers.push({ severity: 4, message: "Generated overlay is empty.", lineNumber: 1 });
    return markers;
  }

  if (!content.includes("/dts-v1/;")) {
    markers.push({ severity: 4, message: "Overlay is missing the DTS header.", lineNumber: 1 });
  }

  if (unresolvedPinCount > 0) {
    markers.push({
      severity: 4,
      message: `${unresolvedPinCount} unresolved pin assignments remain. Review the pinctrl section before exporting.`,
      lineNumber: findLineContaining(content, "&pinctrl"),
    });
  }

  return markers;
}

function buildConfigMarkers(content: string, enabledProtocolCount: number): ArtifactMarker[] {
  const markers: ArtifactMarker[] = [];
  if (!content.trim()) {
    markers.push({ severity: 4, message: "Generated config is empty.", lineNumber: 1 });
    return markers;
  }

  if (!content.includes("CONFIG_PINCTRL=y")) {
    markers.push({ severity: 4, message: "Generated config should keep CONFIG_PINCTRL enabled.", lineNumber: 1 });
  }

  if (enabledProtocolCount > 0 && !content.includes("CONFIG_SERIAL")) {
    markers.push({ severity: 2, message: "Enabled protocol entries usually require a transport config such as CONFIG_SERIAL.", lineNumber: countLines(content) });
  }

  return markers;
}

function buildFragmentMarkers(content: string): ArtifactMarker[] {
  if (!content.trim()) {
    return [{ severity: 4, message: "Generated fragments are empty.", lineNumber: 1 }];
  }

  const parsed = JSON.parse(content) as Record<string, unknown>;
  const outputs = typeof parsed.outputs === "object" && parsed.outputs !== null ? (parsed.outputs as Record<string, unknown>) : {};
  const markers: ArtifactMarker[] = [];

  if (typeof outputs.overlay !== "string" || !outputs.overlay.trim()) {
    markers.push({ severity: 4, message: "Fragments are missing the overlay output descriptor.", lineNumber: findLineContaining(content, '"outputs"') });
  }

  if (typeof outputs.config !== "string" || !outputs.config.trim()) {
    markers.push({ severity: 4, message: "Fragments are missing the config output descriptor.", lineNumber: findLineContaining(content, '"outputs"') });
  }

  return markers;
}

function buildRescMarkers(content: string, enabled: boolean): ArtifactMarker[] {
  const markers: ArtifactMarker[] = [];
  if (enabled && !content.trim()) {
    markers.push({ severity: 4, message: "Renode is enabled but the RESC script is empty.", lineNumber: 1 });
    return markers;
  }

  if (content.trim() && !content.includes("mach create")) {
    markers.push({ severity: 4, message: "RESC scripts should create a Renode machine before they attach analyzers.", lineNumber: 1 });
  }

  return markers;
}

function buildRobotMarkers(content: string, robotTarget: string): ArtifactMarker[] {
  const markers: ArtifactMarker[] = [];
  if (robotTarget.trim() && !content.trim()) {
    markers.push({ severity: 4, message: "Robot target is configured but the Robot suite is empty.", lineNumber: 1 });
    return markers;
  }

  if (content.trim() && !content.includes("*** Test Cases ***")) {
    markers.push({ severity: 4, message: "Robot suites should declare a *** Test Cases *** section.", lineNumber: 1 });
  }

  return markers;
}

function buildProtocolMarkers(content: string, title: string): ArtifactMarker[] {
  if (!content.includes("_init(void)")) {
    return [{ severity: 4, message: `${title} has no enabled protocol entries to generate.`, lineNumber: 1 }];
  }

  return [];
}

export function buildArtifactReviewDocuments(input: {
  activeBoard: BoardSummary | null;
  projectDocument: ProjectDocument;
  unresolvedPinCount: number;
}): ArtifactReviewDocument[] {
  const { activeBoard, projectDocument, unresolvedPinCount } = input;
  const boardId = projectDocument.board_id.trim() || activeBoard?.board || "project";
  const seededOverlay = buildGeneratedOverlayFromBoard(activeBoard);
  const seededConfig = buildGeneratedConfFromBoard(activeBoard);
  const seededFragments = formatGeneratedFragments(buildGeneratedFragmentsFromBoard(activeBoard));
  const generatedHeader = buildProtocolHeader(projectDocument.protocol_editor);
  const generatedSource = buildProtocolSource(projectDocument.protocol_editor);
  const suggestedResc = buildSuggestedResc(projectDocument.renode);
  const suggestedRobot = buildSuggestedRobot(projectDocument.renode, boardId);
  const outputs = projectDocument.generated_fragments.outputs;
  const outputConfig = outputs && typeof outputs === "object" && !Array.isArray(outputs) ? outputs as Record<string, unknown> : {};
  const overlayFileName = typeof outputConfig.overlay === "string" && outputConfig.overlay.trim() ? outputConfig.overlay.trim() : `${boardId}.overlay`;
  const configFileName = typeof outputConfig.config === "string" && outputConfig.config.trim() ? outputConfig.config.trim() : `${boardId}.conf`;
  const overlayFreshness = buildArtifactFreshness({
    content: projectDocument.generated_overlay,
    baselineContent: seededOverlay,
    editable: true,
    sourceKind: "editable-project-asset",
  });
  const configFreshness = buildArtifactFreshness({
    content: projectDocument.generated_conf,
    baselineContent: seededConfig,
    editable: true,
    sourceKind: "editable-project-asset",
  });
  const fragmentsContent = formatGeneratedFragments(projectDocument.generated_fragments);
  const fragmentsFreshness = buildArtifactFreshness({
    content: fragmentsContent,
    baselineContent: seededFragments,
    editable: false,
    sourceKind: "derived-output",
  });
  const headerFreshness = buildArtifactFreshness({
    content: generatedHeader,
    baselineContent: "",
    editable: false,
    sourceKind: "derived-output",
  });
  const sourceFreshness = buildArtifactFreshness({
    content: generatedSource,
    baselineContent: "",
    editable: false,
    sourceKind: "derived-output",
  });
  const rescFreshness = buildArtifactFreshness({
    content: projectDocument.renode.resc,
    baselineContent: suggestedResc,
    editable: true,
    sourceKind: "editable-project-asset",
  });
  const robotFreshness = buildArtifactFreshness({
    content: projectDocument.renode.robot,
    baselineContent: suggestedRobot,
    editable: true,
    sourceKind: "editable-project-asset",
  });

  return [
    {
      id: "overlay",
      panelId: "workspace-generated-overlay",
      title: "Generated Overlay",
      fileName: overlayFileName,
      language: "dts",
      content: projectDocument.generated_overlay,
      baselineContent: seededOverlay,
      editable: true,
      sourceKind: "editable-project-asset",
      ownerLabel: "Saved project artifact",
      description: "Editable overlay text stored in the canonical project document.",
      ...overlayFreshness,
      exportSummary: buildArtifactExportSummary("overlay", overlayFileName),
      markers: buildOverlayMarkers(projectDocument.generated_overlay, unresolvedPinCount),
    },
    {
      id: "config",
      panelId: "workspace-generated-config",
      title: "Generated Config",
      fileName: configFileName,
      language: "ini",
      content: projectDocument.generated_conf,
      baselineContent: seededConfig,
      editable: true,
      sourceKind: "editable-project-asset",
      ownerLabel: "Saved project artifact",
      description: "Editable prj.conf output stored in the canonical project document.",
      ...configFreshness,
      exportSummary: buildArtifactExportSummary("config", configFileName),
      markers: buildConfigMarkers(projectDocument.generated_conf, projectDocument.protocol_editor.entries.filter((entry) => entry.enabled !== false).length),
    },
    {
      id: "fragments",
      panelId: "workspace-generated-fragments",
      title: "Generated Fragments",
      fileName: `${boardId}.fragments.json`,
      language: "json",
      content: fragmentsContent,
      baselineContent: seededFragments,
      editable: false,
      sourceKind: "derived-output",
      ownerLabel: "Structured generated metadata",
      description: "Machine-readable generation metadata stays read-only and authoritative.",
      ...fragmentsFreshness,
      exportSummary: buildArtifactExportSummary("fragments", `${boardId}.fragments.json`),
      markers: buildFragmentMarkers(fragmentsContent),
    },
    {
      id: "header",
      panelId: "workspace-generated-header",
      title: "Generated Header",
      fileName: `${boardId}_protocols.generated.h`,
      language: "c",
      content: generatedHeader,
      baselineContent: "",
      editable: false,
      sourceKind: "derived-output",
      ownerLabel: "Derived protocol preview",
      description: "Header preview derived from the enabled protocol entries.",
      ...headerFreshness,
      exportSummary: buildArtifactExportSummary("header", `${boardId}_protocols.generated.h`),
      markers: buildProtocolMarkers(generatedHeader, "Generated header"),
    },
    {
      id: "source",
      panelId: "workspace-generated-source",
      title: "Generated Source",
      fileName: `${boardId}_protocols.generated.c`,
      language: "c",
      content: generatedSource,
      baselineContent: "",
      editable: false,
      sourceKind: "derived-output",
      ownerLabel: "Derived protocol preview",
      description: "Source preview derived from the enabled protocol entries.",
      ...sourceFreshness,
      exportSummary: buildArtifactExportSummary("source", `${boardId}_protocols.generated.c`),
      markers: buildProtocolMarkers(generatedSource, "Generated source"),
    },
    {
      id: "resc",
      panelId: "workspace-renode-resc",
      title: "Renode RESC",
      fileName: `${boardId}.resc`,
      language: "plaintext",
      content: projectDocument.renode.resc,
      baselineContent: suggestedResc,
      editable: true,
      sourceKind: "editable-project-asset",
      ownerLabel: "Editable simulation source",
      description: "Editable RESC script stored on the Renode profile.",
      ...rescFreshness,
      exportSummary: buildArtifactExportSummary("resc", `${boardId}.resc`),
      markers: buildRescMarkers(projectDocument.renode.resc, projectDocument.renode.enabled),
    },
    {
      id: "robot",
      panelId: "workspace-renode-robot",
      title: "Robot Tests",
      fileName: `${boardId}.robot`,
      language: "plaintext",
      content: projectDocument.renode.robot,
      baselineContent: suggestedRobot,
      editable: true,
      sourceKind: "editable-project-asset",
      ownerLabel: "Editable simulation source",
      description: "Editable Robot smoke-test script stored on the Renode profile.",
      ...robotFreshness,
      exportSummary: buildArtifactExportSummary("robot", `${boardId}.robot`),
      markers: buildRobotMarkers(projectDocument.renode.robot, projectDocument.renode.robot_target),
    },
  ];
}

export function buildArtifactDiagnosticEntries(documents: ArtifactReviewDocument[]): ArtifactDiagnosticEntry[] {
  return documents.flatMap((document) =>
    document.markers.map((marker, index) => ({
      id: `${document.id}:${index}`,
      summary: `${document.title}: ${marker.message}`,
      detail: `${document.fileName} · line ${marker.lineNumber}`,
      severity: marker.severity === 8 ? "error" : marker.severity === 4 ? "warning" : marker.severity === 2 ? "info" : "success",
      navigation: {
        panelId: document.panelId,
        lineNumber: marker.lineNumber,
        column: marker.column,
        label: document.title,
      },
    })),
  );
}