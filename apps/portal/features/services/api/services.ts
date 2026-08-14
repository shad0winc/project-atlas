import { authenticatedAtlasApiRequest } from "../../../lib/services/authenticated";

import {
  createManagedServiceDetail,
  createServiceLifecycleSnapshot,
  type ManagedServiceDetail,
  type ServiceLifecycleSnapshot
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

function getRequestOptions(signal: AbortSignal | undefined) {
  return {
    method: "GET",
    cache: "no-store" as const,
    signal
  };
}

export async function loadServiceLifecycleOverview({
  signal
}: LoadServiceLifecycleOptions = {}): Promise<ServiceLifecycleSnapshot> {
  const [services, health, summary] = await Promise.all([
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
    )
  ]);

  return createServiceLifecycleSnapshot({
    services: services.services,
    health: health.health,
    summary: summary.summary
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
