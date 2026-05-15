import { createEmptyProjectDocument } from "../contracts/api";
import { buildGeneratedArtifactExportBundle, downloadGeneratedArtifactBundle } from "./exportArtifacts";

describe("exportArtifacts", () => {
  it("builds export files directly from the canonical project document", () => {
    const project = createEmptyProjectDocument();
    project.board_id = "lp_mspm0g3507";
    project.generated_overlay = "/dts-v1/;";
    project.generated_conf = "CONFIG_GPIO=y";
    project.generated_fragments = {
      outputs: {
        overlay: "lp_mspm0g3507.overlay",
        config: "lp_mspm0g3507.conf",
      },
      metadata: {
        fragment_owner: "project-controller",
      },
    };

    const bundle = buildGeneratedArtifactExportBundle(project);

    expect(bundle.baseName).toBe("lp_mspm0g3507");
    expect(bundle.files).toEqual([
      {
        fileName: "lp_mspm0g3507.overlay",
        content: "/dts-v1/;",
        mimeType: "text/plain;charset=utf-8",
      },
      {
        fileName: "lp_mspm0g3507.conf",
        content: "CONFIG_GPIO=y",
        mimeType: "text/plain;charset=utf-8",
      },
      {
        fileName: "lp_mspm0g3507.generated-fragments.json",
        content: JSON.stringify(project.generated_fragments, null, 2),
        mimeType: "application/json;charset=utf-8",
      },
    ]);
  });

  it("replays bundle files through the downloader callback", () => {
    const project = createEmptyProjectDocument();
    project.generated_overlay = "/dts-v1/;";
    const bundle = buildGeneratedArtifactExportBundle(project);
    const downloadFile = vi.fn();

    const fileCount = downloadGeneratedArtifactBundle(bundle, downloadFile);

    expect(fileCount).toBe(1);
    expect(downloadFile).toHaveBeenCalledTimes(1);
    expect(downloadFile).toHaveBeenCalledWith({
      fileName: "pin-configurator.overlay",
      content: "/dts-v1/;",
      mimeType: "text/plain;charset=utf-8",
    });
  });
});