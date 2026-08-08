import { readDashboardSummary } from "../../../lib/services/dashboard";

import type { DashboardSnapshot } from "../types/dashboard";

export type LoadDashboardOptions = Readonly<{
  signal?: AbortSignal;
}>;

export async function loadDashboard({
  signal
}: LoadDashboardOptions = {}): Promise<DashboardSnapshot> {
  return readDashboardSummary({
    signal
  });
}
