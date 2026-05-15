export class ApiRequestError extends Error {
  status: number;
  statusText: string;
  url: string;
  detail: string;

  constructor(options: { status: number; statusText: string; url: string; detail?: string }) {
    const detail = options.detail?.trim();
    const suffix = detail ? ` - ${detail}` : "";
    super(`Request failed: ${options.status} ${options.statusText}${suffix}`);
    this.name = "ApiRequestError";
    this.status = options.status;
    this.statusText = options.statusText;
    this.url = options.url;
    this.detail = detail ?? "";
  }
}

export function describeError(error: unknown, fallback: string): string {
  if (error instanceof Error && error.message.trim()) {
    return error.message;
  }

  return fallback;
}