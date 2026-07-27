/**
 * Normalized failures returned by the Atlas Portal API client.
 */

export type AtlasApiHttpErrorKind =
  | "authentication"
  | "authorization"
  | "validation"
  | "conflict"
  | "rate-limit"
  | "unavailable"
  | "http";

export abstract class AtlasApiClientError extends Error {
  readonly method: string;
  readonly path: string;
  readonly requestId: string;

  protected constructor({
    name,
    message,
    method,
    path,
    requestId,
    cause
  }: Readonly<{
    name: string;
    message: string;
    method: string;
    path: string;
    requestId: string;
    cause?: unknown;
  }>) {
    super(message, {
      cause
    });

    this.name = name;
    this.method = method;
    this.path = path;
    this.requestId = requestId;
  }
}

export class AtlasApiError extends AtlasApiClientError {
  readonly status: number;
  readonly detail: string;
  readonly kind: AtlasApiHttpErrorKind;

  constructor({
    status,
    detail,
    method,
    path,
    requestId,
    kind
  }: Readonly<{
    status: number;
    detail: string;
    method: string;
    path: string;
    requestId: string;
    kind: AtlasApiHttpErrorKind;
  }>) {
    super({
      name: "AtlasApiError",
      message: detail,
      method,
      path,
      requestId
    });

    this.status = status;
    this.detail = detail;
    this.kind = kind;
  }
}

export class AtlasApiNetworkError extends AtlasApiClientError {
  constructor({
    method,
    path,
    requestId,
    cause
  }: Readonly<{
    method: string;
    path: string;
    requestId: string;
    cause?: unknown;
  }>) {
    super({
      name: "AtlasApiNetworkError",
      message: `Unable to reach the Atlas API for ${method} ${path}.`,
      method,
      path,
      requestId,
      cause
    });
  }
}

export class AtlasApiTimeoutError extends AtlasApiClientError {
  readonly timeoutMs: number;

  constructor({
    method,
    path,
    requestId,
    timeoutMs,
    cause
  }: Readonly<{
    method: string;
    path: string;
    requestId: string;
    timeoutMs: number;
    cause?: unknown;
  }>) {
    super({
      name: "AtlasApiTimeoutError",
      message: `Atlas API request timed out after ${timeoutMs} ms for ${method} ${path}.`,
      method,
      path,
      requestId,
      cause
    });

    this.timeoutMs = timeoutMs;
  }
}

export class AtlasApiAbortError extends AtlasApiClientError {
  constructor({
    method,
    path,
    requestId,
    cause
  }: Readonly<{
    method: string;
    path: string;
    requestId: string;
    cause?: unknown;
  }>) {
    super({
      name: "AtlasApiAbortError",
      message: `Atlas API request was cancelled for ${method} ${path}.`,
      method,
      path,
      requestId,
      cause
    });
  }
}

export class AtlasApiResponseError extends AtlasApiClientError {
  readonly status: number;
  readonly contentType: string | null;

  constructor({
    status,
    contentType,
    method,
    path,
    requestId,
    cause
  }: Readonly<{
    status: number;
    contentType: string | null;
    method: string;
    path: string;
    requestId: string;
    cause?: unknown;
  }>) {
    super({
      name: "AtlasApiResponseError",
      message: `Atlas API returned an invalid JSON response for ${method} ${path}.`,
      method,
      path,
      requestId,
      cause
    });

    this.status = status;
    this.contentType = contentType;
  }
}
