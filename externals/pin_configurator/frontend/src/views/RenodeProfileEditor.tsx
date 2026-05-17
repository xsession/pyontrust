import type { RenodeProfile } from "../contracts/api";
import { DiagnosticBadge } from "../shared/ui/feedback/DiagnosticBadge";
import { InspectorNotice } from "../shared/ui/inspectors/InspectorNotice";
import { InspectorSection } from "../shared/ui/inspectors/InspectorSection";
import { PropertyGrid, PropertyRow } from "../shared/ui/inspectors/PropertyGrid";

export type RenodeFieldUpdater = <K extends keyof RenodeProfile>(field: K, value: RenodeProfile[K]) => void;

interface RenodeProfileEditorProps {
  renode: RenodeProfile;
  disabled?: boolean;
  onFieldChange: RenodeFieldUpdater;
}

export function RenodeProfileEditor({ renode, disabled = false, onFieldChange }: RenodeProfileEditorProps) {
  const missingTargets = [!renode.platform.trim(), !renode.appbench_target.trim(), !renode.robot_target.trim()].filter(Boolean).length;
  const sourceFieldCount = [renode.resc, renode.robot].filter((value) => value.trim().length > 0).length;
  const automationTargetCount = Number(Boolean(renode.appbench_target.trim())) + Number(Boolean(renode.robot_target.trim()));
  const bundleReady = renode.enabled && missingTargets === 0 && sourceFieldCount === 2;

  return (
    <div className="renode-profile">
      <InspectorSection
        title="Renode readiness"
        summary="Review runtime targets, automation coverage, and source script presence here before editing Renode fields or exporting simulation bundles."
        actions={<DiagnosticBadge label={`${missingTargets} missing targets`} tone={missingTargets ? "warning" : "success"} />}
      >
        <PropertyGrid>
          <PropertyRow label="Mode" value={renode.enabled ? "Enabled" : "Disabled"} />
          <PropertyRow label="Platform" value={renode.platform.trim() ? "Ready" : "Pending"} />
          <PropertyRow label="Automation targets" value={`${automationTargetCount}/2`} />
          <PropertyRow label="Source scripts" value={sourceFieldCount} />
        </PropertyGrid>
        <InspectorNotice
          title={missingTargets ? "Simulation blockers stay above editing" : "Simulation routing is ready for editing"}
          detail={missingTargets
            ? "Populate platform, AppBench, and Robot targets before treating RESC and Robot exports as ready for handoff."
            : "Edit runtime and automation source fields below while generated simulation bundles remain derived outputs."}
          tone={missingTargets ? "warning" : "info"}
        />
      </InspectorSection>

      <InspectorSection
        title="Simulation bundle loop"
        summary="Keep machine selection, automation targets, RESC review, and Robot review in one explicit handoff loop before export."
        actions={<DiagnosticBadge label={bundleReady ? "Bundle ready" : "Bundle review"} tone={bundleReady ? "success" : "warning"} />}
      >
        <PropertyGrid>
          <PropertyRow label="Machine target" value={renode.platform.trim() || "Pending"} />
          <PropertyRow label="AppBench" value={renode.appbench_target.trim() || "Pending"} />
          <PropertyRow label="Robot" value={renode.robot_target.trim() || "Pending"} />
          <PropertyRow label="Source scripts" value={`${sourceFieldCount}/2`} />
          <PropertyRow label="Bundle readiness" value={bundleReady ? "Ready for export" : "Needs review"} />
        </PropertyGrid>
        <InspectorNotice
          title={bundleReady ? "Machine, RESC, and Robot review are aligned" : "The simulation bundle loop still has gaps"}
          detail={bundleReady
            ? "Platform target, automation targets, RESC, and Robot sources are all populated, so the simulation handoff bundle is coherent from one panel."
            : "Review machine selection, AppBench/Robot targets, RESC, and Robot content together before treating the simulation bundle as export-ready."}
          tone={bundleReady ? "info" : "warning"}
        />
      </InspectorSection>

      <InspectorSection
        title="Editable runtime fields"
        summary="Configure runtime enablement, UART handoff, and platform entrypoints for the active project."
      >
        {renode.enabled && !renode.platform.trim() ? (
          <InspectorNotice
            title="Simulation target still depends on a platform"
            detail="Keep the Renode platform populated before exporting bundles so simulator launch configuration and UART ownership stay authoritative."
            tone="warning"
            actions={<DiagnosticBadge label="Platform pending" tone="warning" />}
          />
        ) : null}
        <div className="renode-profile__grid">
          <label className="project-flow__field">
            <span>Renode mode</span>
            <select
              aria-label="Renode mode"
              value={renode.enabled ? "enabled" : "disabled"}
              onChange={(event) => onFieldChange("enabled", event.target.value === "enabled")}
              disabled={disabled}
            >
              <option value="enabled">Enabled</option>
              <option value="disabled">Disabled</option>
            </select>
          </label>
          <label className="project-flow__field">
            <span>Renode UART</span>
            <input
              aria-label="Renode UART"
              type="text"
              value={renode.uart}
              onChange={(event) => onFieldChange("uart", event.target.value)}
              disabled={disabled}
            />
          </label>
        </div>

        <label className="project-flow__field">
          <span>Renode platform</span>
          <input
            aria-label="Renode platform"
            type="text"
            value={renode.platform}
            onChange={(event) => onFieldChange("platform", event.target.value)}
            disabled={disabled}
          />
        </label>

        <label className="project-flow__field">
          <span>Boot line</span>
          <input
            aria-label="Renode boot line"
            type="text"
            value={renode.boot_line}
            onChange={(event) => onFieldChange("boot_line", event.target.value)}
            disabled={disabled}
          />
        </label>
      </InspectorSection>

      <InspectorSection
        title="Editable automation source fields"
        summary="Keep AppBench and Robot routing aligned with the current Renode profile before exporting simulation bundles."
      >
        <InspectorNotice
          title="Generated simulation bundles stay derived from these source fields"
          detail="RESC and Robot text areas are editable inputs, while downstream export artifacts inherit these values and remain generated outputs."
          tone="info"
        />
        <div className="renode-profile__grid">
          <label className="project-flow__field">
            <span>AppBench target</span>
            <input
              aria-label="AppBench target"
              type="text"
              value={renode.appbench_target}
              onChange={(event) => onFieldChange("appbench_target", event.target.value)}
              disabled={disabled}
            />
          </label>
          <label className="project-flow__field">
            <span>Robot target</span>
            <input
              aria-label="Robot target"
              type="text"
              value={renode.robot_target}
              onChange={(event) => onFieldChange("robot_target", event.target.value)}
              disabled={disabled}
            />
          </label>
        </div>

        <label className="project-flow__field">
          <span>Resc script</span>
          <textarea
            aria-label="Renode RESC"
            value={renode.resc}
            onChange={(event) => onFieldChange("resc", event.target.value)}
            rows={4}
            disabled={disabled}
          />
        </label>

        <label className="project-flow__field">
          <span>Robot script</span>
          <textarea
            aria-label="Renode Robot"
            value={renode.robot}
            onChange={(event) => onFieldChange("robot", event.target.value)}
            rows={4}
            disabled={disabled}
          />
        </label>
      </InspectorSection>
    </div>
  );
}