import {
  readPortalDashboard
} from "../../../lib/services/portal-dashboard";

import {
  createPortalDashboardSnapshot,
  type PortalDashboardSnapshot
} from "../types/portal-dashboard";


export type LoadPortalDashboardOptions = Readonly<{
  signal?: AbortSignal;
}>;


export async function loadPortalDashboard(
  {
    signal
  }: LoadPortalDashboardOptions = {}
): Promise<PortalDashboardSnapshot> {

  const response = await readPortalDashboard({
    signal
  });

  return createPortalDashboardSnapshot({
    generatedAt: response.dashboard.operational.generated_at,
    health: {
      status: response.dashboard.health.status,
      service: response.dashboard.health.service,
      apiVersion: response.dashboard.health.api_version
    },
    operational: response.dashboard.operational,
    media: response.dashboard.media,
    operations: response.dashboard.operations,
    scheduler: response.dashboard.scheduler
  });
}
