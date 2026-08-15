import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import {
  createManagedService,
  createManagedServiceDetail,
  createServiceLifecycleSnapshot,
  createServiceUpdateReport,
  mergeManagedServiceDetail
} from "../types/services";

import { ServiceHealthCard } from "./ServiceHealthCard";
import { ServiceOverview } from "./ServiceOverview";

describe("Service Lifecycle presentation", () => {
  const snapshot = createServiceLifecycleSnapshot({
    services: [
      {
        identifier: "jellyfin",
        name: "Jellyfin",
        provider: "docker-compose",
        enabled: true
      },
      {
        identifier: "sonarr",
        name: "Sonarr",
        provider: "docker-compose",
        enabled: true
      }
    ],
    health: {
      status: "degraded",
      score: 75,
      total_services: 2,
      counts: {
        healthy: 1,
        degraded: 1,
        unhealthy: 0,
        unknown: 0
      },
      services: [
        {
          service: {
            identifier: "jellyfin",
            name: "Jellyfin",
            provider: "docker-compose",
            enabled: true
          },
          health: {
            status: "healthy",
            score: 100
          },
          requires_attention: false
        },
        {
          service: {
            identifier: "sonarr",
            name: "Sonarr",
            provider: "docker-compose",
            enabled: true
          },
          health: {
            status: "degraded",
            score: 50
          },
          requires_attention: true
        }
      ],
      evaluated_at: "2026-08-14T00:00:00Z"
    },
    summary: {
      provider: "docker-compose",
      compose_project: "project-atlas",
      total_services: 2,
      runtime_counts: {
        running: 2,
        stopped: 0,
        restarting: 0,
        failed: 0,
        unknown: 0
      },
      services: [
        {
          service: {
            identifier: "jellyfin",
            name: "Jellyfin",
            provider: "docker-compose",
            enabled: true
          },
          runtime: {
            state: "running",
            health: "healthy"
          },
          category: "running"
        },
        {
          service: {
            identifier: "sonarr",
            name: "Sonarr",
            provider: "docker-compose",
            enabled: true
          },
          runtime: {
            state: "running",
            health: "healthy"
          },
          category: "running"
        }
      ],
      evaluated_at: "2026-08-14T00:00:00Z"
    },
    updates: {
      status: "updates-available",
      provider: "docker-compose",
      total_services: 2,
      counts: {
        current: 1,
        "update-available": 1,
        "mutable-tag": 0,
        unknown: 0,
        unsupported: 0
      },
      requires_attention: true,
      attention: [
        {
          service_identifier: "sonarr",
          service_name: "Sonarr",
          status: "update-available"
        }
      ],
      updates: [
        {
          service_identifier: "jellyfin",
          service_name: "Jellyfin",
          status: "current",
          available_image: null,
          details: {
            registry_comparison: true
          }
        },
        {
          service_identifier: "sonarr",
          service_name: "Sonarr",
          status: "update-available",
          available_image: {
            repository: "lscr.io/linuxserver/sonarr",
            tag: "latest",
            digest: "sha256:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
          },
          details: {
            registry_comparison: true
          }
        }
      ],
      evaluated_at: "2026-08-14T00:00:00Z"
    }
  });

  it("normalizes production-shaped managed-service runtime and health entries", () => {
    expect(snapshot.services).toHaveLength(2);
    expect(snapshot.services[0]?.identifier).toBe("jellyfin");
    expect(snapshot.services[0]?.runtimeStatus).toBe("running");
    expect(snapshot.services[0]?.healthStatus).toBe("healthy");
    expect(snapshot.services[1]?.runtimeStatus).toBe("running");
    expect(snapshot.services[1]?.healthStatus).toBe("degraded");
    expect(snapshot.health.score).toBe(75);
    expect(snapshot.summary.composeProject).toBe("project-atlas");
    expect(snapshot.updates.totalServices).toBe(2);
    expect(snapshot.updates.current).toBe(1);
    expect(snapshot.updates.updateAvailable).toBe(1);
    expect(snapshot.updates.requiresAttention).toBe(true);
    expect(snapshot.updates.updates[0]?.status).toBe("current");
    expect(snapshot.updates.updates[1]?.status).toBe("update-available");
  });

  it("normalizes every canonical Update Discovery status", () => {
    const report = createServiceUpdateReport({
      status: "updates-available",
      provider: "docker-compose",
      total_services: 5,
      counts: {
        current: 1,
        "update-available": 1,
        "mutable-tag": 1,
        unknown: 1,
        unsupported: 1
      },
      requires_attention: true,
      updates: [
        {
          service_identifier: "jellyfin",
          service_name: "Jellyfin",
          status: "current"
        },
        {
          service_identifier: "sonarr",
          service_name: "Sonarr",
          status: "update-available"
        },
        {
          service_identifier: "radarr",
          service_name: "Radarr",
          status: "mutable-tag"
        },
        {
          service_identifier: "jellyseerr",
          service_name: "Jellyseerr",
          status: "unknown"
        },
        {
          service_identifier: "legacy",
          service_name: "Legacy",
          status: "unsupported"
        }
      ]
    });

    expect(report.updates.map((update) => update.status)).toEqual([
      "current",
      "update-available",
      "mutable-tag",
      "unknown",
      "unsupported"
    ]);
    expect(report.current).toBe(1);
    expect(report.updateAvailable).toBe(1);
    expect(report.mutableTag).toBe(1);
    expect(report.unknown).toBe(1);
    expect(report.unsupported).toBe(1);
  });

  it("preserves unavailable service-health status", () => {
    const service = createManagedService(
      {
        identifier: "prowlarr",
        name: "Prowlarr",
        provider: "docker-compose",
        enabled: true
      },
      {
        service: {
          identifier: "prowlarr"
        },
        runtime: {
          state: "exited"
        },
        category: "stopped"
      },
      {
        service: {
          identifier: "prowlarr"
        },
        health: {
          status: "unavailable"
        }
      }
    );

    expect(service.runtimeStatus).toBe("stopped");
    expect(service.healthStatus).toBe("unavailable");
  });

  it("renders aggregate lifecycle health", () => {
    const markup = renderToStaticMarkup(<ServiceHealthCard health={snapshot.health} />);

    expect(markup).toContain("Service health");
    expect(markup).toContain("degraded");
    expect(markup).toContain("75%");
    expect(markup).toContain("Total services");
  });

  it("renders managed-service cards with production-derived service state", () => {
    const markup = renderToStaticMarkup(
      <ServiceOverview
        onClearSelection={() => undefined}
        onSelectService={() => undefined}
        snapshot={snapshot}
      />
    );

    expect(markup).toContain("Managed services");
    expect(markup).toContain("Jellyfin");
    expect(markup).toContain("Sonarr");
    expect(markup).toContain("Runtime: running");
    expect(markup).toContain("Health: healthy");
    expect(markup).toContain("Health: degraded");
    expect(markup).toContain("Update availability");
    expect(markup).toContain("1 update available");
    expect(markup).toContain("Updates:");
    expect(markup).toContain("Current");
    expect(markup).toContain("Update available");
    expect(markup).toContain("View details");
    expect(markup).not.toContain(">Restart<");
    expect(markup).not.toContain(">Update service<");
    expect(markup).not.toContain(">Rollback<");
  });

  it("renders missing update observations as unknown", () => {
    const partialSnapshot = {
      ...snapshot,
      updates: {
        ...snapshot.updates,
        updates: []
      }
    };

    const markup = renderToStaticMarkup(
      <ServiceOverview
        onClearSelection={() => undefined}
        onSelectService={() => undefined}
        snapshot={partialSnapshot}
      />
    );

    expect(markup).toContain("Updates:");
    expect(markup).toContain("Unknown");
    expect(markup).not.toContain(">Update service<");
  });

  it("merges overview runtime and health into read-only service detail", () => {
    const detail = createManagedServiceDetail({
      identifier: "jellyfin",
      name: "Jellyfin",
      provider: "docker-compose",
      enabled: true,
      container_name: "jellyfin"
    });

    const merged = mergeManagedServiceDetail(detail, snapshot.services[0]);

    expect(merged.service.runtimeStatus).toBe("running");
    expect(merged.service.healthStatus).toBe("healthy");
    expect(merged.raw.container_name).toBe("jellyfin");
  });

  it("renders normalized service detail without mutation controls", () => {
    const detail = mergeManagedServiceDetail(
      createManagedServiceDetail({
        identifier: "jellyfin",
        name: "Jellyfin",
        provider: "docker-compose",
        enabled: true,
        container_name: "jellyfin"
      }),
      snapshot.services[0]
    );

    const markup = renderToStaticMarkup(
      <ServiceOverview
        detail={detail}
        onClearSelection={() => undefined}
        onSelectService={() => undefined}
        snapshot={snapshot}
      />
    );

    expect(markup).toContain("Read-only service detail");
    expect(markup).toContain("Jellyfin");
    expect(markup).toContain("docker-compose");
    expect(markup).toContain("Runtime: running");
    expect(markup).toContain("Health: healthy");
    expect(markup).toContain("container name");
    expect(markup).toContain("Close details");
    expect(markup).not.toContain(">Restart<");
    expect(markup).not.toContain(">Rollback<");
  });

  it("renders detail loading and failure states accessibly", () => {
    const loadingMarkup = renderToStaticMarkup(
      <ServiceOverview
        detailIdentifier="jellyfin"
        detailLoading
        onClearSelection={() => undefined}
        onSelectService={() => undefined}
        snapshot={snapshot}
      />
    );

    expect(loadingMarkup).toContain("Loading service details");

    const errorMarkup = renderToStaticMarkup(
      <ServiceOverview
        detailError="Service Lifecycle is unavailable."
        detailIdentifier="jellyfin"
        onClearSelection={() => undefined}
        onSelectService={() => undefined}
        snapshot={snapshot}
      />
    );

    expect(errorMarkup).toContain('role="alert"');
    expect(errorMarkup).toContain("Service Lifecycle is unavailable.");
  });
});
