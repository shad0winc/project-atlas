# ADR-0020: Storage Exhaustion Failure Boundaries

## Status

Accepted

## Context

Project Atlas persists configuration, scheduler state, Media Request state,
Operations reports, cleanup history, Sports recording state, health reports,
and backups beneath Atlas-managed storage.

The production storage filesystem is currently healthy and has substantial
free capacity. v1.0 nevertheless requires Atlas to define what happens when a
future write encounters storage exhaustion.

Existing subsystems already provide useful foundations:

- Core JSON state uses same-directory atomic temporary writes;
- Operations wraps failed report persistence in repository errors;
- Media Requests persists external-mutation intent before provider actions;
- Sports reports storage capacity and warns when free space is low; and
- the root verifier checks that required storage paths are writable.

Those controls do not by themselves define a complete storage-exhaustion
contract. In particular, an external process must not become untracked because
its identity could not be persisted, and a partial backup must not look like a
successful backup.

## Decision

Atlas treats storage exhaustion as a fail-closed persistence failure.

The permanent invariant is:

> Storage exhaustion must not corrupt the last durable state, create an
> untracked external operation, or present a partial artifact as successful.

Atlas separates three conditions:

1. **Low capacity** — storage remains writable but free capacity has crossed a
   configured warning threshold. This is observable degraded state.
2. **Exhausted storage** — a persistence operation receives `ENOSPC`, or a
   trusted capacity observation establishes no usable free capacity. The
   requested mutation has failed.
3. **Unknown storage state** — capacity or writability cannot be established.
   Unknown evidence must not be interpreted as healthy or exhausted.

## Persistence Rules

Durable Atlas state must preserve its last committed representation when a new
write fails.

Atomic writers must:

- build replacement content in the destination directory;
- replace the committed target only after the temporary write succeeds;
- propagate or normalize the persistence failure for the owning subsystem;
- remove temporary artifacts when safe; and
- never replace valid state with known-partial content.

Repository and service boundaries should translate raw filesystem failure into
their existing domain error contracts rather than leaking an implementation
detail when that translation already belongs to the boundary.

## External-Operation Rule

Atlas must not perform an external mutation when required durable intent cannot
first be recorded.

If a subsystem necessarily starts an external operation before its final
runtime identity can be persisted, failed identity persistence must trigger a
bounded compensating action using the exact identity returned by that launch.
Ambiguous ownership still fails closed; storage pressure never authorizes a
PID-only or otherwise uncertain termination.

## Artifact Rule

Artifacts that are meaningful only when complete, including backups, must not
be written directly to their final success name.

A failed artifact write must remain distinguishable from a valid artifact and
must not participate in success reporting or normal retention selection.

## Cleanup Rule

Storage pressure is not deletion authorization.

Atlas must not automatically delete Media, favorites, request state, audit
history, backups, or other user data merely because capacity is low or
exhausted. Existing retention and cleanup authorization boundaries remain in
force.

## Verification Rule

Production storage must not be filled to validate this decision.

Failure-path verification should inject `OSError` with `errno.ENOSPC` at
controlled persistence boundaries backed by temporary test data. Tests must
prove state preservation, explicit failure, compensation where required, and
partial-artifact handling.

Production validation remains read-only and confirms the deployed filesystem,
capacity, permissions, health reporting, and absence of repository mutation.

## Consequences

### Benefits

- Valid state survives failed replacement writes.
- External mutations cannot silently outrun required durable intent.
- Recorder failure handling remains compatible with durable process identity.
- Partial backups cannot masquerade as successful recovery artifacts.
- Low-space observation remains distinct from destructive remediation.
- Strong failure-path tests do not endanger the production filesystem.

### Costs

- Persistence boundaries require explicit failure tests.
- External-operation compensation adds narrow recovery logic where ordering
  cannot be made persistence-first.
- Capacity warnings do not themselves recover space.
- Operators must resolve real storage exhaustion intentionally.

## Compatibility

This decision extends the existing atomic-state, Media Request recovery,
Sports recorder identity, cleanup authorization, health, and backup contracts.
It does not introduce a second state store, storage quota system, automatic
deletion engine, new filesystem, or storage migration.

Related records:

- [ADR-0016: Interrupted-Request Recovery Boundaries](0016-interrupted-request-recovery-boundaries.md)
- [ADR-0017: Sports Recorder Process Identity](0017-sports-recorder-process-identity.md)
- [ADR-0018: Cleanup Mutation Authorization](0018-cleanup-mutation-authorization.md)
- [Storage Exhaustion Recovery Architecture](../architecture/STORAGE_EXHAUSTION.md)
