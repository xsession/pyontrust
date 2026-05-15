import { createEmptyProjectDocument } from "../contracts/api";
import { buildRenodeSimulationExportBundle, downloadRenodeSimulationExportBundle } from "./exportSimulation";

describe("exportSimulation", () => {
  it("builds a Renode bundle directly from the canonical project document", () => {
    const project = createEmptyProjectDocument();
    project.board_id = "lp_mspm0g3507";
    project.generated_overlay = "/dts-v1/;";
    project.generated_conf = "CONFIG_GPIO=y";
    project.generated_fragments = {
      outputs: {
        overlay: "lp_mspm0g3507.overlay",
        config: "lp_mspm0g3507.conf",
      },
    };
    project.renode.enabled = true;
    project.renode.platform = "platforms/boards/ti/lp_mspm0g3507.repl";
    project.renode.resc = "mach create\nshowAnalyzer sysbus.uart0";
    project.renode.robot = "*** Settings ***\nSuite Setup  Log  Ready";

    const bundle = buildRenodeSimulationExportBundle(project);

    expect(bundle.baseName).toBe("lp_mspm0g3507");
    expect(bundle.files.map((file) => file.fileName)).toEqual([
      "lp_mspm0g3507.overlay",
      "lp_mspm0g3507.conf",
      "lp_mspm0g3507.generated-fragments.json",
      "lp_mspm0g3507.resc",
      "lp_mspm0g3507.robot",
      "lp_mspm0g3507.simulation.json",
    ]);
    expect(bundle.manifest).toEqual({
      boardId: "lp_mspm0g3507",
      renodeEnabled: true,
      platform: "platforms/boards/ti/lp_mspm0g3507.repl",
      uart: "sysbus.uart0",
      bootLine: "Pin Configurator demo boot",
      appbenchTarget: "appbench",
      robotTarget: "robotbench",
    });
  });

  it("downloads every file in the Renode bundle through the shared downloader path", () => {
    const project = createEmptyProjectDocument();
    project.renode.enabled = true;
    project.renode.platform = "platforms/boards/ti/lp_mspm0g3507.repl";

    const bundle = buildRenodeSimulationExportBundle(project);
    const downloadFile = vi.fn();

    const fileCount = downloadRenodeSimulationExportBundle(bundle, downloadFile);

    expect(fileCount).toBe(1);
    expect(downloadFile).toHaveBeenCalledTimes(1);
    expect(downloadFile).toHaveBeenCalledWith({
      fileName: "pin-configurator.simulation.json",
      content: JSON.stringify(bundle.manifest, null, 2),
      mimeType: "application/json;charset=utf-8",
    });
  });
});