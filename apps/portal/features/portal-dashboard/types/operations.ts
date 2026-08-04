import type {
  AtlasPortalOperationsAttentionResponse,
  AtlasPortalOperationsComparisonResponse,
  AtlasPortalOperationsSummaryResponse
} from "../../../lib/api/contracts";


export type PortalOperationsStatus =
  | "healthy"
  | "warning"
  | "critical"
  | "unknown";


export type PortalOperationsAttention = Readonly<{
  section: string;
  identifier: string;
  name: string;
  status: PortalOperationsStatus;
  severity: "critical" | "warning" | "info";
  message: string;
  recommendation: string | null;
}>;


export type PortalOperationsComparison = Readonly<{
  status: "available" | "unavailable";
  scoreDelta: number | null;
  attentionDelta: number | null;
  addedCount: number | null;
  removedCount: number | null;
  changedCount: number | null;
  unchangedCount: number | null;
  differenceCount: number | null;
  detail: string | null;
}>;


export type PortalOperationsSnapshot = Readonly<{
  status: "available" | "unavailable";
  detail: string | null;
  summary: Readonly<{
    status: PortalOperationsStatus;
    score: number;
    attentionCount: number;
    generatedAt: string;
  }> | null;
  comparison: PortalOperationsComparison;
  recentAttention: readonly PortalOperationsAttention[];
}>;


function normalizeTimestamp(
  value: string
): string {
  const timestamp = new Date(value);

  if (Number.isNaN(timestamp.getTime())) {
    throw new Error(
      "Operations timestamp must be valid."
    );
  }

  return timestamp.toISOString();
}


function mapAttention(
  value: AtlasPortalOperationsAttentionResponse
): PortalOperationsAttention {
  return {
    section: value.section,
    identifier: value.identifier,
    name: value.name,
    status: value.status,
    severity: value.severity,
    message: value.message,
    recommendation: value.recommendation
  };
}


function mapComparison(
  value: AtlasPortalOperationsComparisonResponse
): PortalOperationsComparison {
  return {
    status: value.status,
    scoreDelta: value.score_delta,
    attentionDelta: value.attention_delta,
    addedCount: value.added_count,
    removedCount: value.removed_count,
    changedCount: value.changed_count,
    unchangedCount: value.unchanged_count,
    differenceCount: value.difference_count,
    detail: value.detail
  };
}


export function createPortalOperationsSnapshot(
  value: AtlasPortalOperationsSummaryResponse
): PortalOperationsSnapshot {

  return {
    status: value.status,
    detail: value.detail,

    summary: value.summary
      ? {
          status: value.summary.status,
          score: value.summary.score,
          attentionCount: value.summary.attention_count,
          generatedAt: normalizeTimestamp(
            value.summary.generated_at
          )
        }
      : null,

    comparison: mapComparison(
      value.comparison
    ),

    recentAttention:
      value.recent_attention.map(
        mapAttention
      )
  };
}
