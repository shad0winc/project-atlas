import { readDashboardSummary } from "../../../lib/services/dashboard";

import type { DashboardSnapshot } from "../types/dashboard";

export type LoadDashboardOptions = Readonly<{
  accessToken: string;
  signal?: AbortSignal;
}>;

export async function loadDashboard({
  accessToken,
  signal
}: LoadDashboardOptions): Promise<DashboardSnapshot> {
  return readDashboardSummary({
    accessToken,
    signal
  });
}
