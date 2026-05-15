import { ApiRequestError } from "../shared/errors/apiError";
import { fetchJson } from "./http";

describe("fetchJson", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("throws a typed API error with response detail", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response("backend exploded", {
        status: 500,
        statusText: "Internal Server Error",
      }),
    );

    await expect(fetchJson("/api/boards")).rejects.toEqual(
      expect.objectContaining<ApiRequestError>({
        name: "ApiRequestError",
        status: 500,
        statusText: "Internal Server Error",
        url: "/api/boards",
        detail: "backend exploded",
        message: "Request failed: 500 Internal Server Error - backend exploded",
      }),
    );
  });
});