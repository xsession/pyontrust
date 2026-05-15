import { createEmptyProjectDocument } from "../contracts/api";
import {
  selectPinAssignmentIssues,
  selectPinAssignmentRows,
  selectPinAssignmentSummary,
  selectPinAssignmentsViewModel,
  selectProjectArtifactStatus,
  selectProjectIntegrityLabel,
  selectProjectIntegrityStatus,
  selectProjectReadinessLabel,
  selectProjectReadinessStatus,
} from "./selectors";

describe("project selectors", () => {
  it("reports pending readiness for an empty project", () => {
    const project = createEmptyProjectDocument();

    expect(selectProjectArtifactStatus(project)).toEqual({
      overlayReady: false,
      configReady: false,
      fragmentGroupCount: 0,
      protocolEntryCount: 1,
      enabledProtocolEntryCount: 1,
      hasArtifactPayload: false,
      authorityState: "missing",
      authorityReason: "No generated artifact payload is stored in the project document.",
      authoritative: false,
    });
    expect(selectProjectReadinessStatus(project)).toEqual({
      hasBoard: false,
      hasRenodeTarget: false,
      hasGeneratedArtifacts: false,
      hasProtocolEntries: true,
      readySectionCount: 1,
    });
    expect(selectProjectReadinessLabel(project)).toBe("Project board pending");
    expect(selectProjectIntegrityStatus(project)).toEqual({
      issues: ["Board assignment missing"],
      warningCount: 1,
      staleArtifacts: false,
    });
    expect(selectProjectIntegrityLabel(project)).toBe("Integrity warnings: 1");
  });

  it("reports ready sections for a populated project", () => {
    const project = createEmptyProjectDocument();
    project.board_id = "lp_mspm0g3507";
    project.renode.enabled = true;
    project.renode.platform = "platforms/boards/ti/lp_mspm0g3507.repl";
    project.generated_overlay = "/dts-v1/;";
    project.generated_conf = "CONFIG_GPIO=y";
    project.generated_fragments = {
      board: { id: "lp_mspm0g3507" },
      outputs: { overlay: "lp_mspm0g3507.overlay", config: "lp_mspm0g3507.conf" },
      protocols: { code: "generated" },
    };

    expect(selectProjectArtifactStatus(project)).toEqual({
      overlayReady: true,
      configReady: true,
      fragmentGroupCount: 3,
      protocolEntryCount: 1,
      enabledProtocolEntryCount: 1,
      hasArtifactPayload: true,
      authorityState: "authoritative",
      authorityReason: "Generated fragments fully describe the current overlay, config, and project context.",
      authoritative: true,
    });
    expect(selectProjectReadinessStatus(project)).toEqual({
      hasBoard: true,
      hasRenodeTarget: true,
      hasGeneratedArtifacts: true,
      hasProtocolEntries: true,
      readySectionCount: 4,
    });
    expect(selectProjectReadinessLabel(project)).toBe("Project shell ready");
    expect(selectProjectIntegrityStatus(project)).toEqual({
      issues: [],
      warningCount: 0,
      staleArtifacts: false,
    });
    expect(selectProjectIntegrityLabel(project)).toBe("Integrity checks passing");
  });

  it("reports a clean integrity state when generated fragments match the current board and protocols", () => {
    const project = createEmptyProjectDocument();
    project.board_id = "lp_mspm0g3507";
    project.renode.enabled = true;
    project.renode.platform = "platforms/boards/ti/lp_mspm0g3507.repl";
    project.generated_overlay = "/dts-v1/;";
    project.generated_conf = "CONFIG_GPIO=y";
    project.generated_fragments = {
      board: { id: "lp_mspm0g3507" },
      outputs: { overlay: "lp_mspm0g3507.overlay", config: "lp_mspm0g3507.conf" },
      protocols: { code: "generated" },
    };

    expect(selectProjectIntegrityStatus(project)).toEqual({
      issues: [],
      warningCount: 0,
      staleArtifacts: false,
    });
    expect(selectProjectIntegrityLabel(project)).toBe("Integrity checks passing");
  });

  it("marks generated artifacts stale when stored text is not fully described by fragments", () => {
    const project = createEmptyProjectDocument();
    project.board_id = "lp_mspm0g3507";
    project.generated_overlay = "/dts-v1/;";
    project.generated_conf = "CONFIG_GPIO=y";
    project.generated_fragments = {
      board: { id: "lp_mspm0g3507" },
      protocols: { code: "generated" },
    };

    expect(selectProjectArtifactStatus(project)).toEqual({
      overlayReady: true,
      configReady: true,
      fragmentGroupCount: 2,
      protocolEntryCount: 1,
      enabledProtocolEntryCount: 1,
      hasArtifactPayload: true,
      authorityState: "stale",
      authorityReason: "Generated fragments are missing output descriptors for the stored overlay or config payload.",
      authoritative: false,
    });
    expect(selectProjectIntegrityStatus(project)).toEqual({
      issues: [
        "Generated artifacts appear stale: Generated fragments are missing output descriptors for the stored overlay or config payload.",
      ],
      warningCount: 1,
      staleArtifacts: true,
    });
    expect(selectProjectIntegrityLabel(project)).toBe("Integrity warnings: 1 including stale artifacts");
  });

  it("derives stable pin assignment rows and summary data", () => {
    const summary = selectPinAssignmentSummary(
      {
        "12": { af: { function_id: 3, name: "UART0_TX", pincm: 45, peripheral: "uart0", signal: "tx", direction: "out" } },
        "7": { props: { bias: "pull-up" } },
      },
      {
        "12": {
          af: {
            function_id: 3,
            name: "UART0_TX live",
            pincm: 45,
            peripheral: "uart0",
            signal: "tx",
            direction: "out",
            zephyr_pinmux: "UART0_TX_PA12",
          },
        },
      },
    );

    expect(summary).toEqual({
      resolvedCount: 1,
      savedCount: 2,
      unresolvedCount: 1,
    });
    expect(
      selectPinAssignmentRows(
        {
          "12": { af: { function_id: 3, name: "UART0_TX", pincm: 45, peripheral: "uart0", signal: "tx", direction: "out" } },
          "7": { props: { bias: "pull-up" } },
        },
        {
          "12": {
            af: {
              function_id: 3,
              name: "UART0_TX live",
              pincm: 45,
              peripheral: "uart0",
              signal: "tx",
              direction: "out",
              zephyr_pinmux: "UART0_TX_PA12",
            },
          },
        },
      ),
    ).toEqual([
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
    ]);
  });

  it("reports a pin issue when pull-up and pull-down are both enabled", () => {
    expect(
      selectPinAssignmentIssues("12", {
        props: {
          bias_pull_up: true,
          bias_pull_down: true,
        },
      }),
    ).toEqual([
      {
        id: "pin:12:pull-clash",
        title: "Pull-up and pull-down are both enabled",
        summary: "The current bias properties request opposite electrical defaults on the same pad.",
      },
    ]);
  });

  it("reports a pin issue when the assigned peripheral is disabled", () => {
    expect(
      selectPinAssignmentIssues(
        "12",
        {
          af: {
            function_id: 3,
            name: "UART0_TX",
            pincm: 45,
            peripheral: "uart0",
            signal: "tx",
            direction: "out",
          },
        },
        {
          uart0: false,
        },
        {},
      ),
    ).toEqual([
      {
        id: "pin:12:disabled-peripheral",
        title: "Assigned peripheral is disabled",
        summary: "Pin 12 is routed through uart0, but that peripheral is currently disabled in the canonical project state.",
      },
    ]);
  });

  it("reports a pin issue when the same peripheral signal is claimed on another pin", () => {
    expect(
      selectPinAssignmentIssues(
        "12",
        {
          af: {
            function_id: 3,
            name: "UART0_TX",
            pincm: 45,
            peripheral: "uart0",
            signal: "tx",
            direction: "out",
          },
        },
        {},
        {
          "12": {
            af: {
              function_id: 3,
              name: "UART0_TX",
              pincm: 45,
              peripheral: "uart0",
              signal: "tx",
              direction: "out",
            },
          },
          "14": {
            af: {
              function_id: 8,
              name: "UART0_TX_ALT",
              pincm: 61,
              peripheral: "uart0",
              signal: "tx",
              direction: "out",
            },
          },
        },
      ),
    ).toEqual([
      {
        id: "pin:12:duplicate-signal:uart0:tx",
        title: "uart0.tx is assigned more than once",
        summary: "Only one pin assignment should drive uart0.tx. Also claimed on pin 14.",
      },
    ]);
  });

  it("builds a deterministic pin assignments view model", () => {
    const viewModel = selectPinAssignmentsViewModel(
      {
        "12": {
          props: {
            bias_pull_up: true,
            bias_pull_down: true,
          },
          af: {
            function_id: 8,
            name: "UART0_TX_ALT",
            pincm: 61,
            peripheral: "uart0",
            signal: "tx",
            direction: "out",
          },
        },
        "7": {
          props: {
            drive_open_drain: true,
            bias_pull_down: true,
          },
          af: {
            function_id: 3,
            name: "UART0_TX",
            pincm: 45,
            peripheral: "uart0",
            signal: "tx",
            direction: "out",
          },
        },
      },
      {
        "7": {
          af: {
            function_id: 3,
            name: "UART0_TX live",
            pincm: 45,
            peripheral: "uart0",
            signal: "tx",
            direction: "out",
            zephyr_pinmux: "UART0_TX_PA7",
          },
        },
      },
      {
        soc: "mspm0g3507",
        board: "lp_mspm0g3507",
        vendor: "Texas Instruments",
        package: "LQFP",
        pin_count: 32,
        flash_size_kb: 128,
        sram_size_kb: 32,
        clock_hz: 80000000,
        cores: [],
        output_targets: [],
        pins: [
          {
            number: 7,
            name: "PA7",
            port: "A",
            gpio_num: 7,
            kind: "gpio",
            side: "left",
            default_function: "GPIO",
            alt_functions: [
              {
                function_id: 8,
                name: "UART0_TX_ALT",
                pincm: 61,
                peripheral: "uart0",
                signal: "tx",
                direction: "out",
                zephyr_pinmux: "UART0_TX_ALT_PA7",
              },
              {
                function_id: 3,
                name: "UART0_TX",
                pincm: 45,
                peripheral: "uart0",
                signal: "tx",
                direction: "out",
                zephyr_pinmux: "UART0_TX_PA7",
              },
            ],
          },
          {
            number: 12,
            name: "PA12",
            port: "A",
            gpio_num: 12,
            kind: "gpio",
            side: "right",
            default_function: "GPIO",
            alt_functions: [
              {
                function_id: 11,
                name: "GPIO",
                pincm: 12,
                peripheral: "gpio",
                signal: "gpio",
                direction: "inout",
                zephyr_pinmux: "GPIO_PA12",
              },
            ],
          },
        ],
        peripherals: [],
        external_devices: [],
      },
      {
        uart0: false,
      },
    );

    expect(viewModel.rows.map((row) => row.pinNumber)).toEqual(["7", "12"]);
    expect(Object.keys(viewModel.issuesByPinNumber)).toEqual(["7", "12"]);
    expect(Object.keys(viewModel.propertyValuesByPinNumber)).toEqual(["7", "12"]);
    expect(Object.keys(viewModel.altFunctionOptionsByPinNumber)).toEqual(["7", "12"]);
    expect(viewModel.rows[0]?.propertyKeys).toEqual(["bias_pull_down", "drive_open_drain"]);
    expect(Object.keys(viewModel.propertyValuesByPinNumber["7"] ?? {})).toEqual(["bias_pull_down", "drive_open_drain"]);
    expect(viewModel.altFunctionOptionsByPinNumber["7"]?.map((option) => option.value)).toEqual([
      "3:45:UART0_TX",
      "8:61:UART0_TX_ALT",
    ]);
    expect(viewModel.issuesByPinNumber["7"]?.map((issue) => issue.id)).toEqual([
      "pin:7:disabled-peripheral",
      "pin:7:duplicate-signal:uart0:tx",
    ]);
    expect(viewModel.issuesByPinNumber["12"]?.map((issue) => issue.id)).toEqual([
      "pin:12:disabled-peripheral",
      "pin:12:duplicate-signal:uart0:tx",
      "pin:12:pull-clash",
    ]);
  });
});