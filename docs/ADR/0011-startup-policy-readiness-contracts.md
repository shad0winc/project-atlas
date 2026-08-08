
# ADR-0011: Startup Policy Readiness Contracts
## Status

Accepted

## Date

2026-08-04

## Context

Project Atlas Service Lifecycle management requires a deterministic way to
evaluate whether services are ready for dependent operations.

Container startup ordering alone does not guarantee operational readiness.

A service may have a running container while still waiting for:

application initialization;
dependency availability;
network readiness;
external provider connectivity;
security boundary establishment.

Historically, readiness assumptions can become embedded inside provider-specific
logic or individual consumers. This creates duplicated checks, inconsistent
behavior, and reduced observability.

Project Atlas requires a provider-independent evaluation layer that can consume
normalized Service Lifecycle contracts and report readiness state consistently.

## Decision

Project Atlas introduces Startup Policy as an evaluation boundary within the
Service Lifecycle architecture.

Startup Policy evaluates normalized startup contracts and produces deterministic
readiness results.

The responsibility flow is:


Infrastructure provider
        |
        v
Service Lifecycle provider adapter
        |
        v
Normalized startup contracts
        |
        v
Startup Policy evaluator
        |
        v
Startup Policy result models

Providers are responsible for collecting infrastructure facts.

Service Lifecycle is responsible for normalizing provider-specific information
into stable domain contracts.

Startup Policy is responsible for evaluating those contracts against defined
readiness expectations.

Consumers such as CLI, API, and Portal interfaces consume Startup Policy
results and do not implement provider-specific readiness logic.

## Readiness Contract Model

Startup Policy evaluates explicit readiness contracts rather than assuming that
service process startup represents availability.

A readiness contract describes the expected conditions required before a service
is considered ready for dependent operations.

Examples include:

- dependency health state;
- required startup ordering;
- required provider availability;
- protected network boundaries;
- service lifecycle dependency conditions.

The contract model allows different infrastructure providers to expose a common
evaluation interface.

## Consequences

Positive consequences:

- Startup readiness becomes observable and deterministic.
- Provider-specific logic remains isolated.
- Consumers receive consistent readiness information.
- Future providers can implement lifecycle contracts without changing consumers.
- Automation can make decisions using evaluated policy results.

Tradeoffs:

- Additional contract definitions must be maintained.
- Providers must correctly expose lifecycle information.
- Readiness evaluation requires explicit modeling instead of implicit assumptions.
## Non-Goals

Startup Policy is not responsible for:

starting services;
stopping services;
restarting services;
modifying infrastructure configuration;
editing Docker Compose definitions;
replacing provider health checks;
becoming an orchestration engine.

Startup Policy evaluates state. It does not control state.

## Related Documents

- Service Lifecycle Architecture
- Startup Policy Architecture
- Service Lifecycle CLI Reference
- Service Lifecycle API Reference
- ADR-0010: Service Lifecycle Architecture
