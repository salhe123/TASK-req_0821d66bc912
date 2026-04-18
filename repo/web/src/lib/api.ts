export interface ApiErrorEnvelope {
  error: string;
  message: string;
  details: Record<string, unknown>;
}

export type ApiResult<T> =
  | { ok: true; status: number; data: T }
  | { ok: false; status: number; error: string; message: string; details: Record<string, unknown> };

interface RequestOptions {
  headers?: Record<string, string>;
  signal?: AbortSignal;
}

type CsrfProvider = () => string | null;
let csrfProvider: CsrfProvider = () => null;
export function setCsrfTokenProvider(fn: CsrfProvider): void {
  csrfProvider = fn;
}

type UnauthorizedHandler = () => void;
let unauthorizedHandler: UnauthorizedHandler | null = null;
export function setUnauthorizedHandler(fn: UnauthorizedHandler | null): void {
  unauthorizedHandler = fn;
}

const MUTATING = new Set(["POST", "PUT", "PATCH", "DELETE"]);

async function request<T>(
  method: "GET" | "POST" | "PUT" | "PATCH" | "DELETE",
  path: string,
  body?: unknown,
  opts: RequestOptions = {},
): Promise<ApiResult<T>> {
  const headers: Record<string, string> = {
    Accept: "application/json",
    ...(opts.headers ?? {}),
  };
  if (MUTATING.has(method)) {
    const csrf = csrfProvider();
    if (csrf) headers["X-CSRF-Token"] = csrf;
  }
  let serializedBody: string | undefined;
  if (body !== undefined) {
    headers["Content-Type"] = "application/json";
    serializedBody = JSON.stringify(body);
  }

  let response: Response;
  try {
    response = await fetch(path, {
      method,
      headers,
      body: serializedBody,
      credentials: "same-origin",
      signal: opts.signal,
    });
  } catch (err) {
    return {
      ok: false,
      status: 0,
      error: "network_error",
      message: err instanceof Error ? err.message : "network error",
      details: {},
    };
  }

  const text = await response.text();
  const parsed: unknown = text ? safeParse(text) : undefined;

  if (response.status === 401 && unauthorizedHandler) {
    unauthorizedHandler();
  }

  if (!response.ok) {
    const env = isEnvelope(parsed)
      ? parsed
      : { error: "http_error", message: response.statusText, details: {} };
    return {
      ok: false,
      status: response.status,
      error: env.error,
      message: env.message,
      details: env.details,
    };
  }

  return { ok: true, status: response.status, data: parsed as T };
}

function safeParse(text: string): unknown {
  try {
    return JSON.parse(text);
  } catch {
    return undefined;
  }
}

function isEnvelope(value: unknown): value is ApiErrorEnvelope {
  return (
    typeof value === "object" &&
    value !== null &&
    typeof (value as ApiErrorEnvelope).error === "string" &&
    typeof (value as ApiErrorEnvelope).message === "string"
  );
}

export const apiGet = <T>(path: string, opts?: RequestOptions) => request<T>("GET", path, undefined, opts);
export const apiPost = <T>(path: string, body?: unknown, opts?: RequestOptions) => request<T>("POST", path, body, opts);
export const apiPut = <T>(path: string, body?: unknown, opts?: RequestOptions) => request<T>("PUT", path, body, opts);
export const apiPatch = <T>(path: string, body?: unknown, opts?: RequestOptions) => request<T>("PATCH", path, body, opts);
export const apiDelete = <T>(path: string, opts?: RequestOptions) => request<T>("DELETE", path, undefined, opts);
