"use client";

import {
  Card
} from "../../../components/ui/Card";

import {
  usePortalDashboard
} from "../hooks/use-portal-dashboard";


import {
  PortalDashboardGrid
} from "./PortalDashboardGrid";

import {
  PortalHealthCard
} from "./PortalHealthCard";


function DashboardPlaceholderCard(
  {
    title,
    description
  }: Readonly<{
    title: string;
    description: string;
  }>
): React.ReactElement {
  return (
    <Card>
      <h3>{title}</h3>

      <p>{description}</p>
    </Card>
  );
}


export function PortalDashboardView(): React.ReactElement {
  const {
    state,
    refresh
  } = usePortalDashboard();


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
            <div
              aria-hidden="true"
              className="dashboard-skeleton-card"
              key={index}
            />
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
          <p className="dashboard-error-eyebrow">
            Portal unavailable
          </p>

          <h3
            className="dashboard-error-title"
            id="portal-dashboard-error-title"
          >
            Atlas could not load the portal dashboard
          </h3>

          <p className="dashboard-error-message">
            {state.error.message}
          </p>
        </div>

        <button
          className="dashboard-retry-button"
          onClick={refresh}
          type="button"
        >
          Try again
        </button>
      </section>
    );
  }


  return (
    <div className="dashboard-runtime">
      <PortalHealthCard
        generatedAt={state.data.generatedAt}
        health={state.data.health}
      />


      <PortalDashboardGrid>
        <DashboardPlaceholderCard
          description="Operational dashboard metrics and runtime summaries."
          title="Operations"
        />

        <DashboardPlaceholderCard
          description="Media library availability and statistics."
          title="Media"
        />

        <DashboardPlaceholderCard
          description="Persisted Operations reports and attention data."
          title="Operations Intelligence"
        />

        <DashboardPlaceholderCard
          description="Scheduler runtime state and recent failures."
          title="Scheduler"
        />
      </PortalDashboardGrid>
    </div>
  );
}
