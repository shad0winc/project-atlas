# Changelog

## [Unreleased]

- Added one-shot scheduler execution for due or named tasks with subprocess isolation, runtime locking, stale-lock recovery, success/failure metadata, bounded history, and best-effort module events.
- Added `atlas scheduler run`, `dry-run`, and `history` commands.

### Validation

- Added `atlas test [all|core|sports]` as the authoritative repository-wide validation command.
- Unified Python compilation, Atlas Core unit tests, and Sports integration tests behind one CLI entry point.

### Added

- Dependency-free WSGI registration portal with invitation validation, secure form handling, friendly success/error pages, and no-store security headers

- Transactional invitation redemption and registration service with external user provisioning, Atlas/Jellyfin identity linkage, compensating rollback, and best-effort audit event delivery
- Rollback-safe Atlas profile deletion for failed multi-system registration transactions

- Invitation lifecycle CLI for issuing, listing, inspecting, revoking, verifying, and cleaning up invitations

- Atlas identity infrastructure with secure hashed invitation tokens, durable lifecycle storage, expiration handling, and consistency verification
- Atlas user identity and profile framework with Jellyfin linkage, optional personal fields, atomic storage, validation, and user-management CLI commands
- Foundational Atlas Health Engine with a normalized Python data model and JSON report output
- `atlas health` command for machine-readable foundational health reporting
- Shared shell health-result helpers and Core health-engine unit tests
- Shared Atlas Core Python event publisher in `atlas/events.py`
- Discoverable unit tests for Core event publishing

### Improved

- Sports worker and controller now use the shared Core event publisher
- Core scheduler validation now runs through standard `unittest` discovery
- Nested module `.env` files are explicitly ignored

## [0.4.0]

### Added
- Initial Docker media stack
- Windscribe VPN via Gluetun
- qBittorrent routed through VPN
- Sonarr/Radarr connected to qBittorrent
- Homepage dashboard
- Environment template
- Configuration documentation

## [0.5.0]

### Added

- Atlas Retention Intelligence (ARI)
- Immutable operational snapshots
- Shared Atlas configuration
- Jellyfin server integration
- Jellyfin library discovery
- Jellyfin user discovery
- Library validation
- Library path validation
- Human-readable ARI reporting

### Improved

- Configuration centralization
- Validation framework
- Runtime state separation
- Snapshot schema

# Changelog

## [0.9.0] — Operational Intelligence

### Added

- Atlas Retention Intelligence (ARI)
- Immutable historical snapshots
- Shared configuration architecture
- Jellyfin server adapter
- Jellyfin library adapter
- Jellyfin user adapter
- Jellyfin aggregate metrics
- Human-readable operational reports
- Machine-readable snapshot schema
- Library validation
- Library path validation
- Filesystem ↔ Jellyfin synchronization analysis
- Historical snapshot comparison
- Operational change summaries
- Byte-accurate storage metrics

### Improved

- ARI script organization
- Snapshot schema
- Report formatting
- Documentation

# v1.0.0

## 🚀 Major Features

### Atlas Retention Intelligence (ARI)

- Added Health Engine
- Added Analytics Engine
- Added Forecast Engine
- Added Recommendation Engine

### Health

- Health scoring
- Platform checks
- Media checks
- Intelligence checks

### Forecasting

- Daily storage growth
- Time-normalized forecasting
- 30-day projection
- Estimated storage exhaustion
- Forecast confidence

### Recommendations

- Storage recommendations
- Health recommendations
- Forecast recommendations

### Infrastructure

- Improved CLI
- Enhanced validation
- Runtime state management

- Expanded the Health Engine with infrastructure, service, storage, project, and Git diagnostics.
- Migrated `atlas doctor` to the shared Health Engine text renderer.

### M-018.3 — Module Health Integration

- Added automatic discovery of enabled module health providers.
- Added a normalized JSON health-provider contract for Atlas modules.
- Added Sports runtime health reporting for containers, heartbeat, providers, and endpoint reachability.
- Added Core tests for enabled, disabled, and malformed module health providers.

### M-019.1 — Scheduler Core Management

- Expanded persistent scheduler records with task definitions, execution counters, descriptions, callbacks, module ownership, enablement, and timing metadata.
- Added scheduler task registration, inspection, listing, and removal through the Atlas CLI.
- Preserved compatibility with existing interval and lifecycle callers while adding stored-interval scheduling.
