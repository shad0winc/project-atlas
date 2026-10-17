# Synthetic Dispatcharr restored application restart drill

This source-only diagnostic extends strict native PostgreSQL preparation and
AIO cold-copy acceptance. It uses the exact installed Dispatcharr image and
normal entrypoint, exclusively with fresh disposable volumes and synthetic
database contents. Existing live backup/restore implementation and gates are
unchanged.

## Acceptance sequence

1. Verify candidate HEAD, deployment pointer, image and pinned utility, adapter
   and helper sources. Observe production Dispatcharr, Teamarr and Sports writer
   container images, start times, PIDs and mounts.
2. Create two uniquely labelled local volumes without driver options. Launch
   the normal AIO entrypoint on the first, without network, published ports,
   production environment or bind mounts.
3. Wait for PostgreSQL, uWSGI, Celery, Daphne and Redis processes, populated
   Django migrations, and a successful local HTML response on port 9191.
   Response bodies and application logs are not printed.
4. Insert a synthetic marker, capture a custom-format dump, then change the
   marker and add a table absent from the dump. Explicitly stop PostgreSQL fast
   before stopping AIO. Docker exit alone is insufficient.
5. Initialize only the empty second volume's root as 1000:1000, mode 0700.
   A nonroot helper mounts the stopped original read-only and the second volume
   writable. Require a clean source cluster and make a bounded temporary copy.
   Use the existing strict native adapter to restore into a clone, verify
   global roles, database properties and table set, then stop the clone cleanly.
   Copy the validated cluster to the second volume. Never prepare or start the
   original mounted cluster.
6. Start a second normal AIO application against that prepared cluster. Repeat
   process, migration and local HTTP checks. Require the snapshot marker and
   absence of the post-dump table. Write a new marker, stop PostgreSQL fast and
   the container, restart, and verify that new marker persists.
7. Stop the restored application again. A final helper mounts both volumes
   read-only, requires both clusters cleanly stopped and verifies original
   cluster and dump hashes against the preparation receipt.
8. Remove only the exact labelled disposable resources. Recheck production
   observations and the deployment pointer, including on failure. A first
   volume cleanup failure still attempts second-volume cleanup and observation.

## Isolation and limits

Image:
`sha256:e5d4b045b51519be4142a7baf7da6750ad33f80dcb0a77b8832c2ce930c6fe12`.
Candidate checkpoint: `bfa7c8a0bdb732b5ba01993955784c899fffc904`.
Deployment: `update-20261015T211211Z-632971`.
Run the candidate diagnostic before committing it. Changing the checkpoint
requires review; do not remove that guard to make a run pass.

All containers have network and restart disabled, no Docker log driver,
resource limits and no privilege escalation. Normal AIO uses the same bounded
capabilities as the earlier cold-copy drill. The initializer gets only CHOWN
and its empty target volume. Native preparation uses UID/GID 1000:1000, no
capabilities and a read-only root. Its temporary workspace is bounded tmpfs.
Only fixed receipts or sanitized error categories leave the helpers. Synthetic
credentials are fixed test values in the network-isolated fixture.

Acceptance requires a real CT100 PASS. Local tests cover isolation, attestation,
receipt validation, stop ordering and lifecycle failures; they cannot prove
real image startup or PostgreSQL restore. The local HTML check is a frontend
smoke check, not authenticated API, stream, tuner, provider or Celery task UAT.

Only PostgreSQL state is carried into the second volume. The original JWT,
media/cache files and other Dispatcharr state are not copied. Normal startup
may create fresh synthetic application files. JWT preservation and production
ownership conversion remain outside this component drill. Original cluster
and dump hashes must remain unchanged. The restored cluster may change during
normal startup and writes; its post-start hash is not required to match its
prepared hash.

Combined Sports publication including JWT, Teamarr and metadata/policy, durable
live transaction integration, cross-surface rollback, production load shutdown
and release/deployment acceptance remain separate gates. This does not certify
power-loss recovery or cross-surface capture consistency.

## Mount-order comparison correction

The first CT100 run passed 5290 tests and 693 subtests, native preparation and
the first restored application startup, but did not emit the overall drill
PASS. Read-only diagnosis found no leftover drill resources, a clean canonical
checkout, the unchanged deployment pointer and unchanged production container
identities. Twelve repeated observations showed stable mount contents but two
mount-list orders for the Sports writer.

The corrected final guard sorts each complete mount list by canonical JSON
before comparing it. It retains all entries, duplicates and every field; type,
source name/path, destination, access-mode, container image/PID/start-time or
other mount-field changes still fail. The shared cold-copy utility is unchanged.
Additional fixed progress markers identify persistence and cold verification.
Rerun the full core suite and real synthetic diagnostic before claiming PASS.
