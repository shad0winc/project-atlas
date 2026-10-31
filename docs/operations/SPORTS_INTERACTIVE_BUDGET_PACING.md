# Interactive Sports budget pacing

A cold seven-day league schedule enumerates today and seven following dates.
The existing global burst allowance permits four new upstream requests in ten
seconds. The fifth date therefore produces a local HTTP 429 even with a
successful provider. The first four responses remain in the shared cache.
Previously one click ended at that intermediate deferral.

The Portal now preserves the HTTP Retry-After header on AtlasApiError. Safe
Sports search and events GETs may continue the same operation after that hint:
no more than three HTTP attempts, twenty seconds of cumulative waits, and a
thirty-second cancellable operation. Missing or long hints stop immediately;
other HTTP/network errors are not retried. Transport retries remain disabled.
Search federation allows thirty seconds per provider. A new browse cancels its
predecessor, and leaving the page cancels a pending browse.

Background admission is additionally capped at two new requests per ten
seconds. The existing global four/ten-second, twenty/minute and background
twelve/minute ceilings are unchanged. Interactive priority does not bypass
any provider cooldown, cache expiry, or quota. Long upstream cooldowns and a
busy budget can still yield a visible temporary limit after the bounded wait.

The seven-day horizon is preserved. No partial schedule is labeled complete,
and cached observation ages are not renewed on reads. Playback, recording,
follow mutations, maintenance, credentials and production state are outside
this source change. Multiple leagues may require more work than one bounded
operation can finish; this change does not promise unlimited browsing.

Validation uses mocked provider HTTP only: the actual provider fails after
four cold dates, then completes all eight after the exact retry delay, without
refetching the completed dates. Tests also cover background burst reservation,
actual Portal GET continuation, actual transport header preservation,
auth/network failures, cancellation, deadlines and retry bounds. Full Portal
lint/typecheck/tests/build and release gates remain required before deployment.

Rollout must cover the Portal and both consumers of the shared provider cache.
The live installation uses a layered publication and a narrow controller
provider overlay. Creating or merging this PR does not activate it. Retain the
current publication and maintenance until a separately verified component
rollout and live business acceptance complete. Do not reset the budget file or
replace the controller's entire source root to activate this change.
