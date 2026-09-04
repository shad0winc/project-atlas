# Backup and Recovery Architecture

## Purpose

This document defines the Project Atlas v1.0 backup and restore architecture.
It separates configuration archiving, authoritative runtime-state protection,
restore validation, live mutation, deployment rollback, and disaster-recovery
claims.

## Safety Invariants

> A backup is not recoverable merely because an archive exists. Atlas must
> explicitly identify, protect, validate, and successfully restore every
> authoritative state surface that it claims before that backup can be
> considered recovery-capable.

> No unvalidated backup content may be extracted directly over live production
> state.

## Discovery Baseline

M-023.25 began from certified production source commit `1956e3a6`.

The existing backup already provides useful safety properties: `.partial`
creation, tar validation before publication, atomic final rename, cleanup on
failure, and retention limited to canonical archives. Those contracts remain.

Discovery also proved that existing archives are project-tree configuration
archives rather than state-complete recovery archives. Authoritative runtime
state exists outside the project tree.

## Current State Map

| Surface | Production ownership | Classification |
| --- | --- | --- |
| Project configuration | repository-managed `config/` and declared files | authoritative configuration |
| Atlas users | `ATLAS_USERS_DIR` | authoritative |
| Identity/invitations | `ATLAS_IDENTITY_DIR` | authoritative |
| Favorites | `ATLAS_IDENTITY_DIR/favorites` | authoritative |
| Media requests | configured `JsonMediaRequestRepository` root | authoritative |
| Scheduler | `ATLAS_SCHEDULER_STATE_FILE` | authoritative |
| Event/subscriber state | `ATLAS_RUNTIME_CONFIG_DIR/runtime` | consistency-sensitive |
| ARI/retention | `ATLAS_ARI_DIR` | recovery state |
| Sports subscriptions | configured Sports state | authoritative |
| Sports recordings | configured Sports recordings file | authoritative |
| Sports task scheduler | Atlas runtime scheduler state | authoritative |
| Sports health/heartbeat/output | Sports runtime directories | reconstructible |
| Dispatcharr state | `/mnt/storage/configs/dispatcharr` | authoritative third-party backend state |
| Teamarr state | `/mnt/storage/configs/teamarr` | authoritative third-party backend state |
| Deployment records | Atlas deployment directory | audit evidence |
| Process locks | runtime lock paths | transient; never restored as ownership |
| Media libraries | media storage | outside Atlas backup scope |

Media requests store durable data in `<repository-root>/requests.json`; the
root is caller-injected. M-023.25 established the canonical production root as
`ATLAS_REQUESTS_DIR=${ATLAS_RUNTIME_CONFIG_DIR}/requests` and treats the
`requests.json` surface as explicitly optional when no request registry exists.

## Recovery-Capable Archive

A v1.0 recovery-capable backup extends the existing publication model with
explicit recovery metadata. Its logical layout is:

```text
BACKUP_INFO.txt
RECOVERY_FORMAT
RECOVERY_MANIFEST.tsv
SHA256SUMS
<declared project configuration>
state/
  users/
  identity/
  requests/
  scheduler/
  runtime/
  retention/
  sports/
```

`RECOVERY_FORMAT` identifies the format independently from the application
version. `RECOVERY_MANIFEST.tsv` declares state ownership and restore policy.
`SHA256SUMS` supplies content integrity for recovery-critical members.

Successful `tar -tzf` proves archive readability; it does not prove recovery
integrity or state completeness.

## Legacy Backups

Pre-M-023.25 archives remain historical configuration backups. They may be
inspected, but Atlas must not report them as state-complete or allow them to
cross the automated live-restore boundary.

## State Inclusion Policy

Collection is allowlist-driven. Every restorable surface requires:

1. an authoritative source path;
2. a stable archive-relative path;
3. required/optional semantics;
4. validation rules;
5. checksum coverage; and
6. an approved restore destination.

## Sports State

Sports combines valuable and disposable runtime material. Subscriptions,
recording metadata, and task-scheduler state are recovery-critical. Provider
health, controller heartbeat, generated M3U/XMLTV output, and routine logs are
reconstructible and should not become authoritative simply because they share
the `sportyfin` root.

## Sports Backend State

Teamarr and Dispatcharr are private infrastructure services behind Atlas Sports.
Their application state is persistent and must not be inferred from generated
M3U/XMLTV output.

The authoritative runtime roots are:

- `/mnt/storage/configs/dispatcharr`
- `/mnt/storage/configs/teamarr`

These roots may contain credentials or other sensitive configuration. Backup
collection must therefore use explicit allowlisted state handling rather than
incidental recursive capture, and backup diagnostics must never print their
secret-bearing contents.

Atlas end-user identities are not provisioned in either backend. Atlas remains
the user authority and retains the permanent Atlas-to-Jellyfin user linkage.

## Retention State

ARI observations and retention-related state live under `ATLAS_ARI_DIR`.
M-023.25 proved staged and live consumption of the selected state. The
validator follows ARI history compatibility semantics, accepting compatible
reports while skipping recorded legacy/incompatible history rather than
misclassifying old schema as current-state corruption.

## Event and Subscriber State

Event history and subscriber cursors are consistency-sensitive and must be
captured/restored as a compatible unit. A cursor without its corresponding
event history can skip work; event history with incompatible cursors can replay
work.

## Deployment Recovery Evidence

Deployment records are valuable audit material, but host-specific Docker image
IDs and paths are not portable rollback capability. After host recovery Atlas
must establish a new verified production baseline. Locks and maintenance
ownership are never restored merely because captured files once existed.

## Sensitive Configuration

Discovery found recursive module capture includes module `.env` files while
current canonical archives are mode `0644`.

Recovery-capable backups must explicitly declare any required secret-bearing
files, protect partial and final artifacts with owner-only permissions, avoid
secrets in manifests/diagnostics, and avoid acquiring secrets incidentally via
recursive directory capture. Existing historical archives are not rewritten.

## CLI Contract

Read-only backup/restore operations include:

```text
atlas backup --list
atlas backup --help
atlas restore inspect <archive>
atlas restore verify <archive>
atlas restore validate-stage <staging-root>
atlas restore plan <staging-root>
```

Isolated `atlas restore stage <archive>` writes only to a private temporary
staging root. Live mutation is separately authorized through:

```text
atlas restore apply <staging-root> --confirm-live
atlas restore resume <restore-id> --confirm-live
atlas restore abort <restore-id> --confirm-live
```

Unknown arguments fail without creating a partial archive, publishing a final
archive, invoking retention, or mutating live state. Production apply also
requires clean certified `main` equal to `origin/main`, a verified deployment
baseline, shared-lock ownership, and successful staged validation.

## Backup Transaction

```text
resolve declared state
        |
        v
create protected partial archive
        |
        v
validate archive + manifest + checksums
        |
        v
atomically publish canonical archive
        |
        v
apply explicit retention
```

No retention runs after failed creation or recovery validation.

## Restore Transaction

Before production mutation, restore performs archive identification, isolated
staging, format/path/checksum validation, state-contract validation, and an
operator-visible restore plan. None of those steps may mutate live state.

Live apply then requires mutual exclusion with deployments, a pre-restore
recovery point, maintenance when user-visible services are affected, quiesced
writers, bounded state replacement, consumer restart/reload where required,
and post-restore verification. Maintenance is removed only after verification
succeeds.

## Path Safety

Restore rejects absolute paths, `..` traversal, unexpected symbolic-link
targets, undeclared recovery members, and destinations outside approved Atlas
roots. Extraction always occurs into isolated staging before live replacement.

## Isolated Restore Proof

Representative tests create state, validate recovery-capable archives, stage
them into isolated roots, load the result through real Atlas consumers, and
prove staged and live state remain unchanged during validation. Path traversal,
symbolic links, missing required state, checksum damage, and transactional
mid-apply failure all have explicit regression coverage.

## Controlled Production Proof

M-023.25 performed the bounded production validation only after isolated and
failure-boundary tests passed. Protected source `483085fa` captured a fresh
current-state archive, staged and consumer-validated it, and completed restore
`restore-20260808T174153Z-3004055`. The API, Sports controller, and Notifications
writer were observably restarted and healthy. Final Atlas Health was 100
percent; normal public ingress passed 24/24; maintenance was disabled; the
shared lock was absent; and the verified deployment baseline remained current.

## Recovery-Time Expectations

The controlled restore began with transaction timestamp 17:41:53 UTC and all
three controlled writers had restarted at 17:43:02 UTC, approximately 69
seconds to writer restart. Full health, module, and ingress verification
completed immediately afterward. This is single-host evidence rather than an
SLO; operators should reserve at least a 5-10 minute maintenance window and
scale that allowance with state size and verification cost.

## Single-Host Limitation

`/mnt/storage/backups/atlas` resides in the same host/storage domain as Atlas.
Local archives therefore do not protect against loss of that storage device,
filesystem, or host. Operator documentation must recommend copying validated
recovery archives to an independent storage domain.

## Out of Scope

M-023.25 does not claim media-library backup, complete third-party Docker-volume
recovery, encrypted off-host transport, multi-host failover, or restoration of
host-specific Docker images from deployment metadata.

## Implementation Status

M-023.25 is complete. The implementation progressed through architecture,
versioned recovery metadata, canonical state ownership, consistency-aware
snapshotting, state-complete archive validation, read-only restore inspection,
isolated staging, consumer validation, restore planning, bounded transactional
replacement, fail-closed live orchestration, protected release promotion, and
controlled production recovery before documentation reconciliation.

The final Core regression passed 2,947 tests plus 104 subtests before protected
promotion through `feature/backup-recovery -> release/v1.0.0 -> main`. The
certified feature, release merge, and production merge were `02738ee3`,
`c8a947c0`, and `483085fa` respectively.

Every Backup and Recovery roadmap item is now backed by implementation,
automated regression, controlled runtime evidence, and an explicit scope
statement.

## Sports Backend Application-Consistent Recovery

The Teamarr and Dispatcharr databases are not ordinary filesystem replacement
surfaces.

Atlas Sports backend recovery uses application-consistent artifacts:

- Dispatcharr PostgreSQL state is captured as a PostgreSQL custom-format
  logical dump using Dispatcharr's pinned backup implementation;
- Dispatcharr persistent `jwt` identity is captured separately;
- Teamarr SQLite state is captured through `sqlite3.Connection.backup()`.

Atlas must not archive the live Dispatcharr PostgreSQL cluster or Teamarr
`-wal` / `-shm` files as its application-consistent database representation.

These artifacts belong to recovery format 2 under `backend-recovery/`. They
remain separate from the canonical twelve filesystem replacement surfaces.

Recovery format 2 may be verified and staged only until native backend restore
orchestration is implemented. Live application must fail closed before
maintenance, writer shutdown, or state mutation unless Teamarr and Dispatcharr
native restore, quiescing, rollback, restart, and consumer verification are all
covered by the recovery transaction.

Recovery format 1 remains the historical twelve-surface filesystem recovery
format and remains supported.
