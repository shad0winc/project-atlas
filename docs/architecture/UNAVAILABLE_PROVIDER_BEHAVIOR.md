# Unavailable-Provider Behavior Architecture

## Purpose

This document defines how Project Atlas behaves when an external or
infrastructure provider is unavailable, unreachable, unauthorized, timed out,
or returns unusable data.

M-023.23 verifies the existing provider-specific boundaries and hardens only
gaps demonstrated by deterministic tests. It does not create a parallel
provider framework.

## Safety Invariant

> Provider unavailability must remain observable, must not be interpreted as
> an empty successful response, and must not authorize or replay an external
> mutation.

This invariant applies across read-only observation, provider mutation,
multi-provider aggregation, and provider-assisted safety checks.

## Failure Classes

### Transport or timeout failure

The provider endpoint cannot be reached or does not answer within the owned
timeout. The operation is unavailable, not empty.

### Authentication or authorization failure

The provider rejects configured credentials or the required credential is
missing. Atlas surfaces a provider failure and does not silently downgrade the
operation into an unauthenticated success path.

### Invalid provider response

The endpoint responds, but its payload cannot satisfy the domain contract.
Atlas treats malformed or structurally invalid data as failure rather than
inventing normalized values.

### Authoritative absence

When a provider protocol supplies an authoritative not-found result, a domain
may distinguish that result from provider unavailability. A 404 for a specific
Jellyfin resource is one such case. This distinction must not be inferred from
a general transport failure.

### Outcome-ambiguous mutation

The provider mutation may have occurred but Atlas cannot prove the result. The
operation is recovery-required. Automatic replay is unsafe unless the domain
has an idempotency or reconciliation contract that proves replay safety.

## Behavior Matrix

| Boundary | Unavailable behavior | Preserved state | Mutation behavior |
| --- | --- | --- | --- |
| Jellyfin media provider | Raises `MediaProviderError` for transport/protocol failure | Existing Atlas state remains authoritative | No mutation is inferred from failure |
| Jellyseerr request health | Returns explicit `unavailable` health | Request registry remains durable | Health observation is read-only |
| Media Request submit/cancel | Wraps provider failure and retains intent | `submitting` or `cancelling` remains recovery-required | Replay is blocked |
| Cleanup preview | Records preview failure | Assessment/audit facts remain visible | `modified=0`; v1.0 remains dry-run-only |
| Sports provider discovery | Marks provider degraded and continues isolated work | Non-finished monitored games and recording registry are retained | Existing recordings are not cancelled because discovery failed |
| Portal persisted snapshots | Returns explicit unavailable presentation contract when source snapshot is unusable | Last durable source rules remain separate from presentation | Read-only |
| Service Lifecycle inspection | Normalizes unavailable/unknown runtime health | Lifecycle configuration remains unchanged | Read-only inspection does not mutate runtime |

## Jellyfin Boundary

`JellyfinProvider` owns direct Jellyfin media operations. Its HTTP boundary
normalizes unavailable conditions into `MediaProviderError`:

- a missing API key is an explicit configuration error;
- non-404 HTTP errors are provider request failures;
- URL and timeout failures are reported as unreachable; and
- invalid JSON is a provider response failure.

An authoritative resource 404 has a specific internal not-found error so
preview logic can distinguish missing media from an unavailable server.

Optional enrichment may degrade independently. For example, failure to resolve
an item's library name may omit that metadata without converting the primary
item lookup into a false failure. Such soft degradation is allowed only where
the missing field is not authorization for a destructive action.

## Media Request Boundary

The Media Request provider contract already exposes `ProviderHealth` with
`healthy`, `degraded`, `unavailable`, and `unknown` states. `available` is false
for both `unavailable` and `unknown`.

The Jellyseerr HTTP provider converts HTTP, transport, timeout, OS, and response
contract failures into provider-operation errors. Its health surface maps
failed health requests and invalid health payloads to explicit `unavailable`.

Submission and cancellation use durable intent:

1. persist `submitting` or `cancelling`;
2. invoke the provider mutation;
3. persist the confirmed terminal/intermediate state only after success; and
4. retain recovery-required intent if the provider outcome is ambiguous.

A later caller cannot silently repeat that mutation while recovery-required
intent remains.

## Cleanup Boundary

Cleanup uses provider preview as a safety boundary. In v1.0 the default
executor supports dry-run only.

If provider preview fails:

- the affected item is not reported as successfully planned;
- the failure is present in the cleanup result and audit/event surface;
- partial preview is distinguishable from complete success; and
- `modified` remains zero.

Provider unavailability cannot create deletion authorization.

## Sports Boundary

Sports is intentionally a multi-provider aggregation boundary. One provider
failure does not require the entire worker to discard useful retained state.

`run_provider_pipeline()` isolates provider fetch failures, increments the
degraded-provider count, persists provider health information, and continues
with unaffected providers.

The state-preservation boundary is important when a provider produces no fresh
games because it failed:

- `plan_recordings([])` loads and writes the existing recording registry
  without cancelling retained recordings;
- `process_games([])` preserves previously monitored non-finished games; and
- provider health records the failure separately from lifecycle state.

An unavailable provider therefore does not mean that every event disappeared.

Subscription ownership remains the authority for pruning unmanaged Sports
state. Provider outage is not unsubscribe evidence.

## Read-Only Presentation Boundaries

Some Portal media surfaces consume persisted Atlas snapshots rather than a live
provider call. If their required source snapshot is missing or invalid, the
presentation contract exposes `unavailable` rather than fabricating counts.

This is intentional graceful degradation. Read-only presentation may become
unavailable while mutation and durable-state boundaries remain fail closed.

## Verification Strategy

### Deterministic automated tests

M-023.23 should prove at minimum:

- Jellyfin transport/timeout failure is a provider error, not an empty list;
- Jellyfin authoritative not-found remains distinct from general outage;
- Jellyseerr failed/invalid health is explicitly unavailable;
- Media Request provider mutation failure preserves durable intent and blocks
  replay;
- cleanup provider preview failure produces zero modification;
- Sports provider fetch failure marks degradation while retaining non-finished
  game and recording state; and
- existing read-only unavailable contracts remain stable.

Deterministic tests may use mocked transport errors or loopback endpoints that
are intentionally unreachable. They must not require a real production outage.

### Production validation

Production validation is read-only by default:

- confirm configured provider/runtime surfaces are observable;
- inspect current provider health without changing provider state;
- exercise existing read-only health endpoints or CLI contracts;
- run the deterministic unavailable-provider regression suite; and
- verify the repository remains unchanged.

Stopping or disconnecting a live provider is a separate controlled experiment
and requires explicit approval. M-023.23 does not require it when deterministic
tests prove the failure semantics and read-only production observation proves
the normal operational boundary.

## Recovery Expectations

Read-only health and aggregation paths recover when the provider next returns a
valid response. A healthy response may clear degraded provider health according
to the owning subsystem's state machine.

Outcome-ambiguous mutations are different. Connectivity recovery alone must
not clear `submitting` or `cancelling` intent. Those states require the Media
Request reconciliation boundary because the original external mutation may
already have occurred.

## Release Boundary

M-023.23 is complete only when tests demonstrate that unavailable providers are
observable across the selected v1.0 boundaries, retained state is not erased by
outage-shaped empty input, and no provider failure can become implicit mutation
authorization or automatic replay.

## Implementation Status

M-023.23 is complete.

Implementation and validation established:

- ADR 0021 defines the permanent unavailable-provider failure invariant;
- Jellyfin transport and timeout failure is explicit provider failure rather
  than a successful empty inventory;
- Media Request provider failures preserve durable mutation intent and block
  outcome-ambiguous replay;
- cleanup provider-preview failure remains non-destructive with zero
  modification;
- Sports provider outage records degraded provider health without discarding
  existing recording plans or non-finished monitored state; and
- read-only production validation confirmed live Jellyfin, Jellyseerr, Service
  Lifecycle, and Sports provider visibility without interrupting a provider.

Final automated validation passed 264 provider-related regressions plus 13
subtests. Production validation observed healthy Jellyfin and Sports provider
state, running Jellyseerr with its known missing Docker healthcheck, and zero
provider, Sports-state, or repository mutations.

The architecture commit is `15a502b5`; the dedicated safeguard-test commit is
`faf17404`.
