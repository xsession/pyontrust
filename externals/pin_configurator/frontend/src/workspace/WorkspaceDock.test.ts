import { vi } from "vitest";
import { createEmptyProjectDocument } from "../contracts/api";
import { getDefaultWorkspaceDockPanels, populateDefaultWorkspaceDock, restoreOrPopulateWorkspaceDock } from "./layout/workspaceDockLayout";
import { buildWorkspaceDockPanelParams } from "./panels/dockPanelParams";

describe("WorkspaceDock", () => {
  function createDockPanelParams() {
    return buildWorkspaceDockPanelParams({
      boards: [
        {
          id: "mspm0g3507",
          name: "MSPM0G3507",
          board: "lp_mspm0g3507",
          package: "QFP-48",
          pin_count: 48,
        },
      ],
      activeBoard: {
        id: "mspm0g3507",
        name: "MSPM0G3507",
        board: "lp_mspm0g3507",
        package: "QFP-48",
        pin_count: 48,
      },
      projectDocument: createEmptyProjectDocument(),
      hydratedPinStates: {},
      pinAssignments: {
        summary: {
          resolvedCount: 0,
          savedCount: 0,
          unresolvedCount: 0,
        },
        rows: [],
        issuesByPinNumber: {},
        propertyValuesByPinNumber: {},
        altFunctionOptionsByPinNumber: {},
      },
      peripheralConfigurator: {
        peripherals: [],
        externalDevices: [],
        enabledPeripheralCount: 0,
        selectedExternalDeviceCount: 0,
        setPeripheralEnabled: () => undefined,
        setPeripheralCore: () => undefined,
        setExternalDeviceSelected: () => undefined,
        setExternalDeviceBus: () => undefined,
        importCatalogSensor: () => undefined,
      },
      moduleConfigurator: {
        loading: false,
        error: "",
        status: "",
        generatedPrjConf: "",
        generatedOverlayConf: "",
        modules: [],
        activeModuleId: "",
        activeModule: null,
        definitions: [],
        enabledById: {},
        valuesById: {},
        selectModule: () => undefined,
        setModuleEnabled: () => undefined,
        updateModuleOption: () => undefined,
        resetModule: () => undefined,
        generateEnabledModules: () => undefined,
      },
      clockConfigurator: {
        loading: false,
        error: "",
        status: "",
        availableTrees: [],
        currentTree: null,
        nodes: [],
        selectedNodeId: "",
        selectedNode: null,
        values: {},
        frequencies: {},
        warnings: [],
        generatedOverlay: "",
        generatedConf: "",
        selectTree: () => undefined,
        selectNode: () => undefined,
        updateNodeProperty: () => undefined,
        generateConfig: () => undefined,
      },
      lvglLayout: {
        layout: {},
        summary: {
          preset: "custom",
          screenCount: 0,
          widgetCount: 0,
          startupScreenId: "screen_root",
        },
        draftText: "{}",
        importSourceKind: "json",
        importSourceValue: "",
        exportFilePath: "",
        status: "",
        error: "",
        setDraftText: () => undefined,
        applyDraftText: () => undefined,
        setImportSourceKind: () => undefined,
        setImportSourceValue: () => undefined,
        importLayout: () => undefined,
        setExportFilePath: () => undefined,
        exportLayout: () => undefined,
      },
      boardEditor: {
        drafts: [],
        draftFilename: "",
        draftText: "",
        status: "",
        error: "",
        setDraftFilename: () => undefined,
        setDraftText: () => undefined,
        refreshDrafts: () => undefined,
        loadDraft: () => undefined,
        saveDraft: () => undefined,
        deleteDraft: () => undefined,
        seedFromActiveBoard: () => undefined,
      },
      interruptConfigurator: {
        items: [],
        summary: "",
      },
      sensorParser: {
        jobs: [],
        selectedJobId: "",
        selectedJob: null,
        selectJob: () => undefined,
        removeJob: () => undefined,
        importCatalogSensor: () => undefined,
      },
      packageManager: {
        jobs: [],
        selectedJobId: "",
        selectedJob: null,
        selectJob: () => undefined,
        removeJob: () => undefined,
        importCatalogMcu: () => undefined,
      },
      zephyrCatalog: {
        root: "",
        filter: "all",
        search: "",
        loading: false,
        error: "",
        summaryText: "",
        items: [],
        visibleItems: [],
        selectedKey: "",
        selectedItem: null,
        setRoot: () => undefined,
        refresh: () => undefined,
        setFilter: () => undefined,
        setSearch: () => undefined,
        selectItem: () => undefined,
        useInPinConfigurator: () => undefined,
        useInPackageManager: () => undefined,
        useInSensorParser: () => undefined,
      },
      clearPinAssignment: () => undefined,
      assignPinAltFunction: () => undefined,
      updatePinBooleanProperty: () => undefined,
      updateRenodeField: () => undefined,
      updateGeneratedOverlay: () => undefined,
      updateGeneratedConf: () => undefined,
      addProtocolEntry: () => undefined,
      selectProtocolEntry: () => undefined,
      removeProtocolEntry: () => undefined,
      toggleProtocolEntry: () => undefined,
      updateProtocolEntryValue: () => undefined,
      loading: false,
      error: "",
    });
  }

  it("uses only canonical project document artifact fields for generated panels", () => {
    const params = createDockPanelParams();

    expect(params.generatedOverlay).toBe("");
    expect(params.generatedConf).toBe("");
    expect(params.generatedFragments).toBe("");
    expect(params.artifactDocuments.map((document) => document.id)).toEqual([
      "overlay",
      "config",
      "fragments",
      "header",
      "source",
      "resc",
      "robot",
    ]);
  });

  it("populates the default dock panels when no persisted layout exists", () => {
    const addPanel = vi.fn();

    populateDefaultWorkspaceDock({ addPanel } as never, createDockPanelParams());

    expect(addPanel).toHaveBeenCalledTimes(21);
    expect(addPanel.mock.calls[0]?.[0]).toMatchObject({
      id: "workspace-overview",
      title: "Board Inventory",
      component: "overview",
    });
  });

  it("reorders the default dock anchor panel for layout presets", () => {
    expect(getDefaultWorkspaceDockPanels("renode-validation")[0]).toMatchObject({
      id: "workspace-renode-profile",
      title: "Renode Profile",
    });
  });

  it("restores a persisted dock layout instead of re-adding default panels", () => {
    const addPanel = vi.fn();
    const fromJSON = vi.fn();

    const restored = restoreOrPopulateWorkspaceDock(
      { addPanel, fromJSON } as never,
      createDockPanelParams(),
      { grid: { views: [] } },
    );

    expect(restored).toBe(true);
    expect(fromJSON).toHaveBeenCalledWith({ grid: { views: [] } });
    expect(addPanel).not.toHaveBeenCalled();
  });

  it("falls back to the default dock layout when persisted data cannot be restored", () => {
    const addPanel = vi.fn();
    const fromJSON = vi.fn(() => {
      throw new Error("stale layout");
    });

    const restored = restoreOrPopulateWorkspaceDock(
      { addPanel, fromJSON } as never,
      createDockPanelParams(),
      { invalid: true },
    );

    expect(restored).toBe(false);
    expect(fromJSON).toHaveBeenCalledWith({ invalid: true });
    expect(addPanel).toHaveBeenCalledTimes(21);
  });
});