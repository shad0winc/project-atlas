"use client";

import { useAuth } from "../../../lib/auth/use-auth";
import { useServices } from "../hooks/use-services";

import { ServiceOverview } from "./ServiceOverview";
import { BazarrMaintenanceControls } from "./BazarrMaintenanceControls";

export function ServiceView(): React.ReactElement {
  const { user } = useAuth();
  const {
    state,
    detailState,
    refresh,
    checkForUpdates,
    reloadObservations,
    updateCheckStatus,
    selectService,
    clearSelection
  } = useServices();

  if (state.status === "loading") {
    return (
      <section
        aria-busy="true"
        aria-label="Loading managed services"
        className="dashboard-metric-grid"
      >
        {Array.from({ length: 4 }, (_, index) => (
          <div aria-hidden="true" className="dashboard-skeleton-card" key={index} />
        ))}
      </section>
    );
  }

  if (state.status === "error") {
    return (
      <section
        aria-labelledby="service-lifecycle-error-title"
        className="dashboard-error"
        role="alert"
      >
        <div>
          <p>Services unavailable</p>
          <h3 id="service-lifecycle-error-title">Atlas could not load managed services</h3>
          <p>{state.error.message}</p>
        </div>

        <button className="dashboard-retry-button" onClick={refresh} type="button">
          Try again
        </button>
      </section>
    );
  }

  const selectedBazarr = detailState.status === "ready"
    ? detailState.data.service.identifier === "bazarr"
    : detailState.status !== "idle" && detailState.identifier === "bazarr";

  return (
    <>
    <ServiceOverview
      canPreviewBazarrUpdate={user?.roles.includes("global_admin")}
      detail={detailState.status === "ready" ? detailState.data : undefined}
      detailError={detailState.status === "error" ? detailState.error.message : undefined}
      detailIdentifier={
        detailState.status === "loading" || detailState.status === "error"
          ? detailState.identifier
          : detailState.status === "ready"
            ? detailState.data.service.identifier
            : undefined
      }
      detailLoading={detailState.status === "loading"}
      onCheckForUpdates={checkForUpdates}
      onClearSelection={clearSelection}
      onSelectService={selectService}
      snapshot={state.data}
      updateCheckStatus={updateCheckStatus}
    />
    {user?.roles.includes("global_admin") && selectedBazarr ? (
      <BazarrMaintenanceControls onCompleted={reloadObservations} />
    ) : null}
    </>
  );
}
