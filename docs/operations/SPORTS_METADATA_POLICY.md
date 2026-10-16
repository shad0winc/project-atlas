# Persistent Sports metadata refresh policy

Status: source integration only; disabled by default; not deployed or enabled.

## Fixed layout and permissions

Canonical `atlas update ingress|all` uses the existing metadata bootstrap after
pre-update doctor and artifact preparation, before maintenance and backup. It
provisions the schema-1 database and then the policy. Core-only updates do not
provision these directories. A failed doctor still creates neither directory.

The policy path is `${ATLAS_RUNTIME_CONFIG_DIR}/private/sports-metadata-policy/refresh.json`
(normally `/mnt/storage/configs/atlas/private/sports-metadata-policy/refresh.json`).
The private parent remains root-owned 0700. The policy directory is root-owned,
writer-group 0750; `refresh.json` is root-owned, writer-group 0640 and singly linked.
Only the writer receives its direct read-only bind at `/srv/sports-metadata-policy`;
Docker cannot create a missing host path. Database state remains a separate
writer-owned 0700 read/write mount. API, controller and media services receive
neither policy access nor an added mount.

New policy is exactly `{"version":1,"enabled":false}` plus newline. Bootstrap
stages and validates only new objects before publication. Existing directories
and files are validated without chmod, chown, initialization or content repair.
A valid enabled policy is preserved byte-for-byte and is never replaced by the
packaged disabled default. Unexpected entries, partial installation, links,
wrong ownership/modes, duplicate JSON keys, oversized files, unsupported routes
and cadence/budget violations fail closed. Validation uses the worker's parser.
No upstream request, worker startup, alias enrollment or policy enable is part
of provisioning or candidate tests.

Canonical updates are serialized by the existing update lock. Manual concurrent
policy edits during provisioning are unsupported. If policy provisioning fails
after database creation, the valid newly created database remains in place;
the update stops before maintenance/backup/apply. Inspect the failure before retry.
Never delete existing database state to reset a policy error.

## Recovery and activation limits

The backup helper automatically captures a present policy into metadata recovery
manifest version 2, preserving its exact bytes with a SHA-256 checksum. All staged
artifacts are private 0600. Legacy version-1 database-only metadata snapshots
remain readable, and outer archive format remains 3. Complete backup publication
and archive staging are covered by isolated tests. Corrupt or incomplete present
policy blocks backup publication; it never silently falls back to absence.

This integration supplies capture and validation, not a live policy installation
or restore command. Format-3 live restore is still blocked. Release-specific
restore/rollback evidence, writer quiescence and a reviewed activation operation
remain required before deployment. The snapshot does not attest that a captured
policy generation governed every database record or in-flight request.

Before enabling refresh, review selected routes, nominal and persisted request
budgets, generation, health reporting, existing-follow identity mapping, recovery
and production acceptance. Enabling an initially disabled policy requires writer
restart. Subsequent active workers reread policy each tick. Request ceilings are
Atlas planning controls, not upstream quota or availability guarantees.
SportsDB failures and the existing doctor gate remain visible.

## Verification

Run Core tests in the isolated feature worktree. Policy tests cover disabled
provisioning, exact enabled-policy preservation, unsafe permissions/links/schema,
partial failures, checksummed policy capture, tampering, legacy snapshots, complete
backup publication/staging and parsed Compose topology. CT100 must additionally
pass the non-root writer permission test: the writer can read the policy but
cannot edit, unlink or create entries, even without relying on the read-only bind.
No production policy or database is modified by those tests.
