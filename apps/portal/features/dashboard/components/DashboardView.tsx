"use client";

import { useDashboard } from "../hooks/use-dashboard";

import { DashboardError } from "./DashboardError";
import { DashboardGrid } from "./DashboardGrid";
import { DashboardMediaSection } from "./DashboardMediaSection";
import { DashboardSkeleton } from "./DashboardSkeleton";

export function DashboardView(): React.ReactElement {
  const { state, refresh } = useDashboard();

  if (state.status === "loading") {
    return <DashboardSkeleton cardCount={4} />;
  }

  if (state.status === "error") {
    return <DashboardError message={state.error.message} onRetry={refresh} />;
  }

  return (
    <div className="dashboard-runtime">
      <section aria-labelledby="dashboard-health-heading">
        <header>
          <h2 id="dashboard-health-heading">Operational health</h2>

          <p>Live health across Atlas infrastructure and services.</p>
        </header>

        <DashboardGrid metrics={state.data.metrics} />

        <p className="dashboard-generated-at">
          Health updated{" "}
          <time dateTime={state.data.generatedAt}>
            {new Date(state.data.generatedAt).toLocaleString()}
          </time>
        </p>
      </section>

      <DashboardMediaSection />
    </div>
  );
}
