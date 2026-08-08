import type { AtlasDashboardMetricResponse, AtlasDashboardSummaryResponse } from "../api/contracts";

import {
  createDashboardSnapshot,
  type DashboardMetric,
  type DashboardSnapshot
} from "../../features/dashboard/types/dashboard";

import { authenticatedAtlasApiRequest } from "./authenticated";

export type ReadDashboardSummaryOptions = Readonly<{
  signal?: AbortSignal;
}>;

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
  signal
}: ReadDashboardSummaryOptions = {}): Promise<DashboardSnapshot> {
  const summary = await authenticatedAtlasApiRequest<AtlasDashboardSummaryResponse>(
    "/dashboard/summary",
    {
      method: "GET",
      cache: "no-store",
      signal
    }
  );

  return mapDashboardSummary(summary);
}
