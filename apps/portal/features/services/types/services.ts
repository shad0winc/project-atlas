export type ServiceRuntimeStatus = "running" | "stopped" | "restarting" | "failed" | "unknown";

export type ServiceHealthStatus = "healthy" | "degraded" | "unhealthy" | "unavailable" | "unknown";

export type ManagedService = Readonly<{
  identifier: string;
  name: string;
  provider: string;
  enabled: boolean;
  runtimeStatus: ServiceRuntimeStatus;
  healthStatus: ServiceHealthStatus;
}>;

export type ManagedServiceDetail = Readonly<{
  service: ManagedService;
  raw: Readonly<Record<string, unknown>>;
}>;

export type ServiceLifecycleHealth = Readonly<{
  status: ServiceHealthStatus;
  score: number | null;
  totalServices: number;
  healthy: number;
  degraded: number;
  unhealthy: number;
  unknown: number;
  evaluatedAt?: string;
}>;

export type ServiceLifecycleSummary = Readonly<{
  provider: string;
  composeProject?: string;
  totalServices: number;
  running: number;
  stopped: number;
  restarting: number;
  failed: number;
  unknownRuntime: number;
  evaluatedAt?: string;
}>;

export type ServiceUpdateStatus =
  "current" | "update-available" | "mutable-tag" | "unknown" | "unsupported";

export type ServiceUpdate = Readonly<{
  serviceIdentifier: string;
  serviceName: string;
  status: ServiceUpdateStatus;
  raw: Readonly<Record<string, unknown>>;
}>;

export type ServiceUpdateReport = Readonly<{
  status: string;
  provider: string;
  totalServices: number;
  current: number;
  updateAvailable: number;
  mutableTag: number;
  unknown: number;
  unsupported: number;
  requiresAttention: boolean;
  updates: readonly ServiceUpdate[];
  evaluatedAt?: string;
}>;

export type ServiceMaintenanceResult = "success" | "partial" | "failed" | "skipped" | "unknown";

export type ServiceMaintenanceRecord = Readonly<{
  serviceIdentifier: string;
  serviceName: string;
  provider: string;
  action: string;
  result: ServiceMaintenanceResult;
  succeeded: boolean;
  failed: boolean;
  startedAt?: string;
  completedAt?: string;
  durationSeconds: number | null;
  summary: string;
  raw: Readonly<Record<string, unknown>>;
}>;

export type ServiceMaintenanceHistory = Readonly<{
  provider: string;
  totalRecords: number;
  success: number;
  partial: number;
  failed: number;
  skipped: number;
  unknown: number;
  requiresAttention: boolean;
  records: readonly ServiceMaintenanceRecord[];
  generatedAt?: string;
}>;

export type ServiceLifecycleSnapshot = Readonly<{
  services: readonly ManagedService[];
  health: ServiceLifecycleHealth;
  summary: ServiceLifecycleSummary;
  updates: ServiceUpdateReport;
  history: ServiceMaintenanceHistory;
}>;

export type ServiceLifecycleState =
  | Readonly<{ status: "loading" }>
  | Readonly<{ status: "error"; error: Error }>
  | Readonly<{ status: "ready"; data: ServiceLifecycleSnapshot }>;

export type ServiceDetailState =
  | Readonly<{ status: "idle" }>
  | Readonly<{ status: "loading"; identifier: string }>
  | Readonly<{ status: "error"; identifier: string; error: Error }>
  | Readonly<{ status: "ready"; data: ManagedServiceDetail }>;

type UnknownRecord = Readonly<Record<string, unknown>>;

function recordValue(value: unknown): UnknownRecord {
  if (value === null || typeof value !== "object" || Array.isArray(value)) {
    return {};
  }

  return value as UnknownRecord;
}

function recordArray(value: unknown): readonly UnknownRecord[] {
  if (!Array.isArray(value)) {
    return [];
  }

  return value.map(recordValue);
}

function stringValue(value: unknown, fallback: string): string {
  return typeof value === "string" && value.trim() ? value.trim() : fallback;
}

function integerValue(value: unknown, fallback = 0): number {
  return typeof value === "number" && Number.isInteger(value) && value >= 0 ? value : fallback;
}

function scoreValue(value: unknown): number | null {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

function runtimeStatusValue(value: unknown): ServiceRuntimeStatus {
  const normalized = stringValue(value, "unknown").toLowerCase();

  if (
    normalized === "running" ||
    normalized === "stopped" ||
    normalized === "restarting" ||
    normalized === "failed"
  ) {
    return normalized;
  }

  return "unknown";
}

function healthStatusValue(value: unknown): ServiceHealthStatus {
  const normalized = stringValue(value, "unknown").toLowerCase();

  if (
    normalized === "healthy" ||
    normalized === "degraded" ||
    normalized === "unhealthy" ||
    normalized === "unavailable"
  ) {
    return normalized;
  }

  return "unknown";
}

function updateStatusValue(value: unknown): ServiceUpdateStatus {
  const normalized = stringValue(value, "unknown").toLowerCase();

  if (
    normalized === "current" ||
    normalized === "update-available" ||
    normalized === "mutable-tag" ||
    normalized === "unsupported"
  ) {
    return normalized;
  }

  return "unknown";
}

function maintenanceResultValue(value: unknown): ServiceMaintenanceResult {
  const normalized = stringValue(value, "unknown").toLowerCase();

  if (
    normalized === "success" ||
    normalized === "partial" ||
    normalized === "failed" ||
    normalized === "skipped"
  ) {
    return normalized;
  }

  return "unknown";
}

function serviceEntryMap(value: unknown): ReadonlyMap<string, UnknownRecord> {
  const entries = recordArray(recordValue(value).services);
  const mapped = new Map<string, UnknownRecord>();

  for (const entry of entries) {
    const service = recordValue(entry.service);
    const identifier = stringValue(service.identifier, "");

    if (identifier) {
      mapped.set(identifier, entry);
    }
  }

  return mapped;
}

export function createManagedService(
  value: unknown,
  runtimeEntryValue?: unknown,
  healthEntryValue?: unknown
): ManagedService {
  const service = recordValue(value);
  const embeddedRuntime = recordValue(service.runtime);
  const embeddedHealth = recordValue(service.health);

  const runtimeEntry = recordValue(runtimeEntryValue);
  const runtime = recordValue(runtimeEntry.runtime);

  const healthEntry = recordValue(healthEntryValue);
  const health = recordValue(healthEntry.health);

  const identifier = stringValue(service.identifier, "");

  if (!identifier) {
    throw new Error("Atlas managed service is missing an identifier.");
  }

  return {
    identifier,
    name: stringValue(service.name, identifier),
    provider: stringValue(service.provider, "unknown"),
    enabled: typeof service.enabled === "boolean" ? service.enabled : true,
    runtimeStatus: runtimeStatusValue(
      runtimeEntry.category ??
        runtime.state ??
        embeddedRuntime.category ??
        embeddedRuntime.state ??
        embeddedRuntime.status ??
        service.runtime_status
    ),
    healthStatus: healthStatusValue(health.status ?? embeddedHealth.status ?? service.health_status)
  };
}

export function createManagedServiceDetail(value: unknown): ManagedServiceDetail {
  const raw = recordValue(value);

  return {
    service: createManagedService(raw),
    raw
  };
}

export function mergeManagedServiceDetail(
  detail: ManagedServiceDetail,
  overview: ManagedService | undefined
): ManagedServiceDetail {
  if (overview === undefined) {
    return detail;
  }

  return {
    service: {
      ...detail.service,
      runtimeStatus: overview.runtimeStatus,
      healthStatus: overview.healthStatus
    },
    raw: detail.raw
  };
}

export function createServiceLifecycleHealth(value: unknown): ServiceLifecycleHealth {
  const health = recordValue(value);
  const counts = recordValue(health.counts);

  return {
    status: healthStatusValue(health.status),
    score: scoreValue(health.score),
    totalServices: integerValue(health.total_services),
    healthy: integerValue(counts.healthy),
    degraded: integerValue(counts.degraded),
    unhealthy: integerValue(counts.unhealthy),
    unknown: integerValue(counts.unknown),
    ...(typeof health.evaluated_at === "string" && health.evaluated_at.trim()
      ? { evaluatedAt: health.evaluated_at.trim() }
      : {})
  };
}

export function createServiceLifecycleSummary(value: unknown): ServiceLifecycleSummary {
  const summary = recordValue(value);
  const runtimeCounts = recordValue(summary.runtime_counts);

  return {
    provider: stringValue(summary.provider, "unknown"),
    ...(typeof summary.compose_project === "string" && summary.compose_project.trim()
      ? { composeProject: summary.compose_project.trim() }
      : {}),
    totalServices: integerValue(summary.total_services),
    running: integerValue(runtimeCounts.running),
    stopped: integerValue(runtimeCounts.stopped),
    restarting: integerValue(runtimeCounts.restarting),
    failed: integerValue(runtimeCounts.failed),
    unknownRuntime: integerValue(runtimeCounts.unknown),
    ...(typeof summary.evaluated_at === "string" && summary.evaluated_at.trim()
      ? { evaluatedAt: summary.evaluated_at.trim() }
      : {})
  };
}

export function createServiceUpdateReport(value: unknown): ServiceUpdateReport {
  const report = recordValue(value);
  const counts = recordValue(report.counts);
  const updates = recordArray(report.updates).map((entry) => ({
    serviceIdentifier: stringValue(entry.service_identifier, ""),
    serviceName: stringValue(
      entry.service_name,
      stringValue(entry.service_identifier, "Unknown service")
    ),
    status: updateStatusValue(entry.status),
    raw: entry
  }));

  return {
    status: stringValue(report.status, "unknown"),
    provider: stringValue(report.provider, "unknown"),
    totalServices: integerValue(report.total_services),
    current: integerValue(counts.current),
    updateAvailable: integerValue(counts["update-available"]),
    mutableTag: integerValue(counts["mutable-tag"]),
    unknown: integerValue(counts.unknown),
    unsupported: integerValue(counts.unsupported),
    requiresAttention: report.requires_attention === true,
    updates,
    ...(typeof report.evaluated_at === "string" && report.evaluated_at.trim()
      ? { evaluatedAt: report.evaluated_at.trim() }
      : {})
  };
}

export function createServiceMaintenanceHistory(value: unknown): ServiceMaintenanceHistory {
  const report = recordValue(value);
  const counts = recordValue(report.counts);

  const records = recordArray(report.records).map((entry) => ({
    serviceIdentifier: stringValue(entry.service_identifier, ""),
    serviceName: stringValue(
      entry.service_name,
      stringValue(entry.service_identifier, "Unknown service")
    ),
    provider: stringValue(entry.provider, stringValue(report.provider, "unknown")),
    action: stringValue(entry.action, "unknown"),
    result: maintenanceResultValue(entry.result),
    succeeded: entry.succeeded === true,
    failed: entry.failed === true,
    ...(typeof entry.started_at === "string" && entry.started_at.trim()
      ? { startedAt: entry.started_at.trim() }
      : {}),
    ...(typeof entry.completed_at === "string" && entry.completed_at.trim()
      ? { completedAt: entry.completed_at.trim() }
      : {}),
    durationSeconds:
      typeof entry.duration_seconds === "number" && Number.isFinite(entry.duration_seconds)
        ? entry.duration_seconds
        : null,
    summary: stringValue(entry.summary, "No maintenance summary was reported."),
    raw: entry
  }));

  return {
    provider: stringValue(report.provider, "unknown"),
    totalRecords: integerValue(report.total_records),
    success: integerValue(counts.success),
    partial: integerValue(counts.partial),
    failed: integerValue(counts.failed),
    skipped: integerValue(counts.skipped),
    unknown: integerValue(counts.unknown),
    requiresAttention: report.requires_attention === true,
    records,
    ...(typeof report.generated_at === "string" && report.generated_at.trim()
      ? { generatedAt: report.generated_at.trim() }
      : {})
  };
}

export function createServiceLifecycleSnapshot({
  services,
  health,
  summary,
  updates,
  history
}: Readonly<{
  services: readonly unknown[];
  health: unknown;
  summary: unknown;
  updates: unknown;
  history: unknown;
}>): ServiceLifecycleSnapshot {
  const runtimeEntries = serviceEntryMap(summary);
  const healthEntries = serviceEntryMap(health);

  return {
    services: services.map((value) => {
      const service = recordValue(value);
      const identifier = stringValue(service.identifier, "");

      return createManagedService(
        service,
        runtimeEntries.get(identifier),
        healthEntries.get(identifier)
      );
    }),
    health: createServiceLifecycleHealth(health),
    summary: createServiceLifecycleSummary(summary),
    updates: createServiceUpdateReport(updates),
    history: createServiceMaintenanceHistory(history)
  };
}
