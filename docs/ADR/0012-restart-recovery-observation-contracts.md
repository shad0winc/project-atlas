# ADR-0012: Restart Recovery Observation Contracts

## Status

Accepted

## Date

2026-08-05

## Context

Project Atlas records runtime state, health, restart counts, timestamps, exit
codes, OOM state, and restart-loop findings. These facts describe current or
historical infrastructure state, but they do not provide one explicit contract
for determining whether a service recovered after a restart.

Process startup alone is insufficient evidence. A restarted container may be
running while the application is unhealthy, a dependency is unavailable, or a
required security boundary is not ready.

Recovery logic embedded separately in providers, CLI commands, Operations, or
Root Verify would duplicate business rules and produce inconsistent results.

## Decision

Atlas introduces Restart Recovery as a read-only evaluation capability within
Service Lifecycle.

Providers expose facts. Service Lifecycle normalizes before and after
observations. A pure `RestartRecoveryEvaluator` compares those observations and
returns one deterministic `ServiceRecoveryResult`.

The evaluator does not access Docker or mutate infrastructure.

## Contract Model

`ServiceRecoveryObservation` pairs stable service identity with normalized
runtime, health, and observation time.

`ServiceRecoveryStatus` provides conservative normalized outcomes:
`not-observed`, `recovering`, `recovered`, `degraded`, `failed`, and `unknown`.

`ServiceRecoveryResult` records restart evidence, restart-count delta, status,
explanation, warnings, errors, and evaluation time.

All models follow Atlas standards: input normalization, identity and child
validation, UTC timestamp normalization, deterministic serialization, package
exports, and dedicated tests.

## Recovery Evidence

Restart evidence is present when restart count increases or the normalized
start timestamp advances consistently with a new runtime.

Recovery requires explicit current running and Healthy state without health
errors. Missing, contradictory, degraded, restarting, unavailable, unhealthy,
or failed evidence produces a conservative non-recovered result.

## Consequences

Positive consequences:

- recovery becomes observable, deterministic, and explainable;
- provider-specific behavior remains isolated;
- CLI, Verify, Operations, API, and Portal consumers can share one contract;
- automated decisions can be added later without duplicating evaluation logic;
- v1.0 remains read-only.

Tradeoffs:

- evaluation requires two trustworthy observations;
- live validation requires a controlled operator-approved restart;
- restart-count resets or missing timestamps may produce Unknown rather than a
  speculative result.

## Non-Goals

Restart Recovery does not start, stop, restart, recreate, repair, or modify
services. It does not replace provider health checks, restart policies, Startup
Policy, or Operations history. It is not an orchestration engine.

## Related Documents

- [Restart Recovery Architecture](../architecture/RESTART_RECOVERY.md)
- [Service Lifecycle Architecture](../architecture/SERVICE_LIFECYCLE.md)
- [Startup Policy Architecture](../architecture/STARTUP_POLICY.md)
- [ADR 0010](0010-service-lifecycle-architecture.md)
- [ADR 0011](0011-startup-policy-readiness-contracts.md)
