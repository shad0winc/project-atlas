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

## M-020.3 Hardening — Jellyfin User Link Validation

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

# Current Status

**Development State:** Active post-foundation development

## Platform Capabilities

- Production media platform.
- Operational Atlas CLI.
- Health monitoring.
- Historical analytics.
- Capacity forecasting.
- Operational recommendations.
- Modular sports platform foundation.
- Atlas-native identity and invitation system.
- Transactional registration workflow.
- Provider-neutral favorites infrastructure.
- Jellyfin-backed metadata enrichment and user validation.

## Next Planned Work

- Commit and close M-020.3.
- Begin M-020.4 — Media Policy Engine.
- Add retention decisions driven by favorites, requests, watch history, and user policy.
- Integrate policy decisions with Maintainerr in a later patch.


---

## M-021.4
--------
Implemented the Atlas Retention CLI.

Added:
- atlas.retention_cli
- scripts/commands/retention.sh
- CLI routing
- Help integration
- JSON output
- Human-readable output
- Regression tests

Regression:
153/153 PASS

---

## Completed M-022.2 Cleanup CLI
--------
Added:
- atlas.cleanup_cli
- scripts/commands/cleanup.sh
- CLI routing
- Help integration
- Human and JSON output
- Full regression validation

Core Tests:
167 passing
0 failures

---

# 2026-07-20

## M-023.3 — Cleanup Execution Planning

### Objective

Introduce a non-destructive execution layer that converts cleanup scan results into an execution plan while guaranteeing that no media or provider state is modified.

### Completed

- Added normalized cleanup execution models.
- Added CleanupExecutionService.
- Added dry-run execution planning.
- Added execution report rendering.
- Added `atlas cleanup execute`.
- Added JSON execution output.
- Added human-readable execution output.
- Added execution CLI dependency injection.
- Added focused execution model, service, and CLI tests.

### Verification

- `git diff --check` passed.
- Focused cleanup execution tests: 13 passing.
- Cleanup regression suite: 70 passing.
- Full Atlas Core regression suite: 229 passing.
- Live execution of `atlas cleanup execute jellyfin --dry-run`.
- Live execution of `atlas cleanup execute jellyfin --dry-run --json`.

### Result

Atlas now provides a complete read-only cleanup planning pipeline:

Jellyfin Provider
    ↓
Cleanup Scanner
    ↓
Cleanup Execution Planner
    ↓
Human / JSON Report

No filesystem mutations.
No Jellyfin modifications.
No deletion logic.
Execution planning remains intentionally dry-run only.

