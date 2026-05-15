import {
  addProtocolEntry,
  applyBoardToProjectDocument,
  removeProtocolEntry,
  selectProtocolEntry,
  toggleProtocolEntry,
  updateProtocolEntryValue,
  type BoardAltFunction,
  type ProtocolFieldValue,
} from "../contracts/api";
import type { ProjectDocument, RenodeProfile } from "./projectDocument";

export type ProjectDocumentCommand =
  | {
      type: "apply-board-selection";
      boardId: string;
      seededArtifacts?: {
        overlay: string;
        conf: string;
        fragments: Record<string, unknown>;
      };
    }
  | {
      type: "update-renode-field";
      field: keyof RenodeProfile;
      value: RenodeProfile[keyof RenodeProfile];
    }
  | {
      type: "add-protocol-entry";
      templateId: string;
    }
  | {
      type: "select-protocol-entry";
      entryId: string;
    }
  | {
      type: "remove-protocol-entry";
      entryId: string;
    }
  | {
      type: "toggle-protocol-entry";
      entryId: string;
      enabled: boolean;
    }
  | {
      type: "update-protocol-entry-value";
      entryId: string;
      fieldKey: string;
      value: ProtocolFieldValue;
    }
  | {
      type: "update-generated-overlay";
      value: string;
    }
  | {
      type: "update-generated-conf";
      value: string;
    }
  | {
      type: "replace-lvgl-layout";
      layout: Record<string, unknown>;
    }
  | {
      type: "clear-pin-assignment";
      pinNumber: string;
    }
  | {
      type: "assign-pin-alt-function";
      pinNumber: string;
      altFunction: BoardAltFunction;
    }
  | {
      type: "update-pin-boolean-property";
      pinNumber: string;
      propertyKey: string;
      value: boolean;
    }
  | {
      type: "set-peripheral-enabled";
      peripheral: string;
      enabled: boolean;
    }
  | {
      type: "set-peripheral-core";
      peripheral: string;
      coreId: string;
    }
  | {
      type: "set-external-device-selected";
      deviceId: string;
      selected: boolean;
    }
  | {
      type: "set-external-device-bus";
      deviceId: string;
      bus: string;
    }
  | {
      type: "upsert-sensor-job";
      job: Record<string, unknown>;
      select?: boolean;
    }
  | {
      type: "remove-sensor-job";
      jobId: string;
    }
  | {
      type: "select-sensor-job";
      jobId: string;
    }
  | {
      type: "upsert-mcu-job";
      job: Record<string, unknown>;
      select?: boolean;
    }
  | {
      type: "remove-mcu-job";
      jobId: string;
    }
  | {
      type: "select-mcu-job";
      jobId: string;
    }
  | {
      type: "seed-generated-artifacts";
      overlay: string;
      conf: string;
      fragments: Record<string, unknown>;
    }
  | {
      type: "clear-generated-artifacts";
    }
  | {
      type: "replace-project-document";
      document: ProjectDocument;
    };

export function applyProjectDocumentCommand(
  current: ProjectDocument,
  command: ProjectDocumentCommand,
): ProjectDocument {
  const normalizeJobId = (job: Record<string, unknown>): string => {
    const rawJobId = job.job_id;
    return typeof rawJobId === "string"
      ? rawJobId.trim()
      : typeof rawJobId === "number" || typeof rawJobId === "boolean" || typeof rawJobId === "bigint"
        ? String(rawJobId)
        : "";
  };

  const upsertJob = (jobs: unknown[], job: Record<string, unknown>) => {
    const jobId = normalizeJobId(job);
    if (!jobId) {
      return jobs;
    }

    const nextJobs = [...jobs];
    const existingIndex = nextJobs.findIndex((entry) => {
      if (!entry || typeof entry !== "object" || Array.isArray(entry)) {
        return false;
      }

      return normalizeJobId(entry as Record<string, unknown>) === jobId;
    });

    if (existingIndex >= 0) {
      nextJobs.splice(existingIndex, 1, job);
      return nextJobs;
    }

    nextJobs.push(job);
    return nextJobs;
  };

  switch (command.type) {
    case "apply-board-selection": {
      const next = applyBoardToProjectDocument(current, command.boardId);

      if (!command.seededArtifacts) {
        return next;
      }

      return {
        ...next,
        generated_overlay: command.seededArtifacts.overlay,
        generated_conf: command.seededArtifacts.conf,
        generated_fragments: command.seededArtifacts.fragments,
      };
    }

    case "update-renode-field":
      return {
        ...current,
        renode: {
          ...current.renode,
          [command.field]: command.value,
        },
      };

    case "add-protocol-entry":
      return {
        ...current,
        protocol_editor: addProtocolEntry(current.protocol_editor, command.templateId),
      };

    case "select-protocol-entry":
      return {
        ...current,
        protocol_editor: selectProtocolEntry(current.protocol_editor, command.entryId),
      };

    case "remove-protocol-entry":
      return {
        ...current,
        protocol_editor: removeProtocolEntry(current.protocol_editor, command.entryId),
      };

    case "toggle-protocol-entry":
      return {
        ...current,
        protocol_editor: toggleProtocolEntry(current.protocol_editor, command.entryId, command.enabled),
      };

    case "update-protocol-entry-value":
      return {
        ...current,
        protocol_editor: updateProtocolEntryValue(current.protocol_editor, command.entryId, command.fieldKey, command.value),
      };

    case "update-generated-overlay":
      return {
        ...current,
        generated_overlay: command.value,
      };

    case "update-generated-conf":
      return {
        ...current,
        generated_conf: command.value,
      };

    case "replace-lvgl-layout":
      return {
        ...current,
        lvgl_layout: { ...command.layout },
      };

    case "clear-pin-assignment": {
      const nextPinStates = { ...current.pin_states };
      delete nextPinStates[command.pinNumber];

      return {
        ...current,
        pin_states: nextPinStates,
      };
    }

    case "assign-pin-alt-function": {
      const currentPinState = current.pin_states[command.pinNumber] ?? {};

      return {
        ...current,
        pin_states: {
          ...current.pin_states,
          [command.pinNumber]: {
            ...currentPinState,
            af: {
              function_id: command.altFunction.function_id,
              pincm: command.altFunction.pincm,
              name: command.altFunction.name,
              peripheral: command.altFunction.peripheral,
              signal: command.altFunction.signal,
              direction: command.altFunction.direction,
            },
          },
        },
      };
    }

    case "update-pin-boolean-property": {
      const currentPinState = current.pin_states[command.pinNumber] ?? {};
      const nextProps = {
        ...(currentPinState.props ?? {}),
        [command.propertyKey]: command.value,
      };

      return {
        ...current,
        pin_states: {
          ...current.pin_states,
          [command.pinNumber]: {
            ...currentPinState,
            props: nextProps,
          },
        },
      };
    }

    case "set-peripheral-enabled":
      return {
        ...current,
        periph_states: {
          ...current.periph_states,
          [command.peripheral]: command.enabled,
        },
      };

    case "set-peripheral-core":
      return {
        ...current,
        periph_core_states: {
          ...current.periph_core_states,
          [command.peripheral]: command.coreId,
        },
      };

    case "set-external-device-selected": {
      const currentDevice = current.external_device_states[command.deviceId] ?? { selected: false, bus: "" };

      return {
        ...current,
        external_device_states: {
          ...current.external_device_states,
          [command.deviceId]: {
            ...currentDevice,
            selected: command.selected,
          },
        },
      };
    }

    case "set-external-device-bus": {
      const currentDevice = current.external_device_states[command.deviceId] ?? { selected: false, bus: "" };

      return {
        ...current,
        external_device_states: {
          ...current.external_device_states,
          [command.deviceId]: {
            ...currentDevice,
            bus: command.bus,
          },
        },
      };
    }

    case "upsert-sensor-job": {
      const nextJobs = upsertJob(current.sensor_jobs, command.job);
      const jobId = normalizeJobId(command.job);

      return {
        ...current,
        sensor_jobs: nextJobs,
        sensor_selected: command.select === false ? current.sensor_selected : jobId || current.sensor_selected,
      };
    }

    case "remove-sensor-job": {
      const nextJobs = current.sensor_jobs.filter((entry) => {
        if (!entry || typeof entry !== "object" || Array.isArray(entry)) {
          return true;
        }

        return normalizeJobId(entry as Record<string, unknown>) !== command.jobId;
      });
      const nextSelectedJob = current.sensor_selected === command.jobId
        ? (() => {
            const firstJob = nextJobs.find((entry) => entry && typeof entry === "object" && !Array.isArray(entry)) as Record<string, unknown> | undefined;
            return firstJob ? normalizeJobId(firstJob) : "";
          })()
        : current.sensor_selected;

      return {
        ...current,
        sensor_jobs: nextJobs,
        sensor_selected: nextSelectedJob,
      };
    }

    case "select-sensor-job":
      return {
        ...current,
        sensor_selected: command.jobId,
      };

    case "upsert-mcu-job": {
      const nextJobs = upsertJob(current.mcu_jobs, command.job);
      const jobId = normalizeJobId(command.job);

      return {
        ...current,
        mcu_jobs: nextJobs,
        mcu_selected: command.select === false ? current.mcu_selected : jobId || current.mcu_selected,
      };
    }

    case "remove-mcu-job": {
      const nextJobs = current.mcu_jobs.filter((entry) => {
        if (!entry || typeof entry !== "object" || Array.isArray(entry)) {
          return true;
        }

        return normalizeJobId(entry as Record<string, unknown>) !== command.jobId;
      });
      const nextSelectedJob = current.mcu_selected === command.jobId
        ? (() => {
            const firstJob = nextJobs.find((entry) => entry && typeof entry === "object" && !Array.isArray(entry)) as Record<string, unknown> | undefined;
            return firstJob ? normalizeJobId(firstJob) : "";
          })()
        : current.mcu_selected;

      return {
        ...current,
        mcu_jobs: nextJobs,
        mcu_selected: nextSelectedJob,
      };
    }

    case "select-mcu-job":
      return {
        ...current,
        mcu_selected: command.jobId,
      };

    case "seed-generated-artifacts":
      return {
        ...current,
        generated_overlay: command.overlay,
        generated_conf: command.conf,
        generated_fragments: command.fragments,
      };

    case "clear-generated-artifacts":
      return {
        ...current,
        generated_overlay: "",
        generated_conf: "",
        generated_fragments: {},
      };

    case "replace-project-document":
      return command.document;
  }
}

export function replayProjectDocumentCommands(
  initial: ProjectDocument,
  commands: readonly ProjectDocumentCommand[],
): ProjectDocument {
  return commands.reduce(
    (current, command) => applyProjectDocumentCommand(current, command),
    initial,
  );
}