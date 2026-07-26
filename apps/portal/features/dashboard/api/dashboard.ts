import { placeholderDashboardSnapshot } from "../data/placeholder-dashboard";
import { createDashboardSnapshot, type DashboardSnapshot } from "../types/dashboard";

export type LoadDashboardOptions = Readonly<{
  signal?: AbortSignal;
}>;

function throwIfAborted(signal?: AbortSignal): void {
  if (signal?.aborted) {
    throw new DOMException("The dashboard request was cancelled.", "AbortError");
  }
}

export async function loadDashboard(
  options: LoadDashboardOptions = {}
): Promise<DashboardSnapshot> {
  throwIfAborted(options.signal);

  /*
   * Keep the service asynchronous from the beginning so the UI contract
   * does not change when this placeholder is replaced by the Atlas API.
   */
  await Promise.resolve();

  throwIfAborted(options.signal);

  return createDashboardSnapshot({
    generatedAt: new Date().toISOString(),
    metrics: placeholderDashboardSnapshot.metrics
  });
}
