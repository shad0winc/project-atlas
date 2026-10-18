# TheSportsDB bounded rolling renewal

## Observed production gap

The snapshot-availability repair at `959dc2a9f0475a11abcce4367caee4a0f5a25011`
completed two refreshes 611.773 seconds apart. During observation from
2026-10-18 18:33 through 18:53 UTC, the first completion was usable at
18:39:47, retained through deferred cycles, and exceeded its original-response
freshness bound by 18:44:17. The next completion was observed at 18:49:47.
All 37 native health checks were healthy at the end; sustained acceptance was
correctly false because availability had been lost between completions.

The immutable observation is
`repairs/snapshot-availability-dr7jfnlf/sustained-health-498b6a8fea5e.json`
under `/mnt/storage/configs/atlas/deployments`. A following read-only check
found degraded provider health, no complete-snapshot metadata, a shared
cooldown of 92.7 seconds and 11 admissions in the preceding minute. No provider
requests were added by that diagnosis.

## Candidate behavior

After the first complete plan, retain its exact endpoint/parameter response
set and each response's original monotonic observation. Subsequent controller
cycles renew due responses in oldest-observation order. They use the existing
`request_json` path, normal endpoint cache TTLs, durable shared request budget,
and full upstream Retry-After exclusion. A first cooperative deferral stops
that cycle's HTTP work. There is no parallel request fan-out or added caller.

If some responses were renewed, normalize the entire original request plan
again from retained responses, with network access unavailable to that
normalization path. Every planned response must be present, the request set
must match exactly, and the oldest actual observation must still be at most
900 seconds old. This can combine genuinely renewed responses with still-fresh
responses from the prior completed plan; it never publishes a partially
covered request plan.

`last_success_at` advances only after every response has an observation newer
than the preceding full-renewal completion. A cache hit or a cooldown alone
cannot advance it. Between full renewals, the unchanged completion timestamp
and the oldest remaining original response determine snapshot-age metadata.
Replacing the actual oldest responses can decrease the age-at-completion
value: this represents new provider observations, not an extension of their
lifetimes. Once all responses have renewed, the new full completion establishes
a new completion timestamp and its actual oldest-observation age.

The health contract is unchanged: age at completion plus elapsed time must
remain within 900 seconds. Expiry, clock regression, unknown provider failures,
changed plan coverage or overflow discards coverage and fails closed. Changed
credentials, targets, day or horizon still require a separately completed plan.

The retained complete-plan cache still has at most eight identities and a
4 MiB total serialized payload budget. Its accounting now includes provider
responses and their observation metadata as well as normalized games. Python
object overhead is additional. Cold progress retains the existing 128-request,
4 MiB per-plan and 900-second bounds. No cache is durable across process death.

## Offline evidence

A synthetic 38-request plan with two seconds per HTTP invocation and a
180-second Retry-After after every tenth success was sampled every 30 seconds
for 4,040 simulated seconds. This is a deterministic stress fixture, not a
claim about TheSportsDB's documented or guaranteed quota.

| Variant | Full completions | Usable samples | Unusable samples after first completion | HTTP invocations |
| --- | ---: | ---: | ---: | ---: |
| Previous completed-snapshot retention | 5 | 26 | 76 | 220 |
| Rolling response renewal | 5 | 102 | 0 | 220 |

The candidate improves coverage without increasing simulated HTTP invocations.
Twelve new offline tests cover the slow-provider sequence, oldest-first order,
partial renewal without completion timestamp renewal, cooldown immutability,
unknown failures, memory accounting/overflow, exact normalization coverage,
expiry, unchanged normal cache expiry, populated-game deep-copy isolation and
epoch regression. Existing snapshot tests now inspect retained complete-plan
response coverage and recognize full renewal even when a later request in the
same attempt receives a cooperative deferral.

CT100 tests, protected RC-first/main promotion, fresh isolated image acceptance,
activation and sustained production acceptance remain pending. This candidate
does not certify production throughput or public availability.

## Held deployment boundary

Canonical source remains clean main `f8696d95bbf4488d95c2243e54c305010ae5b22c`;
historical source remains detached at
`79cf73747f9a979ea02fb77446f2fa61df8e3451`. Remote main is `959dc2a9...` and
RC1 is `8f82c6c3...`. The running repair is the private source generation and
writer image described by `snapshot-availability-dr7jfnlf/activation.json`.

Current baseline remains `baseline-20261018T035020Z-2649543`; original failed
transaction `update-20261018T045650Z-2853292`, its recovery assets, both linked
repair journals, maintenance and original lock ownership remain preserved.
Installing this candidate only creates an isolated feature worktree. It does
not commit, push, activate, advance canonical source, reconcile deployment
provenance, reopen public traffic or release the lock. Media browse remains
queued after Sports recovery and deployment acceptance.

## CT100 acceptance: 2026-10-18 UTC

- Five candidate postimage hashes and permission modes verified.
- The initial installer stopped after applying the patch because it compared
  permission bits 0644 with the full Git mode 100644. A guarded continuation
  verified every file and corrected only the permission comparison; candidate
  source was unchanged. The candidate receipt records this correction.
- UID/GID 1000 with cleared supplementary groups: 66 targeted tests and 25
  subtests passed in 1.80 seconds.
- Full core: 5579 tests and 1751 subtests passed in 453.13 seconds.
- Running snapshot-availability repair, original failed transaction, backup,
  source archives, active baseline, maintenance and original lock were preserved.
- Candidate receipt: /var/tmp/atlas-rolling-refresh-candidate-92_drqgx/receipt.json.
- This records isolated candidate acceptance. Protected RC/main CI, staged
  image acceptance, managed activation, sustained provider health and accurate
  private/public deployment reconciliation remain required.
