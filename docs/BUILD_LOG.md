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
