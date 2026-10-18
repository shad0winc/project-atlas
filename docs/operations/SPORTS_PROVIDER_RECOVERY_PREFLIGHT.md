# Sports provider recovery preflight

## Problem and bounded change

On 2026-10-18 UTC, `atlas health --compact` at source
`79cf73747f9a979ea02fb77446f2fa61df8e3451` reported 36 healthy checks and one
critical check: `module:sports / Provider Health`. Controller heartbeat, Docker
health and the five temporary storage write probes passed. This establishes the
reported checks at that observation; it is not provider recovery or sustained use.

The normal update transaction refuses a critical pre-update Doctor. Updating
only ingress would leave the Sports controller on its old loaded provider code.
The explicit candidate command is:

```
atlas update all --migration none --recover-sports-provider
```

This is a full `all` rollout using the existing preparation, backup, maintenance,
apply and recovery contracts. It can pull/build/apply Core, ingress and managed
Sports; it is not a two-container-only deployment. This document and candidate
verification do not authorize or execute that rollout. Do not run it until the
candidate passes CT100, RC/main review, source synchronization, and a separately
reviewed production activation block.

Ordinary update commands keep the existing Doctor behavior. The additional flag
is accepted only as the fourth argument, with `all --migration none`. Unknown or
extra arguments fail before deployment preparation. It cannot be enabled through
an environment variable. The previous baseline must have adopted Sports evidence.

## Admission algorithm

The recovery preflight takes one structured health observation through the same
collector as Doctor. It accepts only collector exit code 0 or 1. The helper reads
at most 1 MiB of JSON from stdin, rejects duplicate JSON keys, and requires schema
1 and a timezone-aware observation no more than 30 seconds old, with no future
clock skew accepted. Check identities must be unique and rows must be well formed.

All 37 identities observed in the known CT100 contract are required: Core,
infrastructure, ten services, five storage write probes, seven project documents,
and seven Sports checks. Additional healthy checks are permitted. Missing checks,
duplicate identities, warnings, unknowns or additional critical results refuse
admission. A fully healthy report with collector exit 0 receives a receipt with
zero exceptions, accommodating recovery between the earlier diagnosis and update.

For a degraded observation, exactly one nonhealthy identity is allowed:
`module:sports / Provider Health`, critical, with the exact expected message,
module `sports`, provider_count exactly integer 1, and the expected provider file
path. The helper then opens the fixed production provider-health path with
O_NOFOLLOW/O_NONBLOCK, requires a regular single-link file at most 256 KiB, and
rejects duplicate keys. It requires exactly `thesportsdb`, degraded status, the
exact existing `Sports provider is temporarily rate limited.` error and a
last-failure timestamp no more than 90 seconds old. Missing/unreadable reports,
authentication/HTTP/network/unknown errors, other providers, stale timestamps and
invalid contracts fail closed. No upstream request is made by the classifier.

The private reader does not reset cooldown, edit provider health, change quota,
rewrite configuration or mark stale games fresh. Its diagnostic refusal withholds
raw values. Provider detail paths in the structured check must use the existing
fixed contract; a custom deployment path requires a separately reviewed change.

The update record receives an exclusive `provider-recovery-preflight.json`
receipt containing the observation hash, accepted time, check count, admission
classification, exception count and, for rate-limit admission, provider-report
hash. Raw health/provider payloads and credentials are not retained in it. An
existing receipt cannot be overwritten. Failed classification may leave an empty
receipt in an aborted record; it is not acceptance evidence.

## Transaction and failure boundaries

Source validation, current baseline runtime verification, shared Scheduler
exclusion, durable deployment lock and previous-source/image capture still
precede the gate. A refusal marks the transaction aborted and releases its
owned deployment lock. No artifact acquisition, maintenance or apply follows a
refused preflight. Artifact acquisition failure after accepted admission retains
the existing abort-before-maintenance behavior and the admission receipt.

Network pulls/builds and target-image completeness checks still happen before
maintenance. Existing runtime bootstrap, maintenance, validated pre-update backup,
deterministic no-build/no-pull apply and applied-image capture remain unchanged.
All-scope apply covers both ingress writer and managed Sports controller. Effective
runtime versions, image IDs, shared budget path and source mounts still need
production verification; merely accepting preflight proves none of those facts.

Both private and public post-update verification still require Doctor success.
The existing bounded transient grace (six attempts, five 30-second waits) remains
unchanged; persistent provider degradation fails. After maintenance begins,
existing failure handling retains maintenance and the deployment lock for explicit
recovery. Existing rollback requires its own validated assets and checks. The
recovery flag is never consulted by post-apply verification or rollback.

Public-key upstream capacity can still be consumed by other clients. The shared
20-request rolling-minute budget is not a promise of provider recovery. A full
rollout may produce a new image different from the separately staged image; record
and verify the actual built/applied IDs rather than treating the old staging tag
as automatically deployed.

## Evidence and remaining gates

Local candidate verification: 20 new unittest cases, with refusal matrices for
all 36 other checks at warning/critical/unknown, every omitted required identity,
malformed/duplicate contracts, stale evidence, provider file safety, CLI scope,
exclusive receipt publication, transaction abort boundaries, both-caller scope and
persistent post-apply degradation. All 56 existing update transaction tests also
passed against the changed update script. Shell syntax and whitespace checks pass.
Local tests use subprocess mocks and private files. Subsequent CT100 acceptance
passed: explicit UID1000/no-groups 76 tests and 178 subtests; corrected focused
regression 131 tests and 178 subtests; full core 5531 tests and 1741 subtests.
The source-order assertion correction and private pytest basetemp lesson are
recorded in V1_SPORTS_RECOVERY_PROGRESS.md. RC/main CI and production rollout
remain pending; these tests do not establish production provider recovery.

The historical recovery ledger records canonical transfer, Notifications adoption,
provider-budget merge and staged-image evidence separately from this candidate.
Live format-3 restore remains blocked. Media browse work remains queued after
Sports, and no final release tag is created by this work.
