# Private coordinated recovery journal

## Purpose and scope

The previous sixteen-registry gate verifies the real shell row engine, consumer
validation and handled rollback failures. Its applied-row log is written after
renames; it does not establish recovery after process death in that interval.
This candidate adds an independent private journal spanning all five native/
metadata units and all sixteen registry units before consumer exposure.

Baseline main: `9f090d75b3cdb3d69f537aa1fe7e2b3b02c3cf02`.
RC1 baseline: `ac3e69c486b261cc86847877421653692daa4d50`.
The existing production format3 planning guard remains in force. No production
restore function, path mapping, service command, image or deployment is changed.

## Files and units

`scripts/lib/sports-coordinated-recovery.py` implements the journal.
`scripts/lib/sports-coordinated-recovery-acceptance.py` binds representative
process-death trials to the same archive used by the combined native rehearsal.
The diagnostic composes that acceptance with the existing actual four-service
capture fence, native boot/rollback, metadata, writer, broker, refresh shutdown
and maintenance checks. The new core test module supplies the exhaustive small
filesystem fixture matrix; those native payloads are unit bytes, not bootable DBs.

The fixed order is dispatcharr-db, dispatcharr-jwt, teamarr-db, sports-metadata,
sports-metadata-policy, then sixteen `registry-<surface>` units in canonical
registry order. Types follow their existing directory/file contracts. All 21
must be captured and present in this version; absent-optional row actions are
covered by the previous gate but are not implemented in this journal.

The only journal roots accepted are current-operator-owned mode700 directories
matching `/tmp/project-atlas-coordinated-recovery.<32 lowercase hex digits>`.
Inputs must resolve under /tmp and obey the existing private bounded digest/copy
contract: no symlinks or hardlinks, regular private files/directories, bounded
entries/bytes and stable reads. Files are mode600, directories mode700.

## Durable layout and transitions

| Item | Contract |
| --- | --- |
| current | Active private fixture destinations, never production destinations |
| source | Cached new inputs needed only while preparing |
| transaction/incoming | Complete new units, plus recognized private partial preparation copies |
| transaction/old | Preserved old units displaced during publication |
| transaction/PLAN.json | Fixed 21-unit order/types, old/new hashes, archive SHA, private scope |
| transaction/STATUS.json | Durable direction/state, published atomically |
| CONTROL.json | PLAN digest and archive binding; admission held until acceptance |
| ACCEPTANCE.json | PLAN/archive/generation/all21 hashes, production/live flags false |
| admission.lock | Nonblocking shared read or exclusive mutation lease |
| journal.lock | Nonblocking exclusive journal inspection/mutation lease |

Offline initialization copies all old/new inputs and then publishes PLAN,
CONTROL and preparing status. It never moves an existing application destination.
Death before initialization finishes is refused rather than reconstructed; remove
an abandoned fixture only after verifying its exact private scope and ownership.
There is no automatic production cleanup API.

Resume prepares each incoming unit through a private `.unit.preparing` copy,
fsyncs it, renames it to its fixed incoming name and syncs directory entries.
It validates all old destinations and all cached sources before cleaning any
recognized abandoned partial. It records staged, then applying intent before
any active displacement. A unit has exactly three legal location/hash states:

| Position | current | old | incoming |
| --- | --- | --- | --- |
| 0 | old hash | absent | new hash |
| 1 | absent | old hash | new hash |
| 2 | new hash | old hash | absent |

Resume reconstructs all 21 positions before moving the first unit. It completes
0 to1 by preserving old, then1 to2 by installing new. Each rename syncs both
parents. Abort records its direction and walks units in reverse, moving2 to1
and1 to0. A second invocation resumes the selected direction from these frozen
hashes and locations. A partial preparation abort keeps all old destinations,
retains unpublished preparation evidence and stays held for validation.

Applied or aborted destinations remain unadmitted. A required validator checks
registry/native/metadata acceptance; its three results must be exactly true.
The coordinator checks all current hashes again after validation, publishes the
bound acceptance receipt, records verified-new or verified-old, and releases
CONTROL last. Death after receipt/status but before release can be completed by
fresh acceptance. Repeated acceptance after release verifies the receipt and
current bytes. Resume/abort cannot reverse an already accepted generation.

Cooperative readers hold a shared lease for their entire read scope; mutations
fail rather than wait while a reader holds it. The read scope rechecks hashes
on exit. This is not kernel write protection or Docker volume admission, and
no application writer is admitted to these private journal destinations.

## Same-archive composition

The actual archive stager safely extracts the retained sixteen registries while
the source archive still exists. The parent performs its existing registry gate,
strict dump preparation, native promotion and metadata extraction. Their archive
SHA bindings must agree before this candidate can initialize the parent journal.

Five representative full-artifact trials kill fresh interpreters after metadata
preparation, native installation, registry installation and registry/metadata
undo transitions. Fresh interpreters resume or abort twice. Registry acceptance
copies the actual journal destinations into a verification view and runs the
real fifteen consumer groups; metadata acceptance checks aliases, attempts,
holds, cache and disabled policy in the actual journal destinations. Native
acceptance checks exact old/new artifact hashes against the preserved or strict
prepared baseline. Acceptance is mandatory before private reader admission.

The parent later boots the matching native baseline through its existing
separate native publication/consumption machinery. It does not mount the new
21-unit journal directly. Old native bytes come from PRE_ARCHIVE; old registry
and metadata state are valid synthetic fixtures, not a coherent production
snapshot. Therefore this gate does not establish a complete operational rollback
of all21 after consumers have written. It is a pre-exposure journal acceptance.
All retained archive sources and baseline hashes must remain unchanged.

## Verification and limitations

The core unit matrix uses os._exit in fresh Python interpreters before rename,
after rename, after source-parent sync and after both-parent sync for every old/
new publication move and every reverse move: 336 boundary cases. It also covers
all21 prepared copies and preparation commits with both resume/abort directions,
durable direction states, receipt/status/release interruptions, repeated calls,
source removal after staging, validator refusal/mutation, tampered preserved
state, unknown entries, symlinks, missing PLAN and reader exclusion.

Local Python tests and source/package checks are recorded in the candidate
README. CT100 full-suite, numeric-identity and combined Docker/native evidence
remain pending until the operator runs the supplied verification command.
These tests model process death while the OS/filesystem remains running. They
do not simulate power loss, filesystem corruption or a hostile same-UID process.
No production format3 apply/resume/abort command is enabled. Production ownership
mapping, Docker admission, coherent old snapshots, populated data migrations,
post-exposure write sealing, operational health and controlled deployment remain
separate acceptance work. Media improvements remain queued after Sports.
