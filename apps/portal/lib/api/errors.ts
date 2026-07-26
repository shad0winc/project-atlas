/**
 * Normalized failures returned by the Atlas Portal API client.
 */

export class AtlasApiError extends Error {
  readonly status: number;
  readonly detail: string;
  readonly method: string;
  readonly path: string;

  constructor({
    status,
    detail,
    method,
    path
  }: Readonly<{
    status: number;
    detail: string;
    method: string;
    path: string;
  }>) {
    super(detail);

    this.name = "AtlasApiError";
    this.status = status;
    this.detail = detail;
    this.method = method;
    this.path = path;
  }
}

export class AtlasApiNetworkError extends Error {
  readonly method: string;
  readonly path: string;
  readonly cause?: unknown;

  constructor({
    method,
    path,
    cause
  }: Readonly<{
    method: string;
    path: string;
    cause?: unknown;
  }>) {
    super(`Unable to reach the Atlas API for ${method} ${path}.`);

    this.name = "AtlasApiNetworkError";
    this.method = method;
    this.path = path;
    this.cause = cause;
  }
}
