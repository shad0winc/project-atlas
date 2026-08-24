# Project Atlas Troubleshooting Guide

**Document Status:** D.3G v1.0 Documentation Candidate
**Applies To:** Project Atlas v1.0 troubleshooting and incident diagnosis
**Audience:** Project Atlas administrators and maintainers
**Canonical Repository Path:** `docs/guides/TROUBLESHOOTING_GUIDE.md`

---

## 1. Purpose

This guide defines the supported Project Atlas v1.0 troubleshooting approach.

Troubleshooting in Atlas is evidence-first and fail-closed.

The goal is not to make a red indicator turn green as quickly as possible. The
goal is to determine what failed, preserve the relevant evidence, avoid widening
the failure, and recover through the correct supported boundary.

Do not use destructive mutation as a diagnostic shortcut.

---

## 2. Troubleshooting Principles

Use these rules for every incident:

1. Observe before changing.
2. Preserve the current failure evidence.
3. Identify whether a deployment, rollback, or restore transaction owns
   maintenance or the shared mutation lock.
4. Distinguish application failure from provider failure.
5. Distinguish authoritative empty state from unavailable state.
6. Prefer Atlas-owned diagnostics before lower-level manual intervention.
7. Avoid unrelated changes while diagnosing.
8. Do not bypass security, VPN, storage, lock, or maintenance boundaries.
9. Do not blindly retry a mutation with an ambiguous provider outcome.
10. Verify recovery with Atlas-owned health and ingress checks.

---

## 3. First Response Checklist

Start with read-only observation:

```bash
atlas maintenance status
atlas doctor
atlas verify
atlas health
atlas operations latest
atlas scheduler history --limit 10
atlas git
```

Also inspect:

```bash
git status --short
git branch --show-current
git log -1 --oneline
```

Use service/container logs only after the Atlas-owned evidence surface is
understood.

---

## 4. Identify the Failure Class

Classify the problem before changing anything.

Common categories include:

- Portal/API unavailable;
- provider unavailable;
- authentication failure;
- authorization failure;
- container unhealthy;
- service startup/readiness failure;
- Scheduler failure;
- VPN failure;
- storage pressure or `ENOSPC`;
- Media request ambiguity;
- Sports provider/recording failure;
- failed deployment;
- failed rollback;
- interrupted restore;
- stale or inconsistent operational state.

The correct recovery path depends on the class.

---

## 5. Portal or API Unavailable

If the Portal or API is unavailable:

1. check maintenance state;
2. check Caddy health;
3. check Portal/API container health;
4. run Atlas Doctor and Verify;
5. determine whether the outage is intentional maintenance or runtime failure.

During intentional maintenance, public Portal/API traffic may return HTTP 503
while Caddy and backends remain healthy.

Do not disable maintenance merely because users cannot access the Portal.

If maintenance is not active, continue through ingress and backend diagnosis.

---

## 6. Distinguish Maintenance from Failure

Maintenance is intentional public isolation.

Expected maintenance behavior includes:

- Caddy healthy;
- required backends healthy;
- public Portal/API traffic isolated with HTTP 503;
- maintenance state observable.

Unexpected behavior includes:

- dead Caddy;
- unhealthy required backend;
- maintenance state inconsistent with transaction ownership;
- public reopen without successful verification.

Do not treat expected HTTP 503 maintenance responses as proof of application
failure.

---

## 7. Provider Unavailable

Atlas deliberately distinguishes provider failure from authoritative empty
results.

If Media, Requests, Favorites, Sports, or another provider-backed surface is
unavailable:

- confirm the provider is reachable;
- inspect the Atlas-visible provider failure;
- do not treat the result as an empty library or empty request history;
- do not authorize deletion or cleanup from unavailable state;
- do not assume durable request/subscription state has been removed.

Provider outage is not equivalent to empty state.

---

## 8. Media Discovery or Search Failure

If Media discovery or search fails:

1. confirm Atlas API health;
2. inspect the Media provider status;
3. confirm provider credentials/configuration without printing secrets;
4. retry only through the normal read-only retry path;
5. verify the returned state distinguishes unavailable from empty.

Do not bypass Atlas by exposing provider credentials to the browser.

---

## 9. Request Provider Failure

If request creation, cancellation, or reconciliation fails, determine whether
the provider outcome is known.

Safe cases:

- the provider clearly rejected the request;
- Atlas clearly reports no mutation occurred;
- the Portal offers an explicit safe retry.

Ambiguous cases:

- network failure after provider submission may have begun;
- timeout after request creation may have reached the provider;
- cancellation result may be unknown.

If Atlas says not to retry, do not retry.

Blind replay can create duplicate or conflicting provider mutations.

---

## 10. Request Reconciliation Required

A reconciliation-required request state means Atlas cannot safely prove the
provider outcome.

Troubleshooting steps:

1. review the Atlas request record;
2. review provider state through the supported administrative boundary;
3. determine whether the provider mutation occurred;
4. reconcile the durable Atlas state using the supported recovery path;
5. preserve the original ambiguous result as evidence.

Do not delete or rewrite the request record merely to remove the error state.

---

## 11. Favorites Unavailable

If Favorites cannot load:

- verify the relevant Atlas API/provider/state path;
- distinguish unavailable from a valid empty Favorites list;
- inspect storage/state availability;
- retry only when the Portal or operator workflow indicates it is safe.

Do not assume Favorites were deleted because the provider/state read failed.

---

## 12. Sports Unavailable

If Sports is unavailable:

1. inspect Sports controller/provider health;
2. inspect shared Scheduler health;
3. inspect Sports storage/runtime ownership;
4. inspect recorder recovery state where relevant;
5. verify that retained subscriptions/recordings remain intact.

Provider failure must not silently erase Sports durable state.

---

## 13. Sports Recorder Recovery

Sports recorder recovery is ownership-sensitive.

PID liveness alone is not proof that a process belongs to Atlas.

Atlas uses PID plus process start-time identity before adopting or signaling an
existing recorder.

If ownership cannot be established:

- fail closed;
- do not signal the ambiguous process;
- do not adopt it as an Atlas recorder;
- inspect the recorded process identity and recovery evidence.

---

## 14. Authentication Failure

If sign-in fails unexpectedly:

- confirm the API is healthy;
- confirm authentication configuration is present;
- confirm the JWT signing secret is supplied to the intended service without
  exposing its value;
- inspect account active/deleted/role state;
- confirm browser credentials/session behavior;
- confirm the Portal is reaching the intended public ingress.

Missing or invalid authentication configuration must fail closed.

Do not print secrets to diagnose authentication.

---

## 15. Authorization Failure

Authentication and authorization are separate.

If a signed-in user receives a permission error:

- confirm the user identity;
- confirm the account is active;
- confirm the role/permissions;
- confirm the API route requires the intended permission;
- verify no backend bypass is being used.

Do not grant broad administrator access simply to remove a permission error.

---

## 16. Container Unhealthy

When a container is unhealthy:

1. run `atlas doctor`;
2. run `atlas verify`;
3. inspect the specific service health;
4. inspect recent logs;
5. verify declared dependencies;
6. verify persistent storage ownership;
7. verify required secrets/configuration.

Do not restart repeatedly without understanding the failure.

Repeated restart can destroy useful evidence or worsen state races.

---

## 17. Service Startup Failure

Service startup may fail because the container is running before dependencies
are ready.

Use Atlas startup/readiness evidence to determine whether:

- required dependency is missing;
- dependency is not running;
- readiness condition is not satisfied;
- configuration is invalid;
- writable state is unavailable.

Do not solve dependency failures by removing required startup conditions.

---

## 18. Non-Root Ownership Failure

A source-correct service can fail when persistent filesystem ownership does not
match its runtime identity.

Symptoms include:

- permission denied;
- failure to create state files;
- repeated unhealthy restart;
- inability to persist logs or runtime state.

Fix the exact ownership/mode required by the service.

Do not:

- make the service privileged;
- use `chmod -R 777`;
- recursively chown unrelated storage.

---

## 19. Scheduler Failure

If Scheduler work is not running:

```bash
atlas scheduler list
atlas scheduler history
```

Inspect the expected state of:

```text
atlas-scheduler.timer
atlas-scheduler.service
```

Production uses one shared `TaskScheduler`; the systemd timer only provides
dispatch opportunities.

A failed one-shot service invocation is a Scheduler execution signal.

Do not create a second scheduler daemon as a workaround.

---

## 20. Scheduler Lock Failure

If Scheduler execution reports a runtime lock conflict:

- identify the current lock owner;
- determine whether another dispatcher invocation is active;
- inspect transaction/runtime evidence;
- wait for legitimate ownership to clear when appropriate.

Do not delete Scheduler lock state manually unless a certified recovery
procedure explicitly authorizes it.

Lock ambiguity fails closed.

---

## 21. Operations Data Missing or Stale

If Operations data looks stale:

- use `atlas operations report` for a current read-only observation;
- use `atlas operations latest` to inspect the latest persisted report;
- inspect Scheduler history for the scheduled collection task;
- verify the Operations persistence path is writable.

Do not edit historical Operations snapshots manually.

---

## 22. Storage Pressure

If storage is approaching exhaustion:

- review capacity;
- identify high-growth surfaces;
- stop optional writes before exhaustion;
- preserve backup/audit/recovery evidence;
- plan capacity expansion or controlled cleanup.

Do not wait for `ENOSPC` during a deployment or restore.

---

## 23. ENOSPC / Storage Exhaustion

Storage exhaustion is fail-closed.

When an `ENOSPC`-class failure occurs:

1. stop optional mutation;
2. preserve last durable state;
3. inspect the affected filesystem;
4. preserve audit and recovery evidence;
5. add/free space through a controlled procedure;
6. revalidate affected persistence;
7. resume only through the correct transaction boundary.

Do not delete the only valid recovery artifact to make another write succeed.

---

## 24. VPN Failure

VPN-dependent traffic must remain fail closed.

If the VPN boundary is unhealthy:

- verify the VPN container/service;
- verify qBittorrent/dependent routing;
- verify no fallback host egress was introduced;
- inspect provider/indexer connectivity through the intended route.

Do not bypass the VPN by moving a dependent service to ordinary host networking.

---

## 25. Public Ingress Failure

If the public Portal/API is unreachable:

- verify DNS/network reachability as applicable;
- verify Caddy health;
- verify internal Portal/API reachability;
- verify the expected Caddy routing;
- inspect security headers and public route behavior;
- determine whether maintenance is active.

Do not expose internal backend ports publicly as a workaround.

---

## 26. API Documentation Exposure

Production API documentation/schema endpoints must remain disabled or protected.

If `/api/docs` or `/api/openapi.json` becomes publicly reachable unexpectedly:

- treat it as a security regression;
- restore the intended ingress/API protection;
- verify public access is blocked;
- review whether the change came from configuration drift or deployment.

Do not accept accidental documentation exposure as harmless.

---

## 27. Security Header Regression

If browser security headers disappear:

- inspect Caddy configuration;
- verify the current public ingress image/config;
- restore the certified policy;
- retest the public Portal response.

Security controls include Content Security Policy and other browser hardening
defined by the current security architecture.

Do not disable headers simply to work around a Portal rendering problem.

---

## 28. Secret Permission Failure

If secret-bearing files have overly broad permissions:

- identify the affected file;
- confirm the service owner;
- restore the intended restrictive mode/ownership;
- verify the service still starts;
- verify no secret value was exposed in logs/evidence.

Do not copy secret values into troubleshooting notes.

---

## 29. Failed Upgrade

If an upgrade fails:

- keep or re-establish maintenance isolation;
- preserve the failed deployment record;
- preserve the previous verified baseline;
- preserve rollback references and backup identity;
- determine whether rollback or forward recovery is appropriate.

Do not relabel the failed deployment as success.

Use the Upgrade and Rollback Guides for the recovery transaction.

---

## 30. Failed Rollback

If rollback fails:

- retain maintenance;
- retain shared mutation ownership;
- preserve failed rollback evidence;
- keep the previous verified baseline authoritative;
- determine whether forward recovery or state restore is required.

Do not stack unrelated mutations on top of a failed rollback.

---

## 31. Interrupted Restore

If a live restore fails after mutation begins:

- retain maintenance;
- retain the shared lock;
- preserve restore transaction evidence;
- do not manually copy archive content;
- choose supported resume or abort after diagnosis.

Supported recovery actions are:

```bash
atlas restore resume <restore-id> --confirm-live
atlas restore abort <restore-id> --confirm-live
```

Do not bypass these boundaries with manual state replacement.

---

## 32. Restore Verification Failure

If restore apply completes but verification fails:

- restore is not successful;
- keep public traffic isolated;
- inspect consumer validation;
- inspect writer recovery;
- inspect Atlas Doctor/Verify;
- inspect affected providers/modules;
- use resume or abort based on the transaction state.

Command success is not recovery success.

---

## 33. Maintenance Will Not Clear

If maintenance remains active after a failed change, first determine whether a
deployment/rollback/restore transaction intentionally owns it.

Do not disable maintenance just to restore user access.

Maintenance may be intentionally retained because:

- post-change verification failed;
- rollback failed;
- restore recovery is incomplete;
- public ingress failed after reopen.

Resolve the owning transaction first.

---

## 34. Deployment Lock Will Not Clear

If the shared deployment/restore lock remains held:

- identify the owning transaction;
- inspect its current state;
- determine whether it is active, failed, interrupted, or recoverable;
- use the documented recovery path.

Do not manually delete the lock merely because it appears stale.

---

## 35. Provider Empty vs Unavailable

Use this rule:

```text
successful provider response with zero results
        =
authoritative empty

provider timeout/error/unreachable state
        =
unavailable
```

Never convert unavailable into empty.

This distinction protects users, retained state, automation, and cleanup logic.

---

## 36. Logs and Evidence

Collect only the logs needed for the incident.

Preserve:

- transaction IDs;
- timestamps;
- service health;
- relevant error messages;
- branch/commit state;
- provider failure type;
- Scheduler history;
- storage state;
- maintenance/lock state.

Do not include credentials or secrets in support evidence.

---

## 37. Git State Problems

If repository state is unexpected:

```bash
git status --short
git branch --show-current
git log -1 --oneline
```

Do not reset, clean, checkout, or rewrite the repository until you understand
whether the current state is needed as deployment or incident evidence.

For production operations, clean synchronized source requirements must be
respected.

---

## 38. Diagnostic Command Failure

If an Atlas diagnostic command fails:

- capture the exact command and exit status;
- preserve stderr;
- determine whether the failure is a normal fail-closed result or a tooling
  defect;
- inspect the underlying service only as needed.

Do not assume a nonzero diagnostic exit means the diagnostic itself is broken.

---

## 39. When to Escalate

Escalate from diagnosis to controlled recovery when:

- the failure requires production mutation;
- a deployment transaction is failed;
- rollback is required;
- authoritative Atlas state is damaged;
- restore is interrupted;
- security controls are violated;
- storage failure threatens durability;
- provider mutation outcome is ambiguous.

Use the specialized guide for the required mutation.

---

## 40. Troubleshooting Completion Checklist

Before closing an incident:

- [ ] Failure class identified.
- [ ] Relevant evidence preserved.
- [ ] Maintenance/lock ownership understood.
- [ ] Root cause or bounded recovery cause identified.
- [ ] No unsupported workaround left in production.
- [ ] `atlas doctor` passes where applicable.
- [ ] `atlas verify` passes where applicable.
- [ ] Provider/module checks pass where applicable.
- [ ] Scheduler health is understood.
- [ ] Storage health is understood.
- [ ] Public ingress is intentionally open or intentionally isolated.
- [ ] Failed transaction history remains immutable.
- [ ] Secrets were not exposed.
- [ ] Recovery outcome documented.

---

## 41. What Must Not Be Done

Do not:

- repeatedly restart services without diagnosis;
- convert provider failure into empty state;
- blindly replay ambiguous request mutations;
- delete request/recovery records to hide errors;
- disable maintenance before transaction recovery is complete;
- manually delete deployment/restore locks;
- create a second Scheduler;
- bypass VPN fail-closed routing;
- expose backend ports publicly as a workaround;
- chmod runtime state world-writable;
- make containers privileged to solve ownership problems;
- prune rollback images during recovery;
- extract unvalidated backup content into live state;
- delete the only valid backup to free space;
- print or copy secrets into diagnostic evidence;
- rewrite failed transaction history as success.

---

## 42. Relationship to the Administrator Guide

The Administrator Guide provides the general operating model and routine
health-review workflow.

This Troubleshooting Guide owns symptom-driven diagnosis and safe escalation.

---

## 43. Relationship to Upgrade and Rollback

Use the Upgrade Guide for planned production change.

Use the Rollback Guide when a failed deployment must return to a previous
known-good runtime.

Troubleshooting determines which path is appropriate but does not replace those
transactions.

---

## 44. Relationship to Backup/Restore

Use the Backup/Restore Guide when authoritative Atlas state must be recovered
from a validated archive.

Troubleshooting may identify the need for restore, but live restore must use its
own staged, locked, maintenance-protected transaction.

---

## 45. Legacy Troubleshooting Guidance

Older Atlas operations documentation may reduce troubleshooting to:

```text
atlas doctor
atlas verify
atlas ari report
atlas git
```

Those commands remain useful, but they are not a complete v1.0 troubleshooting
procedure.

The current troubleshooting model additionally requires:

- failure classification;
- maintenance/lock ownership checks;
- provider empty-vs-unavailable distinction;
- mutation ambiguity handling;
- Scheduler and storage fail-closed behavior;
- deployment/rollback/restore boundaries;
- security and VPN boundaries;
- evidence preservation;
- health-based recovery acceptance.

Do not use the legacy shorthand as the sole incident-response procedure.

---

## 46. Authoritative References

Primary references:

- `ADMINISTRATOR_GUIDE.md`
- `UPGRADE_GUIDE.md`
- `ROLLBACK_GUIDE.md`
- `BACKUP_RESTORE_GUIDE.md`
- `../OPERATIONS.md`
- `../architecture/UNAVAILABLE_PROVIDER_BEHAVIOR.md`
- `../architecture/INTERRUPTED_REQUEST_RECOVERY.md`
- `../architecture/RESTART_RECOVERY.md`
- `../architecture/SCHEDULER_RECOVERY.md`
- `../architecture/STALE_STATE_RECOVERY.md`
- `../architecture/STORAGE_EXHAUSTION.md`
- `../architecture/VPN_FAIL_CLOSED.md`
- `../architecture/DEPLOYMENT_SAFETY.md`
- `../architecture/BACKUP_RECOVERY.md`
- `../architecture/SECURITY.md`
- `../architecture/SPORTS_RECOVERY.md`
- `../architecture/STARTUP_POLICY.md`
- `../ADR/0021-unavailable-provider-failure-semantics.md`
- `../ADR/0022-production-deployment-safety-boundaries.md`
- `../ADR/0023-backup-restore-recovery-boundaries.md`
- `../ADR/0024-security-trust-boundaries.md`
- `../releases/RELEASE_CHECKLIST.md`
- `../../ROADMAP.md`

When older operational shorthand conflicts with current certified architecture
or recovery behavior, use the newer certified contract.
