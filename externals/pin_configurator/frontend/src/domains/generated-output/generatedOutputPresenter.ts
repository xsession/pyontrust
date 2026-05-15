import { formatGeneratedFragments } from "../../project/generatedArtifacts";
import type { ProjectShellController } from "../../project/useProjectShellController";

export interface GeneratedOutputCommandApi {
  updateOverlay: (value: string) => void;
  updateConf: (value: string) => void;
  seedArtifacts: () => void;
  clearArtifacts: () => void;
  exportArtifacts: () => void;
}

export interface GeneratedOutputPresenter extends GeneratedOutputCommandApi {
  generatedOverlay: string;
  generatedConf: string;
  generatedFragments: string;
}

type GeneratedOutputPresenterInput = Pick<
  ProjectShellController,
  "projectDocument" | "updateGeneratedOverlay" | "updateGeneratedConf" | "seedGeneratedArtifacts" | "clearGeneratedArtifacts" | "exportGeneratedArtifacts"
>;

export function createGeneratedOutputPresenter({
  projectDocument,
  updateGeneratedOverlay,
  updateGeneratedConf,
  seedGeneratedArtifacts,
  clearGeneratedArtifacts,
  exportGeneratedArtifacts,
}: GeneratedOutputPresenterInput): GeneratedOutputPresenter {
  return {
    generatedOverlay: projectDocument.generated_overlay,
    generatedConf: projectDocument.generated_conf,
    generatedFragments: formatGeneratedFragments(projectDocument.generated_fragments),
    updateOverlay: updateGeneratedOverlay,
    updateConf: updateGeneratedConf,
    seedArtifacts: seedGeneratedArtifacts,
    clearArtifacts: clearGeneratedArtifacts,
    exportArtifacts: exportGeneratedArtifacts,
  };
}