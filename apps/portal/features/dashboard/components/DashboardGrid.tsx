import type { DashboardMetric } from "../types/dashboard";
import { MetricCard } from "./MetricCard";

type DashboardGridProps = Readonly<{
  metrics: readonly DashboardMetric[];
}>;

export function DashboardGrid({ metrics }: DashboardGridProps): React.ReactElement {
  if (!metrics.length) {
    return (
      <section aria-label="Dashboard overview" className="dashboard-empty-state">
        <h3>No dashboard metrics are available</h3>
        <p>Atlas has not returned any operational dashboard data.</p>
      </section>
    );
  }

  return (
    <section aria-label="Dashboard overview" className="dashboard-metric-grid">
      {metrics.map((metric) => (
        <MetricCard key={metric.id} metric={metric} />
      ))}
    </section>
  );
}
