# Private held acceptance binding

The internal native held-publication coordinator captures fresh post-pointer gates
into a new private-attempts/<random-id> directory in the publication journal. It
never overwrites an attempt or a successful receipt. Failure preserves snapshots,
logs, original ownership and the publication-pending fence.

Before running runtime/Doctor/Verify, the collector requires the published target,
exact record inventory and record observation, current original owner and intent.
It requires execution from the canonical source root, records clean main HEAD/tree,
and checks the executing collector and authority/journal dependency bytes against
their tracked files. It hashes complete generation files/modes and the sole
permitted root .env overlay link/target. It collects every images.tsv container,
requires exact images and running/nonpaused/nonrestarting/non-OOM state with healthy
Docker health when declared, and fingerprints identity, restarts, PID/start time,
Config, HostConfig and mounts. Docker configuration/environment is retained only
as hashes; raw inspect responses are not written to receipts.

Sports provider state is read from a stable no-follow inode using canonical
snapshot-availability semantics. This legitimate container-owned mutable state
does not have to be host-root-owned. Provider identities are hashed. Healthy bounded
snapshots are required before and after; refresh progress may advance between them.

Native gates write private nonclobbering logs and exact exit files. All exits must
be zero, Doctor must report healthy with all parsed checks OK, and Verify must
report PASS without failure lines. Log/status files and receipt are flushed. The
before/after source, record, generation, current, owner and runtime context must
match exactly. Boot identity, wall time and monotonic time prevent reuse across
reboot, clock rollback or more than five minutes.

Successful receipts explicitly state accepted_private=true, public_acceptance_proven
=false, ci_acceptance_proven=false and owner_release_permitted=false. Validation
requires the pinned receipt SHA, exact private attempt inventory/log hashes,
unchanged live context and still-usable provider snapshots. It does not update
or refresh the receipt; stale evidence requires a new explicit attempt.

This collector does not run activation/update, create a production journal, clear
maintenance/pending, change current or release/archive ownership. The native
coordinator remains internal and the held boundary remains a structural record,
not a CI/public certificate. The future release driver must bind exact tested
source/CI and separately collected public evidence before any owner-release policy.

Tests use a real temporary main Git repository, actual journals and native
record/generation/pointer publication, plus explicit Docker/health fixtures. Native
capture and collector CLI are exercised together. Results establish binding and
refusal behavior, not production health, public reachability, physical power-loss
safety, real media decoding/encoder cleanup or production backup restoration.

Native Python module launchers use safe-path mode (-P) and only the canonical
source root in PYTHONPATH. The caller working directory cannot shadow the
collector or held journal. The capture regression invokes the actual shell bridge
from a different source working directory, without replacing that bridge.
