import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import type { BoardDefinition } from "../contracts/api";
import * as exportArtifacts from "./exportArtifacts";
import * as exportSimulation from "./exportSimulation";
import { formatGeneratedFragments } from "./generatedArtifacts";
import { pinConfiguratorApi } from "../services/pinConfiguratorApi";
import { useProjectShellController } from "./useProjectShellController";

const boards = [
  {
    id: "mspm0g3507",
    name: "MSPM0G3507",
    board: "lp_mspm0g3507",
    package: "QFP-48",
    pin_count: 48,
  },
  {
    id: "rp2040",
    name: "RP2040",
    board: "rpi_pico",
    package: "Pico DIP-40",
    pin_count: 40,
  },
];

const mspm0BoardDefinition: BoardDefinition = {
  soc: "MSPM0G3507",
  board: "lp_mspm0g3507",
  vendor: "ti",
  package: "QFP-48",
  pin_count: 48,
  flash_size_kb: 128,
  sram_size_kb: 32,
  clock_hz: 80000000,
  cores: [],
  output_targets: [],
  pins: [
    {
      number: 12,
      name: "PA12",
      port: "A",
      gpio_num: 12,
      kind: "io",
      side: "left",
      default_function: "Reset",
      alt_functions: [
        {
          function_id: 3,
          pincm: 45,
          name: "UART0_TX live",
          peripheral: "uart0",
          signal: "tx",
          direction: "out",
          zephyr_pinmux: "UART0_TX_PA12",
        },
        {
          function_id: 4,
          pincm: 46,
          name: "I2C0_SCL live",
          peripheral: "i2c0",
          signal: "scl",
          direction: "io",
          zephyr_pinmux: "I2C0_SCL_PA12",
        },
      ],
    },
  ],
  peripherals: [],
  external_devices: [],
};

function ProjectControllerHarness() {
  const controller = useProjectShellController(boards);

  return (
    <div>
      <button type="button" onClick={() => controller.selectBoard("rpi_pico")}>
        Select RP2040
      </button>
      <button type="button" onClick={controller.seedGeneratedArtifacts}>
        Seed Overlay
      </button>
      <button type="button" onClick={controller.exportGeneratedArtifacts}>
        Export Artifacts
      </button>
      <button type="button" onClick={controller.exportRenodeSimulation}>
        Export Renode Bundle
      </button>
      <button type="button" onClick={controller.undoProjectDocument} disabled={!controller.canUndoProjectDocument}>
        Undo Project Change
      </button>
      <button type="button" onClick={controller.redoProjectDocument} disabled={!controller.canRedoProjectDocument}>
        Redo Project Change
      </button>
      <button type="button" onClick={controller.saveProjectFile}>
        Save Project
      </button>
      <button type="button" onClick={controller.loadProjectFile}>
        Load Project
      </button>
      <input
        aria-label="Project file path"
        value={controller.projectFilePath}
        onChange={(event) => controller.setProjectFilePath(event.target.value)}
      />
      <input
        aria-label="Renode platform"
        value={controller.projectDocument.renode.platform}
        onChange={(event) => controller.updateRenodeField("platform", event.target.value)}
      />
      <input
        aria-label="Renode boot line"
        value={controller.projectDocument.renode.boot_line}
        onChange={(event) => controller.updateRenodeField("boot_line", event.target.value)}
      />
      <textarea
        aria-label="Renode RESC"
        value={controller.projectDocument.renode.resc}
        onChange={(event) => controller.updateRenodeField("resc", event.target.value)}
      />
      <textarea
        aria-label="Renode Robot"
        value={controller.projectDocument.renode.robot}
        onChange={(event) => controller.updateRenodeField("robot", event.target.value)}
      />
      <button type="button" onClick={() => controller.addProtocolEntry("uart_shell_bridge")}>
        Add UART Protocol
      </button>
      <input
        aria-label="Bluetooth LE Peripheral Instance Name"
        value={String(controller.projectDocument.protocol_editor.entries[0]?.values.instanceName ?? "")}
        onChange={(event) => {
          const entryId = controller.projectDocument.protocol_editor.entries[0]?.id;
          if (entryId) {
            controller.updateProtocolEntryValue(entryId, "instanceName", event.target.value);
          }
        }}
      />
      <input
        aria-label="Bluetooth LE Peripheral Device Name"
        value={String(controller.projectDocument.protocol_editor.entries[0]?.values.deviceName ?? "")}
        onChange={(event) => {
          const entryId = controller.projectDocument.protocol_editor.entries[0]?.id;
          if (entryId) {
            controller.updateProtocolEntryValue(entryId, "deviceName", event.target.value);
          }
        }}
      />
      <textarea
        aria-label="Generated overlay"
        value={controller.projectDocument.generated_overlay}
        onChange={(event) => controller.updateGeneratedOverlay(event.target.value)}
      />
      <textarea
        aria-label="Generated config"
        value={controller.projectDocument.generated_conf}
        onChange={(event) => controller.updateGeneratedConf(event.target.value)}
      />
      <textarea
        aria-label="LVGL layout"
        value={JSON.stringify(controller.projectDocument.lvgl_layout)}
        onChange={(event) => controller.updateLvglLayout(JSON.parse(event.target.value || "{}") as Record<string, unknown>)}
      />
      <textarea
        aria-label="Generated fragments"
        value={formatGeneratedFragments(controller.projectDocument.generated_fragments)}
        readOnly
      />
      <button type="button" onClick={() => controller.clearPinAssignment("12")}>
        Clear Pin 12
      </button>
      <button
        type="button"
        onClick={() => controller.updatePinAltFunction("12", mspm0BoardDefinition.pins[0].alt_functions[1])}
      >
        Assign Pin 12 I2C
      </button>
      <label>
        Pull-up
        <input
          aria-label="Pin 12 Pull-up"
          type="checkbox"
          checked={Boolean(controller.projectDocument.pin_states["12"]?.props?.bias_pull_up)}
          onChange={(event) => controller.updatePinBooleanProperty("12", "bias_pull_up", event.target.checked)}
        />
      </label>
      <label>
        Pull-down
        <input
          aria-label="Pin 12 Pull-down"
          type="checkbox"
          checked={Boolean(controller.projectDocument.pin_states["12"]?.props?.bias_pull_down)}
          onChange={(event) => controller.updatePinBooleanProperty("12", "bias_pull_down", event.target.checked)}
        />
      </label>
      <div data-testid="board-id">{controller.projectDocument.board_id}</div>
      <div data-testid="platform">{controller.projectDocument.renode.platform}</div>
      <div data-testid="hydrated-pin-count">{Object.keys(controller.hydratedPinStates).length}</div>
      <div data-testid="pin-state-count">{Object.keys(controller.projectDocument.pin_states).length}</div>
      <div data-testid="pin-af-name">{controller.projectDocument.pin_states["12"]?.af?.name ?? ""}</div>
      <div data-testid="status">{controller.projectStatus.message}</div>
    </div>
  );
}

describe("useProjectShellController", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("blocks project saves when integrity warnings are still present", async () => {
    const saveSpy = vi.spyOn(pinConfiguratorApi, "saveProjectFile").mockResolvedValue({
      saved: true,
      file_path: "C:/tmp/pin-configurator-shell.zpinproj",
    });
    vi.spyOn(pinConfiguratorApi, "getBoard").mockResolvedValue(mspm0BoardDefinition);

    render(<ProjectControllerHarness />);

    await waitFor(() => {
      expect(screen.getByTestId("board-id")).toHaveTextContent("lp_mspm0g3507");
    });

    fireEvent.change(screen.getByLabelText("Generated overlay"), {
      target: { value: "/dts-v1/;" },
    });
    fireEvent.change(screen.getByLabelText("LVGL layout"), {
      target: { value: '{"preset":"phone"}' },
    });

    fireEvent.click(screen.getByRole("button", { name: "Save Project" }));

    await waitFor(() => {
      expect(saveSpy).not.toHaveBeenCalled();
      expect(screen.getByTestId("status")).toHaveTextContent("Resolve project integrity warnings before saving");
      expect(screen.getByTestId("status")).toHaveTextContent("Generated artifacts appear stale");
    });

    expect(screen.getByLabelText("LVGL layout")).toHaveValue('{"preset":"phone"}');
  });

  it("exports generated artifacts from the canonical project document", async () => {
    const downloadSpy = vi.spyOn(exportArtifacts, "downloadGeneratedArtifactBundle").mockReturnValue(3);
    vi.spyOn(pinConfiguratorApi, "getBoard").mockResolvedValue(mspm0BoardDefinition);

    render(<ProjectControllerHarness />);

    await waitFor(() => {
      expect(screen.getByTestId("board-id")).toHaveTextContent("lp_mspm0g3507");
    });

    fireEvent.click(screen.getByRole("button", { name: "Seed Overlay" }));
    fireEvent.click(screen.getByRole("button", { name: "Export Artifacts" }));

    await waitFor(() => {
      expect(downloadSpy).toHaveBeenCalledTimes(1);
      expect(screen.getByTestId("status")).toHaveTextContent("Exported 3 generated artifact files from the canonical project document.");
    });
  });

  it("exports a Renode simulation bundle from the canonical project document", async () => {
    const downloadSpy = vi.spyOn(exportSimulation, "downloadRenodeSimulationExportBundle").mockReturnValue(4);
    vi.spyOn(pinConfiguratorApi, "getBoard").mockResolvedValue(mspm0BoardDefinition);

    render(<ProjectControllerHarness />);

    await waitFor(() => {
      expect(screen.getByTestId("board-id")).toHaveTextContent("lp_mspm0g3507");
    });

    fireEvent.change(screen.getByLabelText("Renode RESC"), {
      target: { value: "mach create\nshowAnalyzer sysbus.uart0" },
    });
    fireEvent.change(screen.getByLabelText("Renode Robot"), {
      target: { value: "*** Settings ***\nSuite Setup  Log  Ready" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Seed Overlay" }));
    fireEvent.click(screen.getByRole("button", { name: "Export Renode Bundle" }));

    await waitFor(() => {
      expect(downloadSpy).toHaveBeenCalledTimes(1);
      expect(screen.getByTestId("status")).toHaveTextContent("Exported 4 Renode simulation files from the canonical project document.");
    });
  });

  it("supports a save/load round trip through the extracted project controller", async () => {
    const saveSpy = vi.spyOn(pinConfiguratorApi, "saveProjectFile").mockResolvedValue({
      saved: true,
      file_path: "C:/tmp/pin-configurator-shell.zpinproj",
    });
    const loadSpy = vi.spyOn(pinConfiguratorApi, "loadProjectFile").mockResolvedValue({
      version: 1,
      board_id: "lp_mspm0g3507",
      pin_states: {
        "12": {
          af: {
            function_id: 3,
            name: "UART0_TX",
            pincm: 45,
            peripheral: "uart0",
            signal: "tx",
            direction: "out",
          },
        },
      },
      periph_states: {},
      periph_core_states: {},
      external_device_states: {},
      protocol_editor: {
        selectedTemplateId: "uart_shell_bridge",
        selectedEntryId: "proto_uart_shell_bridge_1",
        previewTab: "prj_conf",
        entries: [
          {
            id: "proto_uart_shell_bridge_1",
            templateId: "uart_shell_bridge",
            enabled: true,
            values: {
              instanceName: "uart_shell_1",
              uartNode: "uart1",
              baudRate: 57600,
              shellPrompt: "restored:~$",
              lineMode: true,
            },
          },
        ],
      },
      lvgl_layout: {},
      generated_overlay: "/dts-v1/;\n&chosen {\n    zephyr,console = &uart0;\n};",
      generated_conf: "CONFIG_SERIAL=y",
      generated_fragments: {
        chosen: {
          console: "uart0",
        },
      },
      sensor_jobs: [],
      sensor_selected: "",
      mcu_jobs: [],
      mcu_selected: "",
      renode: {
        enabled: true,
        platform: "platforms/boards/ti/lp_mspm0g3507.repl",
        resc: "mach create\nshowAnalyzer sysbus.uart0",
        robot: "*** Settings ***\nSuite Setup  Log  Ready",
        uart: "sysbus.uart0",
        boot_line: "Renode demo boot confirmed",
        appbench_target: "shellbench",
        robot_target: "robot-shell",
      },
      tabs: {},
    });
    const getBoardSpy = vi.spyOn(pinConfiguratorApi, "getBoard").mockResolvedValue(mspm0BoardDefinition);

    render(<ProjectControllerHarness />);

    await waitFor(() => {
      expect(screen.getByTestId("board-id")).toHaveTextContent("lp_mspm0g3507");
    });

    fireEvent.click(screen.getByRole("button", { name: "Seed Overlay" }));
    await waitFor(() => {
      expect(String(screen.getByLabelText("Generated overlay").getAttribute("value") ?? screen.getByLabelText("Generated overlay").textContent ?? "")).toContain("/dts-v1/;");
      expect(String(screen.getByLabelText("Generated config").getAttribute("value") ?? screen.getByLabelText("Generated config").textContent ?? "")).toContain("CONFIG_SERIAL=y");
      expect(String(screen.getByLabelText("Generated fragments").getAttribute("value") ?? screen.getByLabelText("Generated fragments").textContent ?? "")).toContain('"board"');
    });

    fireEvent.change(screen.getByLabelText("Renode platform"), {
      target: { value: "platforms/demo/custom.repl" },
    });
    fireEvent.change(screen.getByLabelText("Renode boot line"), {
      target: { value: "Custom shell boot line" },
    });
    fireEvent.change(screen.getByLabelText("Bluetooth LE Peripheral Instance Name"), {
      target: { value: "proto_ble_main" },
    });
    fireEvent.change(screen.getByLabelText("Bluetooth LE Peripheral Device Name"), {
      target: { value: "Proto Sensor" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Add UART Protocol" }));

    fireEvent.click(screen.getByRole("button", { name: "Save Project" }));
    await waitFor(() => {
      expect(saveSpy).toHaveBeenCalledTimes(1);
      const serializedSavePayload = JSON.stringify(saveSpy.mock.calls[0]?.[0]);
      expect(serializedSavePayload).toContain('"board_id":"lp_mspm0g3507"');
      expect(serializedSavePayload).toContain('"generated_fragments"');
      expect(serializedSavePayload).toContain('"id":"lp_mspm0g3507"');
      expect(serializedSavePayload).toContain('"platform":"platforms/demo/custom.repl"');
      expect(serializedSavePayload).toContain('"boot_line":"Custom shell boot line"');
      expect(serializedSavePayload).toContain('"protocol_editor"');
      expect(serializedSavePayload).toContain('"deviceName":"Proto Sensor"');
      expect(serializedSavePayload).toContain('"templateId":"uart_shell_bridge"');
    });

    fireEvent.click(screen.getByRole("button", { name: "Select RP2040" }));
    await waitFor(() => {
      expect(screen.getByTestId("board-id")).toHaveTextContent("rpi_pico");
      expect(screen.getByTestId("platform")).toHaveTextContent("platforms/cpus/raspberrypi/rp2040.repl");
    });

    fireEvent.click(screen.getByRole("button", { name: "Load Project" }));
    await waitFor(() => {
      expect(loadSpy).toHaveBeenCalledWith({ file_path: "C:/tmp/pin-configurator-shell.zpinproj" });
      expect(getBoardSpy).toHaveBeenCalledWith("lp_mspm0g3507");
      expect(screen.getByTestId("board-id")).toHaveTextContent("lp_mspm0g3507");
      expect(screen.getByTestId("platform")).toHaveTextContent("platforms/boards/ti/lp_mspm0g3507.repl");
      expect(screen.getByTestId("hydrated-pin-count")).toHaveTextContent("1");
      expect(screen.getByTestId("status")).toHaveTextContent("resolved 1 pin assignments");
      expect(screen.getByLabelText("Renode platform")).toHaveValue("platforms/boards/ti/lp_mspm0g3507.repl");
      expect(screen.getByLabelText("Renode boot line")).toHaveValue("Renode demo boot confirmed");
      expect(screen.getByLabelText("Bluetooth LE Peripheral Instance Name")).toHaveValue("uart_shell_1");
      expect(screen.getByLabelText("Bluetooth LE Peripheral Device Name")).toHaveValue("");
      expect(String(screen.getByLabelText("Generated overlay").getAttribute("value") ?? screen.getByLabelText("Generated overlay").textContent ?? "")).toContain("zephyr,console");
      expect(String(screen.getByLabelText("Generated config").getAttribute("value") ?? screen.getByLabelText("Generated config").textContent ?? "")).toContain("CONFIG_SERIAL=y");
      expect(String(screen.getByLabelText("Generated fragments").getAttribute("value") ?? screen.getByLabelText("Generated fragments").textContent ?? "")).toContain('"console": "uart0"');
    });

    fireEvent.click(screen.getByLabelText("Pin 12 Pull-up"));
    await waitFor(() => {
      expect(screen.getByLabelText("Pin 12 Pull-up")).toBeChecked();
      expect(screen.getByTestId("status")).toHaveTextContent("Enabled bias pull up on pin 12.");
    });

    fireEvent.click(screen.getByLabelText("Pin 12 Pull-down"));
    await waitFor(() => {
      expect(screen.getByLabelText("Pin 12 Pull-down")).toBeChecked();
      expect(screen.getByTestId("status")).toHaveTextContent("Enabled bias pull down on pin 12.");
    });

    fireEvent.click(screen.getByRole("button", { name: "Assign Pin 12 I2C" }));
    await waitFor(() => {
      expect(screen.getByTestId("pin-af-name")).toHaveTextContent("I2C0_SCL live");
      expect(screen.getByTestId("status")).toHaveTextContent("Assigned I2C0_SCL live to pin 12.");
    });

    fireEvent.click(screen.getByRole("button", { name: "Undo Project Change" }));
    await waitFor(() => {
      expect(screen.getByTestId("pin-af-name")).toHaveTextContent("UART0_TX");
      expect(screen.getByTestId("status")).toHaveTextContent("Reverted the last persistent project change.");
    });

    fireEvent.click(screen.getByRole("button", { name: "Redo Project Change" }));
    await waitFor(() => {
      expect(screen.getByTestId("pin-af-name")).toHaveTextContent("I2C0_SCL live");
      expect(screen.getByTestId("status")).toHaveTextContent("Reapplied the next persistent project change.");
    });

    fireEvent.click(screen.getByRole("button", { name: "Clear Pin 12" }));
    await waitFor(() => {
      expect(screen.getByTestId("pin-state-count")).toHaveTextContent("0");
      expect(screen.getByTestId("hydrated-pin-count")).toHaveTextContent("0");
      expect(screen.getByTestId("status")).toHaveTextContent("Removed saved pin assignment for pin 12.");
    });
  });
});