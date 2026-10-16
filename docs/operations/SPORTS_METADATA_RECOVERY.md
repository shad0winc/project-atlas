# Sports metadata recovery

Status: capture and isolated staging support; production activation and live
native restore remain open. This change does not close the v1 restore gate.

## Durable state boundary

The canonical host directory is
`${ATLAS_RUNTIME_CONFIG_DIR}/private/sports-metadata`. It must be a private 0700
directory; database and lock must be regular 0600 files with the same owner as
the directory. The backup command reads this location directly as the operator.
No directory, Compose bind, metadata provider, refresh loop, credential or alias
is provisioned or enabled here.

An absent installation produces the existing recovery-format-2 archive. A present
but incomplete/unsafe installation fails backup publication. Removing or renaming
an active installation to bypass capture is not a supported rollback procedure.
The source directory permits only the SQLite database, writer lock and SQLite
journal/WAL/SHM files. Symlinks and unexpected entries fail validation.

## Consistent capture

`scripts/lib/metadata-recovery.py` acquires the same advisory lock as the writer,
without creating a missing lock or changing ownership/permissions. Acquisition is
bounded to 12 seconds. SQLite online backup includes committed WAL content and
uses an eight-second copy deadline, then switches the private destination to
DELETE journal mode so no WAL/SHM sidecar is needed. Capture never raw-copies a
live database. Failed work is removed before publication.

A snapshot contains only `database.sqlite` and `MANIFEST.json` in a 0700 directory,
with files 0600. The manifest records recovery version, database schema and a
SHA256 checksum. Locks and sidecars are not archived. Validation checks SQLite
integrity, exact schema-1 tables/columns, source identity shape, provenance-digest
shape, canonical owner self-mappings and alias uniqueness. Evidence hashes remain
provenance references, not proof that two real events match. Snapshot database
size is bounded at 512 MiB and alias count at 100,000; validation is time-bounded.

## Archive compatibility and validation

An archive with captured metadata uses recovery format 3. The original 16
filesystem replacement surfaces and their manifest/checksum contract remain
unchanged. The native Sports backend recovery artifact is also required and
validated as in format 2. Metadata has its own private artifact and manifest.

The new reader validates formats 1, 2 and 3. Format 3 requires valid metadata;
formats 1/2 cannot carry it under an undeclared root. Safe-member checks reject
symlinks, hard links, duplicate or additional metadata artifacts and unsafe paths.
Isolated staging validates metadata after extraction. Older readers reject format
3, so retain a compatible reader with archives that contain identity state.

## Recovery limits before activation

SQLite capture and isolated reopen preserve existing canonical mappings. This
is not production restore UAT. Native format-2 live restore was already unsupported;
format 3 is likewise rejected by both the filesystem restore planner and live
preflight before deployment mutation. Never remove metadata or downgrade an
archive header to force it through the filesystem engine.

Before enabling production metadata: provision the selected private state mount,
confirm backups from that exact path, implement/test native live restore and
rollback behavior while preserving canonical owners, include the metadata writer
in any relevant live quiescence boundary, select refresh policy within budget,
and complete user discovery/follow/playback acceptance. Public maintenance alone
does not pause background refresh. Capture uses SQLite consistency and the shared
writer lock rather than assuming maintenance stops the writer.

## Persistent policy artifact

The outer recovery format remains 3. Existing metadata manifest version 1 archives
remain readable. When `private/sports-metadata-policy` is present alongside the
metadata database, capture requires its strict server-owned directory/file
contract and validates policy bytes with the worker's parser. Metadata manifest
version 2 adds `policy_sha256` and exactly one `refresh-policy.json` artifact
(mode 0600, at most 16 KiB). Archive and staged validation enforce the checksum,
policy schema and exact member set. Invalid or incomplete installed policy fails
the backup instead of silently producing a database-only archive. A policy without
a metadata database also fails; absent legacy installations remain absent.

The captured policy is a separate configuration observation. SQLite backup under
the shared metadata lock preserves database consistency, but does not assert
that an in-flight provider request used the captured policy generation. Future
live restore must quiesce the private writer and reconcile both artifacts. No
live policy/database apply or rollback support is introduced here; format-3 live
restore remains explicitly blocked before deployment actions.
