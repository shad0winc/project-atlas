# Unified private Sports recovery preparation

Status: source-only staging primitive. No live restore, publication, service stop,
policy activation or deletion of existing state. Format-2/3 live restore blocks
remain unchanged. No CLI action invokes this primitive on production backups yet.

## Input boundary

`sports-recovery-bundle.py` prepares the Sports portion of an already staged
format-3 archive. Its caller must first run the existing full archive/staged and
consumer validators for the filesystem surfaces. This helper independently checks
the bounded native manifest/checksums and detached metadata/policy inputs; it is
not a substitute for validating the rest of the backup.

The input is an operator-owned private `/tmp/project-atlas-restore.*` directory.
Native artifacts must be either all captured or all absent. Captured input has
exactly the declared Dispatcharr custom-format dump, persistent JWT and Teamarr
SQLite database, plus native manifest/checksums. Partial state, undeclared files,
links, unsafe modes, duplicate/malformed checksum rows and oversized inputs fail.
PostgreSQL header and checksum are checked here; semantic pg_restore validation
and restoration remain required. The earlier real PostgreSQL rehearsal does not
turn any arbitrary dump into a validated production restore.

Unified pair preparation requires metadata recovery manifest version 2 with both
the database and exact policy bytes. Existing version-1 database-only inspection
and validation remain supported by the recovery library, but this helper refuses
to guess which policy to publish. Cache/budget/immutable aliases are preserved by
copying the detached database; alias ownership/schema and policy are revalidated.

## New private output only

The helper creates its own unique `/tmp/project-atlas-sports-prepare.*` workspace.
Copies are bounded and streamed, verified against snapshot checksums, fsynced and
validated before one rename publishes a `bundle` inside that new workspace.
Source contracts are rechecked before publication. A failed operation removes only
its own new workspace, retaining original staged and live state.

All actual output directories/files remain operator-owned 0700/0600. No chmod or
chown is performed on existing/live objects. Numeric dispatcharr/teamarr/writer
identities are explicit preparation inputs. BUNDLE.json records publish_owner,
publish_mode and directory ownership intentions separately from current staging
permissions. These identities are not certified against deployed consumers here;
a future transaction must derive and recheck them from canonical configuration.
Policy publication intends root ownership with the writer group; metadata intends
writer ownership. The new metadata lock is empty and does not reset database
attempts, holds, cache or aliases.

Every bundle has `ready_for_live_apply: false`. PostgreSQL is marked
`native-restore-required`. Absent native state is `absent-unresolved`, never an
instruction to erase an installed backend. The bundle revalidator enforces exact
members, fixed paths, checksums, private modes/ownership, policy and SQLite
integrity and rejects any attempt to mark the bundle live-ready.

Detached metadata validation uses an explicit immutable read-only SQLite option;
the live metadata validator retains its existing locked, WAL-aware default.
Teamarr is validated on the detached copy with immutable read-only access. Input
SQLite files are not opened by the preparer, and no input sidecars are generated.

## Evidence and remaining integration

Core tests use synthetic format-3 fixtures and isolated temporary directories.
They cover complete and absent-native preparation, input immutability, budget and
alias preservation, planned ownership, unsafe input and cleanup, corrupt artifacts,
changed source contracts and post-preparation tampering. Real non-root publication
and native production-schema compatibility remain unverified by this staging test.

Next work is native PostgreSQL restore preparation, JWT/Teamarr publication,
metadata/policy application within the same durable recovery transaction, fault
and crash reversal across all surfaces, container remount/restart verification
and release-specific live acceptance. This helper does not extend the existing
16-surface live replacement registry or unblock format-2/3 apply.
