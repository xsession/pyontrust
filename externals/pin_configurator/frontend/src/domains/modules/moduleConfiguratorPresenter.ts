import { useCallback, useEffect, useMemo, useState } from "react";
import type { ConfigPrimitive, ModuleCategoryDefinition, ModuleDefinition, ModuleOptionDefinition } from "../../contracts/api";
import { pinConfiguratorApi } from "../../services/pinConfiguratorApi";
import { describeError } from "../../shared/errors/apiError";

export interface ModuleOptionViewModel extends ModuleOptionDefinition {
  value: ConfigPrimitive;
  changed: boolean;
}

export interface ModuleCategoryViewModel extends Omit<ModuleCategoryDefinition, "options"> {
  options: ModuleOptionViewModel[];
}

export interface ModuleSummaryViewModel {
  id: string;
  name: string;
  icon: string;
  enabled: boolean;
  changedCount: number;
}

export interface ActiveModuleViewModel {
  id: string;
  name: string;
  icon: string;
  version: string;
  description: string;
  enabled: boolean;
  changedCount: number;
  categories: ModuleCategoryViewModel[];
}

export interface ModuleConfiguratorPresenter {
  loading: boolean;
  error: string;
  status: string;
  generatedPrjConf: string;
  generatedOverlayConf: string;
  modules: ModuleSummaryViewModel[];
  activeModuleId: string;
  activeModule: ActiveModuleViewModel | null;
  definitions: ModuleDefinition[];
  enabledById: Record<string, boolean>;
  valuesById: Record<string, Record<string, ConfigPrimitive>>;
  selectModule: (moduleId: string) => void;
  setModuleEnabled: (moduleId: string, enabled: boolean) => void;
  updateModuleOption: (moduleId: string, optionKey: string, value: ConfigPrimitive) => void;
  resetModule: (moduleId: string) => void;
  generateEnabledModules: () => void;
}

function collectDefaultsByModule(definitions: ModuleDefinition[]) {
  const defaultsById: Record<string, Record<string, ConfigPrimitive>> = {};

  definitions.forEach((definition) => {
    const defaults: Record<string, ConfigPrimitive> = {};
    definition.categories.forEach((category) => {
      category.options.forEach((option) => {
        defaults[option.key] = option.default;
      });
    });
    defaultsById[definition.id] = defaults;
  });

  return defaultsById;
}

function countModuleChanges(values: Record<string, ConfigPrimitive>, defaults: Record<string, ConfigPrimitive>) {
  return Object.keys(defaults).reduce((count, key) => {
    return String(values[key]) !== String(defaults[key]) ? count + 1 : count;
  }, 0);
}

export function useModuleConfiguratorPresenter(): ModuleConfiguratorPresenter {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [status, setStatus] = useState("Loading module definitions.");
  const [definitions, setDefinitions] = useState<ModuleDefinition[]>([]);
  const [defaultsById, setDefaultsById] = useState<Record<string, Record<string, ConfigPrimitive>>>({});
  const [valuesById, setValuesById] = useState<Record<string, Record<string, ConfigPrimitive>>>({});
  const [enabledById, setEnabledById] = useState<Record<string, boolean>>({});
  const [activeModuleId, setActiveModuleId] = useState("");
  const [generatedPrjConf, setGeneratedPrjConf] = useState("");
  const [generatedOverlayConf, setGeneratedOverlayConf] = useState("");

  useEffect(() => {
    let active = true;

    void pinConfiguratorApi
      .listModules()
      .then((result) => {
        if (!active) {
          return;
        }

        const defaults = collectDefaultsByModule(result);
        const values = Object.fromEntries(Object.entries(defaults).map(([id, definitionDefaults]) => [id, { ...definitionDefaults }]));
        const enabled = Object.fromEntries(result.map((definition) => [definition.id, false]));

        setDefinitions(result);
        setDefaultsById(defaults);
        setValuesById(values);
        setEnabledById(enabled);
        setActiveModuleId(result[0]?.id ?? "");
        setError("");
        setStatus(result.length ? `Loaded ${result.length} module definitions.` : "No module definitions available.");
      })
      .catch((loadError) => {
        if (!active) {
          return;
        }

        setDefinitions([]);
        setDefaultsById({});
        setValuesById({});
        setEnabledById({});
        setActiveModuleId("");
        setError(describeError(loadError, "Failed to load module definitions."));
        setStatus("Module definitions unavailable.");
      })
      .finally(() => {
        if (active) {
          setLoading(false);
        }
      });

    return () => {
      active = false;
    };
  }, []);

  const modules = useMemo<ModuleSummaryViewModel[]>(() => {
    return definitions.map((definition) => ({
      id: definition.id,
      name: definition.name,
      icon: definition.icon || "📦",
      enabled: enabledById[definition.id] ?? false,
      changedCount: countModuleChanges(valuesById[definition.id] ?? {}, defaultsById[definition.id] ?? {}),
    }));
  }, [defaultsById, definitions, enabledById, valuesById]);

  const activeModule = useMemo<ActiveModuleViewModel | null>(() => {
    const definition = definitions.find((entry) => entry.id === activeModuleId) ?? null;
    if (!definition) {
      return null;
    }

    const currentValues = valuesById[definition.id] ?? {};
    const currentDefaults = defaultsById[definition.id] ?? {};

    return {
      id: definition.id,
      name: definition.name,
      icon: definition.icon || "📦",
      version: definition.version || "",
      description: definition.desc || "",
      enabled: enabledById[definition.id] ?? false,
      changedCount: countModuleChanges(currentValues, currentDefaults),
      categories: definition.categories.map((category) => ({
        id: category.id,
        title: category.title,
        options: category.options.map((option) => ({
          ...option,
          value: currentValues[option.key] ?? option.default,
          changed: String(currentValues[option.key] ?? option.default) !== String(currentDefaults[option.key] ?? option.default),
        })),
      })),
    };
  }, [activeModuleId, defaultsById, definitions, enabledById, valuesById]);

  const selectModule = useCallback((moduleId: string) => {
    setActiveModuleId(moduleId);
  }, []);

  const setModuleEnabled = useCallback((moduleId: string, enabled: boolean) => {
    setEnabledById((current) => ({
      ...current,
      [moduleId]: enabled,
    }));
    setStatus(`${enabled ? "Enabled" : "Disabled"} ${moduleId} for module generation.`);
  }, []);

  const updateModuleOption = useCallback((moduleId: string, optionKey: string, value: ConfigPrimitive) => {
    setValuesById((current) => ({
      ...current,
      [moduleId]: {
        ...(current[moduleId] ?? {}),
        [optionKey]: value,
      },
    }));
    setStatus(`Updated ${optionKey} on ${moduleId}.`);
  }, []);

  const resetModule = useCallback((moduleId: string) => {
    setValuesById((current) => ({
      ...current,
      [moduleId]: {
        ...(defaultsById[moduleId] ?? {}),
      },
    }));
    setStatus(`Reset ${moduleId} to its default option values.`);
  }, [defaultsById]);

  const generateEnabledModules = useCallback(() => {
    const payload = Object.fromEntries(
      Object.entries(enabledById)
        .filter(([, enabled]) => enabled)
        .map(([moduleId]) => [moduleId, valuesById[moduleId] ?? {}]),
    );

    if (!Object.keys(payload).length) {
      setStatus("Enable at least one module before generating configuration.");
      return;
    }

    void pinConfiguratorApi
      .generateModuleConfig({ modules: payload })
      .then((result) => {
        setGeneratedPrjConf(result.prj_conf || "");
        setGeneratedOverlayConf(result.overlay_conf || "");
        setError("");
        setStatus(`Generated configuration for ${Object.keys(payload).length} enabled module${Object.keys(payload).length === 1 ? "" : "s"}.`);
      })
      .catch((generationError) => {
        setError(describeError(generationError, "Failed to generate module configuration."));
        setStatus("Module configuration generation failed.");
      });
  }, [enabledById, valuesById]);

  return {
    loading,
    error,
    status,
    generatedPrjConf,
    generatedOverlayConf,
    modules,
    activeModuleId,
    activeModule,
    definitions,
    enabledById,
    valuesById,
    selectModule,
    setModuleEnabled,
    updateModuleOption,
    resetModule,
    generateEnabledModules,
  };
}