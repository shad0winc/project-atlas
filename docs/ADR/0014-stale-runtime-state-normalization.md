# ADR-0014: Stale Runtime State Normalization

## Status

Accepted

## Date

2026-08-05

## Context

Docker can expose a valid `FinishedAt` timestamp from a container's previous
lifecycle while that container is currently running. Atlas Operations already
suppresses that stale timestamp for active containers, but the Service
Lifecycle Docker Compose provider currently passes the timestamp through to
`ServiceRuntime`.

Production Restart Recovery observations demonstrated the inconsistency: the
same running service can expose a current `StartedAt` together with an older
`FinishedAt` from the prior lifecycle.

The value is valid Docker history but invalid as a normalized fact about the
current active lifecycle.

## Decision

Atlas will normalize active Docker lifecycle finish timestamps at the provider
boundary.

- Running and restarting containers expose `finished_at=None`.
- Stopped and terminal containers preserve a valid Docker `FinishedAt` value.
- Docker zero timestamps continue to normalize to `None`.
- Invalid non-zero timestamps remain explicit provider errors.
- `ServiceRuntime` remains provider-independent and does not encode Docker
  quirks.
- Restart Recovery, Doctor, CLI, API, and future consumers use the normalized
  contract without reconstructing this rule.

The rule is semantic rather than age-based. Atlas will not add a universal TTL
or generic stale-state engine for M-023.16.

## Rationale

Provider normalization is the smallest correct boundary because only the
provider can interpret Docker's lifecycle-specific timestamp semantics without
leaking Docker behavior into domain models or consumers.

The decision also aligns Service Lifecycle with the established Operations
Docker adapter and preserves Atlas's provider-normalization principle:
providers expose normalized facts; domain services consume contracts.

## Consequences

Positive consequences:

- active Service Lifecycle observations no longer expose contradictory finish
  state;
- Restart Recovery receives cleaner lifecycle evidence;
- Operations and Service Lifecycle agree on Docker active-lifecycle semantics;
- no public model or consumer compatibility break is required;
- no infrastructure mutation is introduced.

Tradeoffs:

- the previous lifecycle's finish time is intentionally unavailable through a
  current running `ServiceRuntime` observation;
- consumers needing historical lifecycle events require a separate history
  contract rather than overloading current runtime state;
- other stale-state domains remain independently scoped.

## Non-Goals

This decision does not define Scheduler recovery, interrupted-request recovery,
Sports recovery, state-file repair, snapshot expiration, automatic remediation,
or service mutation.

## Related Documents

- [Stale-State Recovery Architecture](../architecture/STALE_STATE_RECOVERY.md)
- [Service Lifecycle Architecture](../architecture/SERVICE_LIFECYCLE.md)
- [Restart Recovery Architecture](../architecture/RESTART_RECOVERY.md)
- [ADR 0010 — Service Lifecycle Architecture](0010-service-lifecycle-architecture.md)
- [ADR 0012 — Restart Recovery Observation Contracts](0012-restart-recovery-observation-contracts.md)
