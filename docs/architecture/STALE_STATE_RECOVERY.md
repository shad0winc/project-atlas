# Stale-State Recovery Architecture

## Purpose

Stale-State Recovery ensures that Atlas does not present facts from an earlier
runtime lifecycle as if they describe a service's current lifecycle.

M-023.16 addresses a concrete Docker runtime inconsistency: Docker can retain a
container's previous `FinishedAt` timestamp after that container has started a
new running lifecycle. The timestamp is syntactically valid, but it is no
longer a current finish time.

Atlas normalizes that provider-specific stale fact at the provider boundary.
It does not introduce a general stale-state engine, universal time-to-live
policy, or infrastructure mutation workflow.

## Motivation

Atlas already consumes Docker runtime timestamps through multiple read-only
boundaries. Discovery established that:

- the Operations Docker provider already suppresses `finished_at` for running
  containers;
- the Service Lifecycle Docker Compose provider currently normalizes
  `FinishedAt` without considering whether the container is running;
- production Restart Recovery observations have therefore exposed a running
  service with an old `finished_at` value from its previous lifecycle.

That inconsistency weakens explainability. A consumer should not need Docker
implementation knowledge to decide whether a normalized timestamp is current.

## Runtime Lifecycle Invariant

The normalized contract follows one simple rule:

| Runtime condition | Normalized `finished_at` |
| --- | --- |
| Running | `None` |
| Restarting | `None` |
| Stopped or terminal | Preserve valid Docker `FinishedAt` |
| Docker zero timestamp | `None` |
| Invalid non-zero timestamp | Provider error |

A current lifecycle is either active or finished. Atlas must not represent it
as both at the same time.

The `started_at` timestamp remains required evidence for a running lifecycle
where the provider exposes it. Restart Recovery continues to use start-time
advancement and restart-count evidence without treating stale finish metadata
as a restart signal.

## Responsibility Boundary

### Docker provider

The provider owns translation of Docker-specific lifecycle facts. It knows
whether Docker reports the container as running and therefore owns removal of
a stale `FinishedAt` value before constructing `ServiceRuntime`.

The provider must continue to:

- normalize valid timestamps to UTC;
- map Docker zero timestamps to no observation;
- preserve valid finish timestamps for terminal lifecycles;
- reject malformed non-zero timestamps;
- expose no mutation behavior.

### ServiceRuntime

`ServiceRuntime` remains the provider-independent public contract. It validates
normalized timestamp syntax but does not learn Docker-specific lifecycle
quirks. This keeps the domain model reusable across future providers.

### Restart Recovery

Restart Recovery consumes normalized `ServiceRuntime` observations. It does not
repair Docker state and does not duplicate provider normalization rules.

### Operations

The Operations Docker adapter already follows the active-lifecycle invariant.
M-023.16 preserves that behavior and adds cross-boundary regression coverage so
the two Docker observation paths remain consistent.

## Definition of Stale for M-023.16

For this milestone, stale state is deliberately narrow:

> A previous Docker lifecycle's finish timestamp is stale when the current
> container lifecycle is active.

This definition is evidence-based and does not depend on elapsed wall-clock
time. Atlas does not infer staleness merely because a record is old.

Other forms of recovery remain separately owned:

- stale Scheduler runtime locks and task recovery belong to Scheduler Recovery;
- interrupted media requests belong to Interrupted-Request Recovery;
- recorder process reconciliation belongs to Sports Recovery;
- persisted Operations snapshots remain immutable historical observations and
  retain their explicit generation timestamps.

## Verification Requirements

M-023.16 is complete when:

- running Docker Compose services normalize `finished_at` to `None`;
- restarting services normalize `finished_at` to `None`;
- stopped services preserve a valid terminal finish timestamp;
- Docker zero timestamps continue to normalize to `None`;
- invalid non-zero timestamps remain explicit provider errors;
- Operations and Service Lifecycle agree on active-lifecycle finish semantics;
- Restart Recovery and Service Doctor regressions pass;
- live production inspection shows no running service with a non-null
  `finished_at`;
- validation performs no infrastructure mutation.

## Non-Goals

M-023.16 does not:

- restart, stop, start, or recreate containers;
- rewrite Docker metadata;
- delete persisted state;
- add background remediation;
- introduce a generic stale-state registry;
- define a universal freshness TTL;
- change Scheduler lock handling;
- recover interrupted media requests;
- change Sports recorder recovery;
- infer service health from timestamp age.

## Delivery Sequence

1. Architecture document and ADR 0014.
2. Service Lifecycle Docker provider normalization hardening.
3. Focused provider and lifecycle tests.
4. Restart Recovery, Doctor, and Operations regression validation.
5. Read-only production runtime validation.
6. Roadmap and completion documentation reconciliation.

## Production Validation

Completed against the active Docker Compose environment after implementation
at commit `9dea5c88`.

Automated evidence:

- five focused stale-state provider tests passed;
- all 225 Docker Compose provider tests passed;
- all 64 Restart Recovery tests passed;
- all 33 Service Doctor tests passed;
- all 56 Operations Docker provider tests passed;
- 378 distinct tests passed across the authoritative regression suites, with
  the five focused stale-state cases also run separately;
- Python compilation and Git diff hygiene passed.

Production evidence:

- 15 managed services were inspected through the Service Lifecycle CLI;
- all 15 services were in active `running` lifecycles;
- every active service exposed `finished_at: null`;
- stale active finish-timestamp violations: zero;
- a Jellyfin Restart Recovery observation consumed the same normalized
  `finished_at: null` runtime contract;
- no service was started, stopped, restarted, or recreated;
- validation introduced no repository mutation beyond the implementation under
  review.

## Completion State

M-023.16 is complete. Service Lifecycle and Operations now agree that an
active Docker lifecycle has no current finish timestamp. Valid terminal finish
timestamps and invalid-timestamp rejection remain intact, and all later
recovery domains retain their independent milestone boundaries.

## Related Documents

- [Service Lifecycle Architecture](SERVICE_LIFECYCLE.md)
- [Restart Recovery Architecture](RESTART_RECOVERY.md)
- [Service Dependency Verification](SERVICE_DEPENDENCY_VERIFICATION.md)
- [ADR 0010 — Service Lifecycle Architecture](../ADR/0010-service-lifecycle-architecture.md)
- [ADR 0012 — Restart Recovery Observation Contracts](../ADR/0012-restart-recovery-observation-contracts.md)
- [ADR 0014 — Stale Runtime State Normalization](../ADR/0014-stale-runtime-state-normalization.md)
