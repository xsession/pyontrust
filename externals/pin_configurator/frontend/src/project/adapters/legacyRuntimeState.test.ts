import {
  adaptLegacyRuntimeStateToProjectDocument,
  adaptProjectDocumentToLegacyRuntimeState,
} from "./legacyRuntimeState";

describe("legacy runtime adapters", () => {
  it("adapts legacy runtime aliases into the canonical project document", () => {
    const result = adaptLegacyRuntimeStateToProjectDocument({
      boardId: "lp_mspm0g3507",
      generated_overlay: "/dts-v1/;",
      periph_states: {
        uart0: 1,
      },
    });

    expect(result.board_id).toBe("lp_mspm0g3507");
    expect(result.generated_overlay).toBe("/dts-v1/;");
    expect(result.periph_states).toEqual({ uart0: true });
  });

  it("adapts canonical project documents back to a legacy-compatible persisted shape", () => {
    const project = adaptLegacyRuntimeStateToProjectDocument({ boardId: "rpi_pico" });
    const result = adaptProjectDocumentToLegacyRuntimeState(project);

    expect(result.board_id).toBe("rpi_pico");
    expect(result.version).toBe(1);
    expect(result).toHaveProperty("pin_states");
  });
});