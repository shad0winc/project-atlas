# Independent Sports metadata broker foundation

Status: inactive source foundation. No default instance, production state path,
provider registration, API route, worker hook, configuration or migration is
installed. Importing these modules does not create cache or identity state.

## Ownership and storage

The private Sports writer is the intended sole metadata owner. API and background
consumers will eventually use its authenticated service boundary; they must not
construct independent upstream clients. That integration is not part of this
change. Explicit construction takes a caller-provisioned directory owned by the
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
and league aliases; implement the authenticated writer integration and bounded
collector; wire search/follows/Upcoming with truthful coverage/freshness; handle
stale live status explicitly; validate Sunday completeness and reschedules; and
define effective capability health while retaining individual provider failures.
Wrestling, smaller fights and boxing fallback remain separate coverage work.
Do not bypass doctor or rewrite provider-health.json to enable deployment.
