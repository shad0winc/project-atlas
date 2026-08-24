# Project Atlas Upgrade Guide

**Document Status:** D.3D v1.0 Documentation Candidate
**Applies To:** Project Atlas v1.0 production upgrades
**Audience:** Project Atlas administrators and maintainers
**Canonical Repository Path:** `docs/guides/UPGRADE_GUIDE.md`

---

## 1. Purpose

This guide defines the supported Project Atlas v1.0 production upgrade
procedure.

An Atlas upgrade is not just a source update or container restart. Production
upgrade is a controlled transaction that separates:

1. source promotion;
2. deployment authorization;
3. pre-change capture and backup;
4. maintenance isolation;
5. migration validation;
6. bounded runtime mutation;
7. post-change verification;
8. public reopen;
9. verified-baseline publication;
10. rollback or forward recovery when required.

A successful `git pull`, image pull, build, or Compose recreation is not proof
that a production upgrade succeeded.

---

## 2. Upgrade Safety Principles

Every production upgrade must follow these principles:

- production source must be explicitly approved;
- the repository must be clean and synchronized to the authorized source;
- production mutation requires exclusive transaction ownership;
- maintenance isolation begins before user-visible mutation;
- rollback evidence is captured before mutable runtime identities can change;
- a validated Atlas backup exists before covered mutation;
- migrations are declared and validated before execution;
- only the approved deployment scope is mutated;
- verification determines success, not command exit alone;
- public traffic resumes only after all required checks pass;
- failed transactions remain failed historical evidence;
- rollback or forward recovery never rewrites a prior failure as success.

Unknown migration or recovery behavior fails closed.

---

## 3. Source Promotion Is Not Deployment

Atlas separates source promotion from runtime deployment.

The release direction is:

```text
feature/fix branch
        |
        v
release/<version>
        |
        v
      main
        |
        v
certified release tag
```

Passing tests on a feature branch does not make that branch an approved
production source.

Merging approved source to `main` does not itself deploy production.

Production deployment begins only through the certified deployment transaction.

Atlas does not require a permanent `develop` branch.

---

## 4. Authorized Production Source

Before an upgrade, identify the exact authorized source commit.

For normal production deployment, the checkout must satisfy the source gate
defined by the current Release Promotion and Deployment Safety documentation.

At minimum, confirm:

```bash
git branch --show-current
git status --short
git rev-parse HEAD
git rev-parse origin/main
```

Do not proceed from:

- a dirty checkout;
- an unreviewed feature branch;
- an unexpected detached HEAD;
- a local `main` that differs from `origin/main`;
- a commit whose release/promotion status is unknown.

The deployment transaction must build and deploy from the approved source
commit.

---

## 5. Reconciled Historical v1.0 Tag

A premature historical `v1.0.0` tag previously existed and predated the final
v1.0 release-certification process. Release forensics confirmed that the tag
was not valid release evidence because it claimed v1.0.0 while its tagged
commit contained repository `VERSION` `0.9.0`.

The project owner explicitly reconciled and removed that invalid tag from the
local and remote tag namespaces while preserving the underlying commit in Git
history.

Do not infer final-release status merely because the `v1.0.0` namespace is now
available. Upgrade authorization continues to depend on the approved release
source, exact certified commit, required validation, and the normal protected
promotion and deployment gates. The genuine final `v1.0.0` tag must be created
only by the certified final-release transaction.

---

## 6. Plan the Maintenance Window

Schedule the production upgrade as a planned maintenance window.

The window must include time for:

- preflight;
- backup;
- migration validation;
- image/build work;
- service recreation;
- health and ingress checks;
- rollback or forward recovery if needed.

Do not size the window so narrowly that required validation would need to be
skipped.

Inform affected users before planned downtime when practical.

---

## 7. Pre-Upgrade Read-Only Health Check

Before acquiring the mutation boundary, inspect the current platform.

Representative checks include:

```bash
atlas doctor
atlas verify
atlas health
atlas operations latest
atlas scheduler history --limit 10
atlas git
```

Also inspect applicable Docker/container and provider health.

If the current platform is already degraded, understand and document the
condition before beginning an upgrade.

Do not use an upgrade as an unexplained attempt to fix an unrelated production
failure.

---

## 8. Deployment Transaction Ownership

Only one production deployment or live-restore transaction may own the shared
mutation boundary at a time.

The deployment transaction uses the Atlas runtime lock.

Do not:

- start a second deployment while the lock is held;
- run live restore concurrently with deployment;
- manually delete the shared lock to bypass ownership;
- assume a stale-looking lock is safe to remove without the documented
  ownership checks.

Lock acquisition must fail closed when ownership cannot be safely established.

---

## 9. Pre-Change Capture

Before mutable runtime state changes, Atlas captures the previous production
identity.

The deployment record must preserve enough evidence to identify at least:

- deployment identifier and timestamps;
- source branch/ref;
- full Git commit;
- clean/dirty repository result;
- relevant Compose project/config identity;
- pre-update container image IDs/digests;
- backup artifact identity;
- migration declaration when applicable.

This evidence is required for rollback and auditability.

---

## 10. Preserve Durable Rollback Image References

Mutable image tags are not rollback identities.

Before a pull or build can move a mutable tag, the deployment transaction must
retain durable transaction-scoped rollback references for captured image
identities.

This is especially important for locally built Atlas images whose normal local
tag may be replaced by a successful rebuild.

Do not use `latest` or another mutable tag to infer what production used before
the upgrade.

Do not run `docker image prune` while rollback remains possible.

---

## 11. Enable Maintenance Isolation

Before user-visible production mutation, enable the Atlas maintenance boundary.

The supported maintenance commands are:

```bash
atlas maintenance status
atlas maintenance enable
atlas maintenance disable
```

Caddy owns the public maintenance response because it is upstream of both the
Portal and API.

While maintenance is enabled:

- normal public Portal/API requests receive HTTP 503 Service Unavailable;
- Caddy remains independently observable;
- application backends may remain running unless the transaction requires
  otherwise.

Do not manually disable maintenance merely because a shell command failed.

Maintenance release is a terminal transaction action after verification.

---

## 12. Create the Required Pre-Upgrade Backup

The deployment transaction requires a validated Atlas backup before continuing
through covered production mutation.

The canonical entry point is:

```bash
atlas backup --notes "pre-upgrade"
```

The deployment record should link to the exact resulting canonical backup.

Do not treat a partial archive or an archive that merely opens as sufficient
recovery evidence.

If the upgrade changes persistent state outside the certified Atlas backup
scope, the upgrade must provide additional state-specific recovery evidence.

If required recovery evidence does not exist, block the upgrade.

---

## 13. Migration Declaration

Any schema or configuration migration must be declared before execution.

The declaration must define:

- source version/state;
- target version/state;
- compatibility requirements;
- whether the migration is reversible;
- backup requirements;
- validation steps;
- rollback or forward-recovery behavior;
- irreversible consequences.

Unknown migration behavior fails closed.

Production is not the environment for discovering an unvalidated migration
strategy.

---

## 14. Select the Approved Upgrade Scope

Atlas upgrades should mutate only the approved surface.

Current CLI help exposes the controlled update entry point:

```bash
atlas update <core|ingress|all> --migration none
```

Use the scope approved for the change.

Do not rebuild or recreate unrelated healthy services merely because a global
Compose command would be easier.

Root-service Compose changes and ingress changes are distinct deployable
surfaces.

---

## 15. Apply the Upgrade

Apply the approved deployment using the certified Atlas deployment/update
boundary.

The deployment must use the authorized clean source commit.

During apply:

- preserve transaction ownership;
- preserve maintenance isolation;
- preserve rollback image references;
- mutate only approved services/configuration;
- execute only declared migrations;
- retain immutable audit evidence;
- do not prune rollback assets.

A command returning zero does not finalize the upgrade.

---

## 16. Service Ownership and Writable Runtime State

A source-correct service may still fail after recreation if persistent runtime
ownership is wrong.

For any recreated non-root service, verify that its declared writable runtime
paths have the required ownership and permissions before expecting health to
pass.

Do not solve ownership failures by making the container privileged or making
runtime directories world-writable.

Recovery and upgrade scope must include required dependent runtime contracts.

---

## 17. Post-Upgrade Verification

Required post-change validation is selected by the affected surface.

At minimum, use the existing Atlas health/verification system:

```bash
atlas doctor
atlas verify
```

For public ingress changes, use the repository-owned ingress verification
contract.

Also perform applicable:

- Docker Compose/container health checks;
- service-specific health checks;
- provider checks;
- module verification;
- migration-specific assertions;
- authentication/security checks;
- Scheduler checks.

All required checks must pass before normal public traffic resumes.

---

## 18. Verify Maintenance-State Ingress

While maintenance remains enabled, ingress verification must prove two things at
the same time:

1. Caddy and required application backends are healthy;
2. public Portal/API traffic is intentionally isolated with HTTP 503.

This distinguishes intentional maintenance from a dead proxy or failed
application.

Do not reopen traffic merely because the backends are running.

---

## 19. Reopen Public Traffic

After all maintenance-state verification passes, disable maintenance through the
supported transaction path.

Then verify the normal public Portal and API paths again.

A failure after reopening is still a deployment failure.

If normal ingress verification fails after reopening:

- re-enable or retain maintenance;
- leave the prior verified baseline authoritative;
- continue through rollback or forward recovery.

Do not publish the new deployment baseline yet.

---

## 20. Publish the Verified Baseline

Only after all required post-upgrade and reopened-ingress checks pass may the
deployment publish a new verified production baseline.

The verified baseline records the known-good deployment identity used by later
rollback, restore, and deployment preconditions.

Do not publish a baseline for a deployment that merely completed its shell
commands.

---

## 21. Release the Deployment Lock

Release the shared mutation lock only after the transaction reaches its defined
successful terminal state.

Lock release and maintenance disablement are terminal actions, not generic shell
cleanup.

A failing shell `trap` or process exit must not erase transaction ownership
evidence or reopen production automatically.

---

## 22. Failure During Apply or Verification

If apply or required verification fails:

- the deployment remains failed;
- failed transaction history remains immutable;
- maintenance remains active when required for safety;
- deployment ownership remains controlled;
- the previous verified baseline remains authoritative;
- rollback or forward recovery becomes an explicit operator decision.

Do not relabel the failed transaction as successful after later recovery.

---

## 23. Rollback Decision

Rollback must operate from captured deployment evidence.

The rollback decision uses:

- prior Git commit;
- prior Compose/config inputs;
- captured exact image identities;
- durable rollback image references;
- associated backup artifact;
- migration recovery declaration.

Do not construct rollback from mutable `latest` tags or memory.

The dedicated Rollback Guide owns the complete rollback procedure.

---

## 24. Forward Recovery

Some failures are safer to recover forward rather than restoring the prior
runtime.

Forward recovery may be appropriate when:

- the failed deployment exposed a bounded runtime ownership/configuration defect;
- the defect can be corrected without widening scope;
- the recovery plan is validated;
- the original failed transaction remains preserved.

Forward recovery establishes a new safe state; it does not convert the failed
deployment record into success.

---

## 25. Rollback/Recovery Verification

Rollback or forward recovery is not complete because containers recreated.

The recovered runtime must pass the required applicable:

- heartbeat checks;
- module verification;
- `atlas doctor`;
- `atlas verify`;
- provider checks;
- affected runtime checks;
- ingress checks.

Maintenance and lock release occur only after the recovered production surface
passes the required gates.

---

## 26. Upgrade and Restore Are Different Transactions

Deployment rollback and Atlas state restore are related but distinct.

Do not use a live Atlas restore as an improvised substitute for deployment
rollback unless the recovery plan explicitly requires state restoration.

Live restore has its own staging, validation, lock, maintenance, and
`--confirm-live` authorization contract.

Use the Backup/Restore Guide for state restoration.

---

## 27. Scheduler Considerations

An upgrade can affect the production Scheduler dispatcher or registered tasks.

If Scheduler units, CLI behavior, task registration, or runtime ownership are
part of the upgrade:

- verify the tracked systemd unit content;
- verify `atlas scheduler sync` behavior where applicable;
- verify timer/service state required by the current controlled deployment;
- inspect Scheduler history after the change;
- treat failed `atlas-scheduler.service` invocations as Scheduler execution
  failures.

Do not add a second scheduler as a recovery shortcut.

---

## 28. Security-Sensitive Upgrades

When an upgrade affects authentication, authorization, ingress, Docker control,
secrets, or dependency images, include the relevant security validation.

Examples include:

- valid JWT configuration at service startup;
- permission-deny behavior;
- public API documentation protection;
- browser security headers;
- secret file permissions;
- Docker socket/control-plane boundaries;
- non-root first-party services;
- current vulnerability evidence when required by release certification.

Do not disable a security control merely to make an upgrade pass.

---

## 29. Provider-Sensitive Upgrades

When an upgrade affects Media, request, Sports, or other providers, validate
provider failure semantics as well as the normal healthy path.

Atlas must continue to distinguish:

```text
authoritative empty
```

from:

```text
provider unavailable
```

Provider outage must not become deletion authorization, automatic mutation
replay, or loss of retained Sports/request state.

---

## 30. Storage-Sensitive Upgrades

For upgrades that affect persistent state or write paths:

- confirm available space;
- confirm ownership and writable paths;
- validate backup scope;
- verify the affected persistence boundary;
- preserve last-durable-state semantics.

Do not proceed through an unknown `ENOSPC` or state-persistence failure merely
because containers can still start.

---

## 31. Upgrade Completion Checklist

Do not close the maintenance window until the applicable checks pass.

- [ ] Authorized production source identified.
- [ ] Repository is clean and synchronized.
- [ ] Existing platform health understood.
- [ ] Shared deployment lock acquired safely.
- [ ] Pre-change deployment evidence captured.
- [ ] Durable rollback image references retained.
- [ ] Maintenance isolation enabled.
- [ ] Validated pre-upgrade backup created.
- [ ] Migration declaration validated or explicitly `none`.
- [ ] Approved deployment scope selected.
- [ ] Upgrade applied from the approved source.
- [ ] Recreated non-root runtime ownership validated.
- [ ] `atlas doctor` passes.
- [ ] `atlas verify` passes.
- [ ] Surface-specific verification passes.
- [ ] Maintenance-mode ingress behavior passes.
- [ ] Normal public ingress passes after reopen.
- [ ] New verified baseline published only after success.
- [ ] Deployment lock released only at terminal success.
- [ ] Rollback/recovery evidence retained.
- [ ] Failed historical transactions remain immutable.
- [ ] Upgrade outcome documented.

---

## 32. What Must Not Be Done

Do not:

- deploy production directly from an arbitrary feature branch;
- treat a source merge as a runtime deployment;
- skip the pre-upgrade backup;
- proceed with an undeclared migration;
- delete the shared lock manually;
- disable maintenance before verification;
- use `latest` as rollback identity;
- prune rollback images before rollback is no longer required;
- recreate unrelated healthy services without approved scope;
- make persistent runtime directories world-writable as a generic fix;
- hide a failed transaction after recovery;
- claim success because containers are running.

---

## 33. Relationship to the Administrator Guide

The Administrator Guide provides the high-level operational rules.

This Upgrade Guide owns the detailed production upgrade procedure.

The Administrator Guide should not duplicate every step here, and this guide
does not replace the deeper architecture/ADR rationale.

---

## 34. Relationship to the Rollback Guide

The Upgrade Guide defines when rollback becomes necessary and the evidence that
must exist before upgrade mutation.

The Rollback Guide owns the detailed rollback transaction, verification, and
failure handling.

Do not duplicate rollback mechanics in both guides.

---

## 35. Relationship to Backup/Restore

Every covered production upgrade requires a validated pre-change Atlas backup.

That backup is recovery evidence, not automatic proof that every possible
upgrade is reversible.

If an upgrade changes persistent state outside the certified Atlas recovery
scope, additional recovery evidence is required.

Use the Backup/Restore Guide for state recovery procedures.

---

## 36. Legacy Upgrade Guidance

Older Atlas operations documentation summarizes update preparation as:

```text
atlas doctor
atlas verify
atlas backup
```

followed by update and post-update verification.

Those commands remain useful pieces of the process, but that summary is not the
complete certified v1.0 production upgrade transaction.

The current v1.0 contract additionally requires:

- source/promotion gating;
- exclusive transaction ownership;
- captured pre-change runtime identity;
- durable rollback image references;
- maintenance isolation;
- migration declaration;
- bounded apply scope;
- two-state ingress verification;
- verified-baseline publication;
- explicit rollback/forward-recovery handling.

Do not use the legacy shorthand as the sole production upgrade procedure.

---

## 37. Authoritative References

Primary references:

- `ADMINISTRATOR_GUIDE.md`
- `../OPERATIONS.md`
- `../operations/RELEASE_PROMOTION.md`
- `../architecture/DEPLOYMENT_SAFETY.md`
- `../architecture/BACKUP_RECOVERY.md`
- `../architecture/SECURITY.md`
- `../architecture/STARTUP_POLICY.md`
- `../architecture/SERVICE_LIFECYCLE.md`
- `../architecture/SCHEDULER_RECOVERY.md`
- `../architecture/STORAGE_EXHAUSTION.md`
- `../architecture/UNAVAILABLE_PROVIDER_BEHAVIOR.md`
- `../ADR/0022-production-deployment-safety-boundaries.md`
- `../ADR/0023-backup-restore-recovery-boundaries.md`
- `../ADR/0024-security-trust-boundaries.md`
- `../04-backup-restore.md`
- `../releases/RELEASE_CHECKLIST.md`
- `../governance/RELEASE_POLICY.md`
- `../../ROADMAP.md`

When older operator shorthand conflicts with certified Deployment Safety,
Backup/Recovery, Security, or release policy, use the newer certified contract.
