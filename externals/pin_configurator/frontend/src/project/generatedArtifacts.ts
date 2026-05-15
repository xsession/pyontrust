import type { BoardSummary } from "../contracts/api";

export function buildGeneratedOverlayFromBoard(board?: BoardSummary | null): string {
  if (!board) {
    return [
      "// Waiting for board inventory from /api/boards",
      "// The Monaco baseline is live, but no board metadata has been selected yet.",
      "",
      "&pinctrl {",
      '    status = "disabled";',
      "};",
    ].join("\n");
  }

  return [
    "/dts-v1/;",
    "",
    "/ {",
    `    model = "${board.name}";`,
    `    compatible = "zephyr,${board.board.toLowerCase()}";`,
    "};",
    "",
    "&pinctrl {",
    `    board-id = "${board.board}";`,
    `    package = "${board.package}";`,
    `    pin-count = <${board.pin_count}>;`,
    "};",
  ].join("\n");
}

export function buildGeneratedConfFromBoard(board?: BoardSummary | null): string {
  if (!board) {
    return [
      "# Waiting for board inventory from /api/boards",
      "CONFIG_GPIO=y",
      "CONFIG_PINCTRL=y",
    ].join("\n");
  }

  return [
    `# Generated baseline for ${board.name}`,
    "CONFIG_GPIO=y",
    "CONFIG_PINCTRL=y",
    "CONFIG_SERIAL=y",
    `CONFIG_BOARD_${board.board.toUpperCase().replace(/[^A-Z0-9]+/g, "_")}=y`,
  ].join("\n");
}

export function buildGeneratedFragmentsFromBoard(board?: BoardSummary | null): Record<string, unknown> {
  if (!board) {
    return {
      board: {
        state: "pending",
      },
      outputs: {
        overlay: "generated-overlay.overlay",
        config: "generated.conf",
      },
    };
  }

  return {
    board: {
      id: board.board,
      name: board.name,
      package: board.package,
      pin_count: board.pin_count,
    },
    outputs: {
      overlay: `${board.board}.overlay`,
      config: `${board.board}.conf`,
    },
    protocols: {
      state: "seeded-from-project-document",
    },
    metadata: {
      fragment_owner: "project-controller",
      generated_from: "typed-shell-seed",
    },
  };
}

export function formatGeneratedFragments(fragments: Record<string, unknown>): string {
  if (!Object.keys(fragments).length) {
    return "";
  }

  return JSON.stringify(fragments, null, 2);
}