import { authenticatedAtlasApiRequest } from "../../../lib/services/authenticated";

import {
  createManagedServiceDetail,
  createServiceLifecycleSnapshot,
  createServiceUpdateReport,
  type ManagedServiceDetail,
  type ServiceLifecycleSnapshot,
  type ServiceUpdateReport
} from "../types/services";

export type LoadServiceLifecycleOptions = Readonly<{
  signal?: AbortSignal;
}>;

type ManagedServiceListTransportResponse = Readonly<{
  count: number;
  services: readonly Record<string, unknown>[];
}>;

type ManagedServiceDetailTransportResponse = Readonly<{
  service: Readonly<Record<string, unknown>>;
}>;

type ServiceLifecycleHealthTransportResponse = Readonly<{
  health: Readonly<Record<string, unknown>>;
}>;

type ServiceLifecycleSummaryTransportResponse = Readonly<{
  summary: Readonly<Record<string, unknown>>;
}>;

type ServiceUpdateReportTransportResponse = Readonly<{
  report: Readonly<Record<string, unknown>>;
}>;

type ServiceMaintenanceHistoryTransportResponse = Readonly<{
  report: Readonly<Record<string, unknown>>;
}>;

function getRequestOptions(signal: AbortSignal | undefined) {
  return {
    method: "GET",
    cache: "no-store" as const,
    signal
  };
}

function requestServiceUpdates(signal: AbortSignal | undefined) {
  return authenticatedAtlasApiRequest<ServiceUpdateReportTransportResponse>(
    "/services/updates",
    getRequestOptions(signal)
  );
}

export async function loadServiceUpdateReport({
  signal
}: LoadServiceLifecycleOptions = {}): Promise<ServiceUpdateReport> {
  const { report } = await requestServiceUpdates(signal);
  return createServiceUpdateReport(report);
}

export async function loadServiceLifecycleOverview({
  signal
}: LoadServiceLifecycleOptions = {}): Promise<ServiceLifecycleSnapshot> {
  const [services, health, summary, updates, history] = await Promise.all([
    authenticatedAtlasApiRequest<ManagedServiceListTransportResponse>(
      "/services",
      getRequestOptions(signal)
    ),
    authenticatedAtlasApiRequest<ServiceLifecycleHealthTransportResponse>(
      "/services/health",
      getRequestOptions(signal)
    ),
    authenticatedAtlasApiRequest<ServiceLifecycleSummaryTransportResponse>(
      "/services/summary",
      getRequestOptions(signal)
    ),
    requestServiceUpdates(signal),
    authenticatedAtlasApiRequest<ServiceMaintenanceHistoryTransportResponse>(
      "/services/history",
      getRequestOptions(signal)
    )
  ]);

  return createServiceLifecycleSnapshot({
    services: services.services,
    health: health.health,
    summary: summary.summary,
    updates: updates.report,
    history: history.report
  });
}

export async function loadManagedServiceDetail(
  serviceIdentifier: string,
  { signal }: LoadServiceLifecycleOptions = {}
): Promise<ManagedServiceDetail> {
  const normalizedIdentifier = serviceIdentifier.trim();

  if (!normalizedIdentifier) {
    throw new Error("Atlas managed service identifier cannot be empty.");
  }

  const response = await authenticatedAtlasApiRequest<ManagedServiceDetailTransportResponse>(
    `/services/${encodeURIComponent(normalizedIdentifier)}`,
    getRequestOptions(signal)
  );

  return createManagedServiceDetail(response.service);
}

export type BazarrUpdatePlan = Readonly<{
  current_image: { canonical_reference: string };
  target_image: { canonical_reference: string };
  warnings: readonly string[];
}>;

export async function loadBazarrUpdatePlan(signal: AbortSignal): Promise<BazarrUpdatePlan> {
  const { plan } = await authenticatedAtlasApiRequest<{ plan: BazarrUpdatePlan }>(
    "/services/bazarr/update-preview",
    getRequestOptions(signal)
  );
  return plan;
}

export type ServiceMaintenanceJob = Readonly<{
  id: string;
  operation: string;
  status: "queued" | "running" | "completed" | "failed";
  progress: string;
  error?: string | null;
}>;

export type ServiceMaintenanceState = Readonly<{
  job: ServiceMaintenanceJob | null;
  bazarr: {
    status: string;
    version_label: string | null;
    can_apply: boolean;
    can_rollback: boolean;
    maintenance_enabled: boolean;
  };
}>;

export function loadServiceMaintenance(signal: AbortSignal): Promise<ServiceMaintenanceState> {
  return authenticatedAtlasApiRequest<ServiceMaintenanceState>(
    "/services/maintenance",
    getRequestOptions(signal)
  );
}

export async function startServiceMaintenance(
  operation: "scan" | "bazarr.apply" | "bazarr.rollback",
  signal: AbortSignal
): Promise<ServiceMaintenanceJob> {
  const path = operation === "scan" ? "/services/updates/refresh" :
    operation === "bazarr.apply" ? "/services/bazarr/apply" : "/services/bazarr/rollback";
  const { job } = await authenticatedAtlasApiRequest<{ job: ServiceMaintenanceJob }>(
    path, { method: "POST", cache: "no-store", signal, body: {} }
  );
  return job;
}

export function waitForServicePoll(signal: AbortSignal): Promise<void> {
  return new Promise((resolve, reject) => {
    function abort() {
      globalThis.clearTimeout(timer);
      reject(new DOMException("Request aborted", "AbortError"));
    }
    const timer = globalThis.setTimeout(() => {
      signal.removeEventListener("abort", abort);
      resolve();
    }, 1500);
    if (signal.aborted) {
      abort();
    } else {
      signal.addEventListener("abort", abort, { once: true });
    }
  });
}

export async function scanServiceUpdates(signal: AbortSignal): Promise<void> {
  const job = await startServiceMaintenance("scan", signal);
  const deadline = Date.now() + 10 * 60 * 1000;
  while (!signal.aborted && Date.now() < deadline) {
    await waitForServicePoll(signal);
    const state = await loadServiceMaintenance(signal);
    if (state.job?.id !== job.id) {
      throw new Error("The scan status changed. Refresh the service report.");
    }
    if (state.job.status === "failed") {
      throw new Error("The service scan failed. Try again.");
    }
    if (state.job.status === "completed") {
      return;
    }
  }
  throw new Error("The scan is still running. Check its status again.");
}
