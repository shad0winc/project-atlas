# Admin access during maintenance: implementation and acceptance contract

Status: planned, not implemented or activated. Required for 1.0.
Base source: 05df9e185d901a4a81c88b6443f60104820874ea.

## Required behavior

- An active account with the server-validated global_admin role (including the
  normalized legacy admin alias) can sign in and use Portal/API during maintenance.
  Subsystem admin roles and custom broad permission grants do not grant bypass.
- New ordinary sign-ins and already authenticated ordinary sessions cannot access
  protected Portal/API routes while maintenance is enabled. Enforce this at API
  and ingress boundaries, including legacy token and browser refresh entry points.
- Provide a reachable admin sign-in entry without allowing an arbitrary path,
  request header, query parameter, or unverified cookie to bypass maintenance.
- Browser bypass must use a Secure, HttpOnly, host-only cookie with server-side
  session validation and current role/account checks. Existing browser refresh
  credentials have Path=/api/v1/auth/browser; they are not automatically sent on
  Portal requests. Preserve this narrow refresh-cookie contract.
- Role removal, suspension, logout, expiry and API restart revoke bypass access.
  Avoid stale authorization caches and unbounded long-lived bypass credentials.
- Admin web controls show actual maintenance status and recovery hold status.
  Mutations require authenticated global_admin, same-origin/CSRF protection and
  durable security audit. Do not expose secrets in error text, logs or receipts.
- The API must not receive broad host/deployment write access or a Docker socket.
  Use a narrow, reviewed control interface with only the required host authority.
- Maintenance disable must refuse while durable deployment/recovery ownership is
  present or unreadable. Coordinate web and CLI changes with the existing shared
  scheduler/deployment exclusion lock; preserve the host CLI fallback.
- API/control-service failures fail closed for bypass and mutations. Preserve the
  existing maintenance artwork, ingress liveness and private backend health checks.
- Define maintenance behavior for Theater playback and alternate ingress origins;
  public Portal/API isolation alone must not be claimed to block every media path.

## Acceptance

Test anonymous, ordinary, global admin and subsystem admin identities; new and
existing sessions; browser and legacy auth; refresh/logout/revocation; spoofed
headers/cookies; role changes; CSRF/cross-origin requests; recovery-lock races;
control-service failure and restart; audit failure; and continued private health.
Use isolated fixtures/canaries first. Do not disable production maintenance merely
to prove that the normal site is reachable. Keep original recovery evidence intact.

## Deployment and provenance

Any new API/Portal image, control service or Caddy configuration must have an
explicit source/runtime attestation and rollback recipe. The current reconciliation
candidate describes the existing runtime and stays immutable; do not silently
reuse it to describe later admin-maintenance changes. Extend the native service
provenance contract as needed before recording a changed runtime.

The current failed-after-apply recovery dispatcher reopens ordinary traffic during
verification and does not implement this admin-only contract. Do not run it for
this held recovery. Publication needs separately reviewed interruption handling,
fresh appropriate acceptance, and preserved original recovery ownership.

## Current accepted checkpoint

RC/main source promotion and post-merge gates passed. Canonical source advanced to
this base with live bind bytes/inodes/modes and operator configuration preserved.
Native mixed-runtime verification passed. Fresh private Doctor passed all 37
checks and Verify passed on 2026-10-19T14:03:57Z; provider snapshots remained usable.
Maintenance, original failed-update lock, baseline, failed transaction, backups and
linked repair journals remain held. Candidate remains prepared and unpublished.

Media browse artwork/title matching, native/dub/subtitle provenance, quality,
request/progress consistency, permissions, and Library-to-Theater acceptance remain
1.0 scope; see V1_MEDIA_BROWSE_ACCEPTANCE.md. This feature does not complete them.
