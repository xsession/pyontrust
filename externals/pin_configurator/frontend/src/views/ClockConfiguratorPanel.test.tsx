import { render, screen } from "@testing-library/react";
import { ClockConfiguratorPanel } from "./ClockConfiguratorPanel";
import type { ClockConfiguratorPresenter } from "../domains/clock/clockConfiguratorPresenter";

function createPresenter(): ClockConfiguratorPresenter {
  return {
    loading: false,
    error: "",
    status: "Loaded clock tree MSPM0G3507 Clock Tree.",
    availableTrees: [{ id: "mspm0g3507", name: "MSPM0G3507 Clock Tree", node_count: 4, soc: "MSPM0G3507" }],
    currentTree: { id: "mspm0g3507", name: "MSPM0G3507 Clock Tree", nodes: [], peripheral_clocks: { uart0: "sysclk" } },
    nodes: [
      { id: "sysosc", name: "SYSOSC", type: "source", icon: "🔷", frequencyHz: 32000000, props: [] },
      { id: "pll0", name: "PLL0", type: "pll", icon: "⚡", frequencyHz: 80000000, props: [] },
      { id: "sysclk", name: "SYSCLK", type: "mux", icon: "🔀", frequencyHz: 80000000, props: [] },
      { id: "uart0", name: "UART0", type: "output", icon: "🏁", frequencyHz: 80000000, props: [] },
    ],
    selectedNodeId: "pll0",
    selectedNode: { id: "pll0", name: "PLL0", type: "pll", icon: "⚡", frequencyHz: 80000000, props: [] },
    values: {},
    frequencies: { sysosc: 32000000, pll0: 80000000, sysclk: 80000000, uart0: 80000000 },
    warnings: ["pll0 configuration requires board review"],
    generatedOverlay: "",
    generatedConf: "",
    selectTree: () => undefined,
    selectNode: () => undefined,
    updateNodeProperty: () => undefined,
    generateConfig: () => undefined,
  };
}

describe("ClockConfiguratorPanel", () => {
  it("renders the lane-grouped clock tree scene and property editor", () => {
    render(<ClockConfiguratorPanel presenter={createPresenter()} />);

    expect(screen.getByLabelText("Scene viewport controls")).toBeInTheDocument();
    expect(screen.getByLabelText("Clock tree scene")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Generate Clock Config" })).toBeInTheDocument();
    expect(screen.getAllByText("Clock warning").length).toBeGreaterThan(0);
    expect(screen.getByLabelText("Clock readiness warnings")).toBeInTheDocument();
    expect(screen.getByText("Clock editing loop")).toBeInTheDocument();
    expect(screen.getByLabelText("Clock derived frequencies")).toBeInTheDocument();
  });
});