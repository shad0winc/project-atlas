import type {
  AtlasPortalDashboardData,
  AtlasPortalDashboardResponse
} from "../api/contracts";

import { authenticatedAtlasApiRequest } from "./authenticated";

export type ReadPortalDashboardOptions = Readonly<{
  signal?: AbortSignal;
}>;

export async function readPortalDashboard({
  signal
}: ReadPortalDashboardOptions = {}): Promise<AtlasPortalDashboardData> {
  const response =
    await authenticatedAtlasApiRequest<AtlasPortalDashboardResponse>(
      "/portal/dashboard",
      {
        method: "GET",
        cache: "no-store",
        signal
      }
    );

  if (response.success !== true) {
    throw new Error(
      "Portal dashboard API returned an unsuccessful response."
    );
  }

  if (
    response.data === null ||
    typeof response.data !== "object" ||
    response.data.dashboard === null ||
    typeof response.data.dashboard !== "object"
  ) {
    throw new Error(
      "Portal dashboard API response is missing dashboard data."
    );
  }

  return response.data;
}
