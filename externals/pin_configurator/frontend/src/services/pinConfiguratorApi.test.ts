import { createEmptyProjectDocument } from "../contracts/api";
import { pinConfiguratorApi } from "./pinConfiguratorApi";

describe("pinConfiguratorApi project file contracts", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("posts a typed project document to the project-file save endpoint", async () => {
    const project = createEmptyProjectDocument();
    const fetchSpy = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ saved: true, file_path: "C:/tmp/demo.zpinproj" }), {
        status: 200,
        headers: {
          "Content-Type": "application/json",
        },
      }),
    );

    const result = await pinConfiguratorApi.saveProjectFile({
      ...project,
      board_id: "lp_mspm0g3507",
      file_path: "C:/tmp/demo.zpinproj",
    });

    expect(fetchSpy).toHaveBeenCalledWith(
      "/api/project-file/save",
      expect.objectContaining({
        method: "POST",
        headers: { "Content-Type": "application/json" },
      }),
    );
    expect(result).toEqual({ saved: true, file_path: "C:/tmp/demo.zpinproj" });
  });

  it("loads a normalized project document from the project-file load endpoint", async () => {
    const project = {
      ...createEmptyProjectDocument(),
      board_id: "lp_mspm0g3507",
      renode: {
        ...createEmptyProjectDocument().renode,
        enabled: true,
        platform: "platforms/boards/ti/lp_mspm0g3507.repl",
      },
    };

    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify(project), {
        status: 200,
        headers: {
          "Content-Type": "application/json",
        },
      }),
    );

    const result = await pinConfiguratorApi.loadProjectFile({ file_path: "C:/tmp/demo.zpinproj" });

    expect(result.board_id).toBe("lp_mspm0g3507");
    expect(result.renode.platform).toBe("platforms/boards/ti/lp_mspm0g3507.repl");
    expect(result.version).toBe(1);
  });

  it("loads a typed board definition from the board detail endpoint", async () => {
    const fetchSpy = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({
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
            alt_functions: [],
          },
        ],
        peripherals: [],
        external_devices: [],
      }), {
        status: 200,
        headers: {
          "Content-Type": "application/json",
        },
      }),
    );

    const result = await pinConfiguratorApi.getBoard("lp_mspm0g3507");

    expect(fetchSpy).toHaveBeenCalledWith("/api/board/lp_mspm0g3507", undefined);
    expect(result.board).toBe("lp_mspm0g3507");
    expect(result.pins[0]?.number).toBe(12);
  });

  it("loads the Zephyr catalog through the typed API service", async () => {
    const fetchSpy = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({
        root: "C:/zephyr",
        summary: {
          mcu_count: 1,
          sensor_count: 1,
        },
        mcus: [
          {
            key: "mcu:demo_board",
            kind: "mcu",
            name: "demo_board",
            label: "Demo Board",
            vendor: "demo",
            socs: ["DEMO_SOC"],
            board_path: "boards/demo/board.yml",
            directory: "boards/demo",
            parameters: {},
          },
        ],
        sensors: [
          {
            key: "sensor:demo,temp",
            kind: "sensor",
            name: "TEMP",
            label: "Demo Temp",
            vendor: "demo",
            compatible: "demo,temp",
            buses: ["i2c"],
            properties: [],
            binding_paths: ["dts/bindings/sensor/demo.yaml"],
            description: "Demo sensor binding",
            parameters: {},
          },
        ],
      }), {
        status: 200,
        headers: {
          "Content-Type": "application/json",
        },
      }),
    );

    const result = await pinConfiguratorApi.loadZephyrCatalog({ zephyrRoot: "C:/zephyr", refresh: true });

    expect(fetchSpy).toHaveBeenCalledWith("/api/zephyr/catalog?zephyr_root=C%3A%2Fzephyr&refresh=1", undefined);
    expect(result.summary.mcu_count).toBe(1);
    expect(result.sensors[0]?.compatible).toBe("demo,temp");
  });

  it("loads module definitions through the typed API service", async () => {
    const fetchSpy = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify([
        {
          id: "serial",
          name: "Serial",
          categories: [
            {
              id: "core",
              title: "Core",
              options: [
                {
                  key: "CONFIG_SERIAL",
                  type: "bool",
                  default: false,
                },
              ],
            },
          ],
        },
      ]), {
        status: 200,
        headers: {
          "Content-Type": "application/json",
        },
      }),
    );

    const result = await pinConfiguratorApi.listModules();

    expect(fetchSpy).toHaveBeenCalledWith("/api/modules", undefined);
    expect(result[0]?.id).toBe("serial");
  });

  it("loads clock trees and board editor drafts through the typed API service", async () => {
    const fetchSpy = vi.spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(
        new Response(JSON.stringify([
          { id: "mspm0g3507", name: "MSPM0G3507", node_count: 8 },
        ]), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }),
      )
      .mockResolvedValueOnce(
        new Response(JSON.stringify({
          drafts: [
            { filename: "demo_board.json", size: 128, updated_at: "2026-05-15T10:00:00Z" },
          ],
        }), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }),
      );

    const clockTrees = await pinConfiguratorApi.listClockTrees();
    const drafts = await pinConfiguratorApi.listBoardEditorDrafts();

    expect(fetchSpy).toHaveBeenNthCalledWith(1, "/api/clock-trees", undefined);
    expect(fetchSpy).toHaveBeenNthCalledWith(2, "/api/board-editor/drafts", undefined);
    expect(clockTrees[0]?.id).toBe("mspm0g3507");
    expect(drafts.drafts[0]?.filename).toBe("demo_board.json");
  });

  it("imports and exports LVGL layouts through the typed API service", async () => {
    const fetchSpy = vi.spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(
        new Response(JSON.stringify({
          source: "pasted JSON",
          layout: {
            screens: [],
          },
        }), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }),
      )
      .mockResolvedValueOnce(
        new Response(JSON.stringify({
          saved: true,
          file_path: "C:/tmp/demo.lvgl.json",
        }), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }),
      );

    const imported = await pinConfiguratorApi.importLvglLayout({ sourceKind: "json", text: "{}" });
    const exported = await pinConfiguratorApi.exportLvglLayout({ filePath: "C:/tmp/demo", layout: { screens: [] } });

    expect(fetchSpy).toHaveBeenNthCalledWith(
      1,
      "/api/lvgl/import",
      expect.objectContaining({ method: "POST" }),
    );
    expect(fetchSpy).toHaveBeenNthCalledWith(
      2,
      "/api/lvgl/export",
      expect.objectContaining({ method: "POST" }),
    );
    expect(imported.source).toBe("pasted JSON");
    expect(exported.saved).toBe(true);
  });
});