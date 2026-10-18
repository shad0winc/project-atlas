# Bounded controller refresh progress across upstream throttling

## Observed production failure

Canonical main is `f8696d95bbf4488d95c2243e54c305010ae5b22c`, RC1 is
`5be6f4bf92fcca0834e4103266cd8a8aec61bc17`, and the historical checkout remains
frozen at `79cf73747f9a979ea02fb77446f2fa61df8e3451`.

The all-scope update `update-20261018T045650Z-2853292` applied its target services
but failed the post-update Provider Health gate. Maintenance and its owned lock
remain held; active baseline is `baseline-20261018T035020Z-2649543`. All 26
recorded applied image identities matched running containers. Both provider
callers had the budget fix and used free key 123. No credential was exposed.

Morning state still showed a degraded provider and an active shared cooldown.
A single budgeted daily-event request returned three events. A budgeted request
to the first controller endpoint, eventslast.php, returned one event. A traced
controller-style refresh then made ten successful requests and received an actual
upstream HTTP429 on invocation 11, an eventsday.php request, with Retry-After120.
The probes did not write games or provider-health state and respected the shared
budget. This proves that successful individual endpoints do not establish a
completed refresh. It does not establish an undocumented universal provider quota.

The production plan contained 38 unique requests: one eventslast.php, one
eventsnext.php, fifteen eventsday.php for the retained 14-day horizon, and 21
lookupevent.php. Targets were one team, one league, four explicit events and
17 tracked events. Normal non-search cache TTL is 300 seconds. The worker creates
new provider instances on every cycle; its process-local response cache survives
those instances, but entries expire while later requests remain deferred.

An offline model using the actual old provider code, 38 requests, 30-second cycles
and a synthetic 429 on each eleventh dispatch with Retry-After120 failed to finish
for 1800 simulated seconds (176 dispatches). This demonstrates a starvation
mechanism compatible with the observed failure. One real trace does not prove
that every production cooldown follows the synthetic pattern.

## Candidate behavior

The controller opts into `fetch_games_resumable` when a provider implements it,
with the ordinary fetch_games fallback retained for other providers. Interactive
fetch_games and request_json calls retain their immediate behavior and ordinary
response-cache TTLs. The request budget, lock, charged failures and full persisted
Retry-After remain authoritative; the candidate neither increases quota nor
shortens or clears cooldown.

A separate process-local checkpoint retains successful raw responses for one
complete background snapshot across rate-limit deferrals and newly created
provider instances. It is keyed by a non-persisted credential digest, UTC day,
horizon and normalized target sets. Changed targets, credential or day cannot
consume another checkpoint. No checkpoint file, new production registry or
persistent credential material is created. A process restart discards incomplete
work safely rather than claiming crash-resume acceptance.

Only successful request results are staged. Rate-limit exceptions retain that
work and propagate normally: the provider stays degraded, and no incomplete
snapshot is returned. Other errors, cancellation, size failures and invalid
normalization discard the checkpoint. Once all requests and normalization finish,
the full result is returned and the checkpoint is removed.

Checkpoint age is bounded to 900 seconds from its oldest response observation,
including an original response-cache observation that predates checkpoint
creation. Retries never advance this age. Expired work is discarded before reuse;
expiry during a request refuses publication. Future cache observation timestamps
and regressed/nonfinite monotonic clocks fail closed. Ordinary cache timestamps
are never extended or rewritten from checkpoint data.

**This deliberately permits a completed background snapshot to contain responses
older than the ordinary 300-second cache TTL, within the explicit 900-second
snapshot bound.** It is not an assertion that all data became fresh at completion.
The successful provider-health row carries refresh_snapshot with the oldest
response age, maximum age and completed request count. Event payload timestamps
remain provider supplied. Provider healthy means the complete bounded snapshot
finished; fresh live-game behavior still needs its own production acceptance.

Limits: at most eight plans, 128 successful request results and 4 MiB serialized
response bytes per plan. Python object overhead and the separate ordinary cache
are additional. An opt-in refresh lock serializes checkpoint mutation; the original
provider instance's request method is never replaced. Interactive calls do not
acquire this lock or consume checkpoint results.

## Acceptance and deployment boundary

The new offline tests reproduce the old starvation, then complete the same
38-request plan at 360 simulated seconds with 41 dispatches: 38 successes plus
three429s. They retain 14-day discovery, cover new provider instances and actual
worker health transitions, complete normalized event publication, unchanged
interactive/cache behavior, original observation age, expiry, changed identities,
clock regression, unknown errors, memory/request/plan limits, concurrent callers,
and absence of checkpoint files. Related existing budget, discovery, provider and
metadata checks are run separately. Subsequent CT100 acceptance passed explicit
UID/GID1000/no-groups37 tests and20 subtests, then full core5550 tests and1746
subtests. Installer and final checks preserved canonical/historical roots, baseline,
failed transaction, maintenance and its owned lock. RC/main CI and production
activation remain pending. The ledger retains the detailed observed test output.

This candidate is applied only to an isolated feature worktree. Canonical main
is currently live-mounted into the controller. Do not fast-forward or edit it as
if that were a source-only operation, restart callers ad hoc, overwrite the failed
transaction's source claims, clear maintenance, or release the lock manually.
Production activation needs a separately reviewed repair/recovery transaction
that preserves the original failed record and accurately records resulting source
and image identities. Successful candidate tests do not authorize such activation.

The existing failed-after-apply recovery command can verify an already applied
target once all of its gates pass; it does not install this new source. A repair
must not relabel f8696d95 artifacts as containing these changes. Live format-3
restore and the final release tag remain blocked; Media browse follows Sports.
