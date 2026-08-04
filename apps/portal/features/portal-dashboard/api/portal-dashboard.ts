import { readPortalDashboard } from "../../../lib/services/portal-dashboard";

import {
  createPortalDashboardSnapshot,
  type PortalDashboardSnapshot
} from "../types/portal-dashboard";

import { createDashboardMediaSnapshot } from "../../dashboard/types/dashboard-media";

import { createDashboardSnapshot } from "../../dashboard/types/dashboard";

import { createPortalOperationsSnapshot } from "../types/operations";

import { createPortalSchedulerSnapshot } from "../types/scheduler";

export type LoadPortalDashboardOptions = Readonly<{
  signal?: AbortSignal;
}>;

export async function loadPortalDashboard({
  signal
}: LoadPortalDashboardOptions = {}): Promise<PortalDashboardSnapshot> {
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
    operational: createDashboardSnapshot({
      generatedAt: response.dashboard.operational.generated_at,
      metrics: response.dashboard.operational.metrics.map((metric) => ({
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
      }))
    }),
    media: createDashboardMediaSnapshot({
      generatedAt: response.dashboard.media.generated_at,
      libraries: response.dashboard.media.libraries.map((library) => ({
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
      }))
    }),
    operations: createPortalOperationsSnapshot(response.dashboard.operations),

    scheduler: createPortalSchedulerSnapshot(response.dashboard.scheduler)
  });
}
