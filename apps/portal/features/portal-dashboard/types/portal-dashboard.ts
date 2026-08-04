import type { PortalOperationsSnapshot } from "./operations";
import type { PortalSchedulerSnapshot } from "./scheduler";
import type { DashboardMediaSnapshot } from "../../dashboard/types/dashboard-media";
import type { DashboardSnapshot } from "../../dashboard/types/dashboard";

export type PortalDashboardSnapshot = Readonly<{
  generatedAt: string;
  health: Readonly<{
    status: string;
    service: string;
    apiVersion: string;
  }>;
  operational: DashboardSnapshot;
  media: DashboardMediaSnapshot;
  operations: PortalOperationsSnapshot;
  scheduler: PortalSchedulerSnapshot;
}>;

export function createPortalDashboardSnapshot(
  value: PortalDashboardSnapshot
): PortalDashboardSnapshot {
  const timestamp = new Date(value.generatedAt);

  if (Number.isNaN(timestamp.getTime())) {
    throw new Error("generatedAt must be a valid timestamp.");
  }

  return {
    ...value,
    generatedAt: timestamp.toISOString()
  };
}
