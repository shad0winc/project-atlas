import { atlasApiRequest } from "../api/client";
import type {
  AtlasDashboardMediaLibraryResponse,
  AtlasDashboardMediaSummaryResponse
} from "../api/contracts";

import {
  createDashboardMediaSnapshot,
  type DashboardMediaLibrary,
  type DashboardMediaSnapshot
} from "../../features/dashboard/types/dashboard-media";

export type ReadDashboardMediaSummaryOptions = Readonly<{
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
  accessToken,
  signal
}: ReadDashboardMediaSummaryOptions): Promise<DashboardMediaSnapshot> {
  const summary = await atlasApiRequest<AtlasDashboardMediaSummaryResponse>("/dashboard/media", {
    method: "GET",
    accessToken: normalizeAccessToken(accessToken),
    cache: "no-store",
    signal
  });

  return mapDashboardMediaSummary(summary);
}
