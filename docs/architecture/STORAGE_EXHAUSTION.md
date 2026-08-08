# Storage Exhaustion Recovery Architecture

## Purpose

This document defines how Project Atlas observes, contains, reports, and
recovers from storage exhaustion without corrupting durable state or creating
unsafe external side effects.

M-023.22 verifies failure behavior. It does not create artificial pressure on
the production media filesystem.

## Safety Invariant

> Storage exhaustion must not corrupt the last durable state, create an
> untracked external operation, or present a partial artifact as successful.

Storage availability is a prerequisite for durable mutation, not permission to
delete data.

## Current Production Storage

Discovery at commit `a8326e93` established:

- `/mnt/storage` is an `ext4` filesystem mounted read/write from `/dev/sda1`;
- total filesystem size is approximately 1.92 TB in `df` 1K blocks;
- approximately 1.82 TB was available during discovery;
- reported utilization was 1 percent;
- Atlas configuration, Media, downloads, and backup directories were present;
  and
- the repository was clean and synchronized with
  `origin/feature/public-ingress`.

Production is therefore suitable for read-only capacity validation, not a
real fill-to-exhaustion experiment.

## Storage States

### Healthy

The path exists, required access is available, capacity observation succeeds,
and free capacity is above the configured warning threshold.

### Low capacity

The filesystem remains usable, but free capacity is at or below a configured
operational warning boundary.

Low capacity is degraded state. It should be visible before automation is
affected.

### Exhausted

A required persistence operation fails with `errno.ENOSPC`, or trusted capacity
observation establishes that no usable free capacity remains.

Exhaustion means the requested durable mutation failed. Code must not infer
success from an in-memory state transition.

### Unknown

Atlas cannot inspect the filesystem, determine capacity, or establish the
write boundary reliably.

Unknown is not healthy and must not be silently normalized to exhausted.

## Existing Foundations

### Core atomic state

`atlas.atomic.write_text_atomic()` and `write_json_atomic()` write replacement
content to a same-directory temporary path before replacing the committed
target.

This is the correct Core primitive for state integrity. M-023.22 must verify
its `ENOSPC` behavior explicitly rather than replace it.

### Operations reports

`FileOperationsRepository` writes immutable snapshots and then updates
`latest.json` through the shared atomic helper. It already distinguishes
snapshot failure from a failure to update the latest pointer.

The immutable snapshot must remain valid even when a later latest-pointer write
fails.

### Media Requests

`JsonMediaRequestRepository` uses the shared atomic JSON writer. Media Request
orchestration also persists `submitting` and `cancelling` intent before provider
mutation.

Storage exhaustion before intent persistence must prevent the provider call.
Raw filesystem failure should be normalized through the repository and service
error boundaries.

### Scheduler state

The shared scheduler persists state through `atlas.state.save_json()`, which
uses the Core atomic helper. Its runtime lock is also stored on the configured
state filesystem.

Storage failure must remain explicit. A failed state write must not be treated
as a successfully persisted execution result.

### Sports

Sports already measures filesystem capacity with `shutil.disk_usage()` and
exposes `free_bytes`, `percent_free`, and a configurable low-space warning
threshold through structured health.

Sports recording state currently uses a temporary-file-and-replace pattern.
The recorder also has an important side-effect boundary: a recording process
may be launched immediately before its PID and Linux process start-time identity
are persisted.

If that final persistence fails, Atlas must not leave a newly started process
untracked. Compensation may stop only the process identity returned by the
launch and must retain the PID-reuse protections established by ADR 0017.

### Backups

The supported Atlas backup command writes archives beneath the configured
backup directory. A storage failure during archive creation must not leave a
partial file carrying the same success naming contract as a completed backup.

Retention must operate on completed backups only.

### Cleanup

Atlas cleanup remains dry-run-only for destructive provider behavior, and ADR
0018 requires fresh authorization at a future destructive mutation boundary.

Storage exhaustion does not weaken those rules. Capacity pressure must never
be translated into implicit Media deletion.

## Failure-Containment Rules

### Rule 1 — preserve last durable state

If a replacement write fails before atomic replacement, the previously
committed target remains authoritative.

Tests should verify both file content and temporary-artifact cleanup.

### Rule 2 — persistence failure is not success

An in-memory object is not durable evidence. Repository, scheduler, request,
recording, health, and backup code must return or raise failure when required
persistence cannot complete.

### Rule 3 — durable intent precedes external mutation

Provider mutations require persisted intent first. Existing interrupted-request
recovery already follows this rule.

Where an external process must be started before its final process identity is
known, failure to persist that identity requires exact-identity compensation.

### Rule 4 — partial artifacts are not valid artifacts

Backups and similar complete-file products use a temporary or partial identity
until creation succeeds. Only successful completion may expose the canonical
final name.

### Rule 5 — observation does not authorize deletion

Low-space, exhausted, and unknown storage states may generate health findings,
operator attention, or blocked mutations. They never bypass retention,
favorite protection, cleanup authorization, or audit requirements.

## Error Semantics

`errno.ENOSPC` is storage exhaustion evidence at the failed persistence
boundary.

Other errors remain distinct:

- `EACCES` and `EPERM` indicate access/permission failure;
- `EROFS` indicates a read-only filesystem;
- missing paths are path/configuration failures; and
- inspection failure is unknown unless the underlying error proves a more
  specific state.

Atlas should preserve these distinctions in causal exception chains even when
subsystems expose a normalized domain error to callers.

## Test Strategy

M-023.22 verification is layered.

### 1. Atomic persistence

Inject `OSError(errno.ENOSPC, ...)` during the temporary write and prove:

- the committed file is unchanged;
- no partial replacement becomes authoritative;
- temporary state is removed when safe; and
- the exception remains observable.

### 2. Core repository and orchestration boundaries

Prove Operations and Media Request persistence surface domain-level failure and
that provider mutation is blocked when intent cannot be persisted.

### 3. Sports external-process boundary

Simulate post-launch state persistence failure with a controlled fake recorder.
Prove the exact launched process identity is compensated and no ambiguous
process is signaled.

### 4. Backup artifact boundary

Simulate archive creation failure and prove the canonical completed-backup name
is not published or retained.

### 5. Production observation

Production validation is read-only:

- confirm the real storage mount and capacity;
- confirm required Atlas storage roots remain present and writable;
- inspect existing health/capacity reporting;
- run the relevant regression suites; and
- verify a clean repository before and after observation.

## Why Production Is Not Filled

Filling `/mnt/storage` would risk active downloads, Media writes, Sports
recordings, state persistence, backups, container behavior, and filesystem
recovery. It would test many uncontrolled failure paths at once.

Deterministic `ENOSPC` injection provides stronger evidence for the Atlas-owned
code paths because the exact failing write is known and assertions can inspect
the last durable state directly.

## Recovery

Atlas does not automatically reclaim user data to recover from storage
exhaustion.

Operational recovery is:

1. report or surface the capacity/persistence failure;
2. stop or compensate any newly created external operation whose durable
   identity could not be committed;
3. preserve the last valid state and incomplete artifacts as non-successful;
4. have an operator restore usable capacity through an authorized action; and
5. retry only through the owning subsystem's normal guarded workflow.

## Scope Boundaries

M-023.22 does not:

- fill the production filesystem;
- add a second persistence framework;
- replace `atlas.atomic`;
- introduce filesystem quotas;
- change the production filesystem;
- add automatic Media deletion;
- enable destructive cleanup;
- introduce a new storage daemon; or
- perform a storage migration.

## Implementation Status

M-023.22 is complete.

The implemented and verified boundaries are:

- shared atomic persistence preserves the last durable state when a temporary
  write fails with `ENOSPC` and cleans partial temporary state when safe;
- Media Request registry writes normalize filesystem failures through the
  repository error contract, allowing orchestration to fail before provider
  mutation when durable intent cannot be recorded;
- Sports recording reconciliation tracks only recorders genuinely launched by
  the current pass and compensates failed registry persistence using the exact
  PID plus Linux process start-time identity returned by launch;
- already-running recorders adopted by reconciliation are not signaled as
  persistence compensation;
- `atlas backup` creates a same-directory `.partial` archive, validates it,
  and atomically publishes the canonical `.tar.gz` name only after success;
- backup listing and retention ignore partial artifacts; and
- production validation remains read-only and never fills the live filesystem.

### Validation Evidence

Automated milestone validation included:

- 139 focused atomic/persistence tests during Core hardening;
- 349 broader Media Request regressions;
- 42 Scheduler persistence regressions;
- 4 focused Sports storage-exhaustion tests;
- 4 focused backup storage-safety tests plus 21 Backup CLI regressions; and
- a final cross-boundary run of 189 storage-exhaustion regressions.

Read-only production validation at commit `c5c56992` observed:

- `/mnt/storage` total bytes: `1967846068224`;
- free bytes: `1864692621312`;
- free capacity: 94.76 percent;
- 10 canonical Atlas backup archives;
- zero partial Atlas backup artifacts;
- a valid newest canonical archive and non-empty `BACKUP_INFO.txt` manifest;
- zero persisted and zero active Sports recordings; and
- zero production storage-fill, backup, recorder, cleanup, and repository
  mutations.

### Commits

- `356049f6` — define storage-exhaustion failure boundaries and ADR 0020;
- `ca52c941` — fail closed on Core `ENOSPC` persistence;
- `da2f0318` — compensate Sports recorder launch on persistence failure; and
- `c5c56992` — publish Atlas backup archives transactionally.

The broader v1.0 Backup and Recovery work remains separate. M-023.22 proves
storage-exhaustion behavior and partial-artifact safety; it does not claim a
complete restore certification.

## Related Documents

- [ADR-0020: Storage Exhaustion Failure Boundaries](../ADR/0020-storage-exhaustion-failure-boundaries.md)
- [ADR-0016: Interrupted-Request Recovery Boundaries](../ADR/0016-interrupted-request-recovery-boundaries.md)
- [ADR-0017: Sports Recorder Process Identity](../ADR/0017-sports-recorder-process-identity.md)
- [ADR-0018: Cleanup Mutation Authorization](../ADR/0018-cleanup-mutation-authorization.md)
- [Automatic Cleanup Safety](AUTOMATIC_CLEANUP_SAFETY.md)
- [Sports Recovery](SPORTS_RECOVERY.md)
