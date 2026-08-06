# Interrupted-Request Recovery Architecture

## Purpose

Interrupted-Request Recovery makes external media-request mutations fail closed
when Atlas cannot prove whether a provider-side operation completed.

The design extends the existing Media Requests state machine. It does not add a
transaction coordinator, a second persistence system, or a background recovery
daemon.

M-023.18 is concerned with interruption safety and recovery visibility. It does
not claim exactly-once delivery across Atlas and an external provider.

## Problem

Media-request submission and cancellation cross a persistence boundary:

1. Atlas stores request state in its atomic JSON repository.
2. Atlas invokes an external provider such as Jellyseerr.
3. Atlas persists the provider result.

Today an interruption between steps 2 and 3 can leave Atlas with stale local
state even though the provider mutation succeeded.

For submission, Atlas can remain `pending` without a `provider_request_id` after
the provider has already created the request. Repeating submission can therefore
repeat the external mutation.

For cancellation, Atlas can remain in an active state after the provider has
already deleted the request. Repeating cancellation can therefore repeat an
operation whose outcome Atlas no longer knows.

Refresh is different. Provider refresh is observational: it reads provider
state and can be retried without repeating a provider mutation.

## Architectural Boundary

The existing responsibility split remains authoritative:

- `MediaRequest` owns normalized Atlas request state.
- `JsonMediaRequestRepository` owns durable Atlas persistence.
- `MediaRequestService` owns orchestration and transition rules.
- `MediaRequestProvider` owns provider-specific I/O.
- Provider systems own the actual provider-side request outcome.
- Events are best-effort observations after durable state changes.

Recovery extends these boundaries rather than replacing them.

## Durable Mutation Intent

Atlas records mutation intent before performing a provider mutation.

Two orchestration states are added to `MediaRequestStatus`:

- `submitting`: Atlas has durably committed submission intent but has not yet
  durably committed a provider result.
- `cancelling`: Atlas has durably committed cancellation intent but has not yet
  durably committed the cancellation result.

These states describe Atlas knowledge, not provider truth.

The required ordering is:

| Operation | Durable Atlas step | External step | Final Atlas step |
| --- | --- | --- | --- |
| Submit | `pending -> submitting` | provider submit | persist provider ID and normalized provider status |
| Cancel | active state -> `cancelling` | provider cancel | persist `cancelled` |
| Refresh | none required | provider status read | persist normalized status if changed |

If the durable intent write fails, Atlas must not invoke the provider.

If provider I/O fails after durable intent is committed, Atlas must not assume
the provider mutation failed. Network errors and process interruption can be
outcome-ambiguous.

If the provider succeeds but the final Atlas persistence step fails, the intent
state remains durable and visible.

## Fail-Closed Recovery Contract

`submitting` and `cancelling` are recovery-required states.

While a request is in either state:

- Atlas must not automatically repeat the corresponding external mutation.
- ordinary submission or cancellation must reject the operation.
- Atlas must expose the request as requiring reconciliation.
- operators and future automation can inspect the state without causing a new
  provider mutation.

Ambiguous external outcomes are durable, observable, and fail closed until
reconciled.

This preserves the Atlas reliability rule that uncertainty is not permission to
act.

## State-Machine Extension

The implementation extends the current request lifecycle rather than creating a
parallel recovery state store.

The important new transitions are:

| From | To | Meaning |
| --- | --- | --- |
| `pending` | `submitting` | submission intent durably committed |
| `submitting` | normalized provider state | provider result durably committed |
| submitted active state | `cancelling` | cancellation intent durably committed |
| `cancelling` | `cancelled` | provider cancellation durably committed |

`submitting` and `cancelling` remain non-terminal because the provider outcome
has not been reconciled.

Existing provider lifecycle states remain provider-facing facts. The new intent
states are Atlas orchestration facts and must not be presented as evidence that
the provider accepted or completed a mutation.

## Event Boundary

Durable request state is authoritative. Event delivery is not part of the
mutation commit protocol.

M-023.18 does not require new public events for the internal intent states.
Existing request events remain best-effort observations emitted after the
corresponding durable state transition. Event publication failure must not roll
back or replay a provider mutation.

If future consumers need explicit recovery-state events, that public event
contract can be designed independently without changing the durability rules.

## Reconciliation Boundary

M-023.18 provides safe recovery visibility, not automatic destructive
reconciliation.

The current provider contract can inspect a provider request when Atlas already
knows its provider request ID. It does not provide a reliable provider-wide
lookup keyed by the Atlas request ID.

That matters most for interrupted submission: the provider may have created a
request while Atlas never received or persisted the provider request ID. Atlas
cannot safely infer which provider request is the match.

Therefore the initial recovery contract may identify requests requiring
reconciliation, but it must not guess, resubmit, delete, or otherwise repair an
ambiguous provider outcome automatically.

Future provider-specific reconciliation may be added when a provider exposes a
stable, non-mutating correlation mechanism. Such work must preserve this
fail-closed boundary.

## Retry Semantics

Operations have deliberately different retry contracts:

- create is a local atomic repository mutation and remains locally retry-safe.
- submit is externally mutating and is not replayed from `submitting`.
- refresh is provider-read-only and remains retry-safe.
- cancel is externally mutating and is not replayed from `cancelling`.
- event publication remains best effort and never controls provider replay.

## Persistence and Compatibility

The existing media-request repository remains the persistence authority. Intent
state is stored in the existing request record so atomic repository writes also
protect the recovery marker.

No second journal is introduced.

The model must continue to follow Atlas contract standards:

- normalize inputs;
- validate request identity and child contracts;
- normalize timestamps;
- provide deterministic `to_dict()` output;
- have dedicated tests; and
- remain available through the package public boundary.

Older code that does not recognize a new status must fail validation rather
than silently reinterpret an intent state as safe-to-repeat work.

## Verification Requirements

Implementation is not complete until tests prove at least the following:

- intent persistence occurs before provider submit or cancel;
- provider I/O is not invoked when intent persistence fails;
- provider errors after intent persistence leave durable recovery-required
  state;
- final persistence failure after provider success leaves durable
  recovery-required state;
- repeated submit from `submitting` is blocked;
- repeated cancel from `cancelling` is blocked;
- successful mutations reach their normalized final state;
- refresh remains deterministic and retry-safe;
- recovery-required requests are observable without provider mutation; and
- public model serialization remains deterministic.

Focused tests must be followed by the broader Media Requests regression suite
and read-only production validation before M-023.18 is marked complete.

## Non-Goals

M-023.18 does not introduce:

- distributed transactions;
- exactly-once guarantees across Atlas and providers;
- a second request journal;
- automatic mutation replay;
- automatic provider-side deletion or resubmission;
- a reconciliation daemon;
- time-based assumptions that an ambiguous mutation failed; or
- replacement of the existing Media Requests domain.

## Related Decisions

- [ADR 0016 — Interrupted-Request Recovery Boundaries](../ADR/0016-interrupted-request-recovery-boundaries.md)
- [ADR 0004 — Runtime State Architecture](../ADR/0004-runtime-state-architecture.md)
