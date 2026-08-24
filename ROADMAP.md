# Project Atlas Roadmap

> **Mission:** Build a reliable, observable, secure, and simple platform that
> gives friends and family a seamless Media and Sports experience without
> exposing the underlying infrastructure.

---

# Release Strategy

Project Atlas follows a stability-first release model.

## Atlas v1.0

Deliver a dependable friends-and-family Media and Sports platform.

Users must be able to use Atlas without interacting directly with Docker,
Proxmox, Jellyfin administration, Sonarr, Radarr, Prowlarr, qBittorrent, or
other backend services.

## Atlas v1.1

Continue platform development in the background while users remain on a stable
v1.0 deployment.

Changes will be released through tested updates and planned maintenance
windows.

## Atlas v2.0

Coordinate the next major Atlas release with migration to a larger Proxmox
cluster providing:

- Additional compute resources
- Additional storage capacity
- High availability
- Replication
- Durable backup infrastructure
- Disaster recovery
- Long-term platform scalability

Major distributed capabilities and infrastructure-dependent modules are
reserved for this release.

---

# Current Release

## v0.9.x — Release Candidate Development

**Status:** Active development

**Primary objective:** Complete the stable v1.0 Media and Sports experience.

The v1.0 scope is feature-frozen around user experience, reliability,
operations, and production readiness. Features that are not required for that
objective will be scheduled for v1.1 or v2.0.

---

# Atlas Core Services

Atlas Core Services provide reusable platform capabilities to all Atlas
applications and modules.

- Identity
- Access Control
- Authorization
- Scheduler
- Events
- Health
- Retention
- Cleanup
- Configuration
- Module Registry
- Audit

Media, Sports, Monitoring, Game Servers, and future capabilities consume these
core services rather than implementing separate platform foundations.

---

# Completed Foundations

## Infrastructure

- [x] Proxmox LXC deployment
- [x] Docker infrastructure
- [x] Persistent storage architecture
- [x] Gluetun VPN networking
- [x] qBittorrent VPN isolation
- [x] Intel Quick Sync device availability
- [x] Service configuration persistence
- [x] Atlas backup framework
- [x] Git-based source control workflow

## Media Stack

- [x] Jellyfin
- [x] Jellyseerr
- [x] Sonarr
- [x] Sonarr Anime
- [x] Radarr
- [x] Radarr Anime
- [x] Prowlarr
- [x] Bazarr
- [x] Maintainerr
- [x] qBittorrent
- [x] Homepage
- [x] Dozzle
- [x] Unpackerr
- [x] Tautulli

## Atlas Operational Platform

- [x] Atlas CLI framework
- [x] Health diagnostics
- [x] Verification workflow
- [x] Service status reporting
- [x] Module framework
- [x] Scheduler framework
- [x] Persistent scheduler runtime
- [x] Event framework
- [x] Backup retention
- [x] Configuration framework
- [x] Documentation foundation

## Atlas Retention Intelligence

- [x] Health engine
- [x] Immutable snapshots
- [x] Historical storage analysis
- [x] Library growth analysis
- [x] Trend analysis
- [x] Storage forecasting
- [x] Capacity forecasting
- [x] Health recommendations
- [x] Storage recommendations
- [x] Forecast recommendations
- [x] Policy decision models
- [x] Retention decision service
- [x] Cleanup decision models
- [x] Cleanup planning service
- [x] Cleanup execution foundation

## Identity Foundation

- [x] User profile persistence
- [x] User profile validation
- [x] Multiple-role support
- [x] Permission overrides
- [x] Owner protection
- [x] Invitation persistence
- [x] Secure invitation tokens
- [x] Invitation lifecycle CLI
- [x] Registration service
- [x] Registration web experience
- [x] Jellyfin identity provisioning
- [x] Registration rollback
- [x] Registration audit events
- [x] Favorites persistence
- [x] Favorites CLI
- [x] User profile regression coverage

## API and Portal Foundation

- [x] Select Next.js for the Atlas Portal
- [x] Select FastAPI for the Atlas API
- [x] Define frontend, API, and core boundaries
- [x] Define the `/api/v1` namespace
- [x] Define single-origin public routing
- [x] Define server-managed authentication
- [x] Scaffold the Atlas API
- [x] Scaffold the Atlas Portal
- [x] Add API health contracts
- [x] Add authentication foundation
- [x] Add current-user authentication
- [x] Add reusable authorization dependencies
- [x] Enforce authorization on authenticated user endpoints
- [x] Add public-ingress architecture
- [x] Media library detail domain model
- [x] Media library detail service
- [x] Media library detail API schema
- [x] Media library detail endpoint
- [x] Media library detail API contract tests

---

# v1.0 Release Milestones

## M-018 — Atlas Infrastructure Management

**Status:** In progress

**Goal:** Provide a safe, observable, and reusable service-lifecycle platform
for Atlas-managed infrastructure.

### Service Lifecycle Foundation

- [x] Define Service Lifecycle domain architecture
- [x] Add normalized managed-service models
- [x] Add service image and runtime-state models
- [x] Add service health models
- [x] Add update-plan and update-result models
- [x] Add maintenance-event models
- [x] Add provider-independent service contracts
- [x] Add provider-independent orchestration service
- [x] Add dedicated domain tests
- [x] Export public contracts through the package `__init__.py`

### Docker Compose Provider

- [x] Discover Atlas-managed Compose services
- [x] Normalize container runtime state
- [x] Normalize Docker health status
- [x] Inspect configured and running images
- [x] Inspect image identifiers and digests when available
- [x] Report container timestamps and restart counts
- [x] Report service dependencies
- [x] Distinguish running, stopped, restarting, and failed services
- [x] Preserve read-only behavior during the discovery phase

### Service Health and Reporting

- [x] Add managed-service listing
- [x] Add individual service inspection
- [x] Add aggregate infrastructure health
- [x] Add normalized infrastructure summary
- [x] Add service doctor diagnostics
- [x] Add service dependency graph
- [x] Add update-availability inspection
- [x] Add human-readable reports
- [x] Add machine-readable JSON reports
- [x] Add maintenance history
- [ ] Add audit events for lifecycle operations

### Guarded Lifecycle Operations

- [ ] Add administrator authorization requirements
- [ ] Add allow-listed service identifiers
- [ ] Add update dry-run planning
- [ ] Add guarded single-service updates
- [ ] Add service restart controls
- [ ] Add pre-update state capture
- [ ] Add post-update health validation
- [ ] Add dependency-aware update ordering
- [ ] Add operation locking
- [ ] Add failed-update rollback
- [ ] Add bulk-update planning
- [ ] Add scheduled maintenance-window support

### CLI and API

- [x] Add `atlas service list [--json]`
- [x] Preserve `atlas services [--json]` as a compatibility alias
- [x] Add `atlas service show <service> [--json]`
- [x] Add `atlas service runtime <service> [--json]`
- [x] Add `atlas service health <service> [--json]`
- [x] Add aggregate `atlas service health [--json]`
- [x] Add `atlas service summary [--json]`
- [x] Add `atlas service doctor [--json]`
- [x] Add `atlas service graph [--json]`
- [x] Add `atlas service updates`
- [x] Add `atlas service history`
- [ ] Add `atlas service update <service> --dry-run`
- [x] Add read-only Service Lifecycle API endpoints
- [ ] Add guarded lifecycle mutation API endpoints
- [x] Add read-only lifecycle API authorization tests
- [ ] Add guarded lifecycle mutation API authorization tests
- [x] Add lifecycle CLI contract tests

### Admin Portal Integration

- [x] Add managed-service overview
- [x] Add service health cards
- [x] Add update-availability indicators
- [x] Add service detail views
- [ ] Add restart confirmation workflow
- [ ] Add guarded update confirmation workflow
- [x] Add maintenance-history view
- [ ] Add failure and rollback reporting
- [x] Add responsive phone and tablet administration layouts
- [x] Add touch-friendly lifecycle controls
- [x] Add mobile-safe service cards and tables
- [x] Evaluate Progressive Web App support after responsive validation

---

## M-019 — Atlas Portal and API

**Status:** In progress

**Goal:** Provide the single supported user-facing entry point for Atlas.

### Portal Foundation

- [x] Next.js application foundation
- [x] Portal Docker image
- [x] Portal Compose integration
- [x] FastAPI service foundation
- [x] API Docker image
- [x] API health endpoint
- [x] API contract tests
- [x] Public routing architecture
- [x] Complete production Caddy routing
- [ ] Complete service health checks
- [ ] Complete portal and API deployment verification

### Authentication Experience

- [x] Authentication models
- [x] Authentication service foundation
- [x] Jellyfin authentication provider
- [x] Current-user endpoint
- [x] API authorization dependencies
- [ ] Complete login page
- [ ] Complete logout workflow
- [ ] Complete session expiration
- [ ] Complete session revocation
- [ ] Complete protected Portal layout
- [ ] Complete authentication audit events
- [ ] Complete account recovery documentation

### Shared User Experience

- [ ] Responsive application shell
- [ ] Role-aware navigation
- [ ] Loading states
- [ ] Empty states
- [ ] User-facing error states
- [ ] Accessibility baseline
- [ ] Mobile and tablet verification
- [ ] Browser compatibility verification

---

## M-020 — Atlas Access Control Platform

**Status:** In progress

**Goal:** Provide one consistent authorization platform for Atlas Core Services,
applications, and modules.

### Completed Foundation

- [x] Existing authorization catalog
- [x] Existing authorization service
- [x] Wildcard permission evaluation
- [x] Explicit permission grants
- [x] Explicit permission denials
- [x] Multiple-role permission merging
- [x] Legacy role aliases
- [x] Protected owner semantics
- [x] FastAPI permission dependencies
- [x] FastAPI role dependencies
- [x] ACP package foundation
- [x] Immutable ACP domain models
- [x] Permission definition model
- [x] Permission grouping model
- [x] Permission registry foundation
- [x] Ownership model
- [x] Public, Private, and Shared visibility
- [x] Resource quota model
- [x] Audit event model
- [x] ACP domain tests
- [x] Existing authorization regression verification

### Required for v1.0

- [ ] Built-in permission catalog
- [ ] Built-in role catalog
- [ ] Protected system-role definitions
- [ ] Read Only User role
- [ ] Default User role
- [ ] Media and Sports Administrator role
- [ ] ACP repository interfaces
- [ ] ACP service layer
- [ ] Existing authorization compatibility adapter
- [ ] User domain API
- [ ] Role-assignment API
- [ ] Permission catalog API
- [ ] Effective-permission resolver
- [ ] Portal user administration
- [ ] Portal role assignment
- [ ] Read-only effective-permission viewer
- [ ] Authorization audit events

### Deferred to v1.1

- [ ] Custom role creation
- [ ] Custom role editor
- [ ] Permission simulator
- [ ] Advanced permission overrides UI
- [ ] Role templates
- [ ] Role inheritance
- [ ] Full audit explorer
- [ ] Advanced ownership administration
- [ ] Advanced quota administration

---

## M-021 — Media and Sports Experience

**Status:** In Progress for v1.0

**Goal:** Allow friends and family to use Media and Sports without interacting
with backend services.

### User Dashboard

- [ ] Personalized home page
- [ ] Recently added media
- [ ] Continue Watching
- [ ] Current requests
- [ ] Upcoming sports
- [ ] Recent sports recordings
- [ ] Favorites summary
- [ ] Platform announcements

### Media Experience

- [x] Browse available media
- [x] Search available media
- [ ] Open media in Jellyfin
- [x] Request movies
- [ ] Request television series
  - [x] Preserve server-side TV request/provider capability
  - [x] Add normalized TV-series detail, season, and ongoing metadata
  - [x] Add fail-closed per-season availability and requestability state
  - [x] Add explicit server-owned standard-TV routing and submission preflight
  - [x] Add explicit Portal one-season request UX with no generic/all/current shortcut
  - [x] Derive the Portal TV request type from server-provided series classification
  - [x] Validate ongoing-series monitoring so future episodes can be acquired
        automatically through Seerr and Sonarr without a new Atlas request per episode
    - [x] Define Seerr service-level `monitorNewItems` ownership
    - [x] Pin the canonical Seerr runtime image in repository source
    - [x] Migrate the deployed Jellyseerr runtime to the canonical Seerr image
          under backed-up maintenance control
    - [x] Verify the standard-TV Sonarr service uses `monitorNewItems=all`
    - [x] Complete production E2E future-episode monitoring validation
- [ ] Request anime movies
- [ ] Request anime series
  - [x] Preserve server-side anime-TV request/provider capability
  - [x] Reuse normalized TV-series detail with server-side anime classification
  - [x] Reuse fail-closed per-season availability and requestability state
  - [x] Add explicit server-owned anime-TV routing and submission preflight
  - [x] Add explicit Portal one-season request UX with no generic/all/current shortcut
  - [x] Derive `anime_tv` from server-provided series classification
  - [x] Validate ongoing-series monitoring so future episodes can be acquired
        automatically through Seerr and Sonarr Anime without a new Atlas request per episode
    - [x] Define shared Seerr service-level `monitorNewItems` ownership
    - [x] Verify the Anime-TV Sonarr service uses `monitorNewItems=all`
    - [x] Complete production E2E future-episode monitoring validation
- [x] View request history
- [x] View request status
- [x] Cancel eligible requests
- [ ] Add favorites
- [ ] Remove favorites
- [ ] View personal favorites
- [ ] Display recently added content
- [ ] Display Continue Watching
- [ ] User-friendly media error handling

### Media Administration

- [ ] Review pending requests
- [ ] Approve requests when approval is required
- [ ] Reject requests with a reason
- [ ] View acquisition status
- [ ] Refresh metadata
- [ ] Scan media libraries
- [ ] Delete eligible media
- [ ] Block deletion of protected media
- [ ] Display retention decision reasons
- [ ] Display users protecting a media item

### Favorites and Retention

- [x] Favorites persistence foundation
- [x] Favorites service foundation
- [x] Favorite-aware policy foundation
- [x] Retention decision foundation
- [x] Cleanup decision foundation
- [ ] Connect Portal favorites to Atlas API
- [x] Protect favorited media from automatic deletion
- [x] Remove protection when the final favorite is removed
- [ ] Add personal favorite shortcuts
- [ ] Complete watched-media retention workflow
- [ ] Complete request-expiration workflow
- [ ] Complete deletion audit history
- [x] Verify cleanup dry-run and execution safeguards

### Sports Experience

- [x] Sports module foundation
- [x] Sports provider framework
- [x] Sports feed service
- [x] Sports controller service
- [x] Sports health integration
- [x] Sports scheduling foundation
- [x] Sports recording foundation
- [x] Browse upcoming events
- [ ] Search teams and leagues
- [x] Request sporting events
- [ ] View sports request status
- [ ] View scheduled recordings
- [ ] View completed recordings
- [ ] Open recordings in the supported playback experience
- [ ] Follow favorite teams
- [ ] Follow favorite leagues
- [ ] Auto-follow eligible favorite-team events
- [ ] Handle event cancellation and schedule changes
- [ ] Provide user-friendly sports failure states

### Sports Administration

- [ ] Review requested events
- [ ] Approve or reject sports requests
- [ ] Cancel scheduled events
- [ ] Manage recordings
- [ ] Delete eligible recordings
- [ ] View provider health
- [ ] View recorder health
- [ ] View scheduling conflicts
- [ ] View sports audit events

### User Settings

- [ ] View profile
- [ ] Update display name
- [ ] Update supported profile fields
- [ ] Configure notification preferences
- [ ] Configure subtitle preferences
- [ ] Configure preferred language
- [ ] Configure Media defaults
- [ ] Configure Sports defaults

---

## M-022 — Administration and Operations

**Status:** Required for v1.0

**Goal:** Allow Atlas administrators to operate the stable platform without
requiring routine direct access to individual backend applications.

### Administration Portal

The Administration Portal is a v1.0 release requirement. Atlas v1.0 must not be tagged until the supported administrator workflows below are implemented, authorized, tested, documented, and production-validated.

- [ ] Administrative dashboard
- [ ] User listing
- [ ] User detail view
- [ ] User activation and suspension
- [ ] Role assignment
- [ ] Invitation creation
- [ ] Invitation revocation
- [ ] Request queue
- [ ] Media operations
- [ ] Sports operations
- [ ] Retention status
- [ ] Cleanup status
- [ ] Module status
- [ ] System announcements

### Health and Observability

- [ ] System health dashboard
- [ ] Service health dashboard
- [ ] Storage dashboard
- [ ] Forecast dashboard
- [ ] Media statistics
- [ ] Sports health
- [ ] Recent failures
- [ ] Operational recommendations
- [ ] Structured error correlation
- [ ] User-safe outage messaging

### Notifications

- [ ] Invitation notification
- [ ] Request submitted notification
- [ ] Request approved notification
- [ ] Request rejected notification
- [ ] Media available notification
- [ ] Sports event scheduled notification
- [ ] Sports recording available notification
- [ ] Retention warning notification
- [ ] Administrative failure notification
- [ ] Notification preference enforcement

---

## M-023 — Production Readiness and v1.0 Release

**Status:** In Progress

**Goal:** Make Atlas safe for continuous friends-and-family use.


### Operations Foundation and CLI

- [x] Define immutable Operations domain contracts
- [x] Add deterministic section and attention ordering
- [x] Add the read-only System collector
- [x] Add the guarded Docker adapter and normalized provider
- [x] Add Docker runtime, health, restart, OOM, exit, and governance findings
- [x] Add deterministic multi-collector aggregation
- [x] Isolate collector failures
- [x] Add automatic hostname, version, Git, and UTC context discovery
- [x] Add human-readable and JSON Operations reports
- [x] Add the public `atlas operations report` command
- [x] Add Python CLI and shell integration tests
- [x] Persist immutable Operations reports
- [x] Add atomic `latest.json` retrieval
- [x] Add `atlas operations save`
- [x] Add `atlas operations latest`
- [x] Add report-history listing
- [x] Add `atlas operations history`
- [x] Add configurable newest-first history limits
- [x] Add human and wrapped JSON history output
- [x] Add immutable report-comparison contracts
- [x] Add deterministic finding comparison
- [x] Add human and JSON comparison renderers
- [x] Add `atlas operations compare`
- [x] Add optional unchanged-finding inclusion
- [x] Validate live comparison as read-only
- [x] Add the scheduled Operations collection callback
- [x] Register `operations.collect` through the shared scheduler
- [x] Integrate core jobs into unqualified `atlas scheduler sync`
- [x] Preserve scheduler runtime state during repeated synchronization
- [x] Isolate core Operations tasks from optional-module event routing
- [x] Validate live and subprocess scheduled collection
- [x] Validate scheduled history and comparison continuity
- [x] Add shared transport-neutral API version contracts
- [x] Add immutable API error and response envelopes
- [x] Add deterministic API serialization
- [x] Add FastAPI and OpenAPI envelope adapters
- [x] Preserve existing endpoint response compatibility
- [x] Validate API contracts against Operations domain models
- [x] Add read-only Operations report endpoint
- [x] Add latest persisted Operations endpoint
- [x] Add bounded Operations history endpoint
- [x] Add Operations comparison endpoint
- [x] Add the aggregate Operations Portal dashboard API
- [x] Add Portal-ready Operations summary widgets
- [x] Add Portal-ready Operations comparison widgets
- [x] Add bounded recent Operations attention widgets
- [x] Add Portal-ready Scheduler summary widgets
- [x] Add Scheduler runtime status visibility
- [x] Add bounded Scheduler failure visibility
- [x] Add the Operations Portal dashboard interface
- [x] Consume the aggregate Portal dashboard API
- [x] Normalize aggregate dashboard transport contracts
- [x] Reuse existing operational and media dashboard models
- [x] Reuse existing operational and media presentation components
- [x] Add Operations comparison and recent-attention panels
- [x] Add bounded Scheduler failure presentation
- [x] Remove all Portal dashboard placeholder sections

### Reliability

- [x] Complete full-stack health verification
  - [x] Refactor `atlas verify` into reusable verification sections
  - [x] Lock the `atlas doctor` delegation boundary
  - [x] Validate the canonical Atlas configuration contract
  - [x] Validate required runtime filesystem paths and writability
  - [x] Discover and verify active root Compose services
  - [x] Delegate ingress verification to its owned verifier
  - [x] Validate Scheduler registry readiness through the Scheduler CLI
  - [x] Discover and verify all enabled optional modules
  - [x] Aggregate failures without suppressing later verification sections
  - [x] Complete clean live Verify and Doctor validation
- [x] Complete startup-order verification
  - [x] Add normalized startup dependency and service contracts
  - [x] Translate Docker Compose configuration through the provider boundary
  - [x] Add deterministic Startup Policy results and evaluation
  - [x] Add read-only service orchestration
  - [x] Add human-readable and JSON CLI reporting
  - [x] Enforce fail-closed qBittorrent readiness through Gluetun health
  - [x] Validate the production startup policy as Healthy
- [x] Complete restart recovery verification
  - [x] Define Restart Recovery architecture and ADR 0012
  - [x] Add normalized observation, status, and result contracts
  - [x] Add deterministic provider-independent recovery evaluation
  - [x] Add read-only recovery observation orchestration
  - [x] Add human-readable and JSON CLI reporting
  - [x] Validate the production no-restart path as `not-observed`
  - [x] Perform an explicitly approved controlled live restart
  - [x] Validate the production restart path as `recovered`
- [x] Complete service dependency verification
- [x] Complete stale-state recovery verification
- [x] Complete scheduler recovery verification
- [x] Complete interrupted-request recovery verification
  - [x] Define Interrupted-Request Recovery architecture and ADR 0016
  - [x] Add durable `submitting` and `cancelling` request states
  - [x] Persist mutation intent before provider submission or cancellation
  - [x] Fail closed on outcome-ambiguous provider mutations
  - [x] Expose recovery-required requests through a read-only service boundary
  - [x] Complete read-only production validation
- [x] Complete Sports recovery verification
  - [x] Define Sports Recovery architecture and ADR 0017
  - [x] Persist PID and Linux process start-time recorder identity
  - [x] Fail closed on missing or mismatched recorder identity
  - [x] Prove unrelated processes are neither adopted nor signaled
  - [x] Validate recovery, scheduler, and full Sports regressions
  - [x] Complete read-only production validation
- [x] Verify automatic cleanup safeguards
  - [x] Define Automatic Cleanup Safety architecture and ADR 0018
  - [x] Preserve dry-run-only Atlas cleanup execution
  - [x] Prove favorite protection skips the provider preview boundary
  - [x] Prove unavailable policy state fails before provider action
  - [x] Prove Maintainerr assessment consumes Atlas protection decisions
  - [x] Validate production Maintainerr destructive configuration as disabled
  - [x] Validate the production Atlas cleanup workflow with zero mutations
- [x] Verify VPN fail-closed behavior
  - [x] Define VPN Fail-Closed Verification architecture and ADR 0019
  - [x] Prove qBittorrent has no independent network or published ports
  - [x] Prove Gluetun owns the shared namespace, tunnel, and firewall boundary
  - [x] Complete read-only production topology and healthy-egress validation
  - [x] Perform an explicitly approved controlled VPN-loss test
  - [x] Prove direct IPv4 egress is blocked while `tun0` remains absent
  - [x] Verify automatic VPN recovery and post-recovery Atlas health
- [x] Verify storage-full behavior
  - [x] Define Storage Exhaustion Recovery architecture and ADR 0020
  - [x] Prove atomic persistence preserves the last durable state on `ENOSPC`
  - [x] Normalize Media Request storage failures before provider mutation
  - [x] Compensate newly launched Sports recorders by exact process identity
  - [x] Publish backup archives only after temporary archive validation
  - [x] Complete read-only production validation without filling storage
- [x] Verify unavailable-provider behavior
  - [x] Define Unavailable-Provider Behavior architecture and ADR 0021
  - [x] Prove provider outages cannot become successful empty responses
  - [x] Preserve Media Request mutation intent and block ambiguous replay
  - [x] Preserve cleanup dry-run safety when provider preview fails
  - [x] Preserve Sports recordings and non-finished state during provider outage
  - [x] Complete read-only production provider-observability validation

### Deployment Safety

- [x] Define stable production branch
- [x] Define background development branch strategy
- [x] Define release branch workflow
- [x] Define maintenance-window procedure
- [x] Define pre-update backup procedure
- [x] Define post-update verification procedure
- [x] Define rollback procedure
- [x] Define schema migration procedure
- [x] Define configuration migration procedure
- [x] Prevent untested patches from reaching production
- [x] Add production maintenance mode
  - [x] Require protected `feature/fix -> release/<version> -> main` promotion
  - [x] Require the aggregate `release-gate` status check on protected sources
  - [x] Capture verified source archives and exact running image identities
  - [x] Preserve rollback image identities before pull/build mutation
  - [x] Keep maintenance and the deployment lock on failed post-change checks
  - [x] Verify healthy backends plus public HTTP 503 isolation during maintenance
  - [x] Reverify public ingress after maintenance before publishing a new baseline
  - [x] Complete controlled production failure, recovery, and repair validation
  - [x] Validate failed migration ownership through maintenance and deployment-lock retention
  - [x] Validate explicit recovery without rewriting the failed deployment outcome
  - [x] Repair and verify Sports writable-runtime ownership discovered during production recovery
  - [x] Complete the second controlled Jellyseerr-to-Seerr migration with the verified deployment transaction retained through runtime acceptance
  - [x] Certify standard-TV and Anime-TV server-owned routing, monitoring policy, and production E2E isolation under E2.5
  - [x] Harden target-artifact, isolation, lifecycle-ordering, and recovery contracts from E2.5 attempt #1
  - [x] Fail closed before first-party ingress pull/build when tracked build-context permissions are incompatible
  - [x] Restore captured image identities through verified transaction-scoped rollback aliases
  - [x] Require rollback recovery sources beneath the persistent Atlas deployment-record namespace
  - [x] Reconcile the exact 17-file checkout permission drift from `0600` to repository-authoritative `0644`
  - [x] Certify the combined RC deployment-safety remediation while preserving failed deployment evidence and the recovered production baseline

### Backup and Recovery

- [x] Verify Atlas configuration backups
- [x] Verify identity-state backups
- [x] Verify favorites-state backups
- [x] Verify request-state backups
- [x] Verify scheduler-state backups
- [x] Verify Sports-state backups
- [x] Verify retention-state backups
- [x] Complete restore test
- [x] Document recovery time expectations
- [x] Document single-host backup limitations

### Security

- [x] Complete authentication review
- [x] Complete authorization review
- [x] Complete invitation security review
- [x] Complete session-cookie review
- [x] Complete reverse-proxy security review
- [x] Complete secret-storage review
- [x] Complete API exposure review
- [x] Complete audit-event review
- [x] Complete dependency vulnerability review
- [x] Complete least-privilege review
- [x] Complete final v1.0 Security Acceptance
  - [x] Run current vulnerability and runtime security certification
  - [x] Remove Homepage direct Docker-socket access
  - [x] Replace Dozzle direct Docker-socket access with a private read-only proxy
  - [x] Prove Docker API mutation through the proxy is denied
  - [x] Certify proxy image at zero HIGH / zero CRITICAL findings
  - [x] Certify Atlas-owned fixable CRITICAL findings at zero
  - [x] Accept 19 remaining upstream Caddy HIGH findings for v1.0
  - [x] Reconcile certified `main` into `release/v1.0.0`
  - [x] Certify 22 running containers and zero unhealthy containers
  - [x] Provision the security audit journal through the certified update path
  - [x] Normalize stale extended ACL state and preserve minimal writer access
  - [x] Certify Atlas API audit-journal write access in production
  - [x] Certify real production Caddy hostname and TLS/SNI routing
  - [x] Prove invalid-login audit publication without credential disclosure

### Quality

- [x] Run full automated test suite
- [x] Add critical end-to-end tests
- [x] Add login journey test
- [x] Add media request journey test
- [x] Add favorite-protection journey test
- [x] Add Sports request journey test
- [x] Add administrator journey test
- [x] Complete responsive UI review
- [x] Complete accessibility review
- [x] Complete performance baseline
- [x] Complete sustained-use test
  - [x] Implement Q.6 sustained-use domain contracts and immutable evidence persistence
  - [x] Implement `atlas sustained-use start|sample|status|finalize`
  - [x] Implement idempotent `sustained-use.sample` Scheduler callback
  - [x] Integrate `sustained-use.sample` into unqualified Scheduler sync
  - [x] Certify the pre-activation implementation candidate without live Scheduler mutation or Q.6 persistence
  - [x] Publish the Q.6 instrumentation commit and restore clean Git health
  - [x] Register and certify the dormant live `sustained-use.sample` task
  - [x] Preserve and retire `q6-20260817T171504Z` as immutable `aborted` historical evidence after detecting missing recurring production Scheduler dispatch
  - [x] Implement, publish, install, and live-certify the repository-owned one-minute Scheduler dispatcher
  - [x] Implement and certify guarded retirement/archive support for incomplete Q.6 attempts
  - [x] Restore `sustained-use.sample` and prove autonomous Scheduler dispatch
  - [x] Establish fresh run `q6-20260817T232028Z` and certify its first autonomous production sample
  - [x] Detect deterministic cumulative cadence drift during the second production attempt despite zero Scheduler failures
  - [x] Retire `q6-20260817T232028Z` at `176/193` as immutable `aborted` temporal-cadence failure evidence
  - [x] Implement and certify T0-anchored fixed sampling slots
  - [x] Separate 900-second certification cadence from 60-second dispatch polling
  - [x] Enforce bounded 180-second lateness, hard missed-slot failure, and no backfill
  - [x] Add independent finalization-time fixed-slot validation
  - [x] Prove the fixed-slot evaluator retrospectively rejects the archived drifting production history
  - [x] Publish the Q.6A.5 fixed-cadence repair and synchronize the live `sustained-use.sample` task to 60-second polling
  - [x] Reverify dormant and accelerated autonomous fixed-slot behavior against the published repair
  - [x] Establish the final fresh Q.6 T0 against the repaired published candidate
  - [x] Collect 193 samples across a fresh uninterrupted 48-hour / 15-minute fixed-slot observation window
  - [x] Finalize and certify the complete sustained-use history
    - [x] Collect the complete uninterrupted 193/193 fixed-slot production history
    - [x] Preserve the original production finalization result as immutable failed evidence
    - [x] Diagnose the final Runtime Bus backlog race as a terminal-convergence defect
    - [x] Implement bounded Runtime Bus terminal convergence against the frozen sample-193 journal tail
    - [x] Certify the Q.6A.7 eight-file terminal-convergence repair candidate
    - [x] Reconcile, certify, commit, and publish the Q.6A.7 repair
    - [x] Perform the controlled post-publication release-certification step without rewriting historical Q.6 evidence
    - [x] Certify fresh exact-candidate run `q6-20260822T011449Z` at 193/193 with zero fixed-slot violations, zero Scheduler failures, bounded terminal convergence PASS, and durable `completed` status
    - [x] Preserve the complete sample history byte-identically and retain prior failed/aborted Q.6 evidence unchanged
- [x] Resolve release-blocking defects
  - [x] Close the missing production Scheduler dispatcher defect through committed, published, installed, and live-certified remediation

### Documentation

- [x] Reconcile Media discovery and Request architecture through E2.5 production acceptance
- [x] Update architecture documentation for remaining v1.0 surfaces
- [x] Complete administrator guide
- [x] Complete user guide
- [x] Complete installation guide
- [x] Complete upgrade guide
- [x] Complete rollback guide
- [x] Complete backup and restore guide
- [x] Complete troubleshooting guide
- [x] Document maintenance windows
- [x] Document known limitations
- [ ] Publish v1.0 release notes

### Release

- [x] Create v1.0 release candidate
- [ ] Deploy release candidate to production
  - [x] First exact `1.0.0-rc.1` production attempt failed closed and was
    recovered (`update-20260824T165151Z-3258027`).
  - [x] Deployment-safety remediation for build-context permissions,
    digest-safe rollback, and persistent recovery-source lifetime certified.
  - [x] Second exact `1.0.0-rc.1` production attempt failed closed at the
    post-apply ingress-readiness boundary (`update-20260824T222351Z-3794932`).
  - [x] Bounded read-only ingress-readiness remediation certified.
  - [ ] Complete a successful controlled exact-RC production retry.
- [ ] Complete controlled user pilot
- [ ] Complete stabilization period
- [ ] Resolve pilot defects
- [ ] Freeze release candidate
- [ ] Tag v1.0.0
- [ ] Publish v1.0.0
- [ ] Begin stable support

---

# v1.0 Definition of Done

Atlas v1.0 is complete when:

- Friends and family can sign in through the Atlas Portal.
- Users can browse and watch Media without backend access.
- Users can request movies, television, anime, and Sports.
- Users can view request status and receive availability notifications.
- Users can manage favorites.
- Favorites reliably protect Media from automated deletion.
- Users can access completed Sports recordings.
- Users can manage their supported account settings.
- Administrators can manage users, requests, Media, Sports, and health through
  Atlas.
- The Admin Portal provides the supported v1.0 service overview, diagnostics, updates, and maintenance-history experience.
- Routine user activity does not require direct access to backend services.
- Updates can be tested, scheduled, backed up, verified, and rolled back.
- Critical user journeys have automated or documented validation.
- Recovery procedures are documented and tested.
- Release-blocking defects are resolved.
- The production deployment passes the v1.0 readiness checklist.

---

# v1.1 Background Development

Development of v1.1 will occur separately from the stable user deployment.
Changes will reach production only through planned, tested maintenance windows.

## M-024 — Access Control Administration

- [ ] Custom roles
- [ ] Custom-role persistence
- [ ] Role editor
- [ ] Permission editor
- [ ] Permission simulator
- [ ] Effective-permission explanations
- [ ] Role templates
- [ ] Role inheritance
- [ ] Advanced permission overrides
- [ ] Ownership administration
- [ ] Quota administration
- [ ] Audit explorer

## M-025 — Portal and Module Extensibility

- [ ] Module permission self-registration
- [ ] Dynamic Portal navigation
- [ ] Module-provided settings pages
- [ ] Module-provided dashboards
- [ ] Module lifecycle administration
- [ ] Module SDK expansion
- [ ] Module developer documentation
- [ ] Optional module discovery
- [ ] Portal extension contracts

## M-026 — Intelligence and Personalization

- [ ] Usage analytics
- [ ] Enhanced storage forecasting
- [ ] Predictive retention
- [ ] Personalized recommendations
- [ ] Family recommendations
- [ ] Shared collections
- [ ] Advanced Continue Watching
- [ ] Smart-series subscriptions
- [ ] Enhanced Sports subscriptions
- [ ] Advanced notification routing
- [ ] Administrative reporting

## M-027 — Stable Operations Improvements

- [ ] Automated release packaging
- [ ] Automated upgrade verification
- [ ] Automated rollback assistance
- [ ] Extended backup validation
- [ ] Long-running reliability tests
- [ ] Expanded observability
- [ ] Maintenance-window automation
- [ ] Release-channel support
- [ ] v1.1 release preparation

---

# v2.0 Cluster and Longevity Platform

Atlas v2.0 begins with migration to a new Proxmox host cluster offering greater
compute, storage, resiliency, and room for long-term expansion.

## M-030 — Proxmox Cluster Foundation

- [ ] Select cluster hardware
- [ ] Establish quorum design
- [ ] Deploy Proxmox cluster
- [ ] Configure cluster networking
- [ ] Configure migration networking
- [ ] Configure redundant management access
- [ ] Define failure domains
- [ ] Define node maintenance procedures
- [ ] Validate live migration
- [ ] Validate host-failure recovery

## M-031 — Storage, Backup, and Disaster Recovery

- [ ] Select shared or distributed storage architecture
- [ ] Implement storage redundancy
- [ ] Implement storage replication
- [ ] Deploy dedicated backup infrastructure
- [ ] Add off-host backups
- [ ] Add offline or immutable backup copies
- [ ] Add retention policies
- [ ] Add restore verification
- [ ] Add disaster-recovery runbooks
- [ ] Validate full-platform recovery
- [ ] Define recovery-point objectives
- [ ] Define recovery-time objectives

## M-032 — Atlas Cluster Platform

- [ ] Cluster-aware service discovery
- [ ] Cluster-aware health monitoring
- [ ] Multi-node scheduler
- [ ] Distributed task execution
- [ ] Distributed module placement
- [ ] Cluster maintenance mode
- [ ] Rolling updates
- [ ] Service failover
- [ ] Workload evacuation
- [ ] Distributed state strategy
- [ ] Distributed storage integration
- [ ] Capacity-aware placement

## M-033 — Game Server Platform

- [ ] Dedicated game-server node capacity
- [ ] Game Server Builder role
- [ ] Game Server Administrator role
- [ ] Server ownership
- [ ] Public, Private, and Shared visibility
- [ ] Server request workflow
- [ ] Template library
- [ ] Automatic provisioning
- [ ] CPU quotas
- [ ] Memory quotas
- [ ] Storage quotas
- [ ] Port allocation
- [ ] Lifecycle management
- [ ] Console access
- [ ] Scheduled startup and shutdown
- [ ] Automatic updates
- [ ] Backup integration
- [ ] Restore integration
- [ ] Activity monitoring
- [ ] Administration Portal

### Initial Game Templates

- [ ] Minecraft
- [ ] Terraria
- [ ] Valheim
- [ ] Palworld
- [ ] Satisfactory
- [ ] ARK
- [ ] Factorio
- [ ] Rust

## M-034 — Long-Term Expansion

- [ ] Photos module
- [ ] Music module
- [ ] Home Automation module
- [ ] Additional optional modules
- [ ] Mobile companion application
- [ ] External integration API
- [ ] Module marketplace evaluation
- [ ] Long-term data migration tooling

---

# Explicitly Deferred from v1.0

The following capabilities must not delay the v1.0 release:

- Custom roles
- Permission simulator
- Role inheritance
- Dynamic Portal navigation
- Full module plugin UI
- Game server provisioning
- Multi-host Atlas
- Distributed scheduling
- Distributed storage
- High availability
- Live migration
- Home Automation
- Photos
- Music
- Mobile companion application
- Module marketplace

---

# Engineering Principles

- Simplicity over complexity
- Reliability over novelty
- Observability before automation
- Automation before repetitive manual intervention
- Documentation as a first-class feature
- Maintain stable subsystem architecture documents for mature domains
- Use design, implementation, focused validation, full regression, live validation,
  documentation, architecture review, commit, and push as the standard sprint flow
- Stable user experience over continuous production changes
- Test changes before production deployment
- Back up before production maintenance
- Verify after every production change
- Preserve rollback paths
- Keep modules optional
- Keep core services reusable
- Reserve infrastructure-breaking changes for major releases

---

## M-021 — Atlas Governance

**Status:** In Progress

**Goal:** Establish permanent, repository-owned engineering governance and
release-certification standards for Project Atlas.

### Planned Work

- [x] M-021.1 — Governance Foundation
- [x] Engineering Charter
- [x] Development Workflow
- [x] Coding Standards
- [x] Testing Standard
- [x] Documentation Standard
- [x] ADR Policy
- [x] Release Policy
- [x] Versioning and Contributing guidance
- [x] Release Certification framework
- [x] M-018 Service Lifecycle certification
- [x] Governance audit

Governance is a permanent project capability. Completion of M-021 establishes
the initial standards; later milestones continue to operate under them.
