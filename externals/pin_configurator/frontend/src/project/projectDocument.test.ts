import {
  applyBoardToProjectDocument,
  createEmptyProjectDocument,
  normalizeProjectDocument,
} from "./projectDocument";

describe("projectDocument normalization", () => {
  it("applies board-specific renode defaults when a board is selected", () => {
    const result = applyBoardToProjectDocument(createEmptyProjectDocument(), "lp_mspm0g3507");

    expect(result.board_id).toBe("lp_mspm0g3507");
    expect(result.renode.enabled).toBe(true);
    expect(result.renode.platform).toBe("platforms/boards/ti/lp_mspm0g3507.repl");
  });

  it("normalizes sparse project payloads to a complete project document", () => {
    const result = normalizeProjectDocument({
      board_id: "rpi_pico",
      generated_overlay: 123,
      renode: {
        resc: "demo.resc",
      },
    });

    expect(result.version).toBe(1);
    expect(result.board_id).toBe("rpi_pico");
    expect(result.generated_overlay).toBe("123");
    expect(result.renode.platform).toBe("platforms/cpus/raspberrypi/rp2040.repl");
    expect(result.renode.resc).toBe("demo.resc");
    expect(result.pin_states).toEqual({});
  });

  it("normalizes persisted legacy pin and peripheral state into typed canonical sections", () => {
    const result = normalizeProjectDocument({
      pin_states: {
        "12": {
          af: {
            function_id: "3",
            name: "UART0_TX",
            pincm: "45",
            peripheral: "uart0",
            signal: "tx",
          },
          props: {
            bias: "pull-up",
          },
        },
      },
      periph_states: {
        uart0: 1,
        i2c1: 0,
      },
      periph_core_states: {
        uart0: 7,
      },
      external_device_states: {
        sensor0: {
          selected: "yes",
          bus: 123,
        },
      },
    });

    expect(result.pin_states).toEqual({
      "12": {
        af: {
          function_id: 3,
          name: "UART0_TX",
          pincm: 45,
          peripheral: "uart0",
          signal: "tx",
          direction: "io",
        },
        props: {
          bias: "pull-up",
        },
      },
    });
    expect(result.periph_states).toEqual({ uart0: true, i2c1: false });
    expect(result.periph_core_states).toEqual({ uart0: "7" });
    expect(result.external_device_states).toEqual({
      sensor0: {
        selected: true,
        bus: "123",
      },
    });
  });
});