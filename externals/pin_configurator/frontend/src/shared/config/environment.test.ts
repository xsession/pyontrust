import { buildApiUrl, readFrontendEnvironment } from "./environment";

describe("frontend environment", () => {
  it("provides stable defaults for app and api base paths", () => {
    expect(readFrontendEnvironment({ MODE: "test" })).toEqual({
      apiBasePath: "/api",
      appBasePath: "/app",
      mode: "test",
    });
  });

  it("builds api URLs from explicit environment config", () => {
    expect(
      buildApiUrl("/boards", {
        apiBasePath: "/proxy/api",
        appBasePath: "/app",
        mode: "development",
      }),
    ).toBe("/proxy/api/boards");
  });
});