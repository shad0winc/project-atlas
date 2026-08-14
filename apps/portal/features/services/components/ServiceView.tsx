"use client";

import { useServices } from "../hooks/use-services";

import { ServiceOverview } from "./ServiceOverview";

export function ServiceView(): React.ReactElement {
  const { state, detailState, refresh, selectService, clearSelection } = useServices();

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

  return (
    <ServiceOverview
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
      onClearSelection={clearSelection}
      onSelectService={selectService}
      snapshot={state.data}
    />
  );
}
