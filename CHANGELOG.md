# Changelog

## [Unreleased]

### Added

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
