/**
 * Defines deterministic Atlas API retry policy.
 *
 * The transport executes one HTTP attempt. The public client may use this
 * policy to decide whether and when another attempt should be made.
 */

import { AtlasApiError, AtlasApiNetworkError } from "./errors";

export interface AtlasApiRetryPolicy {
  readonly maxRetries: number;
  readonly baseDelayMs: number;
  readonly maxDelayMs: number;
}

export interface AtlasApiRetryPolicyOptions {
  readonly maxRetries?: number;
  readonly baseDelayMs?: number;
  readonly maxDelayMs?: number;
}

export interface AtlasApiRetryDecision {
  readonly error: unknown;
  readonly retryCount: number;
  readonly policy?: AtlasApiRetryPolicy;
}

export const ATLAS_API_DEFAULT_RETRY_POLICY: AtlasApiRetryPolicy = Object.freeze({
  maxRetries: 0,
  baseDelayMs: 250,
  maxDelayMs: 5_000
});

function normalizeNonNegativeInteger(value: number, name: string): number {
  if (!Number.isFinite(value) || !Number.isInteger(value) || value < 0) {
    throw new Error(`${name} must be a non-negative integer.`);
  }

  return value;
}

export function createAtlasApiRetryPolicy(
  options: AtlasApiRetryPolicyOptions = {}
): AtlasApiRetryPolicy {
  const maxRetries = normalizeNonNegativeInteger(
    options.maxRetries ?? ATLAS_API_DEFAULT_RETRY_POLICY.maxRetries,
    "Atlas API maximum retries"
  );
  const baseDelayMs = normalizeNonNegativeInteger(
    options.baseDelayMs ?? ATLAS_API_DEFAULT_RETRY_POLICY.baseDelayMs,
    "Atlas API retry base delay"
  );
  const maxDelayMs = normalizeNonNegativeInteger(
    options.maxDelayMs ?? ATLAS_API_DEFAULT_RETRY_POLICY.maxDelayMs,
    "Atlas API retry maximum delay"
  );

  if (maxDelayMs < baseDelayMs) {
    throw new Error("Atlas API retry maximum delay cannot be less than the base delay.");
  }

  return Object.freeze({
    maxRetries,
    baseDelayMs,
    maxDelayMs
  });
}

export function isRetryableAtlasApiError(error: unknown): boolean {
  if (error instanceof AtlasApiNetworkError) {
    return true;
  }

  return (
    error instanceof AtlasApiError && (error.kind === "rate-limit" || error.kind === "unavailable")
  );
}

export function shouldRetryAtlasApiRequest({
  error,
  retryCount,
  policy = ATLAS_API_DEFAULT_RETRY_POLICY
}: AtlasApiRetryDecision): boolean {
  const normalizedRetryCount = normalizeNonNegativeInteger(retryCount, "Atlas API retry count");

  if (normalizedRetryCount >= policy.maxRetries) {
    return false;
  }

  return isRetryableAtlasApiError(error);
}

export function atlasApiRetryDelayMs(
  retryCount: number,
  policy: AtlasApiRetryPolicy = ATLAS_API_DEFAULT_RETRY_POLICY
): number {
  const normalizedRetryCount = normalizeNonNegativeInteger(retryCount, "Atlas API retry count");
  const exponentialDelay = policy.baseDelayMs * 2 ** normalizedRetryCount;

  return Math.min(exponentialDelay, policy.maxDelayMs);
}
