import { Card } from "../../../components/ui/Card";

import type {
  ManagedService,
  ManagedServiceDetail,
  ServiceLifecycleSnapshot
} from "../types/services";

import { ServiceHealthCard } from "./ServiceHealthCard";

type ServiceOverviewProps = Readonly<{
  snapshot: ServiceLifecycleSnapshot;
  detail?: ManagedServiceDetail;
  detailIdentifier?: string;
  detailError?: string;
  detailLoading?: boolean;
  onSelectService: (identifier: string) => void;
  onClearSelection: () => void;
}>;

function serviceStatus(service: ManagedService): string {
  if (!service.enabled) {
    return "disabled";
  }

  if (service.healthStatus !== "unknown") {
    return service.healthStatus;
  }

  return service.runtimeStatus;
}

function displayRawValue(value: unknown): string {
  if (value === null || value === undefined) {
    return "Not reported";
  }

  if (typeof value === "string" || typeof value === "number" || typeof value === "boolean") {
    return String(value);
  }

  return JSON.stringify(value);
}

export function ServiceOverview({
  snapshot,
  detail,
  detailIdentifier,
  detailError,
  detailLoading = false,
  onSelectService,
  onClearSelection
}: ServiceOverviewProps): React.ReactElement {
  return (
    <div className="dashboard-runtime">
      <section aria-label="Service Lifecycle summary" className="dashboard-metric-grid">
        <ServiceHealthCard health={snapshot.health} />

        <Card>
          <p>Managed services</p>
          <h3>{snapshot.summary.totalServices}</h3>
          <p>Provider: {snapshot.summary.provider}</p>
          {snapshot.summary.composeProject ? (
            <p>Compose project: {snapshot.summary.composeProject}</p>
          ) : null}
          <p>
            Running {snapshot.summary.running} · Stopped {snapshot.summary.stopped} · Restarting{" "}
            {snapshot.summary.restarting} · Failed {snapshot.summary.failed}
          </p>
        </Card>
      </section>

      <section aria-labelledby="managed-services-title">
        <h2 id="managed-services-title">Managed services</h2>
        <p>Select a service to inspect its normalized read-only details.</p>

        {snapshot.services.length === 0 ? (
          <Card>
            <h3>No managed services were returned</h3>
            <p>Atlas did not report any configured managed-service identities.</p>
          </Card>
        ) : (
          <div className="dashboard-metric-grid">
            {snapshot.services.map((service) => (
              <Card key={service.identifier}>
                <p>{service.provider}</p>
                <h3>{service.name}</h3>
                <p>Identifier: {service.identifier}</p>
                <p>Status: {serviceStatus(service)}</p>
                <p>Runtime: {service.runtimeStatus}</p>
                <p>Health: {service.healthStatus}</p>
                <button
                  className="dashboard-retry-button"
                  onClick={() => onSelectService(service.identifier)}
                  type="button"
                >
                  View details
                </button>
              </Card>
            ))}
          </div>
        )}
      </section>

      {detailIdentifier || detail ? (
        <section aria-labelledby="service-detail-title">
          <div>
            <p>Read-only service detail</p>
            <h2 id="service-detail-title">
              {detail?.service.name ?? detailIdentifier ?? "Managed service"}
            </h2>
          </div>

          {detailLoading ? (
            <Card>
              <p aria-live="polite">Loading service details…</p>
            </Card>
          ) : null}

          {detailError ? (
            <section className="dashboard-error" role="alert">
              <div>
                <h3>Atlas could not load service details</h3>
                <p>{detailError}</p>
              </div>
            </section>
          ) : null}

          {detail ? (
            <Card>
              <p>Runtime: {detail.service.runtimeStatus}</p>
              <p>Health: {detail.service.healthStatus}</p>
              <dl>
                {Object.entries(detail.raw).map(([key, value]) => (
                  <div key={key}>
                    <dt>{key.replaceAll("_", " ")}</dt>
                    <dd>{displayRawValue(value)}</dd>
                  </div>
                ))}
              </dl>
            </Card>
          ) : null}

          <button className="dashboard-retry-button" onClick={onClearSelection} type="button">
            Close details
          </button>
        </section>
      ) : null}
    </div>
  );
}
