# Changelog

All notable changes to Project Atlas are documented in this file.

## [Unreleased]

### Fixed

- Prevented Service Doctor from double-counting a missing Docker health check as both an observability warning and a degraded-health warning.


### Documentation

- Added the Atlas User Acceptance Certification guide covering critical end-user and administrator journeys, accessibility, responsiveness, performance, failure handling, defect classification, and approval.
- Added the permanent Atlas Release Checklist documenting the engineering, operational, documentation, security, recovery, certification, packaging, publication, and post-release validation requirements.

- Established the Atlas v1.0 Release Plan, locking product scope, release blockers, acceptance criteria, user-experience certification, and the execution sequence to v1.0.0.
- Added the Atlas Release Policy defining release readiness, validation, certification, approval, publication, maintenance, and end-of-life requirements.
- Added the Atlas Versioning and Contributing Standard defining semantic versioning, branches, commits, review, compatibility, deprecation, and merge requirements.
- Added the Atlas ADR Policy governance document defining architectural decision criteria, lifecycle, status, structure, review, and validation.
- Added the Atlas Documentation Standard governance document defining architecture, API, CLI, operational, governance, release, and living-document requirements.
- Added the Atlas Testing Standard governance document defining automated, runtime, compatibility, repository, and release-audit validation requirements.
- Added the Atlas Coding Standards governance document defining permanent coding conventions.
- Added the Atlas Development Workflow governance document defining the canonical engineering sprint lifecycle.
- Added the Project Atlas Engineering Charter, formalizing the project's mission, engineering principles, repository philosophy, subsystem standards, development lifecycle, and definition of done.
- Established the Atlas Governance, engineering-specification, and release-certification documentation foundations.
- Completed Service Lifecycle architecture, CLI, and Python API documentation, including compatibility paths, JSON contracts, Administration Portal integration, and the v1.0 read-only boundary.

### Added

- Read-only `atlas service history` CLI for global and service-specific Maintenance History, with human-readable and canonical JSON output.
- Read-only `ServiceMaintenanceHistoryService` with validated global and service-specific history, concrete empty provider defaults, identity enforcement, compatibility exports, and dedicated tests.
- Immutable Service Lifecycle maintenance-history contracts: `MaintenanceAction`, `MaintenanceResult`, `MaintenanceRecord`, and `MaintenanceReport`, with normalized timestamps, deterministic ordering, aggregation, serialization, public exports, and dedicated tests.
- Read-only `atlas service updates` CLI with human-readable and canonical JSON output backed by `ServiceUpdateService`.
- Provider-independent `ServiceUpdateService` orchestration with validated single-service inspection, deterministic platform reports, identity enforcement, and provider error translation.
- Permanent Atlas engineering tooling layout under `tools/` and a canonical engineering guide covering architecture, testing, documentation, cleanup, commit, and release standards.
- Read-only Service Lifecycle provider update metadata through `inspect_update()`, with conservative local-only classification and correct digest-pinned image handling.
- Immutable Service Lifecycle update-discovery contracts: `UpdateStatus`, `ImageReference`, `ServiceUpdate`, and `UpdateReport`, with normalization, validation, deterministic serialization, public exports, and dedicated tests.
- Read-only `atlas service doctor` diagnostics in human-readable and JSON formats.
- Canonical Service Doctor CLI contract shared with future API and Admin Portal integrations.



### Service Lifecycle

#### Added

- Service Lifecycle domain architecture documented in ADR 0010.
- Immutable `ManagedService`, `ServiceImage`, `ServiceRuntime`,
  `ServiceHealth`, and `ServiceHealthStatus` contracts with normalization,
  validation, serialization, package exports, and dedicated Core tests.
- Provider-independent `ServiceLifecycleProvider` contract and
  `ServiceLifecycleService` orchestration layer.
- Read-only `DockerComposeProvider` support for configured-service discovery,
  individual service inspection, normalized runtime state, image identity,
  restart counts, dependency reporting, and health evaluation.
- `atlas service list [--json]` for normalized managed-service discovery.
- `atlas service show <identifier> [--json]` for combined identity, runtime,
  image, and health inspection.
- `atlas service runtime <identifier> [--json]` for focused runtime reporting.
- `atlas service health <identifier> [--json]` for focused health reporting.
- `atlas service health [--json]` for provider-independent aggregate infrastructure health reporting.
- Aggregate infrastructure scoring, status counts, services requiring attention, warnings, errors, and evaluation timestamps.
- Human-readable infrastructure health dashboard and normalized JSON contract for automation and future API and Portal consumers.
- Immutable `ServiceRuntimeEntry` and `InfrastructureSummary` report contracts.
- `atlas service summary [--json]` for provider-independent runtime, enablement,
  health, score, status, attention, provider, Compose project, and timestamp totals.
- Canonical subsystem architecture documentation under `docs/architecture/`.
- Backward-compatible `atlas services [--json]` alias backed by the Service
  Lifecycle domain instead of raw `docker compose ps` output.
- Responsive phone and tablet administration requirements added to the M-018
  Admin Portal roadmap.

#### Changed

- Backward-compatible Service Lifecycle service-package refactor, moving lifecycle, Doctor, and Update Discovery implementations under `atlas.service_lifecycle.services` while preserving legacy imports.
- Adopted guarded full-file heredoc rewrites for future Project Atlas changes
  after incremental text-patch installers proved too sensitive to normal code
  evolution.
- Service Lifecycle development remains read-only first; start, stop, restart,
  pull, update, and rollback operations remain intentionally deferred until
  authorization, planning, locking, validation, and audit boundaries exist.
- `atlas service health` now supports both aggregate infrastructure reporting and
  existing per-service health inspection without changing the provider contract.
- Aggregate evaluation is owned by `ServiceLifecycleService`; the CLI renders the
  normalized report and does not implement health business rules.
- Infrastructure summary orchestration is owned by `ServiceLifecycleService`,
  reuses one managed-service inventory, and keeps provider and rendering concerns
  separated.
- Formalized subsystem architecture documents as stable design specifications,
  distinct from roadmap planning, changelog release notes, and build history.

#### Validation

- Validated live read-only discovery across 15 Docker Compose services.
- Validated live identity, runtime, image, and health output for Jellyfin,
  Sonarr, qBittorrent, Gluetun, and other Atlas-managed services.
- Verified 17 focused Service Lifecycle CLI contracts.
- Verified the complete Core regression suite with 1,379 passing tests and
  104 passing subtests.
- Verified 70 focused aggregate-health service and CLI tests.
- Verified 534 Service Lifecycle regression tests.
- Verified the current Atlas Core regression suite with 648 passing tests and
  five passing Sports integration suites.
- Live-validated aggregate reporting across 15 managed services with an overall
  score of 89/100, a Degraded status, zero unhealthy services, zero unknown
  services, and no aggregate errors.
- Confirmed that 11 running services were degraded only because no Docker health
  check is configured.
- Verified 76 focused infrastructure-summary service and CLI tests.
- Verified 540 Service Lifecycle regression tests.
- Re-verified the full Atlas Core suite with 648 passing tests and five passing
  Sports integration suites.
- Live-validated the infrastructure summary across 15 enabled services: 15 running,
  zero stopped, restarting, failed, or unknown; score 89/100; status Degraded; and
  11 services requiring attention because Docker health checks are not configured.

### Added

- Media Library Detail domain model.
- Media Library Detail API schema.
- Media Library Detail service layer.
- `GET /api/v1/media/libraries/{library_id}` endpoint.
- Comprehensive unit and integration tests for the complete media library detail pipeline.


<!-- AEB-0002.4: authorization-enforcement -->

<!-- M-016.1a: media-contract-boundary -->
- Removed Dashboard-named transport contract imports from the Media feature.
- Added adapter-local Media transport DTOs while preserving the temporary `/dashboard/media` endpoint.
- Moved refresh-state publication from component render into a React effect.
- Strengthened architectural validation so Dashboard feature contracts cannot leak into `features/media`.

<!-- M-016.1: media-portal-foundation -->
- Added the first protected Portal feature route at `/portal/media` with server-owned browser metadata.
- Introduced a Media-owned domain model, authenticated endpoint adapter, loading hook, summary cards, library cards, empty state, partial-availability presentation, request failure recovery, and refresh control.
- Reused the existing dashboard media transport behind a Media feature boundary without coupling the feature to dashboard domain types.
- Added model and component regression coverage for normalization, identity validation, timestamps, aggregate totals, loading, empty, unavailable, and error presentations.

<!-- PAI-0005.2: portal-route-model -->
- Replaced navigation-only route records with a canonical typed Portal route model.
- Derived navigation sections, permission visibility, page titles, and active-route matching from the shared route catalog.
- Migrated the dashboard and navigation links to registered route metadata while preserving current Portal behavior.
- Added regression coverage for route identity, unique paths, section projection, exact dashboard matching, nested feature matching, route lookup, and authorization-aware navigation.

<!-- PAI-0004.2: portal-page-authorization-boundary -->
- Added a canonical permission-aware Portal page boundary with standardized headers, content framing, action slots, and access-denied presentation.
- Migrated the system dashboard from an inline permission guard to the reusable Portal page contract.
- Added component regression coverage for authorized rendering, denied rendering, contextual denial copy, optional presentation regions, and protected child isolation.

<!-- PAI-0003: portal-effective-authorization-migration -->
- Migrated Portal presentation checks and navigation filtering to API-resolved effective grant and denial patterns.
- Removed the duplicated Portal role-to-permission catalog while preserving stable typed permission identifiers.
- Added regression coverage for direct grants, wildcard grants, explicit-denial precedence, empty authorization state, and authorization-aware navigation.

<!-- PAI-0002: effective-authorization-session-contract -->
- Extended the authenticated-user API contract with resolved role, grant, and denial patterns so Portal clients can consume API-owned effective authorization state.
- Added `/auth/me` regression coverage for role aliases, multiple-role merging, direct permission grants, and explicit permission denials.

### Authorization

- Enforced `atlas.dashboard.read` on the operational dashboard summary endpoint.
- Enforced `media.read` on the media-library dashboard endpoint.
- Preserved `/api/v1/health` as a public liveness endpoint.
- Added dashboard route regression coverage for successful access, stable response contracts, unauthenticated requests, and permission-denied requests.

### Added

- One-shot scheduler execution for due or named tasks with subprocess isolation, runtime locking, stale-lock recovery, success/failure metadata, bounded history, and best-effort module events.
- `atlas scheduler run`, `atlas scheduler dry-run`, and `atlas scheduler history` commands.
- `atlas test [all|core|sports]` as the authoritative repository-wide validation command.
- Provider-neutral favorites service with Jellyfin item validation, automatic metadata enrichment, and best-effort favorite lifecycle events.
- Jellyfin REST adapter using the configured Atlas URL and API key.
- Favorites infrastructure with durable per-user media relationships, metadata-only storage, atomic persistence, filtering, removal, and consistency verification.
- Atlas Favorites CLI commands to add, remove, list, show, and verify favorite relationships.
- Username-or-user-ID resolution through the Atlas user profile store.
- JSON output, relationship-based removal, filters, metadata input, and stable exit codes for Favorites CLI operations.
- Dependency-free WSGI registration portal with invitation validation, secure form handling, friendly success and error pages, and no-store security headers.
- Transactional invitation redemption and registration service with external user provisioning, Atlas/Jellyfin identity linkage, compensating rollback, and best-effort audit event delivery.
- Rollback-safe Atlas profile deletion for failed multi-system registration transactions.
- Invitation lifecycle CLI for issuing, listing, inspecting, revoking, verifying, and cleaning up invitations.
- Atlas identity infrastructure with secure hashed invitation tokens, durable lifecycle storage, expiration handling, and consistency verification.
- Atlas user identity and profile framework with Jellyfin linkage, optional personal fields, atomic storage, validation, and user-management CLI commands.
- Foundational Atlas Health Engine with a normalized Python data model and JSON report output.
- `atlas health` command for machine-readable foundational health reporting.
- Shared shell health-result helpers and Core health-engine unit tests.
- Shared Atlas Core Python event publisher in `atlas/events.py`.
- Discoverable unit tests for Core event publishing.
- `atlas retention evaluate` CLI.
- human-readable retention reports.
- JSON retention output.
- Retention CLI regression tests.
- Atlas API refresh-token endpoint at `POST /api/v1/auth/refresh`, returning a rotated access and refresh token pair.

### Improved

- Jellyfin user linking now validates the supplied Jellyfin user ID against the Jellyfin API before persisting the association.
- Jellyfin user validation preserves an existing valid link when a replacement ID is rejected.
- Jellyfin provider errors now use resource-neutral not-found messaging for both media and user lookups.
- Sports worker and controller now use the shared Core event publisher.
- Core scheduler validation now runs through standard `unittest` discovery.
- Python compilation, Atlas Core unit tests, and Sports integration tests are unified behind one CLI entry point.
- Nested module `.env` files are explicitly ignored.
- Access-token and refresh-token identity resolution now share one validated active-profile resolution path.

### Validation

- Added focused Jellyfin provider tests for valid users, malformed responses, mismatched identities, and not-found responses.
- Added user CLI tests confirming valid Jellyfin IDs are persisted only after provider validation.
- Added regression coverage confirming invalid Jellyfin IDs are rejected without overwriting an existing valid link.
- Verified the complete repository test suite with 119 passing tests.
- Live-tested Jellyfin API authentication, user discovery, valid identity linking, invalid identity rejection, and preservation of the prior valid association.
- Added authentication refresh route coverage for successful rotation, invalid identity, user mismatch, empty tokens, and unknown request fields.
- Verified the complete Atlas API regression suite with 98 passing tests.

### Authenticated Services

- Added a shared authenticated service request boundary for protected Portal API operations.
- Removed access-token parameters from dashboard services and dashboard feature APIs.
- Removed direct access-token handling from dashboard hooks.
- Centralized active-session token resolution inside the authentication service boundary.
- Preserved explicit token handling for login, refresh, and current-user authentication operations.
- Added regression coverage for authenticated service requests and unavailable sessions.

### Portal Authentication

- Added single-flight Portal access-token rotation for concurrent authenticated requests.
- Added automatic one-time replay of requests rejected with HTTP 401 after successful token rotation.
- Added typed authentication, authorization, and expired-session client errors.
- Added authentication lifecycle observations for refresh start, success, failure, and session expiration.
- Preserved HTTP 403 responses as authorization failures without attempting token refresh.
- Added focused regression coverage for refresh sharing, replay behavior, refresh failure, repeated HTTP 401 responses, and HTTP 403 handling.

### Added

- Production public ingress stack
- Modular Caddy configuration
- Automatic HTTPS via Let's Encrypt
- HTTP/2 and HTTP/3 support
- Automatic HTTP → HTTPS redirection
- Production security headers
- Structured access logging
- Persistent TLS certificate storage
- Cloudflare-ready ingress architecture

### Infrastructure

- Atlas is now publicly available at:

  https://atlas.shadowinc.co

- Added modular Caddy configuration:
  - snippets/
  - sites/

- Added persistent Caddy storage:
  - certificates
  - configuration
  - logs

### Security

- Strict-Transport-Security
- X-Content-Type-Options
- X-Frame-Options
- Referrer-Policy
- Permissions-Policy
- Cross-Origin-Opener-Policy
- Removed Server header

## [1.0.0] — Production Foundation

### Added

#### Atlas Retention Intelligence

- Health Engine.
- Analytics Engine.
- Forecast Engine.
- Recommendation Engine.
- Immutable historical snapshots.
- Shared configuration architecture.
- Jellyfin server, library, and user adapters.
- Jellyfin aggregate metrics.
- Human-readable operational reports.
- Machine-readable snapshot schema.
- Library and library-path validation.
- Filesystem-to-Jellyfin synchronization analysis.
- Historical snapshot comparison.
- Operational change summaries.
- Byte-accurate storage metrics.

#### Health

- Health scoring.
- Platform, media, Docker, VPN, storage, project, and Git checks.
- Machine-readable and human-readable health reporting.
- Automatic discovery of enabled module health providers.
- Normalized JSON health-provider contract for Atlas modules.
- Sports runtime health reporting for containers, heartbeat, providers, and endpoint reachability.

#### Forecasting and Recommendations

- Daily storage growth calculations.
- Time-normalized forecasting.
- 30-day projection.
- Estimated storage exhaustion date.
- Forecast confidence.
- Storage, health, capacity, and forecast recommendations.

#### Scheduler

- Persistent scheduler records with task definitions, execution counters, descriptions, callbacks, module ownership, enablement, and timing metadata.
- Scheduler task registration, inspection, listing, and removal through the Atlas CLI.
- Compatibility with existing interval and lifecycle callers while adding stored-interval scheduling.

#### Infrastructure

- Improved Atlas CLI.
- Enhanced validation framework.
- Runtime state management.
- Modular service architecture.

### Improved

- ARI script organization.
- Snapshot schema and report formatting.
- Documentation coverage.
- `atlas doctor` migration to the shared Health Engine text renderer.

## [0.5.0] — Retention Intelligence Foundation

### Added

- Atlas Retention Intelligence foundation.
- Immutable operational snapshots.
- Shared Atlas configuration.
- Jellyfin server integration.
- Jellyfin library and user discovery.
- Library and library-path validation.
- Human-readable ARI reporting.
- Cleanup evaluation framework
- Cleanup decision model
- Cleanup service
- atlas cleanup evaluate CLI
- JSON and human-readable cleanup output
- Cleanup CLI shell integration

### Improved

- Configuration centralization.
- Validation framework.
- Runtime state separation.
- Snapshot schema.

## [0.4.0] — Initial Media Platform

### Added

- Initial Docker media stack.
- Windscribe VPN through Gluetun.
- qBittorrent routed through the VPN.
- Sonarr and Radarr connected to qBittorrent.
- Homepage dashboard.
- Environment template.
- Configuration documentation.

### Added

- Cleanup execution planning infrastructure with normalized execution models and reports.
- Provider-neutral CleanupExecutionService for converting cleanup scan reports into non-destructive execution plans.
- `atlas cleanup execute` CLI with human-readable and JSON output.
- Dry-run cleanup execution planning for Jellyfin libraries.
- Cleanup execution CLI regression tests.

### Validation

- Added cleanup execution model, service, and CLI regression coverage.
- Verified focused cleanup execution tests (13 passing).
- Verified cleanup regression suite (70 passing).
- Verified full Atlas Core regression suite (229 passing).
- Live-tested `atlas cleanup execute jellyfin --dry-run` in human-readable and JSON modes.
