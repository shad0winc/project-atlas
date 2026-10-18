# Private coordinated native admission and consumption recovery

## Problem and resulting behavior

The accepted coordinated recovery gate reconstructed all21 filesystem units
before exposure. Its native check compared prepared-baseline hashes, and its
parent booted a separate matching native baseline. It did not join actual native
writes to the21-unit rollback journal.

This candidate materializes native application volumes from coordinated current,
binds their exact owned application epochs to that journal, imports their clean
stopped capture with a resumable three-unit import, seals all21 consumed hashes,
and quarantines/restores all21 units after process death. Restored native apps
boot from copies of coordinated rollback state and pass the existing persistence
restart checks before fixture reader admission is released.

Baseline main: `448b556b3f184c0b5e5697a4e9742ef369acb27f`.
RC1 baseline: `186a4bcddba60f35629683b032c232927d053cdd`.
No production restore, backup, service or image implementation is changed. The
existing format3 production planning refusal remains active.

## Implementation map

| File | Responsibility |
| --- | --- |
| sports-coordinated-recovery.py | Optional internal consumption-aware inspection; ordinary publication/resume/abort/read APIs refuse any consumption marker |
| sports-coordinated-consumption.py | Shared writer leases, durable import, sealing, quarantine/restore and accepted reader leases |
| sports-coordinated-native-admission.py | Root controller, exact owned volumes/epochs, detached barrier and capture receipt binding |
| sports-coordinated-consumption-acceptance.py | Mandatory composition with actual native writes and same-archive fixtures |
| sports-coordinated-consumption-drill.py | Pinned combined CT100 diagnostic and bounded owned-fixture cleanup |
| test_sports_coordinated_consumption.py | Fresh-interpreter import/seal/recovery/acceptance interruption matrix and refusals |
| test_sports_coordinated_native_admission.py | Simulated Docker/ownership contract tests plus real metadata/registry semantic checks |

All journal roots retain the existing strict private /tmp UUID scope. The fixed
21 units and all-captured requirement remain unchanged. Files/directories keep
current-operator ownership and private600/700 modes. Numeric native ownership is
applied only when copying into guarded owned Docker volumes; the journal is not
mounted writable into those applications.

## Native admission protocol

After the same-archive baseline is prepared and its private registry consumers
validate, both initial generations of all21 units use those archive fixture
bytes. The consumption sidecar freezes the publication PLAN/status and archive
binding. A cooperative shared admission lease covers native materialization,
application creation/start, actual native commits, metadata/registry fixture
writes, and clean stop/detach.

Materialization checks all three native source hashes against the frozen PLAN
and both empty, unreferenced, owned native volumes before copying. It records
NATIVE_INTENT.json before copying. Dispatcharr receives the PG17 cluster as
UID/GID1000 and JWT as0:0; Teamarr receives the main SQLite file as0:0. Application
commands, images, network isolation and role-specific readiness are the accepted
native fixture contracts; no production container names are controlled.

After actual application startup, the existing native lifecycle fence binds
full container IDs, start epochs, labels, volumes and images. NATIVE_BOUND.json
binds that lifecycle journal and its application identities to the21-unit
exposure/intent. Both a competing recovery process and a detached-barrier check
must refuse while the native applications are running. The current journal bytes
must remain unchanged during that refusal.

The existing native fence performs PG fast clean shutdown before normal Docker
stop, proves both applications exited, removes the exact owned IDs without force,
and proves no container references either volume. NATIVE_DETACHED.json binds the
final lifecycle ledger. A fresh-process barrier reopens that exact private
lifecycle journal, validates bindings/epochs and checks the actual Docker daemon,
volumes and absence of references. Daemon errors are failures, never absence.
The shared admission lease is released only after the detached proof is recorded.

This is a serial trusted fixture controller, not a global Docker admission lock.
An unrelated process must not create new references during the detached window.
The barrier is repeated before and after mutation phases, rather than claiming
that an advisory filesystem lease can exclude arbitrary Docker clients.

## Capture and durable native import

The accepted native capture helper validates a detached PG17 cluster and JWT,
copies Teamarr main/WAL/SHM together, and folds SQLite state into a detached clean
main-file snapshot. Its receipt must say native-consumer-committed, name exactly
three native hashes, and bind the same detached lifecycle ledger. Every hash is
checked before the21-unit import can start.

IMPORT.json durably freezes source paths/hashes, prior native hashes, capture
receipt digest, exposure digest and detached proof digest before active moves.
While import-preparing, all original destinations, all complete incoming units
and all source hashes are checked before partial-copy cleanup. Recognized private
partial copies are discarded and recopied; unknown or unsafe contents hold.
Preparing needs the original capture source. After importing intent, recovery
uses complete staged units and preserved previous bytes without needing sources.

| Native import position | current | consumption/previous | consumption/incoming |
| --- | --- | --- | --- |
| 0 | prior baseline | absent | captured consumed bytes |
| 1 | absent | prior baseline | captured consumed bytes |
| 2 | captured consumed bytes | prior baseline | absent |

All three positions are reconstructed before the first move. Intent is durable
before each direction starts; every rename syncs both parent directories. A
fresh interpreter finishes an interrupted import idempotently. The previous
native bytes remain private evidence and are rechecked when reading the seal.

## Other writes and the21-unit seal

Metadata uses the actual MetadataStore/IdentityRegistry and policy operations
under the coordinated writer lease: alias, attempt, hold, cache and disabled-policy
fixture updates. The accepted legacy metadata fixture receives the same logical
operations so its independent parent acceptance continues to run.

Registry writes are explicit valid synthetic fixture changes: JSON formatting
changes, one additional valid runtime event and a cursor advancing to1. They are
not real user/request HTTP mutations, remote notifications or populated-data
migration acceptance. Unchanged units such as retention and JWT still participate
in the complete21-unit seal and rollback.

After detached import, writer admission is refused. Sealing intent is recorded
before hashing; SEAL.json binds all21 consumed hashes, all21 old hashes, EXPOSURE
and IMPORT. An interrupted sealing process cannot reopen writers. Preserved old
state, imported native evidence and current hashes must all validate before the
seal is accepted.

## Quarantine, validation and release

Recovery records recovering before any undo. It reconstructs all21 triples and
walks them in reverse. Consumed bytes move to consumption/quarantine, then the
preserved old unit moves back to current. Legal states are consumed/old/absent,
absent/old/consumed, and old/absent/consumed. All units validate before the first
move; all hashes and the detached native barrier validate again at completion.
Reverted remains held. A second recovery invocation verifies the completed
locations and is idempotent.

A private validation reader can lease reverted current while maintenance remains
held. Native restored volumes are copied from those exact current native units;
the old caller's proposed source must match their hashes. Real native applications
start, validate restored DB markers and absence of consumed writes, restart
normally, validate persistence, then stop/detach for fixture teardown. The accepted
writer/broker/refresh/metadata checks also run in the parent rehearsal.

Before release, actual registry consumers validate both current and quarantine;
metadata checks prove new archive baseline in current and consumed state in
quarantine. All five restored native/metadata units must also match the parent's
restored bytes. A required acceptance callback runs under exclusion after native
boot/restart has returned successfully. The receipt binds PLAN, EXPOSURE, SEAL,
detached proof, archive and both21-unit hash maps. Verified status precedes the
CONTROL release, which occurs last. Receipt/status/release interruptions can be
completed only through acceptance with renewed required validation. Ordinary
readers are refused until receipt and all restored/quarantined hashes validate.

## State and failure rules

| State | Permitted continuation |
| --- | --- |
| open | Cooperative fixture writes; native admission intent/binding; detached capture binding |
| import-preparing | Validate sources and prior state, complete incoming copies |
| importing | Reconstruct and finish the three native moves |
| imported | Detached all21 seal, no new writers |
| sealing / sealed | Validate or finish immutable seal, no new writers |
| recovering | Reconstruct and finish all21 quarantine/restore moves |
| reverted | Private native/semantic validation while held |
| verified | Validate bound acceptance and released reader admission |

Incomplete sidecar arming or native admission before complete application binding
is refused, not guessed from names or automatically repaired. No recovery starts
without a valid detached lifecycle/capture binding. A real controller death while
apps run requires owned lifecycle reconciliation/stop/capture before journal
recovery; this candidate does not provide a production CLI for that operation.
Unknown files, symlinks, changed plans, changed source bytes during preparation,
changed native epochs, new volume references, malformed receipts, changed old or
sealed bytes and failed semantic validation all hold. Cleanup is restricted to
owned disposable resources and the strict private journal root.

## Verification and remaining boundary

New unit tests kill fresh interpreters at all six native import moves and all42
quarantine/restore moves: before rename, after rename, after source-parent sync
and after both-parent sync. They also cover staged copies, import-plan/state gaps,
partial-copy death, sealing, acceptance, repeated calls, source removal after
staging, shared leases and tampering/refusal paths. Docker and UID remapping in
unit admission tests are explicitly simulated; actual numeric ownership and
native applications require the combined CT100 diagnostic.

The combined diagnostic additionally checks real running-native refusal, a
process death during import of actual captured native bytes, and three independent
post-write recovery deaths on complete private journal copies. The original
journal is preserved through those cases, then recovered and validated through
actual native boot/restart from coordinated rollback copies. Local results are
recorded in the candidate README; CT100 results remain pending until observed.

This closes a private copy-mediated21-unit native consumption link when CT100
passes. It does not establish direct native mounts of the journal, a coherent
production-wide populated snapshot, real mutations through every registry API,
provider/recording/remote-delivery operation, power-loss durability, global Docker
admission, production provisioning/ownership, or full operational restore.
Production doctor/preflight, coherent backup, guarded plan/apply integration,
controlled deployment/rollback and sustained user-flow acceptance remain release
work. Media browse improvements remain queued after Sports.
