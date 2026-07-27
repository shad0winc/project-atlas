/**
 * Public Atlas Portal API client.
 *
 * A single HTTP attempt is implemented by request.ts. This module orchestrates
 * repeated attempts according to the configured retry policy.
 */

import {
  ATLAS_API_DEFAULT_RETRY_POLICY,
  atlasApiRetryDelayMs,
  createAtlasApiRetryPolicy,
  shouldRetryAtlasApiRequest,
  type AtlasApiRetryPolicy
} from "./policy";
import {
  performAtlasApiRequest,
  type AtlasApiRequestOptions as AtlasApiTransportRequestOptions
} from "./request";

export interface AtlasApiRequestOptions extends AtlasApiTransportRequestOptions {
  readonly retryPolicy?: AtlasApiRetryPolicy;
}

function waitForAtlasApiRetry(delayMs: number): Promise<void> {
  return new Promise((resolve) => {
    globalThis.setTimeout(resolve, delayMs);
  });
}

export async function atlasApiRequest<T>(
  path: string,
  options: AtlasApiRequestOptions = {}
): Promise<T> {
  const { retryPolicy: requestedRetryPolicy, ...transportOptions } = options;

  const retryPolicy =
    requestedRetryPolicy === undefined
      ? ATLAS_API_DEFAULT_RETRY_POLICY
      : createAtlasApiRetryPolicy(requestedRetryPolicy);

  let retryCount = 0;

  while (true) {
    try {
      return await performAtlasApiRequest<T>(path, transportOptions);
    } catch (error: unknown) {
      if (
        !shouldRetryAtlasApiRequest({
          error,
          retryCount,
          policy: retryPolicy
        })
      ) {
        throw error;
      }

      const delayMs = atlasApiRetryDelayMs(retryCount, retryPolicy);

      await waitForAtlasApiRetry(delayMs);
      retryCount += 1;
    }
  }
}
