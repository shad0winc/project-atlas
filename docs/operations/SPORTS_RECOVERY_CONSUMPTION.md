# Isolated recovery after cooperative consumer writes

This source-only phase extends the private five-surface publication journal to
handle modified current state. It accepts only existing private
`/tmp/project-atlas-sports-publication.*` sandboxes. It does not change the live
restore shell pipeline, accept production destinations, control Docker services
or enable format-3 live restore.

## Authority and state transitions

`arm()` requires the existing publication to be applied, all five current and
preserved old hashes to match its plan, and incoming state to be empty. It
creates a private `consumption` marker, quarantine directory and exposure receipt
binding the original publication plan/status and five surface rows. It durably
records `open` before returning permission for a cooperating fixture writer.
An interrupted incomplete arm remains held; no writer may start without the
complete open record. Do not discard or recreate an incomplete journal blindly.

The marker transfers recovery authority to the new consumption journal. Generic
publication stage/apply/recover contexts reject a directory or symlink at that
name, including after recovery. The original publication PLAN and STATUS remain
frozen audit inputs. The authoritative lifecycle is
`consumption/STATUS.json`: open, sealing, sealed, rolling-back, reverted.
No finalize, purge, rearm or production activation API is added.

A cooperating writer uses `writer()` and holds its shared consumer lock for its
entire write lifetime, including any child writers. Recovery acquires that lock
exclusively and nonblocking, then acquires the same exclusive publication lock.
A live cooperative lease blocks sealing/recovery without changing status.
Process exit releases the lease. This is a cooperative protocol, not a service
stop detector or protection against arbitrary external writers.

`seal()` first persists `sealing`, which blocks all future fixture writers. It
checks all preserved old hashes and reads all modified current hashes twice.
The durable seal binds those stopped modified hashes to the exposure receipt.
A crash before the seal is committed can resume hashing under the exclusive
fence. An existing seal is never rebound to changed bytes. A sealed journal
with a missing final seal is held, rather than regenerated.

Recovery validates all five filesystem positions before moving any surface.
Each can be: modified current plus preserved old; quarantined modified state
plus preserved old with current absent; or restored old current plus quarantined
modified state. Other positions or changed hashes are held for review.
Persist rolling-back before moves, rename each modified current surface into
private quarantine, then restore its preserved old surface. Both rename parents
are fsynced. After all five original old hashes are verified, persist reverted.
Repeated recovery revalidates the restored and quarantined hashes.

Quarantine retains consumer-modified state for review. It is not deleted, merged
into the restored state or silently treated as the original prepared snapshot.
The old state is restored exactly; consumer changes are preserved separately.

## Verification and fixture scope

The diagnostic constructs explicit synthetic post-publication filesystem
journals. Its PostgreSQL and identity payloads are ordinary fixture bytes;
SQLite fixtures contain a small probe table. This does not validate native
PostgreSQL, JWT semantics, Teamarr startup or the metadata schema. Those remain
covered by the earlier native/combined diagnostics and future integration.
Both policy fixture generations and their modified form remain disabled.

Real child-process exit cases cover open, sealing, seal-written, sealed,
rolling-back, each of five quarantines, each of five restores, and reverted:
16 durable boundaries. Each case runs recovery twice and checks all restored
old hashes and retained modified hashes. Local regression additionally checks
active leases, killed writers, interrupted fsync after rename, tampering, missing
seals, scope/permission/link guards, partial arm and legacy API exclusion.
These are process-death tests with explicit fsync calls, not power-loss or disk
hardware certification.

The candidate diagnostic pins canonical main checkpoint
`57a2cfe5602449dbed069f4b11f9395093e79a20` and the unchanged deployment pointer.
Run the full core suite and diagnostic before committing. It uses only bounded
private temporary fixtures and read-only source/deployment checks. It does not
inspect or stop application containers. Failure preserves the applicable journal
contract during a run; completed disposable test fixtures are then cleaned.

## Remaining live integration requirements

Only cooperating writers that retain the lease and leave the five units in the
strict private operator format are supported. Adjacent Teamarr WAL/journal files,
unexpected entries, unsafe ownership/modes, links, special files or changed old
state stop recovery. The PostgreSQL directory can contain ordinary private
files, but this helper does not interpret native cluster state or repair it.

A real Docker stop barrier, production consumer identities/modes, grouped SQLite
WAL handling, native clean-shutdown validation, application restart acceptance,
all 16 filesystem surfaces and durable orchestration with maintenance/service
restart must be integrated before live restore is enabled. Arbitrary external
writes are outside the lease protocol. Existing live gates stay closed.

The combined diagnostic's source pin is updated to match the new legacy marker
check. Its behavior and native scope remain unchanged. No provider policy,
Sports activation, backup archive format, production data or deployment changes.
