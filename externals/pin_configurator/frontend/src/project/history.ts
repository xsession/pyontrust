import type { ProjectDocument } from "./projectDocument";
import { applyProjectDocumentCommand, type ProjectDocumentCommand } from "./commands";

export interface ProjectDocumentHistory {
  past: ProjectDocument[];
  present: ProjectDocument;
  future: ProjectDocument[];
}

export function createProjectDocumentHistory(initialDocument: ProjectDocument): ProjectDocumentHistory {
  return {
    past: [],
    present: initialDocument,
    future: [],
  };
}

export function applyProjectDocumentHistoryCommand(
  history: ProjectDocumentHistory,
  command: ProjectDocumentCommand,
): ProjectDocumentHistory {
  const nextDocument = applyProjectDocumentCommand(history.present, command);

  if (nextDocument === history.present) {
    return history;
  }

  return {
    past: [...history.past, history.present],
    present: nextDocument,
    future: [],
  };
}

export function replaceProjectDocumentHistory(document: ProjectDocument): ProjectDocumentHistory {
  return createProjectDocumentHistory(document);
}

export function undoProjectDocumentHistory(history: ProjectDocumentHistory): ProjectDocumentHistory {
  const previousDocument = history.past.at(-1);

  if (!previousDocument) {
    return history;
  }

  return {
    past: history.past.slice(0, -1),
    present: previousDocument,
    future: [history.present, ...history.future],
  };
}

export function redoProjectDocumentHistory(history: ProjectDocumentHistory): ProjectDocumentHistory {
  const [nextDocument, ...remainingFuture] = history.future;

  if (!nextDocument) {
    return history;
  }

  return {
    past: [...history.past, history.present],
    present: nextDocument,
    future: remainingFuture,
  };
}

export function canUndoProjectDocumentHistory(history: ProjectDocumentHistory): boolean {
  return history.past.length > 0;
}

export function canRedoProjectDocumentHistory(history: ProjectDocumentHistory): boolean {
  return history.future.length > 0;
}