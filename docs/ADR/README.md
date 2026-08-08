# Atlas Architecture Decision Records (ADRs)

## Purpose

Architecture Decision Records (ADRs) document significant architectural and
technical decisions made throughout the development of Project Atlas.

Each ADR captures:

- The problem being solved.
- The decision that was made.
- Alternatives that were considered.
- The long-term consequences of the decision.

Together, the ADRs provide the architectural history of the project.

## Naming Convention

Project Atlas currently contains ADRs from two documentation eras.

### Legacy Format

Early ADRs use the original naming convention:

    ADR-0001-...
    ADR-0002-...
    ADR-0003-...

These files are intentionally retained unchanged to preserve repository
history and existing references.

### Current Format

Beginning with ADR 0008, Atlas adopts the simplified naming convention:

    0008-description.md
    0009-description.md
    0010-description.md

All new ADRs must follow this format.

## Documentation Hierarchy

The documentation is organized as follows:

- docs/ADR
    Records why architectural decisions were made.

- docs/architecture
    Describes how Atlas is currently designed.

ADRs explain the reasoning behind architectural decisions, while the
architecture documents describe the current implementation.

## Status

Both naming conventions are considered valid historical records.

The simplified numeric format is the project standard for all future ADRs.

## Current Decision Index

- [ADR 0010 — Service Lifecycle Architecture](0010-service-lifecycle-architecture.md)
- [ADR 0011 — Startup Policy Readiness Contracts](0011-startup-policy-readiness-contracts.md)
- [ADR 0012 — Restart Recovery Observation Contracts](0012-restart-recovery-observation-contracts.md)
- [ADR 0013 — Dependency Verification Boundaries](0013-dependency-verification-boundaries.md)
- [ADR 0014 — Stale Runtime State Normalization](0014-stale-runtime-state-normalization.md)
- [ADR 0015 — Scheduler Recovery Boundaries](0015-scheduler-recovery-boundaries.md)
- [ADR 0016 — Interrupted-Request Recovery Boundaries](0016-interrupted-request-recovery-boundaries.md)
- [ADR 0017 — Sports Recorder Process Identity](0017-sports-recorder-process-identity.md)
- [ADR 0018 — Cleanup Mutation Authorization](0018-cleanup-mutation-authorization.md)
- [ADR 0019 — VPN Fail-Closed Enforcement Boundaries](0019-vpn-fail-closed-enforcement-boundaries.md)
- [ADR 0020 — Storage Exhaustion Failure Boundaries](0020-storage-exhaustion-failure-boundaries.md)
- [ADR 0021 — Unavailable Provider Failure Semantics](0021-unavailable-provider-failure-semantics.md)
- [ADR 0022 — Production Deployment Safety Boundaries](0022-production-deployment-safety-boundaries.md)
- [ADR 0023 — Backup and Restore Recovery Boundaries](0023-backup-restore-recovery-boundaries.md)
