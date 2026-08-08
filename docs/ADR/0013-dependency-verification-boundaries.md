# ADR-0013: Dependency Verification Boundaries

## Status

Accepted

## Date

2026-08-05

## Context

Project Atlas already normalizes Docker Compose dependencies, builds a
bidirectional Service Lifecycle graph, reports unresolved relationships, and
uses Service Doctor to identify missing or non-running dependencies. Startup
Policy separately evaluates readiness conditions.

The roadmap still describes the graph and CLI as future work, and the existing
graph contracts predate the current Atlas model standard. Adding another
dependency evaluator would duplicate mature behavior and create competing
sources of truth.

## Decision

Atlas adopts the existing dependency graph, Service Doctor, and Startup Policy
as the permanent Service Dependency Verification boundaries.

- Providers expose normalized configuration and runtime facts.
- The dependency graph owns topology only.
- Service Doctor owns current missing and non-running dependency findings.
- Startup Policy owns startup readiness conditions.
- Consumers render these contracts without duplicating their logic.

M-023.15 will harden and publicly export the existing graph contracts, add a
dedicated model suite, validate production behavior, and reconcile stale
documentation. It will not add a parallel evaluator or provider method.

## Model Contract

`ServiceDependencyNode` represents one managed service together with resolved
dependencies, reverse dependents, and unresolved dependency identifiers.

`InfrastructureDependencyGraph` represents the deterministic aggregate graph,
including roots, standalone services, unresolved nodes, provider identity,
Compose project identity, edge count, and evaluation time.

Both public models must normalize inputs, validate identity and child
contracts, normalize timestamps, serialize deterministically, have dedicated
tests, and be exported from `atlas.service_lifecycle`.

## Consequences

Positive consequences:

- existing implementation is extended rather than replaced;
- topology, operational diagnosis, and readiness remain independently testable;
- provider-specific configuration stays behind the adapter boundary;
- CLI, API, Portal, Verify, and Operations consumers can share stable models;
- Atlas avoids unnecessary architecture and migration risk.

Tradeoffs:

- dependency verification spans three cooperating read-only capabilities;
- undeclared application relationships remain invisible until modeled;
- missing health checks limit readiness evidence but do not invalidate topology;
- dependency-aware ordering remains deferred.

## Non-Goals

This decision does not authorize service mutation, automatic remediation,
dependency-aware update ordering, inferred relationships, or replacement of
Docker Compose semantics. It does not merge Service Doctor or Startup Policy
into the graph.

## Related Documents

- [Service Dependency Verification Architecture](../architecture/SERVICE_DEPENDENCY_VERIFICATION.md)
- [Service Lifecycle Architecture](../architecture/SERVICE_LIFECYCLE.md)
- [Startup Policy Architecture](../architecture/STARTUP_POLICY.md)
- [ADR 0010](0010-service-lifecycle-architecture.md)
- [ADR 0011](0011-startup-policy-readiness-contracts.md)
- [ADR 0012](0012-restart-recovery-observation-contracts.md)
