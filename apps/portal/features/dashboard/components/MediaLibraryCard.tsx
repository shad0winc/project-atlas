import type { DashboardStatus } from "../types/dashboard";
import type { DashboardMediaLibrary } from "../types/dashboard-media";

import { StatusBadge } from "./StatusBadge";

type MediaLibraryCardProps = Readonly<{
  library: DashboardMediaLibrary;
}>;

function dashboardStatus(library: DashboardMediaLibrary): DashboardStatus {
  return library.status === "available" ? "healthy" : "unknown";
}

function displayValue(library: DashboardMediaLibrary): string {
  if (library.status === "unavailable" || library.count === undefined) {
    return "Unavailable";
  }

  return library.count.toLocaleString("en-US");
}

export function MediaLibraryCard({ library }: MediaLibraryCardProps): React.ReactElement {
  const headingId = `dashboard-media-${library.id}`;

  return (
    <article aria-labelledby={headingId} className="dashboard-metric-card">
      <div className="dashboard-metric-header">
        <p className="dashboard-metric-label" id={headingId}>
          {library.label}
        </p>

        <StatusBadge status={dashboardStatus(library)} />
      </div>

      <strong className="dashboard-metric-value">{displayValue(library)}</strong>

      <p className="dashboard-metric-description">
        Media currently represented in the Atlas library.
      </p>

      {library.detail ? <p className="dashboard-metric-detail">{library.detail}</p> : null}
    </article>
  );
}
