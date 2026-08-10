# Project Atlas Build Log

This document records the major engineering milestones completed during the development of Project Atlas.

---

# 2026-07-03

## M-001 — Platform Foundation

### Objective

Build the core infrastructure required to host Project Atlas.

### Completed

- Created a Debian Docker LXC on Proxmox.
- Mounted dedicated media storage.
- Installed Docker and Docker Compose.
- Deployed the initial Project Atlas stack.
- Configured Gluetun with Windscribe VPN.
- Routed qBittorrent through the VPN.
- Connected Sonarr and Radarr to qBittorrent.
- Created the environment template and configuration documentation.

### Verification

- Docker stack healthy.
- Jellyfin operational.
- Homepage operational.
- VPN verified.
- Sonarr and Radarr download tests passed.

### Result

Project Atlas infrastructure became operational.

---

## M-002 — Anime Expansion

### Objective

Separate anime management from standard media libraries.

### Completed

- Added Sonarr Anime.
- Added Radarr Anime.
- Added Anime TV and Anime Movies libraries.
- Added anime download categories.
- Connected all Arr applications to Prowlarr.
- Simplified Docker startup dependencies.
- Added the Project Atlas Maturity Model.

### Engineering Decisions

- Favored runtime resilience over strict startup ordering.
- Adopted a dedicated anime management workflow.

### Result

Anime became independently managed while remaining fully integrated into Atlas.

---

## M-003 — Media Quality Intelligence

### Objective

Centralize media quality management.

### Completed

- Added Recyclarr.
- Integrated TRaSH Guides.
- Imported Custom Formats.
- Updated Quality Definitions.
- Implemented version-controlled quality profiles.

### Result

Media quality standards became centrally managed and reproducible.

---

## M-004 — Media Platform Integration

### Objective

Complete the media acquisition platform.

### Completed

- Configured Jellyfin libraries.
- Integrated Jellyseerr.
- Configured Movies, TV, Anime Movies, and Anime TV libraries.
- Added dedicated anime root folders.
- Verified Prowlarr synchronization.

### Result

The complete media platform became operational.

---

# 2026-07-05

## M-008 — Atlas Retention Intelligence Foundation

### Objective

Create the intelligence layer for Atlas.

### Completed

- Shared configuration framework.
- Immutable snapshot architecture.
- Historical snapshot storage.
- Jellyfin server, library, and user adapters.
- Library and library-path validation.
- Human-readable reporting.
- Configuration-driven validation.

### Result

ARI became the centralized operational reporting system for Atlas.

---

## M-009 — Operational Intelligence

### Objective

Introduce historical analysis and operational awareness.

### Completed

- Jellyfin aggregate metrics.
- User inventory.
- Library synchronization validation.
- Historical snapshot comparison.
- Operational summaries.
- Byte-accurate storage metrics.
- ARI functional refactor.

### Result

Atlas gained historical operational visibility.

---

# 2026-07-07

## M-010 — Health Engine

### Objective

Measure the operational health of Atlas.

### Completed

- Health scoring.
- Platform, media, Docker, VPN, and storage validation.
- Snapshot freshness monitoring.
- Categorized health reporting.

### Result

ARI can evaluate overall platform health.

---

## M-011 — Analytics Engine

### Objective

Transform snapshots into operational metrics.

### Completed

- Historical storage trends.
- Library growth analysis.
- Metric helper framework.
- Historical averages.
- Minimum and maximum tracking.
- Trend analysis.

### Result

Atlas understands historical behavior instead of only reporting snapshots.

---

## M-012 — Forecast Engine

### Objective

Predict future storage usage.

### Completed

- Time-normalized growth calculations.
- Average daily growth.
- 30-day projection.
- Days-remaining estimation.
- Estimated storage exhaustion date.
- Forecast confidence.

### Result

ARI performs predictive capacity planning.

---

## M-013 — Recommendation Engine

### Objective

Provide operational guidance based on system state.

### Completed

- Runtime state framework.
- Recommendation engine.
- Health, capacity, and forecast recommendations.

### Result

Atlas provides actionable operational guidance instead of reporting alone.

---

# 2026-07-19

## M-020.1 — User Identity Framework

### Objective

Introduce durable Atlas-native user identities that can be linked to external services.

### Completed

- Added normalized Atlas user profiles.
- Added durable per-user storage and a registry index.
- Added username and Atlas user-ID resolution.
- Added role, status, personal-field, and Jellyfin-ID validation.
- Added atomic profile updates and consistency verification.
- Added user-management CLI commands.

### Result

Atlas gained a stable identity layer independent of any single media provider.

---

## M-020.2 — Registration System

### Objective

Provide secure invitation-based registration and cross-system account provisioning.

### Completed

- Added secure hashed invitation tokens.
- Added invitation creation, inspection, revocation, verification, cleanup, and expiration handling.
- Added a dependency-free WSGI registration portal.
- Added transactional Atlas and Jellyfin account provisioning.
- Added compensating rollback for partial registration failures.
- Added best-effort registration lifecycle events.

### Result

Atlas can securely onboard users and maintain consistent identity state across Atlas and Jellyfin.

---

## M-020.3 — Favorites and Jellyfin Integration

### Objective

Create durable user-to-media favorite relationships with provider-neutral service boundaries and Jellyfin metadata enrichment.

### Completed

- Added durable favorite storage with per-user relationships and metadata-only records.
- Added favorite creation, removal, listing, inspection, filtering, and verification.
- Added a provider-neutral `FavoriteService`.
- Added a Jellyfin REST provider for media lookup and metadata normalization.
- Added automatic enrichment for title, normalized media type, Jellyfin type, year, path, series name, and library.
- Added best-effort `favorite.created` and `favorite.removed` event publication.
- Added CLI support without requiring callers to manually provide media type or title.
- Added focused provider, service, store, event, and CLI tests.

### Live Validation

- Confirmed Jellyfin API authentication using the configured Atlas URL and API key.
- Confirmed Jellyfin user discovery through the API.
- Linked the Atlas profile `michael` to the real Jellyfin user `admin`.
- Confirmed the configured media libraries are present but intentionally empty.
- Deferred the real-media favorite smoke test until the first Movie or Series item exists in Jellyfin.

### Result

Atlas now has a reusable favorites domain layer and a functioning Jellyfin integration. The only deferred validation depends on real media being added to the library.

---

# 2026-07-20

## M-020.4 — Jellyfin User Link Validation

### Objective

Prevent invalid Jellyfin user IDs from being stored in Atlas profiles.

### Completed

- Added `JellyfinProvider.get_user()` for validated Jellyfin identity lookup.
- Added response-shape validation for Jellyfin user payloads.
- Added requested-versus-returned user ID matching.
- Updated `atlas user link-jellyfin` to verify the user through Jellyfin before persistence.
- Updated not-found errors to use resource-neutral wording.
- Ensured failed replacement attempts do not overwrite an existing valid Jellyfin link.
- Added focused tests for valid users, malformed responses, mismatched identities, and unknown users.

### Verification

- Python compilation passed.
- Bash syntax validation passed.
- `git diff --check` passed.
- Focused Jellyfin provider and user profile tests passed: 18 tests.
- Full regression suite passed: 119 tests.
- Live valid-user linking succeeded.
- Live invalid-user linking was rejected.
- The existing valid Jellyfin association remained unchanged after the failed attempt.

### Result

Jellyfin identity linkage is now validated before persistence and is safe against accidental replacement with nonexistent users.

---

# 2026-07-20

## M-021.4 — Retention CLI

### Objective

Expose Atlas retention decisions through a stable command-line interface with both human-readable and machine-readable output.

### Completed

- Added `atlas.retention_cli`.
- Added `scripts/commands/retention.sh`.
- Added CLI routing.
- Added help integration.
- Added human-readable output.
- Added JSON output.
- Added regression coverage for retention command behavior.

### Verification

- Full regression suite passed: 153 tests.
- No test failures were reported.

### Result

Atlas retention decisions became directly accessible through the Atlas CLI for operators and automation consumers.

---

## M-022.2 — Cleanup CLI

### Objective

Expose cleanup evaluations through a stable command-line interface without introducing media deletion or provider mutation behavior.

### Completed

- Added `atlas.cleanup_cli`.
- Added `scripts/commands/cleanup.sh`.
- Added CLI routing.
- Added help integration.
- Added human-readable output.
- Added JSON output.
- Added dependency injection for cleanup CLI execution.
- Added focused CLI regression coverage.

### Verification

- Full Atlas Core regression suite passed: 167 tests.
- No test failures were reported.
- Human-readable cleanup evaluation output was validated.
- JSON cleanup evaluation output was validated.

### Result

Atlas cleanup evaluations became accessible through a consistent operator and automation interface while remaining read-only.

---

## M-023.3 — Cleanup Execution Planning

### Objective

Introduce a non-destructive execution layer that converts cleanup scan results into an explicit execution plan while guaranteeing that no media, filesystem, or provider state is modified.

### Completed

- Added normalized cleanup execution models.
- Added `CleanupExecutionService`.
- Added dry-run execution planning.
- Added human-readable execution report rendering.
- Added JSON execution output.
- Added `atlas cleanup execute`.
- Added execution CLI dependency injection.
- Added focused execution-model, service, and CLI tests.
- Preserved a read-only execution boundary with no deletion implementation.

### Verification

- `git diff --check` passed.
- Focused cleanup execution tests passed: 13 tests.
- Cleanup regression suite passed: 70 tests.
- Full Atlas Core regression suite passed: 229 tests.
- Live `atlas cleanup execute jellyfin --dry-run` validation passed.
- Live `atlas cleanup execute jellyfin --dry-run --json` validation passed.
- No filesystem mutations occurred.
- No Jellyfin modifications occurred.
- No deletion logic was introduced.

### Result

Atlas gained a complete read-only cleanup planning pipeline:

```text
Jellyfin Provider
    ↓
Cleanup Scanner
    ↓
Cleanup Execution Planner
    ↓
Human / JSON Report
```

Cleanup execution remains intentionally dry-run only, making planned actions observable and reviewable before any future mutation capability is considered.

---

# 2026-07-26

## M-011.1 — Historical Analytics Timeline

### Objective

Replace ad hoc snapshot comparison with a validated, gap-aware historical timeline that provides one stable analytics contract for forecasting and future intelligence features.

### Completed

- Added `SnapshotReader` for controlled ARI snapshot discovery and loading.
- Added `AnalyticsTimelineBuilder` for ordered historical timeline construction.
- Added the normalized `AnalyticsTimeline` domain model.
- Added `AnalyticsComparisonService` for time-aware snapshot comparisons.
- Added timestamp ordering and timeline identity validation.
- Added rejection handling for malformed or incompatible snapshots.
- Added cadence analysis and explicit gap detection.
- Added median-cadence calculation.
- Added normalized serialization through domain `to_dict()` contracts.
- Exported the completed analytics contracts through their package interfaces.
- Added dedicated model, reader, builder, comparison, and integration tests.
- Documented the architecture and operational contract in EDR-0002.

### Live Validation

- Evaluated 44 stored ARI snapshot documents.
- Accepted 33 compatible snapshots into the historical timeline.
- Rejected 11 invalid or incompatible snapshot documents.
- Detected 2 cadence gaps.
- Calculated a median collection cadence of 86,335 seconds.
- Confirmed that rejected snapshots do not corrupt the valid timeline.

### Verification

- Analytics test suite passed: 74 tests.
- Full Atlas Core regression suite passed: 636 tests.
- Five sports integration suites passed.
- `git diff --check` passed.
- Live construction of the 33-snapshot analytics timeline succeeded.

### Result

Atlas now has a validated, ordered, and gap-aware historical analytics timeline that can serve as the authoritative input contract for forecasting, dashboards, recommendations, and future intelligence services.

---

## M-012.1 — Forecast Engine Implementation

### Objective

Extend the original Forecast Engine into a validated, timeline-driven capacity forecasting system built upon the Analytics Timeline contract, producing explainable predictions while remaining resilient to incomplete historical data.

### Completed

- Refactored forecasting to consume `AnalyticsTimeline` instead of direct snapshot access.
- Added timeline-aware forecast generation.
- Added storage growth-rate calculations.
- Added capacity exhaustion estimation.
- Added remaining-days calculation.
- Added projected exhaustion date.
- Added forecast confidence classification.
- Added explicit Unknown forecast state for insufficient history.
- Added gap-aware forecast handling.
- Added normalized forecast domain contracts and serialization.
- Added comprehensive forecast regression tests.
- Documented the architecture and forecasting contract in EDR-0003.

### Live Validation

- Successfully generated forecasts from the validated 33-snapshot historical timeline.
- Confirmed cadence gaps do not invalidate forecasting.
- Confirmed insufficient historical data returns an explicit Unknown state rather than unreliable projections.

### Verification

- Forecast functionality validated against the production ARI snapshot history.
- Full Analytics regression suite passed.
- Full Atlas Core regression suite passed: 636 tests.
- `git diff --check` passed.

### Result

Atlas forecasting is now driven by a validated historical timeline, producing deterministic, explainable capacity forecasts while remaining isolated from filesystem implementation details.

---

## AEB-0002.3.5 — Authentication Refresh Orchestration

### Objective

Complete the Atlas API refresh-token transport and identity-resolution flow so
an authenticated session can rotate its access and refresh token pair without
contacting Jellyfin or duplicating authentication logic.

### Completed

- Added `POST /api/v1/auth/refresh`.
- Added refresh-token request validation through the existing
  `RefreshRequest` contract.
- Added `resolve_refresh_user()` for refresh-token identity resolution.
- Refactored access-token and refresh-token handling through the shared
  `_resolve_token_user()` dependency helper.
- Enforced refresh-token type validation through `TokenType.REFRESH`.
- Preserved the Atlas user profile store as the authoritative active-user
  source.
- Delegated token-pair rotation to `AuthenticationService.refresh()`.
- Returned a stable unauthorized response for invalid, expired, mismatched, or
  inactive refresh identities.
- Preserved the no-Jellyfin-call boundary during refresh.
- Added dedicated HTTP contract tests for the refresh route.

### Verification

- `git diff --check` passed.
- Targeted authentication suite passed: 20 tests.
- Full Atlas API regression suite passed: 98 tests.
- Successful token rotation was verified.
- Invalid refresh identity handling was verified.
- Refresh-token user mismatch handling was verified.
- Empty refresh-token request validation was verified.
- Unknown request-field rejection was verified.

### Result

Atlas now provides a validated refresh-token endpoint that resolves the current
active Atlas identity and rotates the token pair through the authentication
service while preserving clean transport, identity, token, and provider
boundaries.

---

# Current Status

**Development State:** Active release-candidate development

## Platform Capabilities

- Production Docker-based media platform.
- Operational Atlas CLI with modular command routing.
- Jellyfin, Sonarr, Radarr, Prowlarr, qBittorrent, and supporting-service integration.
- VPN-isolated download traffic through Gluetun and Windscribe.
- Separate standard-media and anime acquisition workflows.
- Centralized media-quality management through Recyclarr.
- Atlas Retention Intelligence snapshot collection and reporting.
- Platform, media, Docker, VPN, storage, and snapshot-freshness health checks.
- Validated historical analytics timelines.
- Snapshot rejection, cadence analysis, and gap detection.
- Timeline-driven storage and capacity forecasting.
- Explicit Unknown forecast handling for insufficient history.
- Operational recommendation infrastructure.
- Atlas-native user identities and Jellyfin account linkage.
- Secure invitation-based registration.
- Transactional Atlas and Jellyfin user provisioning.
- Durable provider-neutral favorites infrastructure.
- Jellyfin-backed metadata enrichment.
- Retention policy evaluation through human-readable and JSON CLI output.
- Cleanup evaluation through human-readable and JSON CLI output.
- Non-destructive cleanup execution planning.
- Dry-run-only cleanup execution with no deletion or provider mutation behavior.
- Modular sports platform foundation and integration-test coverage.
- Architecture and engineering decisions recorded through ADR and EDR documents.

## Current Verification Baseline

- Analytics test suite: 74 passing.
- Full Atlas Core regression suite: 636 passing.
- Sports integration suites: 5 passing.
- Production ARI snapshot documents evaluated: 44.
- Compatible snapshots accepted: 33.
- Invalid or incompatible snapshots rejected: 11.
- Cadence gaps detected: 2.
- Median snapshot cadence: 86,335 seconds.

## Operational Safety Boundaries

- Cleanup execution remains dry-run only.
- No media deletion logic is implemented.
- No cleanup workflow mutates Jellyfin state.
- No cleanup workflow mutates the media filesystem.
- Invalid historical snapshots are rejected without corrupting valid timelines.
- Insufficient forecast history produces an explicit Unknown state.

## Next Planned Work

- Complete the Backup and Restore Guide.
- Complete the Administrator Guide.
- Review the lifecycle of the orphaned `atlas-sports-controller` container before removal.
- Run the final documentation consistency and Markdown validation pass.
- Review the complete staged documentation diff.
- Commit the documentation cleanup as a dedicated repository change.
- Continue production-readiness work toward the Project Atlas v1.0 release.
---

<!-- AEB-0002.4: build-log -->

## 2026-07-27 — AEB-0002.4 Authorization Enforcement Integration

### Objective

Integrate the existing Atlas authorization service with protected dashboard
routes so access is governed by explicit permissions rather than
authentication alone.

### Implementation

- Added the reusable `require_dashboard_read` dependency for
  `atlas.dashboard.read`.
- Applied `require_dashboard_read` to
  `GET /api/v1/dashboard/summary`.
- Added the reusable `require_media_dashboard_read` dependency for
  `media.read`.
- Applied `require_media_dashboard_read` to
  `GET /api/v1/dashboard/media`.
- Preserved `GET /api/v1/health` as a public liveness endpoint for container,
  proxy, and monitoring health checks.
- Updated dashboard endpoint tests to override the composed permission
  dependencies instead of bypassing authorization through
  `get_current_user`.
- Added explicit regression coverage for HTTP 401 and HTTP 403 responses
  while preserving existing successful-response contracts.

### Validation

- Dashboard endpoint tests: 4 passed.
- Media dashboard endpoint tests: 4 passed.
- Complete Atlas API test suite: 100 passed.
- Python compilation: passed.
- Git whitespace validation: passed.
- Temporary AEB-0002.4 source backups removed after successful validation.

### Result

AEB-0002.4 is complete. Atlas dashboard routes now use the established
permission-based authorization boundary, while the public health contract
remains unchanged.

---

# 2026-07-27

## AEB-0003.1 — Authenticated Request Pipeline

### Objective

Strengthen the existing Portal request architecture with reliable token rotation and consistent authentication-failure handling.

### Completed

- Preserved the existing separation between one-attempt transport and multi-attempt client orchestration.
- Added a process-local authentication lifecycle coordinator.
- Added single-flight refresh behavior so concurrent HTTP 401 responses share one token-rotation request.
- Added automatic one-time replay with the replacement access token.
- Added explicit authentication, authorization, and expired-session error contracts.
- Connected the authentication provider to the request lifecycle without coupling the API client to React.
- Added isolated lifecycle observations for refresh and expiration events.
- Added focused authentication-pipeline regression tests.

### Engineering Principles

- Retained all established Project Atlas philosophies.
- Strengthened existing abstractions before introducing new ones.
- Kept authentication orchestration outside the one-attempt HTTP transport.
- Preserved API authorization as the final source of truth.
- Prevented observability callbacks from changing request or session behavior.

### Validation

- Portal unit tests.
- Prettier formatting verification.
- ESLint verification.
- TypeScript verification.
- Next.js production build.
- Repository patch-integrity verification.

### Result

The Portal can recover transparently from an expired access token while ensuring refresh failures and repeated unauthorized responses safely terminate the active session.

---

# 2026-07-27

## AEB-0003.2 — Authenticated Service Layer

### Objective

Remove access-token ownership from Portal feature hooks while preserving the established authenticated request, refresh, replay, and expiration pipeline.

### Completed

- Added a shared authenticated service request boundary.
- Centralized active access-token retrieval through the existing in-memory authentication store.
- Removed explicit access-token parameters from dashboard services.
- Removed explicit access-token parameters from dashboard feature APIs.
- Reduced dashboard hooks to authentication state and UI request state.
- Preserved explicit token handling for login, refresh, and current-user authentication.
- Added focused authenticated-service regression coverage.

### Architecture

- React authentication context owns session creation, rotation, and expiration.
- Authentication storage owns the current in-memory session.
- Authenticated services resolve credentials through one central boundary.
- The API client owns token refresh, authenticated replay, and retry orchestration.
- The HTTP transport owns one request attempt.
- Feature hooks own loading, ready, error, cancellation, and refresh state.

### Validation

- Portal unit tests.
- Prettier verification.
- ESLint verification.
- TypeScript verification.
- Next.js production build.
- Atlas API regression tests.
- Patch-integrity verification.

### Result

Protected Portal services no longer require UI callers to retrieve or pass access tokens.

## PAI-0002 — Effective Authorization Session Contract

Extended the authenticated-user transport contract so Portal clients can
consume authorization state resolved by the Atlas API rather than rebuilding
role permissions independently.

### Changes

- Added `granted_permission_patterns` and `denied_permission_patterns` to the
  `/api/v1/auth/me` response.
- Resolved the current profile through the existing `AuthorizationService`.
- Preserved explicit denials as a separate ordered transport collection.
- Returned normalized effective roles, including legacy role aliases.
- Added route-level regression coverage for role grants, direct grants,
  explicit denials, multiple-role merging, and stable response serialization.

### Architectural result

The API remains the sole authorization authority. The Portal can now migrate
its presentation checks to the effective session contract without adding a
second authorization request, cache, or duplicated role catalog.

## PAI-0003 — Portal Effective Authorization Migration

Migrated Portal presentation authorization from a duplicated role catalog to
the effective grant and denial patterns returned by the Atlas API session
contract.

### Changes

- Extended `AtlasCurrentUserResponse` with effective grant and denial patterns.
- Replaced role-based Portal permission evaluation with effective-pattern
  evaluation.
- Applied explicit denials before exact or wildcard grants.
- Migrated `usePermission()` to the authenticated session contract.
- Migrated Portal navigation filtering and sidebar rendering.
- Preserved `ATLAS_PERMISSIONS` as stable typed feature identifiers.
- Removed Portal runtime ownership of role aliases and role permission maps.
- Added regression coverage for wildcard grants, direct grants, denial
  precedence, empty authorization state, and navigation visibility.

### Architectural result

The API now owns role resolution, permission merging, direct overrides, and
enforcement. The Portal consumes that resolved state solely for presentation.
Adding or changing an Atlas role no longer requires duplicating its permission
definition in the Portal.

## PAI-0004.2 — Portal Page Authorization Boundary

Introduced the canonical presentation and permission boundary for protected
Portal pages before expanding the authenticated route tree.

### Changes

- Added `PortalPage` as the standard protected-page contract.
- Centralized page permission checks through the existing `RequirePermission`
  component and API-resolved effective authorization state.
- Added a reusable `PortalAccessDenied` presentation with accessible status
  semantics and contextual copy support.
- Standardized Portal page eyebrow, title, description, actions, and content
  regions.
- Added an optional actions slot for future page-level controls.
- Migrated the system dashboard from inline authorization and duplicated page
  markup to the reusable boundary.
- Extended the Portal Vitest include configuration to cover component-level
  TypeScript and TSX tests.
- Added server-rendered component regression coverage for granted access,
  denied access, protected-child isolation, contextual denial content, action
  rendering, and optional page regions.

### Architectural result

The protected App Router layout continues to own authentication, while each
Portal page declares one required permission through a consistent,
presentation-only boundary. The Atlas API remains the authoritative
authorization and enforcement layer.

Future Portal routes can now adopt a small declarative contract without
rebuilding headers, access-denied content, or permission-wrapper markup.

## PAI-0005.2 — Portal Route Model

Evolved the existing Portal navigation catalog into the canonical route model
without introducing a second registry or changing the App Router structure.

### Changes

- Replaced `PortalNavigationItem` with a typed `PortalRoute` contract.
- Added stable route IDs and named access through `PORTAL_ROUTES`.
- Centralized route paths, labels, navigation descriptions, abbreviations,
  permissions, section ownership, and optional page descriptions.
- Derived navigation sections from the canonical route collection.
- Centralized exact dashboard matching and nested feature-route matching.
- Added route lookup through `portalRouteForPathname()`.
- Kept topbar title resolution as a projection of the route model.
- Migrated `PortalNavLink` to the shared route matcher.
- Migrated the dashboard page to its registered label, permission, and page
  description.
- Preserved API-owned authorization and presentation-only Portal filtering.
- Added regression coverage for route identity, path uniqueness, named route
  access, navigation projection, exact and nested matching, route lookup, page
  titles, wildcard grants, direct grants, and explicit-denial precedence.

### Architectural result

Portal route reasoning now has one source of truth. Navigation, active-link
state, topbar titles, and page declarations consume the same typed route
records instead of independently interpreting paths.

Next.js page files still own actual route implementation and browser metadata.
The model deliberately avoids module registration, dynamic loading, icons,
breadcrumbs, and other framework concerns until real feature routes require
them.

## M-016.1 — Media Portal Foundation

Implemented the first feature route beneath the authenticated Atlas Portal and
used it to validate the complete authentication, authorization, route-model,
page-boundary, service, state, and presentation architecture.

### Changes

- Added the protected `/portal/media` App Router page.
- Added server-owned Next.js metadata for the Media route.
- Consumed `PORTAL_ROUTES.media` for page label, description, and permission.
- Added a Media-owned feature package with API, service, hook, component, type,
  and export boundaries.
- Added normalized Media library and snapshot factories.
- Validated stable library identity, unique children, availability/count
  contracts, optional text, and timestamps.
- Added aggregate counts for configured libraries, available libraries,
  unavailable libraries, and represented items.
- Reused `/dashboard/media` through a temporary Media-owned transport adapter.
- Kept dashboard transport naming out of Media domain callers.
- Added loading, ready, successful-empty, partial-availability, and request-error
  states.
- Added page-level refresh through the existing `PortalPage` actions slot.
- Kept unavailable libraries visible with their provider detail.
- Added responsive Media summary and library presentation.
- Added domain and server-rendered component regression coverage.

### Architectural result

The Portal now contains its first implemented feature destination beyond the
dashboard. The Media feature owns its domain and presentation contracts while
temporarily reusing an existing transport endpoint.

This keeps M-016.1 small and product-focused without making the dashboard
feature a shared domain dependency or introducing a duplicate API service
before richer Media requirements exist.

## M-016.1a — Media Contract Boundary Refinement

Corrected the first Media Portal implementation after its architectural guard
detected Dashboard-owned transport names inside the new Media feature.

### Changes

- Removed imports of `AtlasDashboardMediaLibraryResponse` and
  `AtlasDashboardMediaSummaryResponse` from `features/media`.
- Added private Media adapter DTOs describing the temporary wire response.
- Preserved `/dashboard/media` as the current transport endpoint.
- Continued mapping all transport data immediately into Media-owned normalized
  domain models.
- Kept Dashboard domain types, hooks, services, and presentation components out
  of the Media feature.
- Moved page refresh-state publication from render-time execution into a React
  effect.

### Architectural result

The Media feature may temporarily consume an endpoint whose URL is
dashboard-oriented, but it no longer depends on Dashboard transport or domain
contracts.

A future dedicated Media API endpoint can replace the adapter path and DTO
without changing Media models, hooks, components, or route callers.

---

## M-016.2 — Media Library Detail API

Completed:

- MediaLibraryDetail domain model
- API response schema
- Service layer
- Media library detail endpoint
- Permission integration
- OpenAPI registration
- Comprehensive test coverage

Validation:

- Focused API tests: 24 passed
- API suite: 127 passed (5 subtests)
- Core suite: 656 passed (104 subtests)

Engineering Notes:

- Verified compatibility with FastAPI's newer `_IncludedRouter` implementation.
- Updated validation strategy to rely on the OpenAPI contract instead of internal route inspection.
- Confirmed protected endpoint behavior requires valid JWT configuration before authorization.

Status:

M-016.2 complete and ready for review.


---

## M-019.5.1 — Engineering Toolkit Test Command

Integrated the Engineering Toolkit contract-test runner into the public
`atlas-dev` command interface.

### Changes

- Added the executable `scripts/dev/commands/test.sh` command adapter.
- Exposed contract-test execution through `scripts/dev/atlas-dev test`.
- Kept `scripts/dev/tests/run-tests` as the low-level test-suite runner.
- Preserved the runner's success, test-failure, misuse, and infrastructure exit
  statuses.
- Rejected unexpected command arguments with status `2`.
- Added the `test` command and usage example to `atlas-dev` help output.
- Preserved dynamic command discovery through the existing toolkit dispatcher.

### Validation

- Contract-test suites discovered: 1.
- Contract-test suites passed: 1.
- Contract-test suites failed: 0.
- Runtime contract assertions passed: 9.
- Engineering Toolkit Bash files validated: 12.
- Bash syntax validation passed.
- Git diff-format validation passed.
- Unexpected command arguments returned status `2`.

### Architectural result

The Engineering Toolkit now exposes contract testing through the same stable
public command interface used for discovery and validation:

```bash
scripts/dev/atlas-dev test
```

The command remains a thin adapter around the standalone contract-test runner.
This preserves a reusable low-level execution boundary while keeping
`atlas-dev` as the stable developer-facing entry point.

---

# 2026-08-01

## M-018 — Atlas Infrastructure Management: Service Lifecycle Foundation

### Objective

Create a safe, observable, provider-independent infrastructure-management
foundation that can power the Atlas CLI, API, scheduler, and Admin Portal
without exposing raw Docker or shell execution to user-facing interfaces.

### Architecture

Atlas now uses the following read-only dependency flow:

```text
CLI / API / Admin Portal / Scheduler
                |
                v
    ServiceLifecycleService
                |
                v
    ServiceLifecycleProvider
                |
                v
      DockerComposeProvider
                |
                v
          Docker Compose
```

ADR 0010 defines the Service Lifecycle domain, provider boundary, command
safety boundary, guarded lifecycle requirements, Admin Portal responsibilities,
responsive administration expectations, testing requirements, and relationship
to the existing Portal and domain architecture ADRs.

### Completed — Domain Foundation

- Added immutable `ManagedService` identity contracts.
- Added normalized `ServiceImage` contracts.
- Added normalized `ServiceRuntime` contracts.
- Added `ServiceHealthStatus` and `ServiceHealth` contracts.
- Normalized service identifiers, optional text, child collections, image
  references, health details, and timestamps.
- Added stable `to_dict()` serialization for every public domain model.
- Exported all public contracts through `atlas.service_lifecycle`.
- Added comprehensive model contract tests.

### Completed — Provider and Orchestration Layers

- Added the provider-independent `ServiceLifecycleProvider` interface.
- Added `ServiceLifecycleService` as the validation and orchestration boundary.
- Enforced deterministic managed-service ordering.
- Rejected duplicate service identifiers.
- Normalized requested service identifiers before provider calls.
- Preserved known domain failures and translated unexpected provider failures
  into stable `ServiceLifecycleError` messages.
- Added dedicated provider and service-layer contract tests.

### Completed — Read-Only Docker Compose Provider

- Added the `DockerComposeProvider` foundation.
- Discovered 15 configured Atlas-managed Compose services from normalized
  Compose configuration.
- Inspected individual managed-service identities.
- Normalized running, stopped, restarting, and failed runtime states.
- Inspected configured and running image references, repositories, tags,
  digests when available, and image IDs.
- Reported restart counts, timestamps, exit codes, status messages, and service
  dependencies.
- Evaluated Docker health state into Atlas health status, score, warnings,
  errors, and action-required signals.
- Preserved a strict read-only boundary throughout provider development.

### Completed — Service Lifecycle CLI

Added the following public commands:

```bash
atlas service list [--json]
atlas service show <identifier> [--json]
atlas service runtime <identifier> [--json]
atlas service health <identifier> [--json]
```

Preserved the existing plural command as a compatibility alias:

```bash
atlas services [--json]
```

The compatibility command now uses normalized Service Lifecycle models instead
of exposing raw `docker compose ps` output.

### Live Validation

- Verified managed-service discovery across all 15 configured services.
- Verified combined identity, runtime, image, and health output for Jellyfin.
- Verified Sonarr health as degraded with score 85 when no Docker health check
  is configured.
- Verified Jellyfin and Gluetun health as healthy with score 100.
- Verified qBittorrent dependency normalization through Gluetun.
- Verified human-readable and JSON output for list, show, runtime, and health
  commands.
- Confirmed that no start, stop, restart, pull, remove, or update operation was
  introduced.

### Test Baseline

- Focused Service Lifecycle CLI contracts: 17 passed.
- Complete Core regression suite: 1,379 passed.
- Core subtests: 104 passed.
- Python compilation passed.
- Bash syntax validation passed.
- Git whitespace validation passed.

### Engineering Workflow Decision

Project Atlas will use guarded full-file heredoc rewrites for future code and
documentation changes whenever practical.

Each change must:

1. Back up every affected existing file.
2. Write complete verified content to a temporary file.
3. Validate syntax before installation.
4. Install atomically.
5. Run focused tests.
6. Run the full regression suite.
7. Perform live validation when applicable.
8. Review the Git diff.
9. Commit and push as a focused engineering increment.

This replaces fragile search-and-replace installers that can fail when valid
code formatting or structure evolves.

### Current Scope

The next M-018 increment is aggregate infrastructure health:

```bash
atlas service health
atlas service health --json
```

This must preserve the existing single-service forms and add overall score,
status counts, per-service results, combined warnings and errors, and an
evaluation timestamp.

### Remaining M-018 Scope

- Aggregate infrastructure health.
- Update-availability inspection.
- Maintenance history and lifecycle audit events.
- Dependency graph and service diagnostics.
- Guarded lifecycle planning and authorization boundaries.
- Admin Portal service overview, detail, health, history, failure, rollback,
  phone, and tablet experiences.

### Deferred Scope

Mutating lifecycle commands remain deferred until Atlas has administrator
authorization, allow-listed identifiers, dry-run planning, operation locking,
pre-update capture, post-update health validation, dependency-aware ordering,
rollback, and audit history.

### Result

Atlas now owns a normalized infrastructure domain instead of relying on direct
Docker helper commands. The same validated contracts can power the CLI today
and the API, scheduler, and responsive Admin Portal in future increments.

---

# 2026-08-01

## M-018.7 — Aggregate Infrastructure Health

### Objective

Introduce provider-independent aggregate infrastructure health reporting while
preserving the existing per-service inspection workflow and the read-only Service
Lifecycle boundary.

### Completed

- Added aggregate infrastructure health evaluation to `ServiceLifecycleService`.
- Added conservative aggregate scoring from normalized per-service health scores.
- Added overall Healthy, Degraded, Unhealthy, and Unknown classification.
- Added service counts by health status.
- Added deterministic services-requiring-attention reporting.
- Added aggregate warning and error reporting.
- Added normalized evaluation timestamps and JSON serialization.
- Added `atlas service health` for human-readable aggregate reporting.
- Added `atlas service health --json` for machine-readable aggregate reporting.
- Preserved `atlas service health <identifier> [--json]`.
- Preserved provider independence; no Docker Compose provider changes were required.
- Preserved the read-only guarantee with no start, stop, restart, pull, update, or
  other Docker mutation operations.

### Engineering Decisions

- Aggregate business rules remain in the Service Lifecycle orchestration layer.
- The CLI is limited to argument handling and rendering normalized reports.
- An empty managed-service inventory produces an explicit Unknown report.
- Aggregate errors force an Unhealthy result.
- The aggregate score uses the conservative integer average of individual service
  scores.
- Services remain visible under Attention Required when warnings, errors, or a
  non-Healthy status are present.

### Verification

- Guarded SHA-256 source verification passed.
- Timestamped rollback backup created successfully.
- Python compilation passed.
- Bash syntax validation passed.
- `git diff --check` passed.
- Focused aggregate-health service and CLI tests passed: 70.
- Service Lifecycle regression suite passed: 534.
- Atlas Core regression suite passed: 648.
- Sports integration suites passed: 5.
- Service Lifecycle help and command registration validation passed.

### Live Validation

- Validated against the production Docker Compose stack.
- Managed services discovered: 15.
- Overall score: 89/100.
- Overall status: Degraded.
- Healthy services: 4.
- Degraded services: 11.
- Unhealthy services: 0.
- Unknown services: 0.
- Aggregate errors: 0.
- The 11 degraded services were running and were reported for attention because no
  Docker health check was configured.
- Individual Jellyfin health remained Healthy at 100/100 with no warnings or
  errors.

### Result

Atlas now has a canonical aggregate infrastructure health contract shared by the
Service Lifecycle orchestration layer and CLI. This contract provides the
foundation for Infrastructure Summary, Service Dependency Graph, Service Doctor,
Update Availability, Maintenance History, future Atlas API endpoints, and the
Administration Portal while preserving observability before automation.

---

# 2026-08-01

## M-018.8 — Infrastructure Summary and Architecture Documentation

### Objective

Establish a normalized infrastructure-summary contract for Service Lifecycle and
create permanent subsystem architecture documentation without introducing Docker
mutations or provider-specific presentation logic.

### Completed

- Added immutable `ServiceRuntimeEntry` runtime-report entries.
- Added immutable `InfrastructureSummary` reporting with normalized serialization.
- Added provider and Compose-project reporting.
- Added total, enabled, and disabled service counts.
- Added running, stopped, restarting, failed, and unknown runtime counts.
- Reused aggregate health counts, score, status, and attention reporting.
- Added `ServiceLifecycleService.inspect_summary()`.
- Reused one deterministic managed-service inventory for runtime and health
  orchestration.
- Added `atlas service summary` human-readable reporting.
- Added `atlas service summary --json` machine-readable reporting.
- Preserved every existing Service Lifecycle command and compatibility alias.
- Added `docs/architecture/README.md` as the architecture-documentation entry point.
- Added `docs/architecture/SERVICE_LIFECYCLE.md` as the canonical subsystem
  specification.
- Preserved `docs/architecture/PORTAL.md` without modification.

### Engineering Decisions

- Summary business rules remain in the provider-independent service layer.
- The CLI performs argument handling and rendering only.
- Providers remain unaware of CLI, JSON, API, and Portal presentation concerns.
- Runtime and health report identities must match exactly.
- Runtime states are normalized into running, stopped, restarting, failed, or
  unknown summary categories.
- Architecture documents describe stable design and contracts rather than sprint
  history or release notes.
- Project Atlas milestones now follow design, source implementation, focused
  validation, full regression, live validation, documentation, architecture
  review, commit, and push.

### Verification

- Guarded SHA-256 source verification passed.
- Timestamped rollback backup created successfully.
- Python compilation passed.
- Bash syntax validation passed.
- `git diff --check` passed.
- Focused Service Lifecycle service and CLI tests passed: 76.
- Service Lifecycle regression suite passed: 540.
- Atlas Core regression suite passed: 648.
- Sports integration suites passed: 5.
- Service Lifecycle help and summary command registration passed.

### Live Validation

- Provider: `docker-compose`.
- Compose project: `project-atlas`.
- Managed services: 15.
- Enabled services: 15.
- Disabled services: 0.
- Running services: 15.
- Stopped services: 0.
- Restarting services: 0.
- Failed services: 0.
- Unknown runtime services: 0.
- Healthy services: 4.
- Degraded services: 11.
- Unhealthy services: 0.
- Unknown health services: 0.
- Overall score: 89/100.
- Overall status: Degraded.
- Services requiring attention: 11.
- Existing aggregate health, individual Jellyfin health, service listing, and help
  commands remained operational.

### Result

Atlas now exposes a canonical infrastructure-summary contract suitable for the
CLI, future Atlas API endpoints, the Administration Portal, Service Doctor,
Service Dependency Graph, update discovery, and maintenance history. Service
Lifecycle remains fully read-only and provider-independent while its architecture
is now documented as a stable living specification.


---

# 2026-08-02

## M-018.12 — Service Doctor CLI Integration

### Objective

Expose the provider-independent Service Doctor through the Atlas CLI while
preserving the canonical `DoctorReport` JSON contract for future API and Admin
Portal use.

### Completed

- Added `atlas service doctor`.
- Added `atlas service doctor --json`.
- Added deterministic human-readable severity grouping.
- Registered the command in Service Lifecycle and global help.
- Reused `ServiceDoctor` without duplicating diagnostic logic in the CLI.
- Preserved the read-only Service Lifecycle boundary.

### Validation

- Python compilation.
- Bash syntax validation.
- Focused Service Doctor and CLI tests.
- Service Lifecycle regression suite.
- `git diff --check`.

---

# 2026-08-02

## M-018.13 — Service Doctor Diagnostic Refinement

### Objective

Reduce diagnostic noise by ensuring one finding is emitted for each underlying
operational condition.

### Completed

- Suppressed duplicate `health-degraded` findings when degradation is caused
  solely by a missing Docker health check.
- Preserved independent health findings when additional warnings or errors exist.
- Added focused root-cause deduplication regression tests.
- Added live Doctor JSON validation for duplicate missing-health-check findings.

### Validation

- Python compilation.
- Focused Service Doctor tests.
- Service Lifecycle regression suite.
- Real `atlas service doctor --json` execution.
- `git diff --check`.

---

# 2026-08-02

## M-018.20 — Update Discovery Domain Contracts

### Objective

Establish normalized, provider-independent contracts for read-only service image
update discovery before adding provider, registry, CLI, API, or Portal behavior.

### Completed

- Added `UpdateStatus`.
- Added normalized `ImageReference` parsing and serialization.
- Added `ServiceUpdate` with child-contract and update-state validation.
- Added deterministic `UpdateReport` aggregation, counts, attention items, and
  serialization.
- Exported all contracts through `atlas.service_lifecycle`.
- Added dedicated Core model tests.
- Documented the read-only boundary and future shared CLI/API/Portal contract.

### Validation

- Python compilation.
- Focused update-model tests.
- Existing Service Lifecycle model and Doctor-model regression tests.
- Public import validation.
- `git diff --check`.

---

# 2026-08-02

## M-018.21 — Local Update Metadata Provider

### Objective

Expose locally verifiable service image metadata through the provider boundary
without registry access, image pulls, or update-availability claims.

### Completed

- Added `inspect_update()` to `ServiceLifecycleProvider`.
- Implemented local Docker Compose update metadata discovery.
- Reported mutable `latest` tags without claiming an available update.
- Reported pinned tags and digest references as unknown pending registry comparison.
- Corrected digest-only image references so null tags do not become `latest`.
- Added provider, Docker Compose, and image-contract tests.

### Validation

- Python compilation.
- Provider abstraction tests.
- Docker Compose provider tests.
- Update-model and Service Lifecycle regression tests.
- `git diff --check`.

---

# 2026-08-02

## M-018.21.5 — Repository Engineering Tooling

### Objective

Establish a permanent repository layout and canonical guidance for Atlas
engineering utilities while removing disposable helper scripts from the
repository root.

### Completed

- Added the `tools/` hierarchy for apply, maintenance, migration, release, and
  archived tooling.
- Added directory-specific safety and lifecycle guidance.
- Added `docs/ENGINEERING_GUIDE.md`.
- Linked the engineering checklist to the canonical guide.
- Archived completed root-level M-018.21 helper scripts outside the working tree.
- Preserved all in-progress Update Discovery source, tests, and documentation.

### Validation

- Verified the active development branch.
- Verified required Update Discovery files.
- Confirmed tracked files were not moved during cleanup.
- Checked documentation links and repository whitespace.

---

# 2026-08-02

## M-018.22 — Update Discovery Service

### Objective

Add the provider-independent orchestration layer for validated single-service
and platform-wide read-only update discovery.

### Completed

- Added immutable `ServiceUpdateService`.
- Added validated `inspect_update()`.
- Added deterministic `inspect_updates()` aggregation.
- Reused `ServiceLifecycleService` inventory and identity validation.
- Enforced provider result type, identifier, and service-name contracts.
- Preserved known domain errors and translated unexpected provider failures.
- Exported the service through `atlas.service_lifecycle`.
- Added dedicated orchestration tests.
- Documented the service boundary for future CLI, API, and Admin Portal use.

### Validation

- Python compilation.
- Update-service focused tests.
- Update-model, provider, service, Doctor, and CLI regressions.
- Public import validation.
- `git diff --check`.

---

# 2026-08-02

## M-018.23 — Service Updates CLI

### Objective

Expose provider-independent, read-only Update Discovery through the Atlas CLI
without duplicating service or provider logic.

### Completed

- Added `atlas service updates`.
- Added `atlas service updates --json`.
- Added concise human-readable update summaries.
- Serialized canonical `UpdateReport` JSON without transformation.
- Registered shell dispatch and service/global help.
- Added human, JSON, empty-inventory, error, and help tests.
- Documented the CLI boundary for future API and Admin Portal consumers.

### Validation

- Python compilation.
- Shell syntax validation.
- Focused Update Discovery and CLI tests.
- Service Lifecycle regression tests.
- Real human CLI execution.
- Real JSON CLI execution and parsing.
- `git diff --check`.

---

# 2026-08-02

## M-018.24 — Maintenance History Domain Models

### Objective

Establish immutable, provider-independent contracts for Service Lifecycle
maintenance history before adding persistence, service orchestration, CLI, API,
Portal, scheduler, or maintenance execution.

### Completed

- Added `MaintenanceAction`.
- Added `MaintenanceResult`.
- Added normalized `MaintenanceRecord`.
- Added deterministic `MaintenanceReport`.
- Added duration, success, failure, attention, count, and latest-record helpers.
- Exported all contracts through `atlas.service_lifecycle`.
- Added dedicated Core tests.
- Documented the strict read-only boundary and future extension points.

### Validation

- Python compilation.
- Public import validation.
- Focused maintenance-model tests.
- Existing Service Lifecycle model regression tests.
- `git diff --check`.

---

# 2026-08-02

## M-018.24.5 — Service Layer Package Refactor

### Objective

Organize Service Lifecycle service implementations under a dedicated package
before adding Maintenance History orchestration, without changing public
behavior or breaking existing imports.

### Completed

- Added `atlas.service_lifecycle.services`.
- Moved the lifecycle implementation to `services/lifecycle.py`.
- Moved Service Doctor to `services/doctor.py`.
- Moved Update Discovery orchestration to `services/updates.py`.
- Preserved `service.py`, `doctor.py`, and `update.py` as compatibility shims.
- Updated top-level package exports to use the canonical services package.
- Added explicit public and legacy import compatibility tests.
- Archived completed apply helpers outside the working tree.
- Documented the package structure and unchanged read-only boundary.

### Validation

- Python compilation.
- Canonical and legacy import validation.
- Full Service Lifecycle regression.
- Real Service Doctor and Service Updates CLI smoke tests.
- Shell syntax validation.
- `git diff --check`.

---

# 2026-08-02

## M-018.25 — Maintenance History Service

### Objective

Add the provider-independent, read-only orchestration layer for global and
service-specific Maintenance History without persistence or execution.

### Completed

- Added `ServiceMaintenanceHistoryService`.
- Added validated `inspect_history()`.
- Added validated `inspect_service_history()`.
- Added concrete empty-history provider defaults.
- Preserved compatibility for existing providers and test doubles.
- Enforced report, service identifier, and service-name contracts.
- Added canonical, package, and legacy compatibility exports.
- Added dedicated Core tests.
- Documented the future persistence boundary.

### Validation

- Python compilation.
- Public and legacy import validation.
- Maintenance service and model tests.
- Full Service Lifecycle regression.
- Service Doctor and Service Updates CLI smoke tests.
- `git diff --check`.

---

# 2026-08-02

## M-018.26 — Maintenance History CLI

### Objective

Expose global and service-specific read-only Maintenance History through the
Atlas CLI without duplicating service logic or enabling maintenance execution.

### Completed

- Added `atlas service history`.
- Added `atlas service history <identifier>`.
- Added JSON variants for both scopes.
- Added human-readable result counts and ordered record output.
- Serialized canonical `MaintenanceReport` JSON directly.
- Registered service and global help.
- Added global, service-specific, JSON, empty-history, error, and help tests.
- Documented the empty-provider behavior and read-only boundary.

### Validation

- Python compilation.
- Shell syntax validation.
- Focused Maintenance History and CLI tests.
- Full Service Lifecycle regression.
- Live global history human and JSON commands.
- Live service-specific history human and JSON commands.
- JSON contract validation.
- `git diff --check`.

---

# 2026-08-02

## M-018.27 — Service Lifecycle Documentation Completion

### Objective

Complete the architecture, CLI, and Python API documentation for the read-only
Service Lifecycle subsystem before final subsystem validation.

### Completed

- Added the complete Service Lifecycle CLI reference.
- Added the public Python API reference.
- Documented canonical models, services, and provider contracts.
- Documented legacy compatibility module aliases.
- Documented JSON contracts and error behavior.
- Documented Administration Portal integration boundaries.
- Documented the post-v1.0 maintenance workflow boundary.
- Added Service Lifecycle links to the architecture index.
- Added a documentation map to the architecture document.
- Archived the completed M-018.26 apply helper.

### Validation

- Verified all referenced documentation files exist.
- Verified public API exports.
- Verified documented CLI commands are registered.
- Verified Markdown links.
- Ran `git diff --check`.

---

# 2026-08-02

## M-021.1 — Governance Foundation

### Objective

Establish permanent repository locations for engineering specifications, Atlas
Governance, and release certification without changing runtime behavior.

### Completed

- Added the engineering-specification index.
- Added the M-021.1 Governance Foundation specification.
- Added the Atlas Governance index.
- Added the Release Certification index.
- Linked governance, specifications, and releases from the Engineering Guide.
- Added governance review gates to the Engineering Checklist.
- Added M-021 Atlas Governance to the Roadmap.

### Validation

- Documentation structure validation.
- Local Markdown-link validation.
- Living-document reference validation.
- Executable-source diff validation.
- `git diff --check`.

---

# 2026-08-02

## M-021.2 — Engineering Charter

### Objective

Create the permanent engineering constitution for Project Atlas and link it
from the existing governance and engineering documentation.

### Completed

- Added `docs/governance/ENGINEERING_CHARTER.md`.
- Formalized the Atlas mission and platform vision.
- Formalized the core engineering principles.
- Formalized the repository-as-source-of-truth philosophy.
- Formalized subsystem independence and public-contract expectations.
- Formalized the engineering lifecycle and definition of done.
- Added Charter review gates to the Engineering Checklist.
- Linked the Charter from the Governance index and Engineering Guide.

### Validation

- Documentation existence validation.
- Local Markdown-link validation.
- Required Charter-section validation.
- Living-document marker validation.
- `git diff --check`.

---

# 2026-08-02

## M-021.3 — Development Workflow

### Completed

- Added the permanent Atlas Development Workflow.
- Linked governance and engineering documentation.
- Added workflow review checklist.

### Validation

- Markdown validation.
- Link validation.
- `git diff --check`.

---

# 2026-08-02

## M-021.4 — Coding Standards

### Completed

- Added the permanent Coding Standards document.
- Linked governance and engineering documentation.
- Added coding standards review gates.

### Validation

- Markdown validation.
- Link validation.
- Required section validation.
- `git diff --check`.

---

# 2026-08-02

## M-021.5 — Testing Standard

### Completed

- Added the permanent Atlas Testing Standard.
- Formalized unit, model, service, provider, CLI, contract, integration,
  regression, runtime, compatibility, and release-audit validation.
- Linked the Testing Standard from governance and engineering documentation.
- Added testing review gates to the Engineering Checklist.
- Marked the Testing Standard complete in the Roadmap.

### Validation

- Required-section validation.
- Local Markdown-link validation.
- Living-document marker validation.
- `git diff --check`.

---

# 2026-08-02

## M-021.6 — Documentation Standard

### Completed

- Added the permanent Atlas Documentation Standard.
- Formalized architecture, API, CLI, operational, governance, decision-record,
  release, user-facing, compatibility, and safety documentation requirements.
- Formalized Roadmap, Changelog, and Build Log responsibilities.
- Linked the standard from governance and engineering documentation.
- Added documentation review gates to the Engineering Checklist.
- Marked the Documentation Standard complete in the Roadmap.

### Validation

- Required-section validation.
- Local Markdown-link validation.
- Living-document marker validation.
- `git diff --check`.

---

# 2026-08-02

## M-021.7 — ADR Policy

### Completed

- Added the permanent Atlas ADR Policy.
- Formalized ADR criteria, lifecycle, statuses, required sections, review,
  approval, implementation, supersession, deprecation, archival, and validation.
- Defined relationships among ADRs, specifications, architecture, governance,
  and release documentation.
- Linked the ADR Policy from governance and engineering documentation.
- Added ADR review gates to the Engineering Checklist.
- Marked the ADR Policy complete in the Roadmap.

### Validation

- Required-section validation.
- Local Markdown-link validation.
- Living-document marker validation.
- `git diff --check`.

---

# 2026-08-02

## M-021.8 — Versioning and Contributing

### Completed

- Added the permanent Atlas Versioning and Contributing Standard.
- Formalized Semantic Versioning, release types, branch strategy, commit
  conventions, staging, review, merge, compatibility, deprecation, dependency,
  revert, emergency, security, and release-impact requirements.
- Linked the standard from governance and engineering documentation.
- Added contribution review gates to the Engineering Checklist.
- Marked Versioning and Contributing guidance complete in the Roadmap.

### Validation

- Required-section validation.
- Local Markdown-link validation.
- Living-document marker validation.
- `git diff --check`.

---

# 2026-08-02

## M-021.9 — Release Policy

### Completed

- Added the permanent Atlas Release Policy.
- Formalized release types, readiness gates, validation, compatibility,
  migration, security, performance, rollback, certification, approval,
  publication, maintenance, support, and end-of-life requirements.
- Added a canonical release certification checklist.
- Linked the Release Policy from governance and engineering documentation.
- Added release review gates to the Engineering Checklist.
- Marked Release Policy complete in the Roadmap.

### Validation

- Required-section validation.
- Local Markdown-link validation.
- Living-document marker validation.
- `git diff --check`.

---

# 2026-08-02

## M-022.1.2 — Atlas v1.0 Release Plan

### Objective

Establish the authoritative release contract governing all remaining work
required to publish Project Atlas v1.0.0.

### Completed

- Added `docs/releases/V1_RELEASE_PLAN.md`.
- Defined the Atlas v1.0 product vision and approved scope.
- Defined explicit non-goals and deferred post-v1.0 capabilities.
- Locked the release blockers and acceptance criteria.
- Added the release validation matrix.
- Established User Experience Certification as a release gate.
- Defined critical end-user and administrator journeys.
- Defined the approved execution sequence through v1.0.0.
- Linked the release plan from the Release Documentation index.

### Validation

- Required-heading validation.
- Duplicate-section validation.
- Local Markdown-link validation.
- `git diff --check`.

---

## M-022.1.3 — Atlas Release Checklist

### Objective

Establish the permanent release checklist used to certify all Atlas releases.

### Completed

- Added `docs/releases/RELEASE_CHECKLIST.md`.
- Defined engineering readiness validation.
- Defined repository readiness validation.
- Defined runtime and operational validation.
- Defined documentation and security review.
- Defined backup and recovery validation.
- Defined user and administrator experience certification.
- Defined release packaging and publication gates.
- Defined post-release validation requirements.
- Added the permanent release approval record.

### Validation

- Section validation completed.
- Duplicate heading validation completed.
- Local Markdown link validation completed.
- Checklist item validation completed.
- `git diff --check` passed.

---

# 2026-08-02

## M-022.1.4 — Atlas User Acceptance

### Objective

Establish the permanent User Acceptance Certification process used to verify
that Atlas releases provide complete, understandable, reliable, and
supportable experiences for end users and administrators.

### Completed

- Added `docs/releases/USER_ACCEPTANCE.md`.
- Defined invitation, registration, authentication, and Portal journeys.
- Defined media discovery, search, request, status, favorites, protection,
  playback, and sign-out journeys.
- Defined administrator invitation, user, request, media, health, module, and
  routine-operation journeys.
- Added accessibility and responsive-experience validation.
- Added performance, failure, and recovery validation.
- Defined acceptance defect severity and recording requirements.
- Added certification summary and approval records.
- Linked User Acceptance from the Release Documentation index.

### Validation

- Required-heading validation.
- Duplicate-section validation.
- End-user journey validation.
- Administrator journey validation.
- Local Markdown-link validation.
- `git diff --check`.

---

# 2026-08-02

## M-022.1.5 — Atlas Release Template

### Objective

Create the reusable release-record template used to document and certify
future Atlas releases consistently.

### Completed

- Added `docs/releases/RELEASE_TEMPLATE.md`.
- Added release identification and scope fields.
- Added feature, improvement, bug-fix, and breaking-change records.
- Added known-limitation and upgrade guidance.
- Added validation, compatibility, and release-metric records.
- Added rollback guidance and approval fields.
- Added permanent references and completion requirements.
- Linked the template from the Release Documentation index.

### Validation

- Required-heading validation.
- Duplicate-section validation.
- Local Markdown-link validation.
- `git diff --check`.

---

# 2026-08-02

## M-022.1.6 — Atlas Release Notes Template

### Objective

Create the permanent user-facing release-notes template used to communicate
Atlas releases clearly and consistently.

### Completed

- Added `docs/releases/RELEASE_NOTES_TEMPLATE.md`.
- Added release overview and highlight sections.
- Added feature, improvement, and bug-fix records.
- Added breaking-change and upgrade guidance.
- Added known-issue and deprecation records.
- Added acknowledgement and support sections.
- Added supporting references and completion requirements.
- Linked the template from the Release Documentation index.

### Validation

- Required-heading validation.
- Duplicate-section validation.
- Local Markdown-link validation.
- `git diff --check`.

---

# 2026-08-02

## M-023.1.1 — Media Request Domain Model

### Objective

Establish the immutable, normalized request contract that will support Atlas
media requests, provider integration, lifecycle reconciliation, Portal APIs,
and user-aware notifications.

### Completed

- Added `atlas/media_requests/models.py`.
- Added `MediaRequestType`.
- Added `MediaRequestStatus`.
- Added immutable `MediaRequest`.
- Added normalized request, user, provider, and media identities.
- Added title, year, and season validation.
- Added UTC timestamp normalization.
- Added lifecycle consistency checks.
- Added `terminal` and `active` properties.
- Added deterministic `to_dict()` serialization.
- Added package exports through `atlas/media_requests/__init__.py`.
- Added dedicated contract tests.

### Boundaries

This sprint intentionally did not add:

- request persistence;
- Jellyseerr integration;
- request services;
- event publication;
- notification delivery;
- API routes;
- Portal functionality;
- Discord preferences.

### Validation

- 85 focused tests passed.
- Package compilation passed.
- `git diff --check` passed.

---

# 2026-08-02

## M-023.1.2 — Media Request Repository

### Objective

Establish the durable persistence boundary for Atlas media requests without
introducing provider, lifecycle, event, notification, API, or Portal behavior.

### Completed

- Added `atlas/media_requests/repository.py`.
- Added `JsonMediaRequestRepository`.
- Added `MediaRequestRepositoryError`.
- Added schema-versioned JSON persistence.
- Reused the shared `atlas.atomic.write_json_atomic` helper.
- Added repository initialization.
- Added request creation through `save()`.
- Added request retrieval through `get()`.
- Added deterministic chronological listing.
- Added per-user request listing.
- Added provider-request lookup.
- Added request deletion.
- Added duplicate request-ID protection.
- Added duplicate provider-request protection.
- Added domain-model reconstruction on reads.
- Added registry-key and record-identity consistency validation.
- Added derived-field consistency validation.
- Added corruption-safe error handling.
- Added deterministic registry key ordering.
- Exported repository contracts through `atlas/media_requests/__init__.py`.
- Added dedicated repository contract tests.

### Boundaries

This sprint intentionally did not add:

- Jellyseerr integration;
- sports request integration;
- request lifecycle services;
- request status reconciliation;
- event publication;
- Discord delivery;
- user notification preferences;
- API routes;
- Portal functionality.

### Validation

- 130 combined media-request model and repository tests passed.
- Package compilation passed.
- `git diff --check` passed.

---

# 2026-08-02

## M-023.1.3 — Media Request Provider Contract

### Objective

Establish the provider-independent boundary that future Jellyseerr, sports, and
other request providers must implement.

### Completed

- Added `atlas/media_requests/provider.py`.
- Added abstract `MediaRequestProvider`.
- Added `MediaRequestProviderError`.
- Added `MediaRequestProviderOperationError`.
- Added normalized `ProviderCapabilities`.
- Added normalized `ProviderEventContext`.
- Added normalized `ProviderSubmissionResult`.
- Added normalized `ProviderStatusResult`.
- Added normalized `ProviderHealth`.
- Added `ProviderHealthStatus`.
- Added media-type capability discovery.
- Added normalized provider and provider-request identities.
- Added UTC timestamp normalization.
- Added lifecycle consistency validation.
- Added available and failed result requirements.
- Added deterministic serialization.
- Added immutable provider contract models.
- Exported provider contracts through `atlas/media_requests/__init__.py`.
- Added dedicated provider contract tests.

### Architectural Boundary

The provider event context contains provider-neutral lifecycle metadata only.

It does not:

- publish Atlas events;
- contain Discord-specific configuration;
- mutate request persistence;
- call provider APIs;
- expose Portal routes.

### Boundaries

This sprint intentionally did not add:

- Jellyseerr API calls;
- sports provider implementation;
- HTTP transport;
- repository mutation;
- request lifecycle services;
- event publication;
- Discord notification delivery;
- API routes;
- Portal functionality.

### Validation

- 178 combined media-request tests passed.
- Package compilation passed.
- `git diff --check` passed.

---

# 2026-08-02

## M-023.1.4B — Media Request Service

### Objective

Establish the provider-agnostic orchestration layer coordinating Atlas media
request models, durable persistence, and provider contracts.

### Completed

- Added `atlas/media_requests/service.py`.
- Added `MediaRequestService`.
- Added `MediaRequestServiceError`.
- Added deterministic provider registration.
- Added duplicate provider-name protection.
- Added request creation and persistence.
- Added provider capability validation.
- Added media-type support validation.
- Added provider request submission.
- Added provider status synchronization.
- Added provider-side cancellation.
- Added immutable lifecycle updates through repository `replace()`.
- Added provider-name consistency validation.
- Added provider-request identity consistency validation.
- Added lifecycle transition enforcement.
- Added duplicate-submission protection.
- Added repository and provider error translation.
- Added request retrieval and deterministic listing.
- Added per-user request listing.
- Added provider-request lookup.
- Exported service contracts through `atlas/media_requests/__init__.py`.
- Added dedicated mocked service contract tests.

### Architectural Boundary

The service coordinates only the existing request domain, repository, and
provider contracts.

It does not contain provider-specific implementation or delivery behavior.

### Boundaries

This sprint intentionally did not add:

- Jellyseerr HTTP integration;
- sports provider implementation;
- event publication;
- Discord notification delivery;
- user notification preferences;
- REST or Portal API routes;
- Portal functionality.

### Validation

- 227 combined media-request tests passed.
- Package compilation passed.
- `git diff --check` passed.

---

# 2026-08-02

## M-023.1.5A — Media Request HTTP Foundation

### Objective

Establish the reusable authenticated HTTP and JSON transport foundation for
concrete Atlas media-request providers.

### Completed

- Added `atlas/media_requests/providers/`.
- Added `atlas/media_requests/providers/base.py`.
- Added `BaseMediaRequestHTTPProvider`.
- Added `MediaRequestHTTPError`.
- Added normalized HTTP and HTTPS base URL validation.
- Added protection against embedded URL credentials.
- Added protection against absolute provider-path host replacement.
- Added API-key validation with secret-safe object representation.
- Added configurable positive request timeout validation.
- Added normalized provider user-agent handling.
- Added authenticated `X-Api-Key` headers.
- Added JSON `Accept` and `Content-Type` headers.
- Added authenticated JSON `GET` requests.
- Added authenticated JSON `POST` requests.
- Added authenticated JSON `DELETE` requests.
- Added deterministic UTF-8 JSON request encoding.
- Added empty-response handling.
- Added HTTP status error translation.
- Added timeout and connection error translation.
- Added operating-system error translation.
- Added invalid UTF-8 response detection.
- Added invalid JSON response detection.
- Ensured normalized exceptions do not expose API keys.
- Added provider-package exports.
- Added top-level media-request package exports.
- Added dedicated mocked HTTP transport tests.

### Architectural Boundary

This foundation implements transport behavior only.

It does not interpret Jellyseerr resources or implement request-domain
submission, lifecycle, cancellation, or health mapping.

### Boundaries

This sprint intentionally did not add:

- Jellyseerr payload mapping;
- Jellyseerr request submission;
- Jellyseerr status synchronization;
- Jellyseerr cancellation behavior;
- Jellyseerr health mapping;
- live network tests;
- repository mutation;
- event publication;
- Discord notification delivery;
- API routes;
- Portal functionality.

### Validation

- 286 combined media-request tests passed.
- Package compilation passed.
- `git diff --check` passed.

---

# 2026-08-03

## M-023.1.5B — Jellyseerr Provider Adapter

### Objective

Implement the first concrete Atlas Media Request provider using the reusable
HTTP foundation and the provider-neutral request contract.

### Completed

- Added `atlas/media_requests/providers/jellyseerr.py`.
- Added `JellyseerrMediaRequestProvider`.
- Added `default_jellyseerr_media_request_provider()`.
- Added Jellyseerr provider capability declaration.
- Added movie request payload mapping.
- Added TV request payload mapping.
- Added anime movie request mapping.
- Added anime TV request mapping.
- Added specific-season request support.
- Added all-season request support.
- Added numeric TMDB identity validation.
- Added Jellyseerr request submission.
- Added provider request-ID extraction.
- Added request creation and update timestamp normalization.
- Added Jellyseerr request-status normalization.
- Added Jellyseerr media-availability normalization.
- Added request-status synchronization.
- Added availability timestamp mapping.
- Added provider request-ID consistency validation.
- Added request cancellation through the documented delete endpoint.
- Added normalized provider health reporting.
- Added environment-based provider construction.
- Added explicit `ATLAS_JELLYSEERR_URL` support.
- Added fallback URL construction from `LXC_IP` and `JELLYSEERR_PORT`.
- Reused `ATLAS_JELLYSEERR_API_KEY`.
- Added provider-neutral event context.
- Added provider-package exports.
- Added top-level media-request package exports.
- Added dedicated mocked Jellyseerr adapter tests.
- Preserved immutable provider configuration.
- Corrected tests to mock class-level transport methods rather than frozen
  provider instances.

### Status Mapping

Jellyseerr request and media states are normalized into Atlas lifecycle states:

- pending;
- approved;
- searching;
- importing;
- available;
- rejected;
- failed;
- cancelled.

### Architectural Boundary

The adapter translates only between Jellyseerr API resources and Atlas
provider contracts.

It does not:

- mutate the request repository directly;
- publish Atlas events;
- deliver Discord notifications;
- expose REST routes;
- implement Portal behavior.

### Boundaries

This sprint intentionally did not add:

- live request creation against the production Jellyseerr instance;
- live cancellation;
- scheduled request reconciliation;
- event publication;
- Discord notification delivery;
- user notification preferences;
- API routes;
- Portal functionality.

### Validation

- 45 focused Jellyseerr provider tests passed.
- 331 combined media-request tests passed.
- Package compilation passed.
- `git diff --check` passed.

---

# 2026-08-03

## M-023.1.6 — Request Event Publication

### Objective

Establish the provider-neutral Media Request lifecycle event contract and
publish successful request state changes through the existing Atlas event
publisher boundary.

### Completed

- Added `atlas/media_requests/events.py`.
- Added `MediaRequestEvent`.
- Added `MediaRequestEventType`.
- Added `MediaRequestEventError`.
- Added deterministic event-name mapping from request lifecycle states.
- Added immutable event contracts.
- Added request, user, provider, provider-request, and provider-media identity.
- Added media type, title, year, and season context.
- Added lifecycle status and terminal-state serialization.
- Added normalized UTC occurrence timestamps.
- Added availability timestamp validation.
- Added provider-neutral `ProviderEventContext` support.
- Added deterministic metadata serialization.
- Added complete `to_payload()` serialization.
- Added complete `to_dict()` serialization.
- Added `MediaRequestEvent.from_request()`.
- Added optional event publisher injection to `MediaRequestService`.
- Added injectable clock support for deterministic event timestamps.
- Added `request.created` publication after successful persistence.
- Added `request.submitted` publication after successful provider submission.
- Added lifecycle event publication after successful submission.
- Added lifecycle event publication after status changes.
- Prevented duplicate lifecycle publication when status is unchanged.
- Added `request.cancelled` publication after successful cancellation.
- Ensured failed repository or provider operations publish no event.
- Added best-effort publication semantics.
- Ensured event publication failure does not roll back committed request state.
- Added captured publication failure observability.
- Added `publication_errors`.
- Added `clear_publication_errors()`.
- Added package exports.
- Added dedicated event-model contract tests.
- Added dedicated service-publication tests.

### Event Names

- `request.created`;
- `request.submitted`;
- `request.pending`;
- `request.approved`;
- `request.searching`;
- `request.downloading`;
- `request.importing`;
- `request.available`;
- `request.rejected`;
- `request.failed`;
- `request.cancelled`.

### Architectural Boundary

The request service publishes normalized event names and payloads only.

It does not know about:

- Discord;
- webhook URLs;
- notification formatting;
- notification routing;
- user notification preferences;
- Portal presentation.

### Publication Semantics

Request persistence and provider state changes remain authoritative.

Event publication is best-effort so a temporary event-bus failure does not
invalidate a successfully committed request operation. Publication failures are
captured for observability and recovery.

### Boundaries

This sprint intentionally did not add:

- notification-module subscriptions for request events;
- Discord request formatting;
- user-specific notification preferences;
- persistent event retry queues;
- scheduled lifecycle reconciliation;
- REST or Portal API routes;
- Portal functionality.

### Validation

- 31 focused event and publication tests passed.
- 362 combined media-request tests passed.
- Package compilation passed.
- `git diff --check` passed.

---

# 2026-08-03

## M-023.1.7 — Request Notification Integration

### Objective

Connect the Notifications module to normalized Media Request lifecycle events
without coupling notification delivery to `MediaRequestService`.

### Completed

- Added the Notifications Runtime Bus subscription for `request.*`.
- Added request routing based on normalized `payload.media_type`.
- Routed movie requests to the Movies Discord channel.
- Routed television requests to the TV Discord channel.
- Routed anime movie requests to the Anime Movies Discord channel.
- Routed anime television requests to the Anime TV Discord channel.
- Added safe system-channel fallback for unknown request media types.
- Added explicit notification titles for all request lifecycle events.
- Added lifecycle-specific request descriptions.
- Added normalized request and media context fields.
- Added title, year, media type, status, provider, and request identity fields.
- Added season context when available.
- Added availability timestamps to ready-to-watch notifications.
- Classified active request lifecycle notifications as informational.
- Classified failed, rejected, and cancelled requests as warnings.
- Classified `request.available` as a success notification.
- Emphasized `request.available` as **Ready to Watch**.
- Added request notification integration to module verification.
- Added dedicated formatter, routing, severity, context, and contract tests.
- Updated Notifications module documentation.
- Preserved all existing health, storage, media, and Sports notification behavior.

### Event Routing

| Media request type | Notification route |
| --- | --- |
| `movie` | `movies` |
| `tv` | `tv` |
| `anime_movie` | `anime_movies` |
| `anime_tv` | `anime_tv` |
| Unknown | `system` |

### Architectural Boundary

The Notifications module consumes normalized Runtime Bus events only.

It does not:

- import or invoke `MediaRequestService`;
- mutate Media Request repository state;
- perform Jellyseerr operations;
- own request lifecycle decisions;
- add provider-specific request behavior;
- add user-specific Discord mentions.

User-specific notification preferences and Discord identity remain deferred to
their later dedicated contracts.

### Validation

- 9 focused request-notification tests passed.
- 371 combined Media Request tests passed.
- Atlas Notifications module verification passed.
- Request notification runtime verification passed.
- Python package compilation passed.
- Shell syntax validation passed.
- `git diff --check` passed.

### Result

Atlas can now convert normalized request lifecycle events into appropriately
routed Discord notifications while keeping request processing and notification
delivery fully decoupled.

---

# 2026-08-03

## M-023.2.2B — Ingress Resource Governance and Caddy Health

### Objective

Add evidence-based resource governance and native health monitoring
to the production ingress stack without constraining media playback
or hardware transcoding.

### Completed

- Added a 512 MiB memory ceiling, 1 CPU ceiling, and 256 PID
  ceiling to Caddy.
- Added a 1 GiB memory ceiling, 2 CPU ceiling, and 512 PID
  ceiling to Atlas API.
- Added a 1.5 GiB memory ceiling, 2 CPU ceiling, and 512 PID
  ceiling to Atlas Portal.
- Added a native Caddy Docker health check through the local
  HTTPS API route.
- Added `scripts/verify-ingress.sh`.
- Added permanent validation for:
  - ingress Compose syntax;
  - ingress network availability;
  - container presence and runtime state;
  - Docker health status;
  - memory, CPU, and PID ceilings;
  - Caddy configuration;
  - Portal routing;
  - API routing.

### Applied Runtime Contract

| Service | Memory | CPU | PID limit |
| --- | ---: | ---: | ---: |
| Caddy | 512 MiB | 1 CPU | 256 |
| Atlas API | 1 GiB | 2 CPUs | 512 |
| Atlas Portal | 1.5 GiB | 2 CPUs | 512 |

### Architectural Boundary

These limits apply only to:

- Caddy;
- Atlas API;
- Atlas Portal.

They do not constrain:

- Jellyfin;
- FFmpeg;
- Intel GPU transcoding;
- media playback or streaming;
- Sonarr or Radarr;
- the broader media stack.

### Validation

- All three ingress containers reported running and healthy.
- Caddy health checks repeatedly completed with exit code `0`.
- Permanent ingress verification passed 24 checks with zero failures.
- Portal routing through Caddy passed.
- API routing through Caddy passed.
- Caddy configuration validation passed.
- Docker Compose validation passed.
- Shell syntax validation passed.
- `git diff --check` passed.

### Result

The production ingress deployment now has explicit fault-containment
ceilings, native health monitoring, and a repeatable verification
contract while preserving substantial capacity for future Portal and
API growth.

---

# 2026-08-03

## M-023.3.1B — Operations Domain Contracts

### Objective

Create the canonical, provider-neutral Operations domain that future
collectors, reports, CLI commands, APIs, notifications, and Portal
dashboards can consume without duplicating operational data contracts.

### Completed

- Added the `atlas.operations` package.
- Added `OperationsStatus`.
- Added `OperationsSeverity`.
- Added `OperationsSectionId`.
- Added `OperationFinding`.
- Added `OperationsSection`.
- Added `OperationsSummary`.
- Added `OperationsReport`.
- Added `OperationsModelError`.
- Added `OPERATIONS_SCHEMA_VERSION`.
- Added immutable dataclass contracts.
- Added normalized text and identifier handling.
- Added timezone-aware timestamp normalization to UTC.
- Added hexadecimal Git commit validation.
- Added deterministic metadata serialization.
- Added canonical section ordering.
- Added deterministic attention ordering by:
  - severity;
  - canonical section order;
  - finding identifier.
- Added duplicate section detection.
- Added duplicate finding detection within sections.
- Added global finding-identifier uniqueness enforcement.
- Added qualified attention references containing section and finding identity.
- Added deterministic `to_dict()` and JSON serialization.
- Added public package exports.

### Canonical Section Identities

```text
system
containers
services
storage
ingress
media
requests
notifications
retention
cleanup
ari
sports
forecast
users
backup
scheduler
```

### Architectural Boundary

This milestone defines domain contracts only.

It does not yet:

- collect live platform data;
- modify systemd timers;
- modify the daily health-report pipeline;
- publish Operations events;
- add CLI commands;
- add API routes;
- add Portal dashboards;
- change Notifications behavior.

### Validation

- 57 focused Operations domain tests passed.
- 376 related Health, Media Request, and Service Lifecycle tests passed.
- Package import validation passed.
- Python compilation passed.
- Deterministic ordering demonstrations passed.
- Runtime integrity demonstrations passed.
- `git diff --check` passed.

### Result

Project Atlas now has a stable and deterministic Operations domain that
can serve as the single normalized contract for collectors, reports,
notifications, APIs, CLI output, historical snapshots, and Portal
dashboards.

---

# 2026-08-03

## M-023.3.2 — Operations Collector and Docker Provider Foundation

### Objective

Establish the first read-only Operations collection infrastructure and
normalize live host and Docker data into stable, immutable contracts
without coupling the subsystem to CLI, API, Portal, scheduler, or
notification presentation layers.

### Completed

#### Collector Framework

- Added the `atlas.operations.collectors` package.
- Added the immutable `OperationsCollector` base contract.
- Added canonical section identity validation.
- Added collector timeout validation.
- Added normalized collector exception contracts.
- Added checked output and section-identity enforcement.
- Added deterministic collector metadata serialization.

#### System Collector

- Added `SystemCollector`.
- Added injectable `SystemProvider`.
- Added `HostSystemProvider`.
- Added read-only collection for:
  - hostname;
  - operating system;
  - kernel release;
  - uptime;
  - logical CPU count;
  - CPU model;
  - total, used, and available memory.
- Added graceful source-level degradation to unknown findings.
- Corrected CPU model discovery so numeric `/proc/cpuinfo`
  processor indexes are not treated as model identities.
- Verified the live AMD Ryzen CPU model successfully.

#### Docker Command Adapter

- Added `DockerCommandRunner`.
- Added `DockerCollectorError`.
- Added validated timeout and executor injection.
- Added read-only Docker commands for:
  - version;
  - daemon information;
  - full container inventory;
  - single-container inspection.
- Added `subprocess.run()` execution with:
  - argument-list invocation;
  - no shell execution;
  - explicit timeout;
  - captured text output;
  - normalized missing-binary, timeout, operating-system, non-zero
    exit, empty-output, malformed-JSON, and output-shape errors.
- Added JSON-lines parsing for Docker container inventory output.
- Added guarded container identity validation.

#### Docker Provider

- Added `DockerProvider`.
- Added `DockerRunner`.
- Added `DockerProviderContractError`.
- Added immutable normalized contracts:
  - `DockerEngineSnapshot`;
  - `DockerContainerSummary`;
  - `DockerContainerSnapshot`;
  - `DockerMountSnapshot`;
  - `DockerNetworkSnapshot`;
  - `DockerPortSnapshot`.
- Added Docker Engine and daemon normalization.
- Added deterministic container inventory ordering.
- Added duplicate container identity and name validation.
- Added runtime and health normalization.
- Added restart, OOM, and exit-state normalization.
- Added lifecycle timestamp normalization to UTC.
- Added stale running-container `FinishedAt` normalization.
- Added memory, CPU, PID, and restart-policy contracts.
- Added mount normalization and destination uniqueness.
- Added network identity, address, gateway, and alias normalization.
- Added exposed and published TCP/UDP port normalization.
- Added deterministic topology ordering and serialization.
- Added public package exports.

### Live Environment Validation

- The System collector reported a healthy live system section.
- CPU identity resolved as an AMD Ryzen 7 5700U with Radeon Graphics.
- Docker inventory discovered 21 live containers.
- Atlas API, Caddy, and Portal resource ceilings matched their
  production governance contracts.
- Atlas API topology validation passed.
- Caddy topology validation passed with TCP and UDP publications.
- Jellyfin topology validation passed with media mounts, Atlas
  networking, and published ports.
- All inspected running containers normalized `finished_at` to null.

### Validation

- 56 Docker provider tests passed.
- 37 Docker command-adapter tests passed.
- 100 Operations collector, System collector, and domain tests passed.
- 376 related Health, Media Request, and Service Lifecycle tests passed.
- 569 focused and related tests passed in total.
- Python compilation passed.
- Package import validation passed.
- Live System collection passed.
- Live Docker inventory passed.
- Live ingress resource-governance validation passed.
- Live Docker topology validation passed.
- `git diff --check` passed.

### Architectural Boundary

This milestone does not yet add:

- the final Docker Operations collector;
- Operations service orchestration;
- multi-section report generation;
- CLI commands;
- API routes;
- Portal dashboards;
- daily-report integration;
- scheduler integration;
- Operations event publication or notifications.

### Result

Project Atlas now has a tested, deterministic, and read-only
Operations acquisition foundation. Host and Docker runtime information
can be collected and normalized without exposing subprocess behavior or
Docker-specific payload structures to future Operations collectors,
reports, APIs, or user interfaces.

---

# 2026-08-03

## M-023.5 — Operations Aggregation, Runtime Context, and CLI

### Objective

Complete the first end-to-end Atlas Operations reporting path
and expose it through the public Atlas CLI.

### Completed

- Added the final read-only Docker Operations collector.
- Added Docker Engine, inventory, runtime, health, restart, OOM,
  exit-state, and resource-governance findings.
- Added deterministic `OperationsService` aggregation.
- Added canonical collector ordering and collector failure isolation.
- Added immutable Operations runtime-context contracts.
- Added automatic hostname, version, Git commit, and UTC discovery.
- Added detailed human and deterministic JSON renderers.
- Added report-ID overrides and normalized CLI errors.
- Added `scripts/commands/operations.sh`.
- Registered Operations in `scripts/atlas` and centralized help.

### Public interface

```bash
atlas operations
atlas operations help
atlas operations report
atlas operations report --json
atlas operations report --report-id nightly-operations
```

### Live validation

- Healthy overall status
- Score 100 out of 100
- Two sections
- Six System findings
- Eight Containers findings
- Fourteen total findings
- Zero attention findings
- All 21 Docker containers running
- All three governed Atlas containers matching policy

### Verification

- 21 focused Operations CLI tests passed.
- 9 shell integration tests passed.
- 307 complete Operations tests passed.
- 376 related regression tests passed.
- Python compilation passed.
- Shell syntax passed.
- Human and JSON live validation passed.
- `git diff --check` passed.

### Boundary

Persistence, historical comparison, scheduling, APIs, events,
notifications, Portal dashboards, and automatic remediation
remain future work.

### Result

Project Atlas now has a complete, deterministic, tested, and public
Operations reporting path backed by stable human and JSON contracts.

---

# 2026-08-03

## M-023.6A — Immutable Operations Report Persistence

### Objective

Add durable, immutable persistence beneath the existing Atlas Operations
reporting contract without changing live report behavior.

### Completed

- Added `OperationFinding.from_dict()`.
- Added `OperationsSection.from_dict()`.
- Added `OperationsReport.from_dict()` with schema-version validation.
- Added canonical-input reconstruction and derived-field recomputation.
- Added `OperationsRepository`.
- Added `FileOperationsRepository`.
- Added immutable timestamped history snapshots.
- Added deterministic atomic JSON writes.
- Added atomic `latest.json` updates.
- Added duplicate-snapshot rejection.
- Added newest-first history loading with validated limits.
- Added repository-specific missing, corruption, and contract errors.
- Added public repository exports.
- Added `atlas operations save`.
- Added `atlas operations latest`.
- Added Python and shell CLI integration.

### Public interface

```bash
atlas operations report
atlas operations report --json
atlas operations save
atlas operations save --json
atlas operations save --report-id nightly-operations
atlas operations latest
atlas operations latest --json
```

### Storage layout

```text
/mnt/storage/configs/atlas/operations/
├── latest.json
└── history/
    └── <generated-at>.json
```

### Verification

- 78 Operations model tests passed.
- 28 Operations repository tests passed.
- 29 Operations Python CLI tests passed.
- 15 Operations shell integration tests passed.
- 370 complete Operations tests passed.
- Python compilation passed.
- Shell syntax validation passed.
- Diff hygiene passed.
- Live `save` and `latest` commands passed.
- Live persisted report status was healthy with score 100.
- Historical snapshot and `latest.json` matched the rendered JSON contract.

### Boundary

History listing, report comparison, scheduled collection, APIs,
notifications, Portal visualization, and automatic remediation remain
future work.

### Result

Atlas Operations now preserves validated, immutable operational snapshots
while keeping live collection and persisted retrieval as explicit, separate
commands.

---

# 2026-08-03

## M-023.6B — Operations History Inspection

### Objective

Expose persisted Operations reports through a deterministic, read-only
history interface without modifying immutable snapshots or `latest.json`.

### Completed

- Added the `history` Python CLI command.
- Added configurable `--limit` handling with a default of 25 reports.
- Added concise newest-first human history rendering.
- Added stable wrapped JSON history output.
- Preserved complete validated `OperationsReport` contracts in JSON.
- Added normalized history repository failure reporting.
- Added public shell forwarding and centralized help.
- Added parser, renderer, limit, empty-history, failure, and shell tests.

### Public interface

```bash
atlas operations history
atlas operations history --json
atlas operations history --limit 10
atlas operations history --limit 10 --json
```

### JSON contract

History JSON contains:

- `count` — the number of returned reports;
- `reports` — complete validated Operations report contracts.

Reports are returned in deterministic newest-first order.

### Live validation

- Loaded the existing production Operations snapshot.
- Rendered healthy human history with score 100.
- Validated the wrapped JSON contract.
- Validated newest-first timestamp ordering.
- Validated `--limit 1` against the complete history result.
- Confirmed history commands did not modify `latest.json`.
- Confirmed history commands did not change the snapshot count.

### Verification

- 38 Operations Python CLI tests passed.
- 18 Operations shell integration tests passed.
- 106 Operations persistence and model tests passed.
- 382 complete Operations integration tests passed.
- Python compilation passed.
- Shell syntax validation passed.
- Diff hygiene passed.

### Boundary

Report comparison, scheduled collection, APIs, notifications, Portal
visualization, and automatic remediation remain future work.

### Result

Atlas administrators can now inspect immutable operational history through
stable human and JSON interfaces without affecting persisted state.

---

# 2026-08-03

## M-023.7 — Operations Report Comparison

### Objective

Add deterministic, read-only comparison between the two newest persisted
Atlas Operations reports.

### Completed

- Added `OperationsChangeType`.
- Added immutable `OperationsFindingChange` contracts.
- Added immutable `OperationsComparison` contracts.
- Added canonical validation and deterministic change ordering.
- Added derived status, score, attention, and change summaries.
- Added validated comparison serialization and reconstruction.
- Added the pure `OperationsComparisonService`.
- Added detection for added, removed, changed, and unchanged findings.
- Added section-move handling as removal plus addition.
- Added concise human comparison rendering.
- Added deterministic JSON comparison rendering.
- Added `atlas operations compare`.
- Added `atlas operations compare --json`.
- Added `atlas operations compare --include-unchanged`.
- Added Python CLI and public shell integration.

### Public interface

```bash
atlas operations compare
atlas operations compare --json
atlas operations compare --include-unchanged
```

### Comparison behavior

The repository returns the two newest validated reports. The newest report
is treated as current and the second-newest report is treated as previous.

Comparison remains strictly read-only. It does not:

- collect a new report;
- modify either source report;
- write a history snapshot;
- update `latest.json`.

### Live validation

- Created a second immutable production Operations snapshot.
- Compared two persisted healthy reports with scores of 100.
- Detected two genuine runtime changes.
- Detected memory usage changing from 9.36% to 9.33%.
- Detected system uptime changing between snapshots.
- Confirmed an overall score delta of zero.
- Confirmed two changed findings and no added or removed findings.
- Validated the four-field JSON comparison contract.
- Validated all derived comparison summary counts.
- Validated `--include-unchanged` with 14 total findings.
- Confirmed 12 unchanged findings.
- Confirmed comparison did not modify `latest.json`.
- Confirmed comparison did not change the snapshot count.

### Verification

- 23 comparison model tests passed.
- 8 comparison service tests passed.
- 7 comparison renderer tests passed.
- 45 Operations Python CLI tests passed.
- 21 Operations shell integration tests passed.
- 106 Operations persistence and model tests passed.
- 430 complete Operations integration tests passed.
- Python compilation passed.
- Shell syntax validation passed.
- Diff hygiene passed.

### Boundary

Scheduled collection, API routes, notifications, Portal visualization,
comparison retention, and automatic remediation remain future work.

### Result

Atlas administrators can now determine exactly what changed between the
two newest immutable Operations snapshots through stable human and JSON
interfaces.

---

# 2026-08-04

## M-023.8 — Shared Scheduled Operations Collection

### Objective

Integrate Atlas Operations with the shared scheduler without introducing
a parallel scheduling implementation.

### Completed

- Added the scheduled Operations collection callback.
- Added the structural Operations collection-service protocol.
- Added normalized callback success and failure output.
- Added configurable repository-root support through
  `ATLAS_OPERATIONS_DIRECTORY`.
- Added the canonical `operations.collect` task.
- Added the default hourly collection interval.
- Added core Operations registration through `TaskScheduler.register()`.
- Integrated core jobs into unqualified `atlas scheduler sync`.
- Preserved targeted module-only synchronization behavior.
- Preserved scheduler runtime state across repeated synchronization.
- Removed optional-module event routing from the core Operations task.
- Added isolated subprocess execution through the production scheduler.
- Added scheduler registration, callback, sync, and execution tests.

### Canonical task

```text
Name:        operations.collect
Interval:    3600 seconds
Callback:    python3 -m atlas.operations_scheduled_collection
Description: Persist an Atlas Operations report
Module:      none
```

### Public interface

```bash
atlas scheduler sync
atlas scheduler inspect operations.collect
atlas scheduler run operations.collect
atlas scheduler history --limit 10
```

### Runtime behavior

An unqualified scheduler synchronization registers core jobs together with
jobs from enabled module manifests. A targeted module synchronization
continues to affect only the requested module.

The scheduled callback executes one direct Operations collection and saves
the resulting report through `FileOperationsRepository`. Successful runs
create an immutable history snapshot, update `latest.json`, and record
scheduler health, counters, duration, timestamps, and execution history.

Operations is a core subsystem rather than an optional module. The task
therefore stores `module: null` and does not use optional-module event
routing.

### Live validation

- Registered `operations.collect` through live scheduler synchronization.
- Verified the hourly callback, description, enabled state, and core-task
  identity.
- Executed the task through the production scheduler.
- Created a third immutable production Operations snapshot.
- Confirmed the new snapshot matched `latest.json`.
- Confirmed a healthy report with score 100.
- Confirmed scheduler status, counters, success time, and duration.
- Confirmed scheduler execution history recorded the successful run.
- Preserved the original event-delivery error as immutable execution
  evidence.
- Resynchronized the corrected task while preserving runtime metadata.
- Confirmed Operations history and comparison continued to function.

### Automated verification

- 9 scheduled-collection callback tests passed.
- 13 Operations scheduler registration tests passed.
- 4 Operations scheduler execution tests passed.
- 33 scheduler regression tests passed.
- 65 Operations persistence regression tests passed.
- Real subprocess collection into an isolated repository passed.
- Python compilation passed.
- Shell syntax validation passed.
- Markdown validation passed.
- Diff hygiene passed.

### Boundary

Operations API routes, notifications, Portal visualization, comparison
retention, and automatic remediation remain future work.

### Result

Atlas Operations now performs automatic immutable report collection through
the shared scheduler while preserving one scheduler architecture, one
Operations persistence contract, deterministic execution, and complete
runtime observability.

---

# 2026-08-04

## M-023.9B — Shared API Contract and FastAPI Adapter Foundation

### Objective

Establish one deterministic, versioned, framework-neutral API contract layer
that can be consumed by the existing FastAPI application without duplicating
Atlas domain behavior or breaking established endpoint response contracts.

### Architecture

```text
FastAPI route and Pydantic schema
              |
              v
      FastAPI envelope adapter
              |
              v
Transport-neutral atlas.api contract
              |
              v
   Atlas application/domain service
```

The dependency direction remains one-way:

- `atlas.api` owns transport-neutral contracts and serialization;
- `apps/api` owns FastAPI, Pydantic, HTTP, and OpenAPI adaptation;
- Atlas domain and application services remain independent of FastAPI;
- framework-specific schemas are never inserted back into shared contracts.

### Completed

- Added canonical API and schema version constants.
- Added the stable Project Atlas vendor media type.
- Added immutable normalized `ApiError` contracts.
- Added immutable success and failure response envelopes.
- Added deterministic response reconstruction.
- Added timezone-aware UTC timestamp normalization.
- Added deterministic JSON-compatible serialization.
- Added support for mappings, sequences, enums, dataclasses, aware
  datetimes, and Atlas contracts exposing `to_dict()`.
- Added explicit rejection of unsupported and framework-specific values.
- Added centralized and explicit `atlas.api` public exports.
- Added cross-contract serialization validation using Operations reports,
  history collections, and comparisons.
- Added Pydantic/OpenAPI success and failure envelope schemas.
- Added FastAPI success and failure envelope-construction helpers.
- Preserved existing health, authentication, dashboard, dashboard-media,
  and media-library response bodies.
- Defined envelope adoption as opt-in for new routes.
- Documented shared-contract ownership, dependency direction, maturity,
  compatibility, and Operations integration boundaries.

### Public contract

```python
from atlas.api import (
    API_MEDIA_TYPE,
    API_SCHEMA_VERSION,
    API_VERSION,
    ApiContractError,
    ApiError,
    ApiFailureResponse,
    ApiSerializationError,
    ApiSuccessResponse,
    to_api_json,
    to_api_value,
)
```

### Compatibility boundary

Existing API consumers continue to receive the established unwrapped response
bodies from current routes.

The shared envelopes are initially opt-in. Existing routes may migrate only
through a deliberate, test-backed compatibility plan.

Operations HTTP routes are planned as the first new consumers of the shared
envelope contracts, but those routes are not part of this milestone.

### Validation

- 81 shared API foundation tests passed.
- 10 FastAPI envelope-schema tests passed.
- 10 FastAPI envelope-helper tests passed.
- 26 existing FastAPI endpoint regression tests passed.
- 109 Operations model and comparison regression tests passed.
- Shared API and Operations cross-contract integration passed.
- Existing endpoint response compatibility passed.
- Python compilation passed.
- Markdown fence validation passed.
- Git diff hygiene passed.

### Boundary

This milestone does not add:

- Operations HTTP routes;
- global FastAPI exception handlers;
- automatic migration of existing endpoint response bodies;
- Portal Operations visualization;
- notification delivery;
- automatic remediation.

### Result

Project Atlas now has one versioned, deterministic API contract and
serialization foundation that remains independent of FastAPI while integrating
cleanly with the existing HTTP application through opt-in Pydantic and OpenAPI
adapters.

The next implementation phase can expose Operations reports, history, and
comparisons through thin FastAPI routes without redefining domain contracts or
serialization behavior.

---

# 2026-08-04

## M-023.10 — Operations Report API (Slice 1)

### Objective

Expose the existing Operations reporting subsystem through the Atlas HTTP
API without duplicating business logic or introducing HTTP-specific
behavior into the Operations domain.

### Completed

- Added the first Operations API route.
- Reused the production OperationsService.
- Added dependency injection for OperationsService.
- Added permission-gated endpoint wiring.
- Added shared API envelope integration.
- Registered the route under `/api/v1`.
- Added OpenAPI registration.
- Added endpoint regression tests.
- Validated live production execution.
- Confirmed read-only behavior.

### Live validation

- Endpoint returned a healthy Operations report.
- Overall score: 100.
- Two report sections returned.
- Unauthorized requests correctly returned HTTP 401.
- Route appeared in generated OpenAPI.
- No Operations snapshots were created.
- `latest.json` remained unchanged.
- History directory remained unchanged.

### Result

Atlas now exposes a production-quality read-only Operations report
endpoint using the shared transport-neutral API contracts established
during M-023.9B.

---

# 2026-08-04

## M-023.10 — Operations Latest API (Slice 2)

### Objective

Expose the latest persisted Operations report through the Atlas HTTP API while
reusing the existing repository implementation and shared API contracts.

### Completed

- Added the persisted Operations report endpoint.
- Reused the production Operations repository.
- Added repository dependency injection.
- Added shared 404 failure envelopes.
- Added OpenAPI success and failure schemas.
- Added endpoint regression tests.
- Validated production latest-report retrieval.
- Confirmed read-only repository behavior.

### Live validation

- Latest persisted report returned successfully.
- Overall score: 100.
- Shared success envelope returned.
- Missing reports returned HTTP 404 with the shared failure contract.
- OpenAPI documented both response types.
- No repository mutations occurred.

### Result

Atlas now exposes both live and persisted Operations reporting through
consistent transport-neutral API contracts without duplicating business logic.

---

# 2026-08-04

## M-023.10 — Operations History API (Slice 3)

### Objective

Expose persisted Atlas Operations report history through the HTTP API while
preserving repository ordering, bounded retrieval, shared response contracts,
and read-only behavior.

### Completed

- Added `GET /api/v1/operations/history`.
- Reused the configured Operations repository dependency.
- Reused the `system.health.read` permission.
- Added a default history limit of 25.
- Added an HTTP maximum history limit of 100.
- Added FastAPI validation for non-integer and out-of-range limits.
- Preserved deterministic newest-first repository ordering.
- Returned the established `count` and `reports` history contract.
- Returned empty history as a successful empty collection.
- Added OpenAPI query-parameter documentation.
- Added focused route, validation, ordering, immutability, and OpenAPI tests.
- Validated the endpoint against the production Operations history.

### Live validation

- Three persisted Operations reports were returned.
- The newest report was generated at
  `2026-08-04T00:15:52.438537Z`.
- `limit=2` returned exactly two reports.
- Limits below 1 returned HTTP 422.
- Limits above 100 returned HTTP 422.
- Non-integer limits returned HTTP 422.
- OpenAPI documented the default, minimum, and maximum limit values.
- `latest.json` remained unchanged.
- Operations history remained unchanged.

### Result

Atlas now exposes deterministic, bounded, newest-first Operations history
through the shared API envelope without collecting, persisting, comparing,
or mutating reports.

---

# 2026-08-04

## M-023.10 — Operations Comparison API (Slice 4)

### Objective

Expose deterministic comparison of the two newest persisted Atlas Operations
reports through the HTTP API while reusing the existing repository,
comparison service, shared response contracts, and read-only architecture.

### Completed

- Added `GET /api/v1/operations/compare`.
- Reused the configured Operations repository dependency.
- Added a cached OperationsComparisonService dependency.
- Reused the `system.health.read` permission.
- Loaded exactly the two newest persisted Operations reports.
- Preserved previous and current report ordering.
- Added the optional `include_unchanged` Boolean query parameter.
- Reused the immutable OperationsComparison domain contract.
- Added a shared HTTP 409 failure envelope when fewer than two reports exist.
- Added OpenAPI success, conflict, and query-parameter documentation.
- Added focused comparison, dependency, validation, immutability, failure,
  serialization, and OpenAPI tests.
- Validated the endpoint against production Operations history.

### Live validation

- Compared the two newest production Operations reports.
- Previous report:
  `2026-08-03T23:38:17.879647Z`.
- Current report:
  `2026-08-04T00:15:52.438537Z`.
- Two operational differences were detected.
- `include_unchanged=true` returned the expanded comparison contract.
- An empty repository returned HTTP 409 using the shared failure envelope.
- OpenAPI documented the Boolean query parameter and both response schemas.
- `latest.json` remained unchanged.
- Operations history remained unchanged.

### Result

Atlas now exposes the complete read-only Operations reporting lifecycle through
the HTTP API: live collection, latest persisted retrieval, bounded history,
and deterministic comparison.

---

# 2026-08-04

## M-023.11 — Aggregate Operations Portal Dashboard API (Slice 1)

### Objective

Provide one stable, read-only Portal endpoint that composes existing Atlas
health, operational dashboard, media dashboard, and persisted Operations
contracts without duplicating business logic or making internal HTTP calls.

### Completed

- Added immutable aggregate Portal dashboard schemas.
- Added validated available and unavailable Operations section states.
- Added `PortalDashboardService`.
- Reused `DashboardSummaryService`.
- Reused `DashboardMediaSummaryService`.
- Reused the configured Operations repository.
- Normalized missing Operations state into an unavailable section.
- Preserved existing media unavailable-state normalization.
- Added cached dashboard, media, and aggregate Portal dependencies.
- Added the dedicated `/portal` API router.
- Added `GET /api/v1/portal/dashboard`.
- Required `atlas.dashboard.read`, `media.read`, and
  `system.health.read`.
- Returned the aggregate through the shared Atlas API success envelope.
- Registered the endpoint in OpenAPI.
- Preserved all existing dashboard, media, and Operations endpoints.
- Added dedicated schema, service, route, authorization, dependency,
  serialization, and OpenAPI tests.
- Exported public permission dependencies for deterministic testing.
- Added `DashboardMediaSummaryService` to the service package exports.

### Aggregate contract

The initial aggregate contains:

- API health identity;
- the existing operational dashboard summary;
- the existing media dashboard summary;
- the latest persisted Operations report when available;
- a normalized unavailable Operations section when no report exists.

The endpoint does not:

- collect a new Operations report;
- persist data;
- query Operations history;
- perform report comparison;
- call Atlas HTTP endpoints internally;
- duplicate dashboard or Operations business logic.

### Live validation

- The aggregate endpoint returned HTTP 200 using production-backed services.
- Operational dashboard metrics were returned.
- Media library state was returned through the existing ARI adapter.
- Persisted Operations state was returned when available.
- OpenAPI registered the Portal route and shared response envelope.
- Missing ARI state remained a successful unavailable media section.
- Missing Operations state remained a successful unavailable section.
- ARI data was unchanged.
- `latest.json` was unchanged.
- Operations history was unchanged.

### Result

Atlas now provides a single-request backend contract for the initial
Operations Portal landing page while preserving modular service boundaries,
partial availability, explicit authorization, and read-only behavior.

---

# 2026-08-04

## M-023.11 — Operations Portal Widget Enrichment (Slice 2)

### Objective

Enrich the aggregate Operations Portal dashboard contract with compact,
Portal-ready latest-report, comparison, and attention data while preserving
the complete persisted report for drill-down access.

### Completed

- Added a compact latest Operations report summary.
- Added canonical status, score, attention count, and generation timestamp
  fields.
- Added a compact comparison contract for the two newest persisted reports.
- Added score and attention deltas.
- Added added, removed, changed, unchanged, and difference counts.
- Added explicit available and unavailable comparison states.
- Added model validation for contradictory comparison states.
- Added deterministic recent-attention contracts.
- Reused the canonical Operations attention ordering.
- Bounded recent attention to five findings.
- Preserved stable finding identity, section, name, status, severity, message,
  and recommendation fields.
- Retained the complete latest Operations report in the aggregate contract.
- Reused `OperationsRepository.latest()`.
- Reused `OperationsRepository.history(limit=2)`.
- Reused `OperationsComparisonService`.
- Injected the shared cached comparison service through the API dependency
  layer.
- Preserved zero-report and one-report partial-availability behavior.
- Preserved immutable tuple representation inside Python and JSON arrays at
  the transport boundary.
- Added focused schema, service, dependency, route, ordering, limit,
  comparison, serialization, and immutability tests.

### Availability behavior

When no persisted report exists:

- the Operations section is unavailable;
- the report and summary are absent;
- comparison is unavailable;
- recent attention is empty.

When exactly one persisted report exists:

- the latest report and summary are available;
- recent attention is available;
- comparison is unavailable.

When at least two persisted reports exist:

- the latest report and summary are available;
- recent attention is available;
- canonical comparison metrics are available.

### Live validation

- Latest production status: `healthy`.
- Latest production score: `100`.
- Latest production attention count: `0`.
- Recent production attention count: `0`.
- Production comparison status: `available`.
- Two production differences were returned.
- Latest summary values matched the canonical persisted report.
- Comparison values matched `OperationsComparisonService`.
- Recent attention matched canonical ordering.
- The five-item recent-attention bound was enforced.
- One-report comparison normalization passed.
- Empty-repository normalization passed.
- `latest.json` remained unchanged.
- Operations history remained unchanged.

### Result

The aggregate Portal endpoint now exposes compact Operations widgets suitable
for dashboard cards, change indicators, and attention panels without requiring
the frontend to parse full Operations reports or reproduce domain logic.


---

# 2026-08-04

## M-023.11 — Scheduler Portal Widget Enrichment (Slice 3)

### Completed

- Added Portal-ready Scheduler summary widgets.
- Added Scheduler runtime status visibility.
- Added bounded Scheduler failure visibility.
- Added a read-only Scheduler dashboard adapter.
- Integrated Scheduler state into the aggregate Portal dashboard contract.

### Architecture

- Existing TaskScheduler runtime remains the source of truth.
- Portal reads scheduler state without executing jobs.
- No scheduler mutation, synchronization, or persistence occurs from the API read path.
- Scheduler ownership remains isolated from Portal presentation.

### Validation

Completed:

- Scheduler widget schema tests
- Scheduler dashboard service tests
- Portal dashboard schema regressions
- Portal dashboard service regressions
- Portal dashboard route regressions
- Operations regressions
- Compilation checks
- Repository hygiene checks

Result:

`M-023.11 Slice 3C Scheduler widget validation: PASS`


---

# 2026-08-04

## M-023.11 — Operations Portal Dashboard Interface Completion

### Objective

Complete the user-facing Operations Portal dashboard on top of the
aggregate `GET /api/v1/portal/dashboard` contract while preserving API
ownership, frontend domain boundaries, read-only behavior, and existing
dashboard presentation components.

### Completed

- Added the authenticated aggregate Portal dashboard client.
- Switched the protected Portal landing page to the aggregate dashboard
  endpoint.
- Added stable frontend transport contracts for aggregate Operations and
  Scheduler state.
- Added normalized Portal domain models for Operations and Scheduler data.
- Normalized aggregate health, operational, media, Operations, and Scheduler
  state before presentation.
- Reused the existing operational `DashboardSnapshot` model.
- Reused the existing operational `DashboardGrid` presentation.
- Reused the existing media `DashboardMediaSnapshot` model.
- Reused the existing `MediaLibraryGrid` and `MediaLibraryCard`
  presentation.
- Added `PortalHealthCard`.
- Added `PortalOperationalSection`.
- Added `PortalMediaSection`.
- Added `OperationsSummaryCard`.
- Added `OperationsComparisonCard`.
- Added `OperationsAttentionPanel`.
- Added `SchedulerSummaryCard`.
- Added `SchedulerFailuresPanel`.
- Removed all aggregate dashboard placeholder cards.
- Exported the new Portal dashboard components through the feature package
  boundary.

### Architecture

- The Atlas API remains responsible for aggregate dashboard assembly.
- The Portal performs one authenticated request to
  `GET /api/v1/portal/dashboard`.
- The Portal does not make secondary operational or media dashboard
  requests.
- Existing operational and media normalization contracts remain the source
  of truth for those frontend domains.
- Operations and Scheduler transport field names are normalized before
  reaching React components.
- React components remain presentation-only and do not reproduce API domain
  logic.
- Operations comparison ordering, attention ordering, and result bounds
  remain owned by the API.
- Scheduler execution, persistence, and mutation remain outside the Portal
  read path.

### Operations Intelligence

The completed Operations presentation includes:

- current availability and status;
- latest score;
- current attention count;
- report generation time;
- score and attention deltas;
- added, removed, changed, unchanged, and total difference counts;
- unavailable comparison normalization;
- bounded recent attention findings;
- severity, message, and optional recommendation presentation;
- explicit clear and unavailable states.

### Scheduler Intelligence

The completed Scheduler presentation includes:

- registered, enabled, running, due, and failed task counts;
- last and next runtime timestamps;
- explicit available and unavailable states;
- bounded recent Scheduler failures;
- task identity;
- error details;
- optional failure timestamps;
- explicit clear state when no recent failures exist.

### Validation

Completed:

- Portal TypeScript validation
- Portal Vitest regression suite
- Portal ESLint validation
- Portal Prettier validation
- Git diff hygiene validation
- Placeholder-removal validation
- Prettier-equivalence audit for previously committed Portal files
- Focused Operations comparison rendering tests
- Focused Operations attention rendering tests
- Focused Scheduler failure rendering tests

Final Portal test result:

- 14 test files passed
- 122 tests passed

### Result

The Atlas Portal now exposes a complete, authenticated, read-only Operations
dashboard composed from one aggregate API response. Operational health, media
statistics, Operations intelligence, comparison state, attention findings,
Scheduler runtime state, and bounded Scheduler failures are presented through
modular and independently testable frontend components.


---

# 2026-08-04

## M-023.12 — Full-Stack Verification Framework

### Objective

Complete a production-ready root verification framework that validates Atlas
configuration, filesystem readiness, infrastructure, the active Compose
service model, ingress, Scheduler readiness, and enabled optional modules
without duplicating subsystem-owned diagnostic logic.

### Completed

#### M-023.12.1 — Verify and Doctor Framework Boundaries

- Refactored `scripts/commands/verify.sh` into reusable verification sections.
- Added deterministic shell regression coverage for the root Verify command.
- Preserved `scripts/commands/doctor.sh` as a thin delegation boundary to the
  Python health engine.
- Added dedicated Doctor shell tests covering text rendering, exit-status
  propagation, and diagnostic-ownership boundaries.

#### M-023.12.2 — Configuration Contract Verification

- Added required-value validation.
- Added absolute-path validation.
- Added HTTP and HTTPS URL validation.
- Added positive-integer validation.
- Added deterministic parent-and-child path relationship validation.
- Kept configuration validation independent from filesystem creation and
  runtime initialization.

#### M-023.12.3 — Runtime Filesystem Contract

- Added required-directory existence checks.
- Added non-destructive writability probes.
- Verified project, storage, media, downloads, backup, configuration, and
  runtime-configuration foundations.
- Preserved lazy ownership for users, identity, ARI, Scheduler, and other
  subsystem state directories.
- Ensured `atlas verify` creates no runtime directories.

#### M-023.12.4 — Compose-Aware Service Verification

- Replaced the incomplete hardcoded service list.
- Added active root Compose service discovery through
  `docker compose config --services`.
- Added running-service discovery through
  `docker compose ps --status running --services`.
- Added automatic verification for newly introduced active services.
- Added explicit handling for Compose discovery and runtime-query failures.
- Kept optional module Compose stacks outside the root Compose contract.

#### M-023.12.5 — Specialized Verifier Orchestration

- Added `scripts/lib/verifiers.sh`.
- Added shared specialized-command aggregation helpers.
- Delegated ingress verification to `scripts/verify-ingress.sh`.
- Delegated Scheduler readiness to the public Scheduler CLI.
- Used shared module enumeration and enabled-state contracts.
- Delegated enabled-module validation to `atlas module verify <module>`.
- Preserved complete subsystem verifier output.
- Continued later verifier execution after individual failures.
- Added explicit handling for installations with no enabled optional modules.

#### M-023.12.6 — Live Verification

Completed clean live validation of:

- the root Atlas configuration contract;
- the runtime filesystem contract;
- Docker Engine and Docker Compose;
- Intel GPU availability;
- all 15 active root Compose services;
- required media and download paths;
- required project documentation;
- Gluetun and the qBittorrent VPN namespace;
- ingress Compose, containers, health, resource ceilings, and HTTPS routes;
- Scheduler registry readiness;
- the enabled Notifications module;
- the enabled Sports module;
- the Python Doctor health engine.

### Architecture

The final ownership model is:

- `atlas verify` owns orchestration, aggregation, and the final PASS or FAIL
  result.
- `atlas doctor` remains a thin wrapper around the Python health engine.
- the ingress verifier owns ingress-specific operational checks;
- the Scheduler CLI owns Scheduler registry presentation;
- the module framework owns module discovery and enabled-state evaluation;
- each module verifier owns its domain-specific verification logic;
- root Compose discovery owns only the active root service model.

This prevents diagnostic duplication while allowing future services and
modules to participate in verification through stable extension boundaries.

### Validation

Completed:

- shell syntax validation;
- Python test compilation;
- Git diff-hygiene validation;
- 21 focused Verify shell tests;
- 138 focused and related operational regression tests;
- clean live `atlas verify`;
- clean live `atlas doctor`;
- clean live ingress verification;
- clean live Scheduler registry inspection;
- clean enabled-module discovery;
- clean repository-hygiene validation.

Live results:

- `atlas verify`: exit status `0`;
- `atlas doctor`: exit status `0`;
- Doctor overall status: `HEALTHY`;
- Doctor overall score: `100%`;
- ingress verifier: 24 passed, 0 failed;
- Scheduler registry: 2 registered tasks;
- enabled modules: Notifications and Sports;
- root Verify overall status: `PASS`.

### Commits

- `d00cee53` — establish the Verify framework;
- `0137bc2c` — lock the Doctor delegation boundary;
- `424d5a73` — validate the Atlas configuration contract;
- `b591060b` — verify the runtime filesystem contract;
- `aca45714` — discover active Compose services;
- `2c8c2d18` — orchestrate specialized verifiers.

### Result

Atlas now has a modular, deterministic, extensible, and production-validated
full-stack verification framework. The root command verifies platform
foundations and delegates specialized diagnostics to their owning
subsystems, providing one complete operational PASS or FAIL result without
centralizing domain-specific implementation details.

---

# 2026-08-04

## M-023.13 — Startup Policy and VPN Readiness

### Objective

Establish a deterministic, provider-independent, read-only policy boundary for
evaluating whether Atlas-managed dependencies provide explicit startup and
readiness guarantees.

### Completed

- Added `StartupDependencyCondition`, `ServiceStartupDependency`, and
  `ServiceStartupContract` with normalization, child validation, deterministic
  ordering, serialization, package imports, and dedicated tests.
- Added Docker Compose startup-contract inspection behind the Service Lifecycle
  provider boundary.
- Added `StartupPolicySeverity`, `StartupPolicyFinding`, and
  `StartupPolicyReport` with normalized timestamps and deterministic output.
- Added the provider-independent `StartupPolicyEvaluator`.
- Added the read-only `ServiceStartupPolicyService` orchestration boundary.
- Added `atlas service startup-policy` with human and JSON output.
- Remediated qBittorrent startup so it waits for Gluetun health, preserving a
  fail-closed VPN readiness boundary.
- Added Startup Policy architecture documentation and ADR 0011.

### Validation

Validated at commit `5f779ac8`:

- 78 Startup Policy model, evaluator, and service tests passed;
- 46 Compose startup-provider tests passed;
- six Startup Policy CLI tests passed;
- 130 focused tests passed in total;
- public import validation passed;
- Python compilation passed;
- shell syntax validation passed;
- Git diff-hygiene validation passed;
- live human and JSON commands both returned exit status `0`;
- live provider status was `healthy`, with no attention requirement and zero
  findings.

### Commits

- `13b87821` — add startup contract models;
- `f1abd2c8` — inspect Compose startup contracts;
- `664ce4c8` — add Startup Policy result models;
- `9b295db9` — evaluate Startup Policy contracts;
- `a789269b` — add the Startup Policy CLI command;
- `b4f16211` — enforce the qBittorrent VPN readiness contract;
- `5f779ac8` — add Startup Policy architecture and ADR documentation.

### Result

M-023.13 is complete. Atlas now has a tested, documented,
production-validated, read-only Startup Policy capability and an explicit
fail-closed readiness contract between qBittorrent and Gluetun.

---

# 2026-08-05

## M-023.14 — Restart Recovery Implementation

### Objective

Establish a deterministic, provider-independent, read-only capability that
compares normalized observations from before and after a service restart and
reports whether the service recovered safely.

### Completed Implementation

- Added `ServiceRecoveryObservation`, `ServiceRecoveryStatus`, and
  `ServiceRecoveryResult` with identity validation, child-contract validation,
  normalized timestamps, deterministic serialization, public exports, and a
  dedicated model suite.
- Added the pure `RestartRecoveryEvaluator` with conservative normalized
  outcomes: `not-observed`, `recovering`, `recovered`, `degraded`, `failed`, and
  `unknown`.
- Added the read-only `ServiceRestartRecoveryService` observation and evaluation
  boundary.
- Reused the existing Docker Compose `ServiceRuntime` facts rather than creating
  a parallel provider contract.
- Added human and JSON CLI workflows for capturing a before observation and
  evaluating it against current state.
- Preserved the v1.0 non-mutation boundary: Restart Recovery cannot start, stop,
  restart, or recreate services.

### Automated Validation

- 32 recovery-model tests passed.
- 22 evaluator tests passed.
- 10 orchestration-service tests passed.
- 9 focused recovery CLI tests passed.
- 117 combined CLI and recovery regression tests passed.
- Public import boundaries, Python compilation, shell syntax, command help, and
  Git diff hygiene passed throughout the implementation slices.

### Production Read-Only Validation

Validated against Jellyfin at commit `834ebf52` without restarting it:

- before and after runtime state: `running`;
- before and after health: `healthy`;
- restart-count delta: `0`;
- start-time advancement: false;
- normalized result: `not-observed`;
- attention required: false;
- infrastructure mutations: none;
- human and JSON interfaces both returned the intentional conservative exit
  status `1`;
- JSON contract assertions passed.

### Commits

- `6b20947d` — define Restart Recovery architecture and ADR 0012;
- `0ee3f6f6` — add Restart Recovery models;
- `ec334109` — add deterministic recovery evaluation;
- `5a9cdcba` — add read-only recovery orchestration;
- `834ebf52` — add human and JSON recovery CLI reporting.

### Controlled Production Restart

Completed against FlareSolverr at commit `391c755a` after explicit operator
approval. FlareSolverr was selected because it had no declared Compose
dependencies, exposed an explicit health check, and presented lower user impact
than Jellyfin or the VPN boundary.

The guarded validation captured the before observation, restarted only
FlareSolverr through Docker Compose, polled health for up to 90 seconds, evaluated
the normalized result, verified final Atlas health, preserved diagnostics, and
kept the repository unchanged.

Observed evidence:

- health returned to Healthy on poll attempt 3;
- restart-count delta was `0`;
- the normalized start timestamp advanced;
- `restart_observed` was true;
- status was `recovered`;
- pass state was true;
- attention required was false;
- warnings and errors were empty;
- final Atlas service health was Healthy at 100/100;
- repository mutations were none.

### Result

M-023.14 is complete. Atlas now has a documented, tested, provider-independent,
production-validated Restart Recovery capability that observes and explains
recovery without performing infrastructure mutation.


---

# 2026-08-05

## M-023.15 — Service Dependency Verification

### Objective

Harden and production-validate Atlas dependency verification without creating
a parallel provider, graph engine, service, or evaluator.

### Architecture and Boundaries

- Added the Service Dependency Verification architecture document and ADR
  0013.
- Confirmed that the dependency graph owns topology, Service Doctor owns
  current missing and non-running dependency findings, and Startup Policy owns
  startup readiness strength.
- Preserved provider adapters as fact translators and kept all dependency
  verification read-only.

### Contract Hardening

- Moved `ServiceDependencyNode` and `InfrastructureDependencyGraph` into the
  dedicated `dependency_models` module.
- Added collection normalization, service identity and child-contract
  validation, duplicate and self-reference rejection, deterministic unresolved
  identifier normalization, UTC timestamp normalization, and deterministic
  `to_dict()` serialization.
- Exported both models through `atlas.service_lifecycle`.
- Preserved compatibility imports through the existing lifecycle service
  module as true class aliases.
- Added a dedicated 30-test dependency-model suite.

### Focused Validation

- 30 dependency-model tests passed.
- Four graph-service tests passed.
- Two Service Doctor dependency tests passed.
- 22 Startup Policy tests passed.
- Four graph CLI tests passed.
- 57 Docker Compose dependency and startup normalization tests passed.
- Public compatibility identity, Python compilation, shell syntax, and Git
  diff hygiene passed.

### Production Validation

Validated at commit `7552b947` without infrastructure mutation:

- provider: `docker-compose`;
- Compose project: `project-atlas`;
- managed services: 15;
- resolved relationships: eight;
- graph roots: Gluetun, Jellyfin, Radarr, and Sonarr;
- standalone services: seven;
- unresolved dependencies: zero;
- forward and reverse relationships: reciprocal;
- Service Doctor dependency findings: zero;
- Startup Policy status: Healthy;
- Startup Policy findings: zero;
- Startup Policy attention required: false;
- repository remained clean.

Service Doctor's overall Degraded result contained 11 observability warnings
for services without explicit Docker health checks and 14 informational
`latest`-tag findings. It contained no dependency errors and does not block
this milestone.

### Commits

- `9a5c3358` — define Dependency Verification architecture and ADR 0013;
- `7552b947` — harden and publicly export dependency graph models.

### Result

M-023.15 is complete. Atlas now has a stable, deterministic, publicly exported,
and production-validated dependency graph integrated with the existing Service
Doctor and Startup Policy boundaries. No duplicate evaluator or infrastructure
mutation capability was introduced.


---

# 2026-08-05

## M-023.16 — Stale-State Recovery Verification

### Objective

Prevent stale Docker lifecycle metadata from being presented as current
Service Lifecycle state while preserving Atlas's read-only provider boundary.

### Discovery

Repository and production review established one concrete stale-state
inconsistency:

- Operations already discarded `FinishedAt` for active containers;
- Service Lifecycle preserved Docker `FinishedAt` regardless of active state;
- live Restart Recovery observations therefore exposed an older finish time
  alongside the current running lifecycle's newer start time.

Scheduler lock recovery, interrupted media requests, and Sports recorder
recovery remain separately scoped milestones.

### Architecture

- Added the Stale-State Recovery architecture document.
- Added ADR 0014, Stale Runtime State Normalization.
- Defined the active-lifecycle invariant: running and restarting services have
  no normalized current finish timestamp.
- Kept `ServiceRuntime` provider-independent and placed Docker-specific stale
  fact suppression in the Docker Compose provider.
- Explicitly rejected a generic stale-state engine or universal freshness TTL.

### Implementation

- The Docker Compose provider validates the complete `ServiceRuntime` contract
  before suppressing a stale active `finished_at` value.
- Running and restarting services expose `finished_at=None`.
- Stopped and terminal services preserve valid finish timestamps.
- Docker zero timestamps remain `None`.
- Malformed non-zero finish timestamps remain explicit provider errors.
- No public command, model shape, or infrastructure mutation capability was
  introduced.

### Automated Validation

- Five focused stale-state tests passed.
- 225 Docker Compose provider tests passed.
- 64 Restart Recovery tests passed.
- 33 Service Doctor tests passed.
- 56 Operations Docker provider tests passed.
- 378 distinct regression tests passed in total, with the five focused
  stale-state cases also run separately.
- Python compilation and Git diff hygiene passed.

### Production Validation

Validated read-only against the active Docker environment:

- managed services inspected: 15;
- active running lifecycles: 15;
- active services with non-null `finished_at`: zero;
- stale-state contract violations: zero;
- Jellyfin Restart Recovery observation: normalized `finished_at` was `null`;
- infrastructure mutations: none.

### Commits

- `69188297` — define Stale-State Recovery architecture and ADR 0014;
- `9dea5c88` — discard stale active Docker finish timestamps.

### Result

M-023.16 is complete. Atlas now presents a consistent current-lifecycle
contract across Service Lifecycle and Operations: active containers do not
carry stale finish metadata from a previous lifecycle, while terminal history
and malformed-input validation remain preserved.

---

# 2026-08-05

## M-023.17 — Scheduler Recovery Verification

### Objective

Verify and harden recovery of the shared Atlas scheduler after scheduler
process interruption without adding a parallel scheduling or recovery engine.

### Discovery

Repository review confirmed that the existing `TaskScheduler` already owns the
required recovery foundation:

- scheduler state is persisted through Atlas atomic JSON writes;
- execution is serialized with an exclusive PID lock;
- task start is persisted before callback execution;
- successful and failed terminal states are explicit;
- normal due-state calculation is based on `last_success`;
- a lock whose PID no longer exists is reclaimable.

The review also identified one fail-open edge. Empty, malformed, or unreadable
lock ownership was treated as stale and automatically deleted even though
exclusive lock creation and PID writing are separate operations. Ambiguous
ownership was therefore not sufficient evidence that the lock was stale.

### Architecture

- Added the Scheduler Recovery architecture document.
- Added ADR 0015, Scheduler Recovery Boundaries.
- Kept `TaskScheduler` as the sole scheduler and recovery authority.
- Defined automatic reclamation only for a PID positively known not to exist.
- Defined fail-closed behavior for ambiguous ownership.
- Preserved `last_success` as the scheduling authority after interruption.
- Explicitly rejected exactly-once claims, a watchdog, a stale-state TTL, and
  a second recovery daemon.

### Implementation

- Empty and malformed runtime locks now fail closed.
- Non-positive PID values fail closed.
- Unreadable ownership fails closed.
- Indeterminate PID ownership fails closed.
- Permission-limited ownership remains protected.
- A positively dead PID still permits automatic stale-lock reclamation.
- Interrupted task state does not advance `last_success`, run counters,
  failure counters, or execution history without a terminal result.
- Successful retry returns the task to `healthy`.
- Failed retry transitions the task to `degraded`.
- No state schema, public model, CLI contract, or scheduler API changed.

### Automated Validation

- Nine focused Scheduler Recovery tests passed.
- 59 shared Scheduler and Operations scheduler regression tests passed.
- 10 Portal Scheduler service and schema tests passed.
- 69 distinct regression tests passed; the nine focused recovery tests are a
  subset of the 59 shared Scheduler tests and were also run separately.
- Python compilation and Git diff hygiene passed.

### Production Validation

Validated read-only at commit `b79870e1`:

- state file: `/mnt/storage/configs/atlas/scheduler/tasks.json`;
- lock file: `/mnt/storage/configs/atlas/scheduler/tasks.lock`;
- scheduler schema version: 2;
- registered tasks: two;
- task states: one `healthy`, one `never_run`;
- due tasks: `operations.collect` and `sports.maintenance`;
- persisted `running` tasks: zero;
- execution-history entries: one;
- runtime lock: absent;
- runtime consistency: passed;
- infrastructure mutations: none;
- repository remained clean.

The single historical Operations execution succeeded. Its stored
`event_error` records an older optional-module publication failure. The current
`operations.collect` registration has `module: null`, matching the later
core-task event-isolation boundary, so the historical event-delivery failure
does not represent a current Scheduler Recovery defect.

Production scheduler termination was intentionally not performed. The focused
tests deterministically exercise dead-owner lock reclamation and interrupted
task recovery without adding unnecessary production risk.

### Commits

- `51ce679a` — define Scheduler Recovery architecture and ADR 0015;
- `b79870e1` — fail closed on ambiguous scheduler locks.

### Result

M-023.17 is complete. Atlas now has a documented, fail-closed, tested, and
production-inspected Scheduler Recovery contract. Provably dead lock owners
remain automatically recoverable, ambiguous ownership cannot authorize
concurrent automation, and interrupted tasks preserve factual scheduler state
until a real terminal execution outcome is recorded.

---

# 2026-08-06

## M-023.18 — Interrupted-Request Recovery Verification

### Objective

Prevent interrupted Atlas media-request mutations from being silently replayed
when Atlas cannot prove whether an external provider operation completed.

### Discovery

Repository review established that request creation is locally atomic and
provider refresh is read-only, but submission and cancellation cross a durable
local/external-provider boundary.

Before M-023.18, provider submission occurred before Atlas persisted the
provider request ID and resulting request status. If the provider mutation
succeeded and Atlas was interrupted before the local replacement, the request
could remain `pending`; repeating submission could repeat the external
mutation.

Cancellation had the analogous window: provider deletion could succeed while
Atlas retained an active local request, allowing cancellation to be repeated
without proof that the first operation failed.

The existing Jellyseerr provider contract does not expose a stable Atlas
request-ID lookup that can safely reconcile an interrupted submission whose
provider request ID was never persisted.

### Architecture

- Added the Interrupted-Request Recovery architecture document.
- Added ADR 0016, Interrupted-Request Recovery Boundaries.
- Kept the existing Media Requests state machine, repository, service, and
  provider boundaries authoritative.
- Defined durable mutation intent before provider-side mutation.
- Defined ambiguous external outcomes as recovery-required state.
- Defined provider refresh as retry-safe because it is observational.
- Kept events best effort and outside the mutation commit protocol.
- Explicitly rejected exactly-once claims, automatic mutation replay, a second
  transaction journal, a recovery daemon, and destructive reconciliation.

### Model Contract

- Added normalized `submitting` and `cancelling` statuses.
- `submitting` requires `provider_request_id` to remain null because Atlas has
  not durably committed a provider result.
- `cancelling` requires `provider_request_id` because cancellation targets an
  already-submitted provider request.
- Both intent states remain active and non-terminal.
- Existing normalization, timestamp validation, deterministic `to_dict()`, and
  public `MediaRequestStatus` export behavior remain intact.

### Service Hardening

- Submission persists `submitting` before calling the provider.
- Cancellation persists `cancelling` before calling the provider.
- Failure to persist intent prevents the provider mutation from being invoked.
- Provider failure after intent persistence leaves the durable intent intact.
- Invalid or mismatched provider results do not erase ambiguous intent.
- Failure of the final Atlas persistence step after provider success leaves the
  durable intent intact.
- Repeated submit or cancel from a recovery-required state fails closed with an
  explicit reconciliation error.
- Successful operations still commit their normalized provider result and emit
  the existing best-effort events.
- Added `MediaRequestService.list_recovery_required_requests()` as a read-only,
  deterministic repository-backed observation boundary.

### Automated Validation

- 94 focused Media Request model tests passed after correcting the generic
  cancelling-state fixture to supply its required provider request ID.
- 149 combined model and repository tests passed.
- 335 broader Media Requests regressions passed for the model slice.
- 47 focused interrupted-request service tests passed.
- 57 combined service and event tests passed.
- 343 broader Media Requests regressions passed for service hardening.
- Three focused recovery-visibility tests passed.
- 50 complete Media Request service tests passed.
- 346 final broader Media Requests regressions passed.
- Python compilation, Atlas shell syntax, and Git diff hygiene passed.

### Production Validation

Validated read-only at commit `0ce8605f`:

- no existing media-request `requests.json` registry was found beneath the
  Atlas production configuration root;
- no non-test `JsonMediaRequestRepository` construction site is currently
  tracked, so there is no deployed request registry requiring migration;
- Jellyseerr runtime state was `running` with exit code zero and no lifecycle
  errors;
- Service Lifecycle reported Jellyseerr as `degraded` with score 85 solely
  because the container does not configure a Docker healthcheck;
- the exact warning was `No Docker health check is configured`;
- the interrupted-request public model/service boundary passed;
- all 346 final Media Requests regressions passed;
- provider mutations: none;
- repository mutations: none;
- repository remained clean.

The Jellyseerr degraded score is an existing observability characteristic, not
an Interrupted-Request Recovery defect. Production submission or cancellation
was intentionally not performed because the milestone's safety properties are
deterministically exercised by provider test doubles and do not require an
unnecessary live external mutation.

### Commits

- `7ff47062` — define Interrupted-Request Recovery architecture and ADR 0016;
- `7d6bb194` — add durable recovery intent states and model invariants;
- `46875eaf` — persist provider mutation intent and block ambiguous replay;
- `0ce8605f` — expose recovery-required requests through a read-only service
  boundary.

### Result

M-023.18 is complete. Atlas now records externally mutating media-request
intent before provider I/O, preserves ambiguity instead of guessing an outcome,
blocks unsafe mutation replay, and exposes recovery-required state through the
existing Media Requests service boundary. Automatic provider reconciliation
remains intentionally deferred until a stable non-mutating correlation
mechanism exists.

---

# 2026-08-06

## M-023.19 — Sports Recovery Verification

### Objective

Verify that the optional Sports module can recover recorder state after
controller interruption without duplicating a recording, adopting an unrelated
process, or signaling a process Atlas cannot prove it owns.

### Discovery

The existing Sports module already contained a substantial recovery foundation:

- durable recording state in `recordings.json`;
- persisted recorder PIDs and output metadata;
- atomic recording-registry replacement;
- exit-code sidecars;
- partial-file finalization;
- live recorder adoption after controller restart;
- scheduler success and failure integration coverage; and
- a dedicated Sports recovery integration test.

Discovery identified one concrete safety gap. Recovery and termination treated
PID liveness as sufficient recorder ownership evidence. Because Linux can reuse
a PID after the original process exits, PID-only ownership could associate
Atlas with an unrelated process.

### Architecture

- Added the Sports Recovery architecture document.
- Added ADR 0017, Sports Recorder Process Identity.
- Preserved the existing Sports scheduler, recorder, recording registry, and
  controller boundaries.
- Defined durable recorder identity as PID plus Linux process start-time token
  from `/proc/<pid>/stat` field 22.
- Defined missing or mismatched identity as ambiguous and fail closed.
- Explicitly prohibited PID-only recorder adoption and process-group signaling.
- Rejected a second recovery engine, process supervisor, transaction journal,
  and destructive reconciliation of ambiguous processes.

### Implementation

At commit `1924f8eb`:

- recorder launch captures and returns the Linux process start-time token;
- the recording reconciler persists `process_start_time` with the recorder PID;
- live recorder adoption verifies PID and start-time identity;
- active recording state fails closed when identity cannot be verified;
- recorder stop verifies identity before `SIGTERM` or `SIGKILL`;
- identity is rechecked during the stop sequence; and
- an unrelated live process is never treated as recorder ownership merely
  because its PID matches persisted state.

### Automated Validation

Focused Sports Recovery integration proved:

- a controlled live recorder remains active after recovery;
- the original PID is retained and persisted;
- duplicate launch does not occur;
- process identity is verified during recorder adoption;
- mismatched process identity fails closed;
- the identity failure remains observable;
- an unrelated process remains running;
- mismatched identity blocks recorder stop;
- the unrelated process receives no signal;
- missing identity blocks recorder adoption; and
- completed recorder state still finalizes and persists correctly.

Sports Scheduler integration also passed for both successful and failed
recordings and proved that new recordings persist process identity.

The complete Sports regression runner passed all five integration suites:

1. maintenance;
2. provider;
3. recording;
4. recovery; and
5. scheduler.

Python compilation and Git diff hygiene passed.

### Production Validation

Read-only validation at commit `1924f8eb` established:

- the production Sports recording registry exists and contains zero persisted
  recordings;
- active recordings: zero;
- ambiguous active recordings: zero;
- therefore no legacy PID-only active recording requires migration;
- `atlas-sports-feed` is running and healthy;
- `atlas-sports-controller` is running and healthy;
- controller heartbeat age was 30 seconds during validation;
- TheSportsDB provider status is healthy with zero consecutive failures;
- FFmpeg is available at `/usr/bin/ffmpeg` and recorder mode is `ffmpeg`;
- structured Sports health is healthy across controller, providers, recorder,
  recordings, and storage;
- Sports storage was writable with 94.82 percent free; and
- production recorder mutations and repository mutations were both zero.

### Documentation Reconciliation

The pre-existing `docs/SPORTS.md` and `modules/sports/README.md` still described
the module as a planned shell with no deployed production services. M-023.19
reconciles both documents with the repository and production evidence while
keeping unfinished v1.0 Portal, request, playback, and administration work
explicit.

### Commits

- `3f620140` — define Sports Recovery architecture and ADR 0017;
- `1924f8eb` — verify and persist Sports recorder process identity.

### Result

M-023.19 is complete. Sports recovery now uses explicit durable process
identity rather than PID liveness, rejects ambiguous ownership, protects
unrelated processes from adoption and signaling, retains existing recording
recovery behavior, and has been validated against the live production runtime
without mutating recorder state.

---

# 2026-08-07

## M-023.20 — Automatic Cleanup Safeguards

### Objective

Verify that automatic cleanup cannot bypass Atlas favorite protection,
retention policy, execution-mode restrictions, or provider mutation boundaries.

The milestone intentionally verifies safety before enabling destructive
automation.

### Discovery

Repository discovery found a mature cleanup foundation:

- favorite-aware policy already feeds `RetentionService`;
- retention eligibility already feeds `CleanupService`;
- cleanup scanning and execution-plan models are normalized and tested;
- `CleanupExecutionService` accepts dry-run mode only;
- `DefaultCleanupExecutor` accepts dry-run reports only;
- provider delete operations are dispatched as previews only;
- dry-run contracts cannot report media modification;
- cleanup audit and history foundations already exist; and
- `MaintainerrIntegration` denies policy failure, invalid contracts, and
  identity mismatch.

Discovery also identified an important architectural distinction. The deployed
Maintainerr service is separate from the Atlas integration adapter, and the
repository has no non-test construction site proving that Maintainerr passes
destructive candidates through Atlas authorization.

Read-only inspection of `/mnt/storage/configs/maintainerr/maintainerr.sqlite`
found zero collections, zero collection-media rows, zero rule groups, and zero
rules. Therefore destructive Maintainerr automation is currently disabled.

### Architecture

Commit `55bf23d7` added:

- `docs/architecture/AUTOMATIC_CLEANUP_SAFETY.md`; and
- ADR 0018, Cleanup Mutation Authorization.

The permanent boundary is:

> A cleanup recommendation is not deletion authorization.

Any future destructive mutation must obtain fresh Atlas policy and retention
authorization for the exact provider and item at the mutation boundary.
Missing, stale, mismatched, invalid, or unavailable authorization fails closed.

M-023.20 does not add destructive Atlas cleanup, enable Maintainerr deletion,
edit the Maintainerr production database, or introduce another cleanup engine.

### Cross-Boundary Verification

Commit `370ebc43` added a dedicated safeguard suite proving the actual service
chain rather than only its individual units.

Six focused tests proved:

- a favorite becomes policy protection, retention ineligibility, cleanup
  `KEEP`, execution `SKIPPED`, and no provider preview call;
- eligible unprotected media may reach preview but remains unmodified;
- policy failure stops the workflow before provider preview;
- destructive `execute` mode is rejected before provider preview;
- Maintainerr assessment denies favorited media through the same Atlas cleanup
  chain; and
- removing the final favorite requires a fresh assessment before eligibility
  can change.

The broader cleanup, retention, favorites, and Maintainerr regression passed
281 tests and 39 subtests.

### Production Validation

Read-only production validation at commit `370ebc43` established:

- Atlas cleanup planning rejects non-dry-run execution;
- the default executor rejects non-dry-run execution;
- the executor contains exactly two provider-preview dispatch boundaries;
- production Maintainerr collections: zero;
- production Maintainerr collection-media rows: zero;
- production Maintainerr rule groups: zero;
- production Maintainerr rules: zero;
- destructive Maintainerr configuration is disabled;
- the live Atlas Jellyfin cleanup execution plan ran in `dry_run` mode;
- the live plan contained zero items and reported `modified=0`;
- the live Atlas cleanup workflow completed successfully in `dry_run` mode;
- workflow total, planned, skipped, and modified counts were all zero;
- temporary validation audit events: zero;
- the live provider validation mode was `preview-validated`;
- 18 safeguard and Maintainerr regression tests passed; and
- production media mutations and repository mutations were both zero.

Python compilation, cleanup shell syntax, and Git diff hygiene passed.

### Documentation Reconciliation

The historical Maintainerr 72-hour cleanup document previously suggested
direct destructive actions plus a manual favorite exclusion. That guidance no
longer represents the supported Atlas safety boundary.

M-023.20 replaces it with explicit non-destructive v1.0 guidance: Maintainerr
may remain deployed, but destructive collections and rules stay disabled until
an Atlas-authorized, fresh, auditable mutation path exists.

The roadmap now records the backend favorite-protection, final-favorite
release, cleanup execution safeguard, and automatic cleanup safeguard proofs as
complete. Portal favorite integration remains separate unfinished work.

### Commits

- `55bf23d7` — define the automatic cleanup safety boundary and ADR 0018;
- `370ebc43` — prove automatic cleanup safeguards across service boundaries.

### Result

M-023.20 is complete. Atlas automatic cleanup remains intentionally
non-destructive, favorite and policy protections are proven across the cleanup
chain, external destructive automation is disabled in production, and the live
cleanup workflow has been validated with zero media mutations.

---

## M-023.21 — VPN Fail-Closed Verification

### Objective

Verify the v1.0 security invariant that qBittorrent cannot use a non-VPN
internet path while its required Gluetun VPN tunnel is unavailable.

The milestone separates startup readiness and healthy-path VPN egress from the
stronger requirement to prove the actual failure path.

### Discovery

Repository and production discovery established the existing safety topology:

- qBittorrent uses `network_mode: service:gluetun`;
- qBittorrent has no independent Compose network or direct published ports;
- Gluetun publishes the qBittorrent Web UI and peer ports;
- Gluetun owns `NET_ADMIN`, `/dev/net/tun`, and `FIREWALL=on`;
- qBittorrent waits for `gluetun` with `condition: service_healthy`; and
- the existing Atlas VPN verifier proves healthy-path egress but does not by
  itself prove leak prevention after tunnel loss.

### Architecture

Commit `94ea38e9` added:

- `docs/architecture/VPN_FAIL_CLOSED.md`; and
- ADR 0019, VPN Fail-Closed Enforcement Boundaries.

The permanent security invariant is:

> qBittorrent must have no usable non-VPN internet egress path while its
> required VPN tunnel is unavailable.

The architecture keeps namespace isolation, tunnel/firewall enforcement,
startup readiness, healthy-path observation, and controlled failure evidence
as separate responsibilities. Unknown or contradictory evidence fails closed.

### Automated Verification

Commit `097f5099` added static production Compose verification and a root
Verify failure-path test.

The tests prove:

- qBittorrent shares only Gluetun's network namespace;
- qBittorrent has no independent network attachment or published ports;
- Gluetun owns the VPN firewall and tunnel boundary;
- qBittorrent ports are published by Gluetun;
- qBittorrent waits for Gluetun health; and
- unavailable VPN egress causes Atlas Verify to fail without suppressing
  later verification sections.

Twenty-six focused VPN/Verify tests passed. Seventy-eight Startup Policy
regressions also passed, for 104 relevant tests across the combined boundary.

### Read-Only Production Validation

Read-only validation at commit `097f5099` established:

- normalized Compose topology matched the architecture;
- Gluetun and qBittorrent were running;
- Gluetun was healthy;
- both containers shared kernel network namespace `net:[4026532761]`;
- `tun0` was up and owned the VPN split routes;
- the underlying namespace also retained an `eth0` default route;
- Gluetun exposed explicit firewall DROP/REJECT enforcement;
- healthy qBittorrent egress differed from host egress;
- Atlas VPN verification passed;
- 104 relevant regressions passed; and
- no VPN, firewall, route, container, or repository mutation occurred.

This was strong runtime evidence but, intentionally, was not recorded as final
failure-path proof.

### Controlled Production Failure Validation

The operator explicitly approved one `SIGTERM` to the dynamically verified
`openvpn2.6` child and approved `docker restart gluetun` only as an emergency
recovery fallback if Gluetun's supervisor did not restore the tunnel.

The controlled run established:

- the OpenVPN child identity was verified immediately before signaling;
- `tun0` disappeared after the single approved signal;
- Gluetun and qBittorrent remained running in their shared namespace;
- with `tun0` absent, the kernel still resolved `1.1.1.1` through
  `172.19.0.1 dev eth0`;
- a DNS-independent direct IPv4 probe from qBittorrent timed out with curl
  exit status 28;
- `tun0` remained absent after the probe, keeping the entire proof window on
  the failure path;
- usable non-VPN qBittorrent egress was therefore blocked by the fail-closed
  boundary rather than by removal of every possible route; and
- the failure-path contract passed.

Gluetun recovered automatically. The emergency restart fallback was not used.
After recovery, Gluetun and qBittorrent still shared the same kernel network
namespace, qBittorrent regained VPN-routed egress distinct from host egress,
Atlas Verify passed, and 26 focused VPN regressions passed again.

Python compilation, Verify shell syntax, Git diff hygiene, branch guards,
commit guards, and working-tree guards all passed. qBittorrent, firewall,
route, Compose, and repository mutations were zero.

### Commits

- `94ea38e9` — define VPN Fail-Closed Verification architecture and ADR 0019;
- `097f5099` — prove fail-closed production topology and Verify failure
  behavior.

### Result

M-023.21 is complete. Atlas now has independent configuration, automated,
read-only runtime, and explicitly controlled production failure evidence that
qBittorrent cannot use the underlying non-VPN egress path while Gluetun's VPN
tunnel is unavailable, and automatic recovery has been proven without an
emergency container restart.

---

## M-023.22 — Storage-Full Behavior

### Objective

Define and verify how Atlas fails when required persistence encounters storage
exhaustion without deliberately filling the production filesystem.

The permanent invariant is:

> Storage exhaustion must not corrupt the last durable state, create an
> untracked external operation, or present a partial artifact as successful.

Storage pressure remains an observability and persistence condition. It is not
deletion authorization.

### Architecture

Commit `356049f6` added the Storage Exhaustion Recovery architecture and ADR
0020, Storage Exhaustion Failure Boundaries.

The architecture distinguishes low capacity, proven exhaustion, and unknown
storage state; preserves existing atomic-state and subsystem boundaries; and
explicitly rejects production-disk filling, automatic Media deletion, a second
persistence framework, and a new storage daemon.

### Core Persistence Hardening

Commit `ca52c941` hardened deterministic `ENOSPC` behavior across Core
persistence boundaries.

Validation proved:

- failed atomic temporary writes preserve the previous durable target;
- partial temporary state is removed when safe;
- Media Request registry filesystem errors become
  `MediaRequestRepositoryError` while retaining the original `ENOSPC` cause;
- failed submission-intent persistence blocks the external provider mutation
  and preserves the prior pending request state; and
- Operations repository persistence retains its normalized repository error
  contract and causal `ENOSPC` evidence.

The stage passed 139 focused atomic/persistence tests, 349 broader Media
Request regressions, and 42 Scheduler persistence regressions.

### Sports External-Process Hardening

Commit `da2f0318` closed the external-process ordering gap discovered during
M-023.22.

Sports recording reconciliation now tracks only recorder processes genuinely
started by the current reconciliation pass. If the updated recording registry
cannot be persisted, Atlas attempts bounded compensation using the exact PID
and Linux process start-time identity returned by launch.

An adopted existing recorder is never added to the compensation set. Failed
exact-identity compensation becomes an explicit error rather than authorizing
an ambiguous signal.

Four deterministic tests proved new-process compensation, adopted-process
protection, explicit compensation failure, and registry/temp-file preservation
under simulated `ENOSPC`.

### Backup Artifact Hardening

Commit `c5c56992` changed `atlas backup` from direct final-name creation to
transactional artifact publication.

New backups are created as `atlas-<timestamp>.tar.gz.partial` on the target
backup filesystem. Atlas reports available capacity, validates the completed
temporary archive, and only then atomically renames it to the canonical
`.tar.gz` name.

Creation, validation, or publication failure returns failure and does not
publish a canonical completed-backup name. Backup listing and retention see
only canonical `.tar.gz` artifacts.

Four focused backup storage-safety tests and 21 Backup CLI regressions passed.

### Read-Only Production Validation

Final M-023.22 validation at commit `c5c56992` deliberately did not fill or
otherwise mutate production storage.

The production observation established:

- storage root: `/mnt/storage`;
- total bytes: `1967846068224`;
- used bytes: `3116777472`;
- free bytes: `1864692621312`;
- free capacity: 94.76 percent;
- canonical Atlas backups: 10;
- partial Atlas backup artifacts: zero;
- newest canonical backup:
  `atlas-20260718-041132-663.tar.gz` (`145153` bytes);
- the newest canonical archive and `BACKUP_INFO.txt` manifest validated;
- the Sports recording registry contained zero persisted and zero active
  recordings; and
- production storage fill, backup mutation, recorder mutation, cleanup
  mutation, and repository mutation were all zero.

The final cross-boundary regression passed 189 tests spanning atomic
persistence, Media Request repository/service behavior, Operations
persistence, Scheduler persistence, Sports recorder compensation, and backup
publication safety.

Python compilation, backup shell syntax, Git diff hygiene, branch guards,
commit guards, and working-tree guards all passed.

### Documentation Reconciliation

The v1.0 reliability roadmap now records Storage-Full Behavior as complete and
keeps unavailable-provider behavior separate and unfinished.

The backup operator document now points to the canonical `atlas backup` CLI
and documents partial-artifact identity, validation-before-publication,
capacity observation, canonical retention, and the boundary between M-023.22
and the still-open full Backup and Recovery certification work.

### Commits

- `356049f6` — define storage exhaustion failure boundaries;
- `ca52c941` — fail closed on `ENOSPC` persistence;
- `da2f0318` — fail closed on Sports recorder persistence; and
- `c5c56992` — publish backup archives atomically.

### Result

M-023.22 is complete. Atlas now preserves last-known-good durable state under
controlled storage exhaustion, prevents provider mutation when required intent
cannot be persisted, compensates only exact-identity newly launched Sports
recorders, prevents partial backups from masquerading as successful artifacts,
and has read-only production evidence confirming the live storage and backup
state without deliberately creating a storage-full incident.

---

## M-023.23 — Unavailable-Provider Behavior

### Objective

Define and verify the v1.0 failure semantics used when an external or
infrastructure provider is unavailable, unreachable, timed out, unauthorized,
or returns unusable data.

The permanent invariant is:

> Provider unavailability must remain observable, must not be interpreted as
> an empty successful response, and must not authorize or replay an external
> mutation.

### Architecture

Commit `15a502b5` added ADR 0021, Unavailable Provider Failure Semantics, and
the Unavailable-Provider Behavior architecture.

The architecture preserves provider-specific domain contracts rather than
introducing a universal provider base class. It separates read-only
observation, required provider mutation, multi-provider aggregation, and
provider-assisted safety checks while applying one shared fail-closed rule.

The documented failure classes include transport/timeout failure,
authentication or authorization failure, invalid provider response,
authoritative resource absence, and outcome-ambiguous mutation.

### Deterministic Cross-Boundary Safeguards

Commit `faf17404` added a dedicated unavailable-provider safeguard suite.

The focused tests prove:

- Jellyfin URL/transport failure raises `MediaProviderError` instead of
  returning an empty successful inventory;
- Jellyfin timeout behavior has the same fail-closed contract;
- an empty Sports provider input does not erase the existing recording
  registry;
- an empty Sports provider input does not erase previously monitored
  non-finished game state; and
- a failed Sports provider fetch becomes explicit degraded provider health
  while subscribed previous-state evidence remains available.

The implementation required no runtime code changes. The discovered production
paths already satisfied ADR 0021; M-023.23 adds direct regression evidence
around the previously implicit boundaries.

### Existing Boundaries Revalidated

M-023.23 also revalidated existing subsystem contracts rather than duplicating
them in a second provider framework.

Media Requests already provide normalized provider health with explicit
`unavailable` and `unknown` states whose `available` property is false.
Jellyseerr HTTP/provider failures are normalized, and failed submission or
cancellation preserves durable `submitting` or `cancelling` intent so an
outcome-ambiguous provider mutation cannot be silently replayed.

The default cleanup executor remains dry-run-only. Provider preview failure is
reported as failed or partial preview and `modified` remains zero.

Sports isolates provider fetch failures, records consecutive-failure evidence,
continues unaffected providers, preserves existing recording plans, and keeps
non-finished monitored state until authoritative lifecycle or subscription
evidence justifies transition or removal.

### Automated Validation

The implementation stage passed:

- 5 focused unavailable-provider safeguards;
- 24 Jellyfin/provider tests plus 13 subtests in the Jellyfin regression run;
- 203 Media Request provider/recovery tests; and
- 37 cleanup unavailable-provider/safeguard tests.

Final cross-boundary validation at commit `faf17404` passed 264 tests plus 13
subtests spanning the dedicated safeguards, Jellyfin provider/preview/scan,
Media Request provider/HTTP/Jellyseerr/service behavior, and cleanup executor
and safety boundaries.

### Read-Only Production Validation

Production validation was deliberately observational. No provider was stopped,
disconnected, reconfigured, or asked to perform a mutation.

The live validation established:

- Jellyfin was running and Docker reported it healthy;
- Jellyseerr was running and continued to expose the known no-healthcheck
  runtime characteristic;
- Service Lifecycle Doctor returned valid JSON containing both Jellyfin and
  Jellyseerr visibility;
- persisted TheSportsDB provider health was `healthy` with zero consecutive
  failures and no last provider error;
- persisted Sports aggregate health was `healthy`;
- `MediaProviderError` remains publicly exported;
- `ProviderHealthStatus.UNAVAILABLE` exposes `available == false`;
- `ProviderHealthStatus.UNKNOWN` exposes `available == false`; and
- the repository remained clean.

Provider interruptions, provider mutations, Sports-state mutations, and
repository mutations were all zero.

### Release-Quality Checks

Python compilation, Git diff hygiene, branch guards, commit guards, and
working-tree guards passed. The production validator stored observational
artifacts beneath `/tmp/m023-23-3-unavailable-provider-validation` without
altering tracked repository state.

### Documentation Reconciliation

The v1.0 Reliability roadmap now records Unavailable-Provider Behavior as
complete and expands the milestone into the architecture, fail-closed mutation,
cleanup, Sports preservation, and production-observability evidence that was
actually verified.

This closes the final open item in the v1.0 Reliability subsection. Deployment
Safety, Backup and Recovery certification, Security, Quality, Documentation,
and release-level certification remain separate unfinished v1.0 work.

### Commits

- `15a502b5` — define unavailable-provider failure semantics; and
- `faf17404` — prove unavailable-provider safeguards.

### Result

M-023.23 is complete. Atlas now has architecture, deterministic regression, and
read-only production evidence that provider unavailability remains observable,
does not masquerade as a successful empty response, preserves safety-critical
state, and cannot implicitly authorize or replay an external mutation.

---

## M-023.24 — Production Deployment Safety

### Objective

Make production source promotion and runtime deployment explicit, tested,
recoverable transactions before v1.0 certification. The boundary must keep
unfinished source out of production, protect users during maintenance, capture
recovery evidence before mutation, fail closed on ambiguous migration or
runtime state, and preserve enough exact evidence for rollback or deliberate
forward recovery.

### Architecture and Protected Promotion

ADR 0022 and the Deployment Safety architecture define `main` as the stable
production source, focused feature/fix branches as development surfaces, and
`release/<version>` as the temporary certification surface. No permanent
`develop` branch was introduced.

GitHub repository rules were configured for `main` and `release/**` with pull
requests, strict required status checks, blocked force pushes, blocked branch
deletion, and no default bypass. The stable required check is the aggregate
`release-gate` job.

The release workflow validates Core Python, API, Sports, Portal, and shell
deployment contracts independently before the aggregate gate succeeds. Clean
runner failures discovered missing Sports `ffmpeg`, host-specific runtime
paths, and a hard-coded Operations project root. Those portability defects were
corrected before certification. The workflow Actions were also moved to the
current supported major versions used by the project.

Feature source was certified through pull request 1 into `release/v1.0.0` and
then promoted through pull request 2 into `main`. Both pull-request and push
release gates passed. The promoted production source became merge commit
`d2fa67fa`.

### Transactional Deployment Boundary

The production CLI now provides Caddy-owned maintenance mode, deployment status
and baseline capture, a transactional `atlas update`, and explicit recorded
rollback. The update boundary requires synchronized clean `main`, an exact
verified runtime baseline, an exclusive lock, `--migration none`, a validated
pre-update Atlas backup, affected-surface application, post-change verification,
and a verified new baseline before completing.

Rollback restores source from recorded archives outside the live Git worktree,
uses exact recorded image identities with `--no-build --pull never`, and blocks
automatic recovery for state-changing migrations without release-specific
evidence.

### First Production Baseline and Controlled Update

The initial verified baseline was
`baseline-20260808T031022Z-2062686`. Production Doctor, Atlas Verify, and ingress
verification were healthy before mutation.

An explicitly approved `atlas update all --migration none` created transaction
`update-20260808T031433Z-2068627` and validated pre-update backup
`atlas-20260807-231434-044.tar.gz`. The update applied successfully and the new
API, Portal, and Caddy containers were healthy, but post-update ingress
verification failed while maintenance was correctly returning HTTP 503.

Atlas failed closed: the transaction became `failed`, maintenance remained
enabled, the deployment lock remained owned by the failed transaction, and the
previous verified baseline remained current.

### Recovery Defects Discovered

Read-only diagnosis established that the runtime itself was healthy and exposed
two deployment-recovery contract defects.

First, the public ingress verifier could not distinguish intentional maintenance
HTTP 503 isolation from an unavailable Portal/API. The update and rollback
paths therefore could not satisfy public-route verification before maintenance
was disabled.

Second, baseline capture recorded exact Docker image IDs but did not create a
durable reference to them. Rebuilding `atlas-api:local` and
`atlas-portal:local` moved those mutable tags. A guarded rollback attempt then
correctly refused before changing runtime because the exact pre-update API image
was unavailable. Seventeen of 19 baseline image IDs remained available; the two
missing identities were precisely the locally built API and Portal images.

No fake rebuild or best-effort substitution was accepted as rollback.

### Controlled Forward Recovery

Because exact rollback was impossible but the candidate runtime was internally
healthy, recovery proceeded forward under explicit approval. While the failed
transaction lock and maintenance boundary remained intact, Atlas verified the
runtime, disabled maintenance, proved public ingress, captured new verified
baseline `baseline-20260808T033011Z-2093776`, reran final verification, and only
then released the lock.

The failed transaction remains `failed` as permanent runtime audit evidence.
The forward-recovery operation did not rewrite its outcome.

### M-023.24.6 Recovery-Contract Repair

Commit `83ff0641` repaired both discovered boundaries.

Before pull or build mutation, the update transaction now attaches a unique
`atlas-rollback:` tag to every image in the previous verified baseline and
verifies the tag resolves to the exact captured ID. This gives locally built
images a durable recovery reference even after their ordinary mutable tag is
replaced.

Ingress verification now has two explicit modes. Normal mode retains the public
Portal/API checks. Maintenance mode instead proves Caddy liveness, direct
Portal/API backend health, and exact HTTP 503 isolation at both public paths.
After maintenance is disabled, update and rollback repeat public verification
before publishing the recovered/candidate baseline or releasing the lock. A
failed reopening re-enables maintenance and leaves the previous verified
baseline authoritative.

### Automated Validation

The focused deployment-recovery suite passed 35 tests. The complete Core suite
passed 2,878 tests plus 104 subtests. Shell syntax, Python compilation, exact
changed-file guards, artifact hygiene, and Git diff hygiene passed.

### Controlled Production Contract Validation

Production validation explicitly exercised the repaired boundaries without
performing another update, pull, build, restart, or container recreation.

The live sequence proved:

- normal ingress: 24 passed, zero failed;
- maintenance mode: 27 passed, zero failed;
- Caddy liveness remained reachable during maintenance;
- direct Portal and API backends remained reachable during maintenance;
- public Portal and API both returned the required HTTP 503 isolation;
- reopened normal ingress: 24 passed, zero failed;
- all 19 baseline images acquired recovery references resolving to their exact
  image IDs; and
- every temporary validation recovery tag was removed afterward.

Final invariants showed maintenance disabled, no deployment lock, verified
baseline `baseline-20260808T033011Z-2093776` still current, failed transaction
`update-20260808T031433Z-2068627` still recorded as `failed`, and a clean repair
branch.

### Remaining Release Boundary

The historical annotated `v1.0.0` tag at `a67bb8a5` remains intentionally
untouched. It predates the current certification line and remains an explicit
final-release blocker. M-023.24 does not reinterpret or silently move it.

Backup and Recovery certification, Security, Quality, Documentation completion,
and final release certification remain separate v1.0 work.

### Result

M-023.24 is complete. Atlas now has protected source promotion, a tested
transactional deployment boundary, user-visible maintenance isolation, exact
pre-mutation rollback-image retention, deterministic failed-update state,
explicit forward recovery, and controlled production evidence for both normal
and maintenance traffic states.

---

## M-023.25 — Backup and Recovery Certification

### Objective

Turn Atlas backup from a useful configuration archive into an explicit,
state-complete Atlas recovery boundary and prove that the corresponding restore
transaction can recover the declared production state without bypassing source
certification, deployment mutual exclusion, maintenance isolation, or consumer
verification.

### Architecture and State Ownership

ADR 0023 and the Backup and Recovery architecture established two governing
rules: an archive is not recoverable merely because it exists, and unvalidated
backup content is never extracted directly over live production state.

The canonical recovery registry now owns 11 state surfaces: users, optional
identity invitations, favorites, optional Media Requests, scheduler state,
runtime events, runtime subscribers, retention/ARI state, Sports
subscriptions, Sports recording metadata, and the Sports scheduler. Related
event/subscriber and Sports state is captured through declared consistency
groups rather than independent best-effort copies.

Media Requests gained the canonical `ATLAS_REQUESTS_DIR` root. Production had
no request registry during certification, so that declared optional surface was
correctly represented as `absent-optional` instead of being manufactured.

### State-Complete Backup

Recovery Format 1 added `RECOVERY_FORMAT`, `RECOVERY_MANIFEST.tsv`, and
`SHA256SUMS` to the protected atomic backup publication contract. Required
state is allowlisted, recovery-critical files are checksummed, unsafe or
incomplete archives fail validation, partial/final recovery archives are
owner-only, and retention runs only after successful publication.

The backup CLI was also made fail closed: help and listing are read-only and an
unknown option no longer falls through to backup creation.

A controlled production-shaped capture proved all nine present required/state
surfaces and the two absent optional surfaces could be captured consistently.
The final fresh round-trip source archive was:

`/tmp/project-atlas-m023-25-live-roundtrip.9PRa7F/atlas-20260808-172136-835.tar.gz`

with SHA-256
`dcc0895d30e06c8561c6ed95a9a010a212485b25d49ee6d90cdfbafe7ea5f6d8`.

### Validation-First Restore

The restore CLI progressed deliberately from read-only inspection to isolated
staging before live mutation was exposed:

- `atlas restore inspect <archive>` reports metadata without asserting
  validity;
- `atlas restore verify <archive>` validates Format 1 integrity and state
  completeness;
- `atlas restore stage <archive>` rejects unsafe members and extracts only to
  a private isolated root;
- `atlas restore validate-stage <staging-root>` loads staged state through real
  Atlas consumer contracts without mutation; and
- `atlas restore plan <staging-root>` reports every live action and safety
  dependency before mutation.

ARI retention validation discovered real legacy history that is intentionally
incompatible with the current strict report model. The validator was repaired
to follow the production `ARIAnalytics(service).load_history()` compatibility
contract while still requiring `service.latest()` to satisfy the strict
current-state contract. The real staged recovery state then passed with 46
compatible reports and 11 legacy/incompatible history reports skipped.

### Transactional Live Replacement

Bounded replacement primitives provide explicit apply, revert, and finalize
phases. Optional-absent state removes a prior live optional surface only as a
recorded transaction action. Deterministic injected mid-transaction failure
proved every already-applied surface returns to its displaced state.

Live orchestration then added the production ceremony around that replacement:

1. require clean certified `main` exactly matching `origin/main`;
2. require a verified deployment baseline and validated staging root;
3. acquire the shared deployment/update lock;
4. enable and verify maintenance isolation;
5. create and validate a fresh pre-restore recovery point;
6. stop the exact writer set (`atlas-api`, `atlas-sports-controller`, and
   `atlas-notifications-worker`);
7. transactionally publish and validate the staged state;
8. restart and verify writers and consumers;
9. run Atlas, module, and ingress verification;
10. reopen and reverify public ingress; and
11. finalize state replacement and release the lock.

If verification fails after mutation begins, maintenance and the shared lock
remain held. `atlas restore resume <restore-id> --confirm-live` and
`atlas restore abort <restore-id> --confirm-live` are the only deliberate
resolution paths; shell cleanup does not silently reopen production.

### Automated Validation

Incremental focused suites covered registry structure, snapshot consistency,
archive integrity, CLI safety, archive-member safety, staged consumer
validation, restore planning, bounded state replacement, writer orchestration,
and live transaction failure/recovery behavior.

The final fail-closed live recovery implementation passed 41 focused restore
tests. The complete Core regression then passed 2,947 tests plus 104 subtests,
with shell syntax and Git diff hygiene clean.

### Protected Certification

Feature commit `02738ee3` was certified through the protected promotion path.
Pull request 5 merged it into `release/v1.0.0` as `c8a947c0`; all six required
pull-request checks and the release push gate passed. Pull request 6 then
promoted the certified release into `main` as `483085fa`, and the post-merge
main push gate passed.

The feature, release, and main trees were byte-identical at certification.
Before promotion, an explicitly confirmed live apply from the feature branch
was rejected because production mutation requires `main`. The rejection left
the deployment baseline, lock, maintenance state, backup inventory, writer
process identities, and repository unchanged.

### Controlled Production Recovery

Production was deliberately synchronized to certified `main` `483085fa` while
verified deployment baseline `baseline-20260808T043132Z-2166158` remained
authoritative. Doctor was 100 percent healthy and normal ingress passed 24/24
before the exercise.

The fresh current-state archive above was verified, staged at a private
temporary root, consumer-validated, and planned before mutation. Live restore
transaction `restore-20260808T174153Z-3004055` then:

- enabled maintenance and passed 27/27 maintenance-aware ingress checks;
- created pre-restore production recovery point
  `atlas-20260808-134255-455.tar.gz` with SHA-256
  `12c15ece97baab3533ace72c8c1a6c601781bf3a4f2c8389f93503db171680d9`;
- validated the recovery point as Format 1 state-complete;
- quiesced and restarted the API, Sports controller, and Notifications worker;
- validated the published live state through the real consumers;
- returned Atlas Health to 100 percent;
- reopened normal public ingress and passed 24/24 checks;
- released the shared deployment lock and disabled maintenance; and
- preserved the verified deployment baseline and clean certified repository.

The retained restore audit record is
`/mnt/storage/configs/atlas/restores/restore-20260808T174153Z-3004055`.
Production backup retention remained at its explicit ceiling of 10 canonical
archives.

The transaction timestamp was 17:41:53 UTC and the three controlled writers
were restarted at 17:43:02 UTC, approximately 69 seconds to writer restart on
the tested topology. Full verification completed immediately afterward. This
is evidence rather than an SLO; the operator guide reserves at least a 5-10
minute maintenance window and scales the allowance with state size.

### Recovery Scope

M-023.25 certifies the declared Atlas configuration and authoritative state
surfaces. It does not contain the media library or claim complete recovery for
Jellyfin, Radarr, Sonarr, qBittorrent, or other third-party application
databases. Local archives under `/mnt/storage/backups/atlas` also share the
single host/storage failure domain. Independent/off-host storage, immutable or
encrypted copies, and full-platform disaster recovery remain later
infrastructure work.

### Result

M-023.25 is complete. Every Backup and Recovery roadmap item now has an
explicit state owner, implementation contract, regression evidence, controlled
production proof, recovery-time expectation, and documented scope limitation.
Atlas can create, validate, stage, plan, transactionally apply, verify, resume,
or abort state recovery without bypassing protected source promotion or the
shared production mutation boundary.

---

## M-023.26 — Security Review and Runtime Hardening

M-023.26 completed the v1.0 Security engineering-review work packages covering
authentication, authorization, invitation security, session behavior,
reverse-proxy and API exposure, secret storage, audit events, dependency/image
risk, network trust boundaries, and least privilege.

### First-Party Module Runtime Hardening

The final implementation slice hardened the Notifications and Sports
first-party module runtimes.

Both images now:

- require explicit operator `PUID` and `PGID` build inputs;
- create and run as the non-root `atlas` identity;
- use `no-new-privileges`;
- preserve source-only hardening separately from production ownership changes.

Notifications no longer receives the complete Atlas Runtime Bus. Its Compose
contract exposes only the read-only event journal, its writable subscriber
cursor, its read-only filter, and Notifications-owned state.

Sports no longer receives the Atlas Runtime Bus and no longer exposes the
obsolete private scheduler-state environment contract. Host TaskScheduler state
remains the authoritative scheduling boundary.

Both module update paths fail closed before container recreation when required
filesystem ownership or access does not satisfy the future runtime identity.
The update paths do not automatically `chown` production state.

### Validation

The source change was applied from synchronized
`feature/security-review` checkpoint
`75cfdc65d43ec8f3faa74cd1002670ed92ebe4da`.

Immediate validation passed:

- exact changed-file guard;
- shell syntax validation;
- 54 focused tests;
- Notifications and Sports Compose validation;
- Git diff whitespace validation.

Both hardened images then built successfully. Image inspection and isolated
runtime probes proved:

- Notifications configured user: `atlas`;
- Sports configured user: `atlas`;
- Notifications effective UID:GID: `1000:1000`;
- Sports effective UID:GID: `1000:1000`.

The existing production Notifications and Sports containers remained running
with their prior root-default runtime identity, proving that source/image
hardening did not silently perform the deferred production ownership migration
or recreate live containers.

The commit-readiness regression gate passed:

- 71 focused security/module tests;
- 26 module, restore, and notification regressions;
- all five Sports integration suites;
- 2,996 Core tests plus 104 subtests;
- 280 API tests plus 5 subtests;
- Compose validation;
- Git diff and repository-state guards.

The resulting atomic commit was
`4f30fb10de3a321b8d4cfdc6d818ca7725aa687e`
(`security: harden first-party module runtimes`) and was pushed to
`origin/feature/security-review` with local/remote equality and a clean working
tree.

### Security Closure

The M-023.26 closure review found no additional general source-hardening sprint
justified by the reviewed evidence. The ten Security roadmap items now represent
completed engineering reviews.

Final v1.0 Security Acceptance remains intentionally open. Release
certification must still include:

- current dependency/container vulnerability evidence with no unreviewed
  release-blocking finding;
- explicit acceptance or remediation of retained privileged capabilities,
  including Homepage/Dozzle Docker-socket access if retained;
- controlled production ownership migration and recreation of the hardened
  Notifications and Sports workers;
- runtime verification of secret, audit, ingress, network, and least-privilege
  boundaries;
- documented accepted security limitations; and
- explicit security approval through the release checklist.

M-023.26 therefore closes the Security engineering implementation without
prematurely certifying the v1.0 release.

---

## M-023.27.3B3 — Media Discovery and Safe Request Action

M-023.27.3B3 established the end-user Media discovery-to-request path while
preserving Atlas as the authoritative security and mutation boundary. The work
was completed as four atomic source commits on `feature/security-review`.

### B3.1 — Seerr Media Discovery Foundation

Commit `755409de9fdefb756f81248ff1f4016c2b100edb`
(`feat(media): add seerr-backed media discovery`) added read-only Media discovery
and search through Atlas.

The API exposes normalized movie/TV discovery state and keeps Seerr server-side.
`request_eligible` is advisory presentation state: only `not_tracked` is exposed
as eligible, while tracked, known, or unsupported provider states fail closed.
Provider media identity is carried only as the internal request target identity.

The final B3.1 regression passed 3,044 Core tests plus 104 subtests and 333 API
tests plus 15 subtests, including the dedicated discovery and Request provider
contracts.

### B3.2 — Personal Media Browse and Search

Commit `7bd4a14a1f2532e4cc69a8f02dadf07c601b2105`
(`feat(portal): add personal media discovery`) added `/portal/media` with
movie/TV browse, search, pagination, manual refresh, and stale-response
suppression.

The Portal consumes Atlas only; it does not connect directly to Seerr. Raw
provider media identifiers are retained internally for stable identity and
future request transport but are not rendered to the user. B3.2 remained
read-only.

### B3.3.1 — Active Request Duplicate and Race Protection

Commit `28cbb7902fd518734a907e02e011b67b484cb345`
(`feat(requests): enforce active request uniqueness`) hardened the durable Media
Request repository before Portal request mutation was exposed.

The Request registry now owns a persistent `requests.lock` sidecar. Every
read-modify-write mutation uses Linux `fcntl.flock()` exclusion, and the active
target conflict check plus the initial `PENDING` write occur in the same locked
transaction. Provider submission remains outside the lock and occurs only after
local persistence succeeds.

Active-target identity is global across Atlas users because all users share the
server-side provider identity. It consists of provider, provider media identity,
and normalized media family; user ID, title, and year do not define uniqueness.
Jellyseerr/Seerr movie and anime-movie requests share one movie family, while TV
and anime-TV share one TV family. An all-seasons TV request overlaps every
explicit season, the same explicit season conflicts, and different explicit
seasons may coexist. Terminal history does not permanently block a later
request.

A losing concurrent creator receives the existing HTTP 409 conflict path before
a second provider submission. Outcome-ambiguous provider mutations continue to
use the existing reconciliation-required/do-not-retry behavior from
Interrupted-Request Recovery. The schema remains version 1.

The final gate passed 3,055 Core tests plus 104 subtests and 336 API tests plus
15 subtests.

### B3.3.2 — Portal Media to Movie Request Action

Commit `b1c2ebcbfaa63775c8230cc17728911dab0b98c2`
(`feat(portal): add movie request action`) extended the existing Personal
Requests feature with caller-controlled POST `/requests` transport and added the
first Media-card Request action.

The Portal requires `requests.create` before rendering the movie mutation
control, while API authorization remains independently authoritative. The POST
contains only caller-controlled media fields, automatic mutation retries are
disabled, and each card owns its own submitting/result state. A target remains
locally blocked from repeated POST for the lifetime of the page after any
mutation attempt. Stale active-target HTTP 409 becomes `Already requested`;
reconciliation-required or otherwise unconfirmed outcomes become `Check
requests` and are not automatically replayed.

TV mutation is deliberately not exposed in this slice. A generic TV-card click
would otherwise map `season_number=None` to all seasons, so the Portal explicitly
requires future season-selection UX instead of making that choice silently.
Server-side TV and anime-TV provider capability remains intact.

For v1.0, ongoing TV and anime series remain a required end-user workflow:
a supported series request must be able to remain monitored downstream through
Seerr and the appropriate Sonarr instance so future episodes can be acquired
automatically without requiring a new Atlas request for each episode. This is a
release acceptance requirement; B3.3.2 does not claim that the Portal
season-selection workflow is complete yet.

The final B3.3.2 gate passed 67 focused Portal tests, the full 194-test Portal
suite, TypeScript typecheck, ESLint, and the Next.js production build.

### Result

M-023.27.3B3 completes the safe movie discovery-to-request source path and the
server-side concurrency prerequisite for future series request UX. No production
deployment was performed by these four source commits. TV/anime season selection,
downstream ongoing-series acceptance validation, and the remaining v1.0
end-to-end/user-acceptance gates remain open.

---

# 2026-08-10

## M-023.27.3B3.3.3A — TV Series Detail / Season Metadata Foundation

### Objective

Add the read-only TV-series contract required for explicit season-selection UX
without enabling TV/anime Request mutation.

### Completed

- Added normalized `MediaSeriesStatus`, `MediaSeriesSeason`, and
  `MediaSeriesDetail` contracts.
- Added deterministic serialization and ongoing-series derivation.
- Added Seerr TV detail retrieval through `GET /api/v1/tv/{id}`.
- Excluded Specials (`season 0`) from normal season selection.
- Added provider-status normalization and server-side anime classification.
- Added `GET /api/v1/media/tv/{provider_media_id}` behind `media.read`.
- Enforced positive TMDB identity before provider HTTP.
- Kept Portal TV/anime mutation, server routing, and Request persistence schema
  unchanged.

### Validation

- Dedicated zero-ID regression passed after correcting the provider guard.
- Focused Core: 63 passed.
- Focused API: 26 passed plus 3 subtests.
- Full Core: 3,076 passed plus 104 subtests.
- Full API: 346 passed plus 15 subtests.
- Commit `b901702d`:
  `feat(media): add tv series detail metadata`.

---

# 2026-08-10

## M-023.27.3B3.3.3B — Explicit TV / Anime Routing and Submission Preflight

### Objective

Make TV/anime downstream routing deterministic and server-owned before the
Portal exposes series mutation.

### Completed

- Added backward-compatible provider `validate_submission()` preflight.
- Required Core preflight before active-target persistence.
- Required revalidation before persisting `SUBMITTING`.
- Required defensive provider validation before provider HTTP.
- Added explicit standard-TV and anime-TV Seerr `serverId` ownership through
  `ATLAS_JELLYSEERR_TV_SERVER_ID` and
  `ATLAS_JELLYSEERR_ANIME_TV_SERVER_ID`.
- Preserved valid server ID `0`.
- Failed missing/invalid TV routing before provider HTTP and before new Request
  persistence.
- Preserved movie/anime-movie payload behavior.
- Added ingress and environment-template configuration without hard-coded
  production server IDs.
- Kept Portal mutation, persisted Request schema/repository, production `.env`,
  and `monitorNewItems` out of the source slice.

### Validation

- Previously failing import-only test defect repaired without weakening tests.
- Focused Core: 209 passed.
- Focused Request API: 23 passed plus 7 subtests.
- Full Core: 3,096 passed plus 104 subtests.
- Full API: 348 passed plus 15 subtests.
- Commit `c1bbe9d5`:
  `feat(requests): add explicit tv routing preflight`.

---

# 2026-08-10

## M-023.27.3B3.3.3C — Seerr Monitoring / Runtime Ownership Review

### Objective

Resolve ownership of ongoing-series monitoring and distinguish repository
runtime truth from the currently deployed production container before enabling
Portal TV/anime mutation.

### Read-Only Findings

- Repository source pins
  `ghcr.io/seerr-team/seerr:v3.4.1` by digest and already includes `init: true`.
- The deployed container still reports
  `fallenbagel/jellyseerr:latest`.
- The deployed runtime has two sanitized Sonarr services:
  standard TV service ID `0` and Anime TV service ID `1`.
- Neither deployed Sonarr service record exposes `monitorNewItems`.
- The deployed application code contains zero `monitorNewItems` references.
- Explicit Atlas routing IDs `0` and `1` remain structurally compatible with
  the observed service identities, but production values are still deployment
  configuration and are not committed.
- Upstream Seerr owns new-season monitoring as a Sonarr-service setting; Atlas
  should not add it to caller-controlled Request state.

### Decision

Repository image ownership is already correct; no additional image source
change is required for this milestone. Production must still migrate from the
legacy Jellyseerr container to the pinned Seerr runtime under backup,
maintenance, and rollback control.

After migration, both supported Seerr Sonarr services must be verified with
`monitorNewItems=all`, Atlas routing IDs must be revalidated, and production E2E
tests must prove ongoing standard TV and anime TV remain monitored for future
episodes. Until those runtime acceptance gates pass, Atlas must not claim
ongoing-series monitoring is production-certified.

Season scope and future-season monitoring remain separate concepts. Portal
season selection must express the user's Request scope without pretending the
service-level Seerr monitoring policy is a per-request toggle.

### Safety

The review was read-only:

- no source or documentation mutation;
- no container restart or image pull;
- no settings or database write;
- no production `.env` change;
- no Request or Portal mutation; and
- no production deployment.
