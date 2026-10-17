# Disposable Docker lifecycle fence

This candidate adds a bounded stop and detach barrier for disposable Dispatcharr
and Teamarr drill containers. It does not enable live restore or deployment.

The diagnostic starts the pinned application images normally, on fresh labelled
local Docker volumes with no network or published ports. Teamarr uses
`SCHEDULER=off`, `DRY_RUN=true` and `SKIP_CACHE_REFRESH=1`. Synthetic probe rows
and backup fixtures are created inside those disposable instances. No production
database, JWT, container environment, logs or feed configuration is copied.

The two native volumes are deliberately separate from the cooperative
filesystem journal used to verify gated recovery. This phase proves Docker
lifecycle fencing plus filesystem recovery composition. It does not prove
rollback of native application writes through the journal, mixed ownership
publication, grouped native SQLite sidecar recovery or live orchestration.

## Barrier

The helper accepts a private `/tmp/project-atlas-sports-publication.*` sandbox
and a lowercase UUID hex identifier. Container and volume names are derived
internally from that identifier and the two fixed roles. Arbitrary names,
images, mounts and production targets are not accepted.

Before recording intent or stopping anything, it verifies both app identities:
full container ID, start timestamp, pinned image, original image entrypoint and
command, ownership label, root user, private IPC/PID/user namespaces, network
none, restart policy no, restart count zero, no auto removal, no privilege or
port publication, a `/tmp` tmpfs and exactly one writable named data volume.
The local volume must have the same ownership label and no driver options.
Its only container reference must be the expected application ID.

The durable ledger binds the publication plan and consumer exposure document.
It records `armed`, `pg-clean`, `stopped`, `detaching` and `detached` transitions
with the existing atomic JSON and directory fsync implementation. A separate
nonblocking lifecycle lock serializes this controller's operations.

Dispatcharr requires PostgreSQL 17 control state `shut down`. If it is in
production, the helper requests `pg_ctl -m fast -w -t 20 stop` as UID/GID 1000.
It persists clean-stop evidence before stopping the AIO object. Both Docker
objects must then be exited, PID zero, neither OOM killed nor restarted, with
exit status 0 or 143. Status 137 and unexpected states hold the barrier.

Only after both exited identities are verified does the helper persist the
removal intent. It removes exact full container IDs using `docker rm` without
force and without deleting volumes. Interrupted removal can resume from the
recorded intent. Missing objects before that intent, replaced names or changed
start epochs hold recovery. The ledger is retained after recovery.

A successful Docker daemon/list response, absence of both IDs and names, and
zero container references to both retained volumes are required before and
after calling the cooperative journal recovery API. Exited helper containers
also count as references. A Docker error is never treated as proof of absence.
Repeated detach and recovery validate the same identities and journal binding.

This is a trusted, serial fixture controller, not a daemon admission lock.
An unrelated privileged operator can still create containers, mount volumes,
restart processes inside an app or mutate local files concurrently. Such
actors must be excluded operationally. Checks before and after recovery cannot
make arbitrary concurrent Docker changes atomic. The existing cooperative
journal primitive remains independently usable and has no Docker semantics;
only this wrapper enforces this barrier. No live path API is introduced.

## Verification

Run before committing, from the new feature worktree on CT100:

```sh
git diff --check
python -B -m pytest -q tests/core
python -B scripts/diagnostics/sports-recovery-lifecycle-drill.py
```

The diagnostic refuses the wrong source checkpoint, records production
container identities and canonicalized mount contents, and checks those plus
the deployment pointer and clean canonical checkout again during cleanup.
It rejects recovery while fixture app objects exist, then kills its detachment
worker after the first actual container removal. The parent resumes the durable
removal intent and runs recovery twice, verifying old filesystem state and
quarantined consumer changes. Cleanup removes only exact owned fixture
resources. Success is printed only after cleanup and unchanged-production
observations pass. Native volumes remain present through the recovery checks
and are removed by final diagnostic cleanup.

Unit tests exercise contract tampering, changed start epochs, unknown and killed
exits, foreign volume references, Docker failure, replaced names, private-ledger
metadata and binding, repeated recovery and interruption at durable transitions.
Unit interruption seams use exceptions; the CT diagnostic performs actual
process death at the first Docker removal. Neither is hardware power-loss
certification. Existing native application restart drills and live gates remain
separate requirements.
