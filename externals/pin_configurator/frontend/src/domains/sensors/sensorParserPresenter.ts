import type { ZephyrCatalogSensorItem } from "../../contracts/api";
import type { ProjectShellController } from "../../project/useProjectShellController";

export interface SensorJobViewModel {
  jobId: string;
  title: string;
  detail: string;
  status: string;
  tone: "neutral" | "success" | "warning";
  raw: string;
}

export interface SensorParserCommandApi {
  selectJob: (jobId: string) => void;
  removeJob: (jobId: string) => void;
  importCatalogSensor: (item: ZephyrCatalogSensorItem) => void;
}

export interface SensorParserPresenter extends SensorParserCommandApi {
  jobs: SensorJobViewModel[];
  selectedJobId: string;
  selectedJob: SensorJobViewModel | null;
}

type SensorParserPresenterInput = Pick<ProjectShellController, "projectDocument" | "selectSensorJob" | "removeSensorJob" | "upsertSensorJob">;

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

function inferSensorPart(item: ZephyrCatalogSensorItem): string {
  const compatible = item.compatible || item.name || item.label;
  return compatible.includes(",") ? compatible.split(",", 2)[1]?.toUpperCase() || compatible : compatible;
}

function normalizeSensorJob(job: unknown): SensorJobViewModel | null {
  const source = asRecord(job);
  const jobId = textFrom(source.job_id);
  if (!jobId) {
    return null;
  }

  const title = textFrom(source.device_name)
    || textFrom(source.part_number)
    || textFrom(source.label)
    || jobId;
  const status = textFrom(source.status) || textFrom(source.state) || "queued";
  const detail = textFrom(source.compatible)
    || textFrom(source.vendor)
    || textFrom(source.source)
    || textFrom(source.binding_path)
    || "Sensor parser job persisted in the canonical project document.";
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

export function createSensorParserPresenter({ projectDocument, selectSensorJob, removeSensorJob, upsertSensorJob }: SensorParserPresenterInput): SensorParserPresenter {
  const jobs = projectDocument.sensor_jobs
    .map(normalizeSensorJob)
    .filter((job): job is SensorJobViewModel => job !== null);
  const selectedJob = jobs.find((job) => job.jobId === projectDocument.sensor_selected) ?? jobs[0] ?? null;

  return {
    jobs,
    selectedJobId: selectedJob?.jobId ?? "",
    selectedJob,
    selectJob: selectSensorJob,
    removeJob: removeSensorJob,
    importCatalogSensor(item) {
      upsertSensorJob({
        job_id: `catalog:${item.key}`,
        label: item.label,
        device_name: item.label || item.name,
        part_number: inferSensorPart(item),
        compatible: item.compatible,
        status: "catalog-imported",
        source: "zephyr-catalog",
        binding_path: item.binding_paths[0] || "",
      });
    },
  };
}