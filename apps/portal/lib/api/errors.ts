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

export interface AtlasApiErrorOptions {
  readonly status: number;
  readonly detail: string;
  readonly method: string;
  readonly path: string;
  readonly requestId: string;
  readonly kind: AtlasApiHttpErrorKind;
}

type AtlasApiAuthorizationErrorOptions = Readonly<Omit<AtlasApiErrorOptions, "status" | "kind">>;

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

  constructor({ status, detail, method, path, requestId, kind }: AtlasApiErrorOptions) {
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

/**
 * A request was rejected because its access token was missing, invalid,
 * expired, or no longer represents an active Atlas user.
 */
export class AtlasApiAuthenticationError extends AtlasApiError {
  constructor(options: AtlasApiAuthorizationErrorOptions) {
    super({
      ...options,
      status: 401,
      kind: "authentication"
    });
  }
}

/**
 * The authenticated user is valid but does not have the required permission.
 */
export class AtlasApiAuthorizationError extends AtlasApiError {
  constructor(options: AtlasApiAuthorizationErrorOptions) {
    super({
      ...options,
      status: 403,
      kind: "authorization"
    });
  }
}

/**
 * Atlas could not restore an authenticated request through token rotation.
 */
export class AtlasAuthenticationExpiredError extends AtlasApiClientError {
  readonly status = 401;

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
      name: "AtlasAuthenticationExpiredError",
      message: "Your Atlas session has expired. Sign in again to continue.",
      method,
      path,
      requestId,
      cause
    });
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
