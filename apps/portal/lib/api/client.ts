import { ATLAS_API_DEFAULT_TIMEOUT_MS, atlasApiPath } from "./config";
import {
  AtlasApiAbortError,
  AtlasApiError,
  AtlasApiNetworkError,
  AtlasApiResponseError,
  AtlasApiTimeoutError,
  type AtlasApiHttpErrorKind
} from "./errors";
import type { AtlasErrorResponse } from "./contracts";

export interface AtlasApiRequestOptions extends Omit<RequestInit, "body" | "headers" | "signal"> {
  readonly body?: unknown;
  readonly headers?: HeadersInit;
  readonly accessToken?: string;
  readonly requestId?: string;
  readonly signal?: AbortSignal;
  readonly timeoutMs?: number;
}

type RequestSignalLifecycle = Readonly<{
  signal: AbortSignal;
  didTimeout: () => boolean;
  cleanup: () => void;
}>;

function requestMethod(options: AtlasApiRequestOptions): string {
  return (options.method ?? "GET").toUpperCase();
}

function normalizeTimeoutMs(timeoutMs: number | undefined): number {
  const value = timeoutMs ?? ATLAS_API_DEFAULT_TIMEOUT_MS;

  if (!Number.isFinite(value) || !Number.isInteger(value) || value <= 0) {
    throw new Error("Atlas API timeout must be a positive integer.");
  }

  return value;
}

function createRequestId(): string {
  if (typeof globalThis.crypto?.randomUUID === "function") {
    return globalThis.crypto.randomUUID();
  }

  return [
    Date.now().toString(36),
    Math.random().toString(36).slice(2),
    Math.random().toString(36).slice(2)
  ].join("-");
}

function resolveRequestId(headers: Headers, requestId: string | undefined): string {
  if (requestId !== undefined) {
    const normalizedRequestId = requestId.trim();

    if (!normalizedRequestId) {
      throw new Error("Atlas API request ID cannot be empty.");
    }

    return normalizedRequestId;
  }

  const headerRequestId = headers.get("X-Request-ID")?.trim();

  if (headerRequestId) {
    return headerRequestId;
  }

  return createRequestId();
}

function normalizeAccessToken(accessToken: string | undefined): string | undefined {
  if (accessToken === undefined) {
    return undefined;
  }

  const normalizedToken = accessToken.trim();

  if (!normalizedToken) {
    throw new Error("Atlas access token cannot be empty.");
  }

  return normalizedToken;
}

function createRequestSignal(
  externalSignal: AbortSignal | undefined,
  timeoutMs: number
): RequestSignalLifecycle {
  const controller = new AbortController();
  let timedOut = false;

  const forwardExternalAbort = (): void => {
    controller.abort(externalSignal?.reason);
  };

  if (externalSignal?.aborted) {
    forwardExternalAbort();
  } else {
    externalSignal?.addEventListener("abort", forwardExternalAbort, {
      once: true
    });
  }

  const timeoutId = globalThis.setTimeout(() => {
    timedOut = true;
    controller.abort();
  }, timeoutMs);

  return {
    signal: controller.signal,
    didTimeout: () => timedOut,
    cleanup: () => {
      globalThis.clearTimeout(timeoutId);
      externalSignal?.removeEventListener("abort", forwardExternalAbort);
    }
  };
}

function classifyHttpError(status: number): AtlasApiHttpErrorKind {
  if (status === 401) {
    return "authentication";
  }

  if (status === 403) {
    return "authorization";
  }

  if (status === 400 || status === 422) {
    return "validation";
  }

  if (status === 409) {
    return "conflict";
  }

  if (status === 429) {
    return "rate-limit";
  }

  if (status === 502 || status === 503 || status === 504) {
    return "unavailable";
  }

  return "http";
}

async function readErrorDetail(response: Response): Promise<string> {
  try {
    const payload = (await response.json()) as AtlasErrorResponse;

    if (typeof payload.detail === "string" && payload.detail.trim()) {
      return payload.detail.trim();
    }
  } catch {
    // The API may return an empty or non-JSON response for infrastructure
    // failures. Fall through to the status-based message.
  }

  return `Atlas API request failed with status ${response.status}.`;
}

async function readSuccessResponse<T>({
  response,
  method,
  path,
  requestId
}: Readonly<{
  response: Response;
  method: string;
  path: string;
  requestId: string;
}>): Promise<T> {
  if (response.status === 204) {
    return undefined as T;
  }

  try {
    return (await response.json()) as T;
  } catch (cause: unknown) {
    throw new AtlasApiResponseError({
      status: response.status,
      contentType: response.headers.get("Content-Type"),
      method,
      path,
      requestId,
      cause
    });
  }
}

export async function atlasApiRequest<T>(
  path: string,
  options: AtlasApiRequestOptions = {}
): Promise<T> {
  const requestPath = atlasApiPath(path);
  const method = requestMethod(options);
  const timeoutMs = normalizeTimeoutMs(options.timeoutMs);
  const headers = new Headers(options.headers);
  const requestId = resolveRequestId(headers, options.requestId);
  const accessToken = normalizeAccessToken(options.accessToken);

  const body = options.body;
  const externalSignal = options.signal;
  const requestInit: RequestInit = {
    cache: options.cache,
    credentials: options.credentials,
    integrity: options.integrity,
    keepalive: options.keepalive,
    method: options.method,
    mode: options.mode,
    priority: options.priority,
    redirect: options.redirect,
    referrer: options.referrer,
    referrerPolicy: options.referrerPolicy
  };

  headers.set("Accept", "application/json");
  headers.set("X-Request-ID", requestId);

  if (body !== undefined) {
    headers.set("Content-Type", "application/json");
  }

  if (accessToken !== undefined) {
    headers.set("Authorization", `Bearer ${accessToken}`);
  }

  const requestSignal = createRequestSignal(externalSignal, timeoutMs);

  let response: Response;

  try {
    response = await fetch(requestPath, {
      ...requestInit,
      method,
      headers,
      body: body === undefined ? undefined : JSON.stringify(body),
      signal: requestSignal.signal
    });
  } catch (cause: unknown) {
    if (requestSignal.didTimeout()) {
      throw new AtlasApiTimeoutError({
        method,
        path: requestPath,
        requestId,
        timeoutMs,
        cause
      });
    }

    if (externalSignal?.aborted) {
      throw new AtlasApiAbortError({
        method,
        path: requestPath,
        requestId,
        cause
      });
    }

    throw new AtlasApiNetworkError({
      method,
      path: requestPath,
      requestId,
      cause
    });
  } finally {
    requestSignal.cleanup();
  }

  const responseRequestId = response.headers.get("X-Request-ID")?.trim() || requestId;

  if (!response.ok) {
    throw new AtlasApiError({
      status: response.status,
      detail: await readErrorDetail(response),
      method,
      path: requestPath,
      requestId: responseRequestId,
      kind: classifyHttpError(response.status)
    });
  }

  return readSuccessResponse<T>({
    response,
    method,
    path: requestPath,
    requestId: responseRequestId
  });
}
