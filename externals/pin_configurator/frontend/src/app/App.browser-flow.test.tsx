import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { BoardDefinition, BoardEditorDraftListResponse, BoardSummary, ClockTreeSummary, ModuleDefinition, ZephyrCatalogResponse } from "../contracts/api";
import { App } from "./App";

vi.mock("../workspace/WorkspaceDock", () => ({
  WorkspaceDock: ({ focusRequest }: { focusRequest?: { panelId: string } | null }) => (
    <div data-testid="workspace-dock-fallback" data-focus-panel={focusRequest?.panelId ?? ""}>
      Dock mock
    </div>
  ),
}));

const boards: BoardSummary[] = [
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

const boardDefinitions: Record<string, BoardDefinition> = {
  mspm0g3507: {
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
    pins: [],
    peripherals: [],
    external_devices: [],
  },
  rp2040: {
    soc: "RP2040",
    board: "rpi_pico",
    vendor: "raspberrypi",
    package: "Pico DIP-40",
    pin_count: 40,
    flash_size_kb: 2048,
    sram_size_kb: 264,
    clock_hz: 133000000,
    cores: [],
    output_targets: [],
    pins: [],
    peripherals: [],
    external_devices: [],
  },
};

const emptyCatalogResponse: ZephyrCatalogResponse = {
  root: "C:/zephyr",
  summary: {
    mcu_count: 0,
    sensor_count: 0,
  },
  mcus: [],
  sensors: [],
};

const emptyDraftsResponse: BoardEditorDraftListResponse = {
  drafts: [],
};

const emptyModules: ModuleDefinition[] = [];
const emptyClockTrees: ClockTreeSummary[] = [];

function jsonResponse(body: unknown) {
  return new Response(JSON.stringify(body), {
    status: 200,
    headers: {
      "Content-Type": "application/json",
    },
  });
}

describe("App browser flow", () => {
  beforeEach(() => {
    window.localStorage.clear();
    vi.spyOn(globalThis, "fetch").mockImplementation((input) => {
      const requestUrl = typeof input === "string" ? input : input instanceof URL ? input.toString() : input.url;
      const pathname = new URL(requestUrl, "http://127.0.0.1").pathname;

      if (pathname === "/api/boards") {
        return Promise.resolve(jsonResponse(boards));
      }

      if (pathname === "/api/modules") {
        return Promise.resolve(jsonResponse(emptyModules));
      }

      if (pathname === "/api/clock-trees") {
        return Promise.resolve(jsonResponse(emptyClockTrees));
      }

      if (pathname === "/api/zephyr/catalog") {
        return Promise.resolve(jsonResponse(emptyCatalogResponse));
      }

      if (pathname === "/api/board-editor/drafts") {
        return Promise.resolve(jsonResponse(emptyDraftsResponse));
      }

      if (pathname.startsWith("/api/board/")) {
        const boardId = decodeURIComponent(pathname.slice("/api/board/".length));
        return Promise.resolve(jsonResponse(boardDefinitions[boardId] ?? boardDefinitions.mspm0g3507));
      }

      throw new Error(`Unhandled fetch in App browser flow test: ${pathname}`);
    });
  });

  afterEach(() => {
    vi.restoreAllMocks();
    window.localStorage.clear();
  });

  it("loads the workspace shell and supports a keyboard-driven review flow", async () => {
    render(<App />);

    expect(await screen.findByText("Pin Configurator workspace")).toBeInTheDocument();
    expect(await screen.findByText("Execution workbench")).toBeInTheDocument();

    fireEvent.click(await screen.findByRole("button", { name: /RP2040/i }, { timeout: 5000 }));

    await waitFor(() => {
      expect(screen.getAllByText("RP2040 (Pico DIP-40)").length).toBeGreaterThan(0);
    });
    expect(screen.getAllByText("platforms/cpus/raspberrypi/rp2040.repl").length).toBeGreaterThan(0);

    fireEvent.keyDown(window, { key: "?", shiftKey: true });
    expect(await screen.findByText("Workspace actions")).toBeInTheDocument();
    expect(screen.getByText("Keyboard map")).toBeInTheDocument();

    fireEvent.keyDown(document, { key: "Escape" });

    fireEvent.click(screen.getByRole("tab", { name: /Diagnostics/i }));
    expect(await screen.findByText("Project integrity checks are passing.")).toBeInTheDocument();
  });
});