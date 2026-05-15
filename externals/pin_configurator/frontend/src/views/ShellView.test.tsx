import { fireEvent, render, screen, within } from "@testing-library/react";
import { vi } from "vitest";
import { createEmptyProjectDocument } from "../contracts/api";
import type { ShellCommandViewModel } from "../presenters/useShellPresenter";
import { ShellView } from "./ShellView";
import type { PinAssignmentsViewModel } from "../shared/viewModels/pinAssignments";
import type { ExecutionWorkbenchViewModel } from "../domains/build-sim-test/buildSimTestPresenter";

vi.mock("../workspace/WorkspaceDock", () => ({
  WorkspaceDock: ({ focusRequest }: { focusRequest?: { panelId: string } | null }) => (
    <div data-testid="workspace-dock-fallback" data-focus-panel={focusRequest?.panelId ?? ""}>
      Dock mock
    </div>
  ),
}));

const emptyPinAssignments: PinAssignmentsViewModel = {
  summary: {
    resolvedCount: 0,
    savedCount: 0,
    unresolvedCount: 0,
  },
  rows: [],
  issuesByPinNumber: {},
  propertyValuesByPinNumber: {},
  altFunctionOptionsByPinNumber: {},
};

describe("ShellView", () => {
  it("renders the professional workspace shell", () => {
    const projectDocument = createEmptyProjectDocument();
    const commandRun = vi.fn();
    const selectBoard = vi.fn();
    const updateRenodeField = vi.fn();
    const exportGeneratedArtifacts = vi.fn();
    const exportRenodeSimulation = vi.fn();
    const seedGeneratedArtifacts = vi.fn();
    const executionWorkbench: ExecutionWorkbenchViewModel = {
      selectedMachine: "platforms/boards/ti/lp_mspm0g3507.repl",
      machineOptions: [
        {
          value: "",
          label: "No machine selected",
          detail: "Leave simulation disabled until a Renode machine target is chosen.",
          recommended: false,
        },
        {
          value: "platforms/boards/ti/lp_mspm0g3507.repl",
          label: "MSPM0G3507 recommended machine",
          detail: "Use the default Renode platform for MSPM0G3507 (QFP-48).",
          recommended: true,
        },
      ],
      support: {
        tone: "success",
        title: "Simulation bundle is staged",
        detail: "Renode machine, AppBench target, and Robot target are aligned for platforms/boards/ti/lp_mspm0g3507.repl.",
      },
      tasks: [
        {
          id: "build",
          label: "Build Console",
          status: "ready",
          detail: "1 enabled protocol entry is staged for code generation and export.",
          latestLog: "Build pipeline shell channel is idle.",
        },
        {
          id: "simulation",
          label: "Simulation Console",
          status: "ready",
          detail: "Machine target platforms/boards/ti/lp_mspm0g3507.repl is selected for Renode export.",
          latestLog: "Renode profile is enabled.",
        },
        {
          id: "tests",
          label: "Test Console",
          status: "ready",
          detail: "Robot target robotbench is ready for validation follow-up.",
          latestLog: "1 protocol entry is enabled for validation.",
        },
      ],
    };
    const commands: ShellCommandViewModel[] = [
      {
        id: "project.save",
        label: "Save Project",
        description: "Persist the canonical project document to the current project path.",
        shortcut: "Ctrl+S",
        group: "Project",
        disabled: false,
        run: commandRun,
      },
      {
        id: "project.load",
        label: "Load Project",
        description: "Load a project file into the canonical document and workspace shell.",
        shortcut: "Ctrl+O",
        group: "Project",
        disabled: false,
        run: vi.fn(),
      },
      {
        id: "history.undo",
        label: "Undo Change",
        description: "Revert the last project-document command.",
        shortcut: "Ctrl+Z",
        group: "History",
        disabled: false,
        run: vi.fn(),
      },
      {
        id: "history.redo",
        label: "Redo Change",
        description: "Reapply the last reverted project-document command.",
        shortcut: "Ctrl+Shift+Z",
        group: "History",
        disabled: true,
        run: vi.fn(),
      },
      {
        id: "export.artifacts",
        label: "Export Artifacts",
        description: "Download generated overlay, config, and fragment outputs.",
        shortcut: "Ctrl+E",
        group: "Export",
        disabled: false,
        run: exportGeneratedArtifacts,
      },
      {
        id: "export.renode",
        label: "Export Renode Bundle",
        description: "Download the Renode simulation bundle from the project document.",
        shortcut: "Ctrl+Shift+E",
        group: "Export",
        disabled: false,
        run: exportRenodeSimulation,
      },
      {
        id: "artifacts.seed",
        label: "Seed Overlay",
        description: "Seed generated artifact fields from the current project state.",
        shortcut: "Alt+Shift+S",
        group: "Artifacts",
        disabled: false,
        run: seedGeneratedArtifacts,
      },
    ];

    render(
      <ShellView
        boards={[
          {
            id: "mspm0g3507",
            name: "MSPM0G3507",
            board: "lp_mspm0g3507",
            package: "QFP-48",
            pin_count: 48,
          },
        ]}
        activeBoard={null}
        loading={false}
        error=""
        metrics={[
          { label: "Board Surface", value: "3", detail: "Three boards loaded.", accent: "sun" },
          { label: "Package Coverage", value: "2", detail: "Two packages available.", accent: "mint" },
          { label: "SoC Families", value: "2", detail: "Two SoC families.", accent: "signal" },
        ]}
        commands={commands}
        statusBarItems={[
          {
            id: "board",
            label: "Board",
            value: "MSPM0G3507 (QFP-48)",
            detail: "lp_mspm0g3507",
            tone: "success",
          },
          {
            id: "dirty",
            label: "Dirty State",
            value: "Unsaved changes",
            detail: "Undo history contains persistent project edits.",
            tone: "warning",
          },
        ]}
        outputChannels={[
          {
            id: "build",
            label: "Build Output",
            badge: "2",
            tone: "warning",
            entries: [
              {
                id: "build-1",
                timestamp: "now",
                summary: "Build pipeline shell channel is idle.",
                detail: "3/4 core sections ready.",
                severity: "info",
              },
            ],
          },
          {
            id: "diagnostics",
            label: "Diagnostics",
            badge: "2",
            tone: "success",
            entries: [
              {
                id: "diag-1",
                timestamp: "integrity",
                summary: "Project integrity checks are passing.",
                detail: "Integrity checks passing",
                severity: "success",
              },
            ],
          },
        ]}
        executionWorkbench={executionWorkbench}
        projectDocument={projectDocument}
        generatedFragments="{}"
        pinAssignments={emptyPinAssignments}
        peripheralConfigurator={{
          peripherals: [],
          externalDevices: [],
          enabledPeripheralCount: 0,
          selectedExternalDeviceCount: 0,
          setPeripheralEnabled: () => undefined,
          setPeripheralCore: () => undefined,
          setExternalDeviceSelected: () => undefined,
          setExternalDeviceBus: () => undefined,
          importCatalogSensor: () => undefined,
        }}
        moduleConfigurator={{
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
        }}
        clockConfigurator={{
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
        }}
        lvglLayout={{
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
        }}
        boardEditor={{
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
        }}
        interruptConfigurator={{
          items: [],
          summary: "",
        }}
        sensorParser={{
          jobs: [],
          selectedJobId: "",
          selectedJob: null,
          selectJob: () => undefined,
          removeJob: () => undefined,
          importCatalogSensor: () => undefined,
        }}
        packageManager={{
          jobs: [],
          selectedJobId: "",
          selectedJob: null,
          selectJob: () => undefined,
          removeJob: () => undefined,
          importCatalogMcu: () => undefined,
        }}
        zephyrCatalog={{
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
        }}
        hydratedPinStates={{
          "12": {
            af: {
              function_id: 3,
              pincm: 45,
              name: "UART0_TX live",
              peripheral: "uart0",
              signal: "tx",
              direction: "out",
              zephyr_pinmux: "UART0_TX_PA12",
            },
          },
        }}
        canUndoProjectDocument={true}
        canRedoProjectDocument={false}
        projectFilePath="C:/tmp/demo.zpinproj"
        projectStatus={{ tone: "neutral", message: "Shell project state ready." }}
        projectBusy={false}
        setProjectFilePath={() => undefined}
        selectBoard={selectBoard}
        updateRenodeField={updateRenodeField}
        addProtocolEntry={() => undefined}
        selectProtocolEntry={() => undefined}
        removeProtocolEntry={() => undefined}
        toggleProtocolEntry={() => undefined}
        updateProtocolEntryValue={() => undefined}
        updateGeneratedOverlay={() => undefined}
        updateGeneratedConf={() => undefined}
        clearPinAssignment={() => undefined}
        assignPinAltFunction={() => undefined}
        updatePinBooleanProperty={() => undefined}
        undoProjectDocument={() => undefined}
        redoProjectDocument={() => undefined}
        exportGeneratedArtifacts={exportGeneratedArtifacts}
        exportRenodeSimulation={exportRenodeSimulation}
        seedGeneratedArtifacts={seedGeneratedArtifacts}
        clearGeneratedArtifacts={() => undefined}
        saveProjectFile={() => undefined}
        loadProjectFile={() => undefined}
      />,
    );

    expect(screen.getByText("Pin Configurator workspace")).toBeInTheDocument();
    expect(screen.getByText("Board Surface")).toBeInTheDocument();
    expect(screen.getByText("Engineering workspace")).toBeInTheDocument();
    expect(screen.getByText("Project controls")).toBeInTheDocument();
    expect(screen.getByDisplayValue("C:/tmp/demo.zpinproj")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Undo Change" })).toBeEnabled();
    expect(screen.getByRole("button", { name: "Redo Change" })).toBeDisabled();
    expect(screen.getByText("Pin assignments")).toBeInTheDocument();
    expect(screen.getByText("resolved selections")).toBeInTheDocument();
    expect(screen.getByText("Renode profile")).toBeInTheDocument();
    expect(screen.getByText("Protocol editor")).toBeInTheDocument();
    expect(screen.getAllByRole("button", { name: "Export Artifacts" }).length).toBeGreaterThan(0);
    expect(screen.getByRole("button", { name: "Export Renode Bundle" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Build" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Simulate" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Test" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Keyboard Map" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Command Palette" })).toBeInTheDocument();
    expect(screen.getByRole("region", { name: "Workspace status bar" })).toBeInTheDocument();
    expect(screen.getByText("Dirty State")).toBeInTheDocument();
    expect(screen.getByText("Unsaved changes")).toBeInTheDocument();
    expect(screen.getByDisplayValue("sysbus.uart0")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Open Generated Overlay" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Open Generated Source" })).toBeInTheDocument();
    expect(screen.getAllByRole("button", { name: "Open Robot Tests" }).length).toBeGreaterThan(0);
    expect(screen.getByText("Execution output and diagnostics")).toBeInTheDocument();
    expect(screen.getByText("Execution workbench")).toBeInTheDocument();
    expect(screen.getByRole("combobox", { name: "Execution Renode machine" })).toHaveValue("platforms/boards/ti/lp_mspm0g3507.repl");
    expect(screen.getByRole("button", { name: "Export Demo Bundle" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Open Test Log" })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: /Build Output/i })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: /Diagnostics/i })).toBeInTheDocument();
    expect(screen.getByLabelText("Workspace density mode")).toHaveValue("regular");
    expect(screen.getByLabelText("Workspace layout preset")).toHaveValue("bring-up");
    expect(screen.getByRole("log", { name: "Build Output entries" })).toBeInTheDocument();
    expect(screen.getAllByText("Build pipeline shell channel is idle.").length).toBeGreaterThan(0);
    expect(screen.getByText("Frontend boundaries")).toBeInTheDocument();
    expect(screen.getByTestId("workspace-dock-fallback")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("tab", { name: /Diagnostics/i }));
    expect(screen.getAllByText("Project integrity checks are passing.").length).toBeGreaterThan(0);

    const diagnosticsTab = screen.getByRole("tab", { name: /Diagnostics/i });
    diagnosticsTab.focus();
    fireEvent.keyDown(diagnosticsTab, { key: "ArrowLeft" });
    expect(screen.getByRole("tab", { name: /Build Output/i })).toHaveAttribute("aria-selected", "true");

    fireEvent.click(screen.getByRole("button", { name: "Command Palette" }));

    const dialog = screen.getByRole("dialog");
    expect(dialog).toBeInTheDocument();
    expect(screen.getByText("Command palette")).toBeInTheDocument();
    fireEvent.click(within(dialog).getByRole("button", { name: /Save Project/i }));
    expect(commandRun).toHaveBeenCalledTimes(1);

    fireEvent.click(screen.getByRole("button", { name: "Command Palette" }));
    expect(screen.getByRole("button", { name: /Recently used/i })).toBeInTheDocument();
    fireEvent.change(screen.getByPlaceholderText(/Search commands, boards, panels/i), {
      target: { value: "m0g35" },
    });
    fireEvent.click(screen.getByRole("button", { name: /Open Board MSPM0G3507/i }));
    expect(selectBoard).toHaveBeenCalledWith("mspm0g3507");

    fireEvent.keyDown(window, { key: "s", ctrlKey: true });
    expect(commandRun).toHaveBeenCalledTimes(2);

    fireEvent.keyDown(window, { key: "?", shiftKey: true });
    expect(screen.getByText("Workspace actions")).toBeInTheDocument();
    expect(screen.getByText("Keyboard map")).toBeInTheDocument();
    fireEvent.keyDown(document, { key: "Escape" });

    fireEvent.change(screen.getByLabelText("Workspace density mode"), { target: { value: "compact" } });
    expect(document.documentElement.dataset.density).toBe("compact");

    fireEvent.change(screen.getByLabelText("Workspace layout preset"), { target: { value: "renode-validation" } });
    expect(screen.getByTestId("workspace-dock-fallback")).toHaveAttribute("data-focus-panel", "workspace-renode-profile");

    fireEvent.click(screen.getByRole("button", { name: "Open Generated Source" }));
    expect(screen.getByTestId("workspace-dock-fallback")).toHaveAttribute("data-focus-panel", "workspace-generated-source");

    const generatedOverlayNav = screen.getByRole("button", { name: /Generated Overlay Alt\+2/i });
    generatedOverlayNav.focus();
    fireEvent.keyDown(generatedOverlayNav, { key: "ArrowDown" });
    expect(screen.getByTestId("workspace-dock-fallback")).toHaveAttribute("data-focus-panel", "workspace-generated-config");

    fireEvent.click(screen.getByRole("button", { name: "Seed Artifacts" }));
    expect(seedGeneratedArtifacts).toHaveBeenCalledTimes(1);

    fireEvent.click(screen.getByRole("button", { name: "Export Demo Bundle" }));
    expect(exportRenodeSimulation).toHaveBeenCalledTimes(1);

    fireEvent.change(screen.getByRole("combobox", { name: "Execution Renode machine" }), { target: { value: "" } });
    expect(updateRenodeField).toHaveBeenCalledWith("platform", "");

    fireEvent.click(screen.getAllByRole("button", { name: "Open Robot Tests" })[1]);
    expect(screen.getByTestId("workspace-dock-fallback")).toHaveAttribute("data-focus-panel", "workspace-renode-robot");

    fireEvent.keyDown(window, { key: "2", altKey: true });
    expect(screen.getByTestId("workspace-dock-fallback")).toHaveAttribute("data-focus-panel", "workspace-generated-overlay");
  });
});