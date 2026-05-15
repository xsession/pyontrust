import { fireEvent, render, screen } from "@testing-library/react";
import { PinAssignmentsPanel } from "./PinAssignmentsPanel";
import type { PinAssignmentsViewModel } from "../shared/viewModels/pinAssignments";

function createPinAssignmentsViewModel(overrides?: Partial<PinAssignmentsViewModel>): PinAssignmentsViewModel {
  return {
    summary: {
      resolvedCount: 0,
      savedCount: 0,
      unresolvedCount: 0,
    },
    rows: [],
    issuesByPinNumber: {},
    propertyValuesByPinNumber: {},
    altFunctionOptionsByPinNumber: {},
    ...overrides,
  };
}

describe("PinAssignmentsPanel", () => {
  it("filters between resolved and unresolved pin assignments", () => {
    render(
      <PinAssignmentsPanel
        pinAssignments={createPinAssignmentsViewModel({
          summary: {
            resolvedCount: 1,
            savedCount: 2,
            unresolvedCount: 1,
          },
          rows: [
            {
              pinNumber: "7",
              savedLabel: "Manual properties only",
              resolvedLabel: "No live board match",
              resolvedRoute: "Unresolved",
              propertyKeys: ["bias"],
              resolution: "unresolved",
              selectedAltFunctionValue: "",
            },
            {
              pinNumber: "12",
              savedLabel: "UART0_TX",
              resolvedLabel: "UART0_TX live",
              resolvedRoute: "uart0.tx",
              propertyKeys: [],
              resolution: "resolved",
              selectedAltFunctionValue: "3:45:UART0_TX",
            },
          ],
        })}
        onClearPinAssignment={() => undefined}
        onAssignPinAltFunction={() => undefined}
        onUpdatePinBooleanProperty={() => undefined}
      />,
    );

    expect(screen.getByRole("button", { name: "Pin 12 UART0_TX" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Pin 7 Manual properties only" })).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Resolved (1)" }));
    expect(screen.getByRole("button", { name: "Pin 12 UART0_TX" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Pin 7 Manual properties only" })).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Unresolved (1)" }));
    expect(screen.getByRole("button", { name: "Pin 7 Manual properties only" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Pin 12 UART0_TX" })).not.toBeInTheDocument();
  });

  it("emits a clear command for the selected pin row", () => {
    const clearPinAssignment = vi.fn();

    render(
      <PinAssignmentsPanel
        pinAssignments={createPinAssignmentsViewModel({
          summary: {
            resolvedCount: 1,
            savedCount: 1,
            unresolvedCount: 0,
          },
          rows: [
            {
              pinNumber: "12",
              savedLabel: "UART0_TX",
              resolvedLabel: "UART0_TX live",
              resolvedRoute: "uart0.tx",
              propertyKeys: [],
              resolution: "resolved",
              selectedAltFunctionValue: "3:45:UART0_TX",
            },
          ],
        })}
        onClearPinAssignment={clearPinAssignment}
        onAssignPinAltFunction={() => undefined}
        onUpdatePinBooleanProperty={() => undefined}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "Clear" }));
    expect(clearPinAssignment).toHaveBeenCalledWith("12");
  });

  it("shows a detail inspector for the selected pin row", () => {
    render(
      <PinAssignmentsPanel
        pinAssignments={createPinAssignmentsViewModel({
          summary: {
            resolvedCount: 1,
            savedCount: 2,
            unresolvedCount: 1,
          },
          rows: [
            {
              pinNumber: "7",
              savedLabel: "Manual properties only",
              resolvedLabel: "No live board match",
              resolvedRoute: "Unresolved",
              propertyKeys: ["bias"],
              resolution: "unresolved",
              selectedAltFunctionValue: "",
            },
            {
              pinNumber: "12",
              savedLabel: "UART0_TX",
              resolvedLabel: "UART0_TX live",
              resolvedRoute: "uart0.tx",
              propertyKeys: [],
              resolution: "resolved",
              selectedAltFunctionValue: "3:45:UART0_TX",
            },
          ],
        })}
        onClearPinAssignment={() => undefined}
        onAssignPinAltFunction={() => undefined}
        onUpdatePinBooleanProperty={() => undefined}
      />,
    );

    expect(screen.getByText("Pin detail")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Pin 7 Manual properties only" })).toBeInTheDocument();
    expect(screen.getByText("Saved only, unresolved")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Pin 12 UART0_TX" }));
    expect(screen.getByText("UART0_TX live")).toBeInTheDocument();
    expect(screen.getByText("Matched against board definition")).toBeInTheDocument();
  });

  it("emits pin property changes for the selected pin", () => {
    const updatePinBooleanProperty = vi.fn();

    render(
      <PinAssignmentsPanel
        pinAssignments={createPinAssignmentsViewModel({
          summary: {
            resolvedCount: 1,
            savedCount: 1,
            unresolvedCount: 0,
          },
          rows: [
            {
              pinNumber: "12",
              savedLabel: "UART0_TX",
              resolvedLabel: "UART0_TX live",
              resolvedRoute: "uart0.tx",
              propertyKeys: ["bias_pull_up", "bias_pull_down", "drive_open_drain", "input_enable"],
              resolution: "resolved",
              selectedAltFunctionValue: "3:45:UART0_TX",
            },
          ],
          propertyValuesByPinNumber: {
            "12": {
              bias_pull_up: false,
              bias_pull_down: true,
              drive_open_drain: false,
              input_enable: true,
            },
          },
        })}
        onClearPinAssignment={() => undefined}
        onAssignPinAltFunction={() => undefined}
        onUpdatePinBooleanProperty={updatePinBooleanProperty}
      />,
    );

    fireEvent.click(screen.getByRole("checkbox", { name: "Pull-up" }));
    expect(updatePinBooleanProperty).toHaveBeenCalledWith("12", "bias_pull_up", true);

    expect(screen.getByRole("checkbox", { name: "Pull-down" })).toBeChecked();
    expect(screen.getByRole("checkbox", { name: "Input enable" })).toBeChecked();
    expect(screen.getByRole("checkbox", { name: "Open-drain" })).not.toBeChecked();

    fireEvent.click(screen.getByRole("checkbox", { name: "Open-drain" }));
    expect(updatePinBooleanProperty).toHaveBeenCalledWith("12", "drive_open_drain", true);
  });

  it("shows a warning when pull-up and pull-down are both enabled", () => {
    render(
      <PinAssignmentsPanel
        pinAssignments={createPinAssignmentsViewModel({
          summary: {
            resolvedCount: 1,
            savedCount: 1,
            unresolvedCount: 0,
          },
          rows: [
            {
              pinNumber: "12",
              savedLabel: "UART0_TX",
              resolvedLabel: "UART0_TX live",
              resolvedRoute: "uart0.tx",
              propertyKeys: ["bias_pull_up", "bias_pull_down"],
              resolution: "resolved",
              selectedAltFunctionValue: "3:45:UART0_TX",
            },
          ],
          issuesByPinNumber: {
            "12": [
              {
                id: "pin:12:pull-clash",
                title: "Pull-up and pull-down are both enabled",
                summary: "The current bias properties request opposite electrical defaults on the same pad.",
              },
            ],
          },
          propertyValuesByPinNumber: {
            "12": {
              bias_pull_up: true,
              bias_pull_down: true,
            },
          },
        })}
        onClearPinAssignment={() => undefined}
        onAssignPinAltFunction={() => undefined}
        onUpdatePinBooleanProperty={() => undefined}
      />,
    );

    expect(screen.getByText("Pull-up and pull-down are both enabled")).toBeInTheDocument();
    expect(screen.getByText("The current bias properties request opposite electrical defaults on the same pad.")).toBeInTheDocument();
  });

  it("emits alt-function reassignment for the selected pin", () => {
    const assignPinAltFunction = vi.fn();

    render(
      <PinAssignmentsPanel
        pinAssignments={createPinAssignmentsViewModel({
          summary: {
            resolvedCount: 1,
            savedCount: 1,
            unresolvedCount: 0,
          },
          rows: [
            {
              pinNumber: "12",
              savedLabel: "UART0_TX",
              resolvedLabel: "UART0_TX live",
              resolvedRoute: "uart0.tx",
              propertyKeys: [],
              resolution: "resolved",
              selectedAltFunctionValue: "3:45:UART0_TX",
            },
          ],
          altFunctionOptionsByPinNumber: {
            "12": [
              {
                value: "3:45:UART0_TX",
                label: "F3 UART0_TX",
                detail: "uart0.tx • PINCM 45",
                functionId: 3,
                pincm: 45,
                name: "UART0_TX",
                peripheral: "uart0",
                signal: "tx",
                direction: "out",
              },
              {
                value: "4:46:I2C0_SCL",
                label: "F4 I2C0_SCL",
                detail: "i2c0.scl • PINCM 46",
                functionId: 4,
                pincm: 46,
                name: "I2C0_SCL",
                peripheral: "i2c0",
                signal: "scl",
                direction: "io",
              },
            ],
          },
        })}
        onClearPinAssignment={() => undefined}
        onAssignPinAltFunction={assignPinAltFunction}
        onUpdatePinBooleanProperty={() => undefined}
      />,
    );

    fireEvent.change(screen.getByRole("combobox", { name: "Alt function" }), {
      target: { value: "4:46:I2C0_SCL" },
    });

    expect(assignPinAltFunction).toHaveBeenCalledWith(
      "12",
      expect.objectContaining({ functionId: 4, name: "I2C0_SCL", peripheral: "i2c0" }),
    );
  });

  it("renders the package surface controls for the selected pin workflow", () => {
    render(
      <PinAssignmentsPanel
        pinAssignments={createPinAssignmentsViewModel({
          summary: {
            resolvedCount: 1,
            savedCount: 1,
            unresolvedCount: 0,
          },
          rows: [
            {
              pinNumber: "12",
              savedLabel: "UART0_TX",
              resolvedLabel: "UART0_TX live",
              resolvedRoute: "uart0.tx",
              propertyKeys: [],
              resolution: "resolved",
              selectedAltFunctionValue: "3:45:UART0_TX",
            },
          ],
          altFunctionOptionsByPinNumber: {
            "12": [
              {
                value: "3:45:UART0_TX",
                label: "F3 UART0_TX",
                detail: "uart0.tx • PINCM 45",
                functionId: 3,
                pincm: 45,
                name: "UART0_TX",
                peripheral: "uart0",
                signal: "tx",
                direction: "out",
              },
            ],
          },
        })}
        onClearPinAssignment={() => undefined}
        onAssignPinAltFunction={() => undefined}
        onUpdatePinBooleanProperty={() => undefined}
      />,
    );

    expect(screen.getByLabelText("Scene viewport controls")).toBeInTheDocument();
    expect(screen.getByLabelText("Package surface")).toBeInTheDocument();
    expect(screen.getByRole("combobox", { name: "Quick assign alt function" })).toBeInTheDocument();
  });
});