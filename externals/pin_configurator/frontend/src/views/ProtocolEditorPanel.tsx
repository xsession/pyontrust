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

  return (
    <div className="protocol-editor-panel">
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
            title={activeTemplate.label}
            summary={activeTemplate.summary}
            actions={<DiagnosticBadge label={activeTemplate.transport} tone="info" />}
          >
            <InspectorNotice
              title="Editable protocol fields"
              detail="The selected entry is the only mutable target. Template family and transport stay derived so later generators can rely on stable protocol metadata."
            />
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
