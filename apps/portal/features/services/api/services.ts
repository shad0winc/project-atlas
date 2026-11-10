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
