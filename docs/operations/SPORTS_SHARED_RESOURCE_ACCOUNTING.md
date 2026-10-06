# Sports shared resource accounting review

This draft changes only resource accounting. The production API constructs the
pool without sharing bindings and therefore retains exclusive admission. No
configuration switch, API route or production state migration is introduced.

Trusted server callers may supply an immutable mapping from exact logical event
and provider resource IDs to a SHA256 route/evidence fingerprint. Its presence
is an assertion by that caller, not proof established by this module. Fingerprints
must eventually bind the exact Dispatcharr channel/stream/account, publication,
Jellyfin item and actual sharing evidence. Browser input must never supply them.

Each viewer owns a distinct durable lease. Matching event/resource/fingerprint
leases occupy one allocation; different events, resources, fingerprints and
legacy exclusive leases remain separate allocations. User limits apply to
consumers. Snapshot `active` measures allocations; `leases` enumerates consumers.
Deleting an owned consumer leaves other consumers intact. Duplicate and foreign
release cannot delete another viewer's lease. Positive capacity remains necessary
for a shared join; a resource reduced below current allocation usage rejects new
joins. Candidate preference order is unchanged.

State remains version 1 for default exclusive use. The first opt-in allocation
writes version 2 and stores the fingerprint. Subsequent writes retain version 2,
even after all consumers leave. Version 1 leases are not adopted into sharing.
Old readers reject version 2, so all writers/readers must be deployed compatibly
before activation; rollback and restoration require explicit reconciliation.
Malformed fingerprints fail closed without rewriting the state.

## Outstanding activation gates

- Exact validated route/evidence binding and rejection of stale/remapped routes.
- Real same-event upstream/license sharing, independently of equal LiveStreamId.
- API admission, bootstrap, heartbeat, switching and cleanup integration.
- Separate Jellyfin play-session ownership and exact-transcode teardown; leaving
  one viewer must not interrupt another. Pool release alone is not teardown proof.
- Failure/unknown open/close outcomes and crash/restart reconciliation. TTL expiry
  is bookkeeping only: it does not establish physical upstream closure. Capacity
  reuse must not outrun that reconciliation.
- Different-event capacity, provider-account failure and event rollover proof.
- Coordinated consumers, reviewed state transition, scoped Atlas deployment and
  controlled UAT before wider admission. Production remains exclusive throughout
  this draft review.

No Dispatcharr limit, catalog, backup option, stream, media registry, acquisition,
retention, reset or credential configuration is changed by this patch.
