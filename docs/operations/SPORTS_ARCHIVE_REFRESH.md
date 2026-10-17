# Controlled refresh worker and bounded fetch shutdown acceptance

This isolated acceptance extends SPORTS_ARCHIVE_BROKER.md and retains the complete
same-archive native/metadata recovery, default-command writer, controlled broker,
persistence restart and private maintenance sequence. Production refresh and live
restore remain disabled. No production paths, credentials or services are changed.
Media browse work remains queued after Sports in V1_MEDIA_BROWSE_ACCEPTANCE.md.

## Enabled only inside an additional fixture process

The existing installed writer runtime/current reviewed-source RO mount contract is
reused. Two additional UUID-labelled containers per restored verification phase use
UID/GID1000, private writable metadata and startup state copies, root:GID1000 read-only
policy, read-only rootfs, network none, no published ports, no added capabilities or
groups, no-new-privileges, private IPC and bounded resources. Image builds/pulls and
production mounts are absent. Exact owned ID/name/image/label, entrypoint/bootstrap,
fixture environment values, network/security and complete mount records are checked.

The actual archived policy file remains disabled and unchanged. A pinned fixture
bootstrap constructs an explicitly enabled in-memory policy through the real policy
parser: NFL only, hourly budget96, TTLs60/900/900/3600, tick1, fixed generation and
fixed 2026-10-17 noon UTC clock. The valid nominal planning budget is93/hour. This is
fixture policy injection, not production refresh provisioning or an external quota.

A scoped wrapper passes a fixture refresh_factory to the real _serve_with_metadata
while invoking the actual private_api.main(). Its normal registry startup, HTTP
server, authentication, signal handler, worker.close(timeout25), server close and
status cleanup run unchanged. MetadataRefreshWorker itself, refresh planning,
MetadataBroker admission and persistent SQLite are real production implementations.
The separate default-command/disabled-policy writer gate also continues to run.

## Real bounded child, restricted loopback transport

The broker uses BoundedESPNTransport with its real8-second subprocess deadline.
Its supported runner seam verifies the original fixed arguments, input protocol,
JSON route/day and deadline. It delegates to real subprocess.run with only the fixed
child bootstrap substituted. The child calls the actual _fetch_worker, using actual
ESPNDayTransport/parser and response protocol. Its fixture-only opener accepts exactly
the expected NFL scoreboard URL and rewrites it to the synthetic loopback server;
redirects/proxies are disabled. Its local socket wait is30 seconds so it cannot
race the parent's real8-second deadline in the stalled case. No general production
endpoint override is added.
The child does not open the broker database. The separate provider handler reads it
to verify the reservation. Production DNS/TLS/ESPN networking are not exercised.

The provider handler checks one paid attempt and request hold through a separate
SQLite connection before publishing an atomic/fsynced FETCH.json marker with the
owned child PID. The server then waits until the real worker stop_event is set.
Before SIGTERM, a bounded in-container read-only probe checks numeric identity and
metadata/policy modes, child liveness, authenticated running refresh status, matching
policy fingerprint, reservation timestamp/hold and absence of shutdown markers.
An unauthenticated refresh-status request must be refused.

## Two in-flight shutdown paths

- complete: after SIGTERM causes worker.close to set stop_event, the provider returns
  an explicitly synthetic valid empty NFL payload. The current admitted fetch may
  finish and cache that response. No subsequent refresh job or child may start.
- deadline: after the same stop request, the provider withholds its reply until the
  real bounded subprocess timeout kills and waits for the child. The real broker
  records a deadline failure and15-second hold. The old expired cache remains old;
  it must not be falsely renewed or reported as provider success.

The actual writer signal handler stops serving and joins the worker. Before the
writer exits, the fixture requires worker state stopped/runningfalse, stop_event set,
no live refresh thread, the exact fetch PID absent and already reaped, and exactly
one runner call/paid attempt. Calling the actual worker.tick again must return30
without another call or metadata change. Both the success/deadline cache/hold/status
outcomes are checked. The provider handler and server thread must also terminate.
Only then is SHUTDOWN.json atomically published with explicit false production/live
restore flags. The receipt reports the child reaped before writer exit, not merely
absence after Docker destroys a PID namespace.

Docker stop uses20-second grace; normal exit0/PID0/no OOM and observed shutdown under
15 seconds are required. A timeout/SIGKILL cannot count as success. Control receipts
are limited and checked as UID1000-owned regular files. Source and policy copies and
the original restored journal bytes remain unchanged. Only disposable metadata changes.
Both cases run at each inherited restored verification phase, so private maintenance
release remains dependent on these checks before and after native persistence restart.

Cleanup revalidates exact owned identity/security/private mounts before stopping and
removing only the created container. It verifies no matching labelled container
remains, then removes private copies. Daemon errors are not empty results. No prune,
force removal, image mutation or production restart. Existing production identity,
full normalized mount, canonical checkout and deployment pointer guards still apply.

## Verification and limits

Before committing, run the writer/broker/refresh tests explicitly as UID/GID1000 with
supplementary groups cleared and pytest cache disabled. Then run all tests/core and
scripts/diagnostics/sports-archive-refresh-drill.py as the CT operator. The diagnostic
requires the exact precommit canonical/source checkpoint. Follow RC1-first CI/merge,
identical main CI/merge and canonical fast-forward only; do not deploy.

Local subprocess tests execute the real writer/refresh thread/broker/bounded child,
loopback HTTP, both SIGTERM paths and child reaping. They also reject unsafe fixture
identity/configuration, leaked-child/new-admission receipts and prior gate failures.
They retain operator source ownership and use host identity/ephemeral loopback ports;
actual mapped UID1000/Docker/native combined acceptance still requires CT100.

This proves controlled in-flight shutdown and post-close admission refusal. It does
not prove a production refresh rollout, multi-hour cadence/freshness, production
DNS/TLS, actual ESPN coverage, image build/deployment integration or arbitrary Docker
admission control. Four writer proxies remain distinct from actual four-service
operational control. Coherent production backup, full sixteen-surface operational
restore, ingress, production health/preflight and cold-cluster roles/configuration
bootstrap remain separate gates. All inherited synthetic archive/detached-import
limits remain. No production refresh or live restore activation is included.
