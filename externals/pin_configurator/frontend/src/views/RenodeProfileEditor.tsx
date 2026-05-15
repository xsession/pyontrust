import type { RenodeProfile } from "../contracts/api";
import { DiagnosticBadge } from "../shared/ui/feedback/DiagnosticBadge";
import { InspectorNotice } from "../shared/ui/inspectors/InspectorNotice";
import { InspectorSection } from "../shared/ui/inspectors/InspectorSection";

export type RenodeFieldUpdater = <K extends keyof RenodeProfile>(field: K, value: RenodeProfile[K]) => void;

interface RenodeProfileEditorProps {
  renode: RenodeProfile;
  disabled?: boolean;
  onFieldChange: RenodeFieldUpdater;
}

export function RenodeProfileEditor({ renode, disabled = false, onFieldChange }: RenodeProfileEditorProps) {
  return (
    <div className="renode-profile">
      <InspectorSection
        title="Simulation transport"
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
        title="Automation targets"
        summary="Keep AppBench and Robot routing aligned with the current Renode profile before exporting simulation bundles."
      >
        <InspectorNotice
          title="Generated scripts stay derived from this profile"
          detail="RESC and Robot fields are editable source inputs, while downstream export artifacts should be treated as generated outputs that inherit these values."
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