# Project Atlas Administrator Guide

**Document Status:** D.3A v1.0 Documentation Candidate
**Applies To:** Project Atlas v1.0 administration and operations
**Audience:** Project Atlas administrators and maintainers
**Canonical Repository Path:** `docs/guides/ADMINISTRATOR_GUIDE.md`

---

## 1. Purpose

This guide is the administrator entry point for operating Project Atlas.

It defines the supported administrative workflow, the boundaries between routine
observation and production mutation, the minimum safety rules for maintenance,
and the authoritative references an administrator should use when a task becomes
specialized.

Project Atlas is designed so ordinary users can use the Portal without direct
Docker, Proxmox, provider, or repository access. Administrators retain the
operational control required to validate, maintain, recover, and support the
platform.

This guide does not replace architecture decisions, release policy, deployment
transactions, or backup/restore contracts. When a specialized procedure is more
specific than this guide, the specialized certified contract is authoritative.

---

## 2. Administration Principles

Project Atlas administration follows these rules:

1. **Observe before changing.**
2. **Validate before mutation.**
3. **Back up before a covered production change.**
4. **Use maintenance isolation for planned production changes that affect user traffic.**
5. **Preserve rollback and recovery evidence before changing mutable runtime state.**
6. **Verify after every production change.**
7. **Fail closed when state, ownership, recovery capability, or provider outcome is uncertain.**
8. **Do not bypass a held deployment/restore lock or maintenance state.**
9. **Keep secrets outside version control and out of diagnostics.**
10. **Keep documentation synchronized with certified behavior.**

Operational safety takes precedence over convenience or speed.

---

## 3. Administrator Surfaces

Atlas administrators operate the platform through several supported surfaces.

### 3.1 Atlas Portal

The authenticated Administration Portal provides the supported v1.0
presentation for service visibility, including:

- managed-service overview;
- service runtime and health presentation;
- read-only service detail;
- update-availability presentation;
- maintenance-history presentation;
- responsive phone and tablet administration layouts.

The v1.0 Service Lifecycle Portal surface is intentionally read-only. It does
not provide generic restart, update, rollback, start, stop, or other lifecycle
mutation controls.

### 3.2 Atlas CLI

The Atlas CLI is the primary operator command surface. Use:

```bash
atlas help
```

as the authoritative command index for the installed checkout.

Common read-only or diagnostic entry points include:

```bash
atlas version
atlas status
atlas services
atlas urls
atlas git

atlas doctor
atlas verify
atlas health

atlas operations report
atlas operations latest
atlas operations history
atlas operations compare

atlas ari collect
atlas ari report

atlas scheduler list
atlas scheduler history

atlas maintenance status
```

Command availability must be verified against `atlas help` before relying on a
command in production.

### 3.3 Repository

The Git repository is the source of truth for Atlas code, tracked
configuration, architecture, and documentation.

Before repository work, inspect:

```bash
git status --short
git branch --show-current
git log -1 --oneline
```

A dirty or unexpected checkout must be understood before it is used for
release, deployment, restore, or documentation certification.

---

## 4. Production Source and Release Boundary

`main` is the production-stable source branch.

Focused `feature/*`, `fix/*`, `docs/*`, and similar branches are development
surfaces. Passing local tests does not make a development branch an approved
production deployment source.

The normal release promotion direction is:

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

Source promotion and production runtime deployment are separate actions. A
merge does not by itself authorize a production runtime change.

Atlas v1.0 does not require a permanent `develop` branch.

### 4.1 Reconciled historical `v1.0.0` tag

An older annotated `v1.0.0` tag previously existed in the repository and
predated the current v1.0 release-readiness program. Independent release
forensics confirmed that it was not valid final v1.0 certification evidence:
the tag claimed a production v1.0.0 release while the tagged commit contained
repository `VERSION` `0.9.0`.

The project owner explicitly reconciled that historical tag during final
release preparation. It is now absent locally and from `origin`; the underlying
historical commit remains preserved in Git history.

This reconciliation does not mean Project Atlas v1.0.0 has been released. The
final `v1.0.0` tag must still be created through the certified release process
and must point to the exact approved final-release commit.

---

## 5. Routine Operational Workflow

Routine administration should favor read-only observation.

A representative health review is:

```bash
atlas doctor
atlas verify
atlas health
atlas operations latest
atlas scheduler history --limit 10
atlas git
```

When a fresh Operations observation is required:

```bash
atlas operations report
```

When a new immutable Operations snapshot is intentionally required:

```bash
atlas operations save
```

ARI remains available for the operational intelligence surfaces it owns:

```bash
atlas ari collect
atlas ari report
```

Do not create new state merely to satisfy a checklist when an existing
read-only report is sufficient.

---

## 6. Suggested Review Cadence

These are operating recommendations, not release guarantees.

### Daily or frequent review

- review `atlas doctor`;
- review `atlas verify`;
- inspect service and storage health;
- inspect recent Scheduler failures;
- review user-impacting provider failures;
- confirm the repository is in the expected state when engineering work is active.

### Weekly review

- review Operations history and meaningful changes;
- review storage growth;
- confirm backup creation is succeeding;
- inspect unresolved container or service warnings;
- verify VPN-dependent services remain fail closed;
- review Scheduler execution health.

### Monthly or planned maintenance review

- review update availability;
- review backup and restore readiness;
- review storage capacity and growth;
- review dependency/security maintenance needs;
- review documentation for stale operational instructions;
- schedule production changes through a tested maintenance window rather than
  applying opportunistic updates.

---

## 7. Health and Observability

### 7.1 Doctor

Use:

```bash
atlas doctor
```

for platform health checks.

A Doctor failure is an operational signal. Do not continue a planned
production mutation merely because the underlying containers appear to be
running.

### 7.2 Verify

Use:

```bash
atlas verify
```

for infrastructure and service verification.

Verification is particularly important:

- before a planned production change;
- after a production change;
- after recovery or restore;
- after storage, VPN, ingress, or service configuration changes.

### 7.3 Operations

Atlas Operations provides read-only host and Docker reporting plus immutable
report persistence.

Useful commands include:

```bash
atlas operations report
atlas operations report --json
atlas operations save
atlas operations latest
atlas operations history
atlas operations history --limit 10
atlas operations compare
atlas operations compare --include-unchanged
```

`report` is live and read-only.

`save` intentionally persists a new immutable report and updates
`latest.json`.

`latest`, `history`, and `compare` read previously persisted reports without
collecting a new one.

### 7.4 Scheduler

Atlas uses one shared TaskScheduler. Production recurring dispatch is provided
by the repository-owned `atlas-scheduler.timer` and `atlas-scheduler.service`;
systemd does not own task-specific cadence.

A failed dispatcher invocation should be inspected as a Scheduler execution
signal. Do not create a second scheduler or a separate daemon loop as a
workaround.

---

## 8. Maintenance Mode

Caddy owns the public maintenance boundary because it is upstream of both the
Portal and API.

The supported CLI operations are:

```bash
atlas maintenance status
atlas maintenance enable
atlas maintenance disable
```

When maintenance is enabled:

- normal public Portal and API traffic receives HTTP 503 Service Unavailable;
- a bounded maintenance response is presented;
- a `Retry-After` response is supplied where practical;
- backends generally remain running unless the maintenance operation requires
  otherwise;
- maintenance state remains observable;
- Caddy has a separate liveness path so intentional maintenance is not confused
  with proxy failure.

Maintenance state is runtime state. It is not toggled by rewriting tracked
Caddy configuration.

### 8.1 Do not bypass maintenance ownership

If an update, rollback, recovery, or restore fails after maintenance begins,
Atlas may intentionally retain maintenance mode.

Do not manually disable maintenance simply to reopen user traffic. First
establish the transaction's documented recovery path and a known-safe runtime.

---

## 9. Deployment Lock

Only one production deployment/restore transaction may own the shared mutation
boundary at a time.

The lock is runtime state, not a Git file.

Lock acquisition and stale-lock handling must fail closed when ownership cannot
be established safely.

Do not manually delete `update.lock` to bypass a failed transaction.

The lock is released only after the owning transaction reaches its defined
terminal state.

---

## 10. Production Updates

A production update is not equivalent to running an arbitrary Docker pull or
deploying the current development checkout.

The certified production transaction requires, at a minimum:

1. acquire the deployment lock;
2. validate operator, repository, source, and runtime preconditions;
3. capture pre-change Git, Compose, and exact image state;
4. retain durable rollback references for mutable image identities;
5. enable maintenance mode;
6. create and validate the required pre-update Atlas backup;
7. validate any schema or configuration migration plan;
8. apply only the approved update scope;
9. run required Doctor, Verify, ingress, runtime, and migration-specific checks;
10. record outcome and rollback evidence;
11. reopen public traffic only after required checks succeed;
12. publish a new verified baseline and release the lock only at the defined
    successful terminal state.

If apply or post-change validation fails, the previous verified baseline remains
authoritative and maintenance/lock ownership may remain intentionally held.

Do not use `docker image prune` while rollback remains possible.

Until the dedicated v1.0 Upgrade Guide is certified, use
`docs/operations/RELEASE_PROMOTION.md`,
`docs/architecture/DEPLOYMENT_SAFETY.md`, and ADR 0022 as the authoritative
production update references.

---

## 11. Backup and Restore

### 11.1 Backups

The canonical backup entry point is:

```bash
atlas backup
```

Useful read-only backup commands include:

```bash
atlas backup --help
atlas backup --list
```

Atlas v1.0 Format 1 recovery archives protect declared Atlas configuration and
authoritative Atlas state surfaces. A file merely existing with a `.tar.gz`
extension does not make it recovery-capable.

A canonical backup is published only after the archive, recovery manifest,
declared state, and checksums validate.

### 11.2 Read-only restore inspection

Use:

```bash
atlas restore inspect <archive>
atlas restore verify <archive>
```

before considering live restore.

### 11.3 Isolated restore preparation

Use:

```bash
atlas restore stage <archive>
atlas restore validate-stage <staging-root>
atlas restore plan <staging-root>
```

to prepare and validate recovery outside live state.

### 11.4 Live restore

Live restore requires explicit authorization:

```bash
atlas restore apply <staging-root> --confirm-live
```

Production apply additionally requires:

- clean `main` exactly equal to `origin/main`;
- a verified deployment baseline;
- validated staged recovery state;
- ownership of the shared deployment/update lock;
- exact operator confirmation.

A live restore coordinates maintenance isolation, a fresh pre-restore recovery
point, writer quiescence, bounded state replacement, consumer validation,
writer recovery, Atlas/module/ingress verification, public reopen, and final
lock release.

### 11.5 Interrupted restore

If a restore fails after live mutation begins, do not manually remove
maintenance or the shared lock.

After diagnosis, the supported explicit recovery paths are:

```bash
atlas restore resume <restore-id> --confirm-live
atlas restore abort <restore-id> --confirm-live
```

Use `resume` to revalidate and complete the applied restore.

Use `abort` to transactionally restore displaced pre-apply state and recover the
platform through the defined safety boundary.

### 11.6 Recovery scope limitation

Atlas state-complete backup does **not** mean complete host or media-stack
disaster recovery.

Atlas recovery archives do not include the Media library and do not claim
complete recovery of Jellyfin, Radarr, Sonarr, qBittorrent, or other
third-party application databases.

The current local backup location shares the host/storage failure domain.
Recovery archives that must survive host loss require an independently
protected storage domain.

Until the dedicated v1.0 Backup/Restore Guide is certified, use
`docs/04-backup-restore.md`, `docs/architecture/BACKUP_RECOVERY.md`, and
ADR 0023 as the authoritative restore references.

---

## 12. Rollback and Recovery

Deployment rollback and Atlas state restore are different operations.

Deployment rollback must use captured deployment evidence, including the prior
Git commit, Compose inputs, exact container image identities, and associated
backup artifact.

Do not reconstruct rollback from mutable tags such as `latest`.

Rollback is not successful merely because containers recreate. The required
health, verification, runtime, and ingress checks must pass.

If safe rollback cannot be established, keep production isolated and follow the
explicit recovery procedure rather than improvising a destructive rollback.

Until the dedicated v1.0 Rollback Guide is certified, use
`docs/architecture/DEPLOYMENT_SAFETY.md`,
`docs/operations/RELEASE_PROMOTION.md`, and ADR 0022.

---

## 13. Security Administration

### 13.1 Authentication and authorization

Authentication configuration is a production startup requirement.

Missing or invalid authentication configuration must fail closed.

Authentication establishes identity; it does not grant authorization.
Authorization remains permission based and deny by default.

### 13.2 Secrets

Secrets are external runtime state.

Never:

- commit `.env` or other secret-bearing runtime files;
- print secret values in diagnostics;
- place credentials in documentation;
- retain plaintext invitation tokens in logs;
- expose passwords, bearer tokens, refresh tokens, JWT signing secrets, API
  keys, or webhook URLs in audit output.

Diagnostics may report presence, ownership, or policy compliance without
reporting secret values.

### 13.3 Public ingress

Caddy is the intended Internet-facing Atlas boundary.

Portal and API backends remain internal to the ingress network. Public API
documentation/schema endpoints must remain disabled or explicitly protected in
production.

### 13.4 Least privilege

Treat host ports, Linux capabilities, Docker API access, writable mounts,
container users, and privilege flags as security capabilities.

Do not add a privileged capability merely to work around an ownership or
deployment problem.

---

## 14. Provider and Failure Behavior

Atlas deliberately distinguishes an unavailable provider from an authoritative
empty result.

Administrators should expect explicit unavailable/error states when a provider
cannot satisfy a request.

Do not reinterpret a provider outage as successful empty state.

Where a mutation outcome is ambiguous, Atlas may require reconciliation and
block automatic replay. Follow the explicit reconciliation guidance rather than
blindly retrying a mutation.

User-facing Portal errors should remain actionable. Some safe read failures
offer retry controls; reconciliation-required mutation failures may explicitly
instruct the user not to retry.

---

## 15. Service Lifecycle Administration

The v1.0 Service Lifecycle Portal/API contract is primarily observational.

Administrators can inspect:

- managed-service inventory;
- runtime state;
- health;
- aggregate summary;
- update availability;
- maintenance history.

The Portal's generic Service Lifecycle surface does not authorize restart,
update, rollback, start, or stop mutations.

Do not infer that a visible update-available state means the Portal may apply
the update.

Production mutation continues to use the certified deployment/release boundary.

---

## 16. Incident Response

When unexpected behavior occurs:

1. stop nonessential changes;
2. identify whether a deployment/restore transaction owns maintenance or the
   shared lock;
3. run applicable read-only health and verification commands;
4. inspect service, Scheduler, Operations, storage, VPN, and ingress evidence;
5. preserve failed transaction and audit evidence;
6. determine whether the problem is observational, provider-specific,
   deployment-related, or recovery-related;
7. follow the specialized recovery path;
8. verify the resulting runtime before reopening user traffic;
9. document the incident and any permanent remediation.

Representative first checks:

```bash
atlas maintenance status
atlas doctor
atlas verify
atlas health
atlas operations latest
atlas scheduler history --limit 10
git status --short
```

Use container or provider logs only as needed after the Atlas-owned evidence
surface is understood.

Do not rewrite failed transaction history as success after a later recovery.

---

## 17. Storage and VPN Failures

### 17.1 Storage

Storage exhaustion is a fail-closed condition.

If Atlas reports storage pressure or an `ENOSPC`-class failure:

- stop optional mutations;
- preserve the last durable state;
- inspect storage capacity and affected persistence surfaces;
- do not delete recovery/audit evidence merely to make a write succeed;
- follow the storage-exhaustion architecture and troubleshooting procedure.

### 17.2 VPN

VPN-dependent traffic must remain fail closed when VPN safety cannot be
established.

Do not bypass the VPN boundary by reconfiguring a dependent service to use
ordinary host egress as an emergency shortcut.

---

## 18. Maintenance Window Planning

Production changes should occur in planned, tested maintenance windows.

Window size depends on the operation and validation cost.

Controlled v1.0 restore evidence reached writer restart in roughly 69 seconds
on the tested single-host topology, but that result is **not an SLO**.

For the current small single-host recovery topology, reserve at least
**5–10 minutes** for a restore-oriented maintenance window and increase the
allowance as state size or validation cost grows.

Upgrade, migration, rollback, or security work may require longer windows.

Never size a maintenance window so narrowly that required validation would have
to be skipped to meet the schedule.

---

## 19. Administrator Session Completion

Before declaring planned maintenance complete, confirm the applicable items:

- [ ] expected production source is running;
- [ ] required deployment or restore transaction reached its terminal state;
- [ ] `atlas doctor` passes;
- [ ] `atlas verify` passes;
- [ ] affected runtime checks pass;
- [ ] ingress verification passes when applicable;
- [ ] public Portal/API traffic is intentionally open;
- [ ] maintenance mode is disabled only when safe;
- [ ] shared deployment/restore lock is released only by the owning transaction;
- [ ] backup/recovery evidence is preserved;
- [ ] failed transaction evidence remains immutable;
- [ ] repository state is understood;
- [ ] documentation is updated when behavior or procedure changed.

A command returning successfully is not, by itself, proof that the platform is
operational.

---

## 20. Documentation Ownership

This Administrator Guide is an entry point. It intentionally avoids duplicating
all specialized procedure details.

During the v1.0 documentation consolidation, the canonical guide set is:

```text
docs/guides/ADMINISTRATOR_GUIDE.md
docs/guides/USER_GUIDE.md
docs/guides/INSTALLATION_GUIDE.md
docs/guides/UPGRADE_GUIDE.md
docs/guides/ROLLBACK_GUIDE.md
docs/guides/BACKUP_RESTORE_GUIDE.md
docs/guides/TROUBLESHOOTING_GUIDE.md
```

Until each specialized guide is individually certified, use the existing
architecture, ADR, release, and operations sources listed below.

---

## 21. Authoritative References

### Architecture and decisions

- `../architecture/README.md`
- `../architecture/DEPLOYMENT_SAFETY.md`
- `../architecture/BACKUP_RECOVERY.md`
- `../architecture/SECURITY.md`
- `../architecture/SERVICE_LIFECYCLE.md`
- `../architecture/STARTUP_POLICY.md`
- `../architecture/RESTART_RECOVERY.md`
- `../architecture/SCHEDULER_RECOVERY.md`
- `../architecture/STALE_STATE_RECOVERY.md`
- `../architecture/STORAGE_EXHAUSTION.md`
- `../architecture/VPN_FAIL_CLOSED.md`
- `../architecture/UNAVAILABLE_PROVIDER_BEHAVIOR.md`
- `../ADR/0021-unavailable-provider-failure-semantics.md`
- `../ADR/0022-production-deployment-safety-boundaries.md`
- `../ADR/0023-backup-restore-recovery-boundaries.md`
- `../ADR/0024-security-trust-boundaries.md`

### Operations and release

- `../OPERATIONS.md`
- `../04-backup-restore.md`
- `../operations/RELEASE_PROMOTION.md`
- `../releases/RELEASE_CHECKLIST.md`
- `../releases/USER_ACCEPTANCE.md`
- `../releases/V1_RELEASE_PLAN.md`
- `../governance/RELEASE_POLICY.md`

### Repository-wide source of truth

- `../../README.md`
- `../../ROADMAP.md`
- `../../CHANGELOG.md`

When documents disagree, use the newest certified architecture, ADR, production
acceptance evidence, and release policy rather than preserving obsolete
operator prose.
