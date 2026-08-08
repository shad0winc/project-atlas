import { atlasApiRequest } from "../api/client";
import type {
  AtlasCurrentUserResponse,
  AtlasLoginRequest,
  AtlasTokenResponse
} from "../api/contracts";

export async function loginAtlasUser(credentials: AtlasLoginRequest): Promise<AtlasTokenResponse> {
  return atlasApiRequest<AtlasTokenResponse>("/auth/login", {
    method: "POST",
    body: credentials,
    cache: "no-store",
    retryAuthentication: false
  });
}

export async function refreshAtlasTokens(refreshToken: string): Promise<AtlasTokenResponse> {
  const normalizedToken = refreshToken.trim();

  if (!normalizedToken) {
    throw new Error("Atlas refresh token cannot be empty.");
  }

  return atlasApiRequest<AtlasTokenResponse>("/auth/refresh", {
    method: "POST",
    body: {
      refresh_token: normalizedToken
    },
    cache: "no-store",
    retryAuthentication: false
  });
}

export async function logoutAtlasSession(refreshToken: string): Promise<void> {
  const normalizedToken = refreshToken.trim();

  if (!normalizedToken) {
    throw new Error("Atlas refresh token cannot be empty.");
  }

  await atlasApiRequest<void>("/auth/logout", {
    method: "POST",
    body: {
      refresh_token: normalizedToken
    },
    cache: "no-store",
    retryAuthentication: false
  });
}

export async function readCurrentAtlasUser(accessToken: string): Promise<AtlasCurrentUserResponse> {
  const normalizedToken = accessToken.trim();

  if (!normalizedToken) {
    throw new Error("Atlas access token cannot be empty.");
  }

  return atlasApiRequest<AtlasCurrentUserResponse>("/auth/me", {
    method: "GET",
    accessToken: normalizedToken,
    cache: "no-store"
  });
}
