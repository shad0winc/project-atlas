import { DashboardGrid } from "../../dashboard/components/DashboardGrid";

import type { DashboardSnapshot } from "../../dashboard/types/dashboard";

type PortalOperationalSectionProps = Readonly<{
  operational: DashboardSnapshot;
}>;

export function PortalOperationalSection({
  operational
}: PortalOperationalSectionProps): React.ReactElement {
  return (
    <section aria-labelledby="portal-operational-heading" className="dashboard-runtime">
      <header>
        <h2 id="portal-operational-heading">Operational health</h2>

        <p>Live health across Atlas infrastructure and services.</p>
      </header>

      <DashboardGrid metrics={operational.metrics} />

      <p className="dashboard-generated-at">
        Health updated{" "}
        <time dateTime={operational.generatedAt}>
          {new Date(operational.generatedAt).toLocaleString()}
        </time>
      </p>
    </section>
  );
}
