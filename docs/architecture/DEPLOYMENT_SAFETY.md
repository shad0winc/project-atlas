# Production Deployment Safety Architecture

## Purpose

This document defines the v1.0 production change-control architecture for
Project Atlas. It describes how tested source reaches production, how users are
protected during maintenance, how pre-change recovery evidence is captured,
and how Atlas decides whether to reopen traffic after an update or rollback.

## Safety Invariant

> Production changes must originate from an explicitly approved and tested
> release state, preserve a verified recovery boundary before mutation, remain
> observable during maintenance, and return user traffic only after post-change
> verification succeeds.

## Discovered Production Topology

At discovery commit `7f82bc8d`:

- `main` and `origin/main` resolve to `791436c7`;
- v1.0 development HEAD is on `feature/public-ingress`;
- `main` is an ancestor of the active development branch;
- Caddy, Atlas API, and Atlas Portal run as the `atlas-ingress` Compose project;
- Caddy owns ports 80 and 443 and routes `/api/*` to `atlas-api:8000` and all
  other public traffic to `atlas-portal:3000`;
- Caddy configuration is a read-only bind mount from `infra/caddy`;
- Caddy data, config, and logs use writable Atlas-managed storage; and
- the current Caddy Docker healthcheck reaches the public API health route.

A historical annotated `v1.0.0` tag previously resolved to `a67bb8a5`
(`feat: add ARI recommendation engine`, 2026-07-09). Release forensics confirmed
that the tag predated the current release-readiness work and was not valid v1.0
certification evidence. The project owner has since reconciled and removed that
invalid tag locally and from `origin` while preserving the underlying commit in
Git history.

## Branch and Release Model

| Surface | Purpose | Production deployment |
| --- | --- | --- |
| `main` | Stable production source | Allowed after required gates |
| `feature/*` / `fix/*` / `docs/*` | Focused development | Not directly allowed |
| `release/<version>` | Frozen certification/stabilization | Validation surface; promoted to `main` before normal production deployment |
| annotated release tag | Certified immutable release identity | Must point to the certified release commit |

Atlas intentionally does not require a permanent `develop` branch. Focused
branches provide background-development isolation with less merge ceremony.

### Promotion flow

```text
focused development
       |
       v
release/<version>  -- certification + release-only fixes
       |
       v
     main          -- production-stable source
       |
       v
certified tag      -- immutable release identity
```

A production runtime change still requires an explicit maintenance/deployment
operation after source promotion.

## Legacy Release-Tag Reconciliation

A historical annotated `v1.0.0` tag previously pointed to an earlier
development commit and could not certify the eventual v1.0 release. Independent
forensics established that the tag claimed `v1.0.0` while the tagged commit
contained repository `VERSION` `0.9.0`.

The project owner explicitly reconciled the mismatch during release
preparation. The invalid tag is now absent locally and from `origin`; its
underlying commit remains preserved in normal Git history.

This reconciliation removes the legacy tag mismatch as a release blocker, but
it does not satisfy the later release gates. Automation and operators must
still require the normal release-candidate, promotion, production-validation,
pilot, stabilization, freeze, final-certification, and publication evidence.
The eventual final `v1.0.0` tag must point to the exact certified final-release
commit.

## Maintenance Mode

### Ownership

Caddy owns the maintenance boundary. It is the only deployed component upstream
of both the Portal and API, so it can protect users even when those application
containers are restarting or unavailable.

### State

Maintenance state lives under Atlas runtime configuration, for example:

```text
/mnt/storage/configs/atlas/maintenance/enabled
```

The final implementation owns the exact path through Atlas configuration. Caddy
receives that state through a read-only mount. The Portal/API do not own the
flag and tracked Caddy files are never rewritten to toggle runtime state.

The CLI exposes only explicit operations:

```text
atlas maintenance status
atlas maintenance enable
atlas maintenance disable
```

Enable/disable operations are idempotent. Status is read-only.

### HTTP behavior

While enabled, normal public requests receive HTTP 503 Service Unavailable and
a bounded maintenance response. A `Retry-After` header should be supplied where
practical.

Maintenance must cover both Portal and API user traffic. It must not rely on
either application being healthy enough to render the maintenance response.

### Ingress liveness

Caddy requires a liveness route that bypasses maintenance mode. Docker must be
able to distinguish:

```text
Caddy is unhealthy
```

from:

```text
Caddy is healthy and intentionally returning maintenance responses
```

The ingress verifier must test both the liveness contract and, when applicable,
the maintenance response contract.

## Deployment Lock

Only one production deployment transaction may be active at a time.

The lock is Atlas runtime state, not a Git file. Acquisition must be atomic.
Lock ownership and stale-lock handling must fail closed when ownership cannot be
established safely.

The lock is released only after the transaction reaches a defined terminal
state. Error cleanup must not disable maintenance merely because the shell
process exits.

## Pre-Update Capture

Before service mutation Atlas captures a deployment manifest containing at
least:

- deployment identifier and timestamps;
- source branch/ref and full Git commit;
- clean/dirty repository result;
- relevant Compose project/config identity;
- pre-update container image IDs/digests;
- backup artifact identity; and
- migration declaration, when applicable.

Mutable tags such as `latest` are not rollback identities. The captured image
identity is authoritative for the previous runtime.

## Pre-Update Backup

The deployment transaction invokes the existing atomic `atlas backup` boundary
and requires a successfully validated canonical archive before continuing.

The deployment record links to that backup artifact.

M-023.25 subsequently certified Format 1 state-complete Atlas backups and the
corresponding live restore transaction for the declared Atlas state surfaces.
Deployment/update and live restore use the same exclusive `update.lock`, so
they cannot simultaneously claim production mutation ownership. A deployment
that changes data outside the declared Atlas recovery surfaces still requires
release-specific compatibility and recovery evidence; state completeness does
not silently widen to media libraries or third-party application databases.

## Apply Phase

The apply phase mutates only the approved deployment scope.

It must not execute `docker image prune` while rollback remains possible.

Root service Compose changes and ingress application changes are separate
deployable surfaces and should be rebuilt/recreated only when the approved
change requires them.

Application builds must come from the approved source commit. Untracked or
dirty source fails the deployment gate.

## Post-Apply Ingress Readiness

A successful deterministic Compose apply is not equivalent to verified ingress
readiness.

For update scopes that recreate ingress services, Atlas performs a bounded,
read-only readiness observation after Compose apply and before authoritative
post-update verification.

The readiness boundary observes `atlas-api`, `atlas-portal`, and `atlas-caddy`.

Success requires both:

- container state `running`; and
- health state `healthy`.

The only transient retry state is `running + starting`.

Atlas fails closed immediately for a missing container, Docker inspection
failure, non-running container, `unhealthy` health state, missing health
contract, or any unexpected health state. Remaining in `running + starting`
beyond the bounded readiness deadline also fails closed.

The readiness phase performs inspection only. It does not restart, stop, start,
recreate, pull, build, invoke Compose, change maintenance state, release the
deployment lock, or modify deployment records.

Readiness does not replace or weaken authoritative verification. Its purpose is
only to distinguish a legitimate bounded health-startup interval from a
terminal verification failure before the existing strict verification gates
run.

## Post-Update Verification

Required validation is selected by the affected surface and includes the
existing Atlas tools rather than a second health system:

- `atlas doctor`;
- `atlas verify`;
- `scripts/verify-ingress.sh` for public ingress changes;
- Docker Compose/container health where relevant; and
- migration-specific assertions when a migration occurred.

All required gates must pass before normal public traffic resumes.

## Failure State

If apply or post-update validation fails:

- maintenance remains enabled;
- the failure is visible and recorded;
- the pre-update manifest and backup remain preserved;
- rollback assets are not pruned; and
- the operator chooses rollback or explicit forward recovery.

Failure is not converted into success because containers happen to be running.

## Post-Restore Rollback Readiness

A successful rollback restore command is not equivalent to verified rollback
readiness.

For rollback scopes that restore ingress services, Atlas performs a bounded,
inspection-only readiness observation after ingress restoration and before
authoritative rollback verification.

The readiness boundary observes `atlas-api`, `atlas-portal`, and `atlas-caddy`.

Success requires container state `running` and health state `healthy`.
The only bounded retry state is `running + starting`.

Missing containers, Docker inspection failure, non-running state, `unhealthy`,
missing health metadata, unexpected health state, and timeout fail closed.

The readiness phase performs inspection only. It does not restart, stop, start,
recreate, pull, build, invoke Compose, change maintenance state, release the
deployment lock, change the current verified baseline, change deployment
status, or modify deployment records.

Authoritative rollback verification remains unchanged and strict.

Readiness occurs before maintenance disable, current-baseline finalization,
`rolled_back` transaction finalization, and final lock release. Failure
therefore preserves the failed transaction, maintenance isolation, lock
ownership, and the previous verified baseline for explicit recovery.

## Rollback

Rollback uses the captured deployment manifest.

It restores the prior approved source/runtime identities and any state recovery
defined by the migration plan. It does not guess at previous versions by
resolving current mutable tags.

After rollback, Atlas reruns the required Doctor, Verify, ingress, and
migration-specific checks. Maintenance is disabled only after those checks
pass.

If rollback is unsafe or incomplete, maintenance stays enabled and the result
becomes an explicit recovery incident.

## Migration Contract

Every production schema or configuration migration has a declaration with:

| Field | Requirement |
| --- | --- |
| Source state | Known and validated |
| Target state | Explicit |
| Compatibility | Documented |
| Reversibility | `reversible`, `forward-recovery`, or `irreversible` |
| Backup | Identified before apply |
| Validation | Deterministic where practical |
| Recovery | Defined before production mutation |

Missing migration evidence blocks deployment.

Irreversible migrations require explicit approval and recovery evidence; they
cannot inherit a generic rollback promise.

## Tested-Release Gate

Deployment Safety uses two complementary gates:

1. repository-hosting CI/branch protection prevents unvalidated source from
   being promoted into the stable production branch; and
2. the production deployment command validates its local branch/ref, commit,
   cleanliness, and approved release state before runtime mutation.

The local deployment gate is required even when CI exists because production
must verify what it is actually about to deploy.

## Implemented `atlas update` Transaction

The canonical `atlas update <core|ingress|all> --migration none` path now
implements the v1.0 deployment transaction. It requires clean synchronized
`main`, an existing verified production baseline, exact runtime identity, an
exclusive deployment lock, an explicit no-migration declaration, maintenance
mode, and a validated pre-update Atlas backup before service mutation.

Before pull or build operations, every image in the previous verified baseline
receives a transaction-scoped `atlas-rollback:` reference. Atlas verifies that
each recovery reference resolves to the exact captured image ID. This prevents
a local Portal or API rebuild from making the prior image unreachable merely
because `atlas-portal:local` or `atlas-api:local` moved to a new image.

Post-change verification is intentionally two-phase:

1. while maintenance is enabled, Atlas verifies container/resource contracts,
   Caddy configuration and liveness, direct Portal/API backend health, and
   HTTP 503 isolation on both public application paths; and
2. after maintenance is disabled, Atlas repeats the affected verification
   against normal public ingress before publishing the candidate deployment as
   the current verified baseline.

If the second phase fails, maintenance is re-enabled, the deployment remains
failed, the previous verified baseline remains current, and the deployment lock
remains held for explicit recovery.

The standalone `scripts/update.sh` delegates to the canonical Atlas CLI and no
longer provides a weaker alternate deployment path. Update paths do not prune
rollback images.

## v1.0 RC Deployment Remediation Contract

The first exact `1.0.0-rc.1` production deployment attempt on 2026-08-24
failed closed and preserved the previous verified production baseline.

The incident established three permanent deployment-safety requirements:

1. **Build-context permission preflight.** Before any first-party ingress pull
   or build, Atlas validates tracked file readability and required parent
   directory traversal for the container-runtime boundary.
2. **Digest-safe rollback aliases.** Rollback restores from transaction-scoped
   `atlas-rollback:` aliases recorded in `rollback-images.tsv` and verifies
   every alias against the exact captured image ID. It does not retag a
   digest-shaped captured reference.
3. **Persistent rollback source lifetime.** Recovery extraction used by
   recreated services must live beneath the persistent deployment transaction
   record at `<deployment-root>/records/<transaction-id>/` and remain available
   after restore returns.

Exactly 17 tracked files whose Git mode was already `100644` but whose checkout
mode had drifted to `0600` were normalized to filesystem `0644` without a Git
content or executable-mode delta.

The failed transaction `update-20260824T165151Z-3258027` remains historical
evidence. Production was recovered to verified baseline
`baseline-reconciliation-20260824T164541Z-927002`.

This remediation certifies the machinery required for a controlled retry. It
does not claim successful exact-RC production deployment and does not close
that Roadmap gate.

## Validation Strategy

Implementation proceeds in bounded stages:

1. maintenance-mode state, Caddy routing, CLI contract, and tests;
2. guarded deployment transaction with backup and post-change verification;
3. rollback capture and deterministic failure/recovery tests;
4. CI/tested-source enforcement; and
5. controlled production validation.

Automated tests use temporary state and mocked/stubbed Docker operations for
failure injection. Production validation begins read-only and only performs a
controlled maintenance/update exercise after explicit approval of the exact
mutation and rollback plan.

## Completion Boundary

M-023.24 is complete only when:

- the production, background-development, and release branch contracts are
  documented;
- maintenance mode protects Portal and API traffic while Caddy remains healthy;
- pre-update backup and rollback capture occur before deployment mutation;
- post-update verification gates user traffic;
- failed deployment/rollback behavior is deterministic and tested;
- migration contracts fail closed when recovery evidence is missing;
- untested source cannot use the canonical production deployment path;
- the premature `v1.0.0` tag is tracked as an unresolved release blocker until
  explicitly reconciled; and
- controlled production validation confirms the deployed contract.

## Implementation Status

M-023.24 is complete.

The first controlled production `atlas update all --migration none` exercise
proved the transaction's fail-closed behavior and exposed two recovery defects
that deterministic pre-production tests had not revealed. The update reached a
healthy new runtime but correctly stayed in maintenance because the public
ingress verifier interpreted the intentional maintenance HTTP 503 response as
an application failure. The subsequent rollback attempt then refused before
mutation because the exact pre-update locally built API image was no longer
available after its mutable `:local` tag moved.

Atlas did not reinterpret either failure as success. The failed transaction
remained recorded, maintenance and the deployment lock remained held, and the
previous verified baseline remained authoritative. After read-only diagnosis,
an explicitly controlled forward recovery verified the healthy runtime,
reopened ingress, established verified baseline
`baseline-20260808T033011Z-2093776`, released the lock, and retained the failed
transaction as audit evidence.

Repair commit `83ff0641` made ingress verification maintenance-aware, added the
second public verification boundary, and preserved exact pre-update images with
durable rollback references. Validation then established:

- 35 focused deployment-recovery tests passed;
- the complete Core regression passed 2,878 tests plus 104 subtests;
- normal production ingress passed 24 of 24 checks before maintenance;
- live maintenance-mode verification passed 27 of 27 checks, including healthy
  Portal/API backends and exact HTTP 503 public isolation;
- reopened public ingress passed 24 of 24 checks;
- all 19 images in the verified production baseline were retained by exact ID
  through temporary rollback references; and
- validation removed its temporary tags and left the verified baseline,
  failed-transaction audit record, repository, maintenance state, and lock
  invariants clean.

The historical premature `v1.0.0` tag has now been explicitly reconciled by the
project owner as part of final v1.0 release preparation. Independent forensics
confirmed that the tag claimed a production v1.0.0 release while its tagged
commit contained repository `VERSION` `0.9.0`; the invalid tag was then removed
locally and from `origin` while preserving the underlying commit in Git history.

That legacy mismatch is no longer a release-certification blocker. Release
candidate creation, protected promotion, production deployment, controlled
pilot, stabilization, candidate freeze, final certification, tagging, and
publication remain separate later release gates.

## E2.5 Migration Recovery Lessons

The first controlled E2.5 Jellyseerr-to-Seerr migration attempt added production
evidence to the deployment-safety contract.

The attempt did not complete successfully. Atlas preserved maintenance mode,
deployment-lock ownership, the previous verified baseline, and the failed
transaction until explicit recovery established a known-safe runtime. Recovery
restored the legacy Jellyseerr service and did not rewrite the failed migration
as a successful deployment.

The recovery also exposed a runtime-ownership dependency outside the primary
migration target: recreating the Sports controller failed because its configured
non-root identity could not write required heartbeat and recording state.

The incident establishes the following permanent deployment rules:

1. **Recovery scope must include required dependent runtime contracts.**
   A service can be correctly defined in source yet still fail recovery when
   persistent writable paths do not match its effective runtime identity.

2. **Non-root runtime ownership is a deployment prerequisite.**
   Install, update, migration, and recovery paths that recreate a non-root
   service must establish and verify ownership of that service's declared
   writable runtime surfaces before health is expected to pass.

3. **Recovery must remain isolated.**
   Recovery of a failed target must not unnecessarily recreate unrelated healthy
   services. Target-artifact selection and Compose operations must remain
   explicitly bounded.

4. **Recovery success is health-based, not command-based.**
   A successful container recreation command is not sufficient. Required
   heartbeat, module verification, Doctor, provider, and affected runtime checks
   must pass before recovery can be finalized.

5. **Failed transaction history is immutable audit evidence.**
   Forward recovery or rollback may establish a new safe state, but it must not
   rewrite the original failed deployment outcome as success.

6. **Maintenance and lock release are terminal actions.**
   They occur only after the recovered production surface passes the required
   verification gates and the transaction reaches its defined terminal state.

These rules extend the existing rollback and forward-recovery architecture; they
do not create a second deployment or lifecycle system.
