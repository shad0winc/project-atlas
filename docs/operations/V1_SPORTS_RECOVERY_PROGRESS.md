# Sports recovery implementation and acceptance ledger

Checkpoint: 2026-10-17. This ledger was introduced through RC PR356/main PR357. Subsequent candidate
sections distinguish accepted evidence from pending verification. User-run CT100 outputs are
the evidence for the completed checkpoints below.

## Current accepted source and production boundary

- Clean canonical main: `8955da81021ea9290b52215e29008578e1a86cf2`.
- RC1: `06bab88a37e08b84e55f4326e24f4d84adefd6fd`.
- Version: `1.0.0-rc.1`; no final v1.0.0 release has been performed here.
- Deployment pointer: `update-20261015T211211Z-632971`, unchanged.
- Production refresh and live restore remain disabled. Source synchronization is
  distinct from building images, deploying services, or performing live recovery.

## Completed sequence

| Gate | RC / main PR | RC merge / main merge | Acceptance added |
| --- | --- | --- | --- |
| Strict consumption | 334 / 335 | 4fb7f18f / 66275e4a | Strict dump preparation combined with native rollback |
| Metadata consumption | 336 / 337 | 7a0e955e / 1de394ae | Alias, budget, policy and UID1000 metadata reader checks |
| Consumption interruption | 338 / 339 | 00711c60 / 5c613934 | Interruption during combined native and metadata recovery |
| Maintenance recovery | 340 / 341 | 8ca0505a / c9266e38 | Real abort orchestration with private callbacks and ten held failure boundaries |
| Backup fence | 342 / 343 | 2850d8b1 / da798030 | Four disposable writer counters stopped during native capture and resumed afterward |
| Complete archive | 344 / 345 | e5502570 / 70ad1f3c | Real backup-command format-3 archive publication, validation and roundtrip of a private sixteen-surface registry |
| Archive native restore | 346 / 347 | 4b7603b8 / 563b720b | Native fixtures booted from extracted archive artifacts and strict prepared dump |
| Same-archive metadata | 348 / 349 | 955cc6eb / 73f149b4 | Native and Atlas metadata/policy rollback baselines bound to the same archive |
| Archived writer startup | 350 / 351 | a450e39f / 88b7d63a | Actual writer startup, authentication, disabled policy and persistent registry restart on archived metadata |
| Archived broker accounting | 352 / 353 | 132a00b4 / 7d2467ff | Reservation visible before one synthetic fetch; persistent cache and quota across restart |
| Refresh shutdown | 354 / 355 | 3b2a574e / 6a46f688 | Real refresh worker and bounded child completion/deadline during SIGTERM; child reaped before writer exit; no post-stop admissions |
| Actual four-service lifecycle | 356 / 357 | 06bab88a / 8955da81 | Actual default-command application fixtures quiesced around native capture, clean restart and notification cursor persistence |

Each gate has its own SPORTS_* operation document, diagnostic, helper and core
tests. Read those files for algorithms, receipt schemas and fixture boundaries;
this ledger is an index of evidence, not a substitute for their detailed contracts.

## Latest refresh evidence

Source commit `10beaa45a58486001d9b39ebc4f9c5696b850261`; RC head
`a3ad2dfcf6e306109c3de234b6382be6172b375a`. Both PRs passed six release checks.
Four new files, 554 insertions, identical file objects and modes across source,
RC squash and main squash. Canonical update was fast-forward only.

CT100 core: 5,434 tests, 825 subtests passed. Explicit UID/GID1000 writer/broker/
refresh tests with supplementary groups cleared: 19 tests, 48 subtests passed.
Combined diagnostic passed both refresh cases at both restored verification
phases, plus archive/native/metadata/writer/broker/maintenance acceptance.

The enabled refresh policy is injected only in a disposable fixture process.
The mounted archived policy stays disabled. Real planning, SQLite reservation,
worker shutdown, subprocess timeout and reaping run against a restricted loopback
provider. This does not exercise production ESPN DNS/TLS or enable refresh.

## Corrections and engineering lessons

- Backup-fence initial drill failed while verifying the stopped counter fixture.
  The corrected candidate uses explicit volume-nocopy; do not claim unobserved
  copied filenames as the proven cause. Clean fixture teardown was verified.
- Writer RC350 initially failed non-root CI because source staging attempted
  default root ownership. Follow-up source commit
  `670a548341474a06e06271566b6bc03d5242a0d9` and RC commit
  `e76c526f656e8f8e7bb231e7523bba25322a9afa` retain operator ownership for staged
  source. UID1000 data and root:GID1000 policy mappings remain intentional.
  Corrected CT checks and CI passed before merge; no force push or history rewrite.
- Compare complete Docker mount records after sorting, preserving duplicates and
  all fields. Mount-array order alone is not runtime identity. A later stable
  preflight passed; the earlier failed assertion does not establish a specific
  underlying field change.
- Root-owned publication readers cannot read UID1000 receipts using their strict
  ownership contract. Validate the expected numeric owner and private file shape
  explicitly before bounded JSON parsing.
- The refresh fixture's socket timeout outlives the parent subprocess deadline,
  avoiding a socket/deadline race. Publish shutdown proof only after the refresh
  thread, child and fixture provider have terminated.

## How the accepted recovery layers fit together

The private writer fence precedes stopped native baseline capture. Strict dump
preparation and the real complete backup command produce and validate a private
archive. Extraction binds native artifacts and metadata/policy to that archive.
The publication journal imports detached captures under exclusion, tracks exposure
and quarantines consumed writes. Restored native applications and writer probes
verify state before and after persistence restart. Maintenance abort holds control
until its ordered stop/revert/validate/start/readiness/publication/release sequence
has accepted the restored state. Dedicated operation documents retain each layer's
hash, identity, ownership, failure and receipt requirements.

## Outstanding operational work

- Extend the completed actual four-application fixture lifecycle acceptance to
  enabled provider work, remote delivery and full production deployment contracts.
  The existing private default-command stop/capture/restart gate passed.
- Integrate full sixteen-surface operational restore and partial setup/import
  failure handling; a synthetic sixteen-surface archive does not prove all real
  applications recover successfully.
- Resolve production health/preflight, coherent operational backup, image and
  mount provisioning, ingress, and compatible cold-cluster roles/configuration.
- Complete remaining Sports user-flow acceptance, controlled deployment/rollback
  and sustained-use evidence before final version/tag/release work.
- After Sports, implement V1_MEDIA_BROWSE_ACCEPTANCE.md: title/source-matched
  artwork with fallback, evidenced original language/dub/sub/quality (unknown is
  distinct from unavailable), separate untracked from requested/processing media,
  and reuse Library progress/status behavior with identity and permission checks.

## Change protocol and documentation continuation

Preserve a clean canonical checkout and deployment pointer. Work in an isolated
feature worktree; freeze candidate hashes and file modes; run explicit non-root
checks, core suite and relevant combined diagnostic; merge RC1 first after CI;
open an identical main PR; verify identities and squash merges; fast-forward only.
Production service mutations require a separately scoped operational procedure.

For subsequent gates record the trigger and intended behavior, source/RC/main
commits, changed files and modes, runtime identities, tests and observed counts,
failure/correction history, receipt evidence, cleanup result, production boundary,
and remaining limitations. The eventual system guide should explain normal
operation, data ownership, backup/recovery ordering, failure handling and operator
runbooks using this evidence and the individual operation documents.

## Four-service lifecycle acceptance

Read-only runtime inventory at main6a46f688 reported all four actual services
running and Docker-healthy, with before/after identity/configuration/mount stability.
Source ZIP at that checkpoint: 567 committed files, SHA256
`e27112623bc8d5e1bc44e2d13d70a02b101f74c694302059b6be322f72bf2c73`.
The candidate adds explicit controller TERM/INT stop and notifications idle-stop
handling, and replaces the counter fence with actual default-command application
fixtures. CT100 mapped-identity tests and the combined diagnostic passed on 2026-10-17.
The RC1 and main PR CI/merge steps were pending at the original CT evidence checkpoint; both subsequently passed six checks and merged. See SPORTS_FOUR_SERVICE_LIFECYCLE.md for exact scope and limits.


### CT100 four-service acceptance evidence (2026-10-17)

- Core Python: 5,444 tests and 853 subtests passed.
- Explicit UID/GID1000 writer/broker/refresh/four-service tests with supplementary
  groups cleared: 29 tests and 76 subtests passed.
- ACTUAL_FOUR_APPLICATION_PROCESSES_READY, stopped native capture/private snapshot,
  restart readiness/notification cursor, and the final combined diagnostic passed.
- API UID999, other workers UID1000; exact installed image commands and reviewed
  source overlays. All four fixture exits were0; production services were not
  controlled. External provider access and live restore remained disabled.
- The real private complete archive command validated format3 across its synthetic
  sixteen-surface registry. Archive SHA256 for this run:
  `412ec0a448a8ce735a593f9043355f7bb82d4143438b77488d5a5b4b825f0e42`.
- Same-archive native/metadata binding, strict dump preparation, native committed
  writes/quarantine/rollback, restored persistence restart, and maintenance
  acceptance/release passed. Broker reservation/cache/budget and both refresh
  child shutdown cases passed in both restored verification phases.
- Canonical main stayed clean at6a46f688; deployment pointer remained
  `update-20261015T211211Z-632971`. Candidate source was uncommitted at test time.
- This closes the private actual-application capture-fence acceptance, not enabled
  provider/remote delivery workflows or full sixteen-surface operational restore.


### Four-service merge and synchronization evidence

Source `1fba0013f3e9444157e679386eb2fcf89bb66e11`; RC head
`9869acd4209671df1cba4b8d752f02125c070b39`. RC PR356 squash
`06bab88a37e08b84e55f4326e24f4d84adefd6fd`; main PR357 squash
`8955da81021ea9290b52215e29008578e1a86cf2`. Each PR passed six release
checks. Seven file objects/modes matched source/RC/main; canonical main was
fast-forwarded cleanly. Deployment remained update-20261015T211211Z-632971.
The controller/notifications shutdown code is source-synced; this was not an
image build or production restart. Source-mounted running services may read
canonical files on subsequent starts, so source synchronization is not a claim
that all running processes execute a new version.

## Sixteen-registry restore candidate (CT100 accepted; CI pending)

See SPORTS_REGISTRY_RESTORE.md. This candidate replaces generic archive registry
placeholder payloads with valid empty consumer schemas plus one event/subscriber,
stages the same real format3 archive and exercises all sixteen private registry
row replacements, consumer readback, held setup/row/copy failures and validation
refusal. Existing production format3 planning stays blocked. This is not a single
crash-safe production transaction spanning native, metadata and registry state;
full operational activation and populated-data migration remain separate gates.
CT100 numeric-identity tests, the full core suite and the combined native
diagnostic passed on 2026-10-17. RC1 and main CI/merge remain pending at this
evidence checkpoint.


### CT100 sixteen-registry acceptance evidence (2026-10-17)

- Core Python: 5,458 tests and 874 subtests passed.
- UID/GID1000 registry/four-service tests, with supplementary groups cleared:
  24 tests and 49 subtests passed.
- All seventeen setup/completed-row boundaries0 through16 passed held rollback
  acceptance. Prepared-copy failure reverted; consumer refusal retained held
  maintenance and rollback; successful replacement validated fifteen consumer
  groups covering sixteen surfaces and finalized only after acceptance.
- Both optional surfaces were captured in the combined format3 archive. Its SHA256:
  `b679a4000e9ec1244ae496fecea4d74119f0c4a0a7cbb29e6a04d5e1a89de890`.
- SAME_ARCHIVE_SIXTEEN_REGISTRY_NATIVE_METADATA_BINDING passed. Actual four-service
  stop/capture/restart, notification cursor, native quarantine/rollback/persistence,
  writer authentication, broker accounting, both refresh shutdown cases in both
  verification phases, and maintenance acceptance/release passed.
- Production format3 planning remained blocked. Full production operational restore
  and power-loss recovery were explicitly false in the diagnostic receipt.
- Canonical main stayed clean at8955da81; active deployment remained
  `update-20261015T211211Z-632971`. Source was uncommitted at test time. Only this
  documentation evidence update follows those tests; executable code is unchanged.
