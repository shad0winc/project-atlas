# ADR-0016: Interrupted-Request Recovery Boundaries

## Status

Accepted

## Context

Atlas media-request submission and cancellation combine durable local state
with external provider mutations.

The provider call and the Atlas repository update cannot be committed as one
atomic transaction. A process interruption, timeout, or local persistence
failure can therefore leave Atlas unable to prove whether the provider mutation
completed.

Repeating an ambiguous submission can create a duplicate provider request.
Repeating an ambiguous cancellation can act on a request whose deletion may
already have completed.

The existing request repository already provides atomic Atlas-local writes, and
the existing service already owns orchestration. Atlas should extend those
contracts instead of creating a parallel transaction system.

## Decision

Atlas will persist durable mutation intent before externally mutating request
operations.

The request lifecycle gains two orchestration states:

- `submitting`
- `cancelling`

The service must persist the appropriate intent state before invoking provider
submission or cancellation.

If intent persistence fails, the provider must not be invoked.

Once intent is durable, any uncertain provider outcome leaves the request in
that intent state until it is explicitly reconciled. Atlas must not
automatically replay the corresponding external mutation.

Provider refresh remains retry-safe because it is observational rather than
mutating.

## Ownership

- The Atlas media-request repository is authoritative for Atlas orchestration
  state.
- The external provider is authoritative for provider-side outcome.
- The media-request service owns transition ordering and fail-closed behavior.
- Providers own provider-specific transport and status translation.
- Events remain best-effort observations and are not part of the mutation
  transaction boundary.

## Recovery Visibility

Intent states must be observable as requiring reconciliation.

Observation must not itself perform a provider mutation. Automatic provider
repair is deferred until a reliable correlation mechanism exists for the
relevant provider.

Unknown provider outcome is not evidence that an operation failed.

## Consequences

### Positive

- Atlas cannot silently treat an interrupted external mutation as safe to
  repeat.
- Recovery state survives process interruption using existing atomic request
  persistence.
- The design remains within the existing Media Requests domain.
- Read-only recovery visibility can be added without a transaction engine.
- Provider-independent service boundaries remain intact.

### Tradeoffs

- Some interrupted requests require explicit reconciliation.
- Atlas does not claim exactly-once external delivery.
- Interrupted submission may lack the provider request ID needed for automatic
  provider lookup.
- Older code that does not recognize the new states will reject those records
  until upgraded.

## Alternatives Considered

### Retry provider mutations after interruption

Rejected. A timeout or process interruption does not prove that the provider
mutation failed, so replay can duplicate or repeat an external action.

### Roll back to the previous local state on provider error

Rejected. Rolling back erases the evidence that an external outcome is
ambiguous and makes an unsafe retry appear valid.

### Add a separate transaction journal

Rejected for this milestone. The existing request state machine and atomic
repository can represent durable mutation intent with substantially less
complexity.

### Automatically reconcile by provider search

Deferred. The current provider contract does not expose a stable Atlas request
correlation lookup for an interrupted submission that never persisted its
provider request ID.

## Non-Goals

This decision does not authorize:

- distributed transactions;
- exactly-once claims;
- automatic resubmission or cancellation replay;
- destructive provider reconciliation;
- a background recovery daemon; or
- replacement of the media-request persistence model.

## Related Architecture

- [Interrupted-Request Recovery](../architecture/INTERRUPTED_REQUEST_RECOVERY.md)
- [Runtime State Architecture](0004-runtime-state-architecture.md)
