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
- Support API and Portal consumers without duplicating business logic.
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
Atlas CLI / Atlas API / Atlas Portal
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

## Read-Only API Contract

M-018.30 exposes the first Service Lifecycle HTTP transport boundary. The API
remains a presentation/transport adapter over the existing
`ServiceLifecycleService`; it does not move provider or lifecycle business logic
into FastAPI routes.

The v1 read-only surface is:

```text
GET /api/v1/services
GET /api/v1/services/{service_identifier}
GET /api/v1/services/health
GET /api/v1/services/summary
```

The endpoints adapt the existing normalized managed-service,
`InfrastructureHealthReport`, and `InfrastructureSummary` contracts. They use
the existing `system.health.read` authorization permission and return
non-leaking HTTP errors when the Service Lifecycle provider is unavailable.

The API does not call Docker Compose directly. Default dependency construction
creates `DockerComposeProvider` behind `ServiceLifecycleService`, preserving the
same provider-independent orchestration boundary used by the CLI.

M-018.30 introduces no POST, PUT, PATCH, or DELETE Service Lifecycle operations.
Restart, update, rollback, operation locking, maintenance writes, audit-event
publication, Update Discovery API, Maintenance History API, and Portal
integration remain outside this slice.

Dedicated route tests cover collection, detail, unknown-service handling,
aggregate health, infrastructure summary, provider failure, authorization,
static route precedence, and the GET-only OpenAPI contract.

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

## Update Discovery Contracts

Update Discovery begins with provider-independent, immutable domain contracts.
`ImageReference` normalizes repository, tag, digest, raw reference, canonical
reference, and mutable-tag identity. `ServiceUpdate` represents one managed
service's read-only update evaluation, while `UpdateReport` provides deterministic
status counts, attention items, ordering, and serialization for future CLI, API,
and Administration Portal consumers.

The initial contract statuses are:

```text
current
update-available
mutable-tag
unknown
unsupported
```

M-018.20 introduces models only. It does not query registries, pull images,
restart services, recreate containers, or otherwise mutate Docker.

### Local provider update metadata

`ServiceLifecycleProvider.inspect_update()` returns one normalized
`ServiceUpdate`. The Docker Compose implementation reuses normalized service and
runtime image identity and remains conservative:

- `latest` is reported as `mutable-tag`;
- pinned tags and digest-pinned references are `unknown` until registry comparison;
- `update-available` is never emitted from local metadata alone;
- no registry request, pull, restart, recreation, or Docker mutation occurs.

Digest-only references retain a null tag and are never classified as mutable.

### Update discovery service

`ServiceUpdateService` is the provider-independent orchestration layer for
update discovery. It depends on `ServiceLifecycleService`, reuses its validated
managed-service inventory, invokes `inspect_update()` through the provider
boundary, and validates every returned `ServiceUpdate`.

The service enforces:

- normalized requested service identity;
- `ServiceUpdate` child contracts;
- matching service identifiers and names;
- preservation of known Atlas domain errors;
- translation of unexpected provider failures;
- deterministic `UpdateReport` aggregation;
- explicit `unknown` and `mixed` provider summaries.

The service contains no registry, Docker, CLI, API, or Portal presentation logic.
It remains fully read-only.

### Update discovery CLI

The read-only Update Discovery service is exposed through:

```text
atlas service updates
atlas service updates --json
```

Human output summarizes provider identity, aggregate status, counts, attention
items, and every evaluated service. JSON output serializes `UpdateReport`
directly and is the canonical contract for future API and Administration Portal
consumers.

The CLI performs argument parsing and presentation only. It does not implement
update evaluation, contact registries, pull images, or mutate Docker.

## Maintenance History Contracts

Maintenance History begins with immutable, provider-independent records and
reports. `MaintenanceRecord` represents one observation or maintenance event,
including normalized service identity, action, result, provider, timestamps,
duration, summary, and structured details.

`MaintenanceReport` provides deterministic newest-first ordering, result counts,
latest-record summaries, and canonical serialization for future CLI, API,
Administration Portal, persistence, scheduling, and post-v1.0 maintenance-engine
consumers.

The v1.0 contracts understand both read-only actions and future write actions,
but this sprint does not execute maintenance, persist records, schedule work, or
mutate Docker.

## Service Implementation Package

Service Lifecycle orchestration implementations are organized under:

```text
atlas/service_lifecycle/services/
├── lifecycle.py
├── doctor.py
└── updates.py
```

The package-level public API remains unchanged:

```python
from atlas.service_lifecycle import (
    ServiceDoctor,
    ServiceLifecycleService,
    ServiceUpdateService,
)
```

The previous internal module paths (`service.py`, `doctor.py`, and `update.py`)
remain as compatibility shims. This preserves existing integrations while making
future service additions, including Maintenance History, easier to organize.

M-018.24.5 is a structural refactor only. It does not change Service Lifecycle
behavior, provider contracts, CLI output, Docker interaction, or the read-only
v1.0 safety boundary.

### Maintenance history service

`ServiceMaintenanceHistoryService` is the provider-independent, read-only
orchestration layer for Maintenance History. It validates provider reports,
normalizes requested service identity through `ServiceLifecycleService`,
preserves known Atlas errors, translates unexpected provider failures, and
enforces service identifier and name consistency for service-specific history.

`ServiceLifecycleProvider` supplies concrete empty-history defaults. This keeps
existing providers and test doubles backward compatible while establishing the
future persistence boundary.

M-018.25 does not persist records, create maintenance events, schedule work, or
mutate Docker.

### Maintenance history CLI

The read-only Maintenance History service is exposed through:

```text
atlas service history
atlas service history <identifier>
atlas service history --json
atlas service history <identifier> --json
```

Human output summarizes scope, provider, result counts, attention state, and
ordered maintenance records. JSON output serializes `MaintenanceReport`
directly and remains the canonical contract for future API and Administration
Portal consumers.

Until a persistence provider is introduced, the live provider returns valid
empty reports. The CLI does not create records, perform maintenance, schedule
work, or mutate Docker.

## Documentation Map

Service Lifecycle documentation is split by audience:

- Architecture and design: [`SERVICE_LIFECYCLE.md`](SERVICE_LIFECYCLE.md)
- CLI reference: [`../cli/SERVICE_LIFECYCLE.md`](../cli/SERVICE_LIFECYCLE.md)
- Python API reference: [`../api/SERVICE_LIFECYCLE.md`](../api/SERVICE_LIFECYCLE.md)
- Engineering standards: [`../ENGINEERING_GUIDE.md`](../ENGINEERING_GUIDE.md)
- Sprint checklist: [`../ENGINEERING_CHECKLIST.md`](../ENGINEERING_CHECKLIST.md)

## Administration Portal Integration

The Administration Portal consumes Service Lifecycle through the Atlas API and
the same provider-independent service-layer contracts used by the CLI. It does
not call Docker or Docker Compose directly.

M-018.31 implements the first Portal Service Lifecycle surfaces:

- protected `/portal/services` navigation under `system.health.read`;
- managed-service inventory and overview cards;
- aggregate Service Lifecycle health presentation;
- normalized runtime and health state on service cards; and
- read-only per-service detail inspection.

The Portal joins managed-service collection identities with the per-service
runtime entries from the infrastructure-summary response and the per-service
health entries from the aggregate-health response. This keeps presentation
aligned with the production API shape instead of inventing browser-side domain
fields. Detail responses are enriched only with already-loaded normalized
overview state.

M-018.32 completes the responsive/mobile Service Lifecycle presentation
prerequisites. The existing Portal responsive architecture remains authoritative:
managed-service cards continue to use the shared auto-fitting dashboard grid,
touch interaction follows the shared Portal control conventions, and
Service Lifecycle cards/read-only detail values are protected against narrow
viewport overflow.

Progressive Web App support was evaluated after responsive validation. No
tracked Portal manifest, service worker, Workbox integration, install prompt, or
other PWA runtime owner exists, and PWA implementation is deferred beyond v1.0.
The responsive authenticated Portal remains the supported v1.0 mobile
administration experience.

Remaining v1.0 Portal Service Lifecycle presentation work includes:

- Update Discovery presentation; and
- Maintenance History presentation.

Representative administrator User Acceptance and final v1.0 approval remain
separate release gates.

The Portal must not duplicate Service Lifecycle business logic. Restart, update,
rollback, and other lifecycle mutation controls remain outside the v1.0
read-only boundary.

## Post-v1.0 Extension Boundary

Future write operations should extend the existing service and provider
abstractions rather than bypassing them.

The intended maintenance workflow is:

```text
Validate
↓
Backup
↓
Pull Image
↓
Recreate
↓
Health Validation
↓
Dependency Validation
↓
Record Maintenance
↓
Rollback if required
```

Those operations remain outside the v1.0 read-only boundary.

## M-018.29 Guarded Lifecycle Planning Contracts

M-018.29 implements the domain contracts required before Atlas can expose
guarded lifecycle mutation.

The public Service Lifecycle package now exports:

- `ServiceUpdateOutcome`;
- `ServiceUpdatePlan`;
- `ServiceUpdateResult`; and
- `MaintenanceEvent`.

`ServiceUpdatePlan` is an immutable dry-run planning contract for one managed
service. It binds normalized plan and service identity, the current and target
image references, requester identity, dependency identities, creation time,
correlation identity, warnings, and structured details. A plan cannot claim to
be an applied operation, and its target image must differ from its current
image.

`ServiceUpdateResult` records the normalized outcome of a later guarded update
operation without providing that operation itself. It binds the plan and
operation identities, service identity, previous/resulting image state,
normalized start/completion timestamps, rollback state, warnings/errors,
correlation identity, and structured details. Rollback identifiers cannot be
reported unless rollback actually occurred, and a `rolled-back` outcome
requires `rollback_performed=true`.

`MaintenanceEvent` implements the audit-domain shape defined by ADR 0010. It
records event/service/operation/requester identity, timestamps,
previous/resulting state, maintenance outcome, warnings/errors, rollback
information, and correlation identity. The model is not itself an event
publisher.

All four contracts follow the existing Atlas model contract: inputs are
normalized, identity and child contracts are validated, timestamps are
normalized to UTC, objects are immutable where practical, deterministic
`to_dict()` serialization is provided, dedicated tests exist, and public
exports are defined through `atlas.service_lifecycle`.

### Current Mutation Boundary

M-018.29 does **not** expose lifecycle mutation.

The following remain intentionally open:

- administrator authorization for lifecycle mutation;
- allow-listed mutation targets;
- lifecycle dry-run orchestration;
- guarded service update and restart execution;
- pre/post-update orchestration;
- dependency-aware execution ordering;
- lifecycle operation locking;
- failed-update rollback execution;
- bulk-update and maintenance-window orchestration;
- lifecycle maintenance-event publication;
- `atlas service update <service> --dry-run`;
- guarded lifecycle mutation API endpoints and authorization tests; and
- Service Lifecycle administration in the Portal.

The existing Service Lifecycle CLI and provider boundary therefore remain
read-only after M-018.29. These contracts establish the normalized planning,
result, and audit data model required by later guarded-mutation work; they do
not claim that guarded mutation is complete.
