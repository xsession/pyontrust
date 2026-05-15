export interface FrontendEnvironment {
  apiBasePath: string;
  appBasePath: string;
  mode: string;
}

type ImportMetaWithOptionalEnv = ImportMeta & {
  env?: Record<string, unknown>;
};

function coerceString(value: unknown, fallback: string): string {
  if (typeof value === "string") {
    return value;
  }

  if (typeof value === "number" || typeof value === "boolean" || typeof value === "bigint") {
    return String(value);
  }

  return fallback;
}

function normalizeBasePath(value: unknown, fallback: string): string {
  const trimmed = coerceString(value, fallback).trim();
  if (!trimmed) {
    return fallback;
  }

  const withLeadingSlash = trimmed.startsWith("/") ? trimmed : `/${trimmed}`;
  return withLeadingSlash.replace(/\/+$/, "") || fallback;
}

export function readFrontendEnvironment(
  metaEnv: Record<string, unknown> = (import.meta as ImportMetaWithOptionalEnv).env ?? {},
): FrontendEnvironment {
  return {
    apiBasePath: normalizeBasePath(metaEnv.VITE_API_BASE_PATH, "/api"),
    appBasePath: normalizeBasePath(metaEnv.BASE_URL, "/app"),
    mode: coerceString(metaEnv.MODE, "development"),
  };
}

export function buildApiUrl(path: string, environment: FrontendEnvironment = readFrontendEnvironment()): string {
  const normalizedPath = path.startsWith("/") ? path : `/${path}`;
  return `${environment.apiBasePath}${normalizedPath}`;
}