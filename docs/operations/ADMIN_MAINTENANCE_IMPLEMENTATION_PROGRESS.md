# Admin maintenance implementation checkpoint

Status: isolated source work; not committed, promoted or activated.

The authority foundation passed 17 CT100 tests, including Unix-socket transport
and abrupt process exit at each durable transition point. API admission, opaque
browser credentials, current-profile authorization, refresh-session revocation,
CSRF controls and existing auth regressions passed 110 tests and 5 subtests.

This next source stage adds the Caddy boundary and static administration console.
The console is reachable at /maintenance/admin.html and linked from maintenance
artwork. It uses the existing browser session endpoints, Web Locks and in-memory
access credentials. Mutation failure never causes an automatic mutation retry.
The refresh cookie keeps its existing narrow path. Caddy's internal authorization
endpoint is blocked from public direct routing. Exact credential entry routes
still enforce API admission. All other Atlas Portal/API routes consult server
maintenance state even without a local flag. A local enabled/control-pending
marker forces a stricter admin check; a request header cannot grant bypass.

The service unit and API socket mount are source proposals only. The socket is
read-only mounted into the API; maintenance/deployment write access and a Docker
socket are not granted. Validate actual socket peer UID/group mapping in a private
integration canary before installation. The service must run from a pinned source
with the audited authority code, root-owned non-writable state parents, and the
shared execution lock. No systemd installation/start is performed by source tests.

Remaining integration before promotion or activation:

- Host CLI and native update/recovery publication ordering. Existing transactions
  reopen while durable ownership is held; generic web/CLI disable must not bypass
  a recovery hold. Preserve a reviewed, explicit transactional completion path.
- Alternate playback/Jellyfin transport policy and scoped admin playback. These
  existing origins are deliberately not silently changed by the Portal boundary
  stage; do not claim all media transport is isolated yet.
- Real API/authority/Caddy canary, revocation/role changes across the full ingress,
  service failure/restart, host CLI fallback, and security audit behavior.
- Complete required checks and RC-first/main promotion. Any changed image, host
  service or Caddy bind needs truthful provenance and retained rollback assets.
  The original reconciliation candidate stays immutable and unpublished.
- Media browse and end-user acceptance remain required 1.0 work.

Caddy route semantics follow its documented forward_auth behavior; real adapter
and isolated HTTP probes are required alongside API authorization tests:
https://caddyserver.com/docs/caddyfile/directives/forward_auth


CLI authority integration: the standalone maintenance commands now use the same
host authority directly, with no dependency on a working API/socket service.
Disable never removes a recovery hold, and missing or contended shared exclusion
refuses before a flag transition. The explicit repair-hold command can clear an
interrupted authority transition only after forcing maintenance on and auditing;
it cannot release recovery ownership. Legacy directory overrides are rejected.

The prior adapter and 22-case internal-network Caddy routing canary passed with
only NET_BIND_SERVICE restored to the Caddy executable's capability bounding set.
All owned resources were removed. These probes used a fixture auth backend;
full real API/authority/ingress integration and alternate media policy remain due.

Do not promote or deploy this intermediate CLI stage: legacy native transactions
already hold the shared flock and cannot invoke the standalone authority inside
that exclusion. They must gain an explicit completion path with publication and
process-death tests before the feature can be activated. Refusal must never be
worked around by falling back to the old direct flag writer.


Host transaction admission foundation: a native caller may pass its inherited
exclusive descriptor and exact durable owner identity to an enable-only helper.
The helper checks the descriptor inode, independent-open exclusion and matching
open-description ownership, then rechecks the owner before audited enable. It
never unlocks the parent's descriptor, releases recovery ownership, repairs a
pending transition or disables maintenance. No new socket operation is exposed.
Abrupt-exit tests cover the authority's durable enable transition checkpoints.

Native orchestration has not yet been rewired to this helper. Publication and
completion ordering, controlled public acceptance and process-death coverage of
the complete publisher remain pending. The current feature is still unsuitable
for production activation or promotion.


Native update/rollback/recovery orchestration now uses owning-transaction enable
for initial admission and verifies an existing maintenance hold at the former
reopen boundary. Both verification rounds remain, including injected failures;
they are held verification and must not be described as public acceptance.
Verified record publication and current-pointer advancement remain before durable
owner release. Update now propagates a failed final owner release. All paths leave
maintenance enabled, including successful completion; normal-user reopening is an
explicit subsequent administrator action, never a borrowed-descriptor operation.

The integration tests run the actual update shell and actual authority against
fixture-owned state, with runtime/Docker/provider boundaries stubbed. They stop
the process before/after publication and after owner release, and inject refused
publication/release. Ordinary updates or recovery are not run on production.

The broader reconciliation finalizer, durable publication crash recovery, restore
orchestration, real API/socket ingress and media transport acceptance still need
review and validation. No held verification result replaces controlled public
acceptance. Keep the feature uncommitted and inactive until those contracts and
all required checks pass; retain the original production recovery evidence.


Restore integration now accepts an already-held regular maintenance flag while
retaining malformed-state refusal, a free durable-owner requirement and all
existing source/staged-consumer and backup-format restrictions. Initial admission
uses the owning-transaction enable helper. Restore completion, verified abort and
pre-mutation cleanup prove an existing hold rather than opening ordinary access.
Both runtime verification rounds and state finalization remain. An isolation
verification failure retains recovery ownership instead of releasing it.
Resume and abort now acquire the same shared execution exclusion as initial apply.

Tests use disposable restore state and stub consumers/backups. They do not prove
operational restoration of the production backup. Formats 2/3 remain refused by
the existing live-restore implementation; this stage does not widen supported
backup formats. Reconciliation publication/finalizer crash recovery, full real
API/authority/ingress, alternate media policy and end-user acceptance remain due.


Dependency composition correction: source review before the real ingress canary
found the maintenance admission callback in the password-recovery factory rather
than the authentication factory. Earlier focused HTTP tests manually constructed
AuthenticationService and missed that production composition defect. Move the
callback to the actual authentication factory and remove the invalid password-
recovery constructor argument. New regressions use actual authentication, JWT,
profile storage and audit factories without app dependency overrides; only the
external Jellyfin credential check and host control transport are doubles.
The negative control must fail against the earlier factory wiring before the
corrected source is accepted. No affected source has been activated in production.
Full real host socket/UID/ingress and media transport testing remain pending.


The private real API/host authority/Caddy TLS canary passed 44 primary-origin
cases using real profile/JWT factories and Unix peer authentication. Jellyfin
credentials and Portal rendering were fixtures; API lifespan workers and the
alternate media origins were not covered by that canary.

Maintenance media API boundary: signed video capabilities now carry an opaque
reference to the issuing Atlas login. During a hold, bootstrap and segment
forward authorization require that exact live access/refresh binding and the
user's current active global-admin role. Refresh rotation, logout, expiry and API
restart revoke this preview binding. The original access-token expiry bounds
preview; after refresh an administrator obtains a new playback bootstrap. Normal
mode retains existing scoped transport behavior. No broad-domain admin cookie is
introduced. The raw-origin authorization endpoint returns success only for a
known maintenance-off state, including no durable recovery or pending transition.

Only the exact DELETE release-capability route bypasses maintenance admission;
its existing signed session/owner/target/lease checks and provider ownership
checks remain. It can drain that viewer's session even during authority outage.
No ordinary allocation, heartbeat or browsing exemption is added.

This stage validates API/session/gateway and release regressions privately before
installing source into the isolated feature worktree. Caddy playback/raw-origin
routing and cleanup passthrough still require integration and a real media-origin
HTTP canary before any deployment. Full release checks, source promotion, host
service provisioning, durable publication/finalizer, production media acceptance
and controlled public acceptance remain pending. Production is unchanged.


The media API focused suite passed 142 tests with four warnings; warnings remain
for full-release review. Dedicated playback ingress now strips client-supplied
maintenance forcing headers and applies the local enabled/control-pending marker
before bootstrap or video forwarding. API forward authorization still requires
current admin session binding during any authority hold. Raw Jellyfin is closed
for everyone during maintenance; admin preview uses the scoped Atlas transport.
When no local marker exists, raw-origin authorization still queries the authority
and fails closed on recovery ownership, pending state or service outage. Only a
known maintenance-off state permits the ordinary raw Jellyfin origin.

Primary ingress forwards only the exact signed DELETE release-capability route
before general maintenance admission. The API's existing cleanup scope and owner
validation remains mandatory. No ordinary heartbeat or allocation bypass exists.
The private multi-origin HTTP canary exercises actual API factories, JWT/session
bindings, profile storage, Unix authority, Caddy TLS and the real library playback
route/provider against a synthetic Jellyfin HTTP backend. Synthetic playlists and
segments establish routing/authorization, not real decoder or production-content
acceptance. No full primary-origin canary or full Core rerun is needed solely for
these proxy changes; affected Core ingress contracts and new media-origin cases
are the fresh checks. Feature source is installed only after they pass. Full
release checks, deployment provenance/finalizer and live media acceptance remain.


The CT private multi-origin stage passed 33 Core ingress contracts and 75 real
API/authority/Caddy TLS cases. All disposable resources were removed. This
establishes synthetic transport behavior, not production decoder or encoder
cleanup acceptance. Production maintenance, original owner and evidence stayed
unchanged. No full-suite or earlier primary canary repetition was performed.

Durability primitive integration: native status and current-pointer writes now
flush the staged file before replacement and its containing directory afterwards.
Native scheduler publication flushes all regular source files and directories
before rename, then its destination namespace and newly created ancestors. An
existing generation is flushed after the existing native identity checks as well.
The single native root .env symlink is allowed only when it names the intended
operator overlay; arbitrary links and hardlinked files are refused. No overlay
contents are copied or changed by this helper. Root ownership is required on
production paths; disposable tests use their own unprivileged owner.

This is a filesystem durability primitive, not acceptance or reconciliation
policy. Failure after rename can leave the new pointer visible while returning
failure, so callers must retain maintenance and recovery ownership. No lock
release function was changed, no original owner was archived or removed, and no
new native reconciliation operation is authorized by these changes. A durable
publication journal/CAS, record-manifest flush, exact acceptance pinning and
reviewed original-owner release remain required before production publication.
Tests inspect syscall order and actual abrupt exits; physical power-loss behavior
and operational backup restore remain unproven.


CT durability regression validation passed 229 tests and three subtests. The
original owner-release primitive remains unchanged; no production publication or
maintenance-state mutation was executed. Completed media canaries were reused.

Publication-intent foundation adds a host-only journal under the exact inherited
original transaction exclusion. It binds the previous current identity, immutable
prepared candidate manifest/inventory, protected baseline and failed-record files,
and original owner bytes plus directory/file identity and permissions. A durable
maintenance/publication-pending marker is created before journal artifacts. Host
and web maintenance status both treat its presence as a pending hold. Generic
repair-hold retains this marker; an incomplete journal requires specific review.

An intact intent may be inspected or explicitly retried only while the old
current, original owner and all pinned evidence still match. Conflicts, partial
writes, unsafe links, candidate changes and pointer movement refuse without
rewriting evidence. Repeated complete intent writes flush their existing files
and namespaces again rather than overwriting them. No journal method publishes a
record, materializes a generation, advances current, releases ownership or clears
the marker. Native finalizer orchestration, post-publication restart
classification, owner archival/release, acceptance freshness and publication
completion remain pending. Do not create a production intent for the older
candidate before the new API/Caddy/authority provenance has been reconciled.


CT publication-intent validation passed 64 tests and 14 subtests. No production
intent or publication marker was created. The new held publication coordinator
is callable only from an existing host intent and the exact inherited original
transaction exclusion. It is deliberately absent from the public deployment
command dispatcher and never releases or archives ownership or clears the marker.

The coordinator enforces the canonical clean-source guard and fixed deployment
namespace. It runs fresh native runtime, Doctor and Verify gates on the prepared
candidate, durably creates a separate exact record with verified status and a
resealed flat manifest, verifies that record, then uses the existing native
mixed-runtime/source-generation/current publisher. Post-pointer runtime, Doctor
and Verify must pass before a held-boundary observation is written. The original
candidate, baseline, failed transaction, lock and provided evidence stay intact.

Explicit restart classification permits only the pinned old or new current
identity. A complete exact staged record or target can be resumed. Partial,
foreign or changed records are retained and refused. After pointer publication,
resume rechecks the exact new record/generation markers and original ownership,
runs fresh native checks and records the held boundary without moving the pointer
again. Structural observations are not private/public acceptance certificates.

Private tests use the actual journal, native shell coordinator, archive extraction,
file/directory fsync and current-pointer publisher. Runtime, Doctor and Verify are
external fixtures; these tests do not attest production health. They exercise
failed gates and pointer publication, three record-process-death boundaries and
shell death before/after actual pointer replacement. Source is not committed or
activated. Required follow-on work remains exact CI/source/acceptance binding,
new API/Caddy/host-service provenance, verified owner archival/release and marker
completion, full required checks/promotion, deployment and live media/public
acceptance. The finalizer must not be invoked on the older production candidate.


CT native held-publication validation passed 26 tests and six subtests. The
coordinator remains internal, uncommitted and inactive. No production intent,
publication, pointer movement, marker creation or owner release was performed.

Post-pointer private gates now execute inside a bounded, unique acceptance attempt.
The collector binds clean canonical main commit/tree and its own tracked bytes,
exact intent/original owner, record manifest/current, full generation inventory
and all managed image/container identities. Config/HostConfig/mount material is
hashed rather than persisting Docker environment or credentials. Healthy runtime
state is checked before and after; changed IDs/images/restarts/configuration,
generation, source or record context invalidate the attempt. Sports provider
bounded snapshots must remain usable and healthy, while legitimate provider
refresh progress is recorded separately and does not invalidate stable runtime.

Runtime, Doctor and Verify logs and exit statuses are stored privately and flushed.
Zero exit alone cannot hide unhealthy Doctor or failed Verify output. Boot identity,
wall/monotonic time and a five-minute maximum age bound reuse. Immutable successful
receipts link all log hashes and explicitly deny CI/public acceptance and owner-
release permission. Revalidation requires the exact receipt SHA, current context,
unchanged logs and fresh healthy provider state. Failed/partial attempts remain.
The native coordinator reports its receipt path with the held-boundary result.

Tests use actual Git source fixtures, actual journal/record/generation context and
native capture/collector CLI, with explicit Docker-inspect and health-command
fixtures. They do not provide production acceptance. The original held-boundary
remains structural; future owner release must bind an explicit verified private
receipt plus separately proved CI/public evidence. Source promotion, expanded
API/Caddy/host provenance, owner archival/release and marker completion, full
required checks and controlled live acceptance remain pending.
