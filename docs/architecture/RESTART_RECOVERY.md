# Restart Recovery Architecture

## Purpose

Restart Recovery is the provider-independent Service Lifecycle capability that
compares normalized observations from before and after a service restart and
reports whether the service recovered safely.

The capability observes and evaluates recovery. It does not start, stop,
restart, recreate, or otherwise modify services.

## Motivation

A configured restart policy does not prove that a service recovered.

After a restart, a container can be running while its application remains
unhealthy, its dependencies are unavailable, its security boundary is not
ready, or its runtime evidence is contradictory.

Atlas therefore requires an explicit comparison between two normalized
observations instead of treating process startup as proof of recovery.

## Responsibility Boundary

The responsibility flow is:

```text
Infrastructure provider
        |
        v
Service Lifecycle provider adapter
        |
        v
Normalized before and after observations
        |
        v
Restart Recovery evaluator
        |
        v
Restart Recovery result
        |
        +--> CLI reporting
        +--> Root Verify orchestration
        +--> Future API and Portal consumers
```

Providers expose runtime and health facts. Service Lifecycle normalizes those
facts. Restart Recovery compares normalized observations. Consumers render the
result and must not duplicate provider-specific recovery logic.

## Planned Contracts

### `ServiceRecoveryObservation`

Represents one immutable observation of a managed service:

- managed-service identity;
- normalized `ServiceRuntime`;
- normalized `ServiceHealth`;
- observation timestamp.

### `ServiceRecoveryStatus`

The normalized recovery states are:

- `not-observed`;
- `recovering`;
- `recovered`;
- `degraded`;
- `failed`;
- `unknown`.

### `ServiceRecoveryResult`

Represents one deterministic comparison:

- before and after observations;
- whether restart evidence was observed;
- restart-count delta;
- normalized recovery status;
- explanation;
- warnings and errors;
- evaluation timestamp.

### `RestartRecoveryEvaluator`

Consumes exactly two normalized observations and returns one recovery result.
The evaluator is pure: it does not call Docker, execute shell commands, read
Compose configuration, or mutate infrastructure.

## Evaluation Rules

A restart is observed when the restart count increases or the normalized start
timestamp advances consistently with a new runtime.

A service is recovered when:

- restart evidence is present;
- the current runtime is running;
- current health is explicitly Healthy;
- the current health contract contains no errors.

Other results are conservative:

- `recovering` when the current runtime is restarting or health is starting;
- `degraded` when the service is running after restart but health is degraded;
- `failed` when the current service is stopped, dead, unavailable, unhealthy,
  or error-bearing;
- `not-observed` when no restart evidence exists;
- `unknown` when required evidence is unavailable or contradictory.

## Existing Contracts Reused

Restart Recovery reuses existing Atlas contracts and facts:

- `ManagedService` identity;
- `ServiceRuntime` state, restart count, timestamps, and exit code;
- `ServiceHealth` status, warnings, errors, and evaluation timestamp;
- Docker provider runtime normalization;
- Operations restart, health, OOM, and exit-code observations;
- immutable Operations history and comparison infrastructure.

It does not create a parallel runtime provider, health engine, persistence
system, or root verification framework.

## Interface Ownership

Service Lifecycle owns recovery contracts and evaluation.

Operations may consume recovery results for historical reporting. Root Verify
may orchestrate the completed read-only capability. CLI, API, and Portal
interfaces consume normalized results.

## Live Validation Safety

Live validation is a separate controlled step. No production service may be
restarted until Atlas has:

- selected the exact service;
- reviewed its dependencies and network relationships;
- captured the before observation;
- defined the expected recovery state and timeout;
- defined a rollback procedure;
- received explicit operator approval.

## Non-Goals

Restart Recovery does not:

- execute service restarts;
- start or stop containers;
- recreate services;
- replace Docker restart policies or health checks;
- infer recovery from process startup alone;
- become an orchestration engine;
- introduce infrastructure mutation into Atlas v1.0.

## Delivery Sequence

1. Architecture document and ADR.
2. Recovery models and dedicated tests.
3. Pure evaluator and dedicated tests.
4. Read-only orchestration service.
5. Human and JSON CLI integration.
6. Controlled live validation.
7. Documentation reconciliation and completion checkpoint.

## Related Documents

- [Service Lifecycle Architecture](SERVICE_LIFECYCLE.md)
- [Startup Policy Architecture](STARTUP_POLICY.md)
- [ADR 0010 — Service Lifecycle Architecture](../ADR/0010-service-lifecycle-architecture.md)
- [ADR 0011 — Startup Policy Readiness Contracts](../ADR/0011-startup-policy-readiness-contracts.md)
- [ADR 0012 — Restart Recovery Observation Contracts](../ADR/0012-restart-recovery-observation-contracts.md)
