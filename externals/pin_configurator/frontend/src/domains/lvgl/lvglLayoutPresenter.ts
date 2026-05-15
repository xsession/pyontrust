import { useCallback, useEffect, useMemo, useState } from "react";
import type { LvglImportSourceKind } from "../../contracts/api";
import type { ProjectShellController } from "../../project/useProjectShellController";
import { pinConfiguratorApi } from "../../services/pinConfiguratorApi";
import { describeError } from "../../shared/errors/apiError";

export interface LvglLayoutSummary {
  preset: string;
  screenCount: number;
  widgetCount: number;
  startupScreenId: string;
}

export interface LvglLayoutPresenter {
  layout: Record<string, unknown>;
  summary: LvglLayoutSummary;
  draftText: string;
  importSourceKind: LvglImportSourceKind;
  importSourceValue: string;
  exportFilePath: string;
  status: string;
  error: string;
  setDraftText: (value: string) => void;
  applyDraftText: () => void;
  setImportSourceKind: (value: LvglImportSourceKind) => void;
  setImportSourceValue: (value: string) => void;
  importLayout: () => void;
  setExportFilePath: (value: string) => void;
  exportLayout: () => void;
}

function asRecord(value: unknown, message: string): Record<string, unknown> {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    throw new Error(message);
  }
  return value as Record<string, unknown>;
}

function nodeCountForScreen(screen: unknown): number {
  if (!screen || typeof screen !== "object" || Array.isArray(screen)) {
    return 0;
  }

  const nodesValue = (screen as Record<string, unknown>)["nodes"];
  return Array.isArray(nodesValue) ? nodesValue.length : 0;
}

function summarizeLayout(layout: Record<string, unknown>): LvglLayoutSummary {
  const screensValue = layout["screens"];
  const screens: unknown[] = Array.isArray(screensValue) ? screensValue : [];
  const widgetCount = screens.reduce<number>((count, screen) => count + nodeCountForScreen(screen), 0);

  const presetValue = layout["preset"];
  const startupScreenIdValue = layout["startupScreenId"];
  const currentScreenIdValue = layout["currentScreenId"];

  return {
    preset: typeof presetValue === "string" ? presetValue : "custom",
    screenCount: screens.length,
    widgetCount,
    startupScreenId: typeof startupScreenIdValue === "string"
      ? startupScreenIdValue
      : typeof currentScreenIdValue === "string"
        ? currentScreenIdValue
        : "screen_root",
  };
}

type LvglLayoutPresenterInput = Pick<ProjectShellController, "projectDocument" | "updateLvglLayout">;

export function useLvglLayoutPresenter({ projectDocument, updateLvglLayout }: LvglLayoutPresenterInput): LvglLayoutPresenter {
  const layout: Record<string, unknown> = projectDocument.lvgl_layout;
  const [draftText, setDraftText] = useState(() => JSON.stringify(layout, null, 2));
  const [importSourceKind, setImportSourceKind] = useState<LvglImportSourceKind>("json");
  const [importSourceValue, setImportSourceValue] = useState("");
  const [exportFilePath, setExportFilePath] = useState("C:/tmp/pin-configurator-layout");
  const [status, setStatus] = useState("LVGL layout ready.");
  const [error, setError] = useState("");

  useEffect(() => {
    setDraftText(JSON.stringify(layout, null, 2));
  }, [layout]);

  const summary = useMemo(() => summarizeLayout(layout), [layout]);

  const applyDraftText = useCallback(() => {
    try {
      const parsed: unknown = JSON.parse(draftText || "{}");
      const parsedRecord = asRecord(parsed, "LVGL layout JSON must be an object.");
      const nestedLayout = parsedRecord["lvgl_layout"];
      const nextLayout = nestedLayout === undefined
        ? parsedRecord
        : asRecord(nestedLayout, "lvgl_layout must be an object.");

      updateLvglLayout(nextLayout);
      setError("");
      setStatus("Applied LVGL layout JSON to the canonical project document.");
    } catch (parseError) {
      setError(describeError(parseError, "Failed to parse LVGL layout JSON."));
      setStatus("LVGL JSON is invalid.");
    }
  }, [draftText, updateLvglLayout]);

  const importLayout = useCallback(() => {
    const payload = importSourceKind === "json"
      ? { sourceKind: importSourceKind, text: importSourceValue }
      : { sourceKind: importSourceKind, filePath: importSourceValue };

    void pinConfiguratorApi
      .importLvglLayout(payload)
      .then((result) => {
        updateLvglLayout(asRecord(result.layout, "Imported LVGL layout must be an object."));
        setImportSourceValue("");
        setError("");
        setStatus(`Imported LVGL layout from ${result.source}.`);
      })
      .catch((importError) => {
        setError(describeError(importError, "Failed to import LVGL layout."));
        setStatus("LVGL import failed.");
      });
  }, [importSourceKind, importSourceValue, updateLvglLayout]);

  const exportLayout = useCallback(() => {
    void pinConfiguratorApi
      .exportLvglLayout({
        filePath: exportFilePath,
        layout,
      })
      .then((result) => {
        setError("");
        setStatus(`Exported LVGL layout to ${result.file_path}.`);
      })
      .catch((exportError) => {
        setError(describeError(exportError, "Failed to export LVGL layout."));
        setStatus("LVGL export failed.");
      });
  }, [exportFilePath, layout]);

  return {
    layout,
    summary,
    draftText,
    importSourceKind,
    importSourceValue,
    exportFilePath,
    status,
    error,
    setDraftText,
    applyDraftText,
    setImportSourceKind,
    setImportSourceValue,
    importLayout,
    setExportFilePath,
    exportLayout,
  };
}