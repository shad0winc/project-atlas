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
    cache: "no-store"
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
