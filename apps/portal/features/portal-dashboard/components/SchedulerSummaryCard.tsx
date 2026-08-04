import { Badge } from "../../../components/ui/Badge";
import { Card } from "../../../components/ui/Card";

import type {
  PortalSchedulerSnapshot
} from "../types/scheduler";


type SchedulerSummaryCardProps = Readonly<{
  scheduler: PortalSchedulerSnapshot;
}>;


function statusVariant(
  status: "available" | "unavailable"
): "default" | "success" {
  if (status === "available") {
    return "success";
  }

  return "default";
}


function formatOptionalTimestamp(
  value: string | null
): string {
  if (!value) {
    return "Not available";
  }

  return new Date(value).toLocaleString();
}


export function SchedulerSummaryCard({
  scheduler
}: SchedulerSummaryCardProps): React.ReactElement {
  if (scheduler.status === "unavailable") {
    return (
      <Card>
        <h3>Scheduler</h3>

        <Badge>
          Unavailable
        </Badge>

        <p>
          {scheduler.detail ??
            "Scheduler state is unavailable."}
        </p>
      </Card>
    );
  }

  return (
    <Card>
      <h3>Scheduler</h3>

      <Badge variant={statusVariant(scheduler.status)}>
        Available
      </Badge>

      <p>
        Registered: {scheduler.registeredCount}
      </p>

      <p>
        Enabled: {scheduler.enabledCount}
      </p>

      <p>
        Running: {scheduler.runningCount}
      </p>

      <p>
        Due: {scheduler.dueCount}
      </p>

      <p>
        Failed: {scheduler.failedCount}
      </p>

      <p>
        Last Run:{" "}
        {formatOptionalTimestamp(
          scheduler.lastRunAt
        )}
      </p>

      <p>
        Next Run:{" "}
        {formatOptionalTimestamp(
          scheduler.nextRunAt
        )}
      </p>
    </Card>
  );
}
