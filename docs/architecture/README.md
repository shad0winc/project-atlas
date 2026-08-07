# Project Atlas Architecture

This directory contains stable architecture documents for mature Project Atlas
subsystems. These documents explain how a subsystem is structured, which
contracts it owns, why its boundaries exist, and how future interfaces should
consume it.

Architecture documents are living specifications. They are intentionally
separate from sprint history, release notes, and future planning.

## Documentation Responsibilities

- `ROADMAP.md` describes planned and remaining work.
- `CHANGELOG.md` records user-visible and operator-visible changes.
- `docs/BUILD_LOG.md` records implementation history and validation evidence.
- `docs/architecture/*.md` describes stable subsystem design and contracts.
- `docs/ADR/` records architectural decisions and their rationale.
- `docs/EDR/` records engineering decisions and implementation constraints.

## Atlas Structure

```text
Project Atlas
├── Core domains
│   ├── Identity and authorization
│   ├── Service Lifecycle
│   │   ├── Startup Policy
│   │   ├── Restart Recovery
│   │   ├── Service Dependency Verification
│   │   └── Stale-State Recovery
│   ├── Health and observability
│   ├── Policy, retention, and cleanup
│   ├── Scheduler and events
│   │   └── Scheduler Recovery
│   ├── Media Requests
│   │   └── Interrupted-Request Recovery
│   └── Module platform
├── Providers and adapters
│   ├── Docker Compose
│   ├── Jellyfin
│   └── Future provider implementations
└── Interfaces
    ├── Atlas CLI
    ├── Atlas API
    └── Atlas Portal
```

Core domains own normalized contracts and business rules. Providers translate
external systems into those contracts. Interfaces consume the service layer and
must not bypass it to assemble provider-specific commands or duplicate domain
logic.

## Current Architecture Documents

- [Service Lifecycle](SERVICE_LIFECYCLE.md)
- [Startup Policy](STARTUP_POLICY.md)
- [Restart Recovery](RESTART_RECOVERY.md)
- [Service Dependency Verification](SERVICE_DEPENDENCY_VERIFICATION.md)
- [Stale-State Recovery](STALE_STATE_RECOVERY.md)
- [Scheduler Recovery](SCHEDULER_RECOVERY.md)
- [Interrupted-Request Recovery](INTERRUPTED_REQUEST_RECOVERY.md)
- [Sports Recovery](SPORTS_RECOVERY.md)
- [Automatic Cleanup Safety](AUTOMATIC_CLEANUP_SAFETY.md)
- [Storage Exhaustion Recovery](STORAGE_EXHAUSTION.md)
- [Portal](PORTAL.md)

Additional subsystem documents should be added only when their design is mature
enough to serve as a stable implementation and integration reference.

## Relationship to ADRs and EDRs

Architecture documents describe the current system. ADRs explain major design
choices. EDRs capture focused engineering constraints, implementation patterns,
or operational contracts. Architecture documents should link to relevant ADRs
and EDRs when those records are required to understand a boundary, but should not
copy their full history.

## Standard Engineering Workflow

Project Atlas milestones use this sequence:

1. Review the repository state and current contracts.
2. Design the smallest coherent feature increment.
3. Implement complete guarded source rewrites.
4. Run focused validation.
5. Run the full regression suite.
6. Perform live validation when applicable.
7. Update roadmap, changelog, and build history.
8. Update stable architecture documentation.
9. Review the complete diff and rollback path.
10. Commit and push.

## Engineering Principles

- Simplicity over complexity.
- Reliability over novelty.
- Observability before automation.
- Automation before repetitive manual intervention.
- Documentation as a first-class feature.
- Modular architecture and reusable Core services.
- Optional feature modules.
- User-first operation and presentation.
- Backups, verification, and rollback paths for production changes.

## Service Lifecycle

- [Architecture](SERVICE_LIFECYCLE.md)
- [CLI reference](../cli/SERVICE_LIFECYCLE.md)
- [Python API reference](../api/SERVICE_LIFECYCLE.md)

## Startup Policy

Startup Policy extends Service Lifecycle with deterministic,
provider-independent evaluation of service startup dependencies and readiness
contracts.

- [Architecture](STARTUP_POLICY.md)
- [CLI reference](../cli/SERVICE_LIFECYCLE.md)
- [Python API reference](../api/SERVICE_LIFECYCLE.md)
- [ADR 0011 — Startup Policy Readiness Contracts](../ADR/0011-startup-policy-readiness-contracts.md)

## Restart Recovery

Restart Recovery extends Service Lifecycle with deterministic comparison of
normalized before and after observations without executing restarts.

- [Architecture](RESTART_RECOVERY.md)
- [Service Lifecycle CLI reference](../cli/SERVICE_LIFECYCLE.md)
- [Python API reference](../api/SERVICE_LIFECYCLE.md)
- [ADR 0012 — Restart Recovery Observation Contracts](../ADR/0012-restart-recovery-observation-contracts.md)

## Service Dependency Verification

Service Dependency Verification hardens the existing Service Lifecycle graph
and preserves separate topology, operational-diagnosis, and startup-readiness
boundaries.

- [Architecture](SERVICE_DEPENDENCY_VERIFICATION.md)
- [Service Lifecycle CLI reference](../cli/SERVICE_LIFECYCLE.md)
- [Python API reference](../api/SERVICE_LIFECYCLE.md)
- [ADR 0013 — Dependency Verification Boundaries](../ADR/0013-dependency-verification-boundaries.md)

## Scheduler Recovery

Scheduler Recovery hardens the shared scheduler's process-interruption and
runtime-lock behavior without introducing a second scheduling engine.

- [Architecture](SCHEDULER_RECOVERY.md)
- [ADR 0015 — Scheduler Recovery Boundaries](../ADR/0015-scheduler-recovery-boundaries.md)

## Interrupted-Request Recovery

Interrupted-Request Recovery extends the existing Media Requests state machine
with durable mutation intent so outcome-ambiguous provider operations fail
closed instead of being silently replayed.

- [Architecture](INTERRUPTED_REQUEST_RECOVERY.md)
- [ADR 0016 — Interrupted-Request Recovery Boundaries](../ADR/0016-interrupted-request-recovery-boundaries.md)


## Sports Recovery

Sports Recovery hardens the existing optional Sports recorder so process
adoption and termination require durable Linux process identity rather than PID
liveness alone.

- [Architecture](SPORTS_RECOVERY.md)
- [ADR 0017 — Sports Recorder Process Identity](../ADR/0017-sports-recorder-process-identity.md)


## Automatic Cleanup Safety

Automatic Cleanup Safety separates retention recommendations from destructive
authorization and keeps the v1.0 cleanup execution boundary fail closed and
non-destructive while cross-boundary safeguards are verified.

- [Architecture](AUTOMATIC_CLEANUP_SAFETY.md)
- [ADR 0018 — Cleanup Mutation Authorization](../ADR/0018-cleanup-mutation-authorization.md)

## VPN Fail-Closed Verification

VPN Fail-Closed Verification separates healthy-path VPN readiness from proof
that qBittorrent has no non-VPN fallback when the tunnel is unavailable.

- [Architecture](VPN_FAIL_CLOSED.md)
- [ADR 0019 — VPN Fail-Closed Enforcement Boundaries](../ADR/0019-vpn-fail-closed-enforcement-boundaries.md)

## Storage Exhaustion Recovery

Storage Exhaustion Recovery defines how Atlas preserves durable state,
contains external side effects, and rejects partial success when persistence
fails because storage capacity is exhausted.

- [Architecture](STORAGE_EXHAUSTION.md)
- [ADR 0020 — Storage Exhaustion Failure Boundaries](../ADR/0020-storage-exhaustion-failure-boundaries.md)
