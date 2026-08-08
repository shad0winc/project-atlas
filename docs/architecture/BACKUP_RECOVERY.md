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
| Deployment records | Atlas deployment directory | audit evidence |
| Process locks | runtime lock paths | transient; never restored as ownership |
| Media libraries | media storage | outside Atlas backup scope |

Media requests store durable data in `<repository-root>/requests.json`; the
root is caller-injected. M-023.25 must resolve and declare the canonical
production repository root before request-state coverage is marked complete.

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

## Retention State

ARI observations and retention-related state live under `ATLAS_ARI_DIR`.
M-023.25 must prove that the selected state can be restored and consumed; it
must not equate backing up retention Python code with protecting runtime state.

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

Read-only operations include:

```text
atlas backup --list
atlas backup --help
atlas restore inspect <archive>
atlas restore verify <archive>
```

Unknown arguments fail without creating a partial archive, publishing a final
archive, or invoking retention. Restore apply is introduced only after staged
validation is implemented and tested.

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

For every roadmap surface, tests will create representative state, create and
validate a recovery-capable backup, restore it into an empty isolated root,
load/validate the restored state, and compare authoritative state with its
source. Production is not modified by this proof.

## Controlled Production Proof

Only after isolated restore and failure-boundary tests pass may M-023.25 perform
a bounded production recovery validation. It must begin and end with certified
source, clean Git, a verified deployment baseline, known maintenance state, and
successful Doctor/specialized verification.

## Recovery-Time Expectations

M-023.25 will measure archive validation, isolated restore, live state apply,
service verification, and total operator recovery time. These are expectations
for the tested single-host topology, not universal guarantees.

## Single-Host Limitation

`/mnt/storage/backups/atlas` resides in the same host/storage domain as Atlas.
Local archives therefore do not protect against loss of that storage device,
filesystem, or host. Operator documentation must recommend copying validated
recovery archives to an independent storage domain.

## Out of Scope

M-023.25 does not claim media-library backup, complete third-party Docker-volume
recovery, encrypted off-host transport, multi-host failover, or restoration of
host-specific Docker images from deployment metadata.

## Implementation Sequence

1. architecture and ADR;
2. recovery manifest and fail-closed CLI semantics;
3. state-complete backup collection;
4. staged validation-first restore;
5. deterministic isolated restore testing;
6. controlled production recovery validation; and
7. documentation reconciliation and roadmap completion.

Roadmap items remain unchecked until their corresponding behavior is proved.
