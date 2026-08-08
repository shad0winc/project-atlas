# Service Lifecycle Python API

## Public import surface

The canonical public API is exported through:

```python
from atlas.service_lifecycle import (
    DockerComposeProvider,
    InfrastructureDependencyGraph,
    ManagedService,
    ServiceDependencyNode,
    ServiceDoctor,
    ServiceLifecycleProvider,
    ServiceLifecycleService,
    ServiceMaintenanceHistoryService,
    ServiceRecoveryObservation,
    ServiceRecoveryResult,
    ServiceRecoveryStatus,
    ServiceRestartRecoveryService,
    ServiceStartupContract,
    ServiceStartupDependency,
    ServiceStartupPolicyService,
    ServiceUpdateService,
    StartupDependencyCondition,
    StartupPolicyEvaluator,
    StartupPolicyFinding,
    StartupPolicyReport,
    StartupPolicySeverity,
)
```

Domain models, reports, enums, and normalized errors are also exported through
`atlas.service_lifecycle`.

## Layering

```text
Presentation
├── CLI
├── Future REST API
└── Administration Portal
        │
        ▼
Services
├── ServiceLifecycleService
├── ServiceDoctor
├── ServiceUpdateService
├── ServiceMaintenanceHistoryService
├── ServiceStartupPolicyService
└── ServiceRestartRecoveryService
        │
        ▼
ServiceLifecycleProvider
        │
        ▼
DockerComposeProvider
```

Presentation layers must reuse service contracts instead of implementing
provider or business logic.

## Core service

### `ServiceLifecycleService`

Responsibilities include:

- managed-service inventory;
- service identity inspection;
- runtime inspection;
- service and aggregate health;
- infrastructure summary;
- dependency graph;
- provider error translation;
- normalized contract validation.

## Dependency Graph

### `ServiceLifecycleService.inspect_graph()`

Returns one deterministic `InfrastructureDependencyGraph` containing every
managed service, its resolved dependencies, reverse dependents, unresolved
dependency identifiers, roots, standalone services, and aggregate edge count.

`ServiceDependencyNode` and `InfrastructureDependencyGraph` are canonical
public contracts exported through `atlas.service_lifecycle`. Compatibility
imports through `atlas.service_lifecycle.services.lifecycle` resolve to the
same class identities.

The graph owns topology only. Service Doctor owns current missing or
non-running dependency findings, while Startup Policy owns readiness strength
and startup conditions. None of these boundaries mutates infrastructure.

## Service Doctor

### `ServiceDoctor`

Produces a canonical `DoctorReport` from read-only lifecycle observations.

It does not repair services or mutate infrastructure.

## Update Discovery

### `ServiceUpdateService.inspect_update(identifier)`

Returns one validated `ServiceUpdate`.

### `ServiceUpdateService.inspect_updates()`

Returns one deterministic `UpdateReport`.

The service validates provider result types, service identity, and service name.
It preserves known Atlas domain errors and translates unexpected provider
failures.

## Maintenance History

### `ServiceMaintenanceHistoryService.inspect_history()`

Returns one validated global `MaintenanceReport`.

### `ServiceMaintenanceHistoryService.inspect_service_history(identifier)`

Returns one validated service-specific `MaintenanceReport`.

Service-specific records must match the requested normalized service identity
and name.

## Startup Policy

`ServiceStartupPolicyService.inspect()` requests normalized startup contracts
from a capable provider, validates the collection and child contracts, and
returns one deterministic `StartupPolicyReport`.

`StartupPolicyEvaluator.evaluate(contracts)` evaluates normalized contracts
without invoking Docker or modifying infrastructure.

`DockerComposeProvider.inspect_startup_contracts()` is the current optional
provider capability. Providers without it remain backward compatible.

## Restart Recovery

### `ServiceRestartRecoveryService.observe(identifier)`

Returns one validated `ServiceRecoveryObservation` assembled from normalized
service identity, runtime, and health contracts.

### `ServiceRestartRecoveryService.evaluate(before, after)`

Delegates two validated observations to `RestartRecoveryEvaluator` and returns
one deterministic `ServiceRecoveryResult`.

### `ServiceRestartRecoveryService.inspect(identifier, before)`

Captures the current after observation and evaluates it against the supplied
before observation. It does not start, stop, or restart the service.

`RestartRecoveryEvaluator.evaluate(before, after)` is pure and
provider-independent. Existing `ServiceRuntime` fields provide restart count,
start and finish timestamps, exit code, runtime state, health state, and status
message; no parallel provider API is required.

## Provider contract

### Required provider methods

```python
list_services()
inspect_service(identifier)
inspect_runtime(identifier)
inspect_health(identifier)
inspect_update(identifier)
```

### Maintenance History defaults

```python
inspect_history()
inspect_service_history(identifier)
```

Maintenance History methods have concrete empty-report defaults so providers
without persistence remain backward compatible.

## Canonical model contracts

### Core

- `ManagedService`
- `ServiceImage`
- `ServiceRuntime`
- `ServiceHealth`
- `InfrastructureHealthReport`
- `InfrastructureSummary`

### Dependency Graph

- `ServiceDependencyNode`
- `InfrastructureDependencyGraph`

### Doctor

- `DoctorSeverity`
- `DoctorCategory`
- `DoctorFinding`
- `DoctorReport`

### Update Discovery

- `UpdateStatus`
- `ImageReference`
- `ServiceUpdate`
- `UpdateReport`

### Maintenance History

- `MaintenanceAction`
- `MaintenanceResult`
- `MaintenanceRecord`
- `MaintenanceReport`

### Startup Policy

- `StartupDependencyCondition`
- `ServiceStartupDependency`
- `ServiceStartupContract`
- `StartupPolicySeverity`
- `StartupPolicyFinding`
- `StartupPolicyReport`

### Restart Recovery

- `ServiceRecoveryObservation`
- `ServiceRecoveryStatus`
- `ServiceRecoveryResult`

All public models normalize inputs, validate identity and child contracts,
normalize timestamps, and provide deterministic `to_dict()` serialization.

## Compatibility module paths

Canonical service implementations live under:

```text
atlas.service_lifecycle.services
```

Legacy module paths remain true aliases:

```text
atlas.service_lifecycle.service
atlas.service_lifecycle.doctor
atlas.service_lifecycle.update
atlas.service_lifecycle.maintenance
```

This preserves imports, module identity, monkeypatch targets, and module-level
state during incremental migration.

## Error behavior

Public Service Lifecycle operations raise `ServiceLifecycleError` or a
documented subtype for normalized domain failures.

Known Atlas errors are preserved. Unexpected provider failures are translated
at the service boundary.

## Read-only v1.0 boundary

The v1.0 Service Lifecycle API does not expose pull, restart, stop, start,
recreate, update, rollback, or other infrastructure mutations.

Write operations are reserved for post-v1.0 validated abstractions and safety
workflows.
