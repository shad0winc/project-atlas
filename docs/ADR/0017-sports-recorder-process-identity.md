# ADR-0017: Sports Recorder Process Identity

## Status

Accepted

## Context

The Atlas Sports module persists active recording state and the PID of its
recorder process. Existing recovery logic can adopt a still-running recorder
after controller interruption and can reconcile a recorder that has exited.

Linux PIDs are reusable identifiers. PID liveness alone therefore cannot prove
that the currently running process is the recorder Atlas originally launched.
Using PID-only ownership during recovery could cause Atlas to adopt or signal
an unrelated process.

Project Atlas requires recovery decisions to be based on explicit evidence and
requires destructive or ownership-sensitive operations to fail closed when
that evidence is ambiguous.

## Decision

Sports recorder ownership will use the pair:

- process PID; and
- Linux process start-time token from `/proc/<pid>/stat` field 22.

Atlas will capture the start-time token when it launches a recorder and persist
it with the recording state.

Recovery adoption requires both the PID and start-time token to match the live
process. Recorder termination likewise requires verified identity before Atlas
signals the target process group.

A live PID with a missing or mismatched identity token is not proof of recorder
ownership. Atlas must fail closed rather than adopt, signal, or silently replace
the durable identity.

## Why Process Start Time

The kernel process start-time token is small, local, deterministic, and already
available through procfs on the Linux hosts Atlas supports. It distinguishes a
reused PID without introducing another service or external dependency.

The token is treated as opaque process identity rather than a user-facing
timestamp.

## Alternatives Considered

### PID only

Rejected because PID reuse can associate Atlas with an unrelated process.

### Command-line matching

Rejected as the primary identity because command lines are mutable in practice,
may be unavailable, and are not a unique process-lifetime identifier.

### External process supervisor

Rejected for M-023.19 because it would duplicate existing recorder lifecycle
responsibility and materially increase operational complexity.

### New recovery database or transaction journal

Rejected because the existing atomic `recordings.json` registry already owns
the durable recording state. Only the missing identity fact is required.

## Consequences

Positive consequences:

- controller recovery can still adopt the correct live recorder;
- reused PIDs cannot be accepted as recorder ownership;
- process termination receives the same ownership verification as adoption;
- the existing Sports scheduler and recorder architecture remain intact; and
- recovery remains deterministic and testable.

Tradeoffs:

- new recordings persist one additional Linux-specific identity value;
- active legacy recordings without that value are ambiguous and must be
  inspected before production enforcement; and
- procfs availability becomes part of the local recorder identity boundary.

## Compatibility

This decision extends the current recording registry rather than replacing it.
Existing terminal recordings do not require migration because process identity
is relevant only while Atlas may adopt or signal an active recorder.

Production validation must determine whether any active legacy recording lacks
the new identity evidence before the hardening is considered complete.

## Related Decisions

- [ADR 0015 — Scheduler Recovery Boundaries](0015-scheduler-recovery-boundaries.md)
