# Isolated Sports publication and crash recovery rehearsal

Status: callable rehearsal engine restricted to private `/tmp` fixtures. No live
restore wiring, production path selection, container control or finalization.
Existing format-2/3 live restore blocks and the 16-surface engine are unchanged.

## Inputs and fixed publication units

Create an operator-owned 0700 `/tmp/project-atlas-sports-publication.*` sandbox
with a 0700 `current` directory containing exactly these five fixture entries:

| Fixture entry | Incoming preparation | Kind |
| --- | --- | --- |
| dispatcharr-db | Prepared restored-cluster | Directory |
| dispatcharr-jwt | Bundle dispatcharr/jwt | File |
| teamarr-db | Bundle teamarr/teamarr.db | File |
| sports-metadata | Bundle sports-metadata, including database and lock | Directory |
| sports-metadata-policy | Bundle sports-metadata-policy | Directory |

These names have no production path mapping. All existing fixtures and prepared
inputs must be private to the same operator: directories 0700, files 0600, with
no links, hardlinks or special files. Actual production ownership/modes are not
applied. All five current entries must exist; absent-state deletion is unsupported.

Call `stage(association_root, sandbox)` with a validated preparation association.
It revalidates the complete association, copies the five incoming units with
bounded content hashing, fsyncs new files/directories, checks the association
again and publishes a private durable PLAN.json plus STATUS.json. The plan binds
both old/new content hashes and the exact association document. Preparation can
leave an incomplete transaction on failure; it never moves current state. Preserve
that workspace for inspection instead of rerunning stage over it.

## Mutation and recovery

`apply(sandbox)` takes a nonblocking exclusive local lock, validates the plan,
all five positions and the source association, then fsyncs `applying` intent
before any state move. Each old unit moves to `transaction/old`; each incoming
unit then moves to `current`. Both rename parents are fsynced. Only after all
five new content hashes match does status become `applied-awaiting-verification`.
Old state remains preserved. There is no commit/finalize API that deletes it.

Ordinary apply errors attempt rollback. Process death leaves the durable plan
and state positions available to `recover(sandbox)`. Recovery recognizes exactly
three per-unit arrangements: old still current; old preserved with current absent;
or new current with old preserved. Every position/hash is checked before any undo.
Unknown, tampered or missing preserved state blocks recovery without deleting
anything. No unverified state may justify restarting consumers.

Rollback records `rolling-back`, moves new state back to incoming, then restores
old state in reverse unit order. Each move is durable before proceeding. A crash
during undo is recoverable again. After exact old hashes are restored, status
becomes `reverted`; repeated recovery verifies that result. Undo does not require
the external association/preparation workspaces to remain available.

There is no automatic resume of partially applied new state. A failed rollback
stays held in `rolling-back`; retain all artifacts and retry only after resolving
the failure. A private operator can rewrite plans and data; these integrity
checks are not signatures or a security boundary against that operator.

## Verification and limits

Core tests publish and reverse actual private files. Native PostgreSQL commands
used by the preparation validators remain stubbed; no database server or Docker
process is launched by this rehearsal. The preceding CT100 native preparation
drill provides separate real PostgreSQL restore/stopped-state evidence.

Child processes really terminate without cleanup at all 12 apply and 11 rollback
boundaries. A fresh call recovers exact old hashes. Tests also cover a filesystem
sync error after rename, stage copy failure, normal error undo, interrupted undo,
tampered incoming/current/preserved state, missing association during recovery,
exclusive locking, stale partial status writes and unsafe plans/paths/permissions.
This verifies process-crash behavior; it does not certify physical storage
power-loss behavior or application health after restarting a restored cluster.

The durable plan remains `scope:isolated-only`, `ready_for_live_apply:false`.
Production cold-copy acquisition, verified consumer identities/ownership, stop
and mount attestation, integration with the existing filesystem transaction,
combined restart acceptance, maintenance/lock lifecycle and production Sports UAT
remain open. Do not translate these fixture names to live paths or remove the
current live restore blocks based on this rehearsal alone.
