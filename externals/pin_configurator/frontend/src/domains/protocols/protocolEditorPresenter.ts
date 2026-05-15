import type { ProtocolFieldValue } from "../../contracts/api";
import type { ProjectShellController } from "../../project/useProjectShellController";

export interface ProtocolEditorCommandApi {
  addEntry: (templateId: string) => void;
  selectEntry: (entryId: string) => void;
  removeEntry: (entryId: string) => void;
  toggleEntry: (entryId: string, enabled: boolean) => void;
  updateEntryValue: (entryId: string, fieldKey: string, value: ProtocolFieldValue) => void;
}

export interface ProtocolEditorPresenter extends ProtocolEditorCommandApi {
  document: ProjectShellController["projectDocument"]["protocol_editor"];
}

type ProtocolEditorPresenterInput = Pick<
  ProjectShellController,
  "projectDocument" | "addProtocolEntry" | "selectProtocolEntry" | "removeProtocolEntry" | "toggleProtocolEntry" | "updateProtocolEntryValue"
>;

export function createProtocolEditorPresenter({
  projectDocument,
  addProtocolEntry,
  selectProtocolEntry,
  removeProtocolEntry,
  toggleProtocolEntry,
  updateProtocolEntryValue,
}: ProtocolEditorPresenterInput): ProtocolEditorPresenter {
  return {
    document: projectDocument.protocol_editor,
    addEntry: addProtocolEntry,
    selectEntry: selectProtocolEntry,
    removeEntry: removeProtocolEntry,
    toggleEntry: toggleProtocolEntry,
    updateEntryValue: updateProtocolEntryValue,
  };
}