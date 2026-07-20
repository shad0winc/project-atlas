# Changelog

All notable changes to Project Atlas are documented in this file.

## [Unreleased]

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

### Improved

- Jellyfin user linking now validates the supplied Jellyfin user ID against the Jellyfin API before persisting the association.
- Jellyfin user validation preserves an existing valid link when a replacement ID is rejected.
- Jellyfin provider errors now use resource-neutral not-found messaging for both media and user lookups.
- Sports worker and controller now use the shared Core event publisher.
- Core scheduler validation now runs through standard `unittest` discovery.
- Python compilation, Atlas Core unit tests, and Sports integration tests are unified behind one CLI entry point.
- Nested module `.env` files are explicitly ignored.

### Validation

- Added focused Jellyfin provider tests for valid users, malformed responses, mismatched identities, and not-found responses.
- Added user CLI tests confirming valid Jellyfin IDs are persisted only after provider validation.
- Added regression coverage confirming invalid Jellyfin IDs are rejected without overwriting an existing valid link.
- Verified the complete repository test suite with 119 passing tests.
- Live-tested Jellyfin API authentication, user discovery, valid identity linking, invalid identity rejection, and preservation of the prior valid association.

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
