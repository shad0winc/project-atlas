import { Badge } from "../../../components/ui/Badge";
import { Card } from "../../../components/ui/Card";

import type { PortalSchedulerSnapshot } from "../types/scheduler";

type SchedulerFailuresPanelProps = Readonly<{
  scheduler: PortalSchedulerSnapshot;
}>;

function formatFailureTimestamp(value: string | null): string {
  if (value === null) {
    return "Time unavailable";
  }

  return new Date(value).toLocaleString();
}

export function SchedulerFailuresPanel({
  scheduler
}: SchedulerFailuresPanelProps): React.ReactElement {
  if (scheduler.status === "unavailable") {
    return (
      <Card>
        <h3>Recent scheduler failures</h3>

        <Badge>Unavailable</Badge>

        <p>{scheduler.detail ?? "Scheduler failure history is currently unavailable."}</p>
      </Card>
    );
  }

  if (!scheduler.recentFailures.length) {
    return (
      <Card>
        <h3>Recent scheduler failures</h3>

        <Badge variant="success">Clear</Badge>

        <p>Atlas has no recent scheduler task failures.</p>
      </Card>
    );
  }

  return (
    <Card>
      <h3>Recent scheduler failures</h3>

      <Badge variant="primary">
        {scheduler.recentFailures.length} failure
        {scheduler.recentFailures.length === 1 ? "" : "s"}
      </Badge>

      <ul className="status-list">
        {scheduler.recentFailures.map((failure) => (
          <li
            className="status-list__item"
            key={`${failure.taskName}:${failure.failedAt ?? failure.error}`}
          >
            <div>
              <strong>{failure.taskName}</strong>

              <p>{failure.error}</p>

              <time dateTime={failure.failedAt ?? undefined}>
                {formatFailureTimestamp(failure.failedAt)}
              </time>
            </div>

            <span className="status-list__state">
              <Badge>Failed</Badge>
            </span>
          </li>
        ))}
      </ul>
    </Card>
  );
}
