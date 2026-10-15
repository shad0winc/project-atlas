# Sports live Administration recovery work

## Status of this review

This review adds read-only durable Sports-session visibility to Administration.
`GET /api/v1/admin/live-sessions/sports` requires `atlas.live_sessions.manage`
and reads the file-backed Sports registry rather than the older process-local
playback registry. It includes expired heartbeat records, relative ages and
snapshot identity. It does not prune, migrate, release, refresh a lease or infer
provider state. Missing or invalid state returns unavailable, not an empty count.
The existing policy controls remain separate.

The new Refresh session status action is read-only. Expired heartbeat is a
reason for recovery review, not authorization to release ownership. This review
does not implement the requested Reconcile stale live sessions mutation or
change live-open recovery. Those requirements remain open.

## Required mutation boundary

The API currently has no Docker socket or CLI access. Preserve that security
boundary. Host-only observer scripts are not suitable API subprocess handlers.
A dedicated, bounded observation/recovery integration must fit existing Atlas
ownership and scheduling/control-plane contracts before a button can invoke it.

The design must provide:

1. administrator permission and an audited exact user/session/target/lease request;
2. a coordinated admission boundary preventing a fresh consumer from racing
   between native-idle proof and release;
3. fresh repeated native clients/account connections, channel owner/metadata,
   Jellyfin process and upstream-peer observations from a trusted observer;
4. deployment/source identity and protected preimage hashes with durable intent;
5. release through the existing owned service boundary, never manual JSON clearing;
6. active, unknown, stale or changed evidence blocking release;
7. bounded single execution, no automatic mutation replay on an uncertain result;
8. preserved failed/unknown history and post-release registry, permission and
   native-state verification; and
9. clear UI progress/outcome with separate read-only Refresh.

Do not grant broad Docker execution, restart providers, accept a browser's idle
claim, or use a stale heartbeat or absent stream record alone as closure proof.
The operator procedure in [session release operations](SPORTS_SESSION_RELEASE_CAPABILITY.md)
remains the recovery path until this integration is implemented and accepted.

A failed shared live open may retain ownership before returning a browser handle.
Its future recovery contract must preserve ownership on uncertain provider
closure while giving the user or administrator an actionable exact-owner path.
Returning a cleanup credential alone does not prove that releasing is safe.
