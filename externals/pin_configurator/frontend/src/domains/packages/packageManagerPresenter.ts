import type { ZephyrCatalogMcuItem } from "../../contracts/api";
import type { ProjectShellController } from "../../project/useProjectShellController";

export interface PackageJobViewModel {
  jobId: string;
  title: string;
  detail: string;
  status: string;
  tone: "neutral" | "success" | "warning";
  raw: string;
}

export interface PackageManagerCommandApi {
  selectJob: (jobId: string) => void;
  removeJob: (jobId: string) => void;
  importCatalogMcu: (item: ZephyrCatalogMcuItem) => void;
}

export interface PackageManagerPresenter extends PackageManagerCommandApi {
  jobs: PackageJobViewModel[];
  selectedJobId: string;
  selectedJob: PackageJobViewModel | null;
}

type PackageManagerPresenterInput = Pick<ProjectShellController, "projectDocument" | "selectMcuJob" | "removeMcuJob" | "upsertMcuJob">;

function asRecord(value: unknown): Record<string, unknown> {
  return value && typeof value === "object" && !Array.isArray(value) ? (value as Record<string, unknown>) : {};
}

function textFrom(value: unknown, fallback = ""): string {
  if (typeof value === "string") {
    return value;
  }
  if (typeof value === "number" || typeof value === "boolean" || typeof value === "bigint") {
    return String(value);
  }
  return fallback;
}

function inferMcuPart(item: ZephyrCatalogMcuItem): string {
  return item.socs[0] || item.name;
}

function normalizePackageJob(job: unknown): PackageJobViewModel | null {
  const source = asRecord(job);
  const jobId = textFrom(source.job_id);
  if (!jobId) {
    return null;
  }

  const title = textFrom(source.part_number) || textFrom(source.label) || textFrom(source.name) || jobId;
  const status = textFrom(source.status) || textFrom(source.state) || "queued";
  const detail = textFrom(source.vendor)
    || textFrom(source.package)
    || textFrom(source.board_path)
    || textFrom(source.source)
    || "Package manager job persisted in the canonical project document.";
  const tone = /done|ready|success/i.test(status)
    ? "success"
    : /error|failed|warning/i.test(status)
      ? "warning"
      : "neutral";

  return {
    jobId,
    title,
    detail,
    status,
    tone,
    raw: JSON.stringify(source, null, 2),
  };
}

export function createPackageManagerPresenter({ projectDocument, selectMcuJob, removeMcuJob, upsertMcuJob }: PackageManagerPresenterInput): PackageManagerPresenter {
  const jobs = projectDocument.mcu_jobs
    .map(normalizePackageJob)
    .filter((job): job is PackageJobViewModel => job !== null);
  const selectedJob = jobs.find((job) => job.jobId === projectDocument.mcu_selected) ?? jobs[0] ?? null;

  return {
    jobs,
    selectedJobId: selectedJob?.jobId ?? "",
    selectedJob,
    selectJob: selectMcuJob,
    removeJob: removeMcuJob,
    importCatalogMcu(item) {
      upsertMcuJob({
        job_id: `catalog:${item.key}`,
        label: item.label,
        name: item.name,
        part_number: inferMcuPart(item),
        vendor: item.vendor,
        board_path: item.board_path,
        status: "catalog-imported",
        source: "zephyr-catalog",
      });
    },
  };
}