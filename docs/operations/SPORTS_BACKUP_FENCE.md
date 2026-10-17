# Four-writer fence around isolated native baseline capture

This candidate rehearses the ordering of four-writer shutdown, native capture,
post-capture quiescence recheck, reverse writer startup, acceptance and private
maintenance release. It does not enable live restore or deploy production changes.

## Exact scope

Four disposable counter writers represent API, Sports controller, notifications
worker and Sports writer in the canonical shutdown order. Each uses the pinned
Teamarr image as a Python runtime with an explicit counter program, root UID/GID,
read-only root filesystem, no network, no capabilities, no healthcheck or restart
policy, resource limits, and one owned labelled local volume. These are generic
proxies, not the four actual Atlas service implementations.

The shell sources the unchanged restore command. Only its writer enumeration and
Docker executable boundary are configured for the four full fixture container IDs.
The actual `atlas_restore_require_writers_running`, `atlas_restore_stop_writers`,
`atlas_restore_require_writers_quiesced`, `atlas_restore_start_writers`, and
`atlas_restore_wait_for_writers` functions run. The real execution-exclusion flock
uses a private runtime directory. Private maintenance and owner markers surround
the capture and acceptance sequence; production ingress/lock APIs are not invoked.

After all four stop normally, the parent verifies immutable SQLite counter reads,
clean exit codes, zero PIDs, no OOM, no sidecars, and exact owned volume/container
identities. The owned stopped volumes can still be referenced by their stopped
counter containers. No arbitrary or production volume is accepted.

The native capture continuation then seeds the native test databases and creates
the PostgreSQL dump and Teamarr snapshot while all four proxies are stopped.
This ordering is explicit: native apps start before the fence, but dump creation
is deferred until after the four-writer stop proof. The normal native lifecycle
then fast-stops PostgreSQL, stops/removes native app objects, performs stopped
capture, and prepares the strict dump-derived baseline. The continuation must run
exactly once. Existing standalone diagnostic defaults retain their earlier path.

Each stopped counter database is copied using the existing checked/fsynced private
copy helper. Copy values must equal stopped values before and after native capture.
The real shell quiescence recheck then runs before reverse startup. After restart,
each counter must advance, while all private counter copies and the complete
strict native baseline remain byte-identical. Only then are private controls
released. The existing metadata/native consumption and maintenance-abort rehearsal
continues afterwards, including restored native app and persistence restarts.

## Verification and failures

Unit tests exercise the real shell helpers with a stateful Docker stub: ordered
four-writer stop, reverse startup, held kernel exclusion, stopped capture, callback
failure, unclean exit refusal, a writer restarting during capture, post-restart
acceptance failure, identifier/private-root checks and callback gating. Unit
tests do not run Docker. CT100 supplies real disposable counter containers and
native applications; full core tests and the entry point must pass there.

On a capture or quiescence failure no restart is requested by the controller.
On a post-restart acceptance failure private controls remain held even though
writers may already be running. Temporary fixture cleanup subsequently stops
and removes exact owned counter objects and their unreferenced volumes. No force
remove, prune, broad name matching or production service names are mutation targets.
The private shell group and pipe handles are bounded and cleaned.

## What this does not certify

This verifies ordering and frozen counter/native captures. The four actual Atlas
service programs, their cross-service transactions, production maintenance/ingress,
full archive creation/publication/validation, full 16-surface restore, Scheduler
workload and production backup coherence remain separate acceptance gates. These
are not counters embedded in production Atlas schemas. The existing native dump
and SQLite source probes are fixture data, not authenticated business API actions.

Private controls are temporary test state, not a new crash-resumable production
journal. No power-loss claim, arbitrary Docker admission exclusion, or 15-case
SIGKILL rerun is introduced. Operation assumes a trusted serial fixture controller.
Only the three existing production containers' bounded identity/mount observations
are read, with no Config.Env, private logs, database/JWT bytes or raw stderr output.
Overall success still requires unchanged canonical checkout, active deployment
pointer, production observations, and cleanup of all owned fixtures.

## Run before committing

At main baseline `c9266e38b52300f93e1b61305ea46149d318b1cd`:

```bash
git diff --check
python -B -m pytest -q tests/core
python -B scripts/diagnostics/sports-backup-fence-drill.py
```

Expect `SYNTHETIC_BACKUP_FENCE_DRILL=PASS` and
`STATE=isolated-four-writer-native-backup-fence-not-deployed`.
Follow RC1-first CI/merge, identical main CI/merge, canonical fast-forward only.

Media browse acceptance requested after Sports is recorded separately in
`V1_MEDIA_BROWSE_ACCEPTANCE.md`; those UI changes are queued, not implemented here.

## Counter volume initialization correction

The first CT100 run passed 5387 core tests and 767 subtests, then refused the
stopped counter volume because entries beyond `state.db` existed. The location
was confirmed with a source-only traceback; no exception payload was printed.
The failed fixtures were cleaned and production identities remained unchanged.

Docker can initialize an empty volume with files from the image mount target.
The counter fixture does not need image data: its mount now explicitly requests
`volume-nocopy`, and inspect attestation requires `VolumeOptions.NoCopy=true`.
This removes the image-population path instead of allowing unknown files. The
exact one-file guard is retained, with regression checks rejecting seed files,
SQLite WAL/SHM/hot journals and symlinks. The actual unexpected entry names were
not collected, so image population remains the explanation being tested by this
correction; the new CT100 run must confirm the result.
