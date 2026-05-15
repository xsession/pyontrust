import { DiffEditor, Editor } from "@monaco-editor/react";
import { useEffect, useMemo, useRef, useState } from "react";
import type { editor as MonacoEditor } from "monaco-editor";
import type * as Monaco from "monaco-editor";
import type { ArtifactReviewDocument } from "../../project/artifactReview";

interface ArtifactReviewPanelProps {
  document: ArtifactReviewDocument;
  focusRequest?: { panelId: string; nonce: number; lineNumber?: number; column?: number } | null;
  onSave?: (value: string) => void;
}

function downloadTextFile(fileName: string, content: string) {
  const blob = new Blob([content], { type: "text/plain;charset=utf-8" });
  const objectUrl = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = objectUrl;
  anchor.download = fileName;
  anchor.click();
  URL.revokeObjectURL(objectUrl);
}

function toMonacoMarkers(markers: ArtifactReviewDocument["markers"]): MonacoEditor.IMarkerData[] {
  return markers.map((marker) => ({
    severity: marker.severity,
    message: marker.message,
    startLineNumber: marker.lineNumber,
    startColumn: marker.column ?? 1,
    endLineNumber: marker.endLineNumber ?? marker.lineNumber,
    endColumn: marker.endColumn ?? Number.MAX_SAFE_INTEGER,
  }));
}

export function ArtifactReviewPanel({ document, focusRequest, onSave }: ArtifactReviewPanelProps) {
  const [draft, setDraft] = useState(document.content);
  const [diffOpen, setDiffOpen] = useState(false);
  const editorRef = useRef<MonacoEditor.IStandaloneCodeEditor | MonacoEditor.IStandaloneDiffEditor | null>(null);
  const monacoRef = useRef<typeof import("monaco-editor") | null>(null);
  const dirty = draft !== document.content;
  const hasDiff = Boolean(document.baselineContent.trim().length);

  useEffect(() => {
    setDraft(document.content);
  }, [document.content, document.id]);

  useEffect(() => {
    const monaco = monacoRef.current;
    const editor = editorRef.current;
    if (!monaco || !editor) {
      return;
    }

    const model = "getModifiedEditor" in editor ? editor.getModifiedEditor().getModel() : editor.getModel();
    if (!model) {
      return;
    }

    monaco.editor.setModelMarkers(model, `artifact-review:${document.id}`, toMonacoMarkers(document.markers));
  }, [document.id, document.markers, draft]);

  useEffect(() => {
    if (!focusRequest || focusRequest.panelId !== document.panelId || focusRequest.nonce < 1) {
      return;
    }

    const editor = editorRef.current;
    if (!editor) {
      return;
    }

    const targetLine = focusRequest.lineNumber ?? 1;
    const targetColumn = focusRequest.column ?? 1;
    const targetEditor = "getModifiedEditor" in editor ? editor.getModifiedEditor() : editor;
    targetEditor.revealLineInCenter(targetLine);
    targetEditor.setPosition({ lineNumber: targetLine, column: targetColumn });
    targetEditor.focus();
  }, [document.panelId, focusRequest]);

  const actionSummary = useMemo(() => {
    if (document.editable) {
      return dirty ? "Unsaved draft changes" : "Saved to the project document";
    }

    return "Derived preview";
  }, [dirty, document.editable]);

  return (
    <div className="dock-panel dock-panel--editor dock-artifact-panel">
      <div className="dock-artifact-panel__toolbar">
        <div className="dock-artifact-panel__summary">
          <strong>{document.fileName}</strong>
          <span>{`${document.ownerLabel} · ${actionSummary}`}</span>
        </div>
        <div className="dock-artifact-panel__actions">
          {hasDiff ? (
            <button type="button" className="shell-button shell-button--ghost" onClick={() => setDiffOpen((current) => !current)}>
              {diffOpen ? "Single" : "Diff"}
            </button>
          ) : null}
          <button
            type="button"
            className="shell-button shell-button--ghost"
            onClick={() => {
              if (typeof navigator !== "undefined" && navigator.clipboard) {
                void navigator.clipboard.writeText(draft);
              }
            }}
          >
            Copy
          </button>
          <button type="button" className="shell-button shell-button--ghost" onClick={() => downloadTextFile(document.fileName, draft)}>
            Export
          </button>
          {document.editable ? (
            <button type="button" className="shell-button" onClick={() => onSave?.(draft)} disabled={!dirty || !onSave}>
              Save
            </button>
          ) : null}
        </div>
      </div>

      {diffOpen && hasDiff ? (
        <DiffEditor
          height="100%"
          original={document.baselineContent}
          modified={draft}
          language={document.language}
          theme="light"
          options={{
            minimap: { enabled: false },
            fontSize: 13,
            lineNumbersMinChars: 3,
            padding: { top: 14, bottom: 14 },
            readOnly: !document.editable,
            scrollBeyondLastLine: false,
          }}
          onMount={(editor: MonacoEditor.IStandaloneDiffEditor, monaco: typeof Monaco) => {
            editorRef.current = editor;
            monacoRef.current = monaco;
          }}
        />
      ) : (
        <Editor
          height="100%"
          defaultLanguage={document.language}
          language={document.language}
          theme="light"
          value={draft}
          onChange={(value) => setDraft(value ?? "")}
          options={{
            minimap: { enabled: false },
            fontSize: 13,
            lineNumbersMinChars: 3,
            padding: { top: 14, bottom: 14 },
            readOnly: !document.editable,
            scrollBeyondLastLine: false,
          }}
          onMount={(editor: MonacoEditor.IStandaloneCodeEditor, monaco: typeof Monaco) => {
            editorRef.current = editor;
            monacoRef.current = monaco;
          }}
        />
      )}
    </div>
  );
}
