# Sixteen-registry replacement and consumer acceptance

This private acceptance extends SPORTS_FOUR_SERVICE_LIFECYCLE.md. It fills the
registry portion of the restore proof: a real format3 complete archive is staged,
all sixteen declared registry destinations are replaced, the actual consumer
contracts validate readback, and failure paths retain maintenance and rollback.
The native/metadata archive binding, actual four-application capture fence,
post-native persistence restart, broker, refresh and maintenance gates still run.
It is not production operational restore enablement and does not start sixteen
application services. Production format3 planning/apply remains blocked.

## Source of state and exact registry

Earlier archive fixtures used generic synthetic JSON to demonstrate byte-preserving
publication. This candidate uses a scoped fixture setup adapter to replace those
placeholders with valid empty registry schemas plus a valid event and subscriber.
Both optional invitations and requests are present in the combined archive. The
archive is still produced by the unchanged real complete backup command, with the
same native dump/JWT/Teamarr and metadata artifacts and normal format3 checksums.
No existing production backup, restore or consumer implementation is modified.

The fixed private coordinator checks all sixteen canonical registry rows, including
surface name, archive path, required/optional policy, file/directory kind and exact
configured destination. It obtains those destinations from the real surface_rows
function with roots pointing exclusively inside an owned mode700
/tmp/atlas-registry-restore.* workspace. Staging uses the actual archive validator,
safe-member extraction and staged-state validator. Format3 is never rewritten as
format1. A separate check requires the existing generic format3 restore plan to
continue refusing the staged archive.

The sixteen surfaces are users, identity-invitations, favorites, dislikes, requests,
scheduler, runtime-events, runtime-subscribers, retention, sports-subscriptions,
sports-live-tv-bindings, sports-dispatcharr-channel-bindings, sports-live-sources,
sports-source-lifecycle, sports-recordings and sports-scheduler. The consumer
validator reports fifteen groups because runtime-events and runtime-subscribers
share one consistency check. Captured optionals must validate as PASS; absent
optionals are additionally covered in local row-engine tests.

Fixture schemas intentionally contain empty user/relationship/task/media registries,
one valid event and one subscriber cursor/filter. This proves schema compatibility,
replacement and consistency, not migration of rich production user or media data.
The native backend and Atlas metadata fixtures retain their inherited nonempty
transaction and identity evidence.

## Private row-engine coordinator

Only low-level existing primitives are called: validate_apply_plan,
validate_restore_destination, apply_plan_row, revert_applied_state and
finalize_applied_state. The generic restore_plan/live CLI is neither overridden
nor enabled. The fixed private plan joins the validated staged manifest and exact
canonical rows; it cannot supply arbitrary host destinations. Transaction and
configuration destinations must not overlap, all rows are validated before the
first displacement, and duplicate/missing/wrong-path or required-absent rows fail.

Each trial starts with distinct private old state, including both optional surfaces.
A real execution-exclusion lease and private maintenance/owner markers are acquired.
Old values are retained in live-rollback, replacements are prepared in incoming,
and the existing row function performs the moves. A six-field plan and five-field
applied log retain the real primitive formats. No new production journal API is
introduced. No Docker or external service is accessed by these registry trials.

After all rows apply, the coordinator remains applied-awaiting-verification with
maintenance held. Every captured destination is compared against its staged source;
an absent optional must be absent. A separate private consumer view is copied from
the actual destinations and validated through validate-recovery-state.py and its
real user/identity/requests/scheduler/retention/Sports readers. Only a successful
acceptance handshake permits the real finalizer to remove rollback state and the
controller to remove maintenance ownership and release exclusion. The staged tree
and source archive must remain unchanged.

## Failure evidence

The combined format3 diagnostic runs these cases under the stopped actual
four-service capture fence, before its inherited restart/release:

- Setup boundary0: transaction prepared but no row displaced; maintenance remains
  held and all old destinations match their original hashes.
- Completed rows1 through16: deterministic interruption after each row, reverse
  rollback through the actual revert function, exact old-state comparison, status
  reverted, and maintenance/owner markers still present.
- Incoming-copy failure: the real copy prepares incoming data and the fixture seam
  returns failure before publication of that row. The row primitive restores its
  displaced value, prior rows revert, and unpublished incoming data stays inside
  the held transaction until private fixture cleanup.
- Post-application validation refusal: after successful destination comparison and
  readback, only the disposable readback view is corrupted to trigger the actual
  user consumer validator. The rejection handshake must retain applied-awaiting-
  verification, rollback data and maintenance ownership; it must not finalize.
- Success: all sixteen replacements, consumer validation, finalization and private
  maintenance release complete, with source/archive hashes unchanged.

The deterministic failures are handled-return tests, not arbitrary process crash
or host-power-loss tests. The existing row engine logs completed rows after moving
them; this candidate does not claim to close that interruption window or provide
idempotent resume for those private trials. Failed trial markers are checked before
removing their owned temporary workspace. No production rollback evidence is removed.

## Composition with native and metadata recovery

A scoped in-memory loader wraps only this invocation's archive fixture setup and
roundtrip. The original archive roundtrip and its immutability checks still run.
The additional real stage/registry trials use that same archive SHA; subsequent
native extraction/strict preparation and metadata extraction bind to it through
the existing receipts. This is a composed acceptance sequence, not a single atomic
production transaction spanning registry/native/metadata state. Registry readback
views do not become the production applications' mounted data. Existing four-app
startup/restart and restored writer/metadata probes retain their documented scopes.

## Verification, documentation and remaining operational work

Local unittest coverage runs real shell primitives and consumer validators using
format1 unit envelopes and a real published/staged format3 unit archive. The latter
uses explicitly labelled unit-only dump-header bytes, not a real PostgreSQL dump;
real native boot remains a CT100 requirement. Tests cover all seventeen boundaries, optional-absent
removal, prepared-copy failure, validation refusal, malformed consumer state,
invalid cursors and unsafe plans. CT100 must run the new tests as UID1000, the full
core suite, then the combined format3 diagnostic at the exact precommit baseline.
Source hashes/modes, archive contents and canonical/deployment guards are mandatory.

This gate closes private sixteen-registry replacement/consumer/failure coverage.
Still open: crash-safe atomic coordination with native/metadata publication,
production format3 plan/apply/resume/abort integration, coherent operational backup,
real identity/permission remapping, representative populated-data migration, enabled
provider and remote notification work, production doctor/ingress, deployed image
provisioning, and full operational release acceptance. Do not describe this as full
production recovery support. Media browse work remains queued after Sports.
