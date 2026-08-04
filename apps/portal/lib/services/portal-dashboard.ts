import type {
  AtlasPortalDashboardResponse
} from "../api/contracts";

import {
  authenticatedAtlasApiRequest
} from "./authenticated";


export type ReadPortalDashboardOptions = Readonly<{
  signal?: AbortSignal;
}>;


export async function readPortalDashboard(
  {
    signal
  }: ReadPortalDashboardOptions = {}
): Promise<AtlasPortalDashboardResponse> {

  return authenticatedAtlasApiRequest<AtlasPortalDashboardResponse>(
    "/portal/dashboard",
    {
      method: "GET",
      cache: "no-store",
      signal
    }
  );
}
