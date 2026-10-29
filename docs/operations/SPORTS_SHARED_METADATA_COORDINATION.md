# Shared Sports metadata coordination

Source candidate, not deployed or activated. Neither CI nor these fixtures prove
live discovery, provider plan coverage, playback, or invitation readiness.

The shared provider cooldown remains authoritative for cache misses. Successful
raw provider responses may be reused across writer/controller processes and
page reloads, retaining their original observation age. Existing TTLs remain
60 seconds for search and 300 seconds for discovery; expired responses are never
relabelled fresh. Only provider-level, user-independent data is stored. User
subscriptions and requested flags are computed downstream per authenticated user.
Keys include an HMAC with the configured provider credential and endpoint/params;
no plaintext credentials, queries, or exception messages are stored as keys.

Set SPORTS_SHARED_METADATA_CACHE_ENABLED=1 only after provisioning and verifying
identical private state access for the writer and controller. The default is 0;
invalid values refuse. The directory provider-request-coordination is under the
existing budget file's parent. Its owner must match the executing service UID,
its mode must be 0700, and database/lock files must be owned regular files at 0600.
Do not run a root-owned warmup which makes a non-root service's directory unusable.
Deploy both source consumers with truthful provenance and rollback; do not edit
running containers or reset/delete existing provider-request-budget.json.

The existing overall limit of 20 admissions per minute is not increased. The
additional coordinator caps background admissions at 12 per minute and overall
bursts at four per ten seconds. This leaves capacity for interactive work but
cannot guarantee availability if interactive demand also exhausts the allowance,
if other consumers use the same account/IP, or if the provider throttles a public
example key. These limits are conservative application defaults, not assertions
about the account's entitlement. Preserve the 14-day discovery horizon and the
controller cadence; cache misses and deferred checkpoints stay bounded.

Successful cache hits require no upstream request. Matching in-flight misses
use bounded nonblocking lock stripes, returning a short retry hint instead of
fetching twice or waiting indefinitely. Admissions commit before HTTP; errors or
process death do not refund quota. A short per-key failure backoff prevents
repeated non-429 failures from stampeding. Actual provider 429 handling continues
to persist the provider cooldown in the existing shared budget. Cross-process
SQLite locking is short and never held over HTTP. Cache memory/disk payloads,
entry counts, freshness, clocks and lock file counts are bounded. Expired data,
clock regression, unsafe ownership and directory replacement refuse.

The events endpoint previously collapsed rate-limit exceptions into generic 503.
Both the private handler and public API now preserve 429 and Retry-After. Genuine
transport/provider failures remain generic 503 without leaking backend details.
A healthy deferred controller snapshot can still be usable cached metadata; this
does not certify fresh interactive searches, live availability, or stream health.

Validation: 25 deterministic stdlib tests include two real local processes sharing
one in-flight request and cache, quota/headroom/burst checks, original cooldown
preservation, default-off behavior, and execution of the actual private events
handler methods with provider/store doubles. API HTTP regression is included for
CI. Full Core/API/Portal/Sports/release-contract validation remains pending.

Live acceptance after activation must demonstrate concurrent repeated NBA searches
reuse bounded upstream calls, controller progress and followed-league events
coexist, cooldowns are honored, stale or incomplete schedules are explicit, and
normal user isolation is retained. Then verify actual playback, limits, release,
failover and pilot access before invitations. Do not call the public example key
production-reliable on the basis of one successful HTTP 200.
