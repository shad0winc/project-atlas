# Sports Recovery Architecture

## Purpose

Sports Recovery defines how the optional Atlas Sports module safely resumes
observation of recorder processes after controller interruption without
duplicating, adopting, or terminating an unrelated operating-system process.

The existing Sports recording scheduler, recorder, and persisted
`recordings.json` registry remain authoritative. This architecture hardens the
evidence used to associate an active recording with a Linux process; it does
not introduce a second recovery engine.

## Motivation

Sports already persists the recorder PID and can recover an active recorder
after the controller restarts. Existing integration coverage proves that a
known live recorder is retained and that a completed recorder is reconciled.

A PID alone is not a durable process identity. Linux may reuse a PID after the
original recorder exits. Treating PID liveness as proof of recorder ownership
could cause Atlas to adopt an unrelated process or, more seriously, signal an
unrelated process during recording shutdown.

Atlas therefore requires stronger evidence before process adoption or
termination.

## Architectural Boundary

The responsibility flow remains:

```text
Sports subscriptions and provider state
              |
              v
      recording planner
              |
              v
       recordings.json
              |
              v
     recording reconciler
              |
              v
        recorder adapter
              |
              v
       operating system
```

The recording registry owns durable recording facts. The recorder adapter owns
operating-system process inspection and signaling. The recording reconciler
may act only on normalized evidence returned by that adapter.

## Durable Recorder Identity

An active recorder identity consists of:

- the numeric PID; and
- the Linux process start-time token read from `/proc/<pid>/stat` field 22.

The start-time token is measured by the kernel from boot and remains stable for
the lifetime of that process. A reused PID receives a different start-time
token.

When Atlas launches a recorder, it captures both values and persists them with
the recording before relying on that identity for later recovery decisions.

The token is an opaque identity value. Atlas does not interpret it as a wall
clock timestamp and does not convert it to UTC.

## Recovery Rules

### Verified active recorder

Atlas may adopt an existing recorder only when:

1. the persisted PID is valid;
2. the process is currently alive;
3. a persisted process start-time token exists; and
4. the current process start-time token matches the persisted token.

All four conditions are required.

### Dead recorder

If the recorded PID no longer exists, Atlas may reconcile the recording using
the existing exit-code sidecar, partial output, schedule, and finalization
rules. PID absence does not authorize Atlas to signal another process.

### Reused or mismatched PID

If the PID exists but its current start-time token differs from the persisted
token, Atlas must treat the process as not owned by the recording.

Atlas must not:

- adopt that process;
- signal that process or its process group;
- overwrite the durable identity with the new process identity; or
- infer successful recovery from PID liveness alone.

The recording may transition through the existing failure/reconciliation path,
but process ownership remains fail closed.

### Missing identity evidence

An active recording with a PID but no durable start-time token is ambiguous.
Atlas must not use PID-only evidence to terminate or adopt a live process.

Before enforcing this contract in production, M-023.19 must inspect the current
Sports registry for active legacy recordings that lack the identity token.

## Recorder Launch

New recorder launch behavior remains intentionally small:

1. build the existing recorder command;
2. launch the recorder process group;
3. capture PID and process start-time token;
4. return both values to the recording reconciler; and
5. persist both values with the existing recorder metadata.

Failure to obtain reliable process identity after launch is an explicit
recovery-safety failure. It must not be silently converted into PID-only
ownership.

## Recorder Stop

Process termination is an ownership-sensitive operation.

Before `SIGTERM` or `SIGKILL`, Atlas verifies that the target PID still has the
expected start-time token. Identity must be rechecked during the stop sequence
because process state can change between observations.

If ownership cannot be verified, the stop operation fails closed and does not
signal the process group.

## Persistence

Sports continues to use the existing atomic `recordings.json` replacement
boundary. M-023.19 adds process identity as another persisted recording fact;
it does not add a journal, database, lock service, or transaction coordinator.

Existing recording fields, output paths, exit-code sidecars, subscription
metadata, and terminal states remain compatible.

## Observability

Recovery decisions must remain explainable through persisted recording state
and tests. A recovery failure caused by missing or mismatched process identity
must be distinguishable from a normal recorder exit.

No automated destructive recovery action is allowed solely because a PID is
present.

## Validation Contract

M-023.19 requires focused coverage for:

- adoption of the same live recorder process;
- persistence of the recorder process start-time token;
- reconciliation after the recorder exits;
- rejection of a reused or mismatched PID;
- rejection of missing identity evidence where ownership is required;
- proof that an unrelated process is not adopted;
- proof that an unrelated process is not signaled;
- successful recording finalization; and
- scheduler and full Sports regression compatibility.

Production validation begins read-only. Any controlled recorder mutation must
be separately justified and explicitly approved.

## Non-Goals

M-023.19 does not add:

- a second Sports scheduler;
- a second recorder registry;
- a recovery daemon;
- automatic replay of failed recordings;
- exactly-once recording guarantees;
- cross-host process recovery;
- a generic process supervisor; or
- destructive reconciliation of ambiguous processes.

## Implementation Status

M-023.19 is complete.

The implemented recovery contract now:

- captures Linux process start-time identity when a recorder launches;
- persists process identity alongside the recorder PID;
- verifies PID and start-time identity before adopting a live recorder;
- verifies the same identity before process-group signaling;
- fails closed when active process identity is missing or mismatched; and
- preserves existing exit-code, partial-file, finalization, and scheduler
  behavior.

The full Sports integration runner passed all five suites after hardening.

## Production Validation

Read-only production validation at commit `1924f8eb` found an existing but
empty recording registry: zero persisted recordings, zero active recordings,
and zero ambiguous active recordings. No legacy active state requires
migration.

Both Sports containers were running and healthy, the controller heartbeat was
fresh, TheSportsDB provider health was healthy, FFmpeg was available, and the
structured Sports health contract was healthy across controller, provider,
recorder, recordings, and storage. Production recorder mutations: none.

## Related Decisions

- [ADR 0015 — Scheduler Recovery Boundaries](../ADR/0015-scheduler-recovery-boundaries.md)
- [ADR 0017 — Sports Recorder Process Identity](../ADR/0017-sports-recorder-process-identity.md)
