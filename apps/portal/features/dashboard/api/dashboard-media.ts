import { readDashboardMediaSummary } from "../../../lib/services/dashboard-media";

import type { DashboardMediaSnapshot } from "../types/dashboard-media";

export type LoadDashboardMediaOptions = Readonly<{
  accessToken: string;
  signal?: AbortSignal;
}>;

export async function loadDashboardMedia({
  accessToken,
  signal
}: LoadDashboardMediaOptions): Promise<DashboardMediaSnapshot> {
  return readDashboardMediaSummary({
    accessToken,
    signal
  });
}
