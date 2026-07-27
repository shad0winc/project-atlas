import type {
  AtlasDashboardMediaLibraryResponse,
  AtlasDashboardMediaSummaryResponse
} from "../api/contracts";

import {
  createDashboardMediaSnapshot,
  type DashboardMediaLibrary,
  type DashboardMediaSnapshot
} from "../../features/dashboard/types/dashboard-media";

import { authenticatedAtlasApiRequest } from "./authenticated";

export type ReadDashboardMediaSummaryOptions = Readonly<{
  signal?: AbortSignal;
}>;

function mapDashboardMediaLibrary(
  library: AtlasDashboardMediaLibraryResponse
): DashboardMediaLibrary {
  return {
    id: library.id,
    label: library.label,
    status: library.status,
    ...(library.count === null
      ? {}
      : {
          count: library.count
        }),
    ...(library.detail === null
      ? {}
      : {
          detail: library.detail
        })
  };
}

function mapDashboardMediaSummary(
  summary: AtlasDashboardMediaSummaryResponse
): DashboardMediaSnapshot {
  return createDashboardMediaSnapshot({
    generatedAt: summary.generated_at,
    libraries: summary.libraries.map(mapDashboardMediaLibrary)
  });
}

export async function readDashboardMediaSummary({
  signal
}: ReadDashboardMediaSummaryOptions = {}): Promise<DashboardMediaSnapshot> {
  const summary = await authenticatedAtlasApiRequest<AtlasDashboardMediaSummaryResponse>(
    "/dashboard/media",
    {
      method: "GET",
      cache: "no-store",
      signal
    }
  );

  return mapDashboardMediaSummary(summary);
}
