# Service Dependency Verification Architecture

## Purpose

Service Dependency Verification is the read-only Service Lifecycle capability
that exposes declared service relationships and verifies whether their current
operational facts are safe and explainable.

The capability reuses the dependency graph, Service Doctor, and Startup Policy
boundaries already implemented in Atlas. It does not introduce a parallel
provider, graph engine, or dependency evaluator.

## Motivation

Docker Compose declares service relationships through `depends_on` and, in
some cases, namespace sharing such as `network_mode: service:<identifier>`.
Atlas must distinguish three questions:

1. What dependency topology is declared?
2. Are declared dependencies present and currently running?
3. Does startup configuration require a stronger readiness condition?

Combining these questions in one provider-specific check would duplicate
existing contracts and blur responsibility boundaries. Atlas instead keeps
topology, operational diagnosis, and startup readiness separate while making
their results available through one Service Lifecycle interface.

## Existing Implementation

The repository already provides:

- Docker Compose `depends_on` normalization;
- normalized dependency identifiers on `ManagedService`;
- `ServiceDependencyNode` forward, reverse, and unresolved relationships;
- `InfrastructureDependencyGraph` aggregate topology;
- `ServiceLifecycleService.inspect_graph()`;
- human-readable and JSON `atlas service graph` reporting;
- Service Doctor findings for unknown and non-running dependencies;
- Startup Policy contracts for `service_started`, `service_healthy`, and
  `service_completed_successfully` readiness conditions;
- provider, model, service, Doctor, and CLI coverage.

M-023.15 therefore hardens and validates the existing capability rather than
replacing it.

## Responsibility Boundary

### Provider adapter

The Docker Compose provider translates infrastructure configuration into
normalized service identities and startup contracts. It exposes facts and does
not decide whether the overall dependency state is acceptable.

### Dependency graph

The graph owns topology:

- configured services;
- direct dependencies;
- reverse dependents;
- unresolved dependency identifiers;
- aggregate roots, standalone services, and edge count.

The graph does not inspect runtime health or assign operational severity.

### Service Doctor

Service Doctor owns current operational findings:

- a declared dependency is missing;
- a required dependency is present but not running.

Doctor consumes normalized service and runtime contracts. It does not parse
Compose configuration directly.

### Startup Policy

Startup Policy owns readiness strength and startup semantics. It evaluates
whether Compose expresses the required condition, such as qBittorrent waiting
for Gluetun to become Healthy.

Startup Policy does not replace the dependency graph or diagnose current
runtime state.

### Consumers

The CLI, Root Verify, API, Portal, Operations, and future guarded automation
consume normalized contracts. Consumers must not reconstruct topology or
duplicate dependency rules.

## Contract Hardening

M-023.15 will bring the existing graph contracts fully in line with the Atlas
Engineering Charter.

Every public graph model must:

- normalize accepted collection inputs;
- validate service identity and child contracts;
- reject duplicate and self-referential relationships;
- normalize unresolved identifiers deterministically;
- normalize timestamps to UTC;
- provide deterministic `to_dict()` serialization;
- have a dedicated test suite;
- be exported through `atlas.service_lifecycle`.

Compatibility imports through the existing lifecycle service module remain
available.

## Verification Rules

Dependency Verification is successful when:

- every declared dependency resolves to one managed service;
- graph relationships are internally consistent;
- enabled services do not depend on stopped or failed services;
- stronger readiness requirements remain owned and satisfied by Startup
  Policy;
- human and JSON interfaces render the same normalized facts;
- the production graph and Doctor report contain no dependency findings.

Services without declared dependencies are valid standalone nodes. Services
without Docker health checks may be operationally degraded elsewhere, but the
graph must not invent readiness evidence. Health-check coverage remains a
separate observability concern.

## Production Relationships

The current Compose contract includes relationships such as:

- qBittorrent depending on Gluetun;
- Jellyseerr depending on Jellyfin, Sonarr, and Radarr;
- Maintainerr depending on Jellyfin, Sonarr, and Radarr;
- Tautulli depending on Jellyfin;
- Unpackerr depending on Sonarr and Radarr;
- Recyclarr depending on Sonarr and Radarr.

The repository remains the source of truth. Live validation must derive the
actual graph from the active Compose configuration rather than hard-code this
inventory into domain logic.

## Non-Goals

Service Dependency Verification does not:

- start, stop, restart, or reorder services;
- add automatic remediation;
- replace Docker Compose dependency semantics;
- replace Startup Policy readiness evaluation;
- require health checks where none are configured;
- infer undeclared application-level relationships;
- add dependency-aware update ordering;
- introduce infrastructure mutation into Atlas v1.0.

## Delivery Sequence

1. Architecture document and ADR 0013.
2. Public graph-contract normalization and exports.
3. Dedicated dependency-model tests.
4. Focused graph, Doctor, Startup Policy, and CLI regression validation.
5. Human and JSON production graph validation.
6. Roadmap and completion documentation reconciliation.

## Related Documents

- [Service Lifecycle Architecture](SERVICE_LIFECYCLE.md)
- [Startup Policy Architecture](STARTUP_POLICY.md)
- [Restart Recovery Architecture](RESTART_RECOVERY.md)
- [Service Lifecycle CLI Reference](../cli/SERVICE_LIFECYCLE.md)
- [Service Lifecycle Python API](../api/SERVICE_LIFECYCLE.md)
- [ADR 0010 — Service Lifecycle Architecture](../ADR/0010-service-lifecycle-architecture.md)
- [ADR 0011 — Startup Policy Readiness Contracts](../ADR/0011-startup-policy-readiness-contracts.md)
- [ADR 0013 — Dependency Verification Boundaries](../ADR/0013-dependency-verification-boundaries.md)
