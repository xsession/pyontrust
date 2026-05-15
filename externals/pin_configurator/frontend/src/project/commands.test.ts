import { createEmptyProjectDocument } from "../contracts/api";
import { applyProjectDocumentCommand, replayProjectDocumentCommands, type ProjectDocumentCommand } from "./commands";

describe("project commands", () => {
  it("applies board selection with seeded artifacts through a serializable command", () => {
    const next = applyProjectDocumentCommand(createEmptyProjectDocument(), {
      type: "apply-board-selection",
      boardId: "lp_mspm0g3507",
      seededArtifacts: {
        overlay: "/dts-v1/;",
        conf: "CONFIG_GPIO=y",
        fragments: {
          board: { id: "lp_mspm0g3507" },
          outputs: { overlay: "lp_mspm0g3507.overlay", config: "lp_mspm0g3507.conf" },
        },
      },
    });

    expect(next.board_id).toBe("lp_mspm0g3507");
    expect(next.renode.platform).toBe("platforms/boards/ti/lp_mspm0g3507.repl");
    expect(next.generated_overlay).toBe("/dts-v1/;");
    expect(next.generated_conf).toBe("CONFIG_GPIO=y");
    expect(next.generated_fragments).toEqual({
      board: { id: "lp_mspm0g3507" },
      outputs: { overlay: "lp_mspm0g3507.overlay", config: "lp_mspm0g3507.conf" },
    });
  });

  it("updates pin state through explicit pin commands", () => {
    const withAltFunction = applyProjectDocumentCommand(createEmptyProjectDocument(), {
      type: "assign-pin-alt-function",
      pinNumber: "12",
      altFunction: {
        function_id: 4,
        pincm: 46,
        name: "I2C0_SCL",
        peripheral: "i2c0",
        signal: "scl",
        direction: "io",
        zephyr_pinmux: "I2C0_SCL_PA12",
      },
    });

    const withProperty = applyProjectDocumentCommand(withAltFunction, {
      type: "update-pin-boolean-property",
      pinNumber: "12",
      propertyKey: "bias_pull_up",
      value: true,
    });

    const cleared = applyProjectDocumentCommand(withProperty, {
      type: "clear-pin-assignment",
      pinNumber: "12",
    });

    expect(withAltFunction.pin_states["12"]?.af?.name).toBe("I2C0_SCL");
    expect(withProperty.pin_states["12"]?.props).toEqual({
      bias_pull_up: true,
    });
    expect(cleared.pin_states["12"]).toBeUndefined();
  });

  it("replaces LVGL layout state through an explicit serializable command", () => {
    const next = applyProjectDocumentCommand(createEmptyProjectDocument(), {
      type: "replace-lvgl-layout",
      layout: {
        preset: "phone",
        screens: [
          {
            id: "screen_root",
            name: "screen_main",
          },
        ],
      },
    });

    expect(next.lvgl_layout).toEqual({
      preset: "phone",
      screens: [
        {
          id: "screen_root",
          name: "screen_main",
        },
      ],
    });
  });

  it("replays serialized commands into the same canonical project document state", () => {
    const commandLog: ProjectDocumentCommand[] = [
      {
        type: "apply-board-selection",
        boardId: "lp_mspm0g3507",
      },
      {
        type: "update-generated-overlay",
        value: "/dts-v1/;",
      },
      {
        type: "replace-lvgl-layout",
        layout: {
          preset: "phone",
        },
      },
      {
        type: "update-renode-field",
        field: "boot_line",
        value: "Replay boot line",
      },
      {
        type: "assign-pin-alt-function",
        pinNumber: "12",
        altFunction: {
          function_id: 4,
          pincm: 46,
          name: "I2C0_SCL",
          peripheral: "i2c0",
          signal: "scl",
          direction: "io",
          zephyr_pinmux: "I2C0_SCL_PA12",
        },
      },
      {
        type: "update-pin-boolean-property",
        pinNumber: "12",
        propertyKey: "bias_pull_down",
        value: true,
      },
    ];

    const serializedLog = JSON.parse(JSON.stringify(commandLog)) as ProjectDocumentCommand[];
    const replayed = replayProjectDocumentCommands(createEmptyProjectDocument(), serializedLog);

    expect(replayed.board_id).toBe("lp_mspm0g3507");
    expect(replayed.generated_overlay).toBe("/dts-v1/;");
    expect(replayed.lvgl_layout).toEqual({ preset: "phone" });
    expect(replayed.renode.boot_line).toBe("Replay boot line");
    expect(replayed.pin_states["12"]?.af?.name).toBe("I2C0_SCL");
    expect(replayed.pin_states["12"]?.props).toEqual({
      bias_pull_down: true,
    });
  });
});