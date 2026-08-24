# Scheduler Recovery Architecture

## Purpose

Scheduler Recovery defines how Project Atlas safely resumes shared scheduled
work after scheduler-process interruption without allowing overlapping
execution or fabricating successful task outcomes.

The capability hardens the existing `TaskScheduler`. It does not introduce a
second scheduler, watchdog, retry daemon, or provider-specific recovery engine.

## Motivation

Atlas already persists scheduler definitions and runtime state, prevents
overlapping execution with a PID lock, and bases interval eligibility on the
last successful execution. Those properties provide most of the mechanics
needed for recovery.

Recovery nevertheless requires explicit guarantees for two independent cases:

1. the scheduler process terminates while it owns the runtime lock;
2. a task was persisted as `running` but no terminal outcome was recorded.

Without a documented contract, lock cleanup can become too permissive and a
persisted `running` value can be mistaken for proof that execution is still
active.

## Existing Scheduler Boundary

`TaskScheduler` remains the scheduler source of truth.

It already owns:

- persistent task definitions;
- interval and due-state calculation;
- execution serialization through the runtime lock;
- `never_run`, `running`, `healthy`, and `degraded` task state;
- success and failure counters;
- bounded execution history;
- task lifecycle events;
- core Operations and optional-module job execution.

Scheduler state is written through the shared Atlas atomic JSON persistence
boundary. Recovery must preserve that boundary rather than adding a parallel
state store.

## Responsibility Boundary

### Runtime lock

The runtime lock owns execution exclusivity. Its purpose is to answer one
question: may this scheduler process execute tasks now?

The lock file records the PID that acquired it. A second runtime must not
execute work while ownership might still be valid.

### Persistent task state

Persistent task state owns historical scheduler facts. `status="running"`
means an execution was started and no later terminal scheduler state has yet
been persisted. It is not, by itself, proof that a scheduler process is still
alive.

### Due-state calculation

`last_success` remains the scheduling authority. Starting an execution never
advances `last_success`. An interrupted scheduled task therefore cannot be
mistaken for a successful run.

### Consumers

The CLI, Portal, Operations, modules, and future API consumers read scheduler
state. They must not bypass the shared scheduler lock or invent independent
recovery semantics.

## Lock Recovery Contract

Atlas uses a fail-closed ownership rule.

| Observed lock state | Scheduler behavior |
| --- | --- |
| Recorded PID is alive | Block execution |
| Recorded PID cannot be safely disproved as owner | Block execution |
| Recorded PID is positively known not to exist | Reclaim the stale lock |
| Lock is empty | Block execution |
| Lock contents are malformed | Block execution |
| Lock ownership cannot be read reliably | Block execution |

Automatic recovery is permitted only when Atlas can positively establish that
the recorded owner process no longer exists.

This rule intentionally prefers a visible scheduler stop over concurrent task
execution when ownership is ambiguous.

## Why Ambiguous Locks Fail Closed

The current lock is created with exclusive file creation and its PID is then
written into that file. Those are separate operating-system operations.

Treating an empty or malformed lock as automatically stale creates a small
race: another scheduler could observe a newly created lock before its owner PID
has been written, remove the live lock, and begin concurrent execution.

M-023.17 hardens this boundary by distinguishing a provably dead owner from an
unknown owner. Unknown ownership is not evidence of staleness.

## Interrupted Task Recovery Contract

Scheduler interruption must never create synthetic success.

When an execution has persisted `status="running"` but does not record a
terminal outcome:

- `last_success` remains unchanged;
- success counters remain unchanged;
- no successful history entry is invented;
- normal due-state calculation continues to use the previous `last_success`;
- an execution that was already due remains due after interruption;
- a later successful execution transitions the task to `healthy`;
- a later failed execution transitions the task to `degraded`.

For a manually forced execution that ran before its interval was due, recovery
does not override the stored interval merely because the forced execution was
interrupted. An operator may explicitly force that task again if required.

## Delivery Semantics

The scheduler provides at-least-once opportunity for normally due work across
process interruption. Because Atlas cannot know how much external work a
terminated callback completed before interruption, it must not claim exactly
once delivery.

Scheduled callbacks should therefore be safe to repeat or own their own
idempotency boundary when external side effects require it.

This milestone does not add automatic compensating actions for interrupted
callbacks.

## Production Dispatch Boundary

Scheduler Recovery and production dispatch are separate responsibilities.

`TaskScheduler` remains the sole scheduler and recovery authority. It owns
persistent task state, task cadence, due-state calculation, the runtime lock,
callback execution, success/failure state, and bounded history.

The production host supplies only a recurring dispatch opportunity through:

```text
atlas-scheduler.timer
        |
        | one-minute host cadence
        v
atlas-scheduler.service
        |
        | /bin/atlas scheduler run
        v
TaskScheduler.run_due_tasks()
```

This systemd layer does not create a second scheduler. It does not decide that
a specific task is due, encode task-specific intervals, maintain Scheduler
state, reclaim locks, retry callbacks independently, or manufacture task
outcomes.

A one-minute timer cadence bounds normal dispatch jitter while leaving each
task's `interval_seconds` and `last_success` semantics entirely inside Atlas.
For example, the 900-second `sustained-use.sample` interval remains an Atlas
task contract; it is not a 15-minute systemd timer.

The existing fail-closed runtime lock remains authoritative when two dispatch
opportunities overlap or an operator starts Scheduler execution manually. A
live owner blocks the new execution, and the Atlas CLI returns its Scheduler
lock-contention status to systemd rather than bypassing or masking the lock.

Dispatcher exit semantics preserve Scheduler facts:

- no due work is successful dispatcher execution;
- all successful due callbacks produce dispatcher exit `0`;
- any failed due callback produces dispatcher exit `1`;
- lock contention produces dispatcher exit `3`;
- mixed due tasks are attempted under the normal shared Scheduler contract.

The dispatcher therefore supplies availability of invocation, not recovery
policy. All lock-recovery and interrupted-task rules defined by this document
and ADR 0015 remain unchanged.

## Verification Requirements

M-023.17 must prove the existing and hardened behavior with focused tests:

- a live PID lock blocks a second scheduler;
- a dead PID lock is reclaimed;
- empty and malformed locks fail closed;
- indeterminate ownership fails closed;
- an interrupted `running` task does not advance `last_success`;
- an already-due interrupted task remains due;
- a successful rerun becomes `healthy`;
- a failed rerun becomes `degraded`;
- counters and execution history remain deterministic.

Broader Scheduler, Operations scheduler, CLI, and Portal scheduler regressions
must pass after the hardening.

Production validation should begin read-only. Atlas must not deliberately
terminate a production scheduler or scheduled callback unless that mutation is
separately reviewed and explicitly approved.

## Non-Goals

Scheduler Recovery does not:

- add a second scheduler or recovery daemon;
- add a watchdog process;
- add a universal stale-state TTL;
- infer that an ambiguous lock is safe to remove;
- claim exactly-once callback execution;
- fabricate success after interruption;
- automatically compensate for callback side effects;
- replace module-specific recovery logic;
- replace interrupted-request or Sports recovery milestones;
- authorize production process termination.

## Delivery Sequence

1. Define Scheduler Recovery architecture and ADR 0015.
2. Harden ambiguous lock ownership to fail closed.
3. Add focused lock and interrupted-task recovery tests.
4. Run Scheduler, Operations, CLI, and Portal scheduler regressions.
5. Inspect the production scheduler and lock state read-only.
6. Perform additional controlled validation only if separately justified and
   approved.
7. Reconcile roadmap, changelog, build history, and architecture completion
   evidence.


## Production Validation

M-023.17 was validated at commit `b79870e1` against the configured production
scheduler without executing tasks, changing scheduler state, deleting locks,
or terminating processes.

Production evidence:

- scheduler schema version: 2;
- registered tasks: 2;
- persisted task states: one `healthy` and one `never_run`;
- persisted `running` tasks: zero;
- due tasks: `operations.collect` and `sports.maintenance`;
- scheduler history entries: one;
- runtime lock: absent;
- scheduler runtime consistency: passed;
- repository mutations: none.

The existing Operations history entry records a successful callback together
with a historical module-event publication error. The currently registered
`operations.collect` task has `module: null`, preserving the later core-job
event-routing isolation. That historical event-delivery record is not a
Scheduler Recovery failure.

Recovery mechanics were proven deterministically rather than by terminating a
production scheduler. Nine focused recovery tests cover live and dead PID
ownership, fail-closed ambiguous ownership, interrupted task facts, successful
retry, and failed retry. The broader shared Scheduler/Operations and Portal
Scheduler regressions also passed.

## Completion State

M-023.17 is complete. Atlas now automatically reclaims only scheduler locks
whose recorded owners are positively known to be gone, fails closed when lock
ownership is ambiguous, preserves interrupted task facts without manufacturing
success, and retains deterministic retry outcomes through the existing shared
scheduler.

No second scheduler, watchdog, stale-state TTL, recovery daemon, or destructive
production failure injection was introduced.

## Related Documents

- [Project Atlas Architecture](README.md)
- [Stale-State Recovery](STALE_STATE_RECOVERY.md)
- [ADR 0015 — Scheduler Recovery Boundaries](../ADR/0015-scheduler-recovery-boundaries.md)
- [ADR 0004 — Runtime State Architecture](../ADR/0004-runtime-state-architecture.md)
