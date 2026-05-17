import {
  PROTOCOL_EDITOR_TEMPLATES,
  protocolTemplateById,
  selectedProtocolEntry,
  type ProtocolEditorDocument,
  type ProtocolFieldValue,
} from "../contracts/api";
import { ContextMenu } from "../shared/ui/commands/ContextMenu";
import { ShortcutHint } from "../shared/ui/commands/ShortcutHint";
import { DiagnosticBadge } from "../shared/ui/feedback/DiagnosticBadge";
import { EmptyState } from "../shared/ui/feedback/EmptyState";
import { InspectorNotice } from "../shared/ui/inspectors/InspectorNotice";
import { InspectorSection } from "../shared/ui/inspectors/InspectorSection";
import { PropertyGrid, PropertyRow } from "../shared/ui/inspectors/PropertyGrid";

interface ProtocolEditorPanelProps {
  document: ProtocolEditorDocument;
  disabled?: boolean;
  onAddEntry: (templateId: string) => void;
  onSelectEntry: (entryId: string) => void;
  onRemoveEntry: (entryId: string) => void;
  onToggleEntry: (entryId: string, enabled: boolean) => void;
  onUpdateEntryValue: (entryId: string, fieldKey: string, value: ProtocolFieldValue) => void;
}

export function ProtocolEditorPanel({
  document,
  disabled = false,
  onAddEntry,
  onSelectEntry,
  onRemoveEntry,
  onToggleEntry,
  onUpdateEntryValue,
}: ProtocolEditorPanelProps) {
  const activeEntry = selectedProtocolEntry(document);
  const activeTemplate = protocolTemplateById(activeEntry?.templateId);
  const enabledEntryCount = document.entries.filter((entry) => entry.enabled).length;
  const disabledEntryCount = document.entries.length - enabledEntryCount;
  const activeEntryTitle = activeEntry && activeTemplate ? String(activeEntry.values.instanceName || activeTemplate.label) : "No active entry";
  const enabledEntries = document.entries.filter((entry) => entry.enabled);
  const generatedReviewItems = enabledEntries.map((entry) => {
    const template = protocolTemplateById(entry.templateId);
    const instanceName = String(entry.values.instanceName || template.label);

    return {
      id: entry.id,
      title: instanceName,
      header: `${instanceName}_init(void)`,
      source: `${instanceName}_attach(void)`,
      transport: template.transport,
    };
  });
  const exportReadiness = enabledEntryCount ? "Ready for generated C/header review" : "Enable a protocol entry before export review";

  return (
    <div className="protocol-editor-panel">
      <InspectorSection
        title="Protocol readiness"
        summary="Check enabled-entry coverage and the active transport here before editing protocol values or expecting generated interface artifacts to be ready."
        actions={<DiagnosticBadge label={`${enabledEntryCount} enabled`} tone={enabledEntryCount ? "success" : "warning"} />}
      >
        <PropertyGrid>
          <PropertyRow label="Entries" value={document.entries.length} />
          <PropertyRow label="Enabled" value={enabledEntryCount} />
          <PropertyRow label="Disabled" value={disabledEntryCount} />
          <PropertyRow label="Active entry" value={activeEntryTitle} />
          <PropertyRow label="Export readiness" value={exportReadiness} />
        </PropertyGrid>
        <InspectorNotice
          title={enabledEntryCount ? "Protocol blockers stay visible above editing" : "Protocol enablement is required before handoff"}
          detail={enabledEntryCount
            ? "Template family and transport remain derived values. Change only the selected entry fields in the editable section below."
            : "Enable at least one protocol entry before treating generated code, diagnostics, and tests as launch-ready."}
          tone={enabledEntryCount ? "info" : "warning"}
        />
      </InspectorSection>

      <InspectorSection
        title="Generated interface review"
        summary="Protocol edits now map directly to generated header and source review targets before export handoff."
        actions={<DiagnosticBadge label={`${generatedReviewItems.length} code paths`} tone={generatedReviewItems.length ? "info" : "warning"} />}
      >
        <InspectorNotice
          title={generatedReviewItems.length ? "Generated C and header review stays attached to protocol edits" : "Generated interface review is waiting for an enabled entry"}
          detail={generatedReviewItems.length
            ? "Use these projected header and source symbols as the immediate handoff between protocol editing and the generated artifact panels."
            : "Enable a protocol entry so generated header and source previews have concrete interface symbols to review."}
          tone={generatedReviewItems.length ? "info" : "warning"}
        />
        {generatedReviewItems.length ? (
          <ul className="domain-list">
            {generatedReviewItems.map((item) => (
              <li key={item.id} className="domain-list__item">
                <strong>{item.title}</strong>
                <span>{`${item.transport} • header ${item.header} • source ${item.source}`}</span>
              </li>
            ))}
          </ul>
        ) : null}
      </InspectorSection>

      <div className="protocol-editor-panel__catalog">
        {PROTOCOL_EDITOR_TEMPLATES.map((template) => (
          <button
            key={template.id}
            type="button"
            className={`protocol-template-card${document.selectedTemplateId === template.id ? " protocol-template-card--active" : ""}`}
            onClick={() => onAddEntry(template.id)}
            disabled={disabled}
          >
            <strong>{template.label}</strong>
            <span>{`${template.family} • ${template.transport}`}</span>
          </button>
        ))}
      </div>

      <div className="protocol-editor-panel__body">
        <div className="protocol-editor-panel__entries">
          {document.entries.map((entry) => {
            const template = protocolTemplateById(entry.templateId);
            const title = String(entry.values.instanceName || template.label);

            return (
              <div
                key={entry.id}
                className={`protocol-entry-card${document.selectedEntryId === entry.id ? " protocol-entry-card--active" : ""}`}
              >
                <button type="button" className="protocol-entry-card__select" onClick={() => onSelectEntry(entry.id)}>
                  <strong>{title}</strong>
                  <span>{template.label}</span>
                </button>
                <label className="protocol-entry-card__toggle">
                  <input
                    aria-label={`Enable ${title}`}
                    type="checkbox"
                    checked={entry.enabled}
                    onChange={(event) => onToggleEntry(entry.id, event.target.checked)}
                    disabled={disabled}
                  />
                  <span>{entry.enabled ? "Enabled" : "Disabled"}</span>
                </label>
                <ContextMenu
                  triggerLabel={`${title} protocol actions`}
                  items={[
                    {
                      id: `${entry.id}.select`,
                      label: "Focus entry",
                      onSelect: () => onSelectEntry(entry.id),
                    },
                    {
                      id: `${entry.id}.toggle`,
                      label: entry.enabled ? "Disable entry" : "Enable entry",
                      onSelect: () => onToggleEntry(entry.id, !entry.enabled),
                    },
                    {
                      id: `${entry.id}.remove`,
                      label: "Remove entry",
                      disabled: disabled || document.entries.length <= 1,
                      onSelect: () => onRemoveEntry(entry.id),
                      shortcut: <ShortcutHint shortcut="Del" />,
                    },
                  ]}
                />
              </div>
            );
          })}
        </div>

        {activeEntry && activeTemplate ? (
          <InspectorSection
            title="Editable protocol values"
            summary={activeTemplate.summary}
            actions={<DiagnosticBadge label={activeTemplate.transport} tone="info" />}
          >
            <InspectorNotice
              title="Editable entry values stay below derived metadata"
              detail="The selected entry is the only mutable target. Template family, transport, and enablement state stay summarized above as derived metadata."
            />
            <PropertyGrid>
              <PropertyRow label="Active entry" value={activeEntryTitle} />
              <PropertyRow label="Template family" value={activeTemplate.family} />
              <PropertyRow label="Transport" value={activeTemplate.transport} />
              <PropertyRow label="Entry status" value={activeEntry.enabled ? "Enabled" : "Disabled"} />
            </PropertyGrid>
            <div className="protocol-editor-panel__fields">
            {activeTemplate.fields.map((field) => {
              const value = activeEntry.values[field.key];
              const label = `${activeTemplate.label} ${field.label}`;

              if (field.type === "textarea") {
                return (
                  <label key={field.key} className="project-flow__field">
                    <span>{field.label}</span>
                    <textarea
                      aria-label={label}
                      rows={4}
                      value={String(value ?? "")}
                      onChange={(event) => onUpdateEntryValue(activeEntry.id, field.key, event.target.value)}
                      disabled={disabled}
                    />
                  </label>
                );
              }

              if (field.type === "select") {
                return (
                  <label key={field.key} className="project-flow__field">
                    <span>{field.label}</span>
                    <select
                      aria-label={label}
                      value={String(value ?? "")}
                      onChange={(event) => onUpdateEntryValue(activeEntry.id, field.key, event.target.value)}
                      disabled={disabled}
                    >
                      {(field.options ?? []).map((option) => (
                        <option key={option.value} value={option.value}>
                          {option.label}
                        </option>
                      ))}
                    </select>
                  </label>
                );
              }

              if (field.type === "checkbox") {
                return (
                  <label key={field.key} className="protocol-editor-panel__checkbox">
                    <input
                      aria-label={label}
                      type="checkbox"
                      checked={Boolean(value)}
                      onChange={(event) => onUpdateEntryValue(activeEntry.id, field.key, event.target.checked)}
                      disabled={disabled}
                    />
                    <span>{field.label}</span>
                  </label>
                );
              }

              return (
                <label key={field.key} className="project-flow__field">
                  <span>{field.label}</span>
                  <input
                    aria-label={label}
                    type={field.type}
                    min={field.min}
                    step={field.step}
                    value={String(value ?? "")}
                    onChange={(event) =>
                      onUpdateEntryValue(
                        activeEntry.id,
                        field.key,
                        field.type === "number" ? Number(event.target.value) || 0 : event.target.value,
                      )
                    }
                    disabled={disabled}
                  />
                </label>
              );
            })}
            </div>
          </InspectorSection>
        ) : (
          <EmptyState
            title="No active protocol entry"
            detail="Create or select a protocol template to edit its instance values in the shared inspector surface."
            compact
          />
        )}
      </div>
    </div>
  );
}
