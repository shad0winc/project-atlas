# Isolated maintenance abort and native recovery rehearsal

This rehearsal connects the unchanged `atlas_restore_abort_live` shell controller
to the strict native and Atlas metadata recovery fixture. It starts from completed
native import and already detached consumer app objects. It does not enable live
restore or deployment.

## Boundaries exercised

The new entry point is `scripts/diagnostics/sports-maintenance-recovery-drill.py`.
Run it in the candidate worktree before committing, at the guarded main baseline
`5c613934c6bdb12c130dfdbdd462778d6b7397a6`.

The existing native fixture starts disposable apps, captures stopped baseline
state, performs strict PostgreSQL dump preparation, installs real Atlas metadata,
commits native and metadata changes, stops/removes owned app objects, and imports
the stopped native changes. All volumes and app names remain label/identity bound.

At the recovery boundary the controller runs in a private temporary directory.
It sources the actual restore command and execution-exclusion implementation.
Explicit fixture adapters replace all production host and service boundaries:

| Controller boundary | Fixture adapter |
| --- | --- |
| Held transaction lookup | Private transaction, owner marker and maintenance marker |
| Stop writers | Reattest that original owned consumer objects are detached and volumes unreferenced |
| Revert applied state | Existing native wrapper seals and recovers the five-surface journal twice |
| Validate consumers | Exact restored/quarantined hashes, actual Atlas schema, aliases, cache, budget and disabled policy |
| Start writers | Existing restored native app start, subsequent persistence restart and numeric UID/GID 1000 metadata reader checks |
| Wait for readiness | Require successful completion of the native acceptance sequence and revalidate restored journal |
| Verify runtime | Repeat acceptance receipt and journal validation under private maintenance and after private reopening |
| Disable maintenance | Remove only the private marker |
| Release owner | Require shell transaction status `aborted`, then remove only the private owner marker |

The unchanged shell abort function chooses when to call these adapters. A strict
ten-operation protocol refuses skipped, duplicate or reordered calls. Private
anonymous pipes carry only operation names and success/failure acknowledgements.
No socket server, network request, raw exception, database bytes, JWT, environment
dump or service log is emitted. The real shared execution-exclusion implementation
uses a kernel flock at the private runtime path for the entire shell operation.

The native acceptance continuation must complete exactly once before overall
PASS. The restored fixture apps are stopped/detached after acceptance for cleanup;
their successful starts and persistence checks are the readiness evidence. This
does not represent continuing production service availability.

## Failure acceptance

Before the Docker sequence the entry point injects failure at each of the ten
controller boundaries using lightweight fixture callbacks. The real shell must
return failure and retain its private maintenance and owner markers. A failure
through consumer validation must not invoke the start adapter. Later failures
retain maintenance; as in the existing controller, they do not promise that
already started consumers have been stopped again.

Unit tests also check callback exceptions, exact success order, real kernel lock
contention/release, private directory refusal, incompatible callback rejection,
five-surface journal recovery before acceptance, and detached-fence refusal before
journal mutation. PostgreSQL/Teamarr bytes in these local unit fixtures are explicit
unit data; CT100 runs actual native applications and strict preparation.

## Limits

This is a held-abort integration rehearsal. Production preflight, real deployment
lock acquisition, ingress maintenance enforcement, four-writer stop/start,
backup creation, full 16-surface application, Scheduler operation, authenticated
business APIs and Sports writer activation are not invoked. Their adapters are
explicit and do not certify those implementations. The stop adapter validates an
already detached fixture; it does not stop production writers or create a new
coherent production backup. Initial native capture occurs earlier as before.

The private shell transaction status and markers are fixture control state. They
are not a newly durable production journal, and no restart/resume or power-loss
claim is made for this adapter. Previous 15 SIGKILL journal tests remain separate;
they are not rerun inside this entry point. No production restore flag or command
implementation changes. The controller source is pinned, not copied or modified.

All private directories, pipes, created shell groups and owned Docker resources
are cleaned after the rehearsal. Failure evidence is checked before temporary
fixture cleanup; markers are not retained outside that temporary lifetime.
Existing production image/running/PID/start/mount observations, active deployment
pointer and clean canonical checkout must remain unchanged throughout the native
component's final checks. Mount arrays are compared without depending on order.

## Candidate verification

```bash
git diff --check
python -B -m pytest -q tests/core
python -B scripts/diagnostics/sports-maintenance-recovery-drill.py
```

Success ends with `SYNTHETIC_MAINTENANCE_RECOVERY_DRILL=PASS` and
`STATE=isolated-maintenance-native-recovery-not-deployed`.
Follow RC1-first CI/merge, identical main CI/merge and canonical source fast-forward.
Do not treat isolated PASS as production restore acceptance.
