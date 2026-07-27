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
  readonly granted_permission_patterns: readonly string[];
  readonly denied_permission_patterns: readonly string[];
}

export type AtlasDashboardMetricStatus = "healthy" | "warning" | "offline" | "unknown";

export interface AtlasDashboardMetricResponse {
  readonly id: string;
  readonly label: string;
  readonly value: string;
  readonly description: string;
  readonly status: AtlasDashboardMetricStatus;
  readonly detail: string | null;
}

export interface AtlasDashboardSummaryResponse {
  readonly generated_at: string;
  readonly metrics: readonly AtlasDashboardMetricResponse[];
}

export type AtlasDashboardMediaLibraryStatus = "available" | "unavailable";

export interface AtlasDashboardMediaLibraryResponse {
  readonly id: string;
  readonly label: string;
  readonly count: number | null;
  readonly status: AtlasDashboardMediaLibraryStatus;
  readonly detail: string | null;
}

export interface AtlasDashboardMediaSummaryResponse {
  readonly generated_at: string;
  readonly libraries: readonly AtlasDashboardMediaLibraryResponse[];
}

export interface AtlasErrorResponse {
  readonly detail?: string;
}
