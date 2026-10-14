# Sports session release capability

Authenticated live-session open returns `X-Atlas-Live-Release-Capability`
alongside the session ID and TTL. The signed credential binds the exact Atlas
user, session, target and resource lease, with a dedicated issuer/audience/kind.
It expires six hours after open and is not renewed by heartbeat.

The Portal holds the credential in the in-memory session result. Cleanup of a
known session sends it in a header to
`DELETE /api/v1/sports/live/sessions/{session_id}/release-capability` without
reading or refreshing the login session. It never belongs in a URL, local
storage, logs, screenshots or diagnostics. Older session responses without the
header use the existing authenticated DELETE route.

The API validates signature, expiry, issuer, audience, kind, exact session scope
and persisted user/target/lease linkage before provider action. Reading linkage
does not prune expired records. Cleanup closes the owned stream first, then
releases the session and linked lease. Uncertain closure returns 503 and retains
ownership; missing ownership returns 404 without provider actions. Repeated
release cannot close another viewer, bootstrap playback or renew a heartbeat.

## Terminal managed-HLS cleanup

PR274/PR275 adds a callback after the managed HLS instance is destroyed on a
fatal error. The exact playback object must still belong to the active Sports
session. Sports stops renewal, rejects late heartbeat results and attempts the
owned release. Concurrent terminal cleanup attempts join the pending operation.
An uncertain result retains the exact session credential, blocks a replacement
feed and leaves Close available for an explicit cleanup retry. Old-player
callbacks cannot select a newer owner's session. Unmount joins pending terminal
cleanup. Recoverable HLS events do not trigger this terminal path.

After successful terminal cleanup the page reports that the session was
released. A later Close may only dismiss the remaining playback-choice UI;
it need not issue another DELETE for already released ownership. A hidden
player or disappeared Close button alone is not proof of server cleanup.

Native playback errors and bootstrap/open failures are outside this callback's
current scope. Heartbeat-failure cleanup, ordinary replacement and other
best-effort paths must not be treated as proven durable retry mechanisms merely
because terminal cleanup now retains its handle.

## Retained ownership and operator reconciliation

A failed shared live open can retain session/lease linkage without returning a
successful session handle to the browser. A later admission may return 409;
inspect its response detail to distinguish session limit from other conflicts.
A Close action with no retained browser handle cannot issue owned cleanup.
This recovery gap remains open; automatic stale-owner reclamation is not
implemented by the release credential.

Before operator reconciliation:

1. identify the exact retained user/session/target/lease linkage and source;
2. establish current source/deployment identity and transaction guards;
3. freeze registry bytes/hashes, owner/group/modes and expected linkage;
4. obtain fresh repeated native observations including clients, account
   connections, channel owner/metadata, Jellyfin processes and upstream peers;
5. block release if any native consumer is active or closure remains uncertain;
6. record private preimages and durable intent before the scoped service request;
7. invoke the existing owned release boundary with an exact-scope credential
   confined to the service process; and
8. verify the HTTP result, registry state/permissions, protected request/config
   state and native idleness afterward. Unknown outcomes require reconciliation
   rather than a blind second request.

Do not clear registry JSON, restart providers, delete transaction guards, expose
operator credentials in the browser or infer native closure from Atlas record
absence alone. Browser termination, expired credentials, outcome uncertainty or
partial durable writes may require this operator path. The proposed
Administration reconciliation action must implement these controls before it is
exposed; it is not currently a deployed button.

## Validation and accepted scope

Review validation covers credential scope/rejection/replay, login-unavailable
cleanup, ownership/expiry handling, terminal callback identity, concurrent
cleanup, late heartbeats, uncertain release retry and mounted Sports lifecycle
behavior. The Portal suite, typecheck, changed lint and build passed before
protected promotion; required release CI passed on the promoted source.

The [October 14 RC status](../releases/V1_RC_STATUS_20261014.md) records the
production two-viewer cleanup sequence and final native idle observations.
Shadow's reported 204 request method/path was not independently confirmed.
Do not extrapolate the observed ownership outcome into all lifecycle, capacity
or browser cases. HLS decode stability and incognito causality remain unresolved;
metadata 503 responses and startup decoder warnings are not established causes.
