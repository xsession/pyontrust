import { ApiRequestError } from "../shared/errors/apiError";

function describeRequestTarget(input: RequestInfo | URL): string {
  if (typeof input === "string") {
    return input;
  }

  if (input instanceof URL) {
    return input.toString();
  }

  if (input instanceof Request) {
    return input.url;
  }

  return "unknown-request";
}

export async function fetchJson<T>(input: RequestInfo | URL, init?: RequestInit): Promise<T> {
  const response = await fetch(input, init);

  if (!response.ok) {
    let detail = "";

    try {
      detail = (await response.text()).trim();
    } catch {
      detail = "";
    }

    throw new ApiRequestError({
      status: response.status,
      statusText: response.statusText,
      url: describeRequestTarget(input),
      detail,
    });
  }

  return response.json() as Promise<T>;
}