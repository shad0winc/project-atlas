# Sustained Use Release Certification

Project Atlas uses the M-023 Q.6 sustained-use certification to prove that the
exact v1.0 release candidate remains operationally stable over an extended
production observation window.

This document defines the operator contract for Q.6. It does not itself certify
that Q.6 has completed.

---

## Certification Contract

The canonical Q.6 contract is:

| Property | Contract |
| --- | --- |
| Duration | 48 hours |
| Sample interval | 15 minutes / 900 seconds |
| Total expected samples | 193 |
| First sample | T0, captured by manual `start` |
| Expected running containers | 22 |
| Automated task | `sustained-use.sample` |
| Automated callback | `python3 -m atlas.sustained_use.scheduled_sample --json` |
| Start | Manual release-engineering action |
| Sampling | Automatic while active and due |
| Status | Manual, read-only |
| Finalize | Manual release-engineering action |

The 193 samples include T0 plus the 192 subsequent 15-minute intervals through
T+48h.

---

## Evidence Location

Production Q.6 evidence is stored under:

```text
/mnt/storage/configs/atlas/sustained-use
```

The repository layer maintains:

- immutable historical sample evidence;
- atomic latest-sample state; and
- atomic `session.json` lifecycle state.

No production evidence directory should exist before the real Q.6 session is
started.

---

## Lifecycle

The supported operator lifecycle is:

```text
clean committed candidate
        |
        v
controlled Scheduler synchronization
        |
        v
atlas sustained-use start
        |
        +----> T0 / sample 1 of 193
        |
        v
sustained-use.sample polled every 60 seconds
        |
        | fixed T0-derived slot gate
        | certification observations every 900 seconds
        v
atlas sustained-use status
        |
        v
T+48 hours / 193 samples
        |
        v
atlas sustained-use finalize
```

### Start

```bash
atlas sustained-use start
```

`start` is intentionally manual.

Before durable session creation, Atlas:

1. resolves the exact current Git commit;
2. collects candidate T0 in memory;
3. strictly evaluates T0;
4. refuses to create the session if T0 fails;
5. creates the immutable session boundary only after T0 passes; and
6. persists T0 immediately as sample 1.

The Q.6 clock starts only after this successful durable T0 boundary.

### Sample

```bash
atlas sustained-use sample
```

The manual `sample` command requires an active session.

A sample that violates a hard invariant is still persisted so the certification
history cannot hide the failure.

### Status

```bash
atlas sustained-use status
```

`status` is read-only and reports the durable session, current sample count,
remaining sample count, and latest persisted observation.

### Finalize

```bash
atlas sustained-use finalize
```

`finalize` is intentionally manual.

Finalization refuses to proceed before the scheduled T+48h boundary or unless
the exact expected sample count is present.

The final decision re-evaluates:

- every persisted sample against the hard invariants; and
- the complete ordered sample history against temporal invariants.

The session transitions to `completed` only when both hard and temporal
evaluation pass. Otherwise the session closes as `failed`.

---

## Automated Sampling

The canonical core Scheduler task is:

```text
name:                   sustained-use.sample
poll interval:          60 seconds
certification interval: 900 seconds
module:                 null
callback:               python3 -m atlas.sustained_use.scheduled_sample --json
```

It is registered only through an **unqualified**:

```bash
atlas scheduler sync
```

Targeted module synchronization does not register or mutate this core task.

The scheduled callback is deliberately idempotent:

| State | Result |
| --- | --- |
| No Q.6 session | Successful no-op |
| Inactive terminal session | Successful no-op |
| Expected sample count already reached | Successful no-op |
| Active before next fixed T0-derived slot | Successful `not_due` no-op |
| Active at fixed slot or <=180 seconds late | Capture and persist exactly one sample |
| Active >180 seconds after next required slot | `missed`; return nonzero and do not backfill |
| Due sample fails hard evaluation | Persist evidence and return nonzero |
| Collection/runtime failure | Return nonzero |

This allows the Scheduler task to remain registered while Q.6 is inactive
without manufacturing Scheduler failures or accidentally starting a
certification session.

The Scheduler never starts or finalizes Q.6.

---

## Observed Domains

Each sustained-use sample aggregates the release-critical runtime observations
required by the Q.6 contract:

- Atlas aggregate health;
- Docker container runtime state;
- root filesystem usage;
- Atlas storage usage;
- canonical Scheduler task observations;
- Runtime Bus journal/cursor state and Notifications heartbeat;
- ARI status, score, warnings, and TV synchronization state; and
- exact Git commit identity.

The production Runtime Bus observation is read-only. The certification
collector does not gain journal write authority.

---

## Hard Invariants

A single sample must satisfy the release-critical hard contract, including:

- exact committed Git identity;
- clean/healthy Atlas release health at the real certification boundary;
- expected running-container count;
- zero unhealthy containers;
- zero OOM kills and disallowed restart growth;
- filesystem/storage safety thresholds;
- readable but non-writable Runtime Bus journal access;
- acceptable Notifications heartbeat freshness;
- required Scheduler state; and
- accepted ARI baseline.

Hard failures are evidence. They are not discarded.

---

## Temporal Invariants

Final history evaluation protects against failures that cannot be judged from a
single snapshot.

The temporal contract includes:

- every sample ordinal belonging to its immutable T0-derived slot;
- no sample occurring before its required slot;
- no sample occurring more than 180 seconds after its required slot;
- no backfilled replacement observations for missed slots;
- Scheduler progress across the observation window;
- no Scheduler failure-count growth;
- no Runtime Bus journal or subscriber-cursor regression;
- final Runtime Bus backlog of zero;
- no ARI score drop below the established T0 baseline;
- no expansion of the ARI warning set; and
- no worsening of the TV synchronization difference.

Finalization evaluates fixed-slot cadence independently from the collection callback through `history.cadence.fixed_slots`. Chronological order and correct sample cardinality alone are not sufficient to certify Q.6.

---

## Activation Gate

Instrumentation readiness and Q.6 execution are separate states.

Do **not** start Q.6 from a dirty development worktree.

Before the real production session begins:

1. complete implementation and documentation certification;
2. commit the exact Q.6 instrumentation candidate;
3. push the exact commit;
4. restore a clean Git working tree and index;
5. prove Atlas health is `healthy:100`;
6. confirm 22 running containers and zero unhealthy containers;
7. perform controlled unqualified `atlas scheduler sync`;
8. inspect `sustained-use.sample`;
9. prove the dormant callback is safe while no session exists; and
10. only then execute `atlas sustained-use start`.

The commit recorded by T0 is part of the immutable certification contract.

---

## Before T0

Expected state before activation:

```text
Q.6 implementation         present and committed
Git working tree           clean
Atlas health               healthy:100
running containers         22
unhealthy containers       0
sustained-use.sample       registered and inspected
Q.6 session.json           absent
Q.6 sample history         absent
Q.6 clock                  not started
```

A dormant Scheduler task does not mean Q.6 has started.

---

## During the Run

Routine observation should use:

```bash
atlas sustained-use status
atlas scheduler inspect sustained-use.sample
atlas health --compact
```

Avoid manually invoking extra samples unless a controlled recovery procedure
requires it. The persisted history is intended to represent the fixed
15-minute observation contract.

Do not change the certified Git candidate during the Q.6 run.

A release-blocking defect discovered during the window must be treated as a
candidate defect, not hidden by modifying the running certification candidate.

---

## Completion

Q.6 is complete only when all of the following are true:

- the full 48-hour interval has elapsed;
- exactly 193 samples are present;
- every sample has been hard-evaluated;
- every sample satisfies the fixed T0-derived slot contract;
- the complete temporal history has been evaluated;
- finalization succeeds;
- the durable session records the final decision; and
- the resulting evidence is reconciled into release documentation.

Only then may the ROADMAP item:

```text
Complete sustained-use test
```

be marked complete.

Q.6 completion does not automatically close the independent
`Resolve release-blocking defects` gate, controlled pilot, stabilization,
release-candidate freeze, tagging, or final publication.

---

## Current Q.6A.2 State

At the Q.6A.2 instrumentation documentation boundary:

- the sustained-use implementation candidate is complete;
- the pre-documentation implementation certification is passing;
- the Q.6 Scheduler registration contract exists in the repository;
- live `sustained-use.sample` registration has not yet occurred;
- no production Q.6 session exists;
- no production Q.6 evidence has been persisted; and
- the 48-hour Q.6 clock has not started.

This document therefore describes the certified instrumentation and the
procedure for the later production certification run. It is not itself Q.6
completion evidence.

## Q.6A.5 Fixed-Cadence Repair

The second production attempt, `q6-20260817T232028Z`, proved that Scheduler execution success is not by itself sufficient to guarantee the Q.6 temporal contract.

The run reached `176/193` samples with zero Scheduler failures and otherwise healthy production, but its effective interval was approximately 16 minutes because each next Scheduler due time inherited the previous callback's execution/completion delay. The resulting cumulative phase drift made 193 observations impossible inside the exact 48-hour window.

The attempt was explicitly retired as `aborted` and preserved under the immutable archive namespace.

Q.6A.5 corrects the certification clock without changing generic `TaskScheduler` semantics.

The certification schedule is fixed:

```text
required_time(sample_number)
    = T0 + ((sample_number - 1) * 900 seconds)
```

The Scheduler polls `sustained-use.sample` every 60 seconds. The callback compares the current time with the next required T0-derived slot.

The maximum accepted lateness is 180 seconds. Polls before the slot are no-ops, observations inside the lateness window may be captured, and observations outside that window are classified as missed. Missed observations are never backfilled.

The complete history is independently rechecked during finalization through `history.cadence.fixed_slots`.

The fixed-slot evaluator has been regression-tested against the archived `176/193` production history and correctly rejects that drifting run.

A fresh Q.6 certification must not begin until this repair is committed, published, synchronized into the live Scheduler, and autonomously reverified.

---

## Aborted certification attempts

`aborted` is the terminal state for an explicitly retired incomplete sustained-use certification attempt.

| State | Meaning |
|---|---|
| `completed` | The complete scheduled history was finalized and passed release evaluation. |
| `failed` | The complete scheduled history was finalized but did not pass release evaluation. |
| `aborted` | The certification attempt was incomplete and was deliberately retired while preserving its evidence. |

The supported operator boundary is:

```bash
atlas sustained-use abort \
  --confirm-run-id <exact-current-run-id>
```

The confirmation is mandatory and must exactly equal the current session run ID. There is no force bypass.

The abort lifecycle loads the current session, permits only `active` or partially archived `aborted` state, transitions an active session to `aborted`, records a UTC `completed_at`, persists the terminal session, archives the run, and returns the immutable archive path. If a previous archive attempt was interrupted after the status transition, retry preserves the original completion timestamp.

Each retired run is stored at:

```text
archive/<run-id>/
├── session.json
├── latest.json
└── history/
```

The move order is `history`, then `latest.json`, then `session.json`. Moving `session.json` last keeps the lifecycle closed until archival is complete. Archived run identities are not reusable.

Before a replacement T0, the release candidate must be committed and published, Git health must be clean, `sustained-use.sample` must be registered at the canonical 60-second polling interval while preserving the 900-second certification interval, the production Scheduler dispatcher must be enabled and active, dormant callback behavior must be reverified, and every previous aborted run must remain intact.
