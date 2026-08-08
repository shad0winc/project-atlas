/**
 * Public Atlas Portal API client.
 *
 * A single HTTP attempt is implemented by request.ts. This module orchestrates
 * token refresh and repeated attempts according to the configured retry policy.
 */

import {
  canRefreshAtlasAuthSession,
  expireAtlasAuthSession,
  refreshAtlasAuthAccessToken
} from "../auth/session-lifecycle";

import { AtlasApiAuthenticationError, AtlasAuthenticationExpiredError } from "./errors";
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

  /**
   * Permit one access-token refresh and one authenticated replay after a 401.
   *
   * Authentication endpoints may disable this explicitly.
   */
  readonly retryAuthentication?: boolean;
}

function waitForAtlasApiRetry(delayMs: number): Promise<void> {
  return new Promise((resolve) => {
    globalThis.setTimeout(resolve, delayMs);
  });
}

function canRetryAuthentication(
  error: unknown,
  options: AtlasApiTransportRequestOptions,
  retryAuthentication: boolean
): error is AtlasApiAuthenticationError {
  return (
    retryAuthentication &&
    options.accessToken !== undefined &&
    error instanceof AtlasApiAuthenticationError &&
    canRefreshAtlasAuthSession()
  );
}

function authenticationExpired(
  error: AtlasApiAuthenticationError,
  cause: unknown = error
): AtlasAuthenticationExpiredError {
  return new AtlasAuthenticationExpiredError({
    method: error.method,
    path: error.path,
    requestId: error.requestId,
    cause
  });
}

export async function atlasApiRequest<T>(
  path: string,
  options: AtlasApiRequestOptions = {}
): Promise<T> {
  const {
    retryPolicy: requestedRetryPolicy,
    retryAuthentication = true,
    ...requestedTransportOptions
  } = options;

  const retryPolicy =
    requestedRetryPolicy === undefined
      ? ATLAS_API_DEFAULT_RETRY_POLICY
      : createAtlasApiRetryPolicy(requestedRetryPolicy);

  let transportOptions = requestedTransportOptions;
  let retryCount = 0;
  let authenticationRetried = false;

  while (true) {
    try {
      return await performAtlasApiRequest<T>(path, transportOptions);
    } catch (error: unknown) {
      if (canRetryAuthentication(error, transportOptions, retryAuthentication)) {
        if (authenticationRetried) {
          expireAtlasAuthSession();
          throw authenticationExpired(error);
        }

        try {
          const replacementAccessToken = await refreshAtlasAuthAccessToken();

          transportOptions = {
            ...transportOptions,
            accessToken: replacementAccessToken
          };

          authenticationRetried = true;
          continue;
        } catch (refreshError: unknown) {
          throw authenticationExpired(error, refreshError);
        }
      }

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
