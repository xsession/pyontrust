import { DiagnosticBadge } from "../shared/ui/feedback/DiagnosticBadge";
import { EmptyState } from "../shared/ui/feedback/EmptyState";
import { InspectorSection } from "../shared/ui/inspectors/InspectorSection";
import type { InterruptConfiguratorPresenter } from "../domains/interrupts/interruptConfiguratorPresenter";

interface InterruptConfiguratorPanelProps {
  presenter: InterruptConfiguratorPresenter;
}

function toneForSeverity(severity: "stable" | "moderate" | "attention") {
  if (severity === "attention") {
    return "error" as const;
  }
  if (severity === "moderate") {
    return "warning" as const;
  }
  return "success" as const;
}

export function InterruptConfiguratorPanel({ presenter }: InterruptConfiguratorPanelProps) {
  return (
    <InspectorSection
      title="Interrupt configurator"
      summary="Interrupt-sensitive workflows are now derived from typed protocol, module, and clock presenters instead of the legacy interrupt snapshot script."
      actions={<DiagnosticBadge label={`${presenter.items.length} items`} tone="info" />}
    >
      <p className="domain-summary-text">{presenter.summary}</p>
      {!presenter.items.length ? <EmptyState title="No interrupt-sensitive items" detail="Enable interrupt-oriented protocol, module, or clock workflows to populate this presenter." compact /> : null}
      {presenter.items.length ? (
        <div className="pin-assignments-panel__issues">
          {presenter.items.map((item) => (
            <div key={item.id} className="pin-assignments-panel__issue">
              <div className="pin-assignments-panel__issue-title-row">
                <strong>{item.title}</strong>
                <DiagnosticBadge label={item.severity} tone={toneForSeverity(item.severity)} />
              </div>
              <span>{`${item.category} • ${item.source}`}</span>
              <span>{item.reason}</span>
              <span>{item.impact}</span>
              <span>{item.priorityLabel}</span>
            </div>
          ))}
        </div>
      ) : null}
    </InspectorSection>
  );
}