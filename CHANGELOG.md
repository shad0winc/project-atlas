# Changelog

All notable changes to Project Atlas are documented in this file.

## [Unreleased]

- Added M-018.29 guarded lifecycle planning contracts: immutable
  `ServiceUpdatePlan`, `ServiceUpdateResult`, and `ServiceUpdateOutcome`
  contracts now normalize managed-service identity, image state, dependency
  identities, UTC timestamps, rollback metadata, warnings/errors, correlation
  identity, and deterministic `to_dict()` serialization.
- Added the `MaintenanceEvent` audit-domain contract required by the Service
  Lifecycle architecture, including requester identity, operation identity,
  previous/resulting state, outcome, warnings/errors, rollback information,
  timestamps, and correlation identity.
- M-018.29 is intentionally domain-only: Service Lifecycle provider mutation,
  audit-event publication, guarded update/restart execution, CLI/API mutation,
  and Portal lifecycle administration remain open.

### Added

- Completed Q.6 sustained-use release certification against exact published candidate `13a48a5ce1a6e4c5f335f4ae6cd19ba61149fefa` with run `q6-20260822T011449Z`: 193/193 immutable samples across the full 48-hour fixed-slot window, zero fixed-slot violations, zero Scheduler failures, bounded Runtime Bus terminal convergence PASS, and durable terminal status `completed`.
- Final terminal evidence froze the sample-193 Runtime Bus target at journal line `7053`; Notifications converged through that target within two bounded probes, with final cursor `7068` and journal line `7070`. Post-target event growth remained allowed and did not move the certification target.
- Preserved all prior failed/aborted Q.6 evidence without rewrite, kept the 193 history samples byte-identical through finalization, and stopped the Scheduler timer at the certification boundary while leaving it enabled for controlled future operation.
- Closed the M-023 `Complete sustained-use test` release gate and the production Scheduler-dispatcher release-blocking defect after the exact published repair candidate completed the full autonomous production certification with Atlas `healthy:100`, 22 running containers, and zero unhealthy containers.

- Added Q.6A.7 bounded Runtime Bus terminal-convergence semantics after the completed 193/193 production run exposed a finalization race between the frozen final sample and Notifications cursor convergence.
- Replaced the historical final Runtime Bus backlog-equals-zero terminal gate with a bounded observer anchored to the Runtime Bus journal tail captured by sample 193. Finalization now requires Notifications to consume through that frozen target within 180 seconds; post-target journal growth is allowed and does not move the certification target.
- Added explicit terminal evidence to the sustained-use lifecycle and CLI. `pending` is not success, convergence is required before `completed`, and timeout is a hard certification failure.
- Certified the eight-file Q.6A.7 repair candidate with 22 terminal-convergence tests, 19 historical evaluator tests, 31 finalization regression tests, 251 complete Sustained Use tests, and 71 generic Scheduler regressions.
- Preserved the production Q.6 record `q6-20260819T233234Z` byte-identically as `failed` at 193/193 while retrospective evaluation proved history PASS, fixed cadence PASS, and bounded terminal convergence PASS against the frozen sample-193 Runtime Bus target.

- Added Q.6A.5 fixed-cadence sustained-use certification semantics after the second production Q.6 attempt exposed cumulative Scheduler phase drift.
- Separated the 900-second Q.6 certification interval from the 60-second Scheduler polling interval. The fixed certification clock is anchored to T0 rather than to previous callback completion time.
- Added a 180-second maximum lateness window for each T0-derived sampling slot. Early polls are successful no-ops, bounded lateness captures exactly one real observation, and a missed slot returns a hard failure.
- Explicitly forbid certification backfill. Atlas never manufactures multiple historical observations after a missed slot.
- Added independent finalization-time fixed-slot validation through `history.cadence.fixed_slots`, providing defense in depth even if collection scheduling regresses.
- Added regression coverage against archived production run `q6-20260817T232028Z`, which was retired at `176/193` after accumulating deterministic temporal drift despite zero Scheduler failures and otherwise healthy production.

- Added explicit Q.6 sustained-use session retirement for incomplete certification attempts. Active sessions can now be transitioned to the distinct terminal `aborted` state and archived without misclassifying an infrastructure-invalid run as a completed certification failure.
- Added immutable sustained-use run archives under `archive/<run-id>/`, preserving `history/`, `latest.json`, and terminal `session.json` evidence while reopening the active sustained-use root for a future certification run.
- Added retry-safe retirement semantics: archive movement is ordered `history -> latest -> session`, the current session boundary moves last, partially completed archival can resume without changing the original completion timestamp, and archived run identities cannot be reused.
- Added the guarded `atlas sustained-use abort --confirm-run-id <run-id>` operator command. The exact current run ID is required, no force bypass exists, and the shell adapter remains a thin argument/exit-code forwarding boundary while the Python CLI owns confirmation validation.
- Certified the seven-file abort/archive candidate with 55 focused abort/archive tests, 189 complete Sustained Use tests, and 71 Scheduler/dispatcher regression tests while preserving the production Q.6 attempt at `1/193` and leaving `sustained-use.sample` absent during the maintenance boundary.

- Added M-023 Q.6A.2 sustained-use release-certification instrumentation without
  starting the certification clock. The new `atlas.sustained_use` domain
  provides immutable contracts, live read-only collectors, atomic evidence
  persistence, hard and temporal evaluation, lifecycle orchestration, an
  executable `atlas sustained-use` CLI, and Scheduler integration.
- Established the v1.0 sustained-use policy at 48 hours with 15-minute
  intervals and 193 expected samples including T0, while freezing the expected
  production runtime at 22 running containers.
- Added the canonical core Scheduler task `sustained-use.sample` at a
  900-second interval. Its idempotent callback is a successful no-op when no
  Q.6 session exists, when the session is inactive, or when the next interval
  is not yet due; only an active due session captures evidence.
- Extended unqualified `atlas scheduler sync` to register
  `sustained-use.sample` alongside `operations.collect` while preserving
  targeted module-sync isolation.
- Added the release-engineering guide `docs/releases/SUSTAINED_USE.md`.
- Q.6 instrumentation certification passed 171 Sustained Use tests together
  with Scheduler, Operations Scheduler, shell-boundary, and Operations
  repository regressions. Production remained at 22 running containers and
  zero unhealthy containers.
- The M-023 ROADMAP item `Complete sustained-use test` remains open.
  Live Scheduler synchronization, production session creation, T0, the
  48-hour observation window, finalization, and the release-blocking-defect
  decision have not yet occurred.

- Completed the M-023 Q.5 v1.0 performance-baseline certification against the
  exact committed release candidate. The certified reference inventory contains
  thirteen API, HTTP, CLI, and browser metrics, including seven authenticated
  exact-candidate Portal surfaces.
- Certified 20 successful samples each for API health and Portal login HTTP,
  10 successful samples for each of the four CLI measurements, and seven
  exact-candidate browser samples for Login, Portal, Media, Favorites, Requests,
  Services, and Sports.
- Established the measured Q.5 results as the v1.0 reference performance
  baseline for future equivalent regression comparison. No candidate
  performance blocker was identified.
- Kept older live Portal runtime drift separate from the exact-candidate
  baseline and introduced no arbitrary universal latency threshold.
- Closed only the M-023 ROADMAP item `Complete performance baseline`.
  `Complete sustained-use test`, release-blocking-defect resolution, pilot,
  stabilization, and final v1.0 release certification remain independent gates.
  Q.5 makes no stress-load or sustained-use certification claim.


- Completed the M-023 Q.4 full automated release-candidate test-suite
  certification. The authoritative matrix passed the complete Core, API,
  Sports, Portal, and critical-browser validation layers together with Portal
  formatting, TypeScript, ESLint, and production-build validation.
- Reconciled the five pre-existing Portal Prettier failures discovered by the
  release-wide formatter gate as formatting-only changes to the Media and
  Service Lifecycle surfaces. Focused validation passed 24 tests, the complete
  Portal suite passed 247 tests across 34 files, and the production Portal
  build remained green before the remediation was committed.
- Certified the formatting remediation as an exact five-file commit and
  re-certified the committed checkpoint with formatting, typecheck, and lint
  green while preserving the Q.4 automated-matrix evidence chain.
- Closed only the M-023 ROADMAP item `Run full automated test suite`. The
  independent performance-baseline, sustained-use, release-blocking-defect,
  human User Acceptance, pilot, stabilization, and final-release gates remain
  separate requirements.


- Added deterministic Administrator critical-browser coverage for the existing
  read-only Service Lifecycle Administration Portal. The certified journey
  authenticates through the real Portal session path, requires
  `system.health.read`, navigates to `/portal/services`, exercises the five
  authenticated overview GET sources plus the Jellyfin read-only detail GET,
  renders aggregate service health, managed-service state, Update Availability,
  and Maintenance History, and proves that Restart, Update service, and Rollback
  lifecycle mutation controls remain absent.
- Completed the M-023 critical-browser engineering set across Login, Media
  Request, Favorites, Sports Request, and Administrator Service Lifecycle. The
  final deterministic Playwright inventory is six tests across five critical
  browser specs.
- Certified the D.5 Administrator delta with 3,156 Core tests plus 104 subtests,
  400 API tests plus 15 subtests, all five Sports integration suites, 247 Portal
  tests, TypeScript, ESLint, a production Next.js build, the targeted
  Administrator browser journey, and the complete six-test critical-browser
  regression.
- Kept D.5 bounded to E2E infrastructure only:
  `apps/portal/e2e/administrator.spec.ts` and
  `apps/portal/e2e/fixtures/atlas-api-server.mjs`. Production Atlas API and
  Portal source were unchanged, and production remained at 22 running
  containers with zero unhealthy.
- Preserved the five independently established pre-existing Portal Prettier
  warnings outside the D.5 delta; D.5 introduced no additional formatting debt.

- Added the v1.0 Sports request surface through the authenticated Atlas API and
  `/portal/sports`, using the existing TheSportsDB provider boundary while
  preserving Atlas-owned user and subscription identity.
- Added deterministic critical-browser coverage for login, Media Request,
  Favorites, and Sports. The Sports journey proves authenticated event discovery,
  an authenticated single event-request POST, provider/event identity preservation,
  server-owned user/subscription identity, and duplicate UI submission prevention.
- Certified the accumulated D.1-D.4 critical-E2E worktree with 3,156 Core tests
  plus 104 subtests, 400 API tests plus 15 subtests, all five Sports integration
  suites, 247 Portal tests, TypeScript, ESLint, a production Next.js build, and
  five Playwright tests across four critical-browser specs.
- Reconciled formatting only for the 25 D.1-D.4-owned Portal files. Five unrelated
  pre-existing Portal Prettier warnings remain unchanged and are not attributed to
  the critical-E2E work.

- Added Seerr-backed Media discovery/search through the Atlas API and the
  authenticated `/portal/media` experience without exposing browser-to-provider
  access or rendering raw provider media identifiers.
- Added self-scoped Personal Request creation to the Portal and an eligible
  movie Request action guarded by `requests.create`, with per-card mutation
  feedback, zero automatic POST retries, and safe stale-conflict handling.
- Added global active-target uniqueness for Media Requests using the persistent
  `requests.lock` sidecar and `fcntl.flock()` so the duplicate check and initial
  `PENDING` persistence are serialized across concurrent writers before any
  provider submission can occur.
- Added normalized TV-series detail, season metadata, ongoing-state derivation,
  and anime classification through the Atlas read boundary while excluding
  Specials (`season 0`) from normal request scope.
- Added fail-closed per-season availability and requestability normalization so
  the Portal can distinguish known requestable seasons from tracked,
  provider-requested, unknown, or malformed provider state.
- Added explicit one-season TV and anime-TV Request actions to the Portal. The
  browser consumes Atlas-normalized season state, derives `tv` versus `anime_tv`
  only from server-provided anime classification, and does not expose generic
  TV, all-seasons, or current-season shortcuts.
- Added deterministic Media Request submission preflight and explicit
  server-owned Seerr routing for standard TV and anime TV so missing or invalid
  routing fails before new Request persistence or provider HTTP.
- Established Seerr ongoing-series monitoring ownership as a service-level
  runtime concern and completed the controlled production migration to the
  repository-pinned Seerr v3.4.1 runtime under backup, maintenance, deployment
  lock, rollback, and post-change verification control.
- Verified `monitorNewItems=all` for both supported Sonarr routes and revalidated
  Atlas's server-owned routing after migration.
- Certified production TV/anime routing through E2.5: standard TV remains on
  server `0`, while `anime_tv` routes to Seerr server `1`, `sonarr-anime`, and
  `/media/Anime TV`; ongoing-series acceptance proved monitored downstream
  ownership without exposing `serverId` or monitoring policy to the browser.
- Added a Docker healthcheck to the repository-pinned Seerr service using the
  unauthenticated public-settings endpoint, while preserving the pinned image,
  `init: true`, existing configuration path, and current dependency topology.

### Fixed

- Added the repository-owned production Scheduler dispatcher contract discovered
  as missing during the first Q.6 sustained-use attempt. The dispatcher uses
  `atlas-scheduler.timer` to provide a one-minute systemd dispatch opportunity
  and `atlas-scheduler.service` to invoke `/bin/atlas scheduler run` as a
  one-shot process; `TaskScheduler` remains the sole authority for registered
  task cadence, due-state calculation, locking, execution, history, and
  success/failure state.
- Added 26 dedicated Scheduler systemd/dispatcher contract tests covering unit
  structure, one-minute dispatch cadence, separation from the existing health
  timer, zero-work success, successful due work, failed due work, mixed due
  work, live-lock contention, and direct propagation of Atlas CLI exit status
  to systemd without failure masking.
- Recorded the first Q.6 production attempt,
  `q6-20260817T171504Z`, as incomplete release evidence. T0 was successfully
  established at `2026-08-17T17:15:04.595315Z` against commit
  `b3dc4a1877285b627386fb989e1a71b0b2acb0eb`, but the run remained at
  `1/193` samples because no recurring production dispatcher existed to invoke
  due Scheduler work automatically.
- Preserved the failed first Q.6 attempt rather than fabricating or backfilling
  the missed 15-minute observations. A new uninterrupted 48-hour / 193-sample
  certification window remains required after the dispatcher repair is
  committed, published, installed, and live-certified.

- Repaired the Notifications Runtime Bus reader contract discovered during
  release-quality preflight. The non-root Notifications worker remains
  `1000:1000` while receiving only supplementary Runtime Bus reader group
  `20000`; the shared event journal remains mounted read-only.
- Hardened Notifications health reporting so a worker is healthy only when the
  Runtime Bus event journal is actually readable in addition to the existing
  heartbeat freshness requirement.
- Hardened the canonical Notifications update preflight to test journal
  readability with the same supplementary reader group used by the deployed
  worker and to fail closed before recreation when that access is unavailable.
- Pinned canonical Notifications Compose operations to project
  `notifications`, preventing container-identity drift during controlled module
  update.
- Added regression coverage for the supplementary reader group, read-only
  journal mount, journal-aware healthcheck, update-time reader-group
  validation, and explicit Compose project boundary.
- This repair does not by itself certify sustained-use completion or close the
  independent release-blocking-defect gate.


- Closed the initial final-v1.0 Security Acceptance baseline after protected
  PR #23 merged Docker socket hardening into `main` and protected PR #24
  reconciled the certified `main` tree into `release/v1.0.0`.
- Re-certified final v1.0 Security Acceptance after a later production
  audit-journal write-boundary defect was discovered during manual acceptance.
  Protected PRs #31/#32 added deterministic security-audit journal provisioning
  on `main` and `release/v1.0.0`; protected PRs #33/#34 added stale extended-ACL
  normalization and portable numeric ACL regression coverage.
- Remediated the live security audit journal in place to owner `root`, writer
  group `20000`, mode `0660`, and minimal ACL `rw-/rw-/---`, preserving the
  existing inode and journal content while restoring effective Atlas API write
  access.
- Certified the real `atlas.shadowinc.co` Caddy/TLS/SNI path and executed one
  controlled invalid-login production acceptance transaction. The request
  returned HTTP 401 and appended exactly one
  `security.authentication.failed` / `invalid_credentials` audit record without
  recording the supplied password or sensitive credential fields.
- Removed direct Docker-socket access from Homepage and Dozzle. Dozzle now uses
  the private read-only `atlas-docker-socket-proxy`; mutation through the proxy
  is denied with HTTP 403, and the proxy image scan reported zero HIGH and zero
  CRITICAL findings.
- Certified the final security runtime with Notifications running non-root, six
  Discord webhooks rotated and recertified, Anime TV routing corrected,
  sports-feed nginx refreshed, and 22 containers running with zero unhealthy.
- Closed Atlas-owned fixable CRITICAL risk at zero. Nineteen remaining fixable
  HIGH observations attributed to the current Caddy image/runtime were
  explicitly accepted for v1.0 after feasibility/freshness review found no
  simple supported upstream refresh; that acceptance does not waive future
  remediation when a safe supported upstream fix becomes available.

- Completed the M-023.26 Security engineering review across authentication,
  authorization, invitations, sessions, reverse proxy and API exposure,
  secret storage, audit events, dependency/image risk, network trust
  boundaries, and least privilege.
- Hardened first-party Notifications and Sports module images to run as the
  operator-mapped non-root `atlas` identity, require explicit PUID/PGID build
  inputs, prevent privilege escalation, and fail closed before recreation when
  writable-state ownership or Runtime Bus access is incompatible.
- Narrowed Notifications Runtime Bus mounts to its event journal, cursor, and
  filter; removed the obsolete Sports private scheduler/runtime mount
  capability; and preserved deployment-time ownership migration as an explicit
  maintenance-controlled operation.
- Preserved final v1.0 Security Acceptance as a separate release gate requiring
  current vulnerability evidence, controlled runtime validation, documented
  residual limitations, and explicit approval.

- Completed M-023.25 Backup and Recovery with a versioned state-complete
  recovery format, explicit authoritative-state ownership, protected archive
  publication, isolated restore staging, consumer validation, transactional
  live replacement, and fail-closed resume/abort recovery.
- Added explicit production restore authorization: live apply requires a clean
  certified `main` checkout equal to `origin/main`, a verified deployment
  baseline, the shared deployment/update lock, maintenance isolation, a
  validated pre-restore recovery point, and `--confirm-live`.
- Proved the certified live recovery path with restore transaction
  `restore-20260808T174153Z-3004055`: API, Sports, and Notifications writers
  were quiesced and restarted healthy, Atlas health returned to 100 percent,
  public ingress reopened at 24 of 24 checks, maintenance was disabled, and the
  shared lock was released.
- Preserved the single-host recovery boundary: Atlas recovery archives protect
  declared Atlas configuration and state, but do not claim media-library,
  third-party application database, off-host, or storage-device disaster
  recovery.

- Completed M-023.24 Deployment Safety with protected release promotion,
  transactional production updates, Caddy-owned maintenance mode, verified
  deployment baselines, and explicit rollback/forward-recovery boundaries.
- Corrected the production verification contract discovered during the first
  controlled update: maintenance-aware ingress verification now proves backend
  health and public HTTP 503 isolation before traffic is reopened, followed by
  a second public verification before a candidate baseline becomes current.
- Preserved exact pre-update Docker image identities with transaction-scoped
  rollback tags before pull/build mutation so locally built Portal and API
  images cannot become unavailable merely because their mutable tags move.
- Exercised the failure path in production without hiding the incident: the
  failed update remained recorded as `failed`, controlled forward recovery
  established a new verified baseline, and the repaired contracts subsequently
  passed 27 maintenance-mode ingress checks, 24 reopened-ingress checks, and
  exact retention of all 19 baseline image identities.

- Completed M-023.23 Unavailable-Provider Behavior with explicit cross-boundary
  failure semantics, deterministic provider-outage safeguards, and read-only
  production validation.
- Proved Jellyfin transport and timeout failures remain provider errors rather
  than successful empty inventories, while Media Request recovery intent and
  cleanup preview boundaries continue to fail closed.
- Proved Sports provider failure records degraded provider health while
  preserving existing recording plans and non-finished monitored game state.
- Validated production Jellyfin, Jellyseerr, Service Lifecycle, and Sports
  provider observability with 264 regressions and 13 subtests and zero provider,
  Sports-state, or repository mutations.

- Completed M-023.22 Storage-Full Behavior with deterministic `ENOSPC`
  injection, last-durable-state preservation, exact-identity Sports recorder
  compensation, and read-only production validation.
- Normalized Media Request registry persistence failures so unavailable storage
  fails before provider mutation instead of escaping the repository boundary.
- Hardened Sports recorder reconciliation so a newly launched recorder is
  stopped by exact PID plus process-start-time identity if its durable identity
  cannot be persisted; adopted recorders are never stopped as compensation.
- Hardened `atlas backup` so archives are created under a `.partial` identity,
  validated, and atomically published to the canonical `.tar.gz` name only
  after successful completion.
- Verified production storage at 94.76 percent free with 10 canonical Atlas
  backups, zero partial backup artifacts, a valid newest backup manifest, and
  zero production storage, backup, recorder, cleanup, or repository mutations.

- Hardened automatic cleanup boundaries so cleanup recommendations remain
  non-destructive until a future mutation path performs fresh Atlas policy and
  retention authorization at the exact mutation boundary.
- Hardened Sports recorder recovery so process adoption and termination require
  both the persisted PID and Linux process start-time identity. Missing or
  mismatched identity now fails closed instead of trusting PID liveness alone.
- Prevented interrupted media-request submission and cancellation from
  silently replaying outcome-ambiguous provider mutations by durably
  persisting `submitting` or `cancelling` intent before external mutation and
  failing closed until reconciliation.
- Hardened Scheduler Recovery lock ownership to fail closed when a runtime
  lock is empty, malformed, unreadable, non-positive, or otherwise
  indeterminate, while preserving automatic reclamation for a PID positively
  known not to exist.
- Prevented active Service Lifecycle observations from exposing a previous
  Docker lifecycle's `FinishedAt` timestamp as the current `finished_at` value.
  Running and restarting services now expose `finished_at: null` while terminal
  services retain valid finish timestamps.
- Prevented Service Doctor from double-counting a missing Docker health check as both an observability warning and a degraded-health warning.


### Documentation

- Reconciled M-023.13 documentation with the completed Startup Policy
  implementation, provider boundary, CLI, tests, VPN readiness remediation,
  and live production validation.
- Adopted `/tmp/project-atlas-doc-work` as the permanent staging and review
  path for reliable documentation changes.

- Added the Atlas Release Notes Template covering release highlights, features, improvements, fixes, breaking changes, upgrades, known issues, deprecations, acknowledgements, and support information.
- Added the reusable Atlas Release Template covering release scope, features, fixes, compatibility, validation, metrics, rollback guidance, and approval.
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

- Completed M-023.21 VPN Fail-Closed Verification with static Compose
  topology tests, read-only production namespace/firewall inspection, and an
  explicitly approved controlled OpenVPN failure-path test.
- Proved qBittorrent cannot use the underlying non-VPN `eth0` route while
  Gluetun's `tun0` tunnel is unavailable: a direct IPv4 probe timed out while
  `tun0` remained absent, followed by automatic VPN recovery and clean Atlas
  verification.
- Preserved the production safety boundary during validation: no qBittorrent,
  firewall, route, Compose, or repository mutation was performed, and the
  emergency Gluetun restart fallback was not required.

- Completed M-023.20 Automatic Cleanup Safeguards with cross-boundary
  favorite, policy-failure, Maintainerr, dry-run, and production preview
  verification.
- Reconciled Maintainerr cleanup guidance with ADR 0018: destructive Maintainerr
  collections remain disabled until Atlas owns a fresh, auditable mutation
  authorization boundary.
- Completed M-023.19 Sports Recovery Verification with durable recorder process
  identity, PID-reuse protection, verified no-signal fail-closed behavior, and
  read-only production validation.
- Reconciled the Sports documentation with the deployed feed/controller,
  provider, subscription, recording, health, scheduler, maintenance, and
  recovery foundations while keeping unfinished Portal experience explicit.
- Completed M-023.18 Interrupted-Request Recovery with normalized recovery
  intent states, provider-ID invariants, deterministic fail-closed orchestration,
  and the read-only `MediaRequestService.list_recovery_required_requests()`
  boundary.
- Validated the completed Media Requests recovery contract with 346 regressions
  and read-only production inspection. No production request registry currently
  exists, so no persisted request state requires migration.
- Completed M-023.15 Service Dependency Verification by hardening and publicly
  exporting `ServiceDependencyNode` and `InfrastructureDependencyGraph`, while
  preserving compatibility through the existing lifecycle service module.
- Validated the permanent dependency boundaries across Docker Compose
  normalization, graph topology, Service Doctor operational findings, Startup
  Policy readiness, and human and JSON CLI reporting.
- Production validation modeled 15 services and eight resolved relationships
  with no unresolved dependencies, no Doctor dependency findings, and a
  Healthy, attention-free Startup Policy result.

- Added normalized Restart Recovery observation, status, and result contracts,
  deterministic provider-independent evaluation, and dedicated tests.
- Added the read-only `ServiceRestartRecoveryService` orchestration boundary.
- Added `atlas service recovery observe` and `atlas service recovery evaluate`
  with human and JSON output, validated observation loading, and no mutation
  operation.
- Validated the production no-restart path as `not-observed`.
- Completed an explicitly approved controlled FlareSolverr restart and verified
  the production recovery path as `recovered`, healthy, and attention-free.

- Added normalized startup dependency and per-service startup contracts,
  Docker Compose provider translation, deterministic Startup Policy result
  contracts, provider-independent evaluation, and dedicated tests.
- Added the read-only `ServiceStartupPolicyService` and public
  `atlas service startup-policy [--json]` command.
- Added fail-closed qBittorrent startup readiness through Gluetun health.

- Added the transport-neutral Atlas API contract foundation under `atlas.api`,
  including canonical API and schema versions, immutable success and failure
  envelopes, normalized API errors, deterministic serialization, UTC timestamp
  normalization, and explicit public exports.
- Added serialization support for mappings, sequences, enums, dataclasses,
  timezone-aware datetimes, and Atlas contracts exposing `to_dict()`, while
  rejecting unsupported and framework-specific values.
- Added opt-in FastAPI and OpenAPI envelope schemas under `apps/api` together
  with reusable success and failure adapter helpers.
- Preserved all existing unwrapped health, authentication, dashboard, and
  media-library response contracts for backward compatibility.
- Added focused shared-contract, serialization, Operations integration,
  Pydantic adapter, OpenAPI schema, and existing-endpoint regression coverage.

- Added scheduled Atlas Operations report collection through the shared
  `TaskScheduler` runtime, without introducing a parallel Operations-specific
  scheduling system.
- Added the canonical `operations.collect` task with hourly registration,
  idempotent scheduler synchronization, persistent runtime-state preservation,
  and core-task event isolation.
- Added the `atlas.operations_scheduled_collection` callback, including
  normalized errors, deterministic result output, immutable report persistence,
  and the `ATLAS_OPERATIONS_DIRECTORY` runtime override.
- Extended unqualified `atlas scheduler sync` to register core Operations jobs
  alongside enabled module manifests while preserving targeted module sync.
- Added live scheduler execution, immutable snapshot, `latest.json`, scheduler
  history, Operations history, comparison, and real subprocess regression
  validation.

- Added deterministic Atlas Operations report comparison with immutable
  finding-change and aggregate comparison contracts, derived status, score,
  attention, and change summaries, and validated round-trip serialization.
- Added a pure comparison service that detects added, removed, changed, and
  optionally unchanged findings while preserving deterministic ordering.
- Added concise human and stable JSON comparison renderers.
- Added `atlas operations compare`, `atlas operations compare --json`, and
  `atlas operations compare --include-unchanged`.
- Added focused comparison model, service, renderer, Python CLI, shell,
  repository-failure, insufficient-history, and live read-only validation.

- Added read-only Atlas Operations history inspection with newest-first
  ordering, configurable limits, concise human output, and a stable wrapped
  JSON contract.
- Added `atlas operations history`, `atlas operations history --json`, and
  `atlas operations history --limit LIMIT`.
- Added focused parser, renderer, repository-forwarding, failure, shell, and
  live read-only validation coverage.

- Added immutable Atlas Operations report persistence with schema-validated
  deserialization, deterministic atomic JSON snapshots, duplicate-snapshot
  protection, `latest.json`, and newest-first repository history support.
- Added `atlas operations save` and `atlas operations latest`, including
  human-readable and deterministic JSON output through both the Python and
  public shell CLIs.
- Added dedicated Operations repository, model round-trip, CLI, shell,
  corruption, failure-isolation, and atomic-write tests.

- Added the complete Atlas Operations reporting and CLI foundation,
  including deterministic aggregation, collector failure isolation,
  automatic runtime context, detailed human reports, stable JSON output,
  and the public `atlas operations report` command.
- Added Docker runtime, health, restart, OOM, exit-state, and
  resource-governance findings.
- Added Operations context, service, Python CLI, and shell integration.

- Added the Operations collector and Docker provider foundation, including immutable collector contracts, a live read-only System collector, a guarded Docker CLI JSON adapter, normalized Docker Engine and container inventory snapshots, runtime and health state, UTC lifecycle timestamps, resource-governance ceilings, mounts, networks, exposed and published ports, deterministic serialization, package exports, live environment verification, and dedicated tests.
- Added the canonical `atlas.operations` domain, including immutable findings, sections, summaries, and reports; schema-versioned serialization; canonical section identities; UTC timestamp and Git commit normalization; deterministic section and attention ordering; global finding uniqueness validation; package exports; and 57 focused tests.
- Added production ingress resource governance for Caddy, Atlas API, and Atlas Portal, including memory, CPU, and PID ceilings, a native Caddy health check, and a permanent runtime verifier.
- Integrated normalized `request.*` lifecycle events with the Notifications module, including media-type Discord routing, lifecycle-specific formatting, Ready to Watch availability notifications, severity classification, module verification, documentation, and dedicated tests.
- Added provider-neutral Media Request lifecycle events and optional best-effort publication from the Media Request service, including created, submitted, lifecycle transition, and cancellation events, publication error observability, package exports, and dedicated tests.
- Added the Jellyseerr Media Request provider adapter with movie, TV, anime movie, and anime TV submission, request and media status normalization, cancellation, health reporting, environment-based construction, package exports, and dedicated mocked tests.
- Added the reusable Media Request HTTP provider foundation with authenticated GET, POST, and DELETE operations, normalized URLs, deterministic JSON transport, timeout and response validation, safe error translation, package exports, and dedicated mocked tests.
- Added the provider-agnostic Media Request service coordinating request creation, submission, status refresh, cancellation, lifecycle validation, repository updates, provider capabilities, package exports, and dedicated contract tests.
- Added the provider-independent Media Request contract with normalized provider capabilities, lifecycle results, health status, event context, abstract operations, package exports, and dedicated contract tests.
- Added the durable Media Request repository with schema-versioned JSON persistence, atomic writes, duplicate protection, deterministic listing, user and provider lookups, deletion, corruption detection, package exports, and dedicated contract tests.
- Added the normalized Media Request domain model with request ownership, provider identity, lifecycle state, timestamp validation, serialization, package exports, and dedicated contract tests.
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

- M-018.30 read-only Service Lifecycle HTTP API foundation.
- `GET /api/v1/services` for normalized managed-service collection.
- `GET /api/v1/services/{service_identifier}` for managed-service detail.
- `GET /api/v1/services/health` for aggregate infrastructure health.
- `GET /api/v1/services/summary` for normalized infrastructure summary.
- Typed Service Lifecycle API response schemas and dedicated HTTP contract tests.
- API dependency construction backed by the existing provider-independent
  `ServiceLifecycleService` and `DockerComposeProvider`.

- Added M-018.31 Administration Portal Service Lifecycle foundation at
  `/portal/services`, protected by `system.health.read`.
- Added production-payload-aligned managed-service overview cards, aggregate
  service-health presentation, and read-only per-service detail inspection.
- Added authenticated GET-only Portal adapters for the M-018.30 Service
  Lifecycle collection, detail, health, and summary endpoints.
- Added runtime/health normalization from aggregate API payloads, including
  preservation of the `unavailable` health state and read-only detail
  enrichment from the already-loaded overview.
- Registered the Services route in the canonical Portal navigation model and
  reconciled authorization-aware navigation tests.
- Completed M-018.32 responsive/mobile Service Lifecycle acceptance:
  preserved the existing responsive managed-service card grid, hardened shared
  retry interaction to the Portal's 2.75rem touch-target convention, and added
  mobile-safe shrinking/wrapping for Service Lifecycle cards and read-only
  detail values.
- Evaluated Progressive Web App support after responsive validation and deferred
  PWA runtime implementation beyond v1.0; the responsive authenticated Portal
  remains the supported v1.0 mobile administration experience.

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

- Verified 9 dedicated Service Lifecycle API route tests.
- Verified the complete Atlas API regression suite with 357 passing tests and
  15 passing subtests.
- Verified all 597 Service Lifecycle regression tests.
- Verified all 225 Docker Compose provider regression tests.
- Verified the OpenAPI surface exposes exactly four Service Lifecycle GET
  operations and no POST, PUT, PATCH, or DELETE lifecycle operations.
- Verified the read-only HTTP surface requires `system.health.read`.
- Verified Atlas Doctor after the implementation.
- Preserved the v1.0 read-only boundary: restart, update, rollback, lifecycle
  writes, Update Discovery API, Maintenance History API, and Portal UI remain
  outside M-018.30.

- M-018.31 focused Portal validation passed 23 tests across the Service
  Lifecycle presentation and navigation contracts.
- The complete Portal regression suite passed with 218 tests across 27 files;
  TypeScript typecheck, Prettier, ESLint, whitespace checks, bounded remote
  race validation, and Atlas Doctor also passed.
- M-018.31 preserves the GET-only v1.0 boundary: no restart, update, rollback,
  maintenance mutation, or other lifecycle write control is exposed by the
  Portal.

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

### Release Hardening

- Completed the first controlled E2.5 Jellyseerr-to-Seerr migration attempt under the Atlas deployment transaction.
- The migration did not complete and is not certified as successful; Atlas failed closed with maintenance enabled and the deployment lock retained for explicit recovery.
- Recovery restored the legacy Jellyseerr runtime and preserved the failed transaction as audit evidence rather than rewriting the outcome.
- Recovery exposed a Sports runtime ownership defect on writable state and recording paths for the configured `atlas` runtime identity (`1000:1000`).
- Corrected the bounded Sports writable-path ownership, recreated the controller, verified a fresh heartbeat, and returned the Sports module to healthy operation.
- Final recovery verification returned `atlas doctor` to 100%, preserved the verified deployment baseline, disabled maintenance only after successful validation, and released the deployment lock.
- Hardened deployment/update and Sports lifecycle contracts from the production evidence before a second Seerr migration attempt.
- Completed the subsequent controlled Jellyseerr-to-Seerr production migration under transaction `seerr-migration-20260813T001057Z-760620`; the migrated runtime reached `runtime_verified` / `migration_runtime_ready` while maintenance and deployment-lock ownership remained fail closed through acceptance.
- Recovered a first Anime-TV acceptance misroute involving Mushoku Tensei without deleting the seven preserved media files; reconciled the stale Seerr and Atlas request artifacts and restored authoritative Anime Sonarr ownership before continuing.
- Certified E2.5 Anime-TV production acceptance with Demon Slayer: Kimetsu no Yaiba Season 2: Atlas persisted `media_type=anime_tv`, Seerr request `3` routed to server `1`, Anime Sonarr created the target under `/media/Anime TV`, Season 2 remained monitored, and standard Sonarr remained untouched.
- E2.5 production migration, routing, monitoring, and TV/anime acceptance are closed; final release-candidate, pilot, stabilization, and v1.0 certification gates remain open.


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

---

## M-018.33 — Update Availability

- Extended existing Update Discovery with read-only Docker registry comparison.
- Added truthful `current` and `update-available` classification using local descriptor and remote top-level manifest/index identity.
- Preserved fail-closed `mutable-tag`, `unknown`, and `unsupported` behavior.
- Added GET-only `GET /api/v1/services/updates`.
- Reused the existing Service Lifecycle permission and canonical `UpdateReport`.
- Added Portal aggregate and per-service Update Availability.
- Reused the existing hook and M-018.32 responsive/mobile-safe presentation.
- Added no update, restart, pull, rollback, or other lifecycle mutation control.
- Closed the v1.0 Update Availability presentation gate.
- Leaves Maintenance History as the final remaining v1.0 presentation gate.

## M-018.34 — Maintenance History

- Reused the established Service Lifecycle Maintenance History domain rather than creating a duplicate history subsystem.
- Added GET-only `GET /api/v1/services/history` using the canonical `ServiceMaintenanceHistoryService` and `MaintenanceReport`.
- Preserved the existing `system.health.read` authorization boundary and static-route ordering ahead of service detail.
- Added Portal Maintenance History normalization, aggregate status, responsive read-only record cards, and truthful empty-history presentation.
- Reused the existing Service Lifecycle hook and M-018.32 responsive/mobile-safe CSS unchanged.
- Kept Cleanup History and Operations History separate from Service Lifecycle Maintenance History.
- Added no restart, update, rollback, start, stop, or other lifecycle mutation control.
- Closed the final v1.0 Maintenance History presentation gate.
- Final representative v1.0 User Acceptance and release certification remain required.

## Q.2 — Responsive UI Review Certification

- Completed the v1.0 responsive UI review across the critical Portal
  surfaces.
- Certified a deterministic visual review matrix covering three
  viewports (`390x844`, `768x1024`, and `1280x800`) across six critical
  surfaces (Login, Dashboard, Media, Favorites, Sports, and Services),
  for 18 screenshots total.
- Confirmed the previously observed compact-navigation/sidebar artifact
  was caused by screenshot capture timing during the drawer-closing
  transition rather than a production Portal responsive defect.
- Final review evidence showed the compact navigation fully off-screen
  after close, with no residual sidebar exposure or material horizontal
  clipping on the reviewed critical surfaces.
- The responsive Playwright contract remains the only Q.2 source/test
  candidate; the responsive certification did not require a production
  Portal or API source change.
- Closed the ROADMAP item `Complete responsive UI review`.
- The broader v1.0 quality gates for the full automated test suite,
  accessibility review, performance baseline, sustained-use testing, and
  release-blocking defect closure remain open.

## Q.3 — Accessibility Review Certification

- Completed the v1.0 accessibility review across the six critical Portal
  surfaces: Login, Dashboard, Media, Favorites, Sports, and Services.
- Added deterministic semantic and keyboard accessibility coverage for the
  critical Portal surfaces, including visible focus behavior and compact
  navigation isolation.
- Added `@axe-core/playwright` and a six-surface Axe scan with a release
  threshold of zero serious or critical violations and no Axe rule
  exclusions or suppressions.
- Certified the human-review matrix across desktop (`1280x800`), phone
  (`390x844`), and tablet (`768x1024`) with 18 baseline screenshots,
  18 keyboard-focus screenshots, and 2 compact-navigation open-state
  screenshots.
- Verified compact-navigation close behavior, accessibility-tree isolation,
  focus return to `Open navigation`, and exclusion of hidden navigation links
  from the keyboard focus flow.
- Classified development-only hydration/caret warnings and `NEXTJS-PORTAL`
  focus artifacts as non-production artifacts: neither had an Atlas-owned
  source anchor and neither reproduced in the isolated standalone production
  runtime.
- Final isolated production provenance recorded zero HTTP 404 responses,
  zero console errors, zero failed requests, and zero page errors.
- Closed only the M-023 ROADMAP item `Complete accessibility review`.
  The older M-019 `Accessibility baseline` remains open as part of that
  milestone's broader Shared User Experience work.
- The remaining v1.0 Quality gates for the full automated test suite,
  performance baseline, sustained-use testing, and release-blocking defect
  closure remain open.
