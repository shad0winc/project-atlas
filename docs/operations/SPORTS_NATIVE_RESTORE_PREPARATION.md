# Private native PostgreSQL restore preparation

Status: source-only native preparation adapter plus a synthetic pinned-image
rehearsal. No live restore command, production stop, live mount, policy activation
or deployment. Existing live format-2/3 recovery blocks remain unchanged.

## Supported preparation contract

`sports-postgres-prepare.py` requires a private operator-created
`/tmp/project-atlas-pg-prepare.*` workspace containing a cleanly stopped
`cold-cluster` copy and a checksummed `database.dump`. It runs non-root as the cold
copy's owner. It creates a new `restored-cluster`; existing targets/receipts are
refused, and failed work is retained for review. There is no live destination
parameter. Do not retry or publish a partially prepared cluster.

The cold copy preserves existing roles, password verifiers, role memberships and
role/database settings. This adapter cannot reconstruct lost roles or restore an
empty installation from a database dump alone. The caller must derive the admin
role, database name, owner identity and dump hash from reviewed canonical inputs.
It does not independently certify those values or create the cold copy from live
state. Cold-copy acquisition and source-container shutdown remain future wiring.

Require a matching installed PostgreSQL major version, no postmaster.pid, and
pg_controldata state exactly `shut down`. Reject links, special files, hardlinks,
unsafe ownership and bounded cluster/archive limits before copying. A dirty or
recovery-mode input is unsupported; it is never repaired in place. Source and
prepared cluster fingerprints bind the receipt to the checked copies.

## Native restore behavior

The adapter starts only the new copy, on a private Unix socket with TCP disabled.
It uses a controlled configuration, temporarily suppresses copied auto-config,
preload, archive and replication hooks, and restores original startup configuration
bytes after clean shutdown. Prepared production configuration is preserved, not
certified by the controlled rehearsal. No application settings or password values
are exported to logs or the host driver.

This revision supports ordinary public-schema application tables. Other schemas
and nonstandard table identifiers fail closed. It drops the new copy's public
schema to remove stale objects, accounts for whether the archive recreates that
schema, then runs pg_restore with --exit-on-error, --single-transaction and
--no-owner. ACLs are restored against preserved roles. Every nonzero native exit
or timeout fails preparation. Raw command output is bounded and not forwarded.

Require the restored table set to match the archive TOC, global role/settings
fingerprints and database properties to remain unchanged, then stop PostgreSQL
and recheck clean cold state. Only then write private PREPARED.json. A failure,
including failed shutdown, never creates a success receipt. The receipt is
`native-prepared-not-live-ready` with `ready_for_live_apply:false` and binds source
archive/cluster and prepared-cluster hashes. `validate_prepared` rechecks stopped
state and hashes without starting PostgreSQL.

## CT100 rehearsal

Run `scripts/diagnostics/sports-native-restore-prepare-drill.py` only in the verified
candidate worktree at its guarded base checkpoint. The host driver pins the
installed Dispatcharr image and both supplied source hashes. It passes code over
stdin into an owned one-shot container, with no network, no production mounts,
no env file, non-root UID/GID, read-only root, private tmpfs and bounded resources.
It compares production Dispatcharr image/restart timestamp and deployment pointer
before and after. Cleanup can remove only its randomly labelled container.

The synthetic drill creates roles and grants, captures backup rows, adds stale
post-backup objects, cleanly stops the source and exercises the actual adapter.
It verifies backup rows replace old rows, stale tables disappear, grants survive,
role/settings and cold-source fingerprints stay unchanged, copied startup hooks
are isolated, original config bytes are preserved, prepared-state revalidation
passes, and corrupt input creates no success receipt. All clusters must stop.
Core tests use temporary files and subprocess stubs; they are not a substitute for
the real pinned-image rehearsal.

## Remaining release boundary

Production cold-copy acquisition, identity/ownership attestation, association with
the unified Sports bundle, PostgreSQL/JWT/Teamarr/metadata-policy publication and
reversal under one durable transaction, crash recovery, remount/restart checks and
release acceptance remain open. This adapter does not extend the 16-surface live
replacement engine or enable any production apply path.
