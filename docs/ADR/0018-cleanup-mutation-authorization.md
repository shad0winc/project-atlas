# ADR-0018: Cleanup Mutation Authorization

## Status

Accepted

## Context

Atlas already has favorite-aware policy, retention eligibility, cleanup
planning, dry-run execution, provider preview, audit history, and a
fail-closed Maintainerr assessment boundary.

Those capabilities deliberately stop short of destructive Atlas cleanup.
`CleanupExecutionService` and `DefaultCleanupExecutor` accept dry-run mode only,
and the default executor dispatches delete operations as previews.

Maintainerr is deployed separately and has direct access to the media mount.
The repository contains a `MaintainerrIntegration` authorization adapter, but
discovery found no non-test construction site proving that the deployed service
uses it. Production database inspection found zero configured collections,
rules, rule groups, or collection-media entries, so no destructive automatic
Maintainerr rule is currently enabled.

Project Atlas must not confuse cleanup eligibility with permission to mutate
media. Protection state can change between planning and execution, and external
automation cannot be trusted merely because an Atlas adapter exists elsewhere
in the repository.

## Decision

A cleanup recommendation is not deletion authorization.

Atlas will keep its v1.0 cleanup execution boundary non-destructive while
M-023.20 verifies the existing safeguards. Destructive automatic cleanup must
not be enabled in Maintainerr as a substitute for that missing execution
boundary.

Any future destructive media mutation must obtain fresh Atlas policy and
retention authorization for the exact provider and item immediately before the
mutation. The authorization identity must match the mutation target.

Missing, stale, mismatched, invalid, or unavailable authorization denies the
mutation.

Protected and review-required media deny the mutation.

Authorization and mutation outcomes must be durably auditable, and ambiguous
provider outcomes must require reconciliation rather than blind replay.

## Consequences

Positive consequences:

- the current production cleanup path cannot accidentally become destructive;
- favorite protection remains authoritative at the Atlas policy boundary;
- external automation cannot silently bypass Atlas policy;
- future deletion support has an explicit contract to satisfy;
- stale cleanup scans cannot be promoted directly into destructive commands;
- failures default to preserving media; and
- M-023.20 can be validated without deleting production media.

Tradeoffs:

- Atlas does not yet automate destructive cleanup;
- Maintainerr destructive rules remain disabled until an Atlas-authorized
  mutation path exists; and
- a future execution milestone must add fresh authorization and durable
  destructive-operation auditing before enabling automation.

## Alternatives Considered

### Treat `DELETE` recommendations as authorization

Rejected because cleanup recommendations may become stale when protection state
changes after planning.

### Enable Maintainerr deletion and rely on configuration exclusions

Rejected because configuration exclusions do not prove the current Atlas
favorite, policy, or retention contract at mutation time.

### Add destructive Atlas execution during M-023.20

Rejected because this milestone verifies safety. Introducing deletion while
verifying deletion safeguards would unnecessarily expand risk and scope.

### Remove Maintainerr

Rejected. Maintainerr remains useful as an optional operational component. The
safety requirement is to constrain destructive authority, not replace a service
that can continue operating non-destructively.

## Compatibility

This decision preserves the current repository behavior and production state.
It adds no database migration, no provider mutation, and no new service.

Existing dry-run commands, preview results, cleanup audit history, favorite
policy, retention evaluation, and Maintainerr assessment contracts remain
compatible.

## Related Decisions

- [ADR 0007 — Atlas Retention Intelligence](0007-atlas-retention-intelligence.md)
