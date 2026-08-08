# Backup and Recovery

Project Atlas v1.0 provides a state-complete Atlas recovery path. Backup and
restore are explicit transactions: an archive is not treated as recovery-capable
merely because it can be opened, and unvalidated archive content is never
extracted directly over live production state.

## Create a Backup

The canonical operator entry point is:

```bash
atlas backup
```

Add an operator note when useful:

```bash
atlas backup --notes "before maintenance"
```

Read help or list completed backups without mutation:

```bash
atlas backup --help
atlas backup --list
```

Production backups are stored under `ATLAS_BACKUP_DIR`, currently
`/mnt/storage/backups/atlas`. The normal production policy retains the newest
10 canonical `atlas-*.tar.gz` archives. A successful new backup can therefore
rotate the oldest canonical backup.

## Recovery Format 1

A state-complete Format 1 archive contains project configuration plus explicit
recovery metadata and allowlisted authoritative Atlas state:

```text
BACKUP_INFO.txt
RECOVERY_FORMAT
RECOVERY_MANIFEST.tsv
SHA256SUMS
state/
```

The recovery registry covers users, optional identity invitations, favorites,
optional Media Request state, scheduler state, runtime events and subscribers,
retention/ARI state, Sports subscriptions, Sports recording metadata, and the
Sports scheduler. Optional state is represented explicitly as absent rather
than silently invented during restore.

Each declared state file is covered by `SHA256SUMS`. Required surfaces must be
present and valid. Recovery archives and partial artifacts are owner-only.
Unknown backup options fail closed and do not create an archive or invoke
retention.

Archive metadata currently records `restore-unverified` when the archive is
created. That is a per-archive creation-time capability marker; it is not a
claim that M-023.25 live restore was untested. M-023.25 separately proved the
Format 1 restore implementation through isolated and controlled production
validation.

## Storage-Safe Publication

Atlas creates a protected `.partial` archive, captures declared content,
validates the tar structure, recovery manifest, state completeness, and
checksums, and only then atomically publishes the canonical `.tar.gz` name.
Retention runs only after successful publication. A failed creation or
validation cannot publish a canonical success artifact.

## Read-Only Restore Inspection

Inspect metadata without asserting validity:

```bash
atlas restore inspect <archive>
```

Validate recovery format, manifest, checksums, and state completeness without
changing live state:

```bash
atlas restore verify <archive>
```

## Isolated Restore Staging

Safe restore preparation is deliberately separate from live mutation:

```bash
atlas restore stage <archive>
atlas restore validate-stage <staging-root>
atlas restore plan <staging-root>
```

`stage` rejects absolute paths, parent traversal, symbolic-link hazards, and
undeclared recovery content before extracting into a private temporary root.
`validate-stage` loads the staged state through Atlas consumer contracts and
proves validation does not mutate staged or live state. `plan` reports every
replace/remove action, consistency group, staged source, live destination, the
writer quiesce set, and the required safety boundaries.

## Live Restore

Live mutation is deliberately difficult to invoke accidentally:

```bash
atlas restore apply <staging-root> --confirm-live
```

Production apply requires all of the following before mutation:

- the checkout is clean `main` exactly equal to `origin/main`;
- the current deployment baseline is verified;
- the staged recovery state validates;
- the shared deployment/update lock is available; and
- the operator supplies the exact `--confirm-live` authorization.

The live transaction then:

1. acquires the shared deployment/update lock;
2. enables maintenance and verifies public isolation;
3. creates and validates a fresh pre-restore production recovery point;
4. quiesces `atlas-api`, `atlas-sports-controller`, and
   `atlas-notifications-worker`;
5. publishes the staged state with bounded transactional replacement;
6. validates the actual live state through Atlas consumers;
7. restarts and verifies the affected writers;
8. runs Atlas, module, and maintenance-aware ingress verification;
9. reopens public ingress and verifies normal routing; and
10. finalizes the state transaction and releases the shared lock.

The deployment baseline is not a restore payload and remains authoritative; a
state restore does not manufacture a new deployment baseline.

## Failure, Resume, and Abort

Failure after live mutation begins is fail-closed. Atlas retains maintenance
and the shared lock instead of pretending that recovery completed. Do not
manually delete `update.lock` and do not manually disable maintenance to bypass
a held restore.

After diagnosing the recorded restore transaction, the explicit recovery paths
are:

```bash
atlas restore resume <restore-id> --confirm-live
atlas restore abort <restore-id> --confirm-live
```

`resume` revalidates the applied state and completes verification/finalization.
`abort` transactionally restores the displaced pre-apply state, validates it,
recovers the writers, verifies public service, and then releases the safety
boundary.

Restore audit records are retained beneath
`/mnt/storage/configs/atlas/restores/<restore-id>`.

## M-023.25 Controlled Production Validation

The certified production source `483085fa` completed controlled restore
`restore-20260808T174153Z-3004055` from a freshly captured current-state
archive. The source archive SHA-256 was
`dcc0895d30e06c8561c6ed95a9a010a212485b25d49ee6d90cdfbafe7ea5f6d8`.
Immediately before mutation Atlas created validated production recovery point
`atlas-20260808-134255-455.tar.gz` with SHA-256
`12c15ece97baab3533ace72c8c1a6c601781bf3a4f2c8389f93503db171680d9`.

The exercise finished with all three controlled writers running healthy, Atlas
Health at 100 percent, normal public ingress at 24/24, maintenance disabled,
the shared lock released, the verified deployment baseline unchanged, and the
repository clean. Production backup retention remained at 10 canonical
archives.

## Recovery-Time Expectation

The controlled transaction identifier records a start at 17:41:53 UTC and all
three writer `StartedAt` timestamps were 17:43:02 UTC, about 69 seconds to
writer restart on the tested single-host topology. Full health/module/ingress
verification completed immediately afterward. This is evidence, not an SLO.
Operators should reserve at least a 5-10 minute maintenance window for this
small single-host deployment and allow more time as state size or validation
cost grows.

## Recovery Scope and Single-Host Limitation

Atlas recovery archives protect the explicitly declared Atlas configuration and
authoritative state surfaces. They do **not** contain the Media library and do
not claim complete recovery of Jellyfin, Radarr, Sonarr, qBittorrent, or other
third-party application databases. Deployment records and Docker image IDs are
audit/rollback evidence, not portable host recovery.

`/mnt/storage/backups/atlas` shares the Atlas host/storage failure domain. Local
backups therefore do not protect against loss, corruption, theft, or destruction
of that storage domain. Validated recovery archives that must survive host loss
should be copied to an independently protected storage domain. Off-host backup,
encryption/immutable copies, and full-platform disaster recovery remain later
infrastructure work.
