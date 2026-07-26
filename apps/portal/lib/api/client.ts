import { atlasApiPath } from "./config";
import { AtlasApiError, AtlasApiNetworkError } from "./errors";
import type { AtlasErrorResponse } from "./contracts";

export interface AtlasApiRequestOptions extends Omit<RequestInit, "body" | "headers"> {
  readonly body?: unknown;
  readonly headers?: HeadersInit;
  readonly accessToken?: string;
}

function requestMethod(options: AtlasApiRequestOptions): string {
  return (options.method ?? "GET").toUpperCase();
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

export async function atlasApiRequest<T>(
  path: string,
  options: AtlasApiRequestOptions = {}
): Promise<T> {
  const requestPath = atlasApiPath(path);
  const method = requestMethod(options);
  const headers = new Headers(options.headers);

  headers.set("Accept", "application/json");

  if (options.body !== undefined) {
    headers.set("Content-Type", "application/json");
  }

  if (options.accessToken) {
    headers.set("Authorization", `Bearer ${options.accessToken}`);
  }

  let response: Response;

  try {
    response = await fetch(requestPath, {
      ...options,
      method,
      headers,
      body: options.body === undefined ? undefined : JSON.stringify(options.body)
    });
  } catch (cause: unknown) {
    throw new AtlasApiNetworkError({
      method,
      path: requestPath,
      cause
    });
  }

  if (!response.ok) {
    throw new AtlasApiError({
      status: response.status,
      detail: await readErrorDetail(response),
      method,
      path: requestPath
    });
  }

  if (response.status === 204) {
    return undefined as T;
  }

  return (await response.json()) as T;
}
