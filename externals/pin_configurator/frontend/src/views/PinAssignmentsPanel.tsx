import { useEffect, useMemo, useState } from "react";
import { ContextMenu } from "../shared/ui/commands/ContextMenu";
import { ShortcutHint } from "../shared/ui/commands/ShortcutHint";
import { DiagnosticBadge } from "../shared/ui/feedback/DiagnosticBadge";
import { EmptyState } from "../shared/ui/feedback/EmptyState";
import { InspectorNotice } from "../shared/ui/inspectors/InspectorNotice";
import { InspectorSection } from "../shared/ui/inspectors/InspectorSection";
import { PropertyGrid, PropertyRow } from "../shared/ui/inspectors/PropertyGrid";
import { SceneViewportToolbar } from "../shared/ui/scene/SceneViewportToolbar";
import { useSceneViewport } from "../shared/ui/scene/useSceneViewport";
import type { PinAssignmentAltFunctionOptionViewModel, PinAssignmentsViewModel } from "../shared/viewModels/pinAssignments";

interface PinAssignmentsPanelProps {
  pinAssignments: PinAssignmentsViewModel;
  onClearPinAssignment: (pinNumber: string) => void;
  onAssignPinAltFunction: (pinNumber: string, option: PinAssignmentAltFunctionOptionViewModel) => void;
  onUpdatePinBooleanProperty: (pinNumber: string, propertyKey: string, value: boolean) => void;
}

type PinAssignmentFilter = "all" | "resolved" | "unresolved";

const pinBooleanProperties = [
  { key: "bias_pull_up", label: "Pull-up" },
  { key: "bias_pull_down", label: "Pull-down" },
  { key: "drive_open_drain", label: "Open-drain" },
  { key: "input_enable", label: "Input enable" },
] as const;

interface PackagePinLayout {
  pinNumber: string;
  x: number;
  y: number;
  width: number;
  height: number;
  side: "top" | "right" | "bottom" | "left";
}

function buildPackageLayout(pinNumbers: string[]): PackagePinLayout[] {
  const sorted = [...pinNumbers].sort((left, right) => Number(left) - Number(right));
  const total = Math.max(sorted.length, 1);
  const topCount = Math.ceil(total / 4);
  const rightCount = Math.ceil((total - topCount) / 3);
  const bottomCount = Math.ceil((total - topCount - rightCount) / 2);
  const leftCount = Math.max(total - topCount - rightCount - bottomCount, 0);
  const chipX = 130;
  const chipY = 120;
  const chipWidth = 340;
  const chipHeight = 240;
  const pinWidth = 42;
  const pinHeight = 24;

  return sorted.map((pinNumber, index) => {
    if (index < topCount) {
      const slot = index;
      const step = chipWidth / Math.max(topCount, 1);
      return {
        pinNumber,
        x: chipX + slot * step + 6,
        y: chipY - 34,
        width: pinWidth,
        height: pinHeight,
        side: "top",
      } satisfies PackagePinLayout;
    }

    if (index < topCount + rightCount) {
      const slot = index - topCount;
      const step = chipHeight / Math.max(rightCount, 1);
      return {
        pinNumber,
        x: chipX + chipWidth - 8,
        y: chipY + slot * step + 8,
        width: pinHeight,
        height: pinWidth,
        side: "right",
      } satisfies PackagePinLayout;
    }

    if (index < topCount + rightCount + bottomCount) {
      const slot = index - topCount - rightCount;
      const step = chipWidth / Math.max(bottomCount, 1);
      return {
        pinNumber,
        x: chipX + chipWidth - (slot + 1) * step - 6,
        y: chipY + chipHeight + 10,
        width: pinWidth,
        height: pinHeight,
        side: "bottom",
      } satisfies PackagePinLayout;
    }

    const slot = index - topCount - rightCount - bottomCount;
    const step = chipHeight / Math.max(leftCount, 1);
    return {
      pinNumber,
      x: chipX - 34,
      y: chipY + chipHeight - (slot + 1) * step - 8,
      width: pinHeight,
      height: pinWidth,
      side: "left",
    } satisfies PackagePinLayout;
  });
}

export function PinAssignmentsPanel({ pinAssignments, onClearPinAssignment, onAssignPinAltFunction, onUpdatePinBooleanProperty }: PinAssignmentsPanelProps) {
  const [filter, setFilter] = useState<PinAssignmentFilter>("all");
  const [selectedPinNumber, setSelectedPinNumber] = useState<string | null>(null);
  const [hoveredPinNumber, setHoveredPinNumber] = useState<string | null>(null);
  const { propertyValuesByPinNumber, rows, summary } = pinAssignments;
  const viewport = useSceneViewport({ fitZoom: 0.88 });
  const filteredRows = rows.filter((row) => filter === "all" || row.resolution === filter);
  const selectedRow = filteredRows.find((row) => row.pinNumber === selectedPinNumber) ?? filteredRows[0] ?? null;
  const hoveredRow = rows.find((row) => row.pinNumber === hoveredPinNumber) ?? null;
  const selectedProps = selectedRow ? propertyValuesByPinNumber[selectedRow.pinNumber] ?? {} : {};
  const selectedAltFunctionOptions = selectedRow ? pinAssignments.altFunctionOptionsByPinNumber[selectedRow.pinNumber] ?? [] : [];
  const selectedAltFunction = useMemo(
    () => selectedAltFunctionOptions.find((option) => option.value === selectedRow?.selectedAltFunctionValue) ?? selectedAltFunctionOptions[0] ?? null,
    [selectedAltFunctionOptions, selectedRow?.selectedAltFunctionValue],
  );
  const packageLayout = useMemo(() => buildPackageLayout(rows.map((row) => row.pinNumber)), [rows]);
  const filteredPinSet = useMemo(() => new Set(filteredRows.map((row) => row.pinNumber)), [filteredRows]);
  const selectedIssues = useMemo(
    () => (selectedRow ? pinAssignments.issuesByPinNumber[selectedRow.pinNumber] ?? [] : []),
    [pinAssignments.issuesByPinNumber, selectedRow],
  );
  const totalIssueCount = useMemo(
    () => Object.values(pinAssignments.issuesByPinNumber).reduce((count, issues) => count + issues.length, 0),
    [pinAssignments.issuesByPinNumber],
  );
  const readinessIssuePreview = useMemo(
    () => Object.entries(pinAssignments.issuesByPinNumber).flatMap(([pinNumber, issues]) => issues.map((issue) => ({ pinNumber, issue }))).slice(0, 3),
    [pinAssignments.issuesByPinNumber],
  );
  const selectedRowIssueCount = selectedRow ? pinAssignments.issuesByPinNumber[selectedRow.pinNumber]?.length ?? 0 : 0;

  const selectPin = (pinNumber: string) => {
    setSelectedPinNumber(pinNumber);
    setHoveredPinNumber(pinNumber);
  };

  useEffect(() => {
    if (!filteredRows.length) {
      if (selectedPinNumber !== null) {
        setSelectedPinNumber(null);
      }
      return;
    }

    if (!selectedRow) {
      setSelectedPinNumber(filteredRows[0]?.pinNumber ?? null);
    }
  }, [filteredRows, selectedPinNumber, selectedRow]);

  return (
    <div className="pin-assignments-panel">
      <InspectorSection
        title="Pin readiness"
        summary="Review unresolved selections and active pin issues here before changing assignment values or treating generated artifacts as ready."
        actions={<DiagnosticBadge label={`${summary.unresolvedCount} unresolved`} tone={summary.unresolvedCount ? "warning" : "success"} />}
      >
        <div className="pin-assignments-panel__summary">
          <div>
            <strong>{summary.resolvedCount}</strong>
            <span>resolved selections</span>
          </div>
          <div>
            <strong>{summary.savedCount}</strong>
            <span>saved pin entries</span>
          </div>
          <div>
            <strong>{summary.unresolvedCount}</strong>
            <span>unresolved after board match</span>
          </div>
          <div>
            <strong>{totalIssueCount}</strong>
            <span>active issues</span>
          </div>
        </div>
        {(summary.unresolvedCount || totalIssueCount) ? (
          <InspectorNotice
            title="Pin blockers stay at the top of the workflow"
            detail={`${summary.unresolvedCount} unresolved selection${summary.unresolvedCount === 1 ? " remains" : "s remain"} and ${totalIssueCount} active issue${totalIssueCount === 1 ? " is" : "s are"} currently affecting board handoff.`}
            tone="warning"
          />
        ) : (
          <InspectorNotice
            title="Pin workflow is aligned"
            detail="Use the package surface and detail editor below to adjust assignments while keeping the resolved route and issue state in view."
            tone="info"
          />
        )}
        {totalIssueCount ? (
          <div className="pin-assignments-panel__issues" aria-label="Pin readiness issues">
            {readinessIssuePreview.map(({ pinNumber, issue }) => (
              <button
                key={issue.id}
                type="button"
                className={selectedRow?.pinNumber === pinNumber ? "pin-assignments-panel__issue pin-assignments-panel__issue--compact pin-assignments-panel__issue--selected" : "pin-assignments-panel__issue pin-assignments-panel__issue--compact"}
                onClick={() => selectPin(pinNumber)}
              >
                <div className="pin-assignments-panel__issue-title-row">
                  <strong>{issue.title}</strong>
                  <span className="pin-assignments-panel__issue-pin">{`Pin ${pinNumber}`}</span>
                </div>
                <span>{issue.summary}</span>
              </button>
            ))}
          </div>
        ) : null}
      </InspectorSection>

      <div className="pin-assignments-panel__filters" role="group" aria-label="Pin assignment filters">
        <button
          type="button"
          className={filter === "all" ? "pin-assignments-panel__filter pin-assignments-panel__filter--active" : "pin-assignments-panel__filter"}
          onClick={() => setFilter("all")}
        >
          {`All (${summary.savedCount})`}
        </button>
        <button
          type="button"
          className={filter === "resolved" ? "pin-assignments-panel__filter pin-assignments-panel__filter--active" : "pin-assignments-panel__filter"}
          onClick={() => setFilter("resolved")}
        >
          {`Resolved (${summary.resolvedCount})`}
        </button>
        <button
          type="button"
          className={filter === "unresolved" ? "pin-assignments-panel__filter pin-assignments-panel__filter--active" : "pin-assignments-panel__filter"}
          onClick={() => setFilter("unresolved")}
        >
          {`Unresolved (${summary.unresolvedCount})`}
        </button>
      </div>

      {rows.length ? (
        <InspectorSection
          title="Package surface"
          summary="The pin workflow now includes an approximate package map with hover inspection, filtered highlight states, quick reassignment, and scene controls."
          actions={<DiagnosticBadge label={`${filteredRows.length} visible pins`} tone="info" />}
        >
          <SceneViewportToolbar zoom={viewport.zoom} onZoomOut={viewport.zoomOut} onZoomIn={viewport.zoomIn} onFit={viewport.fit} onReset={viewport.reset}>
            <span className="domain-summary-text">Drag the scene to pan, or use Fit to recenter the package.</span>
          </SceneViewportToolbar>
          <div className="pin-assignments-panel__scene-shell">
            <svg
              className={viewport.isDragging ? "pin-assignments-panel__scene pin-assignments-panel__scene--dragging" : "pin-assignments-panel__scene"}
              viewBox="0 0 600 480"
              role="img"
              aria-label="Package surface"
              onMouseDown={(event) => viewport.beginPan(event.clientX, event.clientY)}
              onMouseMove={(event) => viewport.movePan(event.clientX, event.clientY)}
              onMouseUp={viewport.endPan}
              onMouseLeave={() => {
                viewport.endPan();
                setHoveredPinNumber(null);
              }}
            >
              <rect x="34" y="34" width="532" height="412" rx="28" className="pin-assignments-panel__scene-backdrop" />
              <g transform={viewport.transform}>
                <rect x="130" y="120" width="340" height="240" rx="32" className="pin-assignments-panel__scene-chip" />
                <text x="300" y="220" textAnchor="middle" className="pin-assignments-panel__scene-chip-title">MCU Package</text>
                <text x="300" y="246" textAnchor="middle" className="pin-assignments-panel__scene-chip-subtitle">Filtered highlight tracks saved, resolved, and unresolved pin selections.</text>
                {packageLayout.map((pin) => {
                  const row = rows.find((entry) => entry.pinNumber === pin.pinNumber);
                  const isSelected = selectedRow?.pinNumber === pin.pinNumber;
                  const isHovered = hoveredPinNumber === pin.pinNumber;
                  const visible = filteredPinSet.has(pin.pinNumber);
                  const unresolved = row?.resolution === "unresolved";
                    const hasIssues = (pinAssignments.issuesByPinNumber[pin.pinNumber]?.length ?? 0) > 0;
                  const toneClass = unresolved
                    ? "pin-assignments-panel__scene-pin--warning"
                      : hasIssues
                        ? "pin-assignments-panel__scene-pin--conflict"
                    : row
                      ? "pin-assignments-panel__scene-pin--resolved"
                      : "pin-assignments-panel__scene-pin--empty";

                  return (
                    <g
                      key={pin.pinNumber}
                      className={[
                        "pin-assignments-panel__scene-pin",
                        toneClass,
                        visible ? "pin-assignments-panel__scene-pin--visible" : "pin-assignments-panel__scene-pin--muted",
                        isSelected ? "pin-assignments-panel__scene-pin--selected" : "",
                        isHovered ? "pin-assignments-panel__scene-pin--hovered" : "",
                      ].filter(Boolean).join(" ")}
                      onMouseEnter={() => setHoveredPinNumber(pin.pinNumber)}
                      onClick={() => selectPin(pin.pinNumber)}
                    >
                      <rect x={pin.x} y={pin.y} width={pin.width} height={pin.height} rx="8" />
                      <text x={pin.x + pin.width / 2} y={pin.y + pin.height / 2 + 4} textAnchor="middle">{pin.pinNumber}</text>
                    </g>
                  );
                })}
              </g>
            </svg>
            <div className="pin-assignments-panel__scene-inspector">
              <strong>{hoveredRow ? `Pin ${hoveredRow.pinNumber}` : selectedRow ? `Pin ${selectedRow.pinNumber}` : "Package overview"}</strong>
              <span>
                {hoveredRow
                  ? `${hoveredRow.savedLabel} • ${hoveredRow.resolvedRoute}`
                  : selectedRow
                    ? `${selectedRow.savedLabel} • ${selectedRow.resolvedRoute}`
                    : "Hover or select a pin to inspect it inside the package surface."}
              </span>
              {selectedRow ? (
                <div className="pin-assignments-panel__status-row" aria-label="Selected pin status">
                  <DiagnosticBadge label={selectedRow.resolution === "resolved" ? "Matched route" : "Incomplete route"} tone={selectedRow.resolution === "resolved" ? "success" : "warning"} />
                  <DiagnosticBadge label={selectedRowIssueCount ? `${selectedRowIssueCount} conflict${selectedRowIssueCount === 1 ? "" : "s"}` : "No conflicts"} tone={selectedRowIssueCount ? "error" : "info"} />
                </div>
              ) : null}
              {selectedRow && selectedAltFunctionOptions.length ? (
                <label className="project-flow__field">
                  <span>Quick assign</span>
                  <select
                    aria-label="Quick assign alt function"
                    value={selectedRow.selectedAltFunctionValue}
                    onChange={(event) => {
                      const nextOption = selectedAltFunctionOptions.find((option) => option.value === event.target.value);
                      if (nextOption) {
                        onAssignPinAltFunction(selectedRow.pinNumber, nextOption);
                      }
                    }}
                  >
                    {selectedAltFunctionOptions.map((option) => (
                      <option key={option.value} value={option.value}>{`${option.label} (${option.detail})`}</option>
                    ))}
                  </select>
                </label>
              ) : null}
              {selectedRow ? (
                <button type="button" className="pin-assignments-panel__clear" onClick={() => onClearPinAssignment(selectedRow.pinNumber)}>
                  Clear
                </button>
              ) : null}
            </div>
          </div>
        </InspectorSection>
      ) : null}

      {!rows.length ? (
        <EmptyState
          title="No saved pin assignments"
          detail="Load a project file or migrate the pin editor next so the inspector can compare saved selections against board routes."
          compact
        />
      ) : null}

      {rows.length ? (
        <ul className="pin-assignments-panel__list">
          {filteredRows.map((row) => {
            const issueCount = pinAssignments.issuesByPinNumber[row.pinNumber]?.length ?? 0;
            return (
              <li
                key={row.pinNumber}
                className={[
                  "pin-assignments-panel__item",
                  selectedRow?.pinNumber === row.pinNumber ? "pin-assignments-panel__item--selected" : "",
                  row.resolution === "unresolved" ? "pin-assignments-panel__item--unresolved" : "",
                  issueCount ? "pin-assignments-panel__item--conflict" : "",
                ].filter(Boolean).join(" ")}
              >
                <div className="pin-assignments-panel__item-header">
                  <button
                    type="button"
                    className="pin-assignments-panel__select"
                    onClick={() => selectPin(row.pinNumber)}
                  >
                    <strong>{`Pin ${row.pinNumber}`}</strong>
                    <span>{row.savedLabel}</span>
                  </button>
                  <div className="pin-assignments-panel__item-badges">
                    <DiagnosticBadge label={row.resolution === "resolved" ? "Matched" : "Unresolved"} tone={row.resolution === "resolved" ? "success" : "warning"} />
                    {issueCount ? <DiagnosticBadge label={`${issueCount} conflict${issueCount === 1 ? "" : "s"}`} tone="error" /> : <DiagnosticBadge label="Saved" tone="info" />}
                  </div>
                  <ContextMenu
                    triggerLabel={`Pin ${row.pinNumber} actions`}
                    items={[
                      {
                        id: `pin.${row.pinNumber}.select`,
                        label: "Select pin detail",
                        onSelect: () => selectPin(row.pinNumber),
                      },
                      {
                        id: `pin.${row.pinNumber}.clear`,
                        label: "Clear assignment",
                        onSelect: () => onClearPinAssignment(row.pinNumber),
                        shortcut: <ShortcutHint shortcut="Del" />,
                      },
                    ]}
                  />
                </div>
                <div className="pin-assignments-panel__item-grid">
                  <span>{`Resolved: ${row.resolvedLabel}`}</span>
                  <span>{`Route: ${row.resolvedRoute}`}</span>
                  <span>{row.propertyKeys.length ? `Props: ${row.propertyKeys.join(", ")}` : "Props: none"}</span>
                </div>
              </li>
            );
          })}
        </ul>
      ) : null}

      {rows.length && !filteredRows.length ? (
        <EmptyState title="No filtered assignments" detail="Switch filters or save additional pin selections to inspect more rows." compact />
      ) : null}

      {selectedRow ? (
        <InspectorSection
          title="Pin selection detail"
          summary="Review the saved selection, matched route, and any board-specific issues before editing pin-owned values."
          actions={
            <DiagnosticBadge
              label={selectedRow.resolution === "resolved" ? "Matched" : "Unresolved"}
              tone={selectedRow.resolution === "resolved" ? "success" : "warning"}
            />
          }
        >
          <InspectorNotice
            title="Editable values stay below derived route data"
            detail="Saved selection, resolved match, and route stay read-only here. Use the alt-function and property controls below to change the canonical pin entry."
            tone="info"
          />
          {selectedIssues.length ? (
            <InspectorNotice
              title="Pin conflicts stay attached to the current selection"
              detail="Conflicts, unresolved routes, and property mismatches remain in this detail section so the selected pin and its blockers never drift apart."
              tone="warning"
            />
          ) : null}
          <PropertyGrid>
            <PropertyRow label="Selected Pin" value={`Pin ${selectedRow.pinNumber}`} />
            <PropertyRow label="Saved Selection" value={selectedRow.savedLabel} />
            <PropertyRow label="Resolved Match" value={selectedRow.resolvedLabel} />
            <PropertyRow label="Route" value={selectedRow.resolvedRoute} />
            <PropertyRow
              label="Status"
              value={selectedRow.resolution === "resolved" ? "Matched against board definition" : "Saved only, unresolved"}
            />
            <PropertyRow label="Conflict count" value={selectedIssues.length ? String(selectedIssues.length) : "0"} />
            <PropertyRow label="Properties" value={selectedRow.propertyKeys.length ? selectedRow.propertyKeys.join(", ") : "None"} />
          </PropertyGrid>
          <div className="pin-assignments-panel__detail-actions">
            {selectedAltFunctionOptions.length ? (
              <div className="pin-assignments-panel__alt-functions" aria-label="Alt function choices">
                <label className="project-flow__field">
                  <span>Alt function</span>
                  <select
                    aria-label="Alt function"
                    value={selectedRow.selectedAltFunctionValue}
                    onChange={(event) => {
                      const nextOption = selectedAltFunctionOptions.find((option) => option.value === event.target.value);
                      if (nextOption) {
                        onAssignPinAltFunction(selectedRow.pinNumber, nextOption);
                      }
                    }}
                  >
                    {selectedAltFunctionOptions.map((option) => (
                      <option key={option.value} value={option.value}>
                        {`${option.label} (${option.detail})`}
                      </option>
                    ))}
                  </select>
                </label>
                {selectedAltFunction ? (
                  <div className="pin-assignments-panel__alt-function-current">
                    <strong>{selectedAltFunction.label}</strong>
                    <span>{selectedAltFunction.detail}</span>
                    <div className="pin-assignments-panel__status-row">
                      <DiagnosticBadge label={`PINCM ${selectedAltFunction.pincm}`} tone="info" />
                      <DiagnosticBadge label={selectedAltFunction.direction || "io"} tone="info" />
                    </div>
                  </div>
                ) : null}
                <ul className="pin-assignments-panel__alt-function-list">
                  {selectedAltFunctionOptions.map((option) => (
                    <li
                      key={option.value}
                      className={option.value === selectedRow.selectedAltFunctionValue ? "pin-assignments-panel__alt-function-item pin-assignments-panel__alt-function-item--selected" : "pin-assignments-panel__alt-function-item"}
                    >
                      <button
                        type="button"
                        className="pin-assignments-panel__alt-function-button"
                        onClick={() => onAssignPinAltFunction(selectedRow.pinNumber, option)}
                      >
                        <strong>{option.label}</strong>
                        <span>{option.detail}</span>
                      </button>
                    </li>
                  ))}
                </ul>
              </div>
            ) : null}
            {pinBooleanProperties.map((property) => (
              <label key={property.key} className="pin-assignments-panel__checkbox">
                <input
                  type="checkbox"
                  checked={selectedProps[property.key] === true}
                  onChange={(event) => onUpdatePinBooleanProperty(selectedRow.pinNumber, property.key, event.target.checked)}
                />
                <span>{property.label}</span>
              </label>
            ))}
          </div>
          {selectedIssues.length ? (
            <div className="pin-assignments-panel__issues">
              {selectedIssues.map((issue) => (
                <div key={issue.id} className="pin-assignments-panel__issue">
                  <div className="pin-assignments-panel__issue-title-row">
                    <strong>{issue.title}</strong>
                    <DiagnosticBadge label="Conflict" tone="error" />
                  </div>
                  <span>{issue.summary}</span>
                </div>
              ))}
            </div>
          ) : null}
        </InspectorSection>
      ) : null}
    </div>
  );
}