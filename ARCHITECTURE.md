# Project Atlas Architecture

> **Simplicity Meets Ingenuity**

Project Atlas is an intelligent, modular, self-hosted entertainment platform. It combines user-facing applications, reusable domain services, operational automation, optional modules, provider integrations, and production infrastructure behind stable interfaces.

This document defines the intended high-level architecture of the implemented Atlas repository. Detailed decisions belong in Architecture Decision Records, Engineering Decision Records, package documentation, and operations guides.

---

## Architectural objectives

Atlas architecture is designed to:

- provide a simple experience for friends and family
- preserve reliable administrative control
- keep domain logic independent from presentation and transport layers
- make platform state observable before automating decisions
- separate policy decisions from destructive execution
- allow optional capabilities without expanding the core unnecessarily
- preserve compatibility while the platform evolves
- maintain documentation and tests as part of the implementation contract

---

## Engineering principles

Atlas follows these architectural principles:

1. **Simplicity over complexity**
2. **Reliability over novelty**
3. **Observability before automation**
4. **Automation before manual intervention**
5. **Documentation as a first-class feature**
6. **Modular architecture**
7. **Optional feature modules**
8. **User-first experience**
9. **One source of truth**
10. **Backward compatibility**
11. **Test-driven development**
12. **Engineering Bundles**
13. **Evolution over replacement**

### Evolution over replacement

Atlas extends existing contracts before replacing them, refactors before rewriting, preserves compatibility, migrates incrementally, and removes legacy behavior only after the replacement has been validated.

---

## System context

```text
Friends and Family                         Administrators
        |                                        |
        v                                        v
  Atlas Portal                            Atlas CLI / Portal
        |                                        |
        +-------------------+--------------------+
                            |
                            v
                       Atlas HTTP API
                            |
                            v
                    Atlas Application Layer
                            |
        +-------------------+-------------------+
        |                   |                   |
        v                   v                   v
  Domain Services      Runtime Services    Module Platform
        |                   |                   |
        +-------------------+-------------------+
                            |
                            v
                  Providers and Infrastructure
                            |
      +----------+----------+----------+----------+
      |          |          |          |          |
      v          v          v          v          v
  Jellyfin   Automation   Storage    Docker     External APIs
```

The Portal, CLI, and HTTP API are entry points. They should coordinate reusable application and domain services rather than duplicate business rules.

---

## Architectural layers

### 1. Presentation layer

The presentation layer contains user-facing interfaces.

#### Atlas Portal

Location:

```text
apps/portal/
```

Responsibilities:

- public landing experience
- authentication user experience
- dashboards and navigation
- user profiles and favorites
- Media and Sports experiences
- administrative interfaces
- access-control management
- operational visibility
- documentation access

The Portal uses Next.js. It consumes stable HTTP contracts and must not become the canonical owner of domain rules.

#### Atlas CLI

Primary entry point:

```text
scripts/atlas
```

Supporting commands:

```text
scripts/commands/
```

Responsibilities:

- platform verification and diagnostics
- service and URL discovery
- backup and maintenance workflows
- scheduler operations
- event operations
- user, invitation, registration, and favorite operations
- retention and cleanup evaluation
- module lifecycle management
- operational intelligence collection and reporting

The CLI is an adapter over Atlas services and shell-based infrastructure operations. Domain behavior should remain testable outside the command dispatcher.

---

### 2. Transport layer

#### Atlas HTTP API

Location:

```text
apps/api/
```

The API uses FastAPI and exposes versioned routes under:

```text
/api/v1
```

Responsibilities:

- request parsing and schema validation
- authenticated-user resolution
- authorization enforcement
- stable HTTP contracts
- OpenAPI generation
- translation between transport schemas and Atlas services
- consistent error responses

The API should remain thin. It must not create a second implementation of core Atlas business logic.

---

### 3. Application and domain layer

The primary Python platform is located under:

```text
atlas/
```

This layer contains models, repositories, services, policies, orchestration, provider abstractions, and runtime contracts.

Major domains include:

- users and profiles
- invitations and registration
- identity providers
- favorites
- authentication integration
- authorization
- Access Control Platform
- policies
- retention
- cleanup
- health
- operational intelligence
- scheduler
- events
- modules
- media/provider integrations

Domain code should remain independent of FastAPI, Next.js, shell output formatting, and specific provider implementations whenever practical.

---

### 4. Runtime services layer

Runtime services coordinate recurring or stateful work.

#### Scheduler

The scheduler owns:

- job definitions
- registration and removal
- inspection
- manual execution
- dry runs
- execution history
- synchronization with module jobs

Scheduler jobs invoke application services. They should not embed duplicate business rules.

#### Event system

The event system owns:

- event publication
- subscriber registration
- pending-event consumption
- filters
- subscriber cursors
- reset and seek operations

Events allow subsystems and modules to react without requiring direct coupling between every producer and consumer.

#### Runtime state

Runtime state contains current operational values needed by multiple services. Persistent records and immutable audit history must remain distinct from disposable caches.

---

### 5. Module layer

Optional features are located under:

```text
modules/
```

Modules may provide:

- domain-specific services
- commands
- scheduled jobs
- event subscribers
- provider integrations
- health checks
- Docker services
- Portal experiences
- API routes through approved integration contracts

Current module work includes the Sports platform and supporting module templates. Notification infrastructure also exists as optional module work.

Modules must not bypass core authentication, authorization, configuration, event, scheduler, or audit contracts.

---

### 6. Provider and integration layer

Provider adapters translate Atlas contracts into external-system operations.

Examples include:

- Jellyfin identity and media operations
- Jellyseerr request workflows
- Sonarr and Radarr automation
- Prowlarr indexer integration
- qBittorrent download operations
- sports data providers
- notification adapters
- Docker and filesystem operations

Provider-specific errors and payloads should be normalized before reaching domain services.

---

### 7. Infrastructure layer

Infrastructure definitions are maintained under:

```text
infra/
docker-compose.yml
modules/*/docker-compose.yml
```

The current deployment model includes:

- Proxmox VE
- Debian LXC
- Docker Engine
- Docker Compose
- Intel Quick Sync when available
- persistent media and configuration storage
- Caddy ingress
- Cloudflare-compatible DNS
- automatic TLS

Infrastructure can evolve independently when Atlas interfaces and persisted contracts remain stable.

---

## Core platform domains

### Users, invitations, and registration

Atlas user services own profile identity and lifecycle state. Invitations authorize controlled registration. Registration coordinates Atlas identity with configured providers.

Identity values must be normalized consistently and remain stable across Portal, API, CLI, provider, favorite, policy, and access-control workflows.

### Authentication

Authentication establishes who is making a request.

The authentication layer may integrate with external providers, but Atlas owns the authenticated-user representation used by its application services and authorization system.

Authentication does not itself determine whether an authenticated user may perform an action.

### Access Control Platform and authorization

ACP and authorization have separate responsibilities.

#### ACP owns

- canonical permission definitions
- permission groups
- canonical roles
- ownership contracts
- visibility contracts
- quota contracts
- access-control repositories and services
- management and audit contracts

#### Authorization owns

- effective permission resolution
- runtime allow-or-deny decisions
- policy enforcement adapters
- reusable API security dependencies

Target flow:

```text
Authenticated Principal
          |
          v
   ACP assignments and roles
          |
          v
Effective Permission Resolution
          |
          v
 Authorization Decision
          |
          v
CLI / API / Portal / Module Action
```

The developing ACP must become the canonical catalog rather than creating a permanently competing role and permission source.

### Favorites

Favorites represent explicit user intent. They are consumed by user experiences and policy services, including retention protection.

A favorite should reference canonical provider and item identities. User-facing shortcuts or views must not create duplicate media ownership.

### Policy engine

The policy engine evaluates facts and produces explicit policy decisions.

A policy decision includes:

- provider identity
- item identity
- action
- reasons
- evaluation timestamp

Policy evaluation does not directly delete media.

### Retention

Retention converts policy results and media facts into eligibility decisions.

```text
User and Media Facts
        |
        v
    Policy Engine
        |
        v
 Retention Decision
```

Retention answers whether an item is eligible for downstream cleanup consideration while preserving policy reasons.

### Cleanup

Cleanup converts retention decisions into explicit plans and controlled execution.

```text
Retention Decision
        |
        v
  Cleanup Planning
        |
        +------> Keep
        +------> Review
        +------> Delete
                       |
                       v
             Provider Execution
                       |
                       v
              History and Audit
```

Destructive operations must be explicit, observable, idempotent where practical, and recorded. Planning and execution remain separate so decisions can be inspected before action.

### Health and operational intelligence

Atlas health and ARI services observe infrastructure and application state.

Inputs may include:

- Docker
- storage
- VPN state
- Jellyfin
- configuration
- snapshots
- module health

Outputs may include:

- health checks and scores
- immutable snapshots
- historical analysis
- forecasts
- recommendations
- operational reports

Observability data informs operators and automation but does not bypass normal authorization, policy, or execution controls.

---

## Primary interaction flows

### Portal request flow

```text
Browser
   |
   v
Caddy Ingress
   |
   v
Atlas Portal
   |
   v
Atlas API /api/v1
   |
   +--> Authentication
   +--> Authorization
   +--> Application Service
   +--> Repository or Provider
   |
   v
Normalized Response
```

### Administrative CLI flow

```text
Administrator
      |
      v
 scripts/atlas
      |
      v
Command Adapter
      |
      +--> Atlas Service
      +--> Runtime Service
      +--> Infrastructure Script
      |
      v
Human or JSON Output
```

### Media request flow

```text
User
  |
  v
Atlas Portal / Jellyseerr
  |
  v
Request Management
  |
  v
Sonarr / Radarr
  |
  v
Prowlarr
  |
  v
qBittorrent through Gluetun
  |
  v
Media Storage
  |
  v
Jellyfin
```

### Sports module flow

```text
Sports Provider
      |
      v
Provider Adapter
      |
      v
Sports Domain Services
      |
      +--> Subscriptions
      +--> Scheduling
      +--> Recording
      +--> Recovery
      +--> Maintenance
      |
      v
Portal / CLI / Events / Storage
```

### Event-driven flow

```text
Producer
   |
   v
Atlas Event Store
   |
   +--> Core Subscriber
   +--> Module Subscriber
   +--> Notification Subscriber
   |
   v
Cursor and Delivery State
```

---

## Data and persistence architecture

Atlas currently uses file-backed and provider-backed persistence for several domains. Repository interfaces should isolate storage details from services so persistence can evolve without rewriting domain behavior.

Persistent data categories include:

- configuration
- user and invitation state
- favorites
- scheduler jobs and history
- events and subscriber state
- health and ARI snapshots
- retention and cleanup history
- audit records
- module state
- provider identifiers

### Identity rules

Persistent records must use stable, normalized identities. Parent and child records must agree on provider, item, user, or execution identities as applicable.

### Timestamp rules

Persisted timestamps must be normalized consistently, preferably as timezone-aware UTC values serialized in a stable format.

### Serialization rules

Domain models expose `to_dict()` serializers so CLI, API, storage, tests, and audit records use consistent representations.

### Immutable history

Historical snapshots, decisions, executions, and audit records should not be silently rewritten. Corrections should be additive when practical.

---

## Domain model contract

Every new Atlas domain model must:

1. normalize inputs
2. validate its identity
3. validate child contracts
4. normalize timestamps
5. provide a `to_dict()` serializer
6. have a dedicated test suite
7. be exported through its package `__init__.py`

Adapters and transport schemas do not remove this requirement from the underlying domain model.

---

## Configuration architecture

The primary shared configuration file is:

```text
config/atlas.conf
```

Environment-specific secrets and deployment values may be supplied through `.env` files or runtime environment variables.

Rules:

- configuration keys must have a single documented owner
- secrets must never be committed
- domain services should receive configuration rather than parse unrelated files directly
- modules should use approved configuration contracts
- defaults must be safe and explicit
- configuration changes must be documented and validated

---

## Storage architecture

A typical deployment uses:

```text
/mnt/storage
├── media/
├── downloads/
├── configs/
├── backups/
└── atlas/
    ├── ari/
    │   ├── latest.json
    │   └── snapshots/
    ├── events/
    ├── scheduler/
    ├── cleanup/
    └── modules/
```

Exact directories are configuration, not domain contracts.

Media and operational state must remain separate. Backups must not be stored only alongside the data they protect.

---

## Network and security architecture

### Ingress

```text
Internet or Private Network
           |
           v
    Cloudflare DNS
           |
           v
      Caddy Ingress
           |
      +----+----+
      |         |
      v         v
   Portal      API
```

Ingress responsibilities include TLS termination, routing, access logging, and security headers. Authentication and authorization remain application responsibilities.

### Download isolation

```text
Sonarr / Radarr / Prowlarr
             |
             v
         qBittorrent
             |
             v
          Gluetun
             |
             v
          Internet
```

VPN routing must be verified by health and operational checks. A failed VPN path must not silently fall back to an unprotected route.

### Trust boundaries

Important trust boundaries include:

- public ingress to Portal/API
- authenticated principal to authorization decision
- Atlas services to external providers
- module code to core platform services
- download services to the public internet
- application containers to persistent storage
- administrative operations to destructive execution

Each boundary should use least privilege, explicit validation, and auditable failure behavior.

---

## Observability architecture

Atlas observability includes:

- CLI diagnostics
- health checks
- structured application logs
- container logs
- API errors and request visibility
- scheduler history
- event state
- cleanup history
- audit records
- ARI snapshots and reports
- module health

Observability must exist before autonomous remediation is introduced.

---

## Recovery architecture

Before significant changes:

1. run `atlas doctor`
2. run `atlas verify`
3. create a backup
4. verify the backup and manifest
5. apply the change incrementally
6. run targeted tests
7. run regression tests
8. verify platform health again
9. document and commit the result

Recovery design must include:

- configuration backups
- Atlas state backups
- media metadata protection
- restoration documentation
- backup retention
- off-system or off-host protection where practical
- periodic restore validation

---

## Repository architecture

```text
project-atlas/
├── apps/
│   ├── api/
│   └── portal/
├── atlas/
├── config/
├── configs/
├── docs/
│   ├── ADR/
│   ├── EDR/
│   ├── architecture/
│   ├── guides/
│   └── milestones/
├── infra/
├── modules/
├── scripts/
└── tests/
```

Canonical source should exclude:

- `.env` files containing secrets
- copied virtual environments
- copied `node_modules`
- generated `.next` output
- `__pycache__`
- temporary repository exports
- review archives
- routine backup payloads

These may exist operationally but should not be treated as source architecture.

---

## Testing architecture

Atlas testing is divided by responsibility.

### Core tests

Location:

```text
tests/
```

Covers domain models, repositories, services, CLI behavior, scheduler, events, health, retention, cleanup, users, registration, favorites, and modules.

### API tests

Location:

```text
apps/api/tests/
```

Covers application creation, routes, schemas, authentication, security dependencies, authorization, ACP contracts, and OpenAPI behavior.

### Module tests

Modules may maintain unit, integration, recovery, recording, provider, scheduler, and maintenance tests under their own directories.

### Portal validation

Portal validation includes clean dependency installation, type checking, linting, tests where present, and production builds.

The current core and API suites both expose top-level `tests` packages. They should be invoked separately until package isolation is corrected.

---

## Documentation architecture

Documentation is part of the platform contract.

- `README.md` introduces the repository.
- `CHARTER.md` governs mission and scope.
- `ARCHITECTURE.md` defines high-level boundaries.
- `ROADMAP.md` defines planned milestones and Engineering Bundles.
- `CHANGELOG.md` records notable changes.
- `BUILD_LOG.md` records engineering implementation history.
- `docs/MATURITY.md` tracks capability maturity.
- `docs/ADR/` records architecture decisions.
- `docs/EDR/` records engineering decisions.
- operations and administrator guides define supported procedures.

A significant change is incomplete until affected documentation is synchronized.

---

## Architectural governance

Atlas changes are delivered through Engineering Bundles.

```text
Repository Review
        |
        v
Architecture and Design Review
        |
        v
Design Freeze
        |
        v
Incremental Implementation
        |
        v
Targeted and Regression Validation
        |
        v
Documentation Synchronization
        |
        v
Git Review and Focused Commit
```

Architecture changes must:

- identify the existing source of truth
- define ownership boundaries
- preserve compatibility or document migration
- include tests
- update ADRs when a durable decision changes
- update EDRs when engineering execution rules change
- synchronize roadmap, build log, changelog, and maturity records
- avoid parallel implementations without an approved convergence plan

---

## Current convergence work

The primary architectural convergence before v1.0 is the relationship between the existing authorization package and the developing Access Control Platform.

The target state is:

- one canonical permission catalog
- one canonical role catalog
- ACP-owned repositories and services
- reusable runtime authorization decisions
- consistent enforcement across API, Portal, CLI, and modules
- audit integration
- backward-compatible migration from existing authorization contracts

This work is planned through the M-020 Engineering Bundles and must follow evolution-over-replacement rules.

---

## Planned evolution

### Before Atlas v1.0

- complete Portal and API integration
- complete authentication workflows
- complete ACP and authorization convergence
- deliver Media and Sports user experiences
- deliver administrative and operational interfaces
- complete production-readiness validation

### After Atlas v1.0

- notifications and communication improvements
- richer analytics and personalization
- expanded automation
- additional optional modules
- UX improvements
- broader provider integrations

### Longer-term platform work

- multi-node or clustered Atlas infrastructure
- resilient storage
- disaster recovery automation
- Game Server Platform integrated with ACP
- advanced operational intelligence

Future architecture must extend stable v1.0 contracts rather than bypass them.

## Operations reporting architecture

Atlas Operations is the canonical read-only infrastructure-reporting domain.

```text
SystemProvider / DockerProvider
              |
              v
SystemCollector / DockerCollector
              |
              v
       OperationsService
              |
              v
       OperationsReport
          /         \
         v           v
 Human CLI        Stable JSON
```

The `atlas.operations` package owns immutable findings, sections,
summaries, reports, validation, deterministic ordering, and serialization.

Collectors remain read-only. Provider boundaries isolate host and Docker
access. Collector failures produce an unknown fallback section instead of
aborting the complete report.

`HostOperationsContextProvider` supplies report identity, hostname, Atlas
version, Git commit, and one timezone-aware UTC timestamp.

Public commands:

```bash
atlas operations
atlas operations help
atlas operations report
atlas operations report --json
atlas operations report --report-id REPORT_ID
atlas operations save
atlas operations latest
atlas operations history
atlas operations history --json
atlas operations history --limit LIMIT
atlas operations compare
atlas operations compare --json
atlas operations compare --include-unchanged
```

The JSON `OperationsReport` is now the canonical persistence contract.
Serialized reports are reconstructed through schema-validated domain
loaders that normalize identities, timestamps, child contracts, and
canonical inputs while recomputing derived status, score, summary, and
attention fields.

Persistence is isolated behind `OperationsRepository` and the default
`FileOperationsRepository` implementation.

The default layout is:

    /mnt/storage/configs/atlas/operations/
    ├── latest.json
    └── history/
        └── <generated-at>.json

Historical snapshots are immutable and written atomically. `latest.json`
is updated only after the historical snapshot succeeds.

History inspection is exposed through the read-only Operations CLI. The
repository returns validated reports in deterministic newest-first order,
and callers may apply a bounded result limit.

Human history output intentionally summarizes report identity, generation
time, status, and score. JSON history output wraps complete validated
`OperationsReport` contracts with a deterministic `count` field.

Persisted reports can be compared through a pure, read-only comparison
pipeline:

```text
FileOperationsRepository
          |
          v
OperationsComparisonService
          |
          v
  OperationsComparison
       /          \
      v            v
Human Renderer   Stable JSON
```

The comparison service receives two validated `OperationsReport` values and
detects added, removed, changed, and optionally unchanged findings. It does
not read files directly, mutate reports, write snapshots, or update
`latest.json`.

`OperationsComparison` stores only canonical reports and finding changes.
Status changes, score deltas, attention deltas, and change counts are
derived from those canonical inputs rather than persisted independently.

Scheduled collection, APIs, notifications, and the Portal remain future
extensions of this stable contract.
