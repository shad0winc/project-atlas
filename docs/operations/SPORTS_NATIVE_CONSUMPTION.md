# Native stopped-state consumption rehearsal

This fixture-only drill connects the existing Docker lifecycle fence to capture,
import and rollback of committed native PostgreSQL and Teamarr SQLite changes.
It does not enable production restore, deployment or direct application writes
to journal directories. Existing live restore gates remain closed.

## Exercised sequence

1. Start fresh pinned Dispatcharr and Teamarr applications on separately owned,
   labelled local volumes. Use normal image entrypoints/commands, network none,
   no published ports, and synthetic fixtures only. Teamarr scheduler is off,
   dry run is true, and startup cache refresh is skipped.
2. Seed native probe tables, require normal readiness, stop PostgreSQL fast and
   detach both app objects through the lifecycle fence. Capture this baseline.
3. Construct an unexposed private journal with baseline PostgreSQL, JWT and
   Teamarr snapshot bytes in both the preserved old set and initial current
   set. The two metadata/policy surfaces remain explicit filesystem fixtures;
   this drill does not claim Sports writer acceptance or full metadata schema
   integration. Arm cooperative exposure before starting the write phase.
4. Materialize the baseline into new empty owned volumes, assigning PostgreSQL
   UID/GID 1000 and JWT/Teamarr UID/GID 0. Start the apps and arm their lifecycle
   identities against this journal. Commit changed probe markers and a new
   PostgreSQL table using database clients inside the running fixture apps.
   These are native database commits, not authenticated business API tests.
5. Detach those exact app objects, capture their stopped state, and import only
   the three native surfaces under the cooperative writer lease. Source native
   volumes remain unchanged and unreferenced through capture and recovery.
6. Seal current state under the cooperative exclusive lock, verify the native
   receipt against the seal, quarantine modified state and restore old state.
   Repeat recovery and verify all old hashes plus quarantined captured hashes.
7. Materialize restored baseline into another set of new empty owned volumes.
   Require normal Dispatcharr frontend/process readiness and Teamarr health.
   Verify original probe markers and absence of the table created after the
   baseline. Stop and restart these apps once more and repeat marker checks.
   Finally stop and detach them through a fresh lifecycle ledger.

The baseline is a clean native cold checkpoint, not a pg_dump restoration in
this drill. The existing strict dump preparation and native restore diagnostics
remain separate requirements. This rehearsal must not be presented as retiring
that gate or as direct native consumer access to journal directories.

## Stopped capture and ownership

Only CT root may run this helper. Volume identities are derived by the existing
lifecycle helper from fixed role names and lowercase UUIDs. Local driver, no
volume options, matching ownership labels and zero container references are
required. Docker user namespace remapping is refused. The returned mountpoint
must equal the daemon DockerRootDir plus `volumes/<derived-name>/_data`, with no
symlink at any path component. No arbitrary bind paths or production volume
names are accepted. Direct filesystem access is confined to these private,
owned disposable local-volume mountpoints while no app object references them.

PostgreSQL source entries must be owned by 1000:1000, regular files/directories,
not writable by group/others, without symlinks, hardlinked files or special
nodes. PG_VERSION must be 17 and postmaster.pid absent. Native clean shutdown
was already verified before container detachment. JWT is root-owned mode 0600
and bounded to 16 KiB. Captured copies become operator-private directories 0700
and files 0600. Byte shapes are checked before/after copy; normalization applies
only to copies. Restored PostgreSQL copies receive 1000:1000 again.

Teamarr capture copies the stopped main database and every existing WAL/SHM
sidecar together. Hot rollback journals, orphan SHM, links, unsafe ownership,
unsafe modes and files over 512 MiB are refused. Only the copied set is opened
to incorporate WAL. SQLite quick_check and the expected probe marker must pass.
A SQLite backup produces a detached DELETE-journal snapshot, verified again
without sidecars. Original cold file hashes and membership are checked again.
A real WAL-only committed row is covered by the unit fixture. Native file sets
may contain WAL or may already be checkpointed; the receipt reports which.

All filesystem trees have a 100,000-entry / 2 GiB bound. Copy helpers use private
new destinations, check byte shapes, assign only fixed owners and fsync output.
Source volumes are never used as restoration destinations. New Teamarr targets
must be empty, so an old WAL/SHM/journal cannot survive snapshot materialization.

## Import and retry boundary

A capture receipt binds the lifecycle ledger, marker, WAL observation and three
normalized hashes. The journal's native import receipt and prior current copies
are retained. `importing` is durable before current surfaces are replaced;
`imported` is written only after all copies and detachment checks pass. Partial
import is deliberately held for review, not automatically reconstructed or
recovered by the native wrapper. Captured hashes must match the sealed journal
before the first undo. Journal rollback itself retains the existing durable
retry/position semantics and repeated recovery checks.

The native wrapper is the required entry point for this drill's recovery.
The lower-level cooperative filesystem primitive has no native import or
Docker semantics. The trusted serial controller must exclude unrelated
privileged Docker/filesystem operators; there is no global admission lock.
This is not a production recovery interface or hardware power-loss proof.

## Verification and cleanup

Run the full CT100 core suite, then, before committing:

```sh
python -B scripts/diagnostics/sports-native-consumption-drill.py
```

The diagnostic pins all loaded support sources and the canonical source HEAD.
It observes production container identity and canonicalized mount contents,
checks the deployment pointer and clean canonical checkout, and repeats those
checks during cleanup. Only exact owned disposable resources are removed;
cleanup attempts each recorded resource even if another cleanup fails. Overall
PASS requires successful cleanup and unchanged-production observations. No raw
JWT, database contents, container environment, logs or feed URLs are printed.

Local tests cover WAL snapshots/source preservation, copy safety, volume-path
and user-namespace refusal, import/quarantine/retry, interrupted import, missing
Docker fence and native seal tampering. The UID 1000 ownership conversion case
requires a runtime able to assign that UID and is exercised on CT100. The real
native app, PostgreSQL and Docker acceptance runs also require CT100.
