import type {
  AtlasCurrentUserResponse,
  AtlasLoginRequest,
  AtlasTokenResponse
} from "../api/contracts";

/**
 * Authentication lifecycle states exposed by the Atlas Portal.
 */
export type AtlasAuthStatus = "loading" | "authenticated" | "unauthenticated";

/**
 * Token pair issued by the Atlas API.
 */
export interface AtlasAuthTokens {
  readonly accessToken: string;
  readonly refreshToken: string;
  readonly tokenType: string;
}

/**
 * Active authenticated Portal session.
 */
export interface AtlasAuthSession {
  readonly tokens: AtlasAuthTokens;
  readonly user: AtlasCurrentUserResponse;
}

/**
 * Public authentication context consumed by Portal components.
 */
export interface AtlasAuthContextValue {
  readonly status: AtlasAuthStatus;
  readonly session: AtlasAuthSession | null;
  readonly user: AtlasCurrentUserResponse | null;
  readonly isAuthenticated: boolean;
  readonly login: (credentials: AtlasLoginRequest) => Promise<void>;
  readonly logout: () => Promise<void>;
}

/**
 * Normalize the API token response into the Portal session contract.
 */
export function normalizeAtlasAuthTokens(response: AtlasTokenResponse): AtlasAuthTokens {
  const accessToken = response.access_token.trim();
  const refreshToken = response.refresh_token.trim();
  const tokenType = response.token_type.trim();

  if (!accessToken) {
    throw new Error("Atlas access token cannot be empty.");
  }

  if (!refreshToken) {
    throw new Error("Atlas refresh token cannot be empty.");
  }

  if (!tokenType) {
    throw new Error("Atlas token type cannot be empty.");
  }

  return {
    accessToken,
    refreshToken,
    tokenType
  };
}
