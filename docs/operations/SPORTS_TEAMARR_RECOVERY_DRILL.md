# Synthetic Teamarr shutdown and restored restart rehearsal

Run `scripts/diagnostics/sports-teamarr-recovery-drill.py` only in its verified
candidate worktree at the guarded source checkpoint. This exercises a fresh
fixture using the installed pinned Teamarr image, never production state.

Observed image:
`sha256:ecec625df0a029cddecf72fcb86d0d2eb9c16ce14f9377b1ddc0954bba4e2ec7`.
Its command is `python app.py` in `/app`, with no image entrypoint or declared
volumes. Uvicorn uses port 9195. Its lifespan shutdown stops the scheduler and
Dispatcharr client; the reviewed handler has no explicit SQLite checkpoint.
Container exit alone therefore cannot prove main-file-only SQLite completeness.

## Isolated fixture lifecycle

The driver reuses hash-pinned resource ownership/cleanup utilities from the
preceding AIO cold-copy drill. The new fixture has a random labelled local Docker
volume mounted only at `/app/data`, original image command, root UID/GID matching
the observed deployed consumer, no capabilities, no network, no published ports,
no production mounts or env file, no restart, no Docker log storage, private tmpfs
scratch and bounded CPU/memory/PIDs/startup. The disposable image layer is writable.
Local volume disk usage is not a filesystem quota.

Explicit flags are `SKIP_CACHE_REFRESH=1`, `SCHEDULER=off`, `DRY_RUN=true` and
`PORT=9195`. Readiness queries only the fixture's loopback GET `/health`, requires
healthy startup and verifies scheduler-disabled/dry-run status. No generation,
EPG, stream, feed or provider endpoint is called. No existing Teamarr data is
imported. Source hashes bind the launcher, API app, safety flags and health route.

The fixture creates one synthetic marker table. SQLite's online backup API writes
a separate snapshot with marker `snapshot`; the running database then changes
to `after-dump`. Connections are explicitly closed and backup progress is timed.
The driver stops only the labelled fixture with a 35-second timeout and requires
exited state, PID 0, exit 0/143 and no OOM before any helper is created.

## Cold-copy and restored application checks

A read-only helper mounts only the owned volume at `/source`, with a read-only
image root and no capabilities/network. It copies the stopped main database and
any WAL/SHM files together into private tmpfs. File sizes, ownership, links and
stable hashes are checked. A rollback journal is rejected, not repaired in place.
Only the detached copy is opened; SQLite can replay its copied WAL there. A
main-file-only immutable read would lose committed WAL data and is not used for
this current-state check. Original main/WAL/SHM/snapshot hashes must be unchanged.
The detached snapshot is separately checked for integrity and its earlier marker.

The application first restarts unchanged and must report healthy safety flags
and retain `after-dump`. It stops again. A separate helper then mounts only that
stopped synthetic volume read/write and stages a verified snapshot database.
It preserves the old main/WAL/SHM set under `atlas-drill-rollback`, replaces the
fixture database with root-owned mode 0600 snapshot state and verifies the marker.
The helper image root remains read-only. This is a test-volume operation, not a
production path mapping or a replacement for the durable five-unit live design.

Teamarr starts a third time using the restored fixture. Healthy startup, unchanged
safety flags and marker `snapshot` must pass. It stops again; a final read-only
helper validates the stopped set and confirms the database remains mode 0600.
Thus the run separately tests current-state persistence and readability of the
prepared private restore mode across real application startup.

## Acceptance limits and cleanup

Core tests execute real SQLite/WAL copying and fixture replacement, including
committed WAL content, snapshot/current separation, preserved old files,
permissions, link/size/corruption/journal rejection and unchanged source checks.
Docker lifecycle and production observation calls are mocked in unit tests.
The actual pinned-image stop/restart rehearsal still requires CT100 execution.

Every resource removal checks the random ownership label. Cleanup removes only
the invocation's containers and local volume; it never lists or prunes unrelated
resources. If Docker is unavailable, test resources can remain for review.
Production Dispatcharr/Teamarr/writer image/PID/start/mount observations and the
active deployment pointer must match before/after, including failure cleanup.
No raw logs, credential material, database contents or health payloads are printed.

This synthetic workload does not certify production-load shutdown, pending jobs,
all SQLite crash scenarios, storage power loss, full domain-data restoration,
or combined PostgreSQL/JWT/Teamarr/metadata-policy publication and rollback.
The fixture restore step is not crash-recoverable live transaction integration;
failure can discard the entire labelled synthetic volume during cleanup.
Existing format-2/3 live restore gates and the isolated publication scope remain.
