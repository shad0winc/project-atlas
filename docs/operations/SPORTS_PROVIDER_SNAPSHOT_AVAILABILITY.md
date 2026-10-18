# Bounded complete Sports snapshot availability

Status: candidate; production remains on the refresh-progress repair at
`5db0f48877c5d7b6c5b83aba31818f552a0dd739`. This follow-up is not activated.

## Live evidence and problem

RC PR 368 merged as `9f7db2daa6c864d7d50ac96afeee26c4a38c0075`;
main PR 369 merged as `5db0f48877c5d7b6c5b83aba31818f552a0dd739`.
Both had all six release-gate checks successful. CT100 accepted 5550 core tests
and 1746 subtests before those merges. The matching controller source generation
passed 37 offline tests, and its writer image passed 18 offline tests as UID/GID
1000. Both used isolated containers with networking disabled.

The guarded repair replaced only controller and writer. Its private journal is
`/mnt/storage/configs/atlas/deployments/repairs/refresh-progress-10tatfnw/activation.json`.
It retained the original failed transaction, backup, source archives, baseline
pointer, maintenance and deployment lock. Its applied-image manifest has 26
verified running rows. Canonical source is still pinned at
`f8696d95bbf4488d95c2243e54c305010ae5b22c`; historical source stays detached at
`79cf73747f9a979ea02fb77446f2fa61df8e3451`.

At 2026-10-18T17:02:28.418982Z the repaired controller completed all 38 requests.
The oldest response was 479.092 seconds old, inside the 900-second bound.
Receipt `provider-completion-2e6ec719ee19.json` recorded this first live success.
However, the next refresh entered cooldown. At 17:06:19 through 17:07:20Z,
health became degraded again while the last complete refresh was only 231–292
seconds old. Native health reported 36 healthy checks and Provider Health
critical. Receipt `health-observation-06e1e520d2c0.json` records the observation.
First completion therefore did not establish stable operational acceptance.

## Candidate behavior

A process-local cache retains only fully normalized, completed snapshots. The
identity includes credential digest, UTC day, discovery horizon and all target
sets. It never shares completed data across changed credentials or targets.
After a cooperative budget/cooldown deferral, the same identity can receive a
deep copy of the prior complete result while the next refresh continues to
accumulate private partial progress. No partial result is returned.

Coverage expires 900 seconds after the original oldest response observation,
not 900 seconds after a retry. Completion time and the original response-age
metadata remain unchanged on reuse. Only a genuinely completed following
refresh advances completion time. Unknown failures discard completed coverage;
missing, expired or clock-invalid coverage leaves the provider degraded.
Process restart drops this memory safely. There is no persistent snapshot cache.

Complete normalized results have an additional global serialized payload bound
of 4 MiB and at most eight identities. Python object overhead is additional;
this is not a hard process-memory limit. The existing partial-progress bounds,
normal response-cache TTLs, shared request budget and full upstream cooldowns
are unchanged. Large complete results can be returned without being retained.

The worker reports `refresh_state=deferred` and sanitized deferral metadata when
using prior complete data, while retaining its actual `last_success_at`.
Downstream resolution receives that complete result rather than an empty
partial result. The controller and native module health consumers both check:
original age at completion + elapsed time since completion <= 900 seconds.
Future/naive times and malformed snapshot metadata fail closed. Providers with
legacy healthy rows and no snapshot contract retain their existing behavior.
This change does not weaken the deployment health gate or fabricate success.

## Candidate validation and remaining gates

Local tests: 17 focused availability tests, 19 refresh-progress tests and 18
shared-budget tests passed. Focused coverage includes populated 21-event reuse,
caller mutation isolation, stable completion timestamps across deferrals,
following completion, expiry, changed targets, unknown failures, clock
regression, total complete-cache payload bounds, and both health consumers.
CT100 UID/GID 1000 and full-core validation are still required. RC-first and main
protected PRs precede any new managed activation. Sustained live health,
accurate mixed-runtime reconciliation, private/public doctor and verify checks,
and release of maintenance/lock remain separate unfinished gates.

Do not upload repair plan JSON or configuration overlays: they contain resolved
service credentials. Source archives exclude the private configuration overlay.

## CT100 acceptance: 2026-10-18

- Eight candidate file hashes and modes matched the frozen packet.
- Corrected test-launch PATH so child `python` resolves to the existing shared
  `/opt/project-atlas/.venv/bin/python`; the first core attempt had nine missing-
  executable failures, with 5558 tests passing. No source correction was needed.
- Restore-state validation rerun: 10 passed in 0.91 seconds.
- UID/GID 1000 with cleared supplementary groups: 54 focused tests and 25
  subtests passed in 1.29 seconds.
- Full core: 5567 tests and 1751 subtests passed in 448.52 seconds.
- Running repair, original failed transaction, backup, source archives, baseline,
  maintenance and original deployment lock remained unchanged.
- This records candidate acceptance only; protected RC/main CI and a separate
  managed activation plus sustained live acceptance are still required.
