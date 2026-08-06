# Automatic Cleanup Safety Architecture

## Purpose

Automatic Cleanup Safety defines the authorization boundary between Atlas
retention decisions and any component capable of destructive media mutation.

The boundary exists to ensure that a cleanup recommendation can never be
treated as permission to delete media without current Atlas policy evidence.

## Current Production State

M-023.20 discovery established the following repository and production facts:

- `CleanupExecutionService` accepts dry-run execution only.
- `DefaultCleanupExecutor` accepts dry-run reports only.
- planned deletions are dispatched as provider preview operations only.
- dry-run execution contracts cannot claim that media was modified.
- favorite-aware policy feeds the retention decision boundary.
- favorited media is ineligible for cleanup through that policy path.
- `MaintainerrIntegration` denies deletion when policy evaluation fails or the
  returned cleanup identity does not match the candidate.
- no non-test repository construction site currently routes the deployed
  Maintainerr service through `MaintainerrIntegration`.
- the production Maintainerr database contains zero collections, zero rule
  groups, zero rules, and zero collection-media rows.

Therefore production does not currently have an enabled automatic destructive
cleanup rule, and Atlas itself does not currently execute destructive cleanup.

## Safety Principle

A cleanup recommendation is not deletion authorization.

Any future destructive media mutation must obtain a fresh Atlas authorization
for the exact provider and item identity at the mutation boundary. Missing,
stale, mismatched, invalid, or unavailable authorization fails closed.

## Responsibility Boundaries

### Policy

Atlas Policy owns protection reasons such as user favorites. It answers whether
an item is protected and explains why.

### Retention

Retention converts policy state into normalized removal eligibility. It does
not delete media.

### Cleanup

Cleanup converts retention eligibility into `KEEP`, `DELETE`, or `REVIEW`
recommendations. A `DELETE` recommendation describes what would be eligible; it
does not authorize a provider mutation.

### Execution

The v1.0 cleanup execution boundary remains dry-run only. It can validate and
preview an eligible deletion but cannot execute one.

### External Automation

External automation such as Maintainerr must not be configured to perform
destructive deletion outside an Atlas-authorized mutation boundary. Merely
having an Atlas adapter class in the repository does not prove that an external
service is using that authorization.

## Required Destructive-Mutation Contract

Before Atlas may support automatic destructive cleanup, all of the following
must be true for every mutation:

1. The provider identity is allow-listed and normalized.
2. The media item identity is normalized and stable.
3. Atlas re-evaluates current policy and retention state immediately before
   mutation.
4. The authorization identity exactly matches the mutation target.
5. Protected or review-required media is denied.
6. Policy, favorite, retention, provider, or authorization failure is denied.
7. The mutation is performed only through an explicitly destructive provider
   capability.
8. Authorization and execution results are durably auditable.
9. A failed or ambiguous mutation result requires operator attention rather
   than blind retry.

Cached cleanup scans or old eligibility decisions are insufficient destructive
authorization because protection state may change after a scan was produced.

## Favorite Protection

Favorite protection is evaluated by Atlas Policy and therefore participates in
the retention decision used by cleanup planning.

M-023.20 verification must prove the complete boundary rather than only testing
its individual services:

```text
favorite
  -> policy PROTECT
  -> retention ineligible
  -> cleanup KEEP
  -> execution SKIPPED
  -> provider mutation not called
```

Removing the final favorite may make a later fresh policy decision eligible,
but it does not retroactively authorize an earlier cleanup plan.

## Failure Semantics

Cleanup safety is fail closed.

Examples that must prevent destructive action include:

- favorite-state persistence cannot be read;
- policy evaluation raises an error;
- retention returns an invalid contract;
- cleanup identity differs from the requested target;
- provider capability is absent or inconsistent;
- external automation cannot prove Atlas authorization; or
- production configuration cannot be conclusively inspected.

For the current dry-run implementation, these failures must occur before any
provider modification because modification is not a supported execution mode.

## Maintainerr Boundary

Maintainerr remains a deployed optional operational service, but its presence
does not make it an Atlas mutation authority.

At the M-023.20 production checkpoint its SQLite registry contains no configured
collections or rules. This is the safe v1.0 state until an explicit integration
can prove that every destructive candidate is authorized through current Atlas
policy at execution time.

M-023.20 must not enable collections, rules, deletion actions, or other
destructive Maintainerr automation as part of verification.

## Audit Boundary

Atlas already provides cleanup execution audit and history foundations. Dry-run
preview events are observable and cannot claim media modification.

Future destructive execution must extend this boundary so that both the
authorization decision and provider mutation result are durably attributable
to one normalized execution identity.

## Non-Goals

M-023.20 does not:

- add destructive Atlas cleanup execution;
- enable Maintainerr deletion rules;
- edit the Maintainerr production database;
- create another retention or cleanup engine;
- bypass favorite or policy protections;
- introduce blind automatic retry; or
- mutate production media during validation.

## Verification Strategy

M-023.20 verification is intentionally layered:

1. prove model and service invariants with existing regressions;
2. add cross-boundary tests from favorites through cleanup execution;
3. prove policy failures stop before provider action;
4. prove Maintainerr authorization remains fail closed;
5. validate production configuration read-only; and
6. reconcile documentation and roadmap state only after all checks pass.

## Related Decisions

- [ADR 0007 — Atlas Retention Intelligence](../ADR/0007-atlas-retention-intelligence.md)
- [ADR 0018 — Cleanup Mutation Authorization](../ADR/0018-cleanup-mutation-authorization.md)
