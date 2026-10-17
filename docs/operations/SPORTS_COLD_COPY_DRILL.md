# Synthetic AIO shutdown and cold-copy rehearsal

Status: isolated pinned-image rehearsal only. No production stop, restart,
backup read, mount, cold-copy acquisition, restore, activation or deployment.

## Scope and identities

The CT100 mapping probe confirmed that Docker and CT100 share the same user
namespace and native bind-mounted file identities. CT100 is unprivileged with
UID/GID map `0 100000 65536`: CT UID 0 corresponds to PVE UID 100000 and CT UID
1000 to PVE UID 101000. Use CT IDs for operations within CT100. Dispatcharr PG
is 1000:1000; JWT and Teamarr state are 0:0. This is observed deployment evidence,
not permission to change existing ownership or stop production containers.

Run `scripts/diagnostics/sports-cold-copy-drill.py` only in its verified candidate
worktree at the guarded base checkpoint. The driver pins the installed Dispatcharr
image, entrypoint and init/uwsgi source hashes. It does not copy production env
values, application settings, files or credentials into the fixture.

## Owned synthetic resources

Each invocation creates a random labelled local Docker volume and two labelled
containers. The fresh volume persists across app shutdown; a tmpfs `/data` would
disappear on stop and cannot prove acquisition of stopped state. There are no
host bind mounts, devices, published ports, production volumes or external network.
The image must declare no additional volumes. Exact owned mount names, label,
image, network and root-filesystem mode are checked before starting containers.

The AIO fixture uses its actual original entrypoint and a disposable writable
image layer for migrations, static assets and generated config. It has a fresh
`/data` volume, fixed synthetic database and credentials, UID/GID 1000 application
identity, explicit capability allowlist, no-new-privileges, CPU/memory/PID limits,
bounded startup time, private tmpfs `/tmp`, no restart and no Docker log storage.
No provider, guide, channel, user or recording data is imported.

Readiness requires the AIO PostgreSQL/uwsgi/Celery/Daphne/Redis process names and
a nonempty Django migration table. That is a startup checkpoint, not full HTTP,
playback or production-load acceptance. The fixture creates one marker table,
captures a custom dump, then changes its row to distinguish the stopped cluster
from the earlier dump. Logs, SQL output and generated credential material are not
forwarded to the terminal.

## Stop and cold-copy acceptance

The initial CT100 rehearsal passed Core tests and AIO startup/container exit, but
the native clean-state guard rejected the cold copy. That run did not establish
clean shutdown; its container-exit marker must not be interpreted as PG acceptance.
An attempted extra diagnostic line was filtered by the host driver and did not
identify which clean-state check failed. The correction labels those checks.

The revised driver first executes PostgreSQL 17 pg_ctl fast/wait shutdown as
UID/GID 1000 inside only its labelled AIO fixture, with a 20-second native timeout.
This tests an explicit native stop before the entrypoint's immediate-stop fallback.
It then stops only its owned AIO fixture with a 35-second Docker timeout. It requires
exited state, no running PID, exit 0 or 143 and no OOM. A separate non-root helper
then mounts only that volume read-only at `/source`, with a read-only image,
no capabilities, no network and private tmpfs scratch.

The helper requires PostgreSQL 17, absence of postmaster.pid and pg_controldata
state exactly `shut down` BEFORE copying or starting anything. This guard and the
native preparation adapter remain unchanged. A dirty source
fails; it is never restarted or repaired to obtain acceptance. The source cluster
is fingerprinted, copied to a new private workspace and rechecked. The existing
native preparation adapter restores the dump into a second copy and validates its
receipt. A controlled clone startup verifies the restored marker is `snapshot`,
then cleanly stops again. Original volume cluster and dump hashes must remain
unchanged. Only the new clone runs; the cold source never does.

The helper volume is read-only, but the local Docker volume is disposable test
storage, not a production snapshot. The fresh AIO workload is not representative
of production shutdown duration or active recordings. Cold copies stay in tmpfs
and are removed after verification. The helper uses bounded copying and native
command deadlines. Fixture volume disk usage is not a filesystem quota; cleanup
removes it after success/failure, subject to Docker availability.

## Cleanup and results

Cleanup checks the random ownership label before removing either container or
the local volume. It never lists, prunes or removes unrelated resources. Missing
resources require a working daemon check; ambiguous cleanup fails closed. On
failure, report only the phase and fixed helper category, not raw logs. If Docker
is unavailable, labelled test resources may remain and require explicit review.
The production image/PID/start timestamp/mount observations and active deployment
pointer must match before and after, including failure cleanup.

Core tests validate resource/identity/cleanup guards and lifecycle ordering with
Docker/native commands mocked. The real rehearsal must pass on CT100 separately.
Success means synthetic AIO shutdown, read-only cold-copy acquisition and native
restore preparation passed for this pinned image. It does not enable live restore
or attest Teamarr shutdown, production load, combined publication/rollback,
remount/restart compatibility, or full Sports UAT.
