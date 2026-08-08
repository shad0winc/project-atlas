# ADR-0021: Unavailable Provider Failure Semantics

## Status

Accepted

## Context

Atlas integrates with external and infrastructure providers whose availability
is outside the control of an individual Atlas operation. These include
Jellyfin, Jellyseerr, TheSportsDB, Docker-backed service inspection, and other
provider boundaries used by optional modules and operational workflows.

Existing subsystems already contain strong but provider-specific failure
contracts. Jellyfin raises explicit media-provider errors for transport and
protocol failures. Jellyseerr exposes normalized provider health and preserves
durable request mutation intent. Sports records provider degradation while
continuing unaffected work and retaining non-finished game state. Cleanup is
dry-run-only and records provider preview failure without modification.

The v1.0 reliability requirement is therefore not a new universal provider
framework. It is a shared failure-semantics boundary that prevents these
different integrations from treating unavailability as successful emptiness
or permission to mutate external state.

## Decision

Atlas adopts the following permanent invariant:

> Provider unavailability must remain observable, must not be interpreted as
> an empty successful response, and must not authorize or replay an external
> mutation.

Provider-specific APIs and models remain authoritative inside their existing
domains. They do not need to inherit from a new common provider abstraction.

Atlas distinguishes these behaviors:

1. **Read-only observation** may return an explicit `unavailable`, `unknown`,
   or degraded contract when live data cannot be obtained. It must not invent
   healthy data or represent an unavailable response as a successful empty
   inventory.
2. **Required external mutation** fails closed when the provider cannot be
   reached or its outcome cannot be established. Durable mutation intent must
   be preserved where the domain already uses an intent state.
3. **Multi-provider aggregation** may continue unaffected providers when the
   failed provider can be isolated. Last-known state owned by the failed
   provider must remain preserved until fresh evidence justifies transition or
   removal.
4. **Provider-assisted safety checks** must fail before destructive action
   when their required evidence cannot be obtained.

Transport failure, timeout, authentication failure, malformed provider data,
and explicit provider-unavailable state are failures. A domain may distinguish
an authoritative resource-not-found response from provider unavailability when
the provider protocol supports that distinction.

## Mutation Boundary

Provider failure must not turn uncertainty into permission.

For Media Requests, Atlas persists `submitting` or `cancelling` before the
provider call. If the outcome becomes ambiguous, the durable intent remains
recovery-required and automatic replay is blocked.

For cleanup, the v1.0 executor remains dry-run-only. A failed provider preview
is reported as a failed or partial preview and `modified` remains zero.

For Sports, provider discovery failure does not authorize cancellation of an
existing recording or removal of non-finished monitored game state. Provider
degradation is recorded independently of the preserved state.

## Observability Boundary

Unavailable and unknown are explicit operational states, not aliases for
healthy or empty.

Provider errors may be normalized into domain-specific error types, health
models, workflow errors, or degraded health reports. The exact type is owned by
the domain, but callers must be able to distinguish failure from a successful
empty result.

## Validation Boundary

M-023.23 uses deterministic failure injection in tests for transport,
authentication, malformed-response, and provider-operation failures.

Production validation is read-only by default. It may inspect provider health,
container/runtime state, and existing public health surfaces. Deliberately
stopping Jellyfin, Jellyseerr, Sports providers, VPN infrastructure, or other
production dependencies requires a separate explicit approval and is not
needed to prove the deterministic failure contract.

## Consequences

Positive consequences:

- provider outages remain visible instead of looking like successful empty
  state;
- external mutations stay fail closed under uncertainty;
- Sports can degrade one provider without discarding retained state;
- existing provider contracts remain small and domain-appropriate; and
- production outage injection is not required for release validation.

Tradeoffs:

- domains continue to expose different error and health model types;
- callers must preserve the distinction between unavailable and empty; and
- recovery of ambiguous mutation intent may require later reconciliation.

## Non-Goals

This decision does not:

- introduce a second provider registry or universal provider base class;
- make every read path dependent on live provider availability;
- automatically replay outcome-ambiguous mutations;
- authorize destructive cleanup during provider degradation; or
- require intentionally taking a production provider offline.
