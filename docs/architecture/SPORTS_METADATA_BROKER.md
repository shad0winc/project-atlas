# Independent Sports metadata broker foundation

Status: opt-in private writer boundary; production remains inactive. No production
state directory, provider registration, worker hook, Compose configuration or
migration is installed. Importing these modules creates no state. Existing
SportsDB discovery and provider health behavior remain unchanged.

## Ownership and storage

The private Sports writer is the intended sole metadata owner. API and background
consumers use `MetadataWriterClient` for the authenticated service boundary;
they must not construct independent upstream clients. No controller caller or
credential configuration is installed yet. Explicit construction takes a
caller-provisioned directory owned by the
writer with mode 0700; database and lock files are 0600. No existing shared path is
chmodded or chowned. Runtime directory provisioning and Compose validation are
required before activation, particularly because writer and API identities differ.

The store uses SQLite schema version 1, synchronous FULL commits and an advisory
process-shared file lock. Provider concurrency is intentionally one, across keys
and processes, to provide a conservative first request boundary. Lock acquisition
is bounded (12 seconds by default); overload fails instead of opening another
upstream request. This is serial single-flight, not a high-throughput scheduler.
It needs Linux/POSIX flock and a local filesystem with reliable SQLite locking.
Do not place this state on a network filesystem or a mergerfs mount without an
explicit validated storage decision. No production path is selected here.

## Requests and outcomes

Only six routes have fixture-backed parsing in this candidate: NFL, NBA, MLB, NHL,
English Premier League and UFC. This is not the whole Teamarr league catalogue.
The transport uses the observed ESPN scoreboard interface, a fixed HTTPS origin,
no redirects, one day per request, an eight-second socket timeout and a four-MB
response limit. A separate short-lived Python fetch process enforces an eight-second overall
deadline across DNS, TLS, response reading and parsing. The parent kills and waits
for the child on timeout. Only the parent accesses persistent metadata state;
worker stdout contains bounded metadata or sanitized failure fields. Production
Compose PID/resource validation must account for this additional child process.
Normal urllib environment proxy handling is retained; Teamarr database proxy
settings are not implicitly imported or copied. No raw URLs/errors/bodies are
logged by this code. The interface is observed, not a guaranteed official API SLA.

The broker accepts yesterday through seven days ahead in UTC as a low-level fetch
budget. That is not the user-local Upcoming window. A later collector must union
needed provider calendar buckets and then filter aware timestamps once, using
user-local schedule requirements. No weekday-based TNF/MNF/RedZone generation is
implemented. UFC is one parent card with individual bouts; parent card start is
not represented as a verified main-card, broadcast or exact bout start time.

A global rolling-hour attempt budget defaults to 96; that is an Atlas limit, not
an assertion about ESPN quota. Reservations and unknown-outcome holds are committed
before upstream calls, so a process crash retains evidence and consumes budget.
A real process-crash regression test covers this boundary. HTTP 429 cooldowns are
persisted across all routes. Other failures produce per-key backoff, and HTTP-date
and numeric Retry-After values are bounded. There are no automatic hot retries.
The controller/operator must select production budgets and refresh policy later.

Successful empty responses are cached as empty. Failures never become successful
empty responses and never overwrite last-known success. Snapshots preserve original
observation/expiry times and cache-hit state. Last-known reads are explicit and
age-bounded, with a stale flag; neither cache reads nor stale reads can be counted
as new provider health successes. Future-day TTL is 15 minutes by default;
today/past-day TTL is one minute. Retention is bounded on successful writes.
Completeness is not inferred from a successful response or its event count.

## Canonical identity

Source identities include provider, league route and event ID. The registry has
no auto-enrollment, heuristic matcher, alias-chain following or automatic merge.
`resolve` returns None for an unknown source. Explicit writer-only enrollment
requires a provenance digest and atomically assigns a canonical owner plus aliases.
Once an identity has an owner it cannot move to another one. Conflicting batches
roll back, including newly proposed owner records. Repeated identical enrollment
is idempotent. Both primary-owned and independently owned source identities are
representable without fabricating SportsDB IDs.

A provenance hash is an audit reference, not proof that events match. A reviewed
policy/import boundary must validate evidence before invoking enrollment. No such
loader or production caller is installed, and the earlier five exact NFL matching
suggestions are NOT enrolled by this change. Durable league/team aliases and
integration with existing follows, recordings and source bindings remain required.

## Evidence and remaining integration

Fixtures project exactly the fields read by the parser from the user's public
response archive, SHA256
12f6d2e257041b41ec8596b5a9e17c717f3f1ba0f21fb2358b3ff2839a03ef4b,
captured 2026-10-16T01:36:30Z. Raw payload hashes and projected payload hashes are
retained. A projection is not a new provider observation. Samples contain 34
parent events: 12 NFL, 12 NBA, two MLB, two NHL, five EPL and one UFC card with
13 bouts. They do not establish full-league completeness or all-promotion coverage.

Before activation: select/provision writer-owned durable local state; install a reviewed identity import policy including team
and league aliases; complete writer deployment integration and the bounded
collector; wire search/follows/Upcoming with truthful coverage/freshness; handle
stale live status explicitly; validate Sunday completeness and reschedules; and
define effective capability health while retaining individual provider failures.
Wrestling, smaller fights and boxing fallback remain separate coverage work.
Do not bypass doctor or rewrite provider-health.json to enable deployment.


## Private writer boundary and team discovery

Authenticated GET `/internal/v1/metadata/day` accepts exactly `route` and an ISO
`day`; `/internal/v1/metadata/teams` accepts exactly `route`. They use the existing
Sports-writer bearer authorization. Structurally invalid queries cannot initialize state or consume upstream budget.
Out-of-horizon dates are rejected before any upstream attempt. Without `ATLAS_SPORTS_METADATA_STATE_DIR`, valid requests
return 503. The explicitly configured absolute directory must already meet the
store's private ownership/mode contract. The HTTP handler never provisions it.
A process-local initialization lock prevents simultaneous first requests from
constructing separate stores. No default production directory is chosen here.

Both endpoints return versioned field allowlists from parsed dataclasses, not
upstream JSON. Source URLs, provider credentials and users are absent. Original
observation and expiry times, route/day, cache-hit and stale flags travel with
the result. The private client validates identities, shapes and age and rejects
stale/expired responses. There are no automatic retries or redirect following.
The existing lightweight `/health` endpoint remains process liveness only;
metadata cache hits do not rewrite individual provider health.

Team directories use the same fixed ESPN origin, child-process deadline, 4 MB
response limit, SQLite cache, lock, rolling attempt budget and global 429 hold as
scoreboards. Their cache key uses a reserved `@teams` day discriminator within
schema 1; no schema migration is required. Directory TTL defaults to one hour.
Five captured directories cover NFL/NBA/MLB/NHL/EPL: 32/30/30/32/20 teams. UFC is
not treated as a team league. Directory availability does not depend on whether
a team has a game in a seven-day window. Public entity IDs include the route;
this does not authorize cross-provider aliases or enroll canonical owners.
An empty search query returns no directory suggestions.

The team fixture projects fields from archive SHA256
817d2edde6e2d377c301de760465a4dfab19bb79d51b8cf369051836fcdda479,
captured 2026-10-16T02:56:25Z; individual original payload hashes are retained.
The source topology review confirms writer/controller share the `atlas` network,
while writer has its own image and state/config mounts. Existing packaging copies
all providers, so these modules need no new Docker COPY directives. Before use,
provision a separate durable local writer-owned state mount, validate backup and
rollback preservation of identity state, configure controller credentials through
the canonical deployment path, then install the collector/discovery caller. No
mount, environment credential, alias, production cache or sharing policy is
modified by this source candidate. End-user search/follow/Upcoming integration
and effective capability health remain outstanding.


## Cache-only seven-day schedule collection

Authenticated GET `/internal/v1/metadata/schedule` takes exactly `route`,
`start_at` and `end_at`. Both timestamps must carry a timezone, and the half-open
window must be positive and at most seven days. The collector requests at most
nine cached date buckets: the UTC window dates plus the preceding provider
calendar bucket where the broker's yesterday-through-day-seven horizon permits.
This handles provider calendar dates and Sunday-night games with Monday UTC
kickoffs without inventing a programme or moving a kickoff to a different date.

The broker reads the bucket set under one lock and SQLite read transaction.
Collection never calls upstream, consumes request budget, renews timestamps or
rewrites provider health. Missing and invalid buckets are explicit; stale
snapshots preserve their observation/expiry time. Bucket retry delays reflect
existing holds. A separate explicit `refresh_one_schedule_day` primitive admits
at most one day request through the existing broker. It skips fresh and held
buckets and returns/raises the original broker outcome. No loop, daemon, cold
cache fan-out or production refresh policy is installed by this change.

The versioned private response carries only the selected window and bucket
snapshots/statuses, with a four-MB aggregate response budget. It fails rather
than silently truncating. The client validates the full requested bucket set,
recomputes the schedule and rechecks expiry at delivery. Missing dates cannot
be interpreted as successful empty dates. A cold cache returns partial coverage.
`all_buckets_fresh` describes cache observations at the evaluation time; it is
not proof of all-league or upstream schedule completeness.

Events reconcile by route and provider event ID before timestamp/status filtering.
The most recently observed record wins, including a newer cancellation/final
record or a reschedule outside the window. Equal-observation conflicts are
withheld explicitly instead of choosing a date-bucket order. Identical overlaps
collapse. Unknown times stay unknown and keep the result partial. Stale scheduled
entries can be retained with explicit age; stale live status never qualifies for
`fresh_live`, and this collector cannot grant playback availability.

Production integration remains open: choose/sustain refresh cadence within the
shared budget, provision and protect durable writer state, validate backup/restore,
wire the collector into user discovery/Upcoming and background consumers, and
install reviewed league/team/event identities for existing follows. The current
SportsDB provider and all runtime health, ownership and sharing policies remain
unchanged. The schedule collector is not automatically registered or enabled.


## Metadata backup integration

The canonical future host state directory is
`${ATLAS_RUNTIME_CONFIG_DIR}/private/sports-metadata`, normally
`/mnt/storage/configs/atlas/private/sports-metadata`. No directory, mount or
configuration is provisioned by this change. `atlas backup` checks that path:
an absent installation keeps recovery format 2; a present installation must be
complete and successfully captured or backup publication fails.

Metadata is captured as a separate application-consistent `metadata-recovery`
artifact using the shared writer file lock and SQLite online backup, then detached
from WAL into one private database. Recovery format 3 requires this artifact and
its integrity/schema/identity validation in addition to existing format-2 state.
Formats 1 and 2 remain readable. The 16 filesystem replacement surfaces are
unchanged. Older readers reject format 3 rather than silently omitting metadata.
Live native-backend/metadata restore remains unsupported; format 3 is explicitly
blocked before live mutation. See `docs/operations/SPORTS_METADATA_RECOVERY.md`.


## Optional writer-owned automatic refresh

The private writer can now own an explicitly configured refresh worker for its
process lifetime. Missing/disabled `ATLAS_SPORTS_METADATA_REFRESH_FILE` starts no
worker and creates no state. This change installs no policy, mount or environment
value, so production remains inactive. Explicit policy and private state must be
ready before startup; invalid enabled state prevents that configured startup.

The worker selects one due job per tick: expired/missing today buckets first,
then missing team directories, missing dates and other expired observations.
It reads cache and hold state before selection and uses the same broker admission,
process deadline, shared rolling budget and cooldown for the selected request.
UFC gets scoreboard requests only. Policy budgets must cover the nominal chosen
cadence; that calculation is neither an ESPN quota claim nor a freshness SLA.
Past-day TTL can be selected independently; the default remains the previous
current-day TTL when no policy is configured.

Policy is reread per tick. Removing/disabling it pauses subsequent automatic
admissions after the in-flight operation. Invalid configuration produces no new
refresh requests. With an explicit refresh-policy environment path, private metadata
requests also require a valid enabled policy. Cache hits/no-work ticks do not
advance the worker's provider-success timestamp. The authenticated refresh-status
endpoint is process observation only; it cannot mark global provider health healthy.
SportsDB doctor behavior and provider-health.json remain unchanged.

SIGTERM/SIGINT close the worker and server; closing prevents new worker admissions
and waits up to 25 seconds for in-flight work. A failure to stop does not report a
clean exit. Before enabling this configuration in Compose, provide a stop grace
period of at least 30 seconds alongside the private state/policy mounts and tested
recovery path. Public maintenance alone does not pause this worker. Details and an
uninstalled policy example are in `docs/operations/SPORTS_METADATA_REFRESH.md`.
