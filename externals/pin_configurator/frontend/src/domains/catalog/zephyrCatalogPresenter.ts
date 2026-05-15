import { useCallback, useEffect, useMemo, useState } from "react";
import type { BoardSummary, ZephyrCatalogItem, ZephyrCatalogMcuItem, ZephyrCatalogResponse, ZephyrCatalogSensorItem } from "../../contracts/api";
import { pinConfiguratorApi } from "../../services/pinConfiguratorApi";
import { describeError } from "../../shared/errors/apiError";
import { filterAndRankByFuzzyMatch, normalizeFuzzyText } from "../../shared/search/fuzzySearch";
import type { PackageManagerPresenter } from "../packages/packageManagerPresenter";
import type { PeripheralConfiguratorPresenter } from "../peripherals/peripheralConfiguratorPresenter";
import type { SensorParserPresenter } from "../sensors/sensorParserPresenter";

const ZEPHYR_CATALOG_STORAGE_KEY = "zpincfg_zephyr_catalog_root";

export type ZephyrCatalogFilter = "all" | "mcu" | "sensor";

export interface ZephyrCatalogPresenter {
  root: string;
  filter: ZephyrCatalogFilter;
  search: string;
  loading: boolean;
  error: string;
  summaryText: string;
  items: ZephyrCatalogItem[];
  visibleItems: ZephyrCatalogItem[];
  selectedKey: string;
  selectedItem: ZephyrCatalogItem | null;
  setRoot: (value: string) => void;
  refresh: (refresh?: boolean) => void;
  setFilter: (value: ZephyrCatalogFilter) => void;
  setSearch: (value: string) => void;
  selectItem: (key: string) => void;
  useInPinConfigurator: (item: ZephyrCatalogItem) => void;
  useInPackageManager: (item: ZephyrCatalogMcuItem) => void;
  useInSensorParser: (item: ZephyrCatalogSensorItem) => void;
}

interface UseZephyrCatalogPresenterInput {
  boards: BoardSummary[];
  selectBoard: (boardId: string) => void;
  peripheralConfigurator: PeripheralConfiguratorPresenter;
  sensorParser: SensorParserPresenter;
  packageManager: PackageManagerPresenter;
}

function normalizeSearchToken(value: string): string {
  return normalizeFuzzyText(value);
}

function resolveBoardId(item: ZephyrCatalogMcuItem, boards: BoardSummary[]): string {
  const tokens = new Set([
    item.name,
    item.label,
    ...item.socs,
  ].map(normalizeSearchToken).filter(Boolean));

  const exactBoard = boards.find((board) => tokens.has(normalizeSearchToken(board.board)));
  if (exactBoard) {
    return exactBoard.id;
  }

  const exactId = boards.find((board) => tokens.has(normalizeSearchToken(board.id)));
  if (exactId) {
    return exactId.id;
  }

  const loose = boards.find((board) => {
    const fields = [board.id, board.board, board.name].map(normalizeSearchToken);
    return [...tokens].some((token) => fields.some((field) => field && (field.includes(token) || token.includes(field))));
  });

  return loose?.id ?? "";
}

function buildVisibleItems(items: ZephyrCatalogItem[], filter: ZephyrCatalogFilter, search: string): ZephyrCatalogItem[] {
  const filteredItems = items.filter((item) => {
    if (filter !== "all" && item.kind !== filter) {
      return false;
    }
  });

  return filterAndRankByFuzzyMatch(filteredItems, search, (item) => [
    item.label,
    item.name,
    item.vendor,
    item.kind === "mcu" ? item.board_path : item.compatible,
    ...(item.kind === "mcu" ? item.socs : item.buses),
  ].join(" "));
}

export function useZephyrCatalogPresenter({ boards, selectBoard, peripheralConfigurator, sensorParser, packageManager }: UseZephyrCatalogPresenterInput): ZephyrCatalogPresenter {
  const [root, setRoot] = useState(() => {
    if (typeof window === "undefined") {
      return "";
    }

    return window.localStorage.getItem(ZEPHYR_CATALOG_STORAGE_KEY) || "";
  });
  const [filter, setFilter] = useState<ZephyrCatalogFilter>("all");
  const [search, setSearch] = useState("");
  const [selectedKey, setSelectedKey] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [response, setResponse] = useState<ZephyrCatalogResponse | null>(null);

  const refresh = useCallback((forceRefresh = false) => {
    setLoading(true);
    setError("");

    void pinConfiguratorApi
      .loadZephyrCatalog({ zephyrRoot: root, refresh: forceRefresh })
      .then((result) => {
        setResponse(result);
        setSelectedKey((current) => {
          const items = [...result.mcus, ...result.sensors];
          return items.some((item) => item.key === current) ? current : items[0]?.key || "";
        });
        if (typeof window !== "undefined") {
          window.localStorage.setItem(ZEPHYR_CATALOG_STORAGE_KEY, result.root || root);
        }
      })
      .catch((catalogError) => {
        setResponse(null);
        setSelectedKey("");
        setError(describeError(catalogError, "Failed to load Zephyr catalog."));
      })
      .finally(() => {
        setLoading(false);
      });
  }, [root]);

  useEffect(() => {
    refresh(false);
  }, [refresh]);

  const items = useMemo<ZephyrCatalogItem[]>(() => {
    if (!response) {
      return [];
    }

    return [...response.mcus, ...response.sensors];
  }, [response]);

  const visibleItems = useMemo(() => buildVisibleItems(items, filter, search), [filter, items, search]);
  const selectedItem = useMemo(
    () => items.find((item) => item.key === selectedKey) ?? visibleItems[0] ?? null,
    [items, selectedKey, visibleItems],
  );
  const summaryText = response
    ? `Root: ${response.root} • ${response.summary.mcu_count} MCU boards • ${response.summary.sensor_count} sensors`
    : error
      ? error
      : "Load the local Zephyr tree to browse supported boards and sensor bindings.";

  return {
    root,
    filter,
    search,
    loading,
    error,
    summaryText,
    items,
    visibleItems,
    selectedKey,
    selectedItem,
    setRoot,
    refresh,
    setFilter,
    setSearch,
    selectItem: setSelectedKey,
    useInPinConfigurator(item) {
      if (item.kind === "mcu") {
        const boardId = resolveBoardId(item, boards);
        if (boardId) {
          selectBoard(boardId);
          return;
        }

        packageManager.importCatalogMcu(item);
        return;
      }

      peripheralConfigurator.importCatalogSensor(item);
    },
    useInPackageManager(item) {
      packageManager.importCatalogMcu(item);
    },
    useInSensorParser(item) {
      sensorParser.importCatalogSensor(item);
    },
  };
}