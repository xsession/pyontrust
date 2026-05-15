import { useCallback, useEffect, useMemo, useState } from "react";
import type { BoardDefinition, BoardSummary } from "../../contracts/api";
import { pinConfiguratorApi } from "../../services/pinConfiguratorApi";
import { describeError } from "../../shared/errors/apiError";

export interface BoardEditorPresenter {
  drafts: Array<{ filename: string; size: number; updatedAt: string }>;
  draftFilename: string;
  draftText: string;
  status: string;
  error: string;
  setDraftFilename: (value: string) => void;
  setDraftText: (value: string) => void;
  refreshDrafts: () => void;
  loadDraft: (filename: string) => void;
  saveDraft: () => void;
  deleteDraft: (filename: string) => void;
  seedFromActiveBoard: () => void;
}

function parseBoardDraftJson(text: string): Record<string, unknown> {
  const parsed: unknown = JSON.parse(text || "{}");
  if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
    throw new Error("Board draft JSON must be an object.");
  }
  return parsed as Record<string, unknown>;
}

function buildSeedBoard(activeBoardDefinition: BoardDefinition | null, activeBoard: BoardSummary | null): Record<string, unknown> {
  if (!activeBoardDefinition && !activeBoard) {
    return {
      board: "draft_board",
      soc: "",
      pins: [],
      peripherals: [],
      external_devices: [],
    };
  }

  return {
    board: activeBoardDefinition?.board || activeBoard?.board || "draft_board",
    soc: activeBoardDefinition?.soc || activeBoard?.name || "",
    vendor: activeBoardDefinition?.vendor || "",
    package: activeBoardDefinition?.package || activeBoard?.package || "",
    pins: activeBoardDefinition?.pins ?? [],
    peripherals: activeBoardDefinition?.peripherals ?? [],
    external_devices: activeBoardDefinition?.external_devices ?? [],
  };
}

export function useBoardEditorPresenter(activeBoardDefinition: BoardDefinition | null, activeBoard: BoardSummary | null): BoardEditorPresenter {
  const [drafts, setDrafts] = useState<Array<{ filename: string; size: number; updatedAt: string }>>([]);
  const [draftFilename, setDraftFilename] = useState("");
  const [draftText, setDraftText] = useState("");
  const [status, setStatus] = useState("Loading board-editor drafts.");
  const [error, setError] = useState("");

  const refreshDrafts = useCallback(() => {
    void pinConfiguratorApi
      .listBoardEditorDrafts()
      .then((result) => {
        setDrafts(result.drafts.map((draft) => ({
          filename: draft.filename,
          size: draft.size,
          updatedAt: draft.updated_at,
        })));
        setError("");
        setStatus(result.drafts.length ? `Loaded ${result.drafts.length} board-editor drafts.` : "No board-editor drafts saved yet.");
      })
      .catch((loadError) => {
        setDrafts([]);
        setError(describeError(loadError, "Failed to load board-editor drafts."));
        setStatus("Board-editor drafts unavailable.");
      });
  }, []);

  useEffect(() => {
    refreshDrafts();
  }, [refreshDrafts]);

  const loadDraft = useCallback((filename: string) => {
    void pinConfiguratorApi
      .loadBoardEditorDraft(filename)
      .then((result) => {
        setDraftFilename(result.filename);
        setDraftText(JSON.stringify(result.board, null, 2));
        setError("");
        setStatus(`Loaded board-editor draft ${result.filename}.`);
      })
      .catch((loadError) => {
        setError(describeError(loadError, `Failed to load ${filename}.`));
        setStatus("Board-editor draft load failed.");
      });
  }, []);

  const saveDraft = useCallback(() => {
    try {
      const board = parseBoardDraftJson(draftText);
      void pinConfiguratorApi
        .saveBoardEditorDraft({
          filename: draftFilename || undefined,
          board,
        })
        .then((result) => {
          setDraftFilename(result.filename);
          setError("");
          setStatus(`Saved board-editor draft ${result.filename}.`);
          refreshDrafts();
        })
        .catch((saveError) => {
          setError(describeError(saveError, "Failed to save board-editor draft."));
          setStatus("Board-editor draft save failed.");
        });
    } catch (parseError) {
      setError(describeError(parseError, "Draft JSON is invalid."));
      setStatus("Board-editor draft JSON is invalid.");
    }
  }, [draftFilename, draftText, refreshDrafts]);

  const deleteDraft = useCallback((filename: string) => {
    void pinConfiguratorApi
      .deleteBoardEditorDraft(filename)
      .then((result) => {
        if (draftFilename === result.filename) {
          setDraftFilename("");
        }
        setError("");
        setStatus(`Deleted board-editor draft ${result.filename}.`);
        refreshDrafts();
      })
      .catch((deleteError) => {
        setError(describeError(deleteError, `Failed to delete ${filename}.`));
        setStatus("Board-editor draft deletion failed.");
      });
  }, [draftFilename, refreshDrafts]);

  const seedBoardText = useMemo(() => JSON.stringify(buildSeedBoard(activeBoardDefinition, activeBoard), null, 2), [activeBoard, activeBoardDefinition]);

  const seedFromActiveBoard = useCallback(() => {
    const filenameBase = activeBoard?.board || activeBoardDefinition?.board || "draft_board";
    setDraftFilename(`${filenameBase}.json`);
    setDraftText(seedBoardText);
    setStatus(`Seeded board-editor draft from ${filenameBase}.`);
    setError("");
  }, [activeBoard?.board, activeBoardDefinition?.board, seedBoardText]);

  return {
    drafts,
    draftFilename,
    draftText,
    status,
    error,
    setDraftFilename,
    setDraftText,
    refreshDrafts,
    loadDraft,
    saveDraft,
    deleteDraft,
    seedFromActiveBoard,
  };
}