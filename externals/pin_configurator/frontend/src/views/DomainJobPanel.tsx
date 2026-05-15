import Editor from "@monaco-editor/react";
import { DiagnosticBadge } from "../shared/ui/feedback/DiagnosticBadge";
import { EmptyState } from "../shared/ui/feedback/EmptyState";
import { InspectorSection } from "../shared/ui/inspectors/InspectorSection";
import { VirtualizedTreeList, type VirtualizedTreeListSection } from "../shared/ui/virtualized/VirtualizedTreeList";
import type { PackageJobViewModel } from "../domains/packages/packageManagerPresenter";
import type { SensorJobViewModel } from "../domains/sensors/sensorParserPresenter";

type DomainJob = PackageJobViewModel | SensorJobViewModel;

interface DomainJobPanelProps {
  title: string;
  summary: string;
  jobs: DomainJob[];
  selectedJobId: string;
  selectedJob: DomainJob | null;
  onSelectJob: (jobId: string) => void;
  onRemoveJob: (jobId: string) => void;
}

export function DomainJobPanel({ title, summary, jobs, selectedJobId, selectedJob, onSelectJob, onRemoveJob }: DomainJobPanelProps) {
  const sections: VirtualizedTreeListSection<DomainJob>[] = [
    { id: "warning", label: "Needs review", items: jobs.filter((job) => job.tone === "warning"), meta: `${jobs.filter((job) => job.tone === "warning").length} jobs` },
    { id: "success", label: "Ready", items: jobs.filter((job) => job.tone === "success"), meta: `${jobs.filter((job) => job.tone === "success").length} jobs`, collapsible: true },
    { id: "neutral", label: "Queued", items: jobs.filter((job) => job.tone === "neutral"), meta: `${jobs.filter((job) => job.tone === "neutral").length} jobs`, collapsible: true },
  ];

  return (
    <div className="domain-panel domain-panel--split">
      <InspectorSection
        title={title}
        summary={summary}
        actions={<DiagnosticBadge label={`${jobs.length} jobs`} tone="info" />}
      >
        <VirtualizedTreeList
          ariaLabel={`${title} jobs`}
          sections={sections}
          getItemId={(job) => job.jobId}
          estimatedRowHeight={112}
          overscan={5}
          viewportClassName="domain-list-viewport"
          emptyState={<EmptyState title="No persisted jobs" detail="Catalog imports or backend parser results will appear here once written into the canonical project document." compact />}
          renderItem={({ item: job }) => (
            <div className={job.jobId === selectedJobId ? "domain-list__item domain-list__item--selected" : "domain-list__item"}>
              <button type="button" className="domain-list__select" onClick={() => onSelectJob(job.jobId)}>
                <strong>{job.title}</strong>
                <span>{job.detail}</span>
              </button>
              <div className="domain-list__header domain-list__header--compact">
                <DiagnosticBadge label={job.status} tone={job.tone === "neutral" ? "info" : job.tone} />
                <button type="button" className="shell-button shell-button--ghost" onClick={() => onRemoveJob(job.jobId)}>
                  Remove
                </button>
              </div>
            </div>
          )}
        />
      </InspectorSection>

      <InspectorSection
        title={selectedJob ? `${selectedJob.title} payload` : "Job payload"}
        summary="The presenter keeps the selected job inspectable without reaching back into legacy tab globals."
      >
        {!selectedJob ? <EmptyState title="No job selected" detail="Select a persisted job to inspect the canonical payload." compact /> : null}
        {selectedJob ? (
          <div className="domain-editor">
            <Editor
              height="100%"
              defaultLanguage="json"
              theme="light"
              value={selectedJob.raw}
              options={{
                minimap: { enabled: false },
                fontSize: 13,
                lineNumbersMinChars: 3,
                padding: { top: 14, bottom: 14 },
                readOnly: true,
                scrollBeyondLastLine: false,
              }}
            />
          </div>
        ) : null}
      </InspectorSection>
    </div>
  );
}