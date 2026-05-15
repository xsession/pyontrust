import { useCallback, useEffect, useMemo, useState } from "react";
import type { BoardDefinition, ClockTreeDefinition, ClockTreeNode, ClockTreeSummary, ConfigPrimitive } from "../../contracts/api";
import { pinConfiguratorApi } from "../../services/pinConfiguratorApi";
import { describeError } from "../../shared/errors/apiError";

export interface ClockNodeViewModel extends ClockTreeNode {
  frequencyHz: number;
}

export interface ClockConfiguratorPresenter {
  loading: boolean;
  error: string;
  status: string;
  availableTrees: ClockTreeSummary[];
  currentTree: ClockTreeDefinition | null;
  nodes: ClockNodeViewModel[];
  selectedNodeId: string;
  selectedNode: ClockNodeViewModel | null;
  values: Record<string, ConfigPrimitive>;
  frequencies: Record<string, number>;
  warnings: string[];
  generatedOverlay: string;
  generatedConf: string;
  selectTree: (treeId: string) => void;
  selectNode: (nodeId: string) => void;
  updateNodeProperty: (propertyKey: string, value: ConfigPrimitive) => void;
  generateConfig: () => void;
}

function normalizeClockToken(value: string): string {
  return value.toLowerCase().replace(/[^a-z0-9]+/g, "");
}

function scoreTreeForBoard(tree: ClockTreeSummary, board: BoardDefinition | null): number {
  if (!board) {
    return 0;
  }

  const boardToken = normalizeClockToken(board.soc || board.board);
  const keys = [tree.id, tree.soc, tree.name].map((value) => normalizeClockToken(value || "")).filter(Boolean);
  if (keys.includes(boardToken)) {
    return 100;
  }
  if (keys.some((key) => key.includes(boardToken) || boardToken.includes(key))) {
    return 80;
  }
  if (boardToken.includes("mspm0") && tree.id === "mspm0g3507") {
    return 60;
  }
  return 0;
}

function defaultValuesForTree(tree: ClockTreeDefinition): Record<string, ConfigPrimitive> {
  const next: Record<string, ConfigPrimitive> = {};
  tree.nodes.forEach((node) => {
    (node.props ?? []).forEach((property) => {
      next[property.key] = property.default;
    });
  });
  return next;
}

export function useClockConfiguratorPresenter(activeBoardDefinition: BoardDefinition | null): ClockConfiguratorPresenter {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [status, setStatus] = useState("Loading clock trees.");
  const [availableTrees, setAvailableTrees] = useState<ClockTreeSummary[]>([]);
  const [currentTree, setCurrentTree] = useState<ClockTreeDefinition | null>(null);
  const [selectedNodeId, setSelectedNodeId] = useState("");
  const [values, setValues] = useState<Record<string, ConfigPrimitive>>({});
  const [frequencies, setFrequencies] = useState<Record<string, number>>({});
  const [warnings, setWarnings] = useState<string[]>([]);
  const [generatedOverlay, setGeneratedOverlay] = useState("");
  const [generatedConf, setGeneratedConf] = useState("");

  const recomputeFrequencies = useCallback((treeId: string, nextValues: Record<string, ConfigPrimitive>) => {
    void pinConfiguratorApi
      .computeClockFrequencies({ tree: treeId, values: nextValues })
      .then((result) => {
        setFrequencies(result.frequencies || {});
        setWarnings(result.warnings ?? []);
      })
      .catch((frequencyError) => {
        setWarnings([describeError(frequencyError, "Failed to compute frequencies.")]);
      });
  }, []);

  const loadTree = useCallback((treeId: string) => {
    setStatus(`Loading clock tree ${treeId}.`);
    void pinConfiguratorApi
      .getClockTree(treeId)
      .then((tree) => {
        const nextValues = defaultValuesForTree(tree);
        setCurrentTree(tree);
        setSelectedNodeId(tree.nodes[0]?.id ?? "");
        setValues(nextValues);
        setError("");
        setStatus(`Loaded clock tree ${tree.name}.`);
        recomputeFrequencies(tree.id, nextValues);
      })
      .catch((treeError) => {
        setCurrentTree(null);
        setSelectedNodeId("");
        setValues({});
        setFrequencies({});
        setWarnings([]);
        setError(describeError(treeError, "Failed to load clock tree."));
        setStatus("Clock tree unavailable.");
      });
  }, [recomputeFrequencies]);

  useEffect(() => {
    let active = true;

    void pinConfiguratorApi
      .listClockTrees()
      .then((result) => {
        if (!active) {
          return;
        }

        setAvailableTrees(result);
        setError("");
        setStatus(result.length ? `Loaded ${result.length} clock trees.` : "No clock trees available.");

        const nextTree = [...result]
          .sort((left, right) => scoreTreeForBoard(right, activeBoardDefinition) - scoreTreeForBoard(left, activeBoardDefinition))[0];

        if (nextTree) {
          loadTree(nextTree.id);
        }
      })
      .catch((loadError) => {
        if (!active) {
          return;
        }

        setAvailableTrees([]);
        setCurrentTree(null);
        setError(describeError(loadError, "Failed to load clock trees."));
        setStatus("Clock tree list unavailable.");
      })
      .finally(() => {
        if (active) {
          setLoading(false);
        }
      });

    return () => {
      active = false;
    };
  }, [activeBoardDefinition, loadTree]);

  const nodes = useMemo<ClockNodeViewModel[]>(() => {
    return (currentTree?.nodes ?? []).map((node) => ({
      ...node,
      frequencyHz: frequencies[node.id] ?? 0,
    }));
  }, [currentTree?.nodes, frequencies]);

  const selectedNode = useMemo(
    () => nodes.find((node) => node.id === selectedNodeId) ?? nodes[0] ?? null,
    [nodes, selectedNodeId],
  );

  const selectTree = useCallback((treeId: string) => {
    if (!treeId) {
      return;
    }
    loadTree(treeId);
  }, [loadTree]);

  const selectNode = useCallback((nodeId: string) => {
    setSelectedNodeId(nodeId);
  }, []);

  const updateNodeProperty = useCallback((propertyKey: string, value: ConfigPrimitive) => {
    if (!currentTree) {
      return;
    }

    setValues((current) => {
      const nextValues = {
        ...current,
        [propertyKey]: value,
      };
      recomputeFrequencies(currentTree.id, nextValues);
      return nextValues;
    });
    setStatus(`Updated clock property ${propertyKey}.`);
  }, [currentTree, recomputeFrequencies]);

  const generateConfig = useCallback(() => {
    if (!currentTree) {
      return;
    }

    void pinConfiguratorApi
      .generateClockConfig({
        tree: currentTree.id,
        values,
      })
      .then((result) => {
        setGeneratedOverlay(result.overlay || "");
        setGeneratedConf(result.prj_conf || "");
        setFrequencies(result.frequencies || {});
        setWarnings(result.warnings ?? []);
        setError("");
        setStatus(`Generated clock configuration for ${currentTree.name}.`);
      })
      .catch((generationError) => {
        setError(describeError(generationError, "Failed to generate clock configuration."));
        setStatus("Clock configuration generation failed.");
      });
  }, [currentTree, values]);

  return {
    loading,
    error,
    status,
    availableTrees,
    currentTree,
    nodes,
    selectedNodeId,
    selectedNode,
    values,
    frequencies,
    warnings,
    generatedOverlay,
    generatedConf,
    selectTree,
    selectNode,
    updateNodeProperty,
    generateConfig,
  };
}