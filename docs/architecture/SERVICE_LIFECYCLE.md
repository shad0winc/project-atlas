# Service Lifecycle Architecture

## Purpose

Service Lifecycle is the Project Atlas Core domain for discovering, inspecting,
reporting, and eventually maintaining Atlas-managed infrastructure services. It
provides one normalized boundary that can be consumed by the Atlas CLI, Atlas
API, scheduler, and Administration Portal.

The domain currently prioritizes read-only observability. It does not start,
stop, restart, pull, update, recreate, or remove containers.

## Design Goals

- Represent Atlas-managed services through stable normalized models.
- Isolate Docker Compose behavior behind a provider contract.
- Keep orchestration and reporting provider-independent.
- Make human and JSON output consume the same service-layer reports.
- Preserve deterministic ordering, validation, serialization, and timestamps.
- Support future API and Portal consumers without duplicating business logic.
- Establish safe boundaries before guarded lifecycle mutations are introduced.

## Non-Goals

The current subsystem does not provide:

- Arbitrary Docker or shell command execution.
- User-supplied image names, Compose arguments, or service identifiers outside
  the managed-service inventory.
- Container start, stop, restart, pull, update, recreate, or delete operations.
- Update locking, rollback execution, maintenance history, or bulk operations.
- Browser-side assembly of lifecycle commands.

## Layered Architecture

```text
Atlas CLI / Future API / Future Portal
                 │
                 ▼
      ServiceLifecycleService
                 │
       ┌─────────┴─────────┐
       ▼                   ▼
InfrastructureHealthReport  InfrastructureSummary
       │                   │
       └─────────┬─────────┘
                 ▼
     ServiceLifecycleProvider
                 │
                 ▼
       DockerComposeProvider
                 │
                 ▼
          Docker Compose
```

Interfaces call the service layer. The service layer validates provider results,
coordinates inspections, and creates normalized reports. Providers translate an
external runtime into domain contracts. Providers do not render CLI text or JSON
and do not know about Portal components or API schemas.

## Package Layout

```text
atlas/service_lifecycle/
├── __init__.py
├── models.py
├── provider.py
├── service.py
└── providers/
    └── docker_compose.py
```

The CLI adapter is located at `atlas/service_lifecycle_cli.py`. Shell dispatch and
help integration are located under `scripts/commands/`.

## Core Models

### `ManagedService`

Represents stable service identity and configuration metadata, including:

- identifier and display name
- provider identity
- Compose project and container name
- enabled state
- normalized dependencies
- optional lifecycle timestamps

### `ServiceImage`

Represents the configured or running image identity, including reference,
repository, tag, digest, image ID, and optional creation timestamp.

### `ServiceRuntime`

Represents normalized runtime inspection, including state, Docker health,
running and healthy convenience properties, restart count, timestamps, exit code,
status message, and image identity.

### `ServiceHealth`

Represents a normalized service-health evaluation with status, score, action
requirement, warnings, errors, details, and evaluation timestamp.

All domain models normalize inputs, validate identity and child contracts,
normalize timestamps, provide `to_dict()` serialization, and are covered by
dedicated tests.

## Provider Contract

`ServiceLifecycleProvider` defines the read-only provider boundary:

```text
list_services()
inspect_service(identifier)
inspect_runtime(identifier)
inspect_health(identifier)
```

A provider must:

- Return normalized domain objects rather than raw Docker responses.
- Reject invalid or unknown service identifiers.
- Preserve stable service identity.
- Report dependencies and runtime state deterministically.
- Translate provider failures into `ServiceLifecycleError` contracts.
- Avoid output rendering and interface-specific behavior.
- Remain read-only until guarded mutation contracts are explicitly introduced.

`DockerComposeProvider` is the current implementation. Additional providers may be
added later without changing the CLI or report contracts when they satisfy the
same provider interface.

## Orchestration Service

`ServiceLifecycleService` validates the provider implementation and owns
provider-independent orchestration.

Current operations include:

```text
list_services()
inspect_service(identifier)
inspect_runtime(identifier)
inspect_health(identifier)
inspect_health_report()
inspect_summary()
```

The service layer normalizes identifiers, validates returned model types,
rejects duplicate or mismatched identities, preserves known domain errors, and
wraps unexpected provider failures.

## Report Models

### `ServiceHealthEntry`

Pairs a `ManagedService` identity with its `ServiceHealth` evaluation and exposes
whether the service requires attention.

### `InfrastructureHealthReport`

Provides canonical aggregate health across all managed services:

- total service count
- Healthy, Degraded, Unhealthy, and Unknown counts
- conservative aggregate score
- aggregate status
- services requiring attention
- warnings and errors
- individual normalized health entries
- evaluation timestamp

Aggregate errors force an Unhealthy result. Empty service inventories produce an
explicit Unknown report.

### `ServiceRuntimeEntry`

Pairs a `ManagedService` identity with a `ServiceRuntime` inspection and
normalizes runtime state into one summary category:

- running
- stopped
- restarting
- failed
- unknown

### `InfrastructureSummary`

Provides a concise operational contract suitable for CLI, API, and Portal
consumers:

- provider and Compose project
- total, enabled, and disabled services
- runtime counts
- health counts
- aggregate score and status
- services requiring attention
- normalized runtime entries
- evaluation timestamp

Runtime and health identities must match exactly. Summary collection lists the
managed-service inventory once and reuses it for runtime and health orchestration.

## CLI Contract

The current CLI is read-only:

```text
atlas service list [--json]
atlas service show <identifier> [--json]
atlas service runtime <identifier> [--json]
atlas service health <identifier> [--json]
atlas service health [--json]
atlas service summary [--json]
```

`atlas services [--json]` remains a compatibility alias. The CLI parses arguments,
invokes `ServiceLifecycleService`, and renders normalized contracts. It must not
call Docker Compose directly or calculate lifecycle business rules.

## Read-Only Guarantee

The current Service Lifecycle surface performs inspection only. No command in the
domain executes Docker mutation operations. This guarantee allows discovery,
runtime reporting, health reporting, and summary reporting to mature before
Atlas is allowed to change infrastructure state.

The read-only phase supports the Project Atlas principle of observability before
automation.

## Dependency Philosophy

Dependencies are stored as normalized managed-service identifiers. They are
currently reported but not used to perform lifecycle operations.

Future dependency analysis must account for relationships such as:

```text
gluetun
└── qbittorrent

jellyfin
├── jellyseerr
├── maintainerr
└── tautulli

radarr / sonarr
├── jellyseerr
└── maintainerr
```

qBittorrent must never be recreated outside its required Gluetun networking
relationship. Dependency-aware validation must precede any mutation capability.

## Future Reporting

Planned read-only capabilities include:

```text
atlas service doctor [--json]
atlas service graph [--json]
atlas service updates [--json]
atlas service history [--json]
```

Service Doctor will consume normalized runtime, health, and dependency data to
identify stopped services, unhealthy services, restart loops, missing health
checks, missing dependencies, and configuration warnings.

Service Graph will expose the dependency contract in human-readable and JSON
forms. Update discovery will inspect image identity and registry state without
applying changes. Maintenance history will provide durable audit visibility.

## Future Guarded Lifecycle Operations

Write operations will be added only after read-only reporting is mature. The
intended request flow is:

```text
Administration Portal
        │ authenticated and authorized request
        ▼
      Atlas API
        │ validated operation contract
        ▼
ServiceLifecycleService
        │ allow-listed plan and lock
        ▼
ServiceLifecycleProvider
        │ controlled provider operation
        ▼
   Docker Compose
```

Guarded operations must require:

- administrator authorization
- allow-listed managed-service identifiers
- no arbitrary shell arguments or image names
- explicit planning and confirmation
- operation locking
- pre-operation state capture
- configuration backup where appropriate
- dependency awareness
- post-operation startup and health validation
- maintenance-event persistence
- complete audit history
- secrets excluded from browser responses
- failed-operation rollback where safe

Individual updates must be reliable before any update-all operation is exposed.

## API and Portal Integration

Future API schemas and Portal components should adapt the normalized service-layer
reports rather than call Docker directly. The Administration area is expected to
provide:

```text
Administration
└── Services
    ├── Overview
    ├── Updates
    ├── Restart
    ├── Logs
    └── Maintenance history
```

The first Portal surfaces should remain read-only and consume
`InfrastructureHealthReport` and `InfrastructureSummary`. Guarded buttons should
be introduced only after authorization, planning, locking, validation, history,
and rollback contracts exist in Atlas Core.

## Extension Points

The provider abstraction allows future implementations such as remote Docker
Compose nodes, Docker Swarm, Kubernetes, or other infrastructure backends. New
providers must preserve the same normalized identities and read-only reporting
contracts before provider-specific operations are considered.

## Engineering Principles

Service Lifecycle follows the Project Atlas principles:

- Simplicity over complexity.
- Reliability over novelty.
- Observability before automation.
- Automation before repetitive manual intervention.
- Documentation as a first-class feature.
- Modular architecture and reusable Core services.
- Optional feature modules.
- User-first operation and presentation.
- Test and validate before production changes.
- Back up, verify, and preserve rollback paths.


## Service Doctor

Service Doctor provides provider-independent, read-only diagnostics over the
normalized Service Lifecycle contracts. `ServiceDoctor` consumes
`ServiceLifecycleService`; it does not call Docker or Docker Compose directly.

The canonical report is `DoctorReport`, which contains deterministic
`DoctorFinding` records grouped by severity and category. The same serialized
contract is intended for the CLI, Atlas API, and Administration Portal.

CLI commands:

```text
atlas service doctor
atlas service doctor --json
```

The command never starts, stops, restarts, pulls, recreates, or updates a
service. Infrastructure mutations remain outside the v1.0 Service Doctor scope.

### Diagnostic deduplication

Service Doctor reports one actionable finding per root cause. A running service
without a Docker health check produces the observability finding
`healthcheck-missing`. Atlas does not also emit `health-degraded` when the
normalized health report is degraded solely because that health check is absent.
Additional health warnings or errors continue to produce an independent health
finding.
