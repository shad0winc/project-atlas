"use client";

import { usePortalDashboard } from "../hooks/use-portal-dashboard";

import { PortalDashboardGrid } from "./PortalDashboardGrid";

import { PortalHealthCard } from "./PortalHealthCard";

import { PortalMediaSection } from "./PortalMediaSection";

import { PortalOperationalSection } from "./PortalOperationalSection";

import { OperationsSummaryCard } from "./OperationsSummaryCard";

import { OperationsComparisonCard } from "./OperationsComparisonCard";

import { OperationsAttentionPanel } from "./OperationsAttentionPanel";

import { SchedulerSummaryCard } from "./SchedulerSummaryCard";

export function PortalDashboardView(): React.ReactElement {
  const { state, refresh } = usePortalDashboard();

  if (state.status === "loading") {
    return (
      <section
        aria-busy="true"
        aria-label="Loading portal dashboard"
        className="dashboard-metric-grid"
      >
        {Array.from(
          {
            length: 5
          },
          (_, index) => (
            <div aria-hidden="true" className="dashboard-skeleton-card" key={index} />
          )
        )}
      </section>
    );
  }

  if (state.status === "error") {
    return (
      <section
        aria-labelledby="portal-dashboard-error-title"
        className="dashboard-error"
        role="alert"
      >
        <div>
          <p className="dashboard-error-eyebrow">Portal unavailable</p>

          <h3 className="dashboard-error-title" id="portal-dashboard-error-title">
            Atlas could not load the portal dashboard
          </h3>

          <p className="dashboard-error-message">{state.error.message}</p>
        </div>

        <button className="dashboard-retry-button" onClick={refresh} type="button">
          Try again
        </button>
      </section>
    );
  }

  return (
    <div className="dashboard-runtime">
      <PortalHealthCard generatedAt={state.data.generatedAt} health={state.data.health} />

      <PortalDashboardGrid>
        <PortalOperationalSection operational={state.data.operational} />

        <PortalMediaSection media={state.data.media} />

        <OperationsSummaryCard operations={state.data.operations} />

        <OperationsComparisonCard comparison={state.data.operations.comparison} />

        <OperationsAttentionPanel operations={state.data.operations} />

        <SchedulerSummaryCard scheduler={state.data.scheduler} />
      </PortalDashboardGrid>
    </div>
  );
}
