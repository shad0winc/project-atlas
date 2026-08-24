# Project Atlas Rollback Guide

**Document Status:** D.3E v1.0 Documentation Candidate
**Applies To:** Project Atlas v1.0 production rollback and deployment recovery
**Audience:** Project Atlas administrators and maintainers
**Canonical Repository Path:** `docs/guides/ROLLBACK_GUIDE.md`

---

## 1. Purpose

This guide defines the supported Project Atlas v1.0 production rollback
procedure.

Rollback is a controlled deployment transaction. It is not:

- "go back to the old tag";
- "pull the previous image";
- "restore the latest backup";
- "recreate the containers and see if they work";
- a substitute for Atlas state restore.

A rollback succeeds only when the recovered production runtime passes the
required health, verification, provider, module, and ingress checks.

---

## 2. Rollback Safety Principles

Every rollback must preserve these rules:

1. Roll back from captured deployment evidence.
2. Preserve the failed deployment as immutable historical evidence.
3. Keep public traffic isolated while production safety is uncertain.
4. Keep shared transaction ownership until the rollback reaches a defined
   terminal state.
5. Restore exact known runtime identities, not mutable-name assumptions.
6. Respect migration reversibility and state-recovery requirements.
7. Recreate only the bounded scope needed for safe recovery.
8. Validate runtime ownership for recreated non-root services.
9. Verify health before reopening public traffic.
10. Publish a verified baseline only after the recovered runtime passes.
11. Never convert the original failed deployment record into success.
12. Escalate to state restore or forward recovery when rollback evidence is
    insufficient.

Unknown rollback state fails closed.

---

## 3. When Rollback Applies

Rollback is appropriate when a production deployment has failed or produced an
unacceptable runtime and the previously verified production state can be
re-established from captured evidence.

Typical rollback triggers include:

- failed post-deployment health checks;
- failed public-ingress verification;
- failed provider or module verification after a deployment;
- incompatible runtime behavior discovered immediately after change;
- an explicitly reversible migration whose rollback contract is satisfied;
- a deployment-scope defect where the prior runtime remains recoverable.

Rollback is not automatically the correct answer for every failed deployment.

---

## 4. When Rollback May Not Apply

Rollback may be unsafe or incomplete when:

- the migration is irreversible;
- persistent state has changed outside the protected recovery scope;
- required rollback image references were not retained;
- exact prior Compose/configuration inputs are unavailable;
- the prior Git commit cannot be established;
- the associated backup/recovery evidence is missing or invalid;
- current state cannot safely be reconciled with the prior runtime;
- provider mutation outcomes are ambiguous;
- restoring the prior application runtime would not restore authoritative state.

In these cases, keep maintenance isolation and follow the documented forward
recovery or Backup/Restore procedure.

Do not improvise a rollback when required evidence is missing.

---

## 5. Rollback Is Not Atlas State Restore

Deployment rollback and Atlas state restore are distinct transactions.

Deployment rollback restores the prior known-good application/runtime
deployment identity from captured deployment evidence.

Atlas state restore replaces declared authoritative Atlas state from a verified,
staged recovery archive using the dedicated restore transaction.

Do not use:

```bash
atlas restore apply ...
```

as a generic substitute for deployment rollback.

Use the Backup/Restore Guide when authoritative Atlas state itself must be
restored.

---

## 6. Required Rollback Evidence

Before beginning rollback, identify the failed deployment record and verify that
it contains the required recovery evidence.

The rollback decision should have access to:

- failed deployment identifier;
- failed deployment source commit;
- previous verified baseline identifier;
- previous Git commit;
- previous source/ref context;
- previous Compose inputs;
- exact prior image IDs/digests;
- durable rollback image references;
- pre-change backup artifact;
- migration declaration;
- affected service scope;
- recorded post-change failures.

Do not substitute memory or mutable tags for missing evidence.

---

## 7. Previous Verified Baseline

The previous verified baseline remains authoritative when a new deployment
fails before successful baseline publication.

Use:

```bash
atlas deployment status
atlas deployment baseline
```

to inspect the current deployment transaction and verified baseline where
applicable.

The baseline is evidence of the last known-good production deployment identity.

Do not overwrite it simply because a newer deployment reached the apply phase.

---

## 8. Maintenance Isolation

Rollback is a maintenance operation.

Before rollback mutation, verify that public maintenance isolation is active or
that the failed deployment transaction still owns it.

Useful commands include:

```bash
atlas maintenance status
atlas maintenance enable
```

Caddy owns the public maintenance boundary.

During rollback, normal public Portal/API traffic should remain isolated with
HTTP 503 while required application backends and recovery surfaces remain
observable.

Do not manually disable maintenance to test whether the old runtime "looks
better."

---

## 9. Shared Deployment Lock

Rollback operates under the same shared deployment/restore mutation boundary.

Do not start rollback while another deployment or live restore owns the lock.

Do not manually delete the lock file.

Ownership must be established through the supported transaction logic.

If lock ownership is indeterminate, fail closed and investigate before mutation.

---

## 10. Freeze Further Mutation

Once rollback is selected:

- stop unrelated deployment changes;
- do not pull or rebuild unrelated images;
- do not prune images;
- do not rewrite failed deployment evidence;
- do not begin independent restore work;
- do not change provider configuration as an unrelated experiment.

Preserve the failed state and rollback evidence long enough to understand and
recover it safely.

---

## 11. Verify Durable Rollback Image References

Captured image IDs are not sufficient by themselves if Docker has no durable
reference that keeps them available.

Before relying on rollback:

1. confirm each required prior image identity exists;
2. confirm the transaction-scoped rollback reference resolves to that exact
   identity;
3. confirm no required prior image was pruned;
4. confirm local first-party images have retained exact rollback identities.

Do not roll back using `latest`, `local`, or another mutable tag unless the
captured deployment evidence proves that tag resolves to the exact intended
prior image.

---

## 12. Verify Previous Source Identity

Establish the exact prior Git commit from deployment evidence.

Do not select the rollback commit by:

- guessing from `git log`;
- using an old release name from memory;
- assuming a tag still points to the intended prior runtime;
- choosing "the commit before this one" without deployment evidence.

The prior commit must match the recorded previous verified baseline or
transaction capture.

---

## 13. Verify Previous Compose and Configuration Inputs

Rollback must restore the deployment definition that belonged to the prior
known-good runtime.

Confirm:

- Compose files;
- environment/configuration inputs;
- enabled service/module scope;
- ingress configuration;
- systemd/unit changes if they were part of the deployment;
- persistent runtime ownership requirements.

Do not combine the old image set with incompatible new configuration.

Rollback is a complete deployment-state reconstruction, not only an image
selection exercise.

---

## 14. Evaluate Migration Reversibility

If the failed deployment included a migration, inspect the migration
declaration before rollback.

The declaration must state whether rollback is:

- directly reversible;
- reversible only with state restoration;
- forward-recovery only;
- irreversible.

If migration behavior is unknown, do not perform destructive rollback.

Production is not the place to invent migration reversal logic.

---

## 15. Determine Rollback Scope

Rollback should be bounded to the affected deployment surface.

Examples may include:

- core Atlas services;
- ingress;
- a specific module;
- one migration target plus required dependents.

Do not recreate unrelated healthy services simply because a broad Compose
command is convenient.

Recovery scope must include required dependency/runtime contracts while
remaining as narrow as safely possible.

---

## 16. Runtime Ownership Preflight

Before recreating a non-root service, verify its writable persistent paths are
owned and permissioned for its effective runtime identity.

This is a permanent deployment-recovery rule.

A service may be source-correct and still fail recovery when the persistent
filesystem does not match the container identity.

Do not:

- make the container privileged;
- chmod runtime state world-writable;
- recursively change ownership without understanding the declared service
  contract.

Fix the exact ownership boundary required by the service.

---

## 17. Execute the Supported Rollback

Current Atlas CLI help exposes:

```bash
atlas deployment rollback <deployment-id>
```

Use the failed deployment identity required by the supported transaction.

The rollback implementation should consume the captured deployment evidence
rather than reconstructing state from mutable names.

Do not invoke lower-level Docker mutation as an undocumented substitute for the
Atlas rollback boundary unless the certified recovery procedure explicitly
requires it.

---

## 18. Rollback Apply Is Not Completion

A successful rollback command or successful container recreation is not proof
of recovery.

The resulting runtime remains under maintenance and transaction ownership until
all required verification passes.

Treat the command result as "rollback apply completed," not "production
recovered."

---

## 19. Core Verification After Rollback

Run the applicable Atlas verification suite.

At minimum:

```bash
atlas doctor
atlas verify
```

Also inspect:

```bash
atlas health
atlas operations latest
```

where appropriate.

Recovery success is health-based, not command-based.

---

## 20. Service and Module Verification

Verify every service/module affected by the failed deployment or rollback.

Depending on scope, this may include:

- service health;
- startup/readiness policy;
- module verification;
- Scheduler behavior;
- provider connectivity;
- Media request behavior;
- Sports runtime;
- Notifications/runtime-bus health;
- persistent storage access.

Do not declare success while a required dependent runtime remains degraded.

---

## 21. Provider Verification

When rollback affects a provider boundary, verify the normal healthy path and
failure semantics.

Atlas must continue to distinguish provider unavailability from authoritative
empty results.

A provider outage must not:

- erase retained state;
- authorize cleanup;
- cause duplicate request mutation;
- cancel Sports state;
- fabricate success.

---

## 22. Scheduler Verification

If the deployment affected Scheduler code, systemd units, task registration, or
runtime ownership, verify:

```bash
atlas scheduler list
atlas scheduler history
```

and the expected state of:

```text
atlas-scheduler.timer
atlas-scheduler.service
```

Treat a failed one-shot dispatcher invocation as a Scheduler execution signal.

Do not create a second scheduler as a rollback workaround.

---

## 23. Maintenance-State Ingress Verification

Before public reopen, verify the maintenance traffic state:

1. Caddy is healthy.
2. Required Portal/API backends are healthy.
3. Public Portal/API traffic remains intentionally isolated with HTTP 503.

This proves that maintenance is deliberate rather than an ingress outage.

Do not reopen public traffic until this state passes.

---

## 24. Reopen Public Traffic

After the recovered runtime passes all required maintenance-state checks,
disable maintenance through the supported transaction path.

Then re-run normal public ingress verification.

If reopened Portal/API verification fails:

- re-enable or retain maintenance;
- keep rollback/recovery ownership;
- do not publish the recovered baseline;
- continue diagnosis or forward recovery.

A failed reopen means rollback has not succeeded.

---

## 25. Publish the Recovered Verified Baseline

Only after all rollback and reopened-ingress checks pass may Atlas publish a new
verified baseline for the recovered runtime.

The recovered baseline should identify the actual known-good runtime now
serving production.

It may match the previous source/runtime identity, but it is still a new
verified post-recovery observation.

---

## 26. Release the Lock

Release the shared deployment/restore lock only after rollback reaches its
defined terminal success state.

Lock release and maintenance disablement are terminal actions.

Do not put them into unconditional cleanup logic that runs after failure.

---

## 27. Preserve Failed Deployment History

The failed deployment remains failed.

Rollback success does not rewrite:

```text
failed deployment
```

into:

```text
successful deployment
```

Instead, record a later recovery/rollback transaction that established a known
safe runtime.

Historical failure evidence is operationally valuable and must remain
immutable.

---

## 28. Forward Recovery Boundary

Forward recovery is preferred over rollback when the prior runtime cannot be
safely reconstructed or when the discovered defect can be corrected with a
bounded validated repair.

Examples include:

- runtime ownership repair;
- configuration correction;
- dependency recovery;
- a migration that is not safely reversible.

Forward recovery must preserve the failed deployment record and independently
pass the same required health/ingress gates.

---

## 29. Escalation to Backup/Restore

Escalate to the Backup/Restore procedure when authoritative Atlas state must be
recovered from archive.

Examples include:

- state corruption;
- state loss;
- a reversible migration whose declared reversal requires archive restoration;
- deployment rollback that cannot restore the required authoritative state.

Do not extract archive content manually over live production.

Use the dedicated staged/validated restore transaction.

---

## 30. Restore Safety Boundary

Live Atlas restore has its own requirements, including:

- verified archive;
- isolated staging;
- staged validation;
- restore plan;
- clean synchronized production source;
- verified deployment baseline;
- shared lock ownership;
- maintenance isolation;
- explicit live authorization.

Representative commands include:

```bash
atlas restore inspect <archive>
atlas restore verify <archive>
atlas restore stage <archive>
atlas restore validate-stage <staging-root>
atlas restore plan <staging-root>
atlas restore apply <staging-root> --confirm-live
```

Those commands belong to state restoration, not ordinary deployment rollback.

---

## 31. Interrupted Rollback

If rollback itself fails:

- do not disable maintenance;
- do not release the transaction lock;
- preserve rollback audit evidence;
- preserve the previous verified baseline;
- determine whether another rollback attempt, forward recovery, or state restore
  is safe;
- do not stack unrelated mutations on top of the failed rollback.

A failed rollback is a new recovery event that requires explicit diagnosis.

---

## 32. Storage and ENOSPC During Rollback

Rollback must fail closed on storage exhaustion or persistence failure.

If `ENOSPC` or another storage failure occurs:

- stop optional mutation;
- preserve last durable state;
- inspect storage capacity and writable paths;
- do not delete audit/rollback evidence just to free enough space for another
  mutation;
- repair the storage boundary before continuing.

---

## 33. Security-Sensitive Rollback

When rolling back security-sensitive changes, verify that the recovered runtime
still satisfies current accepted security requirements.

Do not reintroduce an older insecure configuration merely because it was
previously operational.

Where a prior runtime no longer satisfies required security acceptance,
rollback may be disallowed and forward recovery may be required instead.

Security acceptance can therefore constrain rollback eligibility.

---

## 34. Rollback Completion Checklist

Rollback is complete only when the applicable checks pass.

- [ ] Failed deployment identified.
- [ ] Previous verified baseline identified.
- [ ] Shared transaction ownership established.
- [ ] Maintenance isolation active.
- [ ] Exact prior Git identity verified.
- [ ] Exact prior Compose/config inputs verified.
- [ ] Exact prior image identities retained.
- [ ] Durable rollback references verified.
- [ ] Migration reversibility evaluated.
- [ ] Rollback scope bounded.
- [ ] Required runtime ownership validated.
- [ ] Supported rollback transaction executed.
- [ ] `atlas doctor` passes.
- [ ] `atlas verify` passes.
- [ ] Affected services/modules/providers pass.
- [ ] Scheduler checks pass when affected.
- [ ] Maintenance-state ingress verification passes.
- [ ] Normal public ingress passes after reopen.
- [ ] Recovered verified baseline published.
- [ ] Lock released only after terminal success.
- [ ] Original failed deployment remains immutable.
- [ ] Recovery outcome documented.

---

## 35. What Must Not Be Done

Do not:

- guess the prior production commit;
- use `latest` as rollback identity;
- prune rollback images before recovery is complete;
- mix old images with incompatible new configuration;
- manually delete the shared lock;
- disable maintenance before verification;
- restore an archive as a generic rollback shortcut;
- recreate unrelated healthy services without reason;
- make runtime storage world-writable as a recovery shortcut;
- declare success because containers recreated;
- rewrite failed deployment history as success;
- bypass current security requirements just to restore old behavior.

---

## 36. Relationship to Upgrade

The Upgrade Guide defines:

- the pre-change capture required for rollback;
- when rollback becomes necessary;
- which deployment evidence must be retained.

This Rollback Guide owns the recovery procedure after rollback is selected.

A safe rollback depends on a safe upgrade having captured the necessary
evidence beforehand.

---

## 37. Relationship to Backup/Restore

The Backup/Restore Guide owns authoritative Atlas state restoration.

Rollback uses the pre-change backup as evidence and as a possible recovery
resource, but does not automatically extract it.

State restore begins only when the recovery decision explicitly crosses into
the Backup/Restore boundary.

---

## 38. Legacy Recovery Guidance

Older Atlas operations documentation may summarize recovery as restoring the
latest verified backup, starting services, and running verification.

That summary is not the certified v1.0 deployment rollback procedure.

The current rollback contract additionally requires:

- exact failed deployment identity;
- previous verified baseline;
- exact source/Compose/image evidence;
- durable rollback references;
- migration reversibility;
- maintenance isolation;
- shared transaction ownership;
- bounded rollback scope;
- runtime ownership validation;
- health-based acceptance;
- reopened-ingress verification;
- immutable failed-transaction evidence.

Do not use the legacy recovery shorthand as the sole rollback procedure.

---

## 39. Authoritative References

Primary references:

- `ADMINISTRATOR_GUIDE.md`
- `UPGRADE_GUIDE.md`
- `../OPERATIONS.md`
- `../operations/RELEASE_PROMOTION.md`
- `../architecture/DEPLOYMENT_SAFETY.md`
- `../architecture/BACKUP_RECOVERY.md`
- `../architecture/SECURITY.md`
- `../architecture/STARTUP_POLICY.md`
- `../architecture/RESTART_RECOVERY.md`
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

When older recovery shorthand conflicts with certified Deployment Safety,
Backup/Recovery, Security, or release policy, use the newer certified contract.
