# Project Atlas Backup and Restore Guide

**Document Status:** D.3F v1.0 Documentation Candidate
**Applies To:** Project Atlas v1.0 backup, restore, and Atlas-state recovery
**Audience:** Project Atlas administrators and maintainers
**Canonical Repository Path:** `docs/guides/BACKUP_RESTORE_GUIDE.md`

---

## 1. Purpose

This guide defines the supported Project Atlas v1.0 backup and restore
procedure.

Atlas backup and restore are explicit recovery transactions.

An archive is not considered recovery-capable merely because it exists or can
be opened. Atlas must identify, protect, validate, stage, and successfully
restore the authoritative state it claims before recovery can be considered
complete.

Unvalidated archive content must never be extracted directly over live
production state.

---

## 2. Backup and Restore Safety Principles

Project Atlas recovery follows these rules:

1. Backups are validated recovery artifacts, not ordinary compressed files.
2. Canonical backup publication occurs only after required validation passes.
3. Restore inspection and verification are read-only.
4. Restore staging happens outside live production state.
5. Live restore requires explicit operator authorization.
6. Production restore requires a clean synchronized source boundary.
7. Restore uses the shared deployment/restore mutation lock.
8. Public maintenance isolation remains active through live mutation and
   verification.
9. Writer services are quiesced only as required by the restore transaction.
10. Restore success is health-based, not command-based.
11. Interrupted restores remain explicit recovery transactions.
12. Backup scope must never be overstated.

---

## 3. Backup Scope

Atlas v1.0 provides a state-complete recovery path for the authoritative Atlas
state surfaces declared by the recovery format.

That does **not** mean Atlas backup is a complete host or Media-stack disaster
recovery system.

The Atlas recovery archive does not claim complete recovery of:

- the Media library itself;
- Jellyfin databases;
- Sonarr databases;
- Radarr databases;
- qBittorrent state;
- every third-party application database;
- the Proxmox host;
- Docker Engine;
- arbitrary host configuration outside the declared backup boundary.

Document additional recovery requirements separately for state outside the
Atlas recovery format.

---

## 4. Canonical Backup Command

Create a canonical Atlas backup with:

```bash
atlas backup
```

Add an operator note when useful:

```bash
atlas backup --notes "before maintenance"
```

Read help or list existing completed backups without creating a new one:

```bash
atlas backup --help
atlas backup --list
```

A successful backup command must publish a validated canonical artifact.

---

## 5. Production Backup Location

Production backups are stored under the configured `ATLAS_BACKUP_DIR`.

The current production documentation identifies:

```text
/mnt/storage/backups/atlas
```

as the normal Atlas backup location.

The normal production policy retains the newest 10 canonical
`atlas-*.tar.gz` archives.

A successful new backup can therefore rotate the oldest canonical archive.

Plan retention with that behavior in mind.

---

## 6. Local Backup Failure Domain

A local Atlas backup stored on the same host/storage failure domain does not
provide independent host-loss disaster recovery.

If recovery archives must survive loss of the Atlas host or its attached
storage, copy or replicate validated canonical backups to an independently
protected storage domain.

Do not describe same-host backup retention as off-host disaster recovery.

---

## 7. Recovery Format 1

Project Atlas v1.0 uses the certified state-complete recovery format defined by
the current Backup and Recovery architecture.

A Format 1 archive includes:

- project/configuration content within the declared backup boundary;
- recovery metadata;
- a recovery manifest;
- checksums;
- allowlisted authoritative Atlas state;
- identity and validation information required by restore.

Only declared recovery content is eligible for live replacement.

Unexpected archive content must not silently become live state.

---

## 8. Backup Publication Boundary

Backup creation is transactional.

A backup is canonical only after Atlas has:

1. collected the declared backup content;
2. written recovery metadata;
3. written the recovery manifest;
4. calculated required checksums;
5. validated the archive;
6. published the canonical artifact.

A partial archive is not equivalent to a completed backup.

Do not rename or manually promote a partial backup into canonical status.

---

## 9. Pre-Maintenance Backup

Before covered production upgrades or other risky maintenance, create and
validate a fresh backup.

Representative command:

```bash
atlas backup --notes "before maintenance"
```

The deployment or maintenance record should preserve the exact backup artifact
identity used for recovery evidence.

Do not proceed with a migration that requires recovery evidence when the
required recovery artifact does not exist.

---

## 10. Read-Only Restore Inspection

Begin restore work with read-only inspection:

```bash
atlas restore inspect <archive>
```

Inspection should identify the archive and recovery metadata without writing
over live state.

Use inspection to understand:

- archive format;
- recovery identity;
- declared content;
- expected restore surfaces;
- compatibility information.

Inspection alone does not authorize restore.

---

## 11. Verify the Archive

Verify the archive before staging:

```bash
atlas restore verify <archive>
```

Verification must fail closed for invalid, incomplete, incompatible, or
tampered recovery artifacts.

Do not continue to live restore merely because the archive can be decompressed.

---

## 12. Stage the Restore

Stage verified recovery content outside live state:

```bash
atlas restore stage <archive>
```

Staging creates an isolated restore workspace.

The staging root must not be the live Atlas state location.

Do not manually extract backup contents over live production state.

---

## 13. Validate the Staged Restore

Validate staged recovery content:

```bash
atlas restore validate-stage <staging-root>
```

This step confirms that the staged recovery material satisfies the restore
contract before live mutation.

A failed stage validation blocks restore.

Do not modify staged files merely to force validation to pass without
understanding the recovery contract.

---

## 14. Generate the Restore Plan

Generate the live restore plan:

```bash
atlas restore plan <staging-root>
```

The plan should identify the bounded state replacement and required runtime
coordination.

Review the plan before authorizing live mutation.

Restore planning is still pre-mutation work.

---

## 15. Production Restore Preconditions

A production live restore requires the certified source and deployment
preconditions.

At minimum:

- the repository is on clean `main`;
- local `main` exactly equals `origin/main`;
- a verified deployment baseline exists;
- staged recovery state has passed validation;
- the shared deployment/restore lock can be acquired safely;
- maintenance isolation can be established;
- the operator explicitly authorizes live restore.

If these conditions are not met, live restore must not proceed.

---

## 16. Shared Mutation Lock

Live restore uses the same shared production mutation boundary as deployment.

Do not run a live restore concurrently with:

- production upgrade;
- deployment rollback;
- another live restore.

Do not manually delete the shared lock.

If ownership cannot be established safely, fail closed.

---

## 17. Maintenance Isolation

Live restore is performed under maintenance isolation.

Caddy owns the public maintenance boundary.

During restore:

- normal public Portal/API traffic remains isolated;
- required backends may remain observable;
- maintenance state is intentional;
- public reopen occurs only after restore verification succeeds.

Do not disable maintenance simply because the restore command exited.

---

## 18. Fresh Pre-Restore Recovery Point

Before replacing live state, the restore transaction creates or requires a
fresh pre-restore recovery point for the current live Atlas state.

This provides a bounded recovery path if the applied restore must later be
aborted.

Do not begin live state replacement without the transaction's required
pre-restore safety evidence.

---

## 19. Writer Quiescence

The restore transaction must coordinate services that write the authoritative
state being replaced.

Writers are quiesced only to the extent required by the recovery contract.

Do not stop unrelated healthy services merely because a broad shutdown is
easier.

Do not restore state while active writers can race the replacement.

---

## 20. Apply the Live Restore

The supported live restore entry point is:

```bash
atlas restore apply <staging-root> --confirm-live
```

`--confirm-live` is explicit operator authorization.

Do not automate around or omit the confirmation boundary.

Live apply coordinates the declared state replacement and runtime recovery
transaction.

---

## 21. Live State Replacement

The restore transaction replaces only the declared authoritative Atlas state
surfaces.

It must not turn arbitrary archive content into live state.

The replacement must remain bounded, auditable, and reversible according to the
restore transaction.

Do not manually copy extra files into the live recovery boundary during apply.

---

## 22. Consumer Validation

After state replacement, Atlas validates consumers of the restored state.

Depending on the recovered surfaces, this may include:

- Atlas API;
- Scheduler state consumers;
- request/favorites/policy consumers;
- module consumers;
- Operations or audit readers;
- other state-dependent services.

A restore is not successful until required consumers can read the recovered
state correctly.

---

## 23. Writer Recovery

After consumer validation, required writer services are recovered.

Writer restart alone is not proof that recovery succeeded.

Verify:

- expected runtime identity;
- writable-path ownership;
- health/heartbeat;
- ability to persist required state;
- no unexpected state corruption.

---

## 24. Atlas Verification After Restore

Run the required Atlas verification after live restore.

At minimum:

```bash
atlas doctor
atlas verify
```

Also perform applicable:

- module verification;
- provider checks;
- Scheduler checks;
- request/recovery checks;
- security checks;
- ingress checks.

Restore success is health-based, not command-based.

---

## 25. Verify Maintenance-State Ingress

Before reopening public traffic, verify that:

1. Caddy is healthy;
2. required Portal/API backends are healthy;
3. public Portal/API traffic is intentionally isolated with HTTP 503.

This proves the platform is in controlled maintenance rather than failed
ingress.

---

## 26. Reopen Public Traffic

After all restore verification passes, reopen public traffic through the
supported maintenance transaction.

Then verify normal Portal/API ingress again.

If reopened ingress fails:

- re-enable or retain maintenance;
- preserve restore transaction ownership;
- do not declare restore success;
- continue through explicit restore recovery.

---

## 27. Finalize the Restore

A restore reaches successful terminal state only after:

- state replacement completed;
- consumers validated;
- writers recovered;
- Atlas verification passed;
- module/provider checks passed where required;
- maintenance-state ingress passed;
- normal ingress passed after reopen;
- transaction evidence was recorded.

Only then may the shared lock be released.

---

## 28. Interrupted Restore

If a live restore fails after mutation begins, do not:

- disable maintenance;
- manually release the shared lock;
- overwrite transaction evidence;
- start an unrelated deployment;
- manually copy backup content into live state.

The restore remains an explicit interrupted recovery transaction.

---

## 29. Resume an Interrupted Restore

After diagnosis, resume the transaction with:

```bash
atlas restore resume <restore-id> --confirm-live
```

Resume revalidates the transaction and attempts to complete the applied restore
through the supported safety boundary.

Use resume only when the recovery state supports continuing forward.

---

## 30. Abort an Interrupted Restore

When the correct action is to restore the displaced pre-apply state, use:

```bash
atlas restore abort <restore-id> --confirm-live
```

Abort transactionally restores the saved pre-apply state and recovers the
platform through the same safety boundary.

Do not treat abort as a generic "undo" command without first understanding the
transaction state.

---

## 31. Resume and Abort Are Explicit Recovery Actions

Both resume and abort require explicit live authorization.

Neither action may silently:

- reopen public traffic;
- release the mutation lock;
- rewrite the failed transaction as success;
- skip verification.

The original failure remains historical evidence.

---

## 32. Restore and Deployment Rollback Are Different

Deployment rollback restores a prior application/runtime deployment identity
from captured deployment evidence.

Atlas state restore replaces authoritative Atlas state from a validated staged
archive.

Do not use one as an undocumented substitute for the other.

The Rollback Guide owns deployment rollback.

This guide owns Atlas state recovery.

---

## 33. Migration Recovery

A migration that modifies persistent state must declare its recovery behavior
before production execution.

The declaration must identify whether recovery is:

- ordinary deployment rollback;
- state restore;
- forward recovery;
- irreversible.

If a migration requires state restoration, use the certified restore
transaction rather than manually reversing files or database state.

---

## 34. Backup Verification Before Upgrade

`atlas backup` is the required pre-update repository/configuration recovery
boundary for changes within its certified scope.

The backup archive must validate before the deployment continues.

If an upgrade changes persistent state outside that scope, provide additional
state-specific recovery evidence.

Do not claim reversibility when the required recovery evidence does not exist.

---

## 35. Backup Retention

The current normal policy retains the newest 10 canonical Atlas backups.

Because a new successful backup can rotate the oldest canonical archive:

- understand retention before maintenance;
- preserve special recovery artifacts externally when longer retention is
  required;
- do not rely on an old local archive remaining indefinitely.

Retention is not the same as independent disaster recovery.

---

## 36. Backup Integrity

Do not manually edit canonical backup archives or recovery manifests.

If a backup no longer verifies, treat it as invalid recovery evidence.

Create a new canonical backup from a healthy source state rather than modifying
the archive to make verification pass.

---

## 37. Restore Integrity

Do not edit staged recovery state simply to bypass validation.

If staged validation fails:

- inspect the validation error;
- verify archive compatibility;
- verify archive integrity;
- verify the selected staging root;
- determine whether another canonical archive is required.

Fail closed until the recovery material is trustworthy.

---

## 38. Storage Exhaustion

Backup and restore must fail closed on `ENOSPC` or other persistence failures.

If storage becomes exhausted:

- stop optional mutations;
- preserve the last durable state;
- preserve audit and recovery evidence;
- free or add storage through a controlled procedure;
- revalidate before continuing.

Do not delete the only valid backup or recovery evidence simply to make enough
space for the next write.

---

## 39. Secret Handling

Backup and restore operations can touch sensitive operator-managed state.

Never print or publish:

- passwords;
- JWT signing secrets;
- bearer tokens;
- refresh tokens;
- API keys;
- webhook URLs;
- plaintext invitation tokens.

Recovery evidence may report presence, ownership, identity, and validation
status without exposing secret values.

---

## 40. Recovery Window Planning

The controlled single-host v1.0 restore evidence reached writer restart in
roughly 69 seconds on the tested topology.

That result is **not an SLO**.

For the current small single-host topology, reserve at least **5–10 minutes**
for a restore-oriented maintenance window and increase the allowance as state
size, validation cost, or infrastructure complexity grows.

Never skip required validation to fit an overly narrow maintenance window.

---

## 41. Backup Checklist

Before relying on a backup, confirm:

- [ ] `atlas backup` completed successfully.
- [ ] Canonical archive was published.
- [ ] Recovery manifest is present.
- [ ] Checksums/validation passed.
- [ ] Backup identity is recorded.
- [ ] Retention consequences are understood.
- [ ] Additional state-specific recovery evidence exists when required.
- [ ] Off-host protection exists when host-loss recovery is required.

---

## 42. Restore Preparation Checklist

Before live restore:

- [ ] Archive inspected.
- [ ] Archive verified.
- [ ] Archive staged outside live state.
- [ ] Staged state validated.
- [ ] Restore plan reviewed.
- [ ] Production source is clean synchronized `main`.
- [ ] Verified deployment baseline exists.
- [ ] Shared lock can be acquired safely.
- [ ] Maintenance isolation can be established.
- [ ] Fresh pre-restore recovery point will exist.
- [ ] Writer coordination is understood.
- [ ] Operator is ready to authorize `--confirm-live`.

---

## 43. Restore Completion Checklist

Before declaring restore complete:

- [ ] Declared live state replacement completed.
- [ ] Required consumers validated.
- [ ] Required writers recovered.
- [ ] `atlas doctor` passes.
- [ ] `atlas verify` passes.
- [ ] Module/provider checks pass where required.
- [ ] Scheduler checks pass where required.
- [ ] Maintenance-state ingress passes.
- [ ] Normal public ingress passes after reopen.
- [ ] Restore transaction reached terminal success.
- [ ] Shared lock was released only after success.
- [ ] Original failure/interruption evidence remains immutable.
- [ ] Recovery outcome was documented.

---

## 44. What Must Not Be Done

Do not:

- treat any `.tar.gz` file as automatically recovery-capable;
- extract unvalidated archive content over live production;
- skip staging;
- skip staged validation;
- bypass `--confirm-live`;
- manually delete the shared lock;
- disable maintenance before verification;
- restore while writers can race the replacement;
- mix undeclared archive content into live state;
- claim a local same-host backup is independent disaster recovery;
- rewrite an interrupted restore as success;
- substitute state restore for ordinary deployment rollback;
- delete the only valid recovery artifact to free space.

---

## 45. Relationship to Upgrade

The Upgrade Guide requires a validated pre-change backup and defines when
additional migration recovery evidence is required.

This guide defines the backup artifact and Atlas-state restore procedure.

A backup is part of safe upgrade preparation, but it is not proof that every
upgrade is automatically reversible.

---

## 46. Relationship to Rollback

The Rollback Guide restores application/runtime deployment identity from
captured deployment evidence.

This guide restores authoritative Atlas state from a verified staged archive.

A rollback may use the backup identity as recovery evidence without applying the
archive.

State restore begins only when the recovery decision explicitly requires it.

---

## 47. Legacy Backup/Recovery Guidance

Older Atlas operations documentation may summarize recovery as:

1. restore the latest verified backup;
2. confirm storage mounts;
3. start services;
4. run verification.

That shorthand is not the complete certified v1.0 restore transaction.

The current restore contract additionally requires:

- read-only archive inspection;
- archive verification;
- isolated staging;
- stage validation;
- restore planning;
- clean synchronized production source;
- verified deployment baseline;
- shared mutation lock;
- maintenance isolation;
- fresh pre-restore recovery point;
- writer coordination;
- explicit live authorization;
- consumer validation;
- writer recovery;
- health and ingress verification;
- explicit resume/abort handling for interruption.

Do not use the legacy shorthand as the sole production restore procedure.

---

## 48. Authoritative References

Primary references:

- `ADMINISTRATOR_GUIDE.md`
- `UPGRADE_GUIDE.md`
- `ROLLBACK_GUIDE.md`
- `../04-backup-restore.md`
- `../OPERATIONS.md`
- `../architecture/BACKUP_RECOVERY.md`
- `../architecture/DEPLOYMENT_SAFETY.md`
- `../architecture/SECURITY.md`
- `../architecture/STORAGE_EXHAUSTION.md`
- `../ADR/0023-backup-restore-recovery-boundaries.md`
- `../ADR/0022-production-deployment-safety-boundaries.md`
- `../ADR/0024-security-trust-boundaries.md`
- `../operations/RELEASE_PROMOTION.md`
- `../releases/RELEASE_CHECKLIST.md`
- `../governance/RELEASE_POLICY.md`
- `../../ROADMAP.md`

When older recovery shorthand conflicts with the certified Backup/Recovery,
Deployment Safety, Security, or release-policy contract, use the newer certified
contract.
