/**
 * Stable transport contracts consumed by the Atlas Portal.
 *
 * These interfaces mirror the public Atlas API rather than Atlas domain
 * models. Domain behavior and authorization remain owned by the API.
 */

export type AtlasHealthStatus = "ok";

export interface AtlasHealthResponse {
  readonly status: AtlasHealthStatus;
  readonly service: "atlas-api";
  readonly api_version: "v1";
}

export interface AtlasLoginRequest {
  readonly username: string;
  readonly password: string;
}

export interface AtlasTokenResponse {
  readonly access_token: string;
  readonly refresh_token: string;
  readonly token_type: string;
}

export interface AtlasCurrentUserResponse {
  readonly user_id: string;
  readonly username: string;
  readonly display_name: string;
  readonly roles: readonly string[];
  readonly provider: string;
}

export interface AtlasErrorResponse {
  readonly detail?: string;
}
