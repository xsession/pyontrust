import { createEmptyProjectDocument } from "./normalize";
import { buildProjectFileSaveRequest, serializeProjectDocument } from "./serialize";

describe("project document serialization", () => {
  it("serializes canonical project documents without workspace-only state", () => {
    const project = createEmptyProjectDocument();
    project.board_id = "lp_mspm0g3507";

    const result = serializeProjectDocument(project);

    expect(result.board_id).toBe("lp_mspm0g3507");
    expect(result).not.toHaveProperty("projectFilePath");
    expect(result).not.toHaveProperty("projectBusy");
  });

  it("builds a save request dto with the file path alongside the serialized project", () => {
    const project = createEmptyProjectDocument();
    project.board_id = "rpi_pico";

    const result = buildProjectFileSaveRequest(project, "C:/tmp/demo.zpinproj");

    expect(result.file_path).toBe("C:/tmp/demo.zpinproj");
    expect(result.board_id).toBe("rpi_pico");
  });
});