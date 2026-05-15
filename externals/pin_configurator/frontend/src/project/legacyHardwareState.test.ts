import {
  normalizePinStates,
  rehydratePinStatesForBoard,
} from "./legacyHardwareState";

describe("legacyHardwareState", () => {
  it("rehydrates saved pin selections by exact pincm and function id match", () => {
    const pinStates = normalizePinStates({
      "12": {
        af: {
          function_id: "3",
          name: "UART0_TX",
          pincm: "45",
          peripheral: "uart0",
          signal: "tx",
          direction: "out",
        },
        props: {
          bias: "pull-up",
        },
      },
    });

    const result = rehydratePinStatesForBoard(pinStates, {
      pins: [
        {
          number: 12,
          name: "PA12",
          alt_functions: [
            {
              function_id: 3,
              pincm: 45,
              name: "UART0_TX board object",
              peripheral: "uart0",
              signal: "tx",
              direction: "out",
              zephyr_pinmux: "UART0_TX_PA12",
            },
          ],
        },
      ],
    });

    expect(result).toEqual({
      "12": {
        af: {
          function_id: 3,
          pincm: 45,
          name: "UART0_TX board object",
          peripheral: "uart0",
          signal: "tx",
          direction: "out",
          zephyr_pinmux: "UART0_TX_PA12",
        },
        props: {
          bias: "pull-up",
        },
      },
    });
  });

  it("falls back to peripheral and signal matching when exact ids drift", () => {
    const pinStates = normalizePinStates({
      "7": {
        af: {
          function_id: 99,
          name: "SPI1_MOSI",
          pincm: 999,
          peripheral: "spi1",
          signal: "mosi",
          direction: "out",
        },
      },
    });

    const result = rehydratePinStatesForBoard(pinStates, {
      pins: [
        {
          number: 7,
          name: "PB7",
          alt_functions: [
            {
              function_id: 4,
              pincm: 23,
              name: "SPI1_MOSI live",
              peripheral: "spi1",
              signal: "mosi",
              direction: "out",
            },
          ],
        },
      ],
    });

    expect(result["7"]?.af).toEqual({
      function_id: 4,
      pincm: 23,
      name: "SPI1_MOSI live",
      peripheral: "spi1",
      signal: "mosi",
      direction: "out",
    });
  });
});