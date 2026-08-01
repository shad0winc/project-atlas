# ADR 0010 — Atlas Service Lifecycle Architecture

## Status

Accepted

## Scope

This ADR defines the architecture and safety boundaries for managing
Atlas-operated infrastructure services.

It applies to service discovery, health reporting, update availability,
restart operations, guarded updates, rollback, maintenance history, CLI
access, API access, and Admin Portal integration.

The initial provider targets Docker Compose, but the domain must remain
provider-independent.

---

## Context

Project Atlas currently interacts with Docker and Docker Compose through
multiple operational scripts and commands.

As the Atlas Admin Portal gains infrastructure-management features, Docker
behavior must not be duplicated across the CLI, API, Portal, and scheduler.

Directly exposing Docker or shell execution through the Portal would create
significant security, reliability, and maintainability risks.

Atlas requires one domain that owns managed-service lifecycle behavior and
exposes only explicit, validated operations.

---

## Decision

Atlas adopts a provider-independent Service Lifecycle domain.

The domain owns:

- Managed-service identity
- Runtime-state normalization
- Health evaluation
- Image and update state
- Update planning
- Lifecycle operation results
- Maintenance history
- Dependency-aware orchestration
- Rollback decisions
- Audit events

Docker Compose behavior is encapsulated behind a concrete provider.

The dependency flow is:

    CLI / API / Admin Portal / Scheduler
                    |
                    v
          Service Lifecycle Service
                    |
                    v
         Service Lifecycle Provider
                    |
                    v
           Docker Compose / Docker

Presentation layers must not contain Docker business logic.

---

## Standard Package Layout

    atlas/service_lifecycle/
        __init__.py
        models.py
        provider.py
        service.py
        report.py
        providers/
            __init__.py
            docker_compose.py

Additional modules may be introduced when justified, including:

    history.py
    policy.py
    locking.py
    rollback.py

Unnecessary nesting should be avoided.

---

## Domain Responsibilities

The Service Lifecycle domain owns exactly one business capability:

> Safe and observable management of Atlas-operated services.

It normalizes provider data and coordinates lifecycle workflows.

It must remain independent from HTML rendering, HTTP response formatting,
shell output, and direct user-interface concerns.

---

## Managed-Service Identity

Every managed service must have a stable Atlas identity.

A service identifier must never be accepted directly as an arbitrary Docker
or shell argument.

The domain validates identifiers against an Atlas-managed allow-list derived
from trusted configuration.

Initial managed services may include:

- jellyfin
- prowlarr
- sonarr
- sonarr-anime
- radarr
- radarr-anime
- jellyseerr
- bazarr
- maintainerr
- tautulli
- qbittorrent
- gluetun
- flaresolverr
- homepage
- dozzle
- unpackerr
- recyclarr

Provider-specific names may be normalized into stable Atlas identifiers.

---

## Model Responsibilities

Service Lifecycle models follow the Atlas model contract.

Each public model must:

- Normalize inputs
- Validate identity
- Validate child contracts
- Normalize timestamps
- Provide `to_dict()`
- Remain immutable where practical
- Be exported through the package `__init__.py`
- Have dedicated tests

Initial models may include:

- `ManagedService`
- `ServiceImage`
- `ServiceRuntime`
- `ServiceHealth`
- `ServiceUpdatePlan`
- `ServiceUpdateResult`
- `MaintenanceEvent`

---

## Provider Responsibilities

Providers encapsulate external infrastructure access.

The Docker Compose provider may:

- Discover configured Compose services
- Inspect container state
- Inspect Docker health status
- Inspect image references and identifiers
- Inspect restart counts and uptime
- Inspect trusted service dependencies
- Pull configured images
- Recreate allow-listed services
- Return normalized operation results

Providers must not decide business policy.

Providers normalize external responses into Service Lifecycle models.

Providers must never accept raw shell fragments from callers.

---

## Service Responsibilities

The Service Lifecycle service coordinates business workflows.

It may:

- Validate managed-service identity
- List and inspect services
- Evaluate health
- Determine update state
- Build dry-run update plans
- Enforce dependency ordering
- Acquire operation locks
- Capture pre-operation state
- Invoke providers
- Validate post-operation health
- Produce reports
- Record maintenance events
- Initiate rollback workflows

It must not:

- Format CLI output
- Generate HTTP responses
- Render Portal components
- Construct commands from untrusted text
- Expose secrets
- Execute arbitrary shell input

---

## Read-Only First

Service Lifecycle development begins with read-only capabilities.

The initial implementation sequence is:

1. Managed-service models
2. Provider contracts
3. Docker Compose discovery
4. Runtime inspection
5. Health reporting
6. Update-availability inspection
7. CLI and API read-only views

Mutating lifecycle operations must not be introduced until read-only behavior
is tested and reliable.

---

## Command Safety Boundary

The CLI, API, Admin Portal, and scheduler call typed Service Lifecycle
operations.

They must never construct or execute arbitrary Docker or shell commands.

They must never submit:

- Arbitrary Docker arguments
- Arbitrary Compose arguments
- Shell fragments
- User-supplied image names
- Unvalidated container names
- Unvalidated file paths
- Environment assignments supplied as commands

Permitted requests resemble typed operations such as:

    inspect(service_id)
    health(service_id)
    plan_update(service_id)
    restart(service_id)
    apply_update(service_id, plan_id)
    rollback(operation_id)

The provider alone translates validated operations into Docker or Compose
actions.

---

## Guarded Lifecycle Operations

Mutating operations require explicit safeguards.

At minimum:

- Administrator authorization
- Allow-listed service identity
- Explicit operation type
- Interactive confirmation
- Pre-operation state capture
- Operation locking
- Dependency awareness
- Post-operation health validation
- Maintenance-event recording
- Clear success or failure results
- A rollback path when supported

The initial mutation set may include:

- Restart
- Guarded single-service update
- Rollback

Bulk updates and scheduled maintenance must be added only after single-service
operations are proven reliable.

---

## Update Workflow

A guarded single-service update follows this sequence:

1. Verify administrator authorization
2. Validate the managed-service identifier
3. Acquire an operation lock
4. Inspect current runtime and image state
5. Capture pre-update state
6. Build or validate the update plan
7. Pull the configured image
8. Recreate only the selected service
9. Wait for startup
10. Validate container and domain health
11. Validate required dependencies
12. Record the maintenance event
13. Release the operation lock
14. Return a normalized result

If validation fails, Atlas preserves diagnostics and initiates or recommends
rollback according to provider capability and configured policy.

---

## Dependency Awareness

Lifecycle operations account for trusted service relationships.

Examples include:

- qBittorrent depends on Gluetun networking
- Sonarr and Radarr depend on Prowlarr integration
- Media services depend on storage mounts
- Jellyfin may depend on GPU access and media mounts
- Portal and API services may depend on Atlas Core

Dependencies must come from trusted configuration or normalized provider data.

User-provided dependency expressions are not permitted.

---

## Operation Locking

Only one conflicting lifecycle operation may run at a time.

The implementation prevents:

- Simultaneous updates for the same service
- Restart and update overlap
- Bulk operations colliding with individual operations
- Scheduler operations colliding with Admin Portal operations

Lock ownership and timestamps must be observable.

Stale-lock handling must be explicit and tested.

---

## Maintenance History

Every mutating lifecycle operation produces an auditable maintenance event.

A maintenance event should include:

- Event identifier
- Service identifier
- Operation type
- Requested by
- Start timestamp
- Completion timestamp
- Previous state
- Resulting state
- Outcome
- Warnings
- Errors
- Rollback information
- Correlation identifier

Secrets and sensitive provider data must not be recorded.

---

## Authentication and Authorization

Restart, update, rollback, and other mutating operations require administrator
authorization.

Authorization must be enforced at the API or command boundary and revalidated
inside the lifecycle workflow where appropriate.

The Portal must not rely on hidden controls as an authorization mechanism.

---

## API Responsibilities

The API acts as a typed transport layer.

It may:

- Validate request structure
- Resolve the authenticated administrator
- Call Service Lifecycle operations
- Serialize normalized models and reports
- Return operation identifiers and status

It must not:

- Construct Docker commands
- Execute shell commands
- Accept arbitrary command text
- Return secrets
- Bypass lifecycle validation

---

## Admin Portal Responsibilities

The Admin Portal is a presentation layer.

It may provide:

- Managed-service overview
- Health cards
- Update indicators
- Service details
- Restart confirmation
- Update confirmation
- Operation progress
- Maintenance history
- Rollback status

The Portal submits typed requests to the API.

It must not communicate directly with Docker.

---

## Responsive Administration

The Admin Portal uses responsive design rather than a separate mobile
implementation whenever practical.

Phone and tablet support includes:

- Touch-friendly controls
- Responsive service cards
- Mobile-safe tables
- Collapsible administration navigation
- Clear update and restart confirmations
- Sufficient spacing between destructive and ordinary actions
- Portrait and landscape verification

Potentially destructive controls require explicit confirmation on every
supported layout.

Progressive Web App support may be evaluated after responsive behavior is
stable.

---

## Testing Requirements

The Service Lifecycle domain requires dedicated tests.

At minimum:

- Model normalization and validation
- Model serialization
- Managed-service identity validation
- Provider payload validation
- Provider error translation
- Service behavior
- Health evaluation
- Update-plan validation
- Dependency ordering
- Operation locking
- Maintenance history
- Authorization boundaries
- CLI contracts
- API contracts
- Rollback behavior where applicable

Tests remain deterministic and isolated.

Live Docker validation may supplement but must not replace contract tests.

---

## Observability

Lifecycle operations must be observable before they are automated.

Atlas should expose:

- Current operation
- Service state
- Health state
- Update state
- Start time
- Progress stage
- Warnings
- Errors
- Completion result
- Maintenance history

Automation must not hide failures or discard provider diagnostics.

---

## Consequences

### Benefits

- One lifecycle engine for CLI, API, Portal, and scheduler
- Reduced Docker logic duplication
- Stronger security boundaries
- Predictable service identity
- Better testing
- Safer updates
- Auditable maintenance
- Responsive administration experience
- Easier support for future providers

### Tradeoffs

- Additional domain structure
- More work before update controls are exposed
- Required maintenance of trusted service configuration
- Greater testing requirements for mutations
- Rollback support may vary by provider and service

---

## Relationship to Other ADRs

This ADR complements:

- ADR 0001 — Atlas Platform Architecture
- ADR 0008 — Atlas Portal Architecture
- ADR 0009 — Atlas Domain Architecture

ADR 0001 defines the high-level platform organization.

ADR 0008 defines the relationship between the Portal, API, and Atlas Core.

ADR 0009 defines domain architecture conventions.

This ADR defines the Service Lifecycle domain and its infrastructure-management
safety boundary.
