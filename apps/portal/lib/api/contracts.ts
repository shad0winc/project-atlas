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

export type AtlasPortalOperationsStatus = "healthy" | "warning" | "critical" | "unknown";

export interface AtlasPortalOperationsReportSummaryResponse {
  readonly status: AtlasPortalOperationsStatus;
  readonly score: number;
  readonly attention_count: number;
  readonly generated_at: string;
}

export interface AtlasPortalOperationsComparisonResponse {
  readonly status: "available" | "unavailable";
  readonly score_delta: number | null;
  readonly attention_delta: number | null;
  readonly added_count: number | null;
  readonly removed_count: number | null;
  readonly changed_count: number | null;
  readonly unchanged_count: number | null;
  readonly difference_count: number | null;
  readonly detail: string | null;
}

export interface AtlasPortalOperationsAttentionResponse {
  readonly section: string;
  readonly identifier: string;
  readonly name: string;
  readonly status: AtlasPortalOperationsStatus;
  readonly severity: "critical" | "warning" | "info";
  readonly message: string;
  readonly recommendation: string | null;
}

export interface AtlasPortalOperationsSummaryResponse {
  readonly status: "available" | "unavailable";
  readonly report: Record<string, unknown> | null;
  readonly detail: string | null;
  readonly summary: AtlasPortalOperationsReportSummaryResponse | null;
  readonly comparison: AtlasPortalOperationsComparisonResponse;
  readonly recent_attention: readonly AtlasPortalOperationsAttentionResponse[];
}

export interface AtlasPortalSchedulerFailureResponse {
  readonly task_name: string;
  readonly failed_at: string | null;
  readonly error: string;
}

export interface AtlasPortalSchedulerSummaryResponse {
  readonly status: "available" | "unavailable";
  readonly detail: string | null;

  readonly registered_count: number | null;
  readonly enabled_count: number | null;
  readonly disabled_count: number | null;
  readonly due_count: number | null;
  readonly running_count: number | null;
  readonly failed_count: number | null;

  readonly last_run_at: string | null;
  readonly next_run_at: string | null;

  readonly recent_failures: readonly AtlasPortalSchedulerFailureResponse[];
}

export interface AtlasPortalDashboardData {
  readonly dashboard: {
    readonly health: AtlasHealthResponse;
    readonly operational: AtlasDashboardSummaryResponse;
    readonly media: AtlasDashboardMediaSummaryResponse;
    readonly operations: AtlasPortalOperationsSummaryResponse;
    readonly scheduler: AtlasPortalSchedulerSummaryResponse;
  };
}

export interface AtlasPortalDashboardResponse {
  readonly schema_version: number;
  readonly api_version: string;
  readonly success: boolean;
  readonly generated_at: string;
  readonly data: AtlasPortalDashboardData;
}

export interface AtlasErrorResponse {
  readonly detail?: string;
}
