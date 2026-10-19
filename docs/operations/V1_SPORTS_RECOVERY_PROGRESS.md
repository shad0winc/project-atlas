# Sports recovery implementation and acceptance ledger

Checkpoint: 2026-10-18 UTC. This ledger was introduced through RC PR356/main PR357. Subsequent candidate
sections distinguish accepted evidence from pending verification. User-run CT100 outputs are
the evidence for the completed checkpoints below.

## Current accepted source and production boundary

- Clean canonical main: `/opt/project-atlas-v1-main`,
  `f8696d95bbf4488d95c2243e54c305010ae5b22c`.
- Historical Notifications source: `/opt/project-atlas`, clean and detached at
  `79cf73747f9a979ea02fb77446f2fa61df8e3451`; keep frozen. Controller now mounts
  canonical main read-only. Perform development in isolated worktrees.
- RC1: `5be6f4bf92fcca0834e4103266cd8a8aec61bc17`.
- Version: `1.0.0-rc.1`; no final v1.0.0 release has been performed here.
- Active recovery baseline: `baseline-20261018T035020Z-2649543`, after
  Notifications adoption. Previous baseline `update-20261015T211211Z-632971`
  and its recovery assets were preserved. Adoption was not a service upgrade.
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

| Sixteen-registry restore | 358 / 359 | ac3e69c4 / 9f090d75 | All sixteen replacements, consumer readback, handled setup/row/copy failure and held validation refusal |

| Coordinated pre-exposure recovery | 360 / 361 | 186a4bcd / 448b556b | Durable21-unit prepare/resume/abort and held acceptance, fresh-process deaths and same-archive bindings |

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

## Sixteen-registry restore (merged and source-synced)

See SPORTS_REGISTRY_RESTORE.md. This candidate replaces generic archive registry
placeholder payloads with valid empty consumer schemas plus one event/subscriber,
stages the same real format3 archive and exercises all sixteen private registry
row replacements, consumer readback, held setup/row/copy failures and validation
refusal. Existing production format3 planning stays blocked. This is not a single
crash-safe production transaction spanning native, metadata and registry state;
full operational activation and populated-data migration remain separate gates.
CT100 numeric-identity tests, the full core suite and the combined native
diagnostic passed on 2026-10-17. RC1 and main subsequently passed six checks each, merged and synced as recorded below.


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


### Registry merge and synchronization evidence

Source `6d0b2583daa14407afd7952444a462b9ef38dce8`; RC head
`b45bcb25c3125a7c9ef820466e8d92f542657f3e`. PR358 RC squash
`ac3e69c486b261cc86847877421653692daa4d50`; PR359 main squash
`9f090d75b3cdb3d69f537aa1fe7e2b3b02c3cf02`. Both PRs passed all six
release checks. Five file objects/modes matched across source and both merges;
canonical main fast-forwarded cleanly. Deployment remained
`update-20261015T211211Z-632971`. These are user-reported CT/GitHub results;
no production deployment or final version/tag was performed.

## Coordinated recovery (merged and source-synced)

See SPORTS_COORDINATED_RECOVERY.md for the complete layout/state/receipt protocol.
The candidate adds a separate private all-captured21-unit journal with durable
prepare/publish/resume/abort direction, location/hash reconstruction, shared
reader exclusion and validation-before-release. It composes five representative
fresh-process deaths on same-archive artifacts with the accepted combined gate.
The full small-unit matrix covers every publication/undo rename and parent-sync
boundary. Existing publication5 and production restore code remain unchanged.

This closes no production recovery gate until CT evidence is obtained. Native
acceptance inside the new private journal is a strict-baseline hash comparison;
the parent boots matching bytes through its existing separate journal. It does
not establish direct native volume admission or post-consumer21-unit rollback.
Optional-absent actions and incomplete offline initialization recovery remain
outside this journal version. Process-death testing is not power-loss testing.
Record CT command/results, cleanup, source/RC/main commits and merges here after
they occur. Do not pre-populate those results from local unit tests.


### CT100 coordinated recovery acceptance evidence (2026-10-18 UTC)

- Explicit UID/GID1000 tests with supplementary groups cleared: 14 tests and
  448 subtests passed in 165.34 seconds. Pytest could not write its optional cache
  in the root-owned worktree; the warning did not affect test execution/results.
- Full Core Python: 5,472 tests and 1,322 subtests passed in 334.28 seconds.
- All five representative same-archive process deaths passed fresh-process
  resume/abort, repeated invocation, validation and admission acceptance across
  21 units. Registry, native-baseline and metadata bindings used archive SHA256
  `4598a898991abc6fb698d98e7cb060ccd68f58a766b730a8f9f38846ed53e3f8`.
- Actual four-service capture/restart and notification cursor, sixteen-registry
  handled failures/readback, strict dump preparation, native quarantine/rollback/
  persistence restart, UID1000 metadata reader, writer authentication, broker
  accounting, refresh completion/deadline child reaping in both verification
  phases, and maintenance acceptance/release passed.
- SYNTHETIC_COORDINATED_RECOVERY_DRILL passed. Canonical checkout remained clean;
  candidate status was exactly the six intended files, uncommitted at test time.
- Production live restore and refresh were not enabled. Deployment remained
  `update-20261015T211211Z-632971`. This proves private process-death acceptance;
  power loss, direct native mounts of the21-unit journal, post-exposure writes,
  coherent production snapshots and full operational restore remain unproven.
- This ledger-only evidence update follows the frozen executable verification.
  Source commit, RC/main CI/merge and canonical synchronization remain pending.


### Coordinated recovery merge and synchronization evidence

Source `a6dd83ad3c35a4fb85458745d49261369536a728`; RC head
`434ef8fbaaae260cba13ce9d879010f39940f8d4`. PR360 RC squash
`186a4bcddba60f35629683b032c232927d053cdd`; PR361 main squash
`448b556b3f184c0b5e5697a4e9742ef369acb27f`. Both PRs passed all six
release checks. Six file objects/modes matched source/RC/main; canonical main
fast-forwarded cleanly. The operation guide and CT evidence ledger were committed.
Active deployment stayed update-20261015T211211Z-632971. No final tag/deployment.
These results are from the user's CT100 command outputs, not local simulation.

## Coordinated native consumption candidate (CT100 accepted; CI pending)

See SPORTS_COORDINATED_CONSUMPTION.md. The candidate extends the private journal
with shared writer leases, exact owned native volume/application epoch bindings,
a detached capture barrier, durable resumable native import, all21-unit sealing
and quarantine/restore after application writes. Native restored fixture volumes
are copied from the actual coordinated rollback destinations and pass the
parent's real native boot/persistence restart before reader admission releases.

The original publication APIs refuse any consumption marker. Native ownership
remapping stays in guarded owned Docker volume copies; the journal is not mounted
writable into native applications. Metadata uses actual consumers; registry
mutations are valid synthetic fixture bytes/event/cursor, not real API workflows.
Unit Docker/ownership contracts are simulated. CT100 mapped-identity, complete
core, actual native refusal/capture/import/interruption/restart and cleanup proof
must be observed before commit/RC/main promotion. Record those results and later
commit/merge/sync evidence here. Production format3 restore remains blocked;
power-loss/global-Docker-admission/full operational restore remain unproven.


### CT100 coordinated native consumption evidence (2026-10-18 UTC)

- UID/GID1000 tests with supplementary groups cleared: 21 tests and 226 subtests
  passed in 112.41 seconds. Optional pytest caching was disabled for this run.
- Full Core Python: 5,493 tests and 1,548 subtests passed in 447.97 seconds.
- Combined diagnostic passed coordinated21-unit baseline admission, refusal while
  actual owned native applications ran, real native DB and metadata commits,
  valid synthetic registry/event/cursor writes, and interrupted detached capture
  import resumed by fresh processes.
- Three independent post-write recovery deaths passed: seal-written,
  renamed:quarantine:dispatcharr-db, and source-synced:restore:registry-users.
  The source journal remained preserved through those independent cases.
- Restored native applications booted from copies of coordinated rollback state,
  passed normal persistence restart, then detached for fixture teardown before
  coordinated reader admission and maintenance release passed.
- Same-archive binding SHA256:
  `dc80f8fccd0c0e213274b6a3db12b95c60c0c1e83e58998bfa319eebedc9232a`.
  Actual four-service capture/restart and notification cursor, sixteen-registry
  handled failures/readback, strict dump, metadata numeric readers, writer auth,
  broker accounting and both refresh shutdown cases in both phases also passed.
- SYNTHETIC_COORDINATED_CONSUMPTION_DRILL passed. Canonical checkout remained
  clean at448b556b; candidate status contained exactly nine intended files and
  was uncommitted at verification time. Deployment stayed
  `update-20261015T211211Z-632971`; production live restore/refresh were not enabled.
- Scope remains private copy-mediated native admission. Direct native mounts of
  the journal, real mutations through every registry API, coherent populated
  production snapshots, power loss, global Docker admission and full production
  operational restore remain unproven.
- This ledger-only evidence update follows frozen executable verification.
  Source commit, RC/main CI/merge and canonical synchronization remain pending.

## Coordinated native consumption merges and production health reconciliation

User output confirmed RC PR362 squash
`6b20c39ba07597bb6bb6da60bd688dafa0356193` and main PR363 squash
`3e4c0f9e6edf622434710400fd49190c326726af`, with six successful checks on
each PR. Source head was `b4859ae5bdfcf3666da7f9666a6f4923841e123b`; RC
head was `f774317592410dc0f1abeb1e1e825c4ffded420d`. All nine file objects
and modes matched. Canonical source synchronization was fast-forward only;
the deployment pointer remained unchanged. CT100 core evidence was 5493 tests
and 1548 subtests; explicit UID/GID1000 focused evidence was 21 tests and 226
subtests. The combined coordinated-consumption diagnostic passed, including
owned cleanup and production identity/pointer checks.

Subsequent read-only production inventory and provider diagnostics identified
TheSportsDB degradation with an active cooldown and the same documented public
key in controller/writer. No key or raw error was exposed. Source, deployment
and checked runtime identities stayed stable. See SPORTS_PROVIDER_REQUEST_BUDGET.md
for exact observations, health/liveness distinctions, storage mounts, published
provider context, request-admission algorithm, persistence and rollout contracts.
The inventory did not certify doctor/preflight or open database connections.

The provider-budget candidate passed CT100 verification; both PR gates remain
pending. Local evidence: 18 new offline cases plus 17 existing related contracts/
capability cases passed (35 total). The candidate preserves 14-day discovery and
adds 20 shared rolling-minute admissions, full persisted Retry-After, cache-hit
reuse and charged failure/process-death behavior. It does not claim that the
public provider has recovered or that a new image was deployed. Controlled
rollout must cover all callers; mixed old/new processes do not establish the
new admission guarantee. No production mutation, live restore or final tag.

## Provider request budget: observed CT100 acceptance

User-run CT100 output on 2026-10-18 UTC confirmed candidate ZIP SHA256
`0da44eb6788e9a9fdaea81f087eefbd0016bb1909debf6e841997fae6e5c2ea9`
(58,311 bytes), five intended files and installer pre/postconditions PASS.
The isolated branch is `feat/sports-provider-budget`, based on canonical
`3e4c0f9e6edf622434710400fd49190c326726af`.

Explicit UID/GID 1000, supplementary groups cleared, cache plugin disabled:
18 tests and 15 subtests passed in 0.74 seconds. Full core: 5511 tests and 1563
subtests passed in 446.90 seconds. The combined diagnostic reached
`SYNTHETIC_PROVIDER_BUDGET_RECOVERY_REGRESSION=PASS` and returned successfully.
The final canonical-clean assertion completed, and only the five expected
feature-worktree paths were reported as modified/new. No commit or deployment
was performed by that test command.

Combined acceptance retained all ten held maintenance-abort failures, all 17
sixteen-registry held boundaries, same-archive native/metadata/registry binding,
five representative coordinated preparation/publication deaths, actual four-
application stop/capture/restart and notification cursor, running-native recovery
refusal, detached capture/import resumption, three post-write recovery deaths,
metadata UID 1000 readback, authenticated writer restart, broker accounting and
both refresh shutdown cases at both restored verification phases. Restored native
applications and persistence restart reached PASS. Archive SHA256 was
`387ff0b65bd40f284f7999c2a07ca6777d328ee43f48f995a6ab447abef9a5ef`.

This is offline provider behavior plus private recovery/runtime compatibility
acceptance. The diagnostics explicitly reported no external provider access,
production state access, live restore or production service control. It does not
establish recovery of the live TheSportsDB provider, freshness of production games,
full production operational restore or power-loss recovery. Build/rollout,
effective caller version/mount checks and sustained provider verification remain
separate. Media browse improvements remain queued after Sports.


## Provider budget merged, image staged, canonical root transferred

User-run protected merges passed six checks each: RC PR364 squash
`604be89938f807530da136281d8fa8d010fdbfca` at 2026-10-18T02:52:39Z;
main PR365 squash `79cf73747f9a979ea02fb77446f2fa61df8e3451` at 03:09:18Z.
Source commit `589b0d93dab6514157fdf5a8c7732b497d6af879` and RC head
`abfaf71ffa84b27740de0ac6b3745351d474072d` had identical five-file postimages
and modes. Canonical synchronization was fast-forward only.

The image staging command built a unique writer tag
`atlas-sports-writer:provider-budget-79cf7374-4979d2b1cb13`, Docker image identity
`sha256:a9b2651d6188eeb236a9c8220d55b94c132c98638e9885b335d7c2d87d0e5f11`.
All 25 copied source files were verified. Eighteen offline tests passed inside the
actual image as UID/GID1000, network disabled, read-only root and no production
mounts. Base digest was
`sha256:7ce4b6dfe35e55397b7cda544f8a13f191b7ae28dc5aad71fe664dbc9bc2623f`.
Receipt: `/var/tmp/atlas-provider-budget-image-c2vxhoon/receipt.json`.
Production runtime and existing baseline remained unchanged; image not deployed.

Canonical transfer restored main to `/opt/project-atlas-v1-main` and detached
`/opt/project-atlas` at the same source commit. The host CLI now resolves to
`/opt/project-atlas-v1-main/scripts/atlas`. Canonical root .env was aligned with
the staging environment; the two prior environments and other configuration
backups remain private. Other module/configuration bytes already matched.
Bootstrap data/storage roots stayed aligned, no live bind targeted the canonical
destination, and all production runtime identities stayed unchanged.
Receipt: `/var/tmp/atlas-canonical-transfer-pyoq_l5i/receipt.json`.
Do not upload that private backup directory: it contains environment secrets.
Do not rerun the one-time transfer script or advance the frozen historical root.

## Notifications adoption and actual health preflight

User-run guarded adoption captured Notifications source provenance
`79cf73747f9a979ea02fb77446f2fa61df8e3451`, added exactly one Notifications
manifest row and rollback image aliases, and published verified baseline
`baseline-20261018T035020Z-2649543`. Previous Core/ingress/Sports source identities
and archives were retained; the old record's regular-file hashes stayed unchanged.
Every observed production container's runtime fingerprint stayed unchanged.
Adoption records historical restart source and image recovery evidence; it does
not prove that an already-running process loaded the new source or upgrade it.

The subsequent real health preflight returned exit 1: 36 healthy, one critical
`module:sports / Provider Health`. Core/runtime/configuration, ten services, all
five storage write probes, project documents, Sports feed/controller running and
Docker health, controller heartbeat and Sports liveness endpoint were healthy.
The baseline pointer and clean canonical source remained unchanged. This health
command did not perform an update. Liveness does not imply provider recovery.

## Provider recovery preflight candidate (not yet accepted on CT100)

See SPORTS_PROVIDER_RECOVERY_PREFLIGHT.md. The explicit candidate flag permits
only `all --migration none --recover-sports-provider`, a managed Sports baseline,
and a fresh complete report whose sole fault matches fresh TheSportsDB rate-limit
evidence. Ordinary updates and every post-update health gate retain their
existing behavior. This is a full all-scope transaction, not a two-service-only
patch or authorization to deploy. Local new gate tests and existing update
transaction regression passed; CT100/full-core/CI and actual rollout remain
pending. No live provider recovery, fresh-game result, live operational restore,
sustained-use acceptance or final release has been established by this candidate.


## Provider recovery preflight: observed CT100 acceptance

User-run CT100 verification on 2026-10-18 UTC confirmed all original five packet
postimages and modes. The initial explicit UID1000 run passed the new tests but
54 existing tmp_path cases stopped during fixture setup: pytest inherited the
root login name and selected root-owned /tmp/pytest-of-root. No assertion failure
was reported in that run. The corrected harness creates a private UID1000-owned
TemporaryDirectory and passes its child explicitly as --basetemp; it does not
chown, remove or reuse the global pytest directory. The corrected explicit
UID/GID1000/no-supplementary-groups run passed 76 tests and 178 subtests in 8.90s.

Full core then found one stale source-order assertion in test_deployment_recovery:
it still searched for a direct Doctor call after that call moved into the
preflight helper. The two-line correction checks the actual preflight boundary
before artifact preparation, target verification, maintenance, backup and apply.
No application behavior changed in this correction. Corrected test SHA256:
`a82c9a3504f67b73167d4f4dd0f217aac02e35a7209a01bc47fecb4e71f91a64`.

The corrected three-file regression passed 131 tests and 178 subtests in 9.46s.
Full core passed 5531 tests and 1741 subtests in 448.10s. Final checks confirmed
canonical main and frozen historical HEAD both remained
`79cf73747f9a979ea02fb77446f2fa61df8e3451`, both checkouts were clean, host CLI
resolved to the canonical root, and the active pointer remained
`baseline-20261018T035020Z-2649543`. Exactly six intended candidate paths were
reported, uncommitted. The original packet SHA256 was
`fddc002dfa14a6fdba2903d4a86daf35f26bd11da52812abc660d5b9976b9360`.

These observations accept the source/test candidate on CT100; RC/main CI and
protected merges, activation preflight, production rollout, live provider recovery
and sustained-use verification are separate pending gates. No update, service
restart, live restore or final tag was performed by these test commands.


## Production provider recovery attempt and free-key progress candidate

RC PR366 merged `5be6f4bf92fcca0834e4103266cd8a8aec61bc17` at
2026-10-18T04:45:21Z; main PR367 merged
`f8696d95bbf4488d95c2243e54c305010ae5b22c` at04:53:05Z. Source
`15d2bc4895616c8ffde9b580748559e5162c626e` and RC head
`98990c1dbfb9636858a34020577addee7a3e08dd` had identical six-file postimages
and modes; each PR passed six CI checks. Canonical was fast-forwarded, historical
source stayed frozen, and production runtime stayed unchanged during that sync.

A merged-code admission rehearsal accepted exactly the known TheSportsDB
rate-limit-only fault among37 required checks. All26 baseline rollback aliases
resolved, baseline/source/runtime stayed unchanged. The actual all-scope update
`update-20261018T045650Z-2853292` then passed admission/acquisition/backup and
applied Core, ingress and managed Sports. The recorded backup reported format3,
state-complete but restore-unverified. Post-update Doctor exhausted its bounded
provider-health grace, and the transaction became failed with maintenance and its
owned deployment lock retained. The verified pointer remained
`baseline-20261018T035020Z-2649543`. No successful deployment was claimed.

Read-only failure and morning checks matched all26 applied images to running
containers. Controller image was
`sha256:628a071f8bdeb56fee1bc479ad6b476991540fb173e230791bde9e368bc8dc17`;
writer image was
`sha256:a80d03aa2df0af78374fc83c2d0a5bf20ce41e3a6e6d190e286fe2cc5c2880a8`.
Both had provider SHA256
`f0857e3b89eff1928680f6eed750ef53931f099cb38650269d249afda5a9d55c` and
expected shared budget path. Controller source was mounted read-only from the
canonical root. Both callers used current free key123, not legacy3. The last
success age exceeded63hours. An active cooldown with zero admissions during the
preceding minute did not mean that the provider had recovered.

Budgeted probes respected shared cooldown: one daily-event query returned3events;
one first-controller-endpoint eventslast query returned1event. A full-plan trace
made ten successful calls followed by upstream HTTP429 on call11 (eventsday.php)
with Retry-After120. None of the probes saved games or provider-health data,
changed configuration, restarted services or released maintenance/lock.

The read-only plan inspection found38 unique cold requests, 14-day horizon,
17tracked and4explicit event targets, one team and one league. A synthetic model
of repeated eleventh-dispatch429/120-second cooldown reproduced30minutes of
noncompletion with the actual old provider cache. The user selected fixing
free-key recovery rather than switching to a dedicated key. The new isolated
candidate stages bounded background snapshot progress across rate-limit deferrals,
preserves ordinary interactive cache TTLs, and exposes completed snapshot age.
See SPORTS_PROVIDER_REFRESH_PROGRESS.md for the deliberate15-minute snapshot
bound, local tests and pending CT100/activation gates. No claim is made that this
candidate is installed in the failed production target or that live health has
recovered. The original failed record, baseline, maintenance and lock must remain
intact pending a separately reviewed repair/recovery step.


## Controller refresh progress: observed CT100 acceptance

User-run CT100 verification on 2026-10-18 confirmed packet SHA256
`53658a81c5758b03dca2eae7d9df0c77501df36fce3a36fc84f9b0901704a9e5`
(27318 bytes), all184 support pins, five intended postimages/modes and installer
runtime-stability checks PASS. The isolated worktree was
`/opt/project-atlas-sports-provider-refresh-progress`, based on canonical
`f8696d95bbf4488d95c2243e54c305010ae5b22c`.

Explicit UID/GID1000 with supplementary groups cleared and a private pytest
basetemp passed37 tests and20 subtests in1.05s. Full core passed5550 tests and1746
subtests in448.35s. The nineteen new offline progress tests include the old
30-minute starvation reproduction, new-instance completion at360 simulated
seconds, complete normalized event publication, worker degraded-to-healthy
transition only on completion, snapshot-age reporting, unchanged interactive
cache expiry, identity isolation, clock/expiry refusal, resource bounds and
concurrent-caller serialization. Synthetic requests did not contact a provider.

Final assertions preserved canonical main atf8696d95, historical Notifications
source at79cf7374, the active baseline baseline-20261018T035020Z-2649543, failed
transaction update-20261018T045650Z-2853292, its lock ownership and enabled
maintenance. Exactly five candidate files remained uncommitted. No production
source, image, game state, provider-health state or public maintenance change was
performed by the installer/test command. RC/main CI and protected merges remain
pending. Activation needs its own reviewed recovery transaction; do not advance
the live-mounted canonical checkout or relabel the original failed target.

## 2026-10-18: first live refresh, following-cycle health flap

Refresh progress merged through RC #368 (`9f7db2da`) and main #369 (`5db0f488`).
The guarded two-service repair retained the original failed update and baseline.
At 17:02:28Z it completed 38 requests with oldest observation age 479.092 seconds.
The following refresh returned to rate-limited/degraded at last-success ages
231–292 seconds; normal Atlas health still had one Provider Health critical.
This is live proof of progress across cooldowns, not stable deployment acceptance.

A separate bounded-complete-snapshot candidate preserves usable complete data
and its actual completion timestamp during cooperative deferral. Both health
consumers validate the original 900-second bound at read time. No production
source, cooldown or health record is patched manually. See
`SPORTS_PROVIDER_SNAPSHOT_AVAILABILITY.md` for identities, receipts, cache bounds,
configuration-copy and graceful-stop details, test coverage and remaining gates.
Candidate local validation: 17 availability + 19 progress + 18 budget tests pass;
CT100 and protected RC/main promotion remain pending.

## CT100 acceptance: 2026-10-18

- Eight candidate file hashes and modes matched the frozen packet.
- Corrected test-launch PATH so child `python` resolves to the existing shared
  `/opt/project-atlas/.venv/bin/python`; the first core attempt had nine missing-
  executable failures, with 5558 tests passing. No source correction was needed.
- Restore-state validation rerun: 10 passed in 0.91 seconds.
- UID/GID 1000 with cleared supplementary groups: 54 focused tests and 25
  subtests passed in 1.29 seconds.
- Full core: 5567 tests and 1751 subtests passed in 448.52 seconds.
- Running repair, original failed transaction, backup, source archives, baseline,
  maintenance and original deployment lock remained unchanged.
- This records candidate acceptance only; protected RC/main CI and a separate
  managed activation plus sustained live acceptance are still required.

## 2026-10-18: rolling response renewal candidate

Snapshot availability was merged via RC PR370 (`8f82c6c3...`) and main PR371
(`959dc2a9...`), staged with 54 controller/18 writer offline tests and activated
as `repairs/snapshot-availability-dr7jfnlf`. Only controller/writer changed;
canonical remains pinned at `f8696d95...`, historical at `79cf7374...`.
Original failed transaction, baseline, maintenance, lock and both repair
journals remain held.

The 20-minute sustained watch recorded two completions 611.773 seconds apart,
healthy deferrals and a real freshness gap. Its receipt
`sustained-health-498b6a8fea5e.json` correctly has `accepted=false`, despite 37
healthy native checks at the final instant. The next read-only diagnosis again
reported degraded health and a 92.7-second shared cooldown. This is not private
sustained acceptance or deployment reconciliation.

A new isolated candidate retains complete request-plan responses with their
original observation times and renews the oldest due response first. It
reassembles only fully covered bounded snapshots; the completion timestamp
advances only after all observations have renewed since the preceding full
completion. The 900-second freshness gate, normal cache TTLs, shared admission
budget, Retry-After exclusion, worker publication and both health gates are
unchanged. Complete-cache memory accounting now charges response payloads too.

A deterministic 4,040-second offline comparison produced five full completions
and 220 HTTP invocations for both versions. Previous behavior had 76 unusable
samples after the first completion; the candidate had zero. This synthetic
fixture is not a provider quota guarantee. Twelve additional regressions cover
cadence, full coverage, real ages, timestamps, failure closure and bounds.
CT100/full-core verification and promotion remain pending. See
`SPORTS_PROVIDER_ROLLING_REFRESH.md`. Media browse remains queued after Sports.

## CT100 acceptance: 2026-10-18 UTC

- Five candidate postimage hashes and permission modes verified.
- The initial installer stopped after applying the patch because it compared
  permission bits 0644 with the full Git mode 100644. A guarded continuation
  verified every file and corrected only the permission comparison; candidate
  source was unchanged. The candidate receipt records this correction.
- UID/GID 1000 with cleared supplementary groups: 66 targeted tests and 25
  subtests passed in 1.80 seconds.
- Full core: 5579 tests and 1751 subtests passed in 453.13 seconds.
- Running snapshot-availability repair, original failed transaction, backup,
  source archives, active baseline, maintenance and original lock were preserved.
- Candidate receipt: /var/tmp/atlas-rolling-refresh-candidate-92_drqgx/receipt.json.
- This records isolated candidate acceptance. Protected RC/main CI, staged
  image acceptance, managed activation, sustained provider health and accurate
  private/public deployment reconciliation remain required.

## 2026-10-18: tracked-plan transition regression and candidate

Rolling renewal merged through RC PR372 (`4ba8b306...`) and main PR373
(`a552eb4d...`), passed 66 controller/18 writer image tests, and was activated
as `repairs/rolling-refresh-jf2op8lu`. Only controller/writer changed; canonical
remains `f8696d95...`, historical `79cf7374...`, baseline and original failed
transaction/maintenance/lock remain held.

The sustained watch retained bounded availability for roughly 22 minutes after
its first completion, observed two full completion markers, then correctly
rejected acceptance with Provider Health critical. Receipt is
`sustained-health-789732d152a8.json`. Last usable oldest-response age was
795.664 seconds; subsequent read-only diagnosis found rate-limit messages and
a 41-request plan. Logs showed 20 tracked events during 33 usable cycles,
followed by deferrals, a completion using 19 tracked events, then more deferrals.
Explicit subscription counts remained 4 event / 1 team / 1 league, but exact
identifiers must still be checked by the candidate.

An isolated candidate allows per-request observation handoff across tracked-ID
changes only within identical credentials/day/horizon/explicit-target scope.
A smaller plan can normalize its entire exact request set from still-fresh
observations without a cold replay. New missing requests remain incomplete
until obtained through existing shared admission; no previous plan is claimed
as complete coverage of a new required request. Original response times,
900-second freshness, normal cache TTLs, shared budget, upstream cooldown,
worker publication and health gates are unchanged.

Fourteen new regressions and the preceding 66 focused tests passed locally.
A deterministic 4,040-second comparison produced five full completion markers
and 220 HTTP invocations for both variants; unavailable samples following the
first completion fell from 17 to zero with a tracked-ID contraction. This does
not certify production continuity or provider capacity. CT100/full-core tests
and promotion remain pending. See `SPORTS_PROVIDER_PLAN_HANDOFF.md`. Media
browse remains queued after Sports acceptance and deployment reconciliation.

## CT100 acceptance: 2026-10-18 UTC

- Four frozen candidate postimages and Git/permission modes verified before and
  after isolated testing; installer applied without correction.
- UID/GID 1000 with cleared supplementary groups: 80 targeted tests and 30
  subtests passed in 2.40 seconds.
- Full core: 5593 tests and 1756 subtests passed in 453.39 seconds.
- Running rolling-refresh repair, original failed transaction, backup and source
  archives, active baseline, maintenance and original lock remained unchanged.
- Candidate installation receipt:
  /var/tmp/atlas-plan-handoff-candidate-jsm7p82_/receipt.json.
- The test command reported plan-handoff-tested-uncommitted-not-activated;
  installation receipt state remains applied-uncommitted-not-activated because
  that command did not update it. These observed test results are recorded here
  and in the separate promotion receipt without rewriting installation evidence.
- Protected RC/main CI, staged image acceptance, managed activation, sustained
  live acceptance and accurate private/public deployment reconciliation remain
  separate gates. Media browse remains queued after Sports.


## 2026-10-19 mixed-runtime candidate prepared; native integration pending

The read-only reconciliation audit passed at 01:01:06 UTC. Original and previous
baseline source archives matched their exact tracked Git objects. The repaired
writer's 25 COPY inputs matched d90c3ead, and all four repair pairs' rollback
aliases matched. Backup archive listing succeeded; operational restore remains
unproven. Maintenance, original lock ownership and recovery evidence remained
unchanged.

Candidate `baseline-reconciliation-20261019T012409Z-e98c967e0b` was prepared at
01:24:16 UTC under `reconciliation-prepared-bhdbe6on/candidate`. It contains 21
files, remains `prepared`, and passed the native read-only image/Notifications
verification. Manifest SHA256:
`ebf18fbaabf7bd120baed0710cb5d2c22a8cb0e0f554c352db38ab04d17f2d2c`.
No source checkout, running service, current pointer, maintenance or lock owner
was changed. The scheduler unit reported failed; source-level lock refusal is
consistent with the held state, but its actual failure cause was not diagnosed.

See `MIXED_RUNTIME_PROVENANCE.md` for the bounded native integration. Its local
29 new unittest cases and 93 directly exercised existing test functions passed.
The CT100 integration validation below supersedes the test-pending status of
this preparation entry. RC1/main CI, finalization, canonical advancement and
fresh private/public acceptance remain pending. Do not rerun activation or
ordinary update, republish the original failed transaction, or remove the held
deployment lock.

## 2026-10-19 mixed-runtime native integration: CT100 checks passed

Focused installation passed 129 tests and 2 subtests. After guarded test-harness
and fixture corrections, 94 targeted tests / 194 subtests passed, followed by
148 affected-module tests / 2 subtests and full Core with 5610 passed,
12 skipped and 1758 subtests. API passed 884 tests / 27 subtests with 14 warnings;
all 5 Sports integration programs passed; Portal passed lint, type-check,
118 test files / 661 tests and production build. Release Contracts passed for
35 shell files and deployment safety checks. Python compilation covered
624 Core files plus 243 additional API/Sports test files without bytecode.

The successful full Core receipt is under
`atlas-mixed-runtime-core-isolated-uurrxzjr`; remaining surfaces are under
`atlas-mixed-runtime-remaining-named-fggqqg9u`, both in `/var/tmp`.
Earlier failed attempts remain retained. Production runtime, protected evidence,
original recovery ownership and candidate manifest remained unchanged.
See `MIXED_RUNTIME_PROVENANCE.md` for environment and evidence details.

At this validation checkpoint the source was tested, uncommitted and unactivated;
it was not an accepted deployment.
Protected source promotion, canonical compatibility, finalizer failure handling,
fresh private Doctor/Verify and controlled public acceptance remain pending.
Admin-only authenticated maintenance access/control and the queued media-browse
acceptance requirements remain in the 1.0 scope and are not implemented or
accepted by this provenance patch. Backup listing does not prove operational
restore. The earlier private sustained Sports gate is retained without claiming
it establishes current or public acceptance.
