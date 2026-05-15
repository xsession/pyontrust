import { useEffect, useMemo, useState } from "react";
import Editor from "@monaco-editor/react";
import { DiagnosticBadge } from "../shared/ui/feedback/DiagnosticBadge";
import { EmptyState } from "../shared/ui/feedback/EmptyState";
import { InspectorSection } from "../shared/ui/inspectors/InspectorSection";
import { SceneViewportToolbar } from "../shared/ui/scene/SceneViewportToolbar";
import { useSceneViewport } from "../shared/ui/scene/useSceneViewport";
import { VirtualizedTreeList } from "../shared/ui/virtualized/VirtualizedTreeList";
import type { LvglLayoutPresenter } from "../domains/lvgl/lvglLayoutPresenter";

interface LvglLayoutPanelProps {
  presenter: LvglLayoutPresenter;
}

interface LvglScreenNode {
  id: string;
  name: string;
  type: string;
  x: number;
  y: number;
  w: number;
  h: number;
  text: string;
  styleRefs: string[];
}

interface LvglScreenViewModel {
  id: string;
  name: string;
  text: string;
  w: number;
  h: number;
  bg: string;
  nodes: LvglScreenNode[];
}

interface LvglStyleViewModel {
  id: string;
  name: string;
  values: Record<string, unknown>;
}

type HierarchyRow =
  | { id: string; kind: "screen"; screenId: string; label: string; detail: string; depth: number }
  | { id: string; kind: "node"; screenId: string; nodeId: string; label: string; detail: string; depth: number };

function asRecord(value: unknown): Record<string, unknown> | null {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    return null;
  }
  return value as Record<string, unknown>;
}

function asArray(value: unknown): unknown[] {
  return Array.isArray(value) ? value : [];
}

function asString(value: unknown, fallback: string) {
  return typeof value === "string" && value.trim() ? value : fallback;
}

function asNumber(value: unknown, fallback: number) {
  return typeof value === "number" && Number.isFinite(value) ? value : fallback;
}

export function LvglLayoutPanel({ presenter }: LvglLayoutPanelProps) {
  const viewport = useSceneViewport({ fitZoom: 0.84 });
  const screens = useMemo<LvglScreenViewModel[]>(() => {
    return asArray(presenter.layout["screens"]).flatMap((screen, index) => {
      const record = asRecord(screen);
      if (!record) {
        return [];
      }

      return [{
        id: asString(record["id"], `screen_${index + 1}`),
        name: asString(record["name"], `Screen ${index + 1}`),
        text: asString(record["text"], asString(record["name"], `Screen ${index + 1}`)),
        w: asNumber(record["w"], 320),
        h: asNumber(record["h"], 240),
        bg: asString(record["bg"], "#0f172a"),
        nodes: asArray(record["nodes"]).flatMap((node, nodeIndex) => {
          const nodeRecord = asRecord(node);
          if (!nodeRecord) {
            return [];
          }

          return [{
            id: asString(nodeRecord["id"], `node_${nodeIndex + 1}`),
            name: asString(nodeRecord["name"], `Node ${nodeIndex + 1}`),
            type: asString(nodeRecord["type"], "widget"),
            x: asNumber(nodeRecord["x"], 24 + nodeIndex * 18),
            y: asNumber(nodeRecord["y"], 24 + nodeIndex * 12),
            w: asNumber(nodeRecord["w"], 96),
            h: asNumber(nodeRecord["h"], 40),
            text: asString(nodeRecord["text"], asString(nodeRecord["name"], "Widget")),
            styleRefs: asArray(nodeRecord["styleRefs"]).map((styleRef) => String(styleRef)),
          } satisfies LvglScreenNode];
        }),
      } satisfies LvglScreenViewModel];
    });
  }, [presenter.layout]);
  const styles = useMemo<LvglStyleViewModel[]>(() => {
    return asArray(presenter.layout["sharedStyles"]).flatMap((style, index) => {
      const record = asRecord(style);
      if (!record) {
        return [];
      }

      return [{
        id: asString(record["id"], `style_${index + 1}`),
        name: asString(record["name"], `Style ${index + 1}`),
        values: asRecord(record["values"]) ?? {},
      } satisfies LvglStyleViewModel];
    });
  }, [presenter.layout]);
  const simulationLog = useMemo(() => {
    const simulation = asRecord(presenter.layout["simulation"]);
    return asArray(simulation?.["log"]).map((entry) => String(entry));
  }, [presenter.layout]);
  const validationIssues = useMemo(() => {
    const issues: string[] = [];
    if (!screens.length) {
      issues.push("Layout has no screens.");
    }

    const seenIds = new Set<string>();
    screens.forEach((screen) => {
      if (seenIds.has(screen.id)) {
        issues.push(`Duplicate screen id: ${screen.id}`);
      }
      seenIds.add(screen.id);
      screen.nodes.forEach((node) => {
        if (node.x + node.w > screen.w || node.y + node.h > screen.h) {
          issues.push(`${screen.name}.${node.name} extends beyond the screen bounds.`);
        }
      });
    });

    return issues.length ? issues : ["No validation issues detected."];
  }, [screens]);
  const [selectedScreenId, setSelectedScreenId] = useState("");
  const [selectedNodeId, setSelectedNodeId] = useState("");
  const [collapsedScreenIds, setCollapsedScreenIds] = useState<string[]>([]);

  useEffect(() => {
    if (!screens.length) {
      setSelectedScreenId("");
      setSelectedNodeId("");
      return;
    }

    setSelectedScreenId((current) => (screens.some((screen) => screen.id === current) ? current : screens[0].id));
  }, [screens]);

  const selectedScreen = screens.find((screen) => screen.id === selectedScreenId) ?? screens[0] ?? null;

  useEffect(() => {
    if (!selectedScreen) {
      setSelectedNodeId("");
      return;
    }

    setSelectedNodeId((current) => (selectedScreen.nodes.some((node) => node.id === current) ? current : selectedScreen.nodes[0]?.id ?? ""));
  }, [selectedScreen]);

  const selectedNode = selectedScreen?.nodes.find((node) => node.id === selectedNodeId) ?? null;
  const selectedStyle = styles.find((style) => selectedNode?.styleRefs.includes(style.id)) ?? null;
  const hierarchyRows = useMemo<HierarchyRow[]>(() => {
    return screens.flatMap((screen) => {
      const screenRow: HierarchyRow = {
        id: `screen:${screen.id}`,
        kind: "screen",
        screenId: screen.id,
        label: screen.name,
        detail: `${screen.nodes.length} widgets`,
        depth: 0,
      };
      if (collapsedScreenIds.includes(screen.id)) {
        return [screenRow];
      }

      return [
        screenRow,
        ...screen.nodes.map((node) => ({
          id: `node:${screen.id}:${node.id}`,
          kind: "node" as const,
          screenId: screen.id,
          nodeId: node.id,
          label: node.name,
          detail: node.type,
          depth: 1,
        })),
      ];
    });
  }, [collapsedScreenIds, screens]);

  return (
    <div className="domain-panel">
      <InspectorSection
        title="LVGL layout summary"
        summary="LVGL layout import/export and canonical document mutation are now presenter-owned instead of legacy globals."
        actions={<DiagnosticBadge label={`${presenter.summary.screenCount} screens`} tone="info" />}
      >
        <dl className="shell-key-values shell-key-values--compact">
          <div>
            <dt>Preset</dt>
            <dd>{presenter.summary.preset}</dd>
          </div>
          <div>
            <dt>Screens</dt>
            <dd>{presenter.summary.screenCount}</dd>
          </div>
          <div>
            <dt>Widgets</dt>
            <dd>{presenter.summary.widgetCount}</dd>
          </div>
          <div>
            <dt>Startup screen</dt>
            <dd>{presenter.summary.startupScreenId}</dd>
          </div>
        </dl>
        <div className="catalog-toolbar">
          <label className="project-flow__field">
            <span>Import source</span>
            <select value={presenter.importSourceKind} onChange={(event) => presenter.setImportSourceKind(event.target.value as typeof presenter.importSourceKind)}>
              <option value="json">Pasted JSON</option>
              <option value="zephyr">Zephyr file path</option>
              <option value="display-pdf">Display PDF path</option>
            </select>
          </label>
          <button type="button" className="shell-button" onClick={presenter.importLayout}>
            Import Layout
          </button>
        </div>
        <label className="project-flow__field">
          <span>{presenter.importSourceKind === "json" ? "Source text" : "Source path"}</span>
          <textarea rows={4} value={presenter.importSourceValue} onChange={(event) => presenter.setImportSourceValue(event.target.value)} />
        </label>
        <div className="catalog-toolbar">
          <label className="project-flow__field">
            <span>Export path</span>
            <input type="text" value={presenter.exportFilePath} onChange={(event) => presenter.setExportFilePath(event.target.value)} />
          </label>
          <button type="button" className="shell-button shell-button--ghost" onClick={presenter.exportLayout}>
            Export Layout
          </button>
        </div>
        <p className="domain-summary-text">{presenter.status}</p>
        {presenter.error ? <EmptyState title="LVGL workflow error" detail={presenter.error} tone="error" compact /> : null}
      </InspectorSection>

      <div className="lvgl-workspace">
        <InspectorSection
          title="Stage"
          summary="The stage is now rendered as an SVG workspace with screen selection, hierarchy-linked selection, validation context, and simulation log panels."
          actions={<DiagnosticBadge label={selectedScreen ? `${selectedScreen.w}x${selectedScreen.h}` : "No screen"} tone="info" />}
        >
          {!screens.length ? <EmptyState title="No screens" detail="Import or paste a layout with screens to render the stage." compact /> : null}
          {screens.length ? (
            <div className="lvgl-stage">
              <div className="catalog-toolbar">
                <label className="project-flow__field">
                  <span>Screen</span>
                  <select value={selectedScreen?.id ?? ""} onChange={(event) => setSelectedScreenId(event.target.value)}>
                    {screens.map((screen) => (
                      <option key={screen.id} value={screen.id}>{screen.name}</option>
                    ))}
                  </select>
                </label>
              </div>
              <SceneViewportToolbar zoom={viewport.zoom} onZoomOut={viewport.zoomOut} onZoomIn={viewport.zoomIn} onFit={viewport.fit} onReset={viewport.reset}>
                <span className="domain-summary-text">Stage selection stays coordinated with hierarchy, props, and style panels.</span>
              </SceneViewportToolbar>
              <svg
                className={viewport.isDragging ? "lvgl-stage__svg lvgl-stage__svg--dragging" : "lvgl-stage__svg"}
                viewBox="0 0 960 560"
                aria-label="LVGL stage"
                role="img"
                onMouseDown={(event) => viewport.beginPan(event.clientX, event.clientY)}
                onMouseMove={(event) => viewport.movePan(event.clientX, event.clientY)}
                onMouseUp={viewport.endPan}
                onMouseLeave={viewport.endPan}
              >
                <rect x="24" y="24" width="912" height="512" rx="28" className="lvgl-stage__backdrop" />
                {selectedScreen ? (
                  <g transform={viewport.transform}>
                    <rect x="180" y="92" width={selectedScreen.w} height={selectedScreen.h} rx="24" fill={selectedScreen.bg} className="lvgl-stage__screen" />
                    <text x="196" y="118" className="lvgl-stage__screen-label">{selectedScreen.text}</text>
                    {selectedScreen.nodes.map((node) => {
                      const selected = selectedNode?.id === node.id;
                      return (
                        <g key={node.id} className={selected ? "lvgl-stage__node lvgl-stage__node--selected" : "lvgl-stage__node"} onClick={() => setSelectedNodeId(node.id)}>
                          <rect x={180 + node.x} y={92 + node.y} width={Math.max(node.w, 40)} height={Math.max(node.h, 24)} rx="14" />
                          <text x={192 + node.x} y={114 + node.y} className="lvgl-stage__node-title">{node.name}</text>
                          <text x={192 + node.x} y={130 + node.y} className="lvgl-stage__node-meta">{node.type}</text>
                        </g>
                      );
                    })}
                  </g>
                ) : null}
              </svg>
            </div>
          ) : null}
        </InspectorSection>
                role="img"

        <InspectorSection title="Hierarchy" summary="Screens and widgets are now browseable as a coordinated hierarchy rather than only raw JSON.">
          {!screens.length ? <EmptyState title="No hierarchy" detail="Screens appear here once the layout contains scene nodes." compact /> : null}
          {screens.length ? (
            <VirtualizedTreeList
              ariaLabel="LVGL hierarchy"
              sections={[{ id: "hierarchy", label: "Layout hierarchy", items: hierarchyRows, meta: `${hierarchyRows.length} rows` }]}
              getItemId={(row) => row.id}
              getItemDepth={(row) => row.depth}
              estimatedRowHeight={84}
              overscan={5}
              viewportClassName="domain-list-viewport"
              showSectionHeaders={false}
              renderItem={({ item: row }) => {
                if (row.kind === "screen") {
                  const collapsed = collapsedScreenIds.includes(row.screenId);
                  return (
                    <div className={row.screenId === selectedScreen?.id ? "domain-list__item domain-list__item--selected" : "domain-list__item"}>
                      <div className="domain-list__header domain-list__header--compact">
                        <button type="button" className="domain-list__select" onClick={() => setSelectedScreenId(row.screenId)}>
                          <strong>{row.label}</strong>
                          <span>{row.detail}</span>
                        </button>
                        <button
                          type="button"
                          className="shell-button shell-button--ghost"
                          onClick={() => setCollapsedScreenIds((current) => (collapsed ? current.filter((entry) => entry !== row.screenId) : [...current, row.screenId]))}
                        >
                          {collapsed ? "Expand" : "Collapse"}
                        </button>
                      </div>
                    </div>
                  );
                }

                return (
                  <div className={row.nodeId === selectedNode?.id ? "domain-list__item domain-list__item--selected" : "domain-list__item"}>
                    <button type="button" className="domain-list__select" onClick={() => {
                      setSelectedScreenId(row.screenId);
                      setSelectedNodeId(row.nodeId);
                    }}>
                      <strong>{row.label}</strong>
                      <span>{row.detail}</span>
                    </button>
                  </div>
                );
              }}
            />
          ) : null}
        </InspectorSection>

        <InspectorSection title="Props" summary="Selection-aware properties and style references are available next to the stage.">
          {!selectedNode ? <EmptyState title="No widget selected" detail="Select a widget from the stage or hierarchy to inspect its bounds and styles." compact /> : null}
          {selectedNode ? (
            <dl className="shell-key-values shell-key-values--compact">
              <div><dt>Name</dt><dd>{selectedNode.name}</dd></div>
              <div><dt>Type</dt><dd>{selectedNode.type}</dd></div>
              <div><dt>Bounds</dt><dd>{`${selectedNode.x}, ${selectedNode.y}, ${selectedNode.w}x${selectedNode.h}`}</dd></div>
              <div><dt>Styles</dt><dd>{selectedNode.styleRefs.length ? selectedNode.styleRefs.join(", ") : "None"}</dd></div>
              <div><dt>Selected Style</dt><dd>{selectedStyle?.name ?? "None"}</dd></div>
            </dl>
          ) : null}
        </InspectorSection>

        <InspectorSection title="Style library" summary="Shared styles are visible beside the stage so style references are inspectable without dropping to JSON.">
          {!styles.length ? <EmptyState title="No shared styles" detail="Import or add shared styles to populate the library." compact /> : null}
          {styles.length ? (
            <ul className="domain-list">
              {styles.map((style) => (
                <li key={style.id} className={style.id === selectedStyle?.id ? "domain-list__item domain-list__item--selected" : "domain-list__item"}>
                  <strong>{style.name}</strong>
                  <span>{Object.keys(style.values).length ? Object.keys(style.values).join(", ") : "No style properties"}</span>
                </li>
              ))}
            </ul>
          ) : null}
        </InspectorSection>

        <InspectorSection title="Validation" summary="Basic layout validation and simulation log output now sit in dedicated companion panels.">
          <div className="pin-assignments-panel__issues">
            {validationIssues.map((issue) => (
              <div key={issue} className={issue === "No validation issues detected." ? "domain-list__item" : "pin-assignments-panel__issue"}>
                <strong>{issue === "No validation issues detected." ? "Validation" : "Issue"}</strong>
                <span>{issue}</span>
              </div>
            ))}
          </div>
        </InspectorSection>

        <InspectorSection title="Simulation log" summary="Legacy simulation state is now surfaced beside the stage instead of hidden behind the old tab layout.">
          {!simulationLog.length ? <EmptyState title="No simulation log" detail="Simulation log entries appear here when the layout carries simulation state." compact /> : null}
          {simulationLog.length ? (
            <ul className="domain-list">
              {simulationLog.map((entry, index) => (
                <li key={`${entry}-${index}`} className="domain-list__item">
                  <span>{entry}</span>
                </li>
              ))}
            </ul>
          ) : null}
        </InspectorSection>
      </div>

      <InspectorSection
        title="LVGL layout JSON"
        summary="The current layout stays editable as structured JSON so the canonical project document can be updated without legacy scene globals."
      >
        <div className="domain-editor">
          <Editor height="100%" defaultLanguage="json" theme="light" value={presenter.draftText} onChange={(value) => presenter.setDraftText(value ?? "")} options={{ minimap: { enabled: false }, fontSize: 13, scrollBeyondLastLine: false }} />
        </div>
        <div className="domain-list__header domain-list__header--compact">
          <span className="domain-summary-text">Apply JSON to the canonical project document after validating the edited layout payload.</span>
          <button type="button" className="shell-button" onClick={presenter.applyDraftText}>
            Apply JSON
          </button>
        </div>
      </InspectorSection>
    </div>
  );
}