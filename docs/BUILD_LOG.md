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
