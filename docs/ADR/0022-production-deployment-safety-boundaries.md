# ADR-0022: Production Deployment Safety Boundaries

## Status

Accepted

## Context

Project Atlas has completed the v1.0 Reliability milestone and has strong
health, verification, backup-artifact, provider-failure, recovery, and ingress
observation foundations. Production change control is not yet equivalently
defined.

Discovery at commit `7f82bc8d` established:

- `main` and `origin/main` both resolve to `791436c7`, while active v1.0 work
  continues on `feature/public-ingress`;
- the existing governance documents recommend focused feature branches and
  `release/<version>` branches but do not define the exact production promotion
  boundary;
- a local annotated `v1.0.0` tag already exists and resolves to commit
  `a67bb8a5`, dated 2026-07-09, long before current v1.0 certification work;
- the current `atlas update` runs Doctor, pulls/recreates the root Compose
  services, prunes unused images, then runs Doctor and Verify;
- that update path does not create a mandatory pre-update backup, capture a
  rollback manifest, acquire a deployment lock, or enter maintenance mode;
- pruning unused images immediately after update can destroy useful rollback
  evidence;
- Caddy is the public boundary for both the Portal and `/api/*` traffic;
- Caddy configuration is mounted read-only from the repository; and
- Service Lifecycle maintenance models describe read-only maintenance history,
  not production maintenance mode.

The deployment-safety design must preserve the existing operational tools
without pretending unfinished Service Lifecycle mutation orchestration is
complete.

## Decision

Atlas adopts the following permanent production-deployment invariant:

> Production changes must originate from an explicitly approved and tested
> release state, preserve a verified recovery boundary before mutation, remain
> observable during maintenance, and return user traffic only after post-change
> verification succeeds.

Deployment Safety is implemented as a small orchestration layer around existing
Atlas backup, Doctor, Verify, ingress, Git, and Docker Compose boundaries. It
does not create a second Service Lifecycle engine.

## Production Branch Boundary

`main` is the production-stable source branch.

Focused `feature/*`, `fix/*`, `docs/*`, and similar branches are development
surfaces. They are not production deployment sources merely because they pass a
local test run.

Atlas does not add a permanent `develop` branch for v1.0. Background work uses
focused branches. This keeps the branch model small while separating unfinished
work from the stable deployment source.

`release/<version>` is the temporary certification surface for a planned
release. Release branches may receive only release-scoped fixes, documentation,
versioning, certification, and other explicitly approved stabilization work.

The normal promotion direction is:

```text
feature/fix branch -> release/<version> -> main -> certified release tag
```

Production source promotion and production runtime deployment are separate
actions. A merge does not itself authorize a runtime change.

## Tested-Commit Gate

Production automation must reject an arbitrary development commit.

The v1.0 gate requires repository state to be clean and the deployment source
to satisfy the approved production/release policy. Automated tests and release
validation must succeed before promotion. Repository-hosting branch protection
and CI should enforce the same rule where available.

No local `--force`, environment switch, or undocumented bypass may silently
convert an untested feature commit into an approved production deployment.
Emergency handling must remain explicit, narrow, tested to the extent possible,
and recorded.

## Existing `v1.0.0` Tag

The annotated `v1.0.0` tag discovered at commit `a67bb8a5` predates the current
v1.0 release-readiness program and is not accepted as certification evidence.

It is a release blocker, not a source of truth for current readiness.

M-023.24 does not move or delete that tag. Before actual v1.0 publication, the
project owner must explicitly reconcile it and record the chosen correction.
Tag reconciliation is a deliberate release action because changing a published
tag can affect external clones and automation.

No final v1.0 certification may claim that the current `v1.0.0` reference is
the certified release until that mismatch is resolved.

## Maintenance-Mode Boundary

Caddy owns production maintenance mode because it is upstream of both Portal
and API traffic.

Maintenance state is runtime state stored beneath Atlas-managed configuration,
not a modification to tracked Caddy source. Caddy receives the minimum
read-only mount needed to observe that state.

When maintenance is enabled:

- normal public Portal and API traffic receives an explicit HTTP 503 response;
- a `Retry-After` response is provided where practical;
- backend services remain running unless the maintenance operation explicitly
  requires otherwise;
- maintenance state is observable through the Atlas CLI; and
- Caddy itself remains independently health-checkable.

The current Caddy container healthcheck traverses the public API health route.
Implementation must therefore add a dedicated ingress-liveness path that
bypasses the maintenance response. Planned maintenance must not make a healthy
proxy appear unhealthy merely because user traffic is intentionally gated.

## Deployment Transaction

A production update is an ordered transaction:

1. acquire the deployment lock;
2. validate operator, repository, branch/release, and runtime preconditions;
3. capture the pre-change Git/Compose/container-image state;
4. enable maintenance mode;
5. create and validate the required pre-update Atlas backup;
6. validate any schema or configuration migration plan;
7. apply the approved update;
8. run post-update Doctor, Verify, and affected ingress/runtime checks;
9. record the outcome and rollback evidence; and
10. disable maintenance mode only after required verification succeeds.

Failure after maintenance begins leaves maintenance enabled until the operator
has a known safe runtime or deliberately approves recovery behavior.

The transaction must not prune old images before the rollback decision is
closed.

Captured image IDs are evidence, but an ID without a durable Docker reference
is not sufficient retention. Before any pull or build can move a mutable image
tag, the transaction must attach a transaction-scoped rollback tag to every
captured image and verify that the tag resolves to the exact captured ID. This
is especially important for locally built images such as the Atlas Portal and
API, whose ordinary `:local` tags are replaced by a successful rebuild.

## Backup Boundary

`atlas backup` is the required pre-update repository/configuration artifact
boundary for changes it covers. Its archive must validate before deployment
continues.

M-023.24 does not claim that the later v1.0 Backup and Recovery certification
work is already complete. A deployment that changes persistent state outside
the currently verified backup scope must provide the additional state-specific
backup/recovery evidence required by that migration.

If required recovery evidence does not exist, the migration is blocked rather
than treated as safely reversible.

## Migration Boundary

Schema and configuration migrations must declare before execution:

- source and target version/state;
- compatibility requirements;
- whether the migration is reversible;
- backup requirements;
- validation steps;
- rollback or forward-recovery behavior; and
- irreversible consequences.

Unknown migration behavior fails closed. Production is not the experiment for
an unvalidated migration.

## Rollback Boundary

Pre-update capture must preserve enough information to identify the prior Git
commit, Compose inputs, container image identities, and backup artifact used by
the deployment.

Rollback must operate from captured evidence rather than from `latest` tags or
assumptions about what an image name previously resolved to.

Rollback is not declared successful until the same required post-change health
and verification gates pass. If rollback cannot safely restore a changed state,
the system remains in maintenance mode and recovery becomes an explicit
operator procedure.

Verification has two distinct traffic states. While maintenance is enabled,
ingress verification must prove that Caddy and both application backends are
healthy while public Portal and API requests are intentionally isolated with
HTTP 503. After maintenance is disabled, Atlas must verify the normal public
Portal and API paths again before publishing the candidate as the current
verified baseline or releasing the deployment lock. A failure after reopening
re-enables maintenance and leaves the previous verified baseline authoritative.

## v1.0 RC Deployment Evidence and Clarification

The first exact `1.0.0-rc.1` production deployment attempt on 2026-08-24
added three clarifications to this accepted decision.

> Production build paths must validate effective readability and traversal of
> tracked first-party build inputs before pull or build mutation begins.

> Rollback must restore from transaction-scoped aliases created and
> identity-verified before mutation; it must not recreate prior availability by
> retagging a captured digest-shaped image reference.

> Recovery source used by recreated services must live beneath the persistent
> Atlas deployment-record transaction namespace and remain present after the
> restore command returns.

These clarifications harden the existing fail-closed transaction and recovery
model rather than creating a new lifecycle abstraction.

The failed transaction `update-20260824T165151Z-3258027` remains immutable
audit evidence. Production recovery restored verified baseline
`baseline-reconciliation-20260824T164541Z-927002`. The exact RC production
deployment gate remains open until a controlled retry succeeds.

## Post-Restore Rollback Readiness Invariant

Recovery of failed exact-RC transaction `update-20260824T222351Z-3794932` established a separate
rollback-side invariant from the previously documented
`POST_APPLY_READINESS_RACE`.

The restored runtime could legitimately remain `running + starting` briefly
after restore. Immediate authoritative verification therefore exposed the
distinct:

`POST_RESTORE_ROLLBACK_READINESS_RACE`

A restore command returning successfully is not equivalent to rollback
readiness.

For rollback scopes that restore ingress, Atlas requires bounded,
inspection-only readiness before authoritative rollback verification and before
state finalization.

`running + healthy` is success. `running + starting` is the only retryable
state. Missing containers, inspection failure, non-running state, `unhealthy`,
missing health metadata, unexpected health state, and timeout fail closed.

This readiness boundary is not a second health authority and does not weaken
strict ingress verification.

Failure preserves the failed transaction, maintenance mode, deployment-lock
ownership, and previous verified baseline `baseline-reconciliation-20260824T164541Z-927002` until explicit recovery
completes.

This decision does not authorize manual finalization, lock deletion, automatic
recovery, rollback replay, or another production deployment attempt.

## Second Exact-RC Attempt: Post-Apply Readiness Invariant

The second controlled exact `1.0.0-rc.1` production attempt,
`update-20260824T222351Z-3794932`, established an additional deployment-safety invariant.

A successful Compose apply is not equivalent to verified readiness.

Ingress services recreated by an approved update may legitimately report
`running + starting` for a bounded interval after Compose returns. Atlas may
observe and retry that transitional state before authoritative verification.

The readiness observation is bounded and read-only:

- `running + healthy` is terminal success;
- `running + starting` is the only retryable state;
- missing containers, inspection failure, non-running state, `unhealthy`,
  missing health metadata, unexpected health state, and timeout fail closed.

The readiness phase does not replace authoritative verification. Strict ingress
verification continues to require `running + healthy`.

A readiness failure after maintenance begins enters the existing failed
transaction path. Maintenance remains enabled, deployment-lock ownership
remains held, and the previous verified baseline remains authoritative until
explicit recovery or a separately authorized safe continuation.

The failed transaction `update-20260824T222351Z-3794932` remains immutable audit evidence.
The authoritative production baseline remains
`baseline-reconciliation-20260824T164541Z-927002`.

This clarification extends the existing deployment transaction and verification
boundary; it does not create a new lifecycle abstraction and does not authorize
another production retry.

## Consequences

Positive consequences:

- production and background development have explicit boundaries;
- users receive a controlled maintenance response during change windows;
- backups and rollback evidence exist before risky mutation;
- failed verification cannot silently reopen the Portal;
- old images remain available until rollback is no longer required; and
- the existing Atlas health and backup tools are reused.

Tradeoffs:

- production updates take longer because backup and validation are mandatory;
- maintenance mode requires a small runtime state mount at Caddy;
- release promotion requires explicit Git/CI discipline; and
- some migrations may remain blocked until Backup and Recovery certification
  provides adequate recovery coverage.

## Non-Goals

This decision does not:

- complete the unfinished generic Service Lifecycle mutation engine;
- introduce Kubernetes, a deployment daemon, or a second scheduler;
- add a permanent `develop` branch;
- declare all persistent state backups certified;
- automatically rewrite or delete the premature `v1.0.0` tag; or
- make every production failure automatically reversible.

## E2.5 Production Evidence

The first controlled E2.5 Jellyseerr-to-Seerr migration attempt confirmed the
ADR's fail-closed transaction model and exposed an additional recovery
requirement.

The migration failed without reopening user traffic or releasing transaction
ownership. Atlas retained maintenance mode, the deployment lock, the previous
verified baseline, and the failed transaction until explicit recovery completed.

Recovery restored the legacy Jellyseerr runtime. During that recovery, the
Sports controller could not become healthy because its effective non-root
runtime identity lacked write ownership for required persistent heartbeat and
recording paths.

The resulting architectural clarification is:

> A deployment or recovery transaction that recreates a non-root service must
> establish and verify the declared writable-runtime ownership required by that
> service before the service can satisfy post-change health gates.

This is part of the existing deployment prerequisite and verification boundary,
not a new lifecycle abstraction.

Recovery operations must also remain bounded to the intended target and its
declared dependencies. Healthy unrelated services must not be recreated merely
because they share a broader Compose or operational environment.

Finally, recovery establishes a new safe state without changing the historical
meaning of the failed transaction. Failed deployment records remain audit
evidence even when rollback or forward recovery subsequently succeeds.

These clarifications preserve the existing decision that maintenance mode and
deployment-lock ownership remain in force until deterministic post-recovery
verification succeeds.
