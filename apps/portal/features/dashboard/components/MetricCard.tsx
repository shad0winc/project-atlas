import type { DashboardMetric } from "../types/dashboard";
import { StatusBadge } from "./StatusBadge";

type MetricCardProps = Readonly<{
  metric: DashboardMetric;
}>;

export function MetricCard({ metric }: MetricCardProps): React.ReactElement {
  return (
    <article aria-labelledby={`dashboard-metric-${metric.id}`} className="dashboard-metric-card">
      <div className="dashboard-metric-header">
        <p className="dashboard-metric-label" id={`dashboard-metric-${metric.id}`}>
          {metric.label}
        </p>

        <StatusBadge status={metric.status} />
      </div>

      <strong className="dashboard-metric-value">{metric.value}</strong>

      <p className="dashboard-metric-description">{metric.description}</p>

      {metric.detail ? <p className="dashboard-metric-detail">{metric.detail}</p> : null}
    </article>
  );
}
