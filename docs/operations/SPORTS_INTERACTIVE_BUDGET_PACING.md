# Interactive Sports budget pacing

A cold seven-day league schedule enumerates today and seven following dates.
The existing global burst allowance permits four new upstream requests in ten
seconds. The fifth date therefore produces a local HTTP 429 even with a
successful provider. The first four responses remain in the shared cache.
Previously one click ended at that intermediate deferral.

The Portal preserves the HTTP Retry-After header on AtlasApiError. Safe
Sports searches retain no more than three HTTP attempts, twenty seconds of
cumulative waits, and a thirty-second cancellable operation. Search federation
also retains its thirty-second per-provider window.

Schedules have a separate bounded continuation: at most twelve safe GET
attempts, ninety seconds of cumulative waits, and a two-minute cancellable
operation. Two cold followed leagues require sixteen date fetches and cannot
complete under the old three-attempt/twenty-second window; three leagues can
also encounter the twenty-per-minute ceiling. The longer schedule operation
honors each server hint and reuses completed cached dates. No partial schedule
is published as complete. Missing or excessive hints stop; auth, other HTTP
errors and network failures are not retried. Transport retries remain disabled.
Leaving the page or changing the refresh selection cancels pending work.

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

College-football league aliases (including NCAA, NCAAF and college football)
resolve through TheSportsDB league 4479. The returned league identity and
American Football sport must match before a result is shown; the current name
comes from the provider. Alias variants share the same lookup/cache identity.
A missing provider result remains empty; aliases do not manufacture events or
playable sources. Other league searches preserve their existing transport.
Do not replace search with the free all-leagues directory: the provider's
published documentation limits that directory, so it is not complete coverage.

The two-minute fixture tests cover one, two and three leagues, unchanged burst
and minute quotas, no duplicate fetches, cancellation, deadline and cumulative
wait bounds. Genuine provider cooldowns remain enforced. Local deferrals and
upstream throttling still share the existing public error contract; this change
does not claim to distinguish a historical 429 or eliminate upstream limits.
