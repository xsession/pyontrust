import type { ProjectShellController } from "../../project/useProjectShellController";
import type { RenodeProfile } from "../../project/projectDocument";

export interface RenodeProfileCommandApi {
  updateField: <K extends keyof RenodeProfile>(field: K, value: RenodeProfile[K]) => void;
  exportSimulation: () => void;
}

export interface RenodeProfilePresenter extends RenodeProfileCommandApi {
  profile: RenodeProfile;
}

type RenodeProfilePresenterInput = Pick<ProjectShellController, "projectDocument" | "updateRenodeField" | "exportRenodeSimulation">;

export function createRenodeProfilePresenter({ projectDocument, updateRenodeField, exportRenodeSimulation }: RenodeProfilePresenterInput): RenodeProfilePresenter {
  return {
    profile: projectDocument.renode,
    updateField: updateRenodeField,
    exportSimulation: exportRenodeSimulation,
  };
}