"use client";

import { useDashboard } from "../hooks/use-dashboard";
import { DashboardError } from "./DashboardError";
import { DashboardGrid } from "./DashboardGrid";
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
      <DashboardGrid metrics={state.data.metrics} />

      <p className="dashboard-generated-at">
        Updated{" "}
        <time dateTime={state.data.generatedAt}>
          {new Date(state.data.generatedAt).toLocaleString()}
        </time>
      </p>
    </div>
  );
}
