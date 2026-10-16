# Isolated native PostgreSQL restore rehearsal

Status: synthetic validation tooling only. Not production apply, quiescence,
backup restore or rollback support. Live recovery formats 2 and 3 remain blocked.

## Observed installed-image contract

Read-only CT100 diagnostics identified Dispatcharr image
`sha256:e5d4b045b51519be4142a7baf7da6750ad33f80dcb0a77b8832c2ce930c6fe12`.
Its `/app/apps/backups/services.py` SHA-256 is
`58dbcca79aedbfd36732c5ac5a7caf2d3bc634d3fbf6c24614ba27878a04a450`.
Its `/app/docker/entrypoint.sh` SHA-256 is
`2c96dd61a1999654e32ac7b60999d0b9af196cded50952e4650f8530df426ceb`.
These observations do not certify arbitrary versions of the image.

The entrypoint tracks PostgreSQL, nginx and the uWSGI wrapper. Unexpected tracked
process exit triggers cleanup of application workers and PostgreSQL. s6 service
names observed in this image do not provide separate Dispatcharr app/database
controls. The PostgreSQL directory is `/data/db`. Production recovery therefore
needs an explicit whole-container shutdown and a separately verified database-only
helper; selectively killing guessed processes is not a quiescence contract.
The installed upstream restore helper tolerates some nonzero pg_restore exits.
Atlas must reject every nonzero restore exit and retain its recovery point.

## Synthetic drill boundary

`scripts/lib/sports-postgres-recovery-drill.py` uses only the Python standard
library and the pinned image's PostgreSQL binaries. Run it as UID/GID 65534 in a
one-shot container with no network, no production mounts, a read-only root,
private tmpfs /tmp, dropped capabilities, no-new-privileges and bounded resources.
Do not use Compose run, environment files, volumes-from, app initialization or
production backups for this drill. The helper creates its own temporary cluster,
Unix socket, role and three fixed-prefix synthetic databases. It constructs an
explicit libpq environment and disables TCP. No Django settings or existing
application state are read. An image-declared anonymous volume, if any, remains
new and disposable; no host data path is supplied. The --rm container removes it.

The drill generates a custom-format dump, restores both fixture tables and rows,
then proves a conflicting restore fails and leaves the earlier synthetic target
unchanged under --single-transaction. A truncated archive must fail without target
mutation. --list validation precedes restore; every nonzero exit is fatal, and
command timeouts/errors are sanitized. PostgreSQL must stop successfully before a
success receipt. The one-shot container boundary removes remaining processes on
exit. Temporary state is never copied into production.

## Evidence and remaining work

Core unit tests validate strict flags, preflight ordering, fatal nonzero/timeout,
input bounds and sanitized failures without PostgreSQL or new Python dependencies.
The actual CT100 container drill must additionally pass; mock tests alone are not
native restore evidence. The drill is not a policy/database pair restore test,
production-schema compatibility test, or proof of container bind remount behavior.

Remaining live work includes quiescing every writer, a durable pre-restore backup,
verified native restore preparation (Dispatcharr dump/JWT and Teamarr SQLite),
metadata database/policy staging with original ownership, journaled application
and reversal across all surfaces, container recreation/remount and health checks,
held failures and crash recovery. The existing live restore blocks are retained
until those paths and release-specific acceptance are complete.
