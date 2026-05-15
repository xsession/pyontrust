import type { ProjectDocument } from "../../project/projectDocument";
import type { ExecutionWorkbenchViewModel } from "../../domains/build-sim-test/buildSimTestPresenter";
import type { PinAssignmentsViewModel } from "../../shared/viewModels/pinAssignments";
import type { ShellOutputChannelViewModel } from "../../presenters/useShellPresenter";
import type { ProjectStatus } from "../../project/workspaceState";
import { useRef } from "react";
import { StatusChip } from "../../shared/ui/StatusChip";
import { VirtualizedTreeList, type VirtualizedTreeListSection } from "../../shared/ui/virtualized/VirtualizedTreeList";

interface WorkspaceOutputZoneProps {
  outputChannels: ShellOutputChannelViewModel[];
  activeOutputChannel: ShellOutputChannelViewModel | null;
  executionWorkbench: ExecutionWorkbenchViewModel;
  followOutput: boolean;
  severityFilter: "all" | "info" | "success" | "warning" | "error";
  projectStatus: ProjectStatus;
  projectBusy: boolean;
  projectFilePath: string;
  projectDocument: ProjectDocument;
  pinAssignments: PinAssignmentsViewModel;
  onSelectChannel: (channelId: string) => void;
  onSelectSeverityFilter: (severity: "all" | "info" | "success" | "warning" | "error") => void;
  onToggleFollow: () => void;
  onCopyVisibleEntries: () => void;
  onResetView: () => void;
  onNavigateEntry: (entry: ShellOutputChannelViewModel["entries"][number]) => void;
  onSelectRenodeMachine: (value: string) => void;
  onSeedArtifacts: () => void;
  onExportArtifacts: () => void;
  onExportRenodeBundle: () => void;
  onOpenRenodeProfile: () => void;
  onOpenRenodeResc: () => void;
  onOpenRobotTests: () => void;
}

export function WorkspaceOutputZone({
  outputChannels,
  activeOutputChannel,
  executionWorkbench,
  followOutput,
  severityFilter,
  projectStatus,
  projectBusy,
  projectFilePath,
  projectDocument,
  pinAssignments,
  onSelectChannel,
  onSelectSeverityFilter,
  onToggleFollow,
  onCopyVisibleEntries,
  onResetView,
  onNavigateEntry,
  onSelectRenodeMachine,
  onSeedArtifacts,
  onExportArtifacts,
  onExportRenodeBundle,
  onOpenRenodeProfile,
  onOpenRenodeResc,
  onOpenRobotTests,
}: WorkspaceOutputZoneProps) {
  const tabRefs = useRef(new Map<string, HTMLButtonElement>());
  const visibleEntries = activeOutputChannel?.entries.filter((entry) => severityFilter === "all" || entry.severity === severityFilter) ?? [];
  const activeTabIndex = Math.max(outputChannels.findIndex((channel) => channel.id === activeOutputChannel?.id), 0);
  const entrySections: VirtualizedTreeListSection<(typeof visibleEntries)[number]>[] = ["error", "warning", "success", "info"].map((severity) => ({
    id: severity,
    label: severity[0].toUpperCase() + severity.slice(1),
    items: visibleEntries.filter((entry) => entry.severity === severity),
    meta: `${visibleEntries.filter((entry) => entry.severity === severity).length} entries`,
    collapsible: true,
    defaultCollapsed: severityFilter === "all" && (severity === "info" || severity === "success"),
  }));

  return (
    <div className="workspace-output-zone">
      <section className="workspace-execution-workbench" aria-label="Execution workbench">
        <div className="workspace-execution-workbench__header">
          <div>
            <strong>Execution workbench</strong>
            <span>Move from generation to demo export and test review without leaving the workspace shell.</span>
          </div>
          <StatusChip label={executionWorkbench.support.title} tone={executionWorkbench.support.tone} />
        </div>

        <div className={`workspace-execution-workbench__support workspace-execution-workbench__support--${executionWorkbench.support.tone}`}>
          <strong>{executionWorkbench.support.title}</strong>
          <p>{executionWorkbench.support.detail}</p>
        </div>

        <div className="workspace-execution-workbench__grid">
          {executionWorkbench.tasks.map((task) => (
            <article key={task.id} className="workspace-execution-task">
              <div className="workspace-execution-task__meta">
                <div>
                  <strong>{task.label}</strong>
                  <span>{task.detail}</span>
                </div>
                <StatusChip
                  label={task.status}
                  tone={task.status === "ready" ? "success" : task.status === "blocked" ? "warning" : task.status === "running" ? "info" : "neutral"}
                />
              </div>
              {task.id === "simulation" ? (
                <label className="workspace-output-zone__filter workspace-output-zone__filter--machine">
                  <span>Renode machine</span>
                  <select
                    aria-label="Execution Renode machine"
                    value={executionWorkbench.selectedMachine}
                    onChange={(event) => onSelectRenodeMachine(event.target.value)}
                    disabled={projectBusy}
                  >
                    {executionWorkbench.machineOptions.map((option) => (
                      <option key={option.value || "none"} value={option.value}>
                        {option.recommended ? `${option.label} (recommended)` : option.label}
                      </option>
                    ))}
                  </select>
                </label>
              ) : null}
              <p className="workspace-execution-task__log">Latest log: {task.latestLog}</p>
              <div className="workspace-execution-task__actions">
                {task.id === "build" ? (
                  <>
                    <button type="button" className="shell-button" onClick={onSeedArtifacts} disabled={projectBusy}>
                      Seed Artifacts
                    </button>
                    <button type="button" className="shell-button shell-button--ghost" onClick={() => onSelectChannel("build")}>
                      Open Build Log
                    </button>
                    <button type="button" className="shell-button" onClick={onExportArtifacts} disabled={projectBusy}>
                      Export Artifacts
                    </button>
                  </>
                ) : null}
                {task.id === "simulation" ? (
                  <>
                    <button type="button" className="shell-button shell-button--ghost" onClick={onOpenRenodeProfile}>
                      Open Renode Profile
                    </button>
                    <button type="button" className="shell-button shell-button--ghost" onClick={onOpenRenodeResc}>
                      Open RESC Script
                    </button>
                    <button type="button" className="shell-button" onClick={onExportRenodeBundle} disabled={projectBusy}>
                      Export Demo Bundle
                    </button>
                  </>
                ) : null}
                {task.id === "tests" ? (
                  <>
                    <button type="button" className="shell-button shell-button--ghost" onClick={onOpenRobotTests}>
                      Open Robot Tests
                    </button>
                    <button type="button" className="shell-button shell-button--ghost" onClick={() => onSelectChannel("tests")}>
                      Open Test Log
                    </button>
                    <button type="button" className="shell-button shell-button--ghost" onClick={() => onSelectChannel("diagnostics")}>
                      Review Diagnostics
                    </button>
                  </>
                ) : null}
              </div>
            </article>
          ))}
        </div>
      </section>

      <div
        className="workspace-output-zone__toolbar"
        role="tablist"
        aria-label="Execution output channels"
        onKeyDown={(event) => {
          if (!["ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key)) {
            return;
          }

          event.preventDefault();
          if (!outputChannels.length) {
            return;
          }

          let nextIndex = activeTabIndex;
          if (event.key === "ArrowRight") {
            nextIndex = (activeTabIndex + 1) % outputChannels.length;
          } else if (event.key === "ArrowLeft") {
            nextIndex = (activeTabIndex - 1 + outputChannels.length) % outputChannels.length;
          } else if (event.key === "Home") {
            nextIndex = 0;
          } else if (event.key === "End") {
            nextIndex = outputChannels.length - 1;
          }

          const nextChannel = outputChannels[nextIndex];
          if (!nextChannel) {
            return;
          }

          onSelectChannel(nextChannel.id);
          requestAnimationFrame(() => tabRefs.current.get(nextChannel.id)?.focus());
        }}
      >
        <div className="workspace-output-zone__tabs">
          {outputChannels.map((channel) => (
            <button
              key={channel.id}
              ref={(node) => {
                if (node) {
                  tabRefs.current.set(channel.id, node);
                  return;
                }

                tabRefs.current.delete(channel.id);
              }}
              id={`workspace-output-tab-${channel.id}`}
              type="button"
              role="tab"
              aria-selected={channel.id === activeOutputChannel?.id}
              aria-controls={`workspace-output-panel-${channel.id}`}
              tabIndex={channel.id === activeOutputChannel?.id ? 0 : -1}
              className={`workspace-output-zone__tab workspace-output-zone__tab--${channel.tone}`}
              onClick={() => onSelectChannel(channel.id)}
            >
              <span>{channel.label}</span>
              <StatusChip
                label={channel.badge}
                tone={channel.tone === "success" ? "success" : channel.tone === "warning" ? "warning" : "neutral"}
              />
            </button>
          ))}
        </div>
        <div className="workspace-output-zone__actions">
          <label className="workspace-output-zone__filter">
            <span>Severity</span>
            <select value={severityFilter} onChange={(event) => onSelectSeverityFilter(event.target.value as "all" | "info" | "success" | "warning" | "error")}>
              <option value="all">All</option>
              <option value="info">Info</option>
              <option value="success">Success</option>
              <option value="warning">Warning</option>
              <option value="error">Error</option>
            </select>
          </label>
          <button type="button" className="shell-button" onClick={onToggleFollow}>
            {followOutput ? "Follow Tail On" : "Follow Tail Off"}
          </button>
          <button type="button" className="shell-button" onClick={onCopyVisibleEntries}>
            Copy Visible
          </button>
          <button type="button" className="shell-button" onClick={onResetView}>
            Reset View
          </button>
        </div>
      </div>

      {activeOutputChannel ? (
        <div id={`workspace-output-panel-${activeOutputChannel.id}`} className="workspace-output-zone__content" role="tabpanel" aria-labelledby={`workspace-output-tab-${activeOutputChannel.id}`}>
          <div className="workspace-output-zone__header">
            <div>
              <strong>{activeOutputChannel.label}</strong>
              <span>{followOutput ? "Follow-tail enabled for the active channel." : "Follow-tail paused for review."}</span>
            </div>
            <div className={`project-flow__status project-flow__status--${projectStatus.tone}`} role="status" aria-live="polite" aria-atomic="true">
              {projectStatus.message}
            </div>
          </div>

          <VirtualizedTreeList
            ariaLabel={`${activeOutputChannel.label} entries`}
            sections={entrySections}
            getItemId={(entry) => entry.id}
            estimatedRowHeight={98}
            overscan={6}
            containerRole="log"
            rowRole={undefined}
            viewportClassName="workspace-output-zone__entries"
            emptyState={<p className="workspace-output-zone__empty">No output entries match the active severity filter.</p>}
            renderItem={({ item: entry }) => (
              <article className={`workspace-output-entry workspace-output-entry--${entry.severity}`}>
                <div className="workspace-output-entry__meta">
                  <StatusChip
                    label={entry.timestamp}
                    tone={entry.severity === "success" ? "success" : entry.severity === "warning" ? "warning" : entry.severity === "error" ? "error" : "info"}
                  />
                  <strong>{entry.summary}</strong>
                  {entry.navigation ? (
                    <button type="button" className="shell-button shell-button--ghost workspace-output-entry__navigate" onClick={() => onNavigateEntry(entry)}>
                      Open {entry.navigation.label}
                    </button>
                  ) : null}
                </div>
                <p>{entry.detail}</p>
              </article>
            )}
          />

          <dl className="shell-key-values shell-key-values--compact workspace-output-zone__summary">
            <div>
              <dt>Project file</dt>
              <dd>{projectFilePath || "Pending"}</dd>
            </div>
            <div>
              <dt>AppBench target</dt>
              <dd>{projectDocument.renode.appbench_target || "Not configured"}</dd>
            </div>
            <div>
              <dt>Protocol selection</dt>
              <dd>{projectDocument.protocol_editor.selectedEntryId || "None"}</dd>
            </div>
            <div>
              <dt>Unresolved pins</dt>
              <dd>{pinAssignments.summary.unresolvedCount}</dd>
            </div>
          </dl>
        </div>
      ) : null}
    </div>
  );
}
