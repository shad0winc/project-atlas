/**
 * Shared authenticated request boundary for protected Atlas services.
 *
 * Feature hooks and components must not retrieve or pass access tokens.
 * Authentication lifecycle endpoints remain explicit because they create or
 * rotate the session itself.
 */

import {
  atlasApiRequest,
  atlasApiRequestWithMetadata,
  type AtlasApiRequestOptions
} from "../api/client";
import type {
  AtlasApiResponseWithMetadata
} from "../api/request";
import { readAtlasAuthSession } from "../auth/storage";

export type AuthenticatedAtlasApiRequestOptions = Omit<
  AtlasApiRequestOptions,
  "accessToken" | "retryAuthentication"
>;

function readAuthenticatedAccessToken(): string {
  const accessToken = readAtlasAuthSession()?.tokens.accessToken.trim();

  if (!accessToken) {
    throw new Error("Atlas authentication session is unavailable.");
  }

  return accessToken;
}

export async function authenticatedAtlasApiRequest<T>(
  path: string,
  options: AuthenticatedAtlasApiRequestOptions = {}
): Promise<T> {
  return atlasApiRequest<T>(path, {
    ...options,
    accessToken: readAuthenticatedAccessToken()
  });
}


export async function authenticatedAtlasApiRequestWithMetadata<T>(
  path: string,
  options: AuthenticatedAtlasApiRequestOptions = {}
): Promise<AtlasApiResponseWithMetadata<T>> {
  return atlasApiRequestWithMetadata<T>(path, {
    ...options,
    accessToken: readAuthenticatedAccessToken()
  });
}
