# ADR-0023: Backup and Restore Recovery Boundaries

## Status

Accepted and validated by M-023.25.

## Context

Project Atlas already provides an atomic configuration-backup command and a
deployment rollback system, but those mechanisms solve different problems.

The existing `atlas backup` command captures a curated subset of the project
tree and publishes a validated `atlas-*.tar.gz` archive atomically. M-023.22
verified its storage-exhaustion and partial-publication boundaries.

M-023.25 discovery demonstrated that important authoritative Atlas state lives
outside that project-tree archive, including:

- Atlas users and profiles;
- identity and favorites state;
- scheduler state;
- Atlas event/subscriber state;
- ARI/retention state; and
- Sports subscriptions, recording metadata, and scheduler state.

Media-request persistence is implemented by `JsonMediaRequestRepository`. Its
durable file is `<repository-root>/requests.json`; the repository root is
injected by its caller rather than hard-coded by the persistence class. Backup
coverage must therefore resolve the authoritative configured request repository
instead of creating a second request store.

Discovery also found that current archives can contain module `.env` files
because `modules/` is captured recursively. Production backup files were mode
`0644`. Secret-bearing recovery material must not become broadly readable
merely because it is stored in a backup archive.

Finally, the backup CLI currently treats an unrecognized option such as
`--help` as a request to create a backup. During discovery this caused an
unintended but valid backup and invoked the documented ten-backup retention
policy. Recovery interfaces must fail closed at their command boundaries.

## Decision

Atlas will distinguish a configuration archive from a recovery-capable backup.

The governing invariant is:

> A backup is not recoverable merely because an archive exists. Atlas must
> explicitly identify, protect, validate, and successfully restore every
> authoritative state surface that it claims before that backup can be
> considered recovery-capable.

Restore operations have a second invariant:

> No unvalidated backup content may be extracted directly over live production
> state.

## Versioned Recovery Format

M-023.25 will introduce an explicit recovery format rather than silently
changing the meaning of historical archives. A recovery-capable archive must
identify:

- recovery-format version;
- source Atlas version and Git commit;
- creation time;
- explicitly captured state surfaces;
- archive-relative paths for those surfaces;
- required versus optional surfaces;
- cryptographic checksums; and
- restore policy for each surface.

Historical archives that predate the recovery format remain valid historical
configuration archives. They must not be silently treated as state-complete
recovery archives.

## State Classification

### Authoritative state

Authoritative state cannot safely be reconstructed from generated output or
provider observations alone. It includes, when configured and present:

- user registry and user profiles;
- identity and invitation state;
- favorites;
- media-request repository state;
- scheduler task definitions;
- event/subscriber recovery state required for consistent replay;
- ARI/retention state required by retention behavior;
- Sports subscriptions;
- Sports recording metadata; and
- Sports task-scheduler state.

Every authoritative surface requires an explicit backup and restore contract.

### Reconstructible or transient state

Generated output and liveness information do not become authoritative simply
because they live under a configuration directory. Examples include health
reports, controller heartbeats, generated Sports M3U/XMLTV output, routine
logs, Python bytecode caches, and process locks. These should normally be
regenerated rather than restored.

### Deployment audit state

Deployment records are valuable audit evidence, but host-local Docker image
identities, paths, locks, and prior deployment conditions are not portable
rollback capability. A recovered host must establish a new verified deployment
baseline before future rollback claims are made.

## Explicit Inclusion

Recovery coverage is allowlist-driven. Atlas must not recursively capture a
runtime root and assume every member has identical recovery semantics. Each
restorable surface requires a source, archive destination, validation rules,
checksum coverage, and restore destination.

Secret-bearing files may be included only when intentionally declared. The
backup system must not acquire them accidentally through recursive parent
directory capture.

## Confidentiality

Recovery archives may contain identity information and explicitly approved
secret-bearing configuration. Therefore:

- new recovery archives and partial artifacts must be owner-only;
- manifests and diagnostics must not print secret values;
- copying an archive off-host requires equivalent or stronger protection; and
- filesystem permissions are not encryption or off-host disaster protection.

## CLI Safety

Mutating commands require recognized syntax. Read-only list/help/inspect/verify
operations must remain read-only. Unknown backup or restore arguments must fail
without creating an archive, deleting an archive, or invoking retention.

A parsing error must never fall through to a mutating default.

## Backup Publication

The existing storage-safe publication contract remains:

1. create a protected partial artifact;
2. capture only declared content;
3. validate archive structure;
4. validate recovery metadata and checksums;
5. atomically publish the canonical archive; and
6. only after successful publication apply explicit retention.

Failure before publication must not produce a canonical success artifact.

## Restore Pipeline

Live restore is a transaction, not an extraction command:

1. identify the requested archive;
2. validate format and reject unsafe archive paths;
3. extract into isolated staging only;
4. validate checksums and every declared state surface;
5. construct and report the restore plan;
6. acquire mutual exclusion with production deployment/update operations;
7. capture a pre-restore recovery point;
8. enable maintenance when live state will change;
9. quiesce affected writers;
10. apply validated state using bounded replacement operations;
11. restart or reload affected consumers when required;
12. run post-restore state and service verification; and
13. reopen traffic only after verification succeeds.

Failure after production mutation begins remains observable and fails closed.

## Cross-Surface Consistency

Related state must be restored from one coherent recovery point. Event logs and
subscriber cursors must not be mixed independently, and Sports recording state
must remain compatible with the subscriptions/scheduler state required to
interpret it.

## Media and Third-Party Application Data

Atlas recovery archives do not contain the media library. M-023.25 also does
not claim complete recovery for Jellyfin, Radarr, Sonarr, qBittorrent, or other
third-party application databases merely because their volumes live under
`/mnt/storage/configs`. Those require separate explicit recovery contracts.

## Restore Testing

Restore behavior must first be proved against isolated temporary roots. A
controlled production recovery exercise may occur only after isolated restore,
failure-boundary, and regression tests pass.

## Single-Host Limitation

Backups under `/mnt/storage/backups/atlas` share the host/storage domain with
Atlas. They protect against many configuration and software failures but not
loss or corruption of that storage device. Final M-023.25 documentation must
state this limitation and recommend an independent storage domain.

## M-023.25 Validation Evidence

The decision is implemented and production-validated. Format 1 now captures
explicit recovery metadata, checksum-covered allowlisted state, owner-only
archives, and state-completeness semantics. Restore provides read-only
inspection/verification, isolated safe staging, consumer validation, an
operator-visible plan, transactional live replacement, and explicit
`--confirm-live` apply/resume/abort boundaries.

The final automated Core regression passed 2,947 tests plus 104 subtests. A
controlled exercise from protected production source `483085fa` then completed
restore `restore-20260808T174153Z-3004055`. The transaction created and
validated a pre-restore state-complete recovery point, isolated public traffic,
quiesced the API/Sports/Notifications writers, applied and consumed the staged
state, restarted all three writers healthy, restored normal ingress at 24/24,
and released maintenance and the shared deployment lock. The deployment
baseline remained verified and unchanged.

The exercise validates Atlas state recovery only within the declared scope. It
does not change the single-host, media-library, third-party application data,
or off-host disaster-recovery exclusions in this decision.

## Consequences

Backup completeness becomes explicit and testable, runtime state receives
deliberate recovery ownership, and legacy configuration archives cannot be
mistaken for full disaster recovery. The cost is a versioned format, state
validators, representative recovery fixtures, and intentional live-restore
ceremony. That ceremony is appropriate for a destructive production boundary.
