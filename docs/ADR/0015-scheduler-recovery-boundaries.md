# ADR-0015: Scheduler Recovery Boundaries

## Status

Accepted

## Date

2026-08-05

## Context

Project Atlas already provides a persistent shared scheduler. `TaskScheduler`
stores task state atomically, serializes execution with a PID lock, records
task start and terminal outcomes, and bases interval eligibility on
`last_success`.

The existing implementation also attempts stale-lock recovery. A lock whose
PID no longer exists is safely reclaimable. However, empty, malformed, or
unreadable lock contents are currently treated as stale and removed.

Lock creation and PID writing are separate operations. A competing scheduler
can therefore theoretically observe a newly created lock before its PID has
been written. Automatically deleting an ambiguous lock can turn uncertainty
into concurrent execution.

An interrupted scheduler can also leave a task persisted as `running` without
a terminal outcome. Atlas needs explicit semantics for that state without
inventing a second recovery engine or claiming that an interrupted callback
either succeeded or failed beyond the evidence available.

## Decision

Atlas keeps `TaskScheduler` as the sole scheduler and recovery authority.

Scheduler lock ownership is fail-closed:

- a recorded live PID blocks execution;
- a PID that cannot safely be disproved as owner blocks execution;
- empty, malformed, or unreadable ownership blocks execution;
- a lock is reclaimed automatically only when its recorded PID is positively
  known not to exist.

Interrupted task recovery preserves scheduler facts:

- starting a task never advances `last_success`;
- interruption never creates synthetic success;
- normal due-state calculation continues to use the previous `last_success`;
- an already-due scheduled execution therefore remains eligible after
  interruption;
- the next completed execution owns the next `healthy` or `degraded` outcome.

Atlas does not add a second scheduler status store, stale-state TTL, watchdog,
or general recovery daemon for M-023.17.

## Delivery Guarantee

Atlas does not claim exactly-once scheduled callback execution.

If a scheduler process terminates after a callback has produced an external
side effect but before Atlas persists its outcome, the scheduler cannot infer
how much work completed. Normally due work may execute again after recovery.

Scheduled callbacks should therefore be repeat-safe or provide their own
idempotency protection where required.

## Consequences

Positive consequences:

- ambiguous ownership cannot silently create overlapping scheduler execution;
- provably dead scheduler processes remain automatically recoverable;
- interrupted work cannot be reported as successful without evidence;
- existing state, CLI, module, Operations, and Portal boundaries are preserved;
- recovery behavior can be proven without introducing another scheduler.

Tradeoffs:

- an empty, malformed, or unreadable lock requires explicit operator
  intervention rather than automatic deletion;
- a persisted `running` state can outlive the process that originally wrote it
  until another execution records a terminal outcome;
- repeated execution after an ambiguous callback interruption remains possible;
- callback-level idempotency remains the responsibility of the callback's
  owning domain.

## Non-Goals

This decision does not add automatic retry loops, lock timeouts, callback
compensation, exactly-once execution, a watchdog process, a new scheduler
model hierarchy, interrupted-request recovery, or Sports recorder recovery.
It does not authorize destructive production failure injection.

## Related Documents

- [Scheduler Recovery Architecture](../architecture/SCHEDULER_RECOVERY.md)
- [Project Atlas Architecture](../architecture/README.md)
- [ADR 0004 — Runtime State Architecture](0004-runtime-state-architecture.md)
- [ADR 0014 — Stale Runtime State Normalization](0014-stale-runtime-state-normalization.md)
