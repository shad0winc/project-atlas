# Startup Policy Architecture

## Purpose

Startup Policy is the provider-independent Service Lifecycle capability that
evaluates whether configured service dependencies provide explicit and safe
startup-readiness guarantees.

Startup Policy observes infrastructure state and produces deterministic policy
results.

It does not directly start, stop, restart, recreate, or modify services.

## Motivation

Container startup does not guarantee dependency readiness.

A dependency can have a running container while still lacking:

- application initialization;
- a reachable service endpoint;
- a healthy backend dependency;
- a ready VPN tunnel;
- a valid security boundary;
- a required external provider connection.

Startup Policy closes the gap between:

dependency container started

and:

dependency is ready for dependent services

The policy layer allows Atlas to evaluate readiness expectations explicitly
rather than assuming that process startup represents operational availability.


## Architectural Boundary

Startup Policy extends the Service Lifecycle architecture by introducing a
dedicated evaluation boundary between infrastructure discovery and consumer
interfaces.

The responsibility flow is:

```text
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
        |
        +--> CLI reporting
        +--> API consumers
        +--> Portal consumers
```

The provider layer is responsible for collecting infrastructure facts.

The Service Lifecycle layer is responsible for normalizing provider-specific
information into stable domain contracts.

Startup Policy is responsible for evaluating those contracts against defined
readiness expectations.

User interfaces and automation consumers consume Startup Policy results and
must not duplicate provider-specific readiness logic.

