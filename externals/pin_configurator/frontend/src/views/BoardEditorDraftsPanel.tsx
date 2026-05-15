import { useMemo, useState } from "react";
import Editor from "@monaco-editor/react";
import { DiagnosticBadge } from "../shared/ui/feedback/DiagnosticBadge";
import { EmptyState } from "../shared/ui/feedback/EmptyState";
import { InspectorSection } from "../shared/ui/inspectors/InspectorSection";
import { SceneViewportToolbar } from "../shared/ui/scene/SceneViewportToolbar";
import { useSceneViewport } from "../shared/ui/scene/useSceneViewport";
import type { BoardEditorPresenter } from "../domains/board-editor/boardEditorPresenter";

interface BoardEditorDraftsPanelProps {
  presenter: BoardEditorPresenter;
}

function safeParseBoardDraft(text: string): Record<string, unknown> | null {
  try {
    const parsed: unknown = JSON.parse(text || "{}");
    if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
      return null;
    }
    return parsed as Record<string, unknown>;
  } catch {
    return null;
  }
}

function arrayOfRecords(value: unknown): Record<string, unknown>[] {
  return Array.isArray(value)
    ? value.flatMap((entry) => (entry && typeof entry === "object" && !Array.isArray(entry) ? [entry as Record<string, unknown>] : []))
    : [];
}

function safeString(value: unknown, fallback: string) {
  return typeof value === "string" && value.trim() ? value : fallback;
}

export function BoardEditorDraftsPanel({ presenter }: BoardEditorDraftsPanelProps) {
  const viewport = useSceneViewport({ fitZoom: 0.82 });
  const [visibleLayers, setVisibleLayers] = useState({ package: true, pins: true, devices: true, buses: true, annotations: true });
  const parsedDraft = useMemo(() => safeParseBoardDraft(presenter.draftText), [presenter.draftText]);
  const pins = useMemo(() => arrayOfRecords(parsedDraft?.["pins"]), [parsedDraft]);
  const devices = useMemo(() => arrayOfRecords(parsedDraft?.["external_devices"]), [parsedDraft]);
  const packageName = typeof parsedDraft?.["package"] === "string" ? parsedDraft["package"] : "Package";
  const boardName = typeof parsedDraft?.["board"] === "string" ? parsedDraft["board"] : "Board draft";
  const packageLayout = useMemo(() => {
    const topCount = Math.ceil(Math.max(pins.length, 1) / 4);
    const rightCount = Math.ceil((pins.length - topCount) / 3);
    const bottomCount = Math.ceil((pins.length - topCount - rightCount) / 2);
    const leftCount = Math.max(pins.length - topCount - rightCount - bottomCount, 0);
    return pins.map((pin, index) => {
      const pinNumber = typeof pin["number"] === "number" ? String(pin["number"]) : safeString(pin["number"], String(index + 1));
      const pinName = safeString(pin["name"], `P${pinNumber}`);
      if (index < topCount) {
        const step = 320 / Math.max(topCount, 1);
        return { pinNumber, pinName, x: 220 + index * step, y: 102 };
      }
      if (index < topCount + rightCount) {
        const slot = index - topCount;
        const step = 220 / Math.max(rightCount, 1);
        return { pinNumber, pinName, x: 548, y: 148 + slot * step };
      }
      if (index < topCount + rightCount + bottomCount) {
        const slot = index - topCount - rightCount;
        const step = 320 / Math.max(bottomCount, 1);
        return { pinNumber, pinName, x: 540 - slot * step, y: 380 };
      }
      const slot = index - topCount - rightCount - bottomCount;
      const step = 220 / Math.max(leftCount, 1);
      return { pinNumber, pinName, x: 188, y: 362 - slot * step };
    });
  }, [pins]);
  const deviceLayout = useMemo(() => {
    return devices.map((device, index) => ({
      id: safeString(device["id"], `device_${index + 1}`),
      label: safeString(device["display"], safeString(device["name"], `Device ${index + 1}`)),
      bus: safeString(device["bus"], "bus"),
      x: 650,
      y: 120 + index * 96,
    }));
  }, [devices]);

  return (
    <div className="domain-panel domain-panel--split">
      <InspectorSection
        title="Board-editor drafts"
        summary="Draft discovery, load, save, and delete now flow through typed presenter actions instead of the legacy board-editor runtime globals."
        actions={<DiagnosticBadge label={`${presenter.drafts.length} drafts`} tone="info" />}
      >
        <div className="domain-list__header domain-list__header--compact">
          <span className="domain-summary-text">{presenter.status}</span>
          <button type="button" className="shell-button" onClick={presenter.refreshDrafts}>
            Refresh Drafts
          </button>
        </div>
        <label className="project-flow__field">
          <span>Draft filename</span>
          <input type="text" value={presenter.draftFilename} onChange={(event) => presenter.setDraftFilename(event.target.value)} placeholder="demo_board.json" />
        </label>
        <div className="domain-list__header domain-list__header--compact">
          <button type="button" className="shell-button" onClick={presenter.seedFromActiveBoard}>
            Seed From Active Board
          </button>
          <button type="button" className="shell-button shell-button--ghost" onClick={presenter.saveDraft}>
            Save Draft
          </button>
        </div>
        {presenter.error ? <EmptyState title="Board-editor workflow error" detail={presenter.error} tone="error" compact /> : null}
        {!presenter.error && !presenter.drafts.length ? <EmptyState title="No saved drafts" detail="Seed from the active board or save JSON into a new board-editor draft." compact /> : null}
        {presenter.drafts.length ? (
          <ul className="domain-list">
            {presenter.drafts.map((draft) => (
              <li key={draft.filename} className="domain-list__item">
                <div className="domain-list__header">
                  <button type="button" className="domain-list__select" onClick={() => presenter.loadDraft(draft.filename)}>
                    <strong>{draft.filename}</strong>
                    <span>{`${draft.size} bytes • ${draft.updatedAt}`}</span>
                  </button>
                  <button type="button" className="shell-button shell-button--ghost" onClick={() => presenter.deleteDraft(draft.filename)}>
                    Delete
                  </button>
                </div>
              </li>
            ))}
          </ul>
        ) : null}
      </InspectorSection>

      <InspectorSection
        title="Board scene"
        summary="Package, pins, external devices, buses, and annotations now render as a layered SVG workbench beside the JSON editor."
      >
        {!presenter.draftText ? <EmptyState title="No draft loaded" detail="Load an existing draft or seed one from the active board to edit its JSON payload." compact /> : null}
        {presenter.draftText ? (
          <div className="board-scene">
            <SceneViewportToolbar zoom={viewport.zoom} onZoomOut={viewport.zoomOut} onZoomIn={viewport.zoomIn} onFit={viewport.fit} onReset={viewport.reset}>
              <label className="domain-toggle"><input type="checkbox" checked={visibleLayers.package} onChange={() => setVisibleLayers((current) => ({ ...current, package: !current.package }))} /><span>Package</span></label>
              <label className="domain-toggle"><input type="checkbox" checked={visibleLayers.pins} onChange={() => setVisibleLayers((current) => ({ ...current, pins: !current.pins }))} /><span>Pins</span></label>
              <label className="domain-toggle"><input type="checkbox" checked={visibleLayers.devices} onChange={() => setVisibleLayers((current) => ({ ...current, devices: !current.devices }))} /><span>Devices</span></label>
              <label className="domain-toggle"><input type="checkbox" checked={visibleLayers.buses} onChange={() => setVisibleLayers((current) => ({ ...current, buses: !current.buses }))} /><span>Buses</span></label>
              <label className="domain-toggle"><input type="checkbox" checked={visibleLayers.annotations} onChange={() => setVisibleLayers((current) => ({ ...current, annotations: !current.annotations }))} /><span>Annotations</span></label>
            </SceneViewportToolbar>
            <svg
              className={viewport.isDragging ? "board-scene__svg board-scene__svg--dragging" : "board-scene__svg"}
              viewBox="0 0 960 560"
              aria-label="Board editor scene"
              role="img"
              onMouseDown={(event) => viewport.beginPan(event.clientX, event.clientY)}
              onMouseMove={(event) => viewport.movePan(event.clientX, event.clientY)}
              onMouseUp={viewport.endPan}
              onMouseLeave={viewport.endPan}
            >
              <rect x="24" y="24" width="912" height="512" rx="28" className="board-scene__backdrop" />
              <g transform={viewport.transform}>
                {visibleLayers.package ? <rect x="220" y="120" width="320" height="240" rx="28" className="board-scene__package" /> : null}
                {visibleLayers.annotations ? <text x="240" y="150" className="board-scene__package-label">{`${boardName} • ${packageName}`}</text> : null}
                {visibleLayers.pins ? packageLayout.map((pin) => (
                  <g key={pin.pinNumber} className="board-scene__pin">
                    <circle cx={pin.x} cy={pin.y} r="12" />
                    <text x={pin.x + 18} y={pin.y + 4}>{`${pin.pinNumber} ${pin.pinName}`}</text>
                  </g>
                )) : null}
                {visibleLayers.devices ? deviceLayout.map((device) => (
                  <g key={device.id} className="board-scene__device">
                    <rect x={device.x} y={device.y} width="170" height="62" rx="16" />
                    <text x={device.x + 14} y={device.y + 24}>{device.label}</text>
                    <text x={device.x + 14} y={device.y + 42}>{device.bus}</text>
                  </g>
                )) : null}
                {visibleLayers.buses ? deviceLayout.map((device, index) => {
                  const pin = packageLayout[index % Math.max(packageLayout.length, 1)];
                  if (!pin) {
                    return null;
                  }
                  return <path key={`${device.id}:bus`} d={`M ${pin.x} ${pin.y} C ${pin.x + 140} ${pin.y}, ${device.x - 40} ${device.y + 30}, ${device.x} ${device.y + 30}`} className="board-scene__bus" />;
                }) : null}
                {visibleLayers.annotations ? (
                  <text x="650" y="104" className="board-scene__annotation">External devices</text>
                ) : null}
              </g>
            </svg>
            <div className="domain-editor">
              <Editor height="100%" defaultLanguage="json" theme="light" value={presenter.draftText} onChange={(value) => presenter.setDraftText(value ?? "")} options={{ minimap: { enabled: false }, fontSize: 13, scrollBeyondLastLine: false }} />
            </div>
          </div>
        ) : null}
      </InspectorSection>
    </div>
  );
}