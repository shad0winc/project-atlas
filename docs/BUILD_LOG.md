# Project Atlas Build Log

This document records the major engineering milestones completed during the development of Project Atlas.

---

# 2026-07-03

## M-001 — Platform Foundation

### Objective

Build the core infrastructure required to host Project Atlas.

### Completed

- Created Debian Docker LXC on Proxmox
- Mounted dedicated media storage
- Installed Docker and Docker Compose
- Deployed the initial Project Atlas stack
- Configured Gluetun with Windscribe VPN
- Routed qBittorrent through the VPN
- Connected Sonarr and Radarr to qBittorrent
- Created environment template and configuration documentation

### Verification

- Docker stack healthy
- Jellyfin operational
- Homepage operational
- VPN verified
- Sonarr/Radarr download tests passed

### Result

Project Atlas infrastructure operational.

---

## M-002 — Anime Expansion

### Objective

Separate anime management from standard media libraries.

### Completed

- Added Sonarr Anime
- Added Radarr Anime
- Added Anime TV library
- Added Anime Movies library
- Added anime download categories
- Connected all Arr applications to Prowlarr
- Simplified Docker startup dependencies
- Added Project Atlas Maturity Model

### Engineering Decisions

- Runtime resilience over startup ordering
- Dedicated anime management workflow

### Result

Anime is now independently managed while remaining fully integrated into Atlas.

---

## M-003 — Media Quality Intelligence

### Objective

Centralize media quality management.

### Completed

- Added Recyclarr
- Integrated TRaSH Guides
- Imported Custom Formats
- Updated Quality Definitions
- Implemented version-controlled quality profiles

### Result

Media quality standards are now centrally managed and reproducible.

---

## M-004 — Media Platform Integration

### Objective

Complete the media acquisition platform.

### Completed

- Configured Jellyfin libraries
- Integrated Jellyseerr
- Configured Movies
- Configured TV
- Configured Anime Movies
- Configured Anime TV
- Added dedicated anime root folders
- Verified Prowlarr synchronization

### Result

The complete media platform became operational.

---

# 2026-07-05

## M-008 — Atlas Retention Intelligence Foundation

### Objective

Create the intelligence layer for Atlas.

### Completed

- Shared configuration framework
- Immutable snapshot architecture
- Historical snapshot storage
- Jellyfin server adapter
- Jellyfin library adapter
- Jellyfin user adapter
- Library validation
- Library path validation
- Human-readable reporting
- Configuration-driven validation

### Result

ARI became the centralized operational reporting system for Atlas.

---

## M-009 — Operational Intelligence

### Objective

Introduce historical analysis and operational awareness.

### Completed

- Jellyfin aggregate metrics
- User inventory
- Library synchronization validation
- Historical snapshot comparison
- Operational summaries
- Byte-accurate storage metrics
- ARI functional refactor

### Result

Atlas gained historical operational visibility.

---

# 2026-07-07

## M-010 — Health Engine

### Objective

Measure the operational health of Atlas.

### Completed

- Health scoring
- Platform validation
- Media validation
- Docker validation
- VPN validation
- Storage validation
- Snapshot freshness monitoring
- Categorized health reporting

### Result

ARI can now evaluate overall platform health.

---

## M-011 — Analytics Engine

### Objective

Transform snapshots into operational metrics.

### Completed

- Historical storage trends
- Library growth analysis
- Metric helper framework
- Historical averages
- Minimum/maximum tracking
- Trend analysis

### Result

Atlas now understands historical behavior instead of simply reporting snapshots.

---

## M-012 — Forecast Engine

### Objective

Predict future storage usage.

### Completed

- Time-normalized growth calculations
- Average daily growth
- 30-day projection
- Days remaining estimation
- Estimated storage exhaustion date
- Forecast confidence

### Result

ARI now performs predictive capacity planning.

---

## M-013 — Recommendation Engine

### Objective

Provide operational guidance based on system state.

### Completed

- Runtime state framework
- Recommendation engine
- Health recommendations
- Capacity recommendations
- Forecast recommendations

### Result

Atlas now provides actionable operational guidance instead of reporting alone.

---

# Current Status

**Version:** 1.0.0

**Development State:** Production Ready

## Platform Capabilities

- Production media platform
- Operational CLI
- Health monitoring
- Historical analytics
- Capacity forecasting
- Operational recommendations

## Next Milestone

**M-014 — Documentation & Release Preparation**
---

## Atlas Core Event Publisher Consolidation

### Completed

- Added `atlas/events.py` as the shared Python interface for module event publishing.
- Preserved the Atlas CLI as the authority for event declaration validation, durable event storage, and subscriber delivery.
- Removed duplicate Sports event publisher implementations from the worker and controller.
- Converted Core scheduler checks into discoverable `unittest` tests.
- Added Core event publisher tests covering command construction, payload serialization, input validation, and CLI failure propagation.
- Updated `.gitignore` to exclude nested module `.env` files.

### Validation

```bash
python3 -m compileall -q atlas modules/sports/src tests
python3 -m unittest discover -s tests -p 'test_*.py' -v
```

Result: eight Core tests passed.



## Unified Atlas Test Command

- Added `atlas test` with `all`, `core`, and `sports` scopes.
- Core validation runs compilation and discoverable unit tests.
- Sports validation runs the complete module integration suite.
- Verified eight Core tests and five Sports integration suites pass.

## M-018.1 — Health Engine Foundation

### Completed

- Added `atlas/health.py` with normalized health statuses, checks, reports, scoring, and JSON serialization.
- Added foundational Core checks for the Python runtime, Atlas project directory, and Atlas configuration.
- Added `atlas health` with formatted and compact JSON output.
- Added shared shell helpers for emitting normalized health-check results.
- Added Core unit tests for health validation, aggregation, scoring, serialization, and foundational collection.

### Scope

Existing `status`, `services`, `verify`, and `doctor` behavior remains unchanged. Migration to the shared engine is deferred to later M-018 sections.

## 2026-07-19 — M-018.2 Health diagnostics migration

- Added shared operational collectors to `atlas.health`.
- Migrated `atlas doctor` to render the Health Engine report.
- Preserved `atlas verify` and `atlas services` for the next migration section.

## M-018.3 — Module Health Integration

Atlas Health Engine now discovers health providers under `modules/<module>/scripts/health.py`
or `health.sh` for enabled modules. Provider output is normalized into Core `HealthCheck`
objects and appears automatically in both `atlas health` and `atlas doctor`. Sports is the
first module implementation and reports container state, controller heartbeat freshness,
provider health, and endpoint availability without introducing Sports-specific logic into Core.

## M-019.1 — Scheduler Core Management

Atlas now exposes its existing persistent interval scheduler as a first-class Core subsystem.
Tasks carry durable definitions and runtime metadata, including callback, interval, module,
enablement, run counts, failure counts, last duration, due state, and next-run time. The CLI
supports registering, listing, inspecting, and removing tasks. Execution remains manually
invoked and is deferred to M-019.2.
### M-019.2 — Scheduler Runtime

- Added deterministic one-shot execution for due and explicitly named scheduler tasks.
- Added shell-free callback parsing, execution timing, success/failure counters, bounded history, runtime locking, stale-lock recovery, and best-effort module event publication.
- Added CLI commands for run, dry-run, and execution history.
- Added scheduler runtime tests for success, failure, due selection, dry runs, history limits, event isolation, and overlap protection.

## M-019.3 — Module Scheduler API

- Added optional `modules/<module>/scheduler.json` manifests.
- Added enabled-module discovery and scheduler task reconciliation.
- Added callback containment validation and stale module task cleanup.
- Added `atlas scheduler sync [module]` and focused module scheduler tests.

## M-019.4 — Module Command Interface

- Added declarative `commands.json` manifests for module-owned commands.
- Added safe command discovery and execution through `atlas module commands` and `atlas module exec`.
- Enforced enabled-module checks, callback containment, command allowlisting, and exit-code propagation.
- Added the Sports module as the reference command-manifest implementation while preserving its existing CLI shortcut.

## M-019.5 — Sports Scheduler Integration

- Added the Sports `scheduler.json` manifest for hourly maintenance.
- Added an allowlisted `maintenance` module command using the existing maintenance implementation.
- Added a scheduler callback that delegates through the Atlas Module Command Interface.
- Removed the private Sports `TaskScheduler` and maintenance timing state from `worker.py`.
- Added tests confirming the Sports scheduler contract and removal of duplicate scheduling logic.

## M-020.1 — User Identity and Profile Framework

- Added durable Atlas user profiles under the shared runtime configuration root.
- Added normalized usernames, optional personal profile fields, roles, account status, and Jellyfin user linkage.
- Added atomic registry and profile writes with schema validation and duplicate username/email protection.
- Added `atlas users` and `atlas user` commands for creation, inspection, updates, enable/disable, Jellyfin linking, and verification.
- Added focused Core tests for profile storage, validation, registry consistency, and CLI lifecycle operations.
- Passwords remain owned by Jellyfin and are not stored by Atlas.
