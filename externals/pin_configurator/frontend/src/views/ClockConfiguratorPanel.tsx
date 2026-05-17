import { useMemo } from "react";
import Editor from "@monaco-editor/react";
import { DiagnosticBadge } from "../shared/ui/feedback/DiagnosticBadge";
import { EmptyState } from "../shared/ui/feedback/EmptyState";
import { InspectorNotice } from "../shared/ui/inspectors/InspectorNotice";
import { InspectorSection } from "../shared/ui/inspectors/InspectorSection";
import { PropertyGrid, PropertyRow } from "../shared/ui/inspectors/PropertyGrid";
import { SceneViewportToolbar } from "../shared/ui/scene/SceneViewportToolbar";
import { useSceneViewport } from "../shared/ui/scene/useSceneViewport";
import type { ClockConfiguratorPresenter } from "../domains/clock/clockConfiguratorPresenter";

interface ClockConfiguratorPanelProps {
  presenter: ClockConfiguratorPresenter;
}

function formatFrequency(hz: number) {
  if (!hz) {
    return "OFF";
  }
  if (hz >= 1_000_000) {
    return `${(hz / 1_000_000).toFixed(2)} MHz`;
  }
  if (hz >= 1_000) {
    return `${(hz / 1_000).toFixed(2)} kHz`;
  }
  return `${hz} Hz`;
}

const laneOrder = ["source", "pll", "mux", "divider", "output"] as const;

interface ClockSceneNode {
  id: string;
  label: string;
  type: string;
  icon: string;
  frequencyHz: number;
  lane: string;
  x: number;
  y: number;
  width: number;
  height: number;
  warning: boolean;
}

function laneForType(type: string) {
  return laneOrder.includes(type as (typeof laneOrder)[number]) ? type : "output";
}

function warningMatchesNode(nodeId: string, warning: string) {
  return warning.toLowerCase().includes(nodeId.toLowerCase().replace(/[_-]/g, ""));
}

export function ClockConfiguratorPanel({ presenter }: ClockConfiguratorPanelProps) {
  const selectedNode = presenter.selectedNode;
  const viewport = useSceneViewport({ fitZoom: 0.9 });
  const sceneNodes = useMemo<ClockSceneNode[]>(() => {
    const lanes = laneOrder.map((lane) => ({
      lane,
      items: presenter.nodes.filter((node) => laneForType(node.type) === lane),
    })).filter((lane) => lane.items.length);

    return lanes.flatMap((lane, laneIndex) => {
      return lane.items.map((node, rowIndex) => ({
        id: node.id,
        label: node.name,
        type: node.type,
        icon: node.icon,
        frequencyHz: node.frequencyHz,
        lane: lane.lane,
        x: 70 + laneIndex * 190,
        y: 70 + rowIndex * 112,
        width: 150,
        height: 76,
        warning: presenter.warnings.some((warning) => warningMatchesNode(node.id, warning) || warningMatchesNode(node.name, warning)),
      }));
    });
  }, [presenter.nodes, presenter.warnings]);
  const sceneLanes = useMemo(() => {
    return laneOrder
      .map((lane) => ({
        lane,
        nodes: sceneNodes.filter((node) => node.lane === lane),
      }))
      .filter((entry) => entry.nodes.length);
  }, [sceneNodes]);
  const sceneLinks = useMemo(() => {
    const links: Array<{ id: string; x1: number; y1: number; x2: number; y2: number }> = [];
    sceneLanes.forEach((lane, index) => {
      const nextLane = sceneLanes[index + 1];
      if (!nextLane) {
        return;
      }

      lane.nodes.forEach((node, nodeIndex) => {
        const target = nextLane.nodes[Math.min(nodeIndex, nextLane.nodes.length - 1)];
        if (!target) {
          return;
        }

        links.push({
          id: `${node.id}:${target.id}`,
          x1: node.x + node.width,
          y1: node.y + node.height / 2,
          x2: target.x,
          y2: target.y + target.height / 2,
        });
      });
    });
    return links;
  }, [sceneLanes]);
  const generatedArtifactCount = [presenter.generatedOverlay, presenter.generatedConf].filter((value) => value.trim().length > 0).length;
  const activeNodeCount = sceneNodes.filter((node) => node.frequencyHz > 0).length;
  const selectedNodeWarnings = useMemo(() => {
    if (!selectedNode) {
      return [] as string[];
    }

    return presenter.warnings.filter((warning) => warningMatchesNode(selectedNode.id, warning) || warningMatchesNode(selectedNode.name, warning));
  }, [presenter.warnings, selectedNode]);
  const derivedFrequencyPreview = useMemo(
    () => Object.entries(presenter.frequencies).slice(0, 4).map(([key, value]) => `${key}: ${formatFrequency(value)}`),
    [presenter.frequencies],
  );

  return (
    <div className="domain-panel domain-panel--split">
      <InspectorSection
        title="Clock readiness"
        summary="Review active-node coverage, warnings, and generated artifact status here before editing node properties or exporting clock outputs."
        actions={<DiagnosticBadge label={`${presenter.warnings.length} warnings`} tone={presenter.warnings.length ? "warning" : "success"} />}
      >
        <PropertyGrid>
          <PropertyRow label="Trees" value={presenter.availableTrees.length} />
          <PropertyRow label="Active nodes" value={activeNodeCount} />
          <PropertyRow label="Warnings" value={presenter.warnings.length} />
          <PropertyRow label="Generated outputs" value={generatedArtifactCount} />
        </PropertyGrid>
        <InspectorNotice
          title={presenter.warnings.length ? "Clock blockers stay above editing" : "Clock workflow is ready for editing"}
          detail={presenter.warnings.length
            ? "Resolve clock warnings before treating generated overlay and config output as final."
            : "Edit node properties below while keeping the generated overlay and config outputs in a separate derived section."}
          tone={presenter.warnings.length ? "warning" : "info"}
        />
        {presenter.warnings.length ? (
          <div className="pin-assignments-panel__issues" aria-label="Clock readiness warnings">
            {presenter.warnings.slice(0, 3).map((warning) => (
              <div key={warning} className="pin-assignments-panel__issue pin-assignments-panel__issue--compact">
                <strong>Clock warning</strong>
                <span>{warning}</span>
              </div>
            ))}
          </div>
        ) : null}
      </InspectorSection>

      <InspectorSection
        title="Clock editing loop"
        summary="Keep tree context, derived frequencies, and current warnings visible while you edit the selected node."
        actions={<DiagnosticBadge label={selectedNode ? formatFrequency(selectedNode.frequencyHz) : "No node"} tone={selectedNode ? "info" : "warning"} />}
      >
        <PropertyGrid>
          <PropertyRow label="Current tree" value={presenter.currentTree?.name ?? "None"} />
          <PropertyRow label="Selected node" value={selectedNode ? `${selectedNode.icon} ${selectedNode.name}` : "None"} />
          <PropertyRow label="Derived frequency" value={selectedNode ? formatFrequency(selectedNode.frequencyHz) : "Pending selection"} />
          <PropertyRow label="Node warnings" value={selectedNodeWarnings.length} />
        </PropertyGrid>
        <InspectorNotice
          title={selectedNodeWarnings.length ? "Selected node still has warning context" : "Tree context stays visible while editing"}
          detail={selectedNodeWarnings.length
            ? selectedNodeWarnings.join(" ")
            : "The current tree, selected node frequency, and generated artifact counts stay visible here so you do not have to switch back to the scene while editing properties."}
          tone={selectedNodeWarnings.length ? "warning" : "info"}
        />
        <div className="pin-assignments-panel__issues" aria-label="Clock derived frequencies">
          {derivedFrequencyPreview.map((entry) => (
            <div key={entry} className="domain-list__item">
              <strong>Derived frequency</strong>
              <span>{entry}</span>
            </div>
          ))}
        </div>
      </InspectorSection>

      <InspectorSection
        title="Clock scene"
        summary="Inspect the lane-grouped tree here, then move to the detail editor and generated outputs below for the selected node." 
        actions={<DiagnosticBadge label={`${presenter.availableTrees.length} trees`} tone="info" />}
      >
        <div className="catalog-toolbar">
          <label className="project-flow__field">
            <span>Clock tree</span>
            <select value={presenter.currentTree?.id || ""} onChange={(event) => presenter.selectTree(event.target.value)}>
              {presenter.availableTrees.map((tree) => (
                <option key={tree.id} value={tree.id}>{tree.name}</option>
              ))}
            </select>
          </label>
          <button type="button" className="shell-button" onClick={presenter.generateConfig} disabled={!presenter.currentTree}>
            Generate Clock Config
          </button>
        </div>
        <p className="domain-summary-text">{presenter.status}</p>
        {presenter.error ? <EmptyState title="Clock tree unavailable" detail={presenter.error} tone="error" compact /> : null}
        {!presenter.error && !presenter.nodes.length ? <EmptyState title="No active clock tree" detail="Select a tree to inspect nodes, computed frequencies, and generated output." compact /> : null}
        {presenter.nodes.length ? (
          <div className="clock-scene">
            <SceneViewportToolbar zoom={viewport.zoom} onZoomOut={viewport.zoomOut} onZoomIn={viewport.zoomIn} onFit={viewport.fit} onReset={viewport.reset}>
              <span className="domain-summary-text">Live frequency propagation drives node coloring; warnings surface directly on the scene.</span>
            </SceneViewportToolbar>
            <svg
              className={viewport.isDragging ? "clock-scene__svg clock-scene__svg--dragging" : "clock-scene__svg"}
              aria-label="Clock tree scene"
              viewBox="0 0 980 480"
              onMouseDown={(event) => viewport.beginPan(event.clientX, event.clientY)}
              onMouseMove={(event) => viewport.movePan(event.clientX, event.clientY)}
              onMouseUp={viewport.endPan}
              onMouseLeave={viewport.endPan}
            >
              <rect x="24" y="24" width="932" height="432" rx="28" className="clock-scene__backdrop" />
              <g transform={viewport.transform}>
                {sceneLanes.map((lane, laneIndex) => (
                  <g key={lane.lane}>
                    <text x={145 + laneIndex * 190} y="46" textAnchor="middle" className="clock-scene__lane-label">{lane.lane}</text>
                  </g>
                ))}
                {sceneLinks.map((link) => (
                  <path key={link.id} d={`M ${link.x1} ${link.y1} C ${link.x1 + 36} ${link.y1}, ${link.x2 - 36} ${link.y2}, ${link.x2} ${link.y2}`} className="clock-scene__wire" />
                ))}
                {sceneNodes.map((node) => {
                  const active = presenter.selectedNodeId === node.id;
                  const off = node.frequencyHz <= 0;
                  return (
                    <g
                      key={node.id}
                      className={[
                        "clock-scene__node",
                        active ? "clock-scene__node--selected" : "",
                        off ? "clock-scene__node--off" : "",
                        node.warning ? "clock-scene__node--warning" : "",
                      ].filter(Boolean).join(" ")}
                      onClick={() => presenter.selectNode(node.id)}
                    >
                      <rect x={node.x} y={node.y} width={node.width} height={node.height} rx="18" />
                      <text x={node.x + 14} y={node.y + 24} className="clock-scene__node-title">{`${node.icon} ${node.label}`}</text>
                      <text x={node.x + 14} y={node.y + 44} className="clock-scene__node-meta">{node.type}</text>
                      <text x={node.x + 14} y={node.y + 63} className="clock-scene__node-frequency">{formatFrequency(node.frequencyHz)}</text>
                    </g>
                  );
                })}
              </g>
            </svg>
            <div className="clock-scene__legend">
              <span className="domain-summary-text">{`${sceneNodes.filter((node) => node.frequencyHz > 0).length} active nodes • ${presenter.warnings.length} warnings`}</span>
            </div>
          </div>
        ) : null}
      </InspectorSection>

      <InspectorSection
        title={selectedNode ? `${selectedNode.icon} ${selectedNode.name}` : "Clock detail"}
        summary={selectedNode ? `${selectedNode.type} node detail` : "Select a node to edit its typed properties while keeping generated clock outputs separate."}
        actions={selectedNode ? <DiagnosticBadge label={formatFrequency(selectedNode.frequencyHz)} tone="info" /> : undefined}
      >
        {!selectedNode ? <EmptyState title="No node selected" detail="Select a clock node to edit its configuration properties." compact /> : null}
        {selectedNode ? (
          <div className="domain-panel">
            <InspectorNotice
              title="Editable node values stay here"
              detail="Computed frequency and generated overlay/config outputs are derived from this node. Change only the typed properties in this detail section."
              tone="info"
            />
            <div className="protocol-editor-panel__fields">
              {(selectedNode.props ?? []).map((property) => {
                const value = presenter.values[property.key] ?? property.default;
                if (property.type === "bool") {
                  return (
                    <label key={property.key} className="protocol-editor-panel__checkbox">
                      <input type="checkbox" checked={value === true} onChange={(event) => presenter.updateNodeProperty(property.key, event.target.checked)} />
                      <span>{property.label || property.key}</span>
                    </label>
                  );
                }
                if (property.type === "choice") {
                  return (
                    <label key={property.key} className="project-flow__field">
                      <span>{property.label || property.key}</span>
                      <select value={String(value)} onChange={(event) => presenter.updateNodeProperty(property.key, event.target.value)}>
                        {(property.choices ?? []).map((choice) => (
                          <option key={String(choice)} value={String(choice)}>{String(choice)}</option>
                        ))}
                      </select>
                    </label>
                  );
                }
                return (
                  <label key={property.key} className="project-flow__field">
                    <span>{property.label || property.key}</span>
                    <input type={property.type === "int" ? "number" : "text"} value={String(value)} onChange={(event) => presenter.updateNodeProperty(property.key, property.type === "int" ? Number(event.target.value) || 0 : event.target.value)} />
                  </label>
                );
              })}
            </div>
            {selectedNodeWarnings.length ? (
              <div className="pin-assignments-panel__issues">
                {selectedNodeWarnings.map((warning) => (
                  <div key={warning} className="pin-assignments-panel__issue">
                    <strong>Clock warning</strong>
                    <span>{warning}</span>
                  </div>
                ))}
              </div>
            ) : null}
          </div>
        ) : null}
      </InspectorSection>

      <InspectorSection
        title="Generated clock artifacts"
        summary="Overlay and config outputs remain read-only here so generated clock artifacts stay visually separate from editable node values."
        actions={<DiagnosticBadge label={`${generatedArtifactCount} outputs`} tone={generatedArtifactCount ? "info" : "warning"} />}
      >
        <div className="domain-panel domain-panel--split">
          <div className="domain-editor">
            <Editor height="100%" defaultLanguage="dts" theme="light" value={presenter.generatedOverlay} options={{ minimap: { enabled: false }, readOnly: true, fontSize: 13, scrollBeyondLastLine: false }} />
          </div>
          <div className="domain-editor">
            <Editor height="100%" defaultLanguage="ini" theme="light" value={presenter.generatedConf} options={{ minimap: { enabled: false }, readOnly: true, fontSize: 13, scrollBeyondLastLine: false }} />
          </div>
        </div>
      </InspectorSection>
    </div>
  );
}