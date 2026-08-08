export type DashboardStatus = "healthy" | "warning" | "offline" | "unknown" | "preparing";

export type DashboardMetric = Readonly<{
  id: string;
  label: string;
  value: string;
  description: string;
  status: DashboardStatus;
  detail?: string;
}>;

export type DashboardSnapshot = Readonly<{
  generatedAt: string;
  metrics: readonly DashboardMetric[];
}>;

function normalizeRequiredText(value: string, fieldName: string): string {
  const normalized = value.trim();

  if (!normalized) {
    throw new Error(`${fieldName} must not be empty.`);
  }

  return normalized;
}

function normalizeTimestamp(value: string): string {
  const timestamp = new Date(value);

  if (Number.isNaN(timestamp.getTime())) {
    throw new Error("generatedAt must be a valid timestamp.");
  }

  return timestamp.toISOString();
}

export function createDashboardMetric(metric: DashboardMetric): DashboardMetric {
  return {
    id: normalizeRequiredText(metric.id, "metric.id"),
    label: normalizeRequiredText(metric.label, "metric.label"),
    value: normalizeRequiredText(metric.value, "metric.value"),
    description: normalizeRequiredText(metric.description, "metric.description"),
    status: metric.status,
    ...(metric.detail?.trim()
      ? {
          detail: metric.detail.trim()
        }
      : {})
  };
}

export function createDashboardSnapshot(snapshot: DashboardSnapshot): DashboardSnapshot {
  const metrics = snapshot.metrics.map(createDashboardMetric);
  const metricIds = new Set(metrics.map((metric) => metric.id));

  if (metricIds.size !== metrics.length) {
    throw new Error("Dashboard metric IDs must be unique.");
  }

  return {
    generatedAt: normalizeTimestamp(snapshot.generatedAt),
    metrics
  };
}
