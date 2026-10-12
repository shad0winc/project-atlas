# Recovery of an unidentified failed Jellyfin live open

A failed `LiveStreams/Open` can retain a blocked write-ahead owner with an exact
PlaySessionId and MediaSourceId but no returned LiveStreamId. Retain that owner,
its linked Atlas session, and its resource lease. Normal close, TTL expiry,
quiet Jellyfin Sessions output, zero Redis counters, a successful HEAD response,
and an API restart do not prove that an uncertain provider open has closed.

## Narrow internal recovery contract

`OwnedJellyfinLiveStreams.reconcile_failed_open_after_retirement` is an internal
operator method. It has no HTTP endpoint, automatic scheduler invocation, or
Administration reset button. It does not itself restart Jellyfin or call a
provider open/close endpoint. Installing this method does not perform recovery.

The method accepts only a registry containing one blocked owner with no known
LiveStreamId and with recorded PlaySessionId and MediaSourceId. Session, user,
item and registry SHA-256 must match the operator's reviewed snapshot. Known
stream IDs and uncertain closes remain outside this operation.

A trusted host-side verifier must produce `JellyfinProcessRetirement` evidence
and independently establish all of the following while admission is quiesced:

- The old Jellyfin process generation, which existed at the failed attempt, has
  ended. Include container identity, host boot identity and process start ticks
  in generation identifiers; a PID alone is insufficient because it can be reused.
- A different, healthy Jellyfin process generation started after the failed
  attempt. Timestamps alone do not establish process retirement.
- New Atlas/public/Jellyfin playback admission and scheduler work cannot race
  the recovery. Public Atlas maintenance alone does not fence direct Jellyfin
  access or privileged local writers.
- Existing native upstream readers and consumers for the retired generation
  are absent. Inspect actual workers/connections and native identities;
  zero Redis counters alone are insufficient evidence of physical closure.

The evidence object is not a signed capability and must never be accepted from
an ordinary API request. The callback is a trusted internal operator boundary,
just as existing provider close callbacks are. The evidence verifier and
controlled process-retirement transaction require separate review before use.

## Archive and commit behavior

Use a new, private, current-user-owned directory with mode 0700 and distinct,
absolute backup/receipt paths beneath it. The method verifies evidence, saves
and fsyncs the exact registry preimage at mode 0600, then saves and fsyncs a
prepared intent with generation evidence and before/after registry hashes.
It verifies evidence a second time and requires the generation identities and
facts to remain unchanged before writing the ownership registry atomically.
Evidence must be observed within 30 seconds of the store clock.

A prepared intent is not a completion receipt. The guarded caller must verify
the resulting registry hash and record transaction completion. If an operation
stops, preserve the backup and intent and compare current state before doing
anything else. Existing archive paths are never overwritten. The original
expected digest cannot be reused after a successful reconciliation.

After verified owner retirement, release only the exact correlated session and
lease through `SportsSessionRegistry.release_record` and
`SportsResourcePool.release`, with their recorded ownership identities. These
are separate writes: preserve a transaction journal and track each step so a
partial operation can be reconciled without releasing another viewer's records.
Do not hand-edit or truncate the session/lease registries. No linked-record
release is performed by this ownership-store method.

## Acceptance gates

Run focused failed-open recovery tests, existing ownership/cleanup tests, full
Core and API suites, and the required release CI checks before merging. Use a
reviewed deployment to publish the method before a separately guarded recovery
transaction. A successful recovery does not prove feed liveness, viewer stop
isolation, capacity accounting, or physical upstream sharing; those production
acceptance gates remain open.
