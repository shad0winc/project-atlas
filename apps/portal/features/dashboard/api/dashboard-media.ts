import { readDashboardMediaSummary } from "../../../lib/services/dashboard-media";

import type { DashboardMediaSnapshot } from "../types/dashboard-media";

export type LoadDashboardMediaOptions = Readonly<{
  signal?: AbortSignal;
}>;

export async function loadDashboardMedia({
  signal
}: LoadDashboardMediaOptions = {}): Promise<DashboardMediaSnapshot> {
  return readDashboardMediaSummary({
    signal
  });
}
