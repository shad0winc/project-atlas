"use client";

import { RequirePermission } from "../../../components/auth/RequirePermission";
import { ATLAS_PERMISSIONS } from "../../../lib/authorization";

import { useDashboardMedia } from "../hooks/use-dashboard-media";

import { DashboardError } from "./DashboardError";
import { DashboardSkeleton } from "./DashboardSkeleton";
import { MediaLibraryGrid } from "./MediaLibraryGrid";

function DashboardMediaContent(): React.ReactElement {
  const { state, refresh } = useDashboardMedia();

  return (
    <section aria-labelledby="dashboard-media-heading" className="dashboard-runtime">
      <header>
        <h2 id="dashboard-media-heading">Media libraries</h2>

        <p>Current library totals collected by Atlas Retention Intelligence.</p>
      </header>

      {state.status === "loading" ? <DashboardSkeleton cardCount={7} /> : null}

      {state.status === "error" ? (
        <DashboardError message={state.error.message} onRetry={refresh} />
      ) : null}

      {state.status === "ready" ? (
        <>
          <MediaLibraryGrid libraries={state.data.libraries} />

          <p className="dashboard-generated-at">
            Media statistics updated{" "}
            <time dateTime={state.data.generatedAt}>
              {new Date(state.data.generatedAt).toLocaleString()}
            </time>
          </p>
        </>
      ) : null}
    </section>
  );
}

export function DashboardMediaSection(): React.ReactElement {
  return (
    <RequirePermission permission={ATLAS_PERMISSIONS.mediaRead}>
      <DashboardMediaContent />
    </RequirePermission>
  );
}
