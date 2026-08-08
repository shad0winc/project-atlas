import type { DashboardStatus } from "../types/dashboard";

type StatusBadgeProps = Readonly<{
  status: DashboardStatus;
}>;

const statusLabels: Readonly<Record<DashboardStatus, string>> = {
  healthy: "Healthy",
  warning: "Warning",
  offline: "Offline",
  unknown: "Unknown",
  preparing: "Preparing"
};

export function StatusBadge({ status }: StatusBadgeProps): React.ReactElement {
  return (
    <span className="dashboard-status-badge" data-status={status}>
      <span aria-hidden="true" className="dashboard-status-indicator" />
      {statusLabels[status]}
    </span>
  );
}
