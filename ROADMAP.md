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
- [ ] Add update-plan and update-result models
- [ ] Add maintenance-event models
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
- [ ] Add service doctor diagnostics
- [ ] Add service dependency graph
- [ ] Add update-availability inspection
- [x] Add human-readable reports
- [x] Add machine-readable JSON reports
- [ ] Add maintenance history
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
- [ ] Add `atlas service doctor [--json]`
- [ ] Add `atlas service graph [--json]`
- [ ] Add `atlas service updates`
- [ ] Add `atlas service history`
- [ ] Add `atlas service update <service> --dry-run`
- [ ] Add guarded lifecycle API endpoints
- [ ] Add lifecycle API authorization tests
- [x] Add lifecycle CLI contract tests

### Admin Portal Integration

- [ ] Add managed-service overview
- [ ] Add service health cards
- [ ] Add update-availability indicators
- [ ] Add service detail views
- [ ] Add restart confirmation workflow
- [ ] Add guarded update confirmation workflow
- [ ] Add maintenance-history view
- [ ] Add failure and rollback reporting
- [ ] Add responsive phone and tablet administration layouts
- [ ] Add touch-friendly lifecycle controls
- [ ] Add mobile-safe service cards and tables
- [ ] Evaluate Progressive Web App support after responsive validation

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
- [ ] Complete production Caddy routing
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

**Status:** Planned for v1.0

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

- [ ] Browse available media
- [ ] Search available media
- [ ] Open media in Jellyfin
- [ ] Request movies
- [ ] Request television series
- [ ] Request anime movies
- [ ] Request anime series
- [ ] View request history
- [ ] View request status
- [ ] Cancel eligible requests
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
- [ ] Protect favorited media from automatic deletion
- [ ] Remove protection when the final favorite is removed
- [ ] Add personal favorite shortcuts
- [ ] Complete watched-media retention workflow
- [ ] Complete request-expiration workflow
- [ ] Complete deletion audit history
- [ ] Verify cleanup dry-run and execution safeguards

### Sports Experience

- [x] Sports module foundation
- [x] Sports provider framework
- [x] Sports feed service
- [x] Sports controller service
- [x] Sports health integration
- [x] Sports scheduling foundation
- [x] Sports recording foundation
- [ ] Browse upcoming events
- [ ] Search teams and leagues
- [ ] Request sporting events
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

**Status:** Planned

**Goal:** Make Atlas safe for continuous friends-and-family use.

### Reliability

- [ ] Complete full-stack health verification
- [ ] Complete startup-order verification
- [ ] Complete restart recovery verification
- [ ] Complete service dependency verification
- [ ] Complete stale-state recovery verification
- [ ] Complete scheduler recovery verification
- [ ] Complete interrupted-request recovery verification
- [ ] Complete Sports recovery verification
- [ ] Verify automatic cleanup safeguards
- [ ] Verify VPN fail-closed behavior
- [ ] Verify storage-full behavior
- [ ] Verify unavailable-provider behavior

### Deployment Safety

- [ ] Define stable production branch
- [ ] Define background development branch strategy
- [ ] Define release branch workflow
- [ ] Define maintenance-window procedure
- [ ] Define pre-update backup procedure
- [ ] Define post-update verification procedure
- [ ] Define rollback procedure
- [ ] Define schema migration procedure
- [ ] Define configuration migration procedure
- [ ] Prevent untested patches from reaching production
- [ ] Add production maintenance mode

### Backup and Recovery

- [ ] Verify Atlas configuration backups
- [ ] Verify identity-state backups
- [ ] Verify favorites-state backups
- [ ] Verify request-state backups
- [ ] Verify scheduler-state backups
- [ ] Verify Sports-state backups
- [ ] Verify retention-state backups
- [ ] Complete restore test
- [ ] Document recovery time expectations
- [ ] Document single-host backup limitations

### Security

- [ ] Complete authentication review
- [ ] Complete authorization review
- [ ] Complete invitation security review
- [ ] Complete session-cookie review
- [ ] Complete reverse-proxy security review
- [ ] Complete secret-storage review
- [ ] Complete API exposure review
- [ ] Complete audit-event review
- [ ] Complete dependency vulnerability review
- [ ] Complete least-privilege review

### Quality

- [ ] Run full automated test suite
- [ ] Add critical end-to-end tests
- [ ] Add login journey test
- [ ] Add media request journey test
- [ ] Add favorite-protection journey test
- [ ] Add Sports request journey test
- [ ] Add administrator journey test
- [ ] Complete responsive UI review
- [ ] Complete accessibility review
- [ ] Complete performance baseline
- [ ] Complete sustained-use test
- [ ] Resolve release-blocking defects

### Documentation

- [ ] Update architecture documentation
- [ ] Complete administrator guide
- [ ] Complete user guide
- [ ] Complete installation guide
- [ ] Complete upgrade guide
- [ ] Complete rollback guide
- [ ] Complete backup and restore guide
- [ ] Complete troubleshooting guide
- [ ] Document maintenance windows
- [ ] Document known limitations
- [ ] Publish v1.0 release notes

### Release

- [ ] Create v1.0 release candidate
- [ ] Deploy release candidate to production
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
- [ ] Documentation Standard
- [ ] ADR Policy
- [ ] Release Policy
- [ ] Versioning and Contributing guidance
- [ ] Release Certification framework
- [ ] M-018 Service Lifecycle certification
- [ ] Governance audit

Governance is a permanent project capability. Completion of M-021 establishes
the initial standards; later milestones continue to operate under them.
