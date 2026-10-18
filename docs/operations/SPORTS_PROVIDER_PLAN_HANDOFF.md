# Bounded handoff when tracked Sports events change

## Observed failure

The rolling-renewal repair at `a552eb4d904ee0cb1e3b75ca837663c3c867c2b8`
held usable snapshots from the first observed completion at 19:59 UTC through
20:20 UTC on 2026-10-18. Two full completion markers were observed, but the
required third completion and sustained acceptance were not reached. The final
report contained 36 healthy checks and one critical Provider Health check.

Receipt:
`/mnt/storage/configs/atlas/deployments/repairs/rolling-refresh-jf2op8lu/sustained-health-789732d152a8.json`.
The last usable sample's oldest response was 795.664 seconds old. The next
sample was degraded, so this evidence did not justify assuming the 900-second
freshness gate itself caused the transition.

A read-only diagnostic found only rate-limit deferrals in the inspected known
failure messages. The current request plan was 41 unique requests: 15 day
requests, one recent-team request, one next-team request and 24 event lookups;
20 events were tracked. Timestamped controller logs established:

| UTC interval | Result | Tracked events | Subscription counts (event/team/league) |
| --- | --- | ---: | --- |
| 19:58:37–20:19:53 | 33 completed or retained snapshots, 25 games each | 20 | 4 / 1 / 1 |
| 20:20:33–20:26:47 | 12 rate-limit deferrals without usable current-plan coverage | — | — |
| 20:27:23 | Completed snapshot, 25 games | 19 | 4 / 1 / 1 |
| 20:28:03–20:32:00 | 8 rate-limit deferrals without usable current-plan coverage | — | — |

Tracked IDs are part of the exact complete-cache identity. Changing that set
starts a cold plan under the previous implementation even when every request
in the smaller plan already has a valid observation. An offline regression
reproduced loss of current-plan coverage while the prior complete plan remained
fresh. Unchanged subscription counts alone do not prove unchanged subscription
identifiers; the candidate enforces exact explicit identifiers itself.

## Candidate behavior

A new tracked-ID identity can borrow individual response observations only
from completed plans with exactly matching credential digest, UTC day, horizon
and explicit event/team/league target sets. It first enumerates the current
request plan without HTTP. It copies only current-plan responses, selecting the
newest actual observation for a common request. Original observation times are
never rewritten.

If every current request is covered, normalization runs again entirely from
retained response payloads. Its actual request set must exactly match the
planned set. Removed lookup payloads are not returned as games. Discovery data
can still legitimately include an event matched by a current league/team
subscription. Normal rolling renewal then continues on the new complete plan.

If a newly required request is missing, only the still-fresh common responses
seed a partial checkpoint. The usual shared admission and full upstream
Retry-After exclusion must obtain the missing response before publication can
claim a complete current plan. A previously complete, different plan is never
reported as coverage of a missing new request. True additions can therefore
still be unavailable during a provider cooldown; this patch does not promise
uninterrupted service when required data has not been obtained.

Completion timestamps remain conservative. An existing completion marker is
retained until every required response has a newer observation; only then may
a full-renewal marker advance. The oldest actual observation, age-at-completion
and elapsed-time health check still enforce the same 900-second limit. Expired
observations, clock regression, scope changes, unexpected request coverage and
memory/request overflow fail closed. Existing global eight-identity/4 MiB
complete-cache bounds and partial-checkpoint bounds remain enforced.

A complete donor whose oldest observation has already expired is not used,
even if some individual responses might still be fresh. This conservative
choice does not extend a donor's lifetime. Normal endpoint cache TTLs, the
shared rolling admission budget, provider Retry-After, worker publication,
health gates and production configuration are unchanged.

## Offline evidence and pending gates

Fourteen new tests cover cooldown contraction without HTTP, unchanged original
observations/completion markers, missing additions, fetching only a missing
request, credential/explicit-target/day/horizon isolation, expiry, clock
regression, cache bounds, normalization coverage, removed lookup data,
populated-game isolation, a slow-provider contraction/restoration sequence,
expiry during normalization and selection of the newest compatible observation.
All 80 focused local tests passed, including the preceding 66 regressions.

A deterministic 4,040-second fixture uses a 38-request initial plan, two seconds
per HTTP invocation, a 180-second Retry-After after every tenth success and a
single tracked-ID contraction during the run. This is a synthetic stress case,
not a provider quota guarantee.

| Variant | Full completion markers | Usable samples | Unusable samples after first completion | HTTP invocations |
| --- | ---: | ---: | ---: | ---: |
| Rolling renewal with exact identity cold restart | 5 | 85 | 17 | 220 |
| Bounded tracked-plan handoff | 5 | 102 | 0 | 220 |

CT100 targeted/full-core verification, RC-first/main promotion, isolated image
acceptance, managed activation and sustained live acceptance remain pending.
The running rolling-refresh repair is not changed by candidate installation.

## Deployment remains held

Canonical source remains clean main `f8696d95bbf4488d95c2243e54c305010ae5b22c`;
historical source remains detached at `79cf73747f9a979ea02fb77446f2fa61df8e3451`.
Remote main is `a552eb4d904ee0cb1e3b75ca837663c3c867c2b8`; RC1 is
`4ba8b3062429d3384a60af3874111c8f830559d7`.

Active baseline remains `baseline-20261018T035020Z-2649543`. Original failed
transaction `update-20261018T045650Z-2853292`, backup and recovery assets, all
linked repair journals, maintenance and original lock ownership remain held.
Candidate installation creates only an isolated feature worktree. It does not
activate, advance canonical source, reconcile deployment provenance, reopen
public traffic or release the lock. Media browse remains queued after Sports.

## CT100 acceptance: 2026-10-18 UTC

- Four frozen candidate postimages and Git/permission modes verified before and
  after isolated testing; installer applied without correction.
- UID/GID 1000 with cleared supplementary groups: 80 targeted tests and 30
  subtests passed in 2.40 seconds.
- Full core: 5593 tests and 1756 subtests passed in 453.39 seconds.
- Running rolling-refresh repair, original failed transaction, backup and source
  archives, active baseline, maintenance and original lock remained unchanged.
- Candidate installation receipt:
  /var/tmp/atlas-plan-handoff-candidate-jsm7p82_/receipt.json.
- The test command reported plan-handoff-tested-uncommitted-not-activated;
  installation receipt state remains applied-uncommitted-not-activated because
  that command did not update it. These observed test results are recorded here
  and in the separate promotion receipt without rewriting installation evidence.
- Protected RC/main CI, staged image acceptance, managed activation, sustained
  live acceptance and accurate private/public deployment reconciliation remain
  separate gates. Media browse remains queued after Sports.
