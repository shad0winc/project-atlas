import { atlasApiRequest } from "../api/client";
import type { AtlasDashboardMetricResponse, AtlasDashboardSummaryResponse } from "../api/contracts";

import {
  createDashboardSnapshot,
  type DashboardMetric,
  type DashboardSnapshot
} from "../../features/dashboard/types/dashboard";

export type ReadDashboardSummaryOptions = Readonly<{
  accessToken: string;
  signal?: AbortSignal;
}>;

function normalizeAccessToken(accessToken: string): string {
  const normalizedToken = accessToken.trim();

  if (!normalizedToken) {
    throw new Error("Atlas access token cannot be empty.");
  }

  return normalizedToken;
}

function mapDashboardMetric(metric: AtlasDashboardMetricResponse): DashboardMetric {
  return {
    id: metric.id,
    label: metric.label,
    value: metric.value,
    description: metric.description,
    status: metric.status,
    ...(metric.detail === null
      ? {}
      : {
          detail: metric.detail
        })
  };
}

function mapDashboardSummary(summary: AtlasDashboardSummaryResponse): DashboardSnapshot {
  return createDashboardSnapshot({
    generatedAt: summary.generated_at,
    metrics: summary.metrics.map(mapDashboardMetric)
  });
}

export async function readDashboardSummary({
  accessToken,
  signal
}: ReadDashboardSummaryOptions): Promise<DashboardSnapshot> {
  const summary = await atlasApiRequest<AtlasDashboardSummaryResponse>("/dashboard/summary", {
    method: "GET",
    accessToken: normalizeAccessToken(accessToken),
    cache: "no-store",
    signal
  });

  return mapDashboardSummary(summary);
}
