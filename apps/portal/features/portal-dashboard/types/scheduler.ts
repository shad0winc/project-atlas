import type { AtlasPortalSchedulerSummaryResponse } from "../../../lib/api/contracts";

export type PortalSchedulerFailure = Readonly<{
  taskName: string;
  failedAt: string | null;
  error: string;
}>;

export type PortalSchedulerSnapshot = Readonly<{
  status: "available" | "unavailable";
  detail: string | null;

  registeredCount: number | null;
  enabledCount: number | null;
  disabledCount: number | null;
  dueCount: number | null;
  runningCount: number | null;
  failedCount: number | null;

  lastRunAt: string | null;
  nextRunAt: string | null;

  recentFailures: readonly PortalSchedulerFailure[];
}>;

function normalizeOptionalTimestamp(value: string | null): string | null {
  if (value === null) {
    return null;
  }

  const timestamp = new Date(value);

  if (Number.isNaN(timestamp.getTime())) {
    throw new Error("Scheduler timestamp must be valid.");
  }

  return timestamp.toISOString();
}

export function createPortalSchedulerSnapshot(
  value: AtlasPortalSchedulerSummaryResponse
): PortalSchedulerSnapshot {
  return {
    status: value.status,
    detail: value.detail,

    registeredCount: value.registered_count,
    enabledCount: value.enabled_count,
    disabledCount: value.disabled_count,
    dueCount: value.due_count,
    runningCount: value.running_count,
    failedCount: value.failed_count,

    lastRunAt: normalizeOptionalTimestamp(value.last_run_at),

    nextRunAt: normalizeOptionalTimestamp(value.next_run_at),

    recentFailures: value.recent_failures.map((failure) => ({
      taskName: failure.task_name,
      failedAt: normalizeOptionalTimestamp(failure.failed_at),
      error: failure.error
    }))
  };
}
