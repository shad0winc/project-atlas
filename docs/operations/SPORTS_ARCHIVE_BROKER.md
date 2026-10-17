# Controlled broker request accounting inside the archive-restored writer

This isolated gate extends SPORTS_ARCHIVE_WRITER.md. It keeps the full archive,
five-surface rollback, native application/persistence restart, UID1000 readers,
default-command writer startup and private maintenance acceptance sequence.
Nothing is deployed or provisioned in production. Media browse acceptance remains
queued after Sports in V1_MEDIA_BROWSE_ACCEPTANCE.md.

## Controlled process boundaries

After each existing restored-state verification, create another disposable writer
container using the same pinned installed runtime and reviewed source mounted RO.
The exact numeric identity, private bind sources, read-only rootfs and policy,
network none, no published ports, private IPC, no capabilities, no-new-privileges,
resource limits, disabled Docker healthcheck and logging-none contracts are checked.
Source staging preserves the invoking operator's UID/GID, including nonroot CI.
Metadata is a UID1000-owned writable private copy of the restored archive data;
policy is a root:GID1000 read-only copy with directory0750/file0640. Startup
registries and provider audit use a fresh writable UID1000 /state directory.

A pinned fixture bootstrap replaces the command only in this additional disposable
container. It calls the real private_api.main(), starts a loopback-only synthetic
provider server and uses the existing query_metadata broker_factory keyword seam.
The real writer authentication, query validation, response serializer/parser,
MetadataBroker admission/cache logic and MetadataStore SQLite operations run.
The disabled policy still goes through real writer startup; it starts no scheduler.
The existing default-command writer acceptance runs separately and unchanged.

The fixture broker uses hourly_budget1 and a fixed 2026-10-17 noon UTC clock.
ESPNDayTransport uses a fixture-only opener which accepts exactly the expected
fixed NFL scoreboard URL and rewrites it to the synthetic loopback server.
Redirects and environment proxies are disabled for that local transport. The actual
transport JSON/content-type/size/parser handling runs. This exercises synchronous
ESPNDayTransport, not the separate production BoundedESPNTransport fetch worker or
its child-process/DNS/TLS deadline. No production transport or configuration source
is edited, and no general provider URL override is introduced.

The provider server accepts only the expected scoreboard request. Before replying,
it opens a separate SQLite connection and requires the paid attempt and matching
unknown-outcome hold to be committed and visible. It then appends/fsyncs one bounded
synthetic audit record and returns an explicitly synthetic valid empty NFL payload.
No real sporting event or provider coverage is claimed.

## Acceptance sequence

1. Health succeeds. Missing/wrong bearer tokens are refused. A malformed query is
   refused before broker access. Before the first admitted request the original
   archived attempt123 remains and no provider audit exists. Refresh status is
   authenticated and exactly disabled/not running.
2. One authenticated valid day request returns a validated fresh snapshot, cache_hit
   false. Its observation is the fixed fixture clock and its expiry is clock+60.
   The expired archived reservation is pruned by normal broker admission; exactly
   one new paid attempt replaces it. The provider sees that committed reservation
   and the clock+30 request hold before it replies.
3. Repeating the request returns cache_hit true with identical observation/expiry
   and no additional provider request or paid attempt.
4. Requesting a different uncached day returns unavailable with retry_after3600
   because the shared hourly budget is exhausted. It must not return an empty
   success, call the provider, add another attempt or create another cache row.
   The warm cache must still serve after this refusal.
5. Verify complete archived alias rows unchanged, expected one attempt/cache row,
   removal of the successful request hold, unchanged expired global hold, exact
   single provider audit, actual SQLite quick_check and no WAL/SHM/other sidecars.
6. Stop normally with exit0/PID0/no OOM. Restart the same container with the same
   data. Repeat authenticated cache and budget checks: cache remains warm, budget
   remains spent and no new provider request occurs despite process-local broker
   and provider objects being recreated. Registry/audit/metadata bytes after this
   second normal stop must match those after the first stop.

Source and policy remain unchanged. Only the private broker copy of the metadata
changes; the original restored journal is checked byte-for-byte unchanged. Existing
native/metadata archive acceptance remains valid. Broker acceptance occurs twice
through the inherited verification hook, before restored native startup and after
native persistence restart, so private maintenance release depends on both phases.

Cleanup revalidates full owned ID, UUID-derived name, label, pinned image, exact
bootstrap/security settings and mount sources before stopping/removing the object.
It checks no matching labelled container remains before removing private copies.
Docker daemon errors are not treated as empty results. No prune or force removal.
Production identities/full normalized mounts, canonical checkout and deployment
pointer remain guarded throughout the outer diagnostic.

## Verification

Before commit, use the new feature worktree and shared virtualenv. Run the writer
and broker tests explicitly as UID/GID1000 with supplementary groups cleared and
pytest's cache provider disabled. Then run the full tests/core suite and
scripts/diagnostics/sports-archive-broker-drill.py as the normal CT100 operator.
The diagnostic intentionally pins the exact precommit source/canonical HEAD.
Follow RC1-first CI/merge, identical main CI/merge and canonical fast-forward only.

Local tests run actual unmodified writer HTTP, the real broker and transport JSON
parser, local provider HTTP and persistent SQLite across a normal process restart.
They also reject wrong command/image identity, unsafe network/mounts and incorrect
accounting receipts, and block broker acceptance when prior verification fails.
Local subprocesses use the host identity and an ephemeral loopback writer port;
actual UID1000/Docker isolation and combined native acceptance require CT100.

This is fixture dependency injection with fixed time and a synthetic upstream,
not production broker provisioning, provider request accounting evidence, enabled
refresh/cadence/shutdown admission, external ESPN networking or production image
build acceptance. Four-writer proxies still do not prove actual four-service
operational control. Full sixteen-surface restore, coherent production backups,
ingress, health/deployment preflight and native roles/configuration bootstrap remain
separate gates. All inherited synthetic archive/cold-cluster and detached-import
limits remain. Production refresh and live restore stay disabled.
