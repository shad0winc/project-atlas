import type { ReactNode } from "react";

type PortalDashboardGridProps = Readonly<{
  children: ReactNode;
}>;

export function PortalDashboardGrid({
  children
}: PortalDashboardGridProps): React.ReactElement {
  return (
    <section
      aria-label="Portal dashboard sections"
      className="dashboard-metric-grid"
    >
      {children}
    </section>
  );
}
