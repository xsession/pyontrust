import Editor from "@monaco-editor/react";
import { DiagnosticBadge } from "../shared/ui/feedback/DiagnosticBadge";
import { EmptyState } from "../shared/ui/feedback/EmptyState";
import { InspectorSection } from "../shared/ui/inspectors/InspectorSection";
import type { ModuleConfiguratorPresenter } from "../domains/modules/moduleConfiguratorPresenter";

interface ModuleConfiguratorPanelProps {
  presenter: ModuleConfiguratorPresenter;
}

export function ModuleConfiguratorPanel({ presenter }: ModuleConfiguratorPanelProps) {
  const activeModule = presenter.activeModule;

  return (
    <div className="domain-panel domain-panel--split">
      <InspectorSection
        title="Module definitions"
        summary="Typed module definitions now load through the shared API layer and keep local option state inside a presenter instead of legacy globals."
        actions={<DiagnosticBadge label={`${presenter.modules.filter((module) => module.enabled).length} enabled`} tone="info" />}
      >
        <div className="domain-list__header domain-list__header--compact">
          <span className="domain-summary-text">{presenter.status}</span>
          <button type="button" className="shell-button" onClick={presenter.generateEnabledModules} disabled={presenter.loading}>
            Generate Enabled
          </button>
        </div>
        {presenter.error ? <EmptyState title="Module definitions unavailable" detail={presenter.error} tone="error" compact /> : null}
        {!presenter.error && !presenter.modules.length ? <EmptyState title="No module definitions" detail="The backend did not return any Zephyr module metadata for the workspace." compact /> : null}
        {presenter.modules.length ? (
          <ul className="domain-list">
            {presenter.modules.map((module) => (
              <li key={module.id} className={module.id === presenter.activeModuleId ? "domain-list__item domain-list__item--selected" : "domain-list__item"}>
                <div className="domain-list__header">
                  <button type="button" className="domain-list__select" onClick={() => presenter.selectModule(module.id)}>
                    <strong>{`${module.icon} ${module.name}`}</strong>
                    <span>{`${module.changedCount} changed option${module.changedCount === 1 ? "" : "s"}`}</span>
                  </button>
                  <label className="domain-toggle">
                    <input type="checkbox" checked={module.enabled} onChange={(event) => presenter.setModuleEnabled(module.id, event.target.checked)} />
                    <span>{module.enabled ? "Enabled" : "Disabled"}</span>
                  </label>
                </div>
              </li>
            ))}
          </ul>
        ) : null}
      </InspectorSection>

      <InspectorSection
        title={activeModule ? `${activeModule.icon} ${activeModule.name}` : "Module detail"}
        summary={activeModule?.description || "Select a module to edit its typed options and generate its configuration payload."}
        actions={activeModule ? <DiagnosticBadge label={`${activeModule.changedCount} changed`} tone={activeModule.changedCount ? "warning" : "success"} /> : undefined}
      >
        {!activeModule ? <EmptyState title="No active module" detail="Select a module definition to edit or enable it for generation." compact /> : null}
        {activeModule ? (
          <div className="domain-panel">
            <div className="domain-list__header domain-list__header--compact">
              <span className="domain-summary-text">{activeModule.version ? `Version ${activeModule.version}` : "Version not provided"}</span>
              <button type="button" className="shell-button shell-button--ghost" onClick={() => presenter.resetModule(activeModule.id)}>
                Reset Module
              </button>
            </div>
            {activeModule.categories.map((category) => (
              <div key={category.id} className="project-flow">
                <strong>{category.title}</strong>
                <div className="protocol-editor-panel__fields">
                  {category.options.map((option) => {
                    if (option.type === "bool") {
                      return (
                        <label key={option.key} className="protocol-editor-panel__checkbox">
                          <input
                            type="checkbox"
                            checked={option.value === true}
                            onChange={(event) => presenter.updateModuleOption(activeModule.id, option.key, event.target.checked)}
                          />
                          <span>{option.label || option.key}</span>
                        </label>
                      );
                    }

                    if (option.type === "choice") {
                      return (
                        <label key={option.key} className="project-flow__field">
                          <span>{option.label || option.key}</span>
                          <select value={String(option.value)} onChange={(event) => presenter.updateModuleOption(activeModule.id, option.key, event.target.value)}>
                            {(option.choices ?? []).map((choice) => (
                              <option key={String(choice)} value={String(choice)}>{String(choice)}</option>
                            ))}
                          </select>
                        </label>
                      );
                    }

                    return (
                      <label key={option.key} className="project-flow__field">
                        <span>{option.label || option.key}</span>
                        <input
                          type={option.type === "int" ? "number" : "text"}
                          value={String(option.value)}
                          onChange={(event) => presenter.updateModuleOption(activeModule.id, option.key, option.type === "int" ? Number(event.target.value) || 0 : event.target.value)}
                        />
                      </label>
                    );
                  })}
                </div>
              </div>
            ))}
            <div className="domain-panel domain-panel--split">
              <div className="domain-editor">
                <Editor height="100%" defaultLanguage="ini" theme="light" value={presenter.generatedPrjConf} options={{ minimap: { enabled: false }, readOnly: true, fontSize: 13, scrollBeyondLastLine: false }} />
              </div>
              <div className="domain-editor">
                <Editor height="100%" defaultLanguage="ini" theme="light" value={presenter.generatedOverlayConf} options={{ minimap: { enabled: false }, readOnly: true, fontSize: 13, scrollBeyondLastLine: false }} />
              </div>
            </div>
          </div>
        ) : null}
      </InspectorSection>
    </div>
  );
}