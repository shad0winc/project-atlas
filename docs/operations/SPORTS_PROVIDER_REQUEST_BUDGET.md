# TheSportsDB shared request admission and production preflight

## Observed production checkpoint

User-run read-only CT100 checks on 2026-10-18 UTC confirmed clean canonical
main `3e4c0f9e6edf622434710400fd49190c326726af`, RC1
`6b20c39ba07597bb6bb6da60bd688dafa0356193`, version `1.0.0-rc.1`, and unchanged
active deployment `update-20261015T211211Z-632971`. All 17 inspected, present
containers were running. Configured Docker health checks were healthy; several
media services have no Docker health check. Runtime identities remained stable.
No separate `atlas-sports-db` container or module health script was present;
that observation alone does not establish a database fault. Dispatcharr and
Teamarr were present and Docker-healthy. Database connections were not opened.

Sports `/health` returned HTTP200/healthy, while `/health.json` and stored
health reported degraded provider health. The static nginx route proves
liveness only. Controller heartbeat, recorder, recordings and reported storage
health were healthy. Storage observations found the local ext4 configs root and
mergerfs bulk root. Actual media/download clients mount downloads from
`/mnt/storage/downloads`; presence of `/mnt/atlas-pool/downloads` is not evidence
that clients use it. No storage write probes were run. Doctor/preflight was not
certified by this inventory.

TheSportsDB health recorded 5,177 consecutive failures, 21 games at the last
success, and a last-success age of 188,433.5 seconds (about 52 hours). This is
controller failure accounting, not an upstream request count or proof that the
stored games are fresh. A subsequent cooldown observation found a valid active
shared cooldown with about 44.6 seconds remaining and file age 75.4 seconds,
consistent with a 120-second deadline. The five-minute Retry-After cap was not
established as the cause of this observed cooldown.

Controller and writer both had the same documented public key; no key was
printed. Both configured one league, a 14-day background discovery horizon and
15-second HTTP timeout. The controller interval was 30 seconds. Configured league
count is not a measurement of actual active subscription targets or traffic.
Provider source SHA256 was
`1878422570e6b48a2304ac6516295d13a3c2e47cf455e1c93b50b8e3844c325f`;
worker source SHA256 was
`1e60a8a397e6db90fed17c87f1ca3685d9b9fac8e4b7ed3673d8285ac93cd0d5`.

Official documentation reviewed 2026-10-18 lists free 30, Premium 100 and
Business 120 requests/minute, and documents public key 123 (testing material also
mentions 3). These published limits are context, not proof of the quota actually
applied to this server or control over other consumers of the public key.
Sources: https://api.thesportsdb.com/documentation and
https://api.thesportsdb.com/docs_api_testing .

## Problem and resulting behavior

Previously, uncached requests went directly upstream. The shared JSON artifact
recorded a cooldown only after an HTTP 429. Successful response caches were
bounded but local to each process. Multiple processes could each emit uncached
requests before learning about a cooldown. Retry-After values longer than 300
seconds were shortened before being persisted.

The candidate retains the 14-day background discovery configuration and existing
endpoint/status semantics. Every uncached TheSportsDB request now reserves one
of 20 shared admissions in a rolling 60-second window before calling urlopen.
The conservative fixed limit is shared across all credentials using the same
artifact, rather than attempting to infer account entitlement from a key. It is
not a configurable Premium policy or a fleet-wide/global provider quota.

Fresh local cache hits return without a reservation or network call, including
while a cooldown is active. Cache entries retain their original 60-second search
and 300-second discovery TTLs; no stale entries are promoted to fresh. Identical
cache misses in different processes can still consume separate slots. This
change does not introduce a shared response cache.

Under the existing `.lock` flock, admission rereads the cooldown, removes
reservations at least 60 seconds old, refuses if 20 remain, or appends the current
wall-clock epoch. The updated JSON is written to a private unique temporary
file, flushed/fsynced, atomically replaced and its parent directory fsynced
before HTTP is attempted. The lock is released before network I/O. Exhaustion
returns the existing provider-rate-limit exception and retry hint immediately;
there is no long sleep inside a request handler.

HTTP/network/parse failures and a process dying after admission remain charged.
Uncertainty is not refunded. Cooldown updates use the same lock and preserve
admissions and the longest known deadline. Legacy cooldown-only documents keep
their deadline and start with an empty admission history. Provider Retry-After
seconds/dates retain the full positive duration; client retry hints may be at
most 300 seconds, but repeated hints cannot shorten upstream exclusion. Missing
or malformed Retry-After retains the existing 60-second fallback.

State is bounded to 16 KiB and 20 numeric, finite, nonnegative reservation epochs.
Invalid existing documents, duplicate JSON fields, symlinks/hardlinks, invalid
lock files and persistence errors refuse uncached upstream work. They are not
silently reset. Backward clock movement retains future reservations, which can
extend refusal until the clock catches up. Do not delete the artifact to clear
a legitimate cooldown. Newly replaced budget files have private temporary-file
permissions; controller and writer must retain their verified shared numeric
UID 1000 and writable parent mapping.

## Verification and acceptance boundaries

Local: 18 new offline unittest cases passed, including 40 concurrent fresh
processes with exactly 20 admissions and 20 refusals; durable charge after process
death; rolling-window boundary; cooldown race; legacy migration; HTTP 429 3600-
second persistence and restart refusal; network failure charge; malformed/link
refusal; file and directory sync failure; cache reuse; and a synthetic 14-day,
one-league/21-event fetch that completes 36 uncached endpoints across two budget
windows. This synthetic workload is not a measurement of production traffic.
Nine existing provider/cooldown/discovery contracts and eight discovery
capability tests also passed: 35 local cases total in the final related run.

Numeric UID/GID1000 execution, full core pytest and the combined regression
remain CT100 acceptance gates. The new provider-budget diagnostic runs the
existing coordinated native-consumption rehearsal with the new reviewed source
pins and current base HEAD. Its disposable default-command applications do not
exercise real TheSportsDB access. It proves compatibility with the accepted
private recovery chain, not production provider recovery.

No live requests were made while preparing or testing this candidate. The
observed production degradation remains unresolved until controlled rollout and
sustained verification show new successful provider refreshes and fresh data.
Old processes do not implement admission and can overwrite the legacy JSON
shape without retaining new fields. There is no mixed-version enforcement
claim: both controller and writer, and any other direct caller, must use the
reviewed version and same budget/lock mapping before the new limit is accepted.
The controller binds canonical source; the writer embeds source in its image.
Canonical source synchronization alone does not deploy that writer code or
change imports already loaded in running processes. Build and rollout are
separate gated work; this packet does not perform either.

External public-key users and provider-side restrictions can still produce 429.
Production acceptance must confirm effective source/image versions and mounts,
retain rather than reset the cooldown, observe successful refresh timestamps
and appropriate data freshness over repeated cycles, and distinguish local
budget refusal from actual measured upstream responses. General acquisition,
protected Sports access, production recovery controls and deferred Media browse
work remain in scope of their existing acceptance documents.
