import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { BoardDefinition, BoardEditorDraftListResponse, BoardSummary, ClockTreeSummary, ModuleDefinition, ZephyrCatalogResponse } from "../contracts/api";
import { App } from "./App";
import * as exportArtifacts from "../project/exportArtifacts";

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

      if (pathname === "/api/project-file/save") {
        return Promise.resolve(jsonResponse({
          saved: true,
          file_path: "C:/tmp/app-browser-flow.zpinproj",
        }));
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

    fireEvent.click(await screen.findByRole("button", { name: /RP2040/i }, { timeout: 10000 }));

    await waitFor(() => {
      expect(screen.getAllByText("RP2040 (Pico DIP-40)").length).toBeGreaterThan(0);
    }, { timeout: 10000 });
    expect(screen.getAllByText("platforms/cpus/raspberrypi/rp2040.repl").length).toBeGreaterThan(0);

    fireEvent.keyDown(window, { key: "?", shiftKey: true });
    expect(await screen.findByText("Workspace actions")).toBeInTheDocument();
    expect(screen.getByText("Keyboard map")).toBeInTheDocument();

    fireEvent.keyDown(document, { key: "Escape" });

    fireEvent.click(screen.getByRole("tab", { name: /Diagnostics/i }));
    await waitFor(() => {
      expect(screen.getAllByText("Project integrity checks are passing.").length).toBeGreaterThan(0);
    }, { timeout: 10000 });
  }, 15000);

  it("supports a browser flow for save, focus, export, and diagnostics review", async () => {
    const downloadSpy = vi.spyOn(exportArtifacts, "downloadGeneratedArtifactBundle").mockReturnValue(3);

    render(<App />);

    expect(await screen.findByText("Pin Configurator workspace")).toBeInTheDocument();

    fireEvent.click(await screen.findByRole("button", { name: /RP2040/i }, { timeout: 10000 }));

    await waitFor(() => {
      expect(screen.getAllByText("RP2040 (Pico DIP-40)").length).toBeGreaterThan(0);
    }, { timeout: 10000 });

    fireEvent.change(screen.getByLabelText("Project file path"), {
      target: { value: "C:/tmp/app-browser-flow.zpinproj" },
    });

    fireEvent.click(screen.getAllByRole("button", { name: "Seed Overlay" })[0]);

    await waitFor(() => {
      expect(screen.getAllByText(/Generated project artifacts for RP2040/i).length).toBeGreaterThan(0);
    }, { timeout: 10000 });

    fireEvent.click(screen.getByRole("button", { name: "Save Project" }));

    await waitFor(() => {
      expect(screen.getAllByText("Saved typed project document to C:/tmp/app-browser-flow.zpinproj.").length).toBeGreaterThan(0);
    }, { timeout: 10000 });

    fireEvent.click(screen.getByRole("button", { name: "Open Generated Overlay" }));
    expect(screen.getByTestId("workspace-dock-fallback")).toHaveAttribute("data-focus-panel", "workspace-generated-overlay");

    fireEvent.click(screen.getAllByRole("button", { name: "Export Artifacts" })[0]);

    await waitFor(() => {
      expect(downloadSpy).toHaveBeenCalledTimes(1);
      expect(screen.getAllByText("Exported 3 generated artifact files from the canonical project document.").length).toBeGreaterThan(0);
    }, { timeout: 10000 });

    fireEvent.click(screen.getAllByRole("button", { name: "Review Diagnostics" })[0]);

    await waitFor(() => {
      expect(screen.getByRole("tab", { name: /Diagnostics/i })).toHaveAttribute("aria-selected", "true");
      expect(screen.getAllByText("Project integrity checks are passing.").length).toBeGreaterThan(0);
    }, { timeout: 10000 });
  }, 15000);
});