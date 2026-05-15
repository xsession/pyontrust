import { parseProjectFileLoadResponse, normalizeProjectDocument } from "./normalize";

describe("project document migration and normalization", () => {
  it("upgrades missing or legacy versions to the current schema version", () => {
    const withoutVersion = normalizeProjectDocument({ board_id: "lp_mspm0g3507" });
    const legacyVersion = normalizeProjectDocument({ version: 0, board_id: "rpi_pico" });

    expect(withoutVersion.version).toBe(1);
    expect(legacyVersion.version).toBe(1);
  });

  it("applies missing-field defaults on load responses", () => {
    const result = parseProjectFileLoadResponse({
      version: 1,
      board_id: "lp_mspm0g3507",
      renode: {
        enabled: true,
      },
    });

    expect(result.protocol_editor.entries).toHaveLength(1);
    expect(result.generated_fragments).toEqual({});
    expect(result.renode.platform).toBe("platforms/boards/ti/lp_mspm0g3507.repl");
    expect(result.tabs).toEqual({});
  });
});