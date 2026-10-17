# Same-archive native and Atlas metadata recovery rehearsal

This isolated acceptance extends SPORTS_ARCHIVE_RESTORE.md. It is not a live
restore implementation or permission to deploy. The production deployment,
canonical source tree, application identities and mounts remain guarded.
Media browse acceptance remains queued after Sports in V1_MEDIA_BROWSE_ACCEPTANCE.md.

## What this gate proves

The unchanged real backup command publishes a private format-3 archive inside
the four-writer counter-proxy fence. Existing complete-archive and safe-member
validators must pass. Native dump, JWT and Teamarr restoration still use the
existing archive-to-native pipeline and strict PostgreSQL preparation helper.

A separately loaded, invocation-local archive module extends readback to stream
exactly metadata-recovery/database.sqlite and metadata-recovery/refresh-policy.json
into a fresh private workspace. Only regular mode-0600 members, unique names and
bounded sizes are accepted. No tar extract-all or archive-directed destination
paths are used. Writes are exclusive, no-follow, bounded and fsynced. A new empty
metadata lock is created; copied WAL/SHM and other sidecars are refused. The actual
Atlas schema, aliases, request attempts, cooldown, cached payload and disabled
refresh policy must match the synthetic archive generation. Archive SHA must
remain unchanged throughout extraction.

METADATA_EXTRACTED.json binds both member hashes and both surface digests to the
archive SHA. After native baseline promotion, that SHA must equal the native
ARCHIVE_RESTORED.json archive SHA. There is one extraction per rehearsal instance;
missing extraction cannot fall back to fresh rollback metadata.

Before consumer exposure, the extracted metadata and policy are copied into both
the unexposed journal's old and current slots. Their initial bytes intentionally
match. PLAN.json records their archive-derived digests. A separate root-level
ARCHIVE_METADATA.json preserves provenance without changing the existing strict
transaction or consumption document schemas. Installation refuses exposed or
reused journals and checks every source/destination surface before replacement.
A partial unexposed install is held, not crash-resumable; preserve for diagnosis.

Real metadata consumer operations then enroll another synthetic identity, commit
another attempt, update cooldown/cache and change the policy's formatting while
keeping refresh disabled. Real native database commits occur alongside them.
The stopped native writes are captured/imported through the existing detached
journal path. Recovery must quarantine the consumed five surfaces and restore
all baseline surfaces. Repeated recovery must remain idempotent.

The private adapter reuses the unchanged actual shell abort controller and shared
execution exclusion. Its validation compares all five journal hashes and requires
restored metadata/policy bytes to match archive provenance before starting restored
native fixtures. The continuation performs application startup, another persistence
restart, semantic metadata checks and actual UID/GID1000 reader probes on private
ownership-normalized copies. Consumed metadata is checked and probed separately.
Private maintenance and ownership can be released only after the continuation and
subsequent validation succeed. Any controller failure retains those private controls
until the disposable fixture is cleaned up. The ten existing held-failure cases also
run before the native sequence.

## Running before commit

Use the feature worktree, shared virtualenv, PYTHONDONTWRITEBYTECODE=1 and the
Sports source PYTHONPATH. Run git diff --check, the full tests/core pytest suite,
then scripts/diagnostics/sports-archive-metadata-drill.py. The entry point pins its
source dependencies and requires the exact precommit canonical baseline. Do not
blindly rerun the diagnostic after committing or merging; its HEAD guard is
intentional. Follow the established RC1-first CI/merge, identical main CI/merge
and canonical fast-forward workflow. No deployment is included.

Expected additional acceptance markers:

- SAME_ARCHIVE_NATIVE_AND_METADATA_BINDING=PASS
- ARCHIVE_METADATA_INSTALLED_AS_ROLLBACK_BASELINE=PASS
- ARCHIVED_METADATA_ALIASES_BUDGET_POLICY_AND_UID1000_READER=PASS
- ARCHIVE_METADATA_MAINTENANCE_ACCEPTANCE_AND_RELEASE=PASS
- SYNTHETIC_ARCHIVE_METADATA_DRILL=PASS
- STATE=isolated-same-archive-five-surface-recovery-not-deployed

## Verification and limits

Unit tests exercise the real archive command/validators, actual Atlas schema and
consumer journal, exact byte/hash restoration, wrong binding, corruption, bounds,
existing destination, exposed journal, repeat install, semantic tampering, actual
shell maintenance sequencing and held native-acceptance failure. Unit PostgreSQL
bytes are explicit fixtures. Native app startup, strict PostgreSQL restoration and
numeric UID/GID1000 reader execution require CT100 and must pass there before commit.

The archive's metadata is synthetic and refresh-disabled. This proves artifact
flow into a disposable recovery journal, not coherent production capture, real
provider coverage, broker HTTP requests or refresh activation. Counter proxies
represent four writers; actual four-service stop/start acceptance remains separate.
UID1000 probes do not exercise the complete Sports writer container and mounts.
The native PostgreSQL restore still requires the preserved compatible cold-cluster
scaffold for roles/configuration outside the dump. This is not standalone disaster
bootstrap or complete sixteen-surface operational restore. Existing explicit private
packaging scaffolds remain where exported source inputs were absent. No ingress,
production paths, live restore enablement, role provisioning, durability under host
power loss, partial-import resume or production deployment is added here.
