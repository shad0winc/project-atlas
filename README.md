# Project Atlas

> **An intelligent, modular, self-hosted entertainment platform built for reliability, observability, automation, and long-term evolution.**

Project Atlas provides a unified platform for operating private media, sports, user, automation, and administration services for friends and family.

Atlas combines a production media stack with a test-backed Python platform, operational CLI, scheduler, event system, user and identity services, retention intelligence, cleanup workflows, a versioned HTTP API, and a developing web portal.

The platform is designed to hide infrastructure complexity from ordinary users while preserving clear operational control for administrators.

---

## Project status

- **Release line:** `v0.9.x` release-candidate development
- **Primary objective:** Complete the stable Atlas v1.0 Media and Sports experience
- **Current focus:** Portal, API, authentication, authorization, ACP, operations, and production readiness

The authoritative version is stored in `VERSION`. The detailed implementation plan is maintained in `ROADMAP.md`.

---

## Mission

Atlas exists to give friends and family a seamless entertainment experience without requiring them to interact directly with Docker, Proxmox, Jellyfin administration, download automation, reverse-proxy configuration, internal credentials, or infrastructure maintenance workflows.

Administrators retain observability and control through the Atlas CLI, API, Portal, health systems, audit records, and operational documentation.

---

## Engineering principles

Atlas development follows these principles:

1. Simplicity over complexity
2. Reliability over novelty
3. Observability before automation
4. Automation before manual intervention
5. Documentation as a first-class feature
6. Modular architecture
7. Optional feature modules
8. User-first experience
9. One source of truth
10. Backward compatibility
11. Test-driven development
12. Engineering Bundles
13. Evolution over replacement

### Evolution over replacement

Atlas favors controlled evolution instead of unnecessary rewrites:

- Extend before replacing.
- Refactor before rewriting.
- Preserve compatibility.
- Migrate incrementally.
- Validate replacements before removing legacy behavior.
- Keep existing users and operations working throughout transitions.

---

## Platform architecture

```text
Users
  |
  v
Atlas Portal
  |
  v
Atlas HTTP API
  |
  v
Atlas Core Services
  |
  +-- Identity and user profiles
  +-- Invitations and registration
  +-- Favorites
  +-- Access control and authorization
  +-- Scheduler and runtime jobs
  +-- Event system
  +-- Policies
  +-- Retention intelligence
  +-- Cleanup planning and execution
  +-- Health and operational intelligence
  +-- Module registry
  |
  v
Providers and Infrastructure
  |
  +-- Jellyfin and Jellyseerr
  +-- Sonarr and Radarr
  +-- Prowlarr and qBittorrent
  +-- Docker and Caddy
  +-- Proxmox
```

The Portal and API are transport and presentation layers. Business rules remain in reusable Atlas domain and service packages whenever practical.

---

## Major components

### Atlas CLI

The Atlas CLI provides a unified administrative and operational interface.

Representative command groups include:

```bash
atlas help
atlas version
atlas status
atlas services
atlas urls
atlas git

atlas verify
atlas doctor
atlas backup
atlas update
atlas restart
atlas logs <container>

atlas health
atlas ari collect
atlas ari report

atlas retention evaluate <provider> <item-id>
atlas cleanup evaluate <provider> <item-id>

atlas user
atlas invite
atlas favorite
atlas scheduler
atlas modules
atlas event
```

Use `atlas help` as the authoritative command reference.

### Atlas Core

The `atlas/` package contains the primary Python domain and runtime services, including:

- ARI and operational intelligence
- health evaluation
- user profiles
- invitations and registration
- identity providers
- favorites
- policy evaluation
- retention decisions
- cleanup planning and execution
- scheduler services
- event publication and consumption
- module management
- provider integrations
- configuration and runtime state

### Atlas API

The API application is located under `apps/api/` and uses FastAPI with versioned routes under `/api/v1`.

The current foundation includes:

- application factory
- health routes
- authentication routes
- authenticated-user resolution
- reusable security dependencies
- authorization services
- ACP domain models
- OpenAPI generation
- dedicated API tests

### Atlas Portal

The Portal application is located under `apps/portal/` and uses Next.js as the primary user-facing Atlas interface.

The v1.0 Portal roadmap includes:

- public landing experience
- authentication
- application dashboard
- user profiles
- favorites
- media and sports navigation
- module integration
- administrative tools
- access-control management
- operational visibility
- documentation access

The existence of the Portal foundation does not imply that every planned page is complete.

### Authentication, identity, and access control

Atlas provides foundations for user profiles, invitations, registration, authentication providers, Jellyfin identity integration, and API authenticated-user resolution.

The intended access-control boundary is:

- **ACP** owns canonical permissions, permission groups, roles, ownership, visibility, quotas, and access-control domain contracts.
- **Authorization** owns effective permission resolution and runtime allow-or-deny decisions.
- **API security dependencies** enforce authorization decisions at transport boundaries.

This relationship is being finalized through the ACP Engineering Bundles before v1.0.

### Scheduler and events

Atlas includes reusable scheduling and event foundations for platform and module workloads, including job registration, inspection, manual execution, dry runs, history, event publication, subscribers, pending-event consumption, filtering, and cursor management.

### Retention and cleanup

Atlas separates policy decisions from destructive operations. The platform supports retention eligibility, policy reasons, protection rules, cleanup planning, keep/delete/review outcomes, cleanup execution, history, audit records, and provider abstractions.

Destructive behavior must remain explicit, observable, test-backed, and auditable.

### Optional modules

Optional capabilities are maintained under `modules/`. The module architecture allows features to be installed, enabled, disabled, verified, and operated without expanding the core platform unnecessarily.

Current module work includes the Sports platform and supporting templates.

---

## Repository layout

```text
project-atlas/
├── apps/
│   ├── api/                 # FastAPI application
│   └── portal/              # Next.js web portal
├── atlas/                   # Core Python platform
├── config/                  # Atlas configuration
├── configs/                 # Service configuration assets
├── docs/                    # Architecture and operations documentation
│   ├── ADR/                 # Architecture Decision Records
│   ├── EDR/                 # Engineering Decision Records
│   ├── architecture/        # Architecture references
│   ├── guides/              # Administrator and operator guides
│   └── milestones/          # Milestone documentation
├── infra/                   # Infrastructure and ingress definitions
├── modules/                 # Optional Atlas modules
├── scripts/                 # CLI, installation, and operational scripts
├── tests/                   # Core test suite
├── ARCHITECTURE.md          # High-level system architecture
├── BUILD_LOG.md             # Engineering implementation record
├── CHANGELOG.md             # Notable changes
├── CHARTER.md               # Mission and governing principles
├── ROADMAP.md               # Release and milestone plan
└── VERSION                  # Current Atlas version
```

Generated output, copied dependencies, temporary exports, virtual environments, backups, and secrets are not part of the intended canonical source layout.

---

## Infrastructure

The current Atlas deployment model uses:

- Proxmox VE
- Debian LXC
- Docker Engine and Docker Compose
- Intel Quick Sync when available
- persistent media and configuration storage
- Caddy ingress
- Cloudflare-compatible DNS
- automatic TLS certificate management

Atlas is designed so infrastructure providers can evolve without requiring replacement of the domain platform.

---

## Requirements

The current deployment model generally expects:

- Linux host or virtualized Linux environment
- Docker Engine
- Docker Compose
- Python 3
- Git
- persistent configuration storage
- persistent media storage
- network access to configured providers

Portal development additionally requires a supported Node.js release and npm.

---

## Installation

Atlas installation is environment-sensitive. Review the installation and configuration documentation before applying production changes.

Typical repository setup:

```bash
cd /opt
git clone <atlas-repository-url> project-atlas
cd project-atlas

cp .env.example .env
nano .env

./scripts/install.sh
```

Never commit `.env` files or production secrets.

After installation, verify the platform:

```bash
atlas verify
atlas doctor
atlas status
```

Primary references:

```text
docs/01-install.md
docs/CONFIGURATION.md
docs/OPERATIONS.md
docs/guides/ADMINISTRATOR_GUIDE.md
```

---

## Development workflow

Create a focused feature branch before beginning an Engineering Bundle:

```bash
git switch main
git pull --ff-only
git switch -c feature/<bundle-or-feature-name>
```

Before changing code or documentation:

```bash
git status --short
git branch --show-current
git log -1 --oneline
```

Changes should be incremental, test-backed, documented, and committed in focused units.

---

## Testing

### Core tests

```bash
atlas test core
```

Or run the core Python suite directly:

```bash
python3 -m pytest -q tests
```

### API tests

```bash
PYTHONPATH="$PWD:$PWD/apps/api" \
python3 -m pytest -q apps/api/tests
```

The core and API suites currently expose top-level packages named `tests`. Until test-package isolation is corrected, do not combine both paths in one pytest collection command.

### Python compilation

```bash
python3 -m compileall atlas apps/api
```

### Sports tests

```bash
atlas test sports
```

### Portal validation

Always validate the Portal from clean dependencies:

```bash
cd apps/portal
npm ci
npm run typecheck
npm run lint
npm run build
```

Do not rely on archived or copied `node_modules` content.

### Pre-commit review

```bash
git diff --check
git status --short
git diff --stat
```

Run all test scopes affected by the change.

---

## Domain model contract

Every new Atlas domain model must:

1. Normalize inputs.
2. Validate its identity.
3. Validate child contracts.
4. Normalize timestamps.
5. Provide a `to_dict()` serializer.
6. Have a dedicated test suite.
7. Be exported through its package `__init__.py`.

Models must not bypass this contract merely because they are used by an API, Portal, module, adapter, or migration layer.

---

## Atlas Engineering Bundles

Atlas uses Engineering Bundles, or AEBs, to organize related architecture, implementation, validation, and documentation work.

Each bundle follows this lifecycle:

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

An Engineering Bundle is not complete until its implementation, tests, documentation, roadmap state, build log, and changelog are consistent.

---

## Roadmap summary

### M-019 — Atlas Portal and API

Establish the public Portal, authentication, dashboard, profiles, favorites integration, versioned API foundation, Portal/API integration, and documentation access.

### M-020 — Atlas Access Control Platform

Establish the canonical permission catalog, role catalog, repositories, services, authorization adapter, REST API, management interface, and audit integration.

### M-021 — Media and Sports Experience

Deliver the stable user-facing media and sports workflows required for v1.0.

### M-022 — Administration and Operations

Provide reliable administrative, operational, observability, maintenance, and support workflows.

### M-023 — Production Readiness and v1.0 Release

Complete security, validation, documentation, deployment, backup, recovery, and release-readiness work.

Later milestones continue Portal extensibility, intelligence, personalization, cluster infrastructure, disaster recovery, and the future Game Server Platform.

See `ROADMAP.md` for the authoritative milestone definitions.

---

## Operations reporting

Atlas includes a read-only Operations subsystem that aggregates host and
Docker intelligence into deterministic reports.

```bash
atlas operations
atlas operations help
atlas operations report
atlas operations report --json
atlas operations report --report-id nightly-operations
atlas operations save
atlas operations save --json
atlas operations save --report-id nightly-operations
atlas operations latest
atlas operations latest --json
atlas operations history
atlas operations history --json
atlas operations history --limit 10
```

`report` collects a live report without persisting it.

`save` collects a live report, writes an immutable timestamped JSON
snapshot, and atomically updates `latest.json`.

`latest` loads and validates the most recently persisted report without
executing the collectors again.

`history` loads persisted reports in newest-first order without modifying
the snapshot archive or `latest.json`. The optional `--limit` argument
controls the maximum number of reports returned.

The default storage layout is:

```text
/mnt/storage/configs/atlas/operations/
├── latest.json
└── history/
    └── <generated-at>.json
```

Stored reports are reconstructed through the Operations domain models.
Schema versions, identities, child contracts, timestamps, and canonical
inputs are validated, while derived status, score, summary, and attention
fields are recomputed.

Historical listing is implemented through concise human output and a
wrapped JSON contract containing `count` and complete validated reports.

Report comparison, scheduling, APIs, and Portal visualization remain
planned extensions.

See `docs/OPERATIONS.md` for the complete command and persistence contract.

## Documentation

| Document | Purpose |
|---|---|
| `CHARTER.md` | Mission, scope, and governing principles |
| `ARCHITECTURE.md` | High-level platform architecture |
| `ROADMAP.md` | Releases, milestones, and planned bundles |
| `CHANGELOG.md` | Notable changes |
| `BUILD_LOG.md` | Engineering implementation history |
| `docs/MATURITY.md` | Capability and production maturity |
| `docs/OPERATIONS.md` | Operational procedures |
| `docs/CONFIGURATION.md` | Configuration reference |
| `docs/guides/ADMINISTRATOR_GUIDE.md` | Administrator workflows |
| `docs/ADR/` | Architecture Decision Records |
| `docs/EDR/` | Engineering Decision Records |

Documentation must describe the implemented repository rather than only the intended future state.

---

## Security

Atlas is a private platform but must still be operated as a production service.

Minimum expectations include:

- never commit secrets
- keep `.env` files outside distributable archives
- use least-privilege service credentials
- protect public routes with authentication and authorization
- maintain backups
- validate restoration procedures
- update dependencies deliberately
- preserve audit records
- review public ingress exposure
- rotate credentials after suspected disclosure

---

## Contribution expectations

Changes to Atlas should:

- follow the Charter and Engineering Philosophy
- preserve backward compatibility unless migration is explicitly approved
- extend existing architecture before introducing replacements
- include focused tests
- update relevant documentation
- preserve model contracts
- avoid duplicate sources of truth
- avoid generated files and secrets in Git
- include clear verification commands
- use small, reviewable commits

---

## Release strategy

### Atlas v1.0

Deliver a dependable friends-and-family Media and Sports platform with a usable Portal, secure access, reliable operations, and production documentation.

### Atlas v1.1

Continue platform improvements while preserving a stable v1.0 deployment experience.

### Atlas v2.0

Coordinate major distributed and infrastructure-dependent capabilities with the planned larger Proxmox cluster, resilient storage, backup, disaster recovery, and long-term scaling work.

---

## License and use

Project Atlas is currently a private project intended for personal, friends, and family use.

No public redistribution or external support commitment is implied unless the project adopts a formal license in the future.
