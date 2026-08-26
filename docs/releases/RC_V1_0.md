# Project Atlas v1.0.0-rc.1 Release Candidate Record

**Document Status:** Release Candidate Identity Record
**Release Version:** `1.0.0-rc.1`
**Release Type:** Major Release Candidate
**Release Date:** 2026-08-24
**Milestone:** Project Atlas v1.0
**Release Branch:** `release/v1.0.0`
**RC Preparation Branch:** `release/v1.0.0-rc1-prep`
**Certified Source Promotion:** `1545133b1576fea0e8a390aa00fcf0efdd3e7e3d`
**Certified Feature Source:** `8b7a5876e8fb1b2054eab7a67685bc7d0b2e9ea5`
**Candidate Tag:** `v1.0.0-rc.1`
**Release Manager:** Project Atlas project owner

---

# 1. Release Information

| Field | Value |
| --- | --- |
| Release Version | `1.0.0-rc.1` |
| Release Type | Major Release Candidate |
| Release Date | 2026-08-24 |
| Milestone | Project Atlas v1.0 |
| Branch | `release/v1.0.0` |
| Certified Source Promotion | `1545133b1576fea0e8a390aa00fcf0efdd3e7e3d` |
| Certified Feature Source | `8b7a5876e8fb1b2054eab7a67685bc7d0b2e9ea5` |
| Candidate Tag | `v1.0.0-rc.1` |
| Release Manager | Project Atlas project owner |

The original release-record mutation intentionally did not create the immutable
RC tag.

The annotated `v1.0.0-rc.1` tag was subsequently created and verified against
certified `main` commit `0691a2827ade3c2256fd6f57e969c54a3ef1120e`.
Its annotated tag object is
`83e65bd194d3382d848e3ad706596e87fb5a0d3f`.

The later Roadmap-closure merge does not move or redefine that immutable RC
identity.

---

# 2. Executive Summary

Project Atlas `1.0.0-rc.1` is the feature-complete v1 release candidate
prepared for controlled production validation.

The candidate incorporates the certified v1 critical user and administrator
journeys, Media and Sports request surfaces, favorites and retention
protections, Service Lifecycle read surfaces, Scheduler and Runtime Bus
reliability work, sustained-use certification, release documentation, and
release-gate remediation completed before the candidate identity transaction.

This candidate is not the final Project Atlas v1.0.0 release.

Production RC deployment, controlled user pilot, stabilization, pilot-defect
resolution, release freeze, final release notes, final `v1.0.0` tagging,
publication, and stable-support activation remain independent later gates.

---

# 3. Release Scope

## Included

- certified Project Atlas v1 functional scope represented by the promoted
  `release/v1.0.0` tree;
- authenticated Portal critical journeys;
- Media discovery and request workflows;
- Sports discovery and request workflows;
- favorites and protected-media behavior;
- Service Lifecycle read and administrator surfaces;
- Scheduler production dispatch and recovery contracts;
- Runtime Bus and Notifications convergence protections;
- sustained-use lifecycle and 48-hour certification evidence;
- installation, upgrade, rollback, backup/restore, troubleshooting,
  architecture, operations, and known-limitations documentation;
- release-gate contract remediation required before protected release
  promotion.

## Explicitly Excluded

- post-v1 feature development;
- new unrelated capability during RC stabilization;
- final `v1.0.0` publication;
- stable-support declaration before final certification;
- claims that the exact `1.0.0-rc.1` runtime has already completed its
  production pilot.

---

# 4. New Features

| Feature | Description | Notes |
| --- | --- | --- |
| Media discovery and Requests | Atlas-owned Media discovery and request workflows through authenticated API and Portal boundaries | Includes bounded provider routing and request identity |
| Sports Requests | Authenticated Sports discovery and request workflow | Preserves Atlas-owned user/subscription identity |
| Sustained-use certification | Fixed-cadence 48-hour / 193-sample certification lifecycle | Includes bounded terminal Runtime Bus convergence |
| Administrator release surfaces | Certified administrator critical journey and Service Lifecycle visibility | Mutation controls remain governed by supported lifecycle boundaries |
| Release documentation suite | Canonical v1 installation, operations, upgrade, rollback, backup/restore, troubleshooting, architecture, and limitations documentation | Documentation gates completed before RC creation |

---

# 5. Improvements

| Area | Improvement | Notes |
| --- | --- | --- |
| Scheduler | Production dispatcher and sustained-use scheduling corrections | Release-blocking dispatcher defect closed |
| Runtime Bus | Restored Notifications delivery and bounded terminal convergence | Terminal target remains fixed after final sample |
| Portal | Accessibility, responsiveness, formatting, and critical-browser certification | Certified release-gate surfaces pass |
| Release engineering | Protected branch promotion, release contracts, immutable evidence boundaries, and tag reconciliation | Historical premature `v1.0.0` tag removed before RC creation |

---

# 6. Bug Fixes

| Issue | Resolution | Notes |
| --- | --- | --- |
| Historical premature `v1.0.0` tag | Invalid tag removed locally and remotely while preserving underlying Git history | Final `v1.0.0` namespace remains available |
| Release-gate Core contract drift | Test reconciled to the completed historical-tag remediation | Production behavior unchanged |
| API CI audit fixture | Media Catalog authentication test now uses an isolated pre-existing audit journal | Production fail-closed audit contract preserved |
| Sustained-use cadence drift | Sampling anchored to fixed T0-derived cadence | No certification backfill |
| Runtime Bus terminal race | Finalization uses bounded convergence against frozen sample-193 journal target | Post-target growth does not move certification target |

---

# 7. Breaking Changes

None identified for the supported v1 RC workflow.

The candidate does not intentionally introduce an unsupported migration or
compatibility break relative to the certified v1 release-readiness boundary.

---

# 8. Known Limitations

The canonical accepted v1 limitations are maintained in
[`KNOWN_LIMITATIONS.md`](KNOWN_LIMITATIONS.md).

Accepted limitations do not waive release-blocking security, data-integrity,
recovery, or supported-contract failures.

Production RC deployment may identify additional candidate defects. Any such
defect must be classified through the normal release policy before final
v1.0.0 certification.

---

# 9. Upgrade Notes

Before deploying this release candidate:

1. follow the canonical installation and upgrade documentation;
2. create the required Atlas backup/recovery checkpoint;
3. use maintenance mode where the documented procedure requires it;
4. preserve immutable rollback identity;
5. deploy only from the approved protected source;
6. run the required post-deployment health, verification, provider, module,
   and ingress checks;
7. do not resume normal public traffic until all required validation passes.

No final-release status should be inferred solely from the presence of the RC
version or tag.

---

# RC Production Deployment Attempt and Safety Remediation

## Current Runtime Status — EXACT RC PRODUCTION DEPLOYMENT VERIFIED

The immutable release-candidate identity remains `1.0.0-rc.1`.

Two controlled production attempts are now preserved as release evidence.

### First controlled attempt

Transaction:

`update-20260824T165151Z-3258027`

Result:

- failed closed;
- production recovery completed;
- transaction remains immutable historical evidence; and
- deployment-safety remediation for build-context permission safety,
  digest-safe rollback aliases, and persistent recovery-source lifetime was
  certified.

### Second controlled attempt

Transaction:

`update-20260824T222351Z-3794932`

Result:

- deterministic Compose apply completed;
- immediate strict ingress verification encountered the legitimate transitional
  health state `running + starting`;
- the transaction failed closed;
- maintenance remained enabled;
- deployment-lock ownership remained preserved; and
- the previous verified baseline remained authoritative.

Root cause:

`POST_APPLY_READINESS_RACE`

The authoritative verifier was not weakened.

A bounded, read-only ingress readiness phase has now been implemented and
certified between deterministic Compose apply and strict post-update
verification for `ingress` and `all` update scopes.

Readiness requires `running + healthy` for success and permits only
`running + starting` as a bounded transient state.

Engineering certification:

- Full Core: 3,456 tests passed
- Core subtests: 104 passed
- Canonical Sports: PASS
- Legacy Sports: PASS
- readiness remediation: CERTIFIED

The authoritative production baseline remains:

`baseline-reconciliation-20260824T164541Z-927002`

The controlled exact `1.0.0-rc.1` production retry subsequently completed
successfully as transaction `update-20260825T232236Z-1274121` with status
`verified`.

The authoritative post-deployment baseline is
`baseline-20260825T232627Z-1296276` with status `verified`. The production
runtime is stable at 22 running containers, zero unhealthy, and zero
restarting. Strict ingress verification passes, the deployment lock is absent,
and maintenance mode is disabled.

The ingress-readiness and rollback-readiness remediations are production-proven.
No further RC redeployment is required. Final `v1.0.0` release authorization
remains a separate release gate.


### Subsequent rollback-readiness remediation

Recovery of failed transaction `update-20260824T222351Z-3794932` exposed the distinct
`POST_RESTORE_ROLLBACK_READINESS_RACE` after the update-side
`POST_APPLY_READINESS_RACE` had already been remediated.

The restored production runtime subsequently settled to healthy state, but
rollback finalization did not complete. Therefore:

- transaction `update-20260824T222351Z-3794932` remains `failed`;
- authoritative baseline `baseline-reconciliation-20260824T164541Z-927002` remains verified and current;
- maintenance remains enabled;
- deployment-lock ownership remains with the failed transaction;
- runtime remains 22 running, zero unhealthy, zero restarting; and
- strict live ingress is 29/29 PASS.

A bounded, inspection-only post-restore rollback-readiness phase has now been
implemented and engineering-certified. The strict ingress verifier remains
unchanged.

Current engineering certification:

- focused rollback readiness: 6 passed;
- deployment recovery: 30 passed;
- update transaction: 25 passed;
- release gate: 18 passed;
- Full Core: 3,467 tests passed;
- Core subtests: 104 passed;
- Canonical Sports: PASS;
- `atlas test sports`: PASS;
- strict live ingress: 29/29 PASS.

The earlier Full Core: 3,456 tests passed certification remains valid historical
evidence for the separate update-side post-apply remediation.

This record does **not** authorize rollback rerun or controlled exact-RC retry
#3 and does not close the `Deploy release candidate to production` gate.

The first exact-RC production deployment attempt failed closed and did not
complete the production-deployment release gate.

Failed transaction:

`update-20260824T165151Z-3258027`

Recovered authoritative baseline:

`baseline-reconciliation-20260824T164541Z-927002`

The remediation certifies build-context permission preflight, digest-safe
transaction-scoped rollback aliases, and persistent transaction-owned recovery
source. Exactly 17 permission-drift files were normalized from `0600` to
repository-authoritative `0644`.

Final remediation certification passed 3,446 Core tests plus 104 subtests, all
five canonical Sports integration suites, 52 focused release-safety tests,
18/18 rollback alias identity checks, and production remained at 22 running
containers with zero unhealthy or restarting containers.

This is remediation certification, not successful exact-RC production
deployment. A controlled retry remains required.

---

# 10. Validation Summary

| Validation | Result | Evidence |
| --- | --- | --- |
| Engineering | PASS | Protected Atlas Release Gate passed on the promoted candidate |
| Repository | PASS | Feature source `8b7a5876...` promoted through merge commit `1545133b...`; release tree matched certified feature tree |
| Runtime | PASS — EXACT RC DEPLOYMENT VERIFIED | Exact `1.0.0-rc.1` production transaction `update-20260825T232236Z-1274121` is verified; authoritative baseline `baseline-20260825T232627Z-1296276` is verified; runtime is 22 running / 0 unhealthy / 0 restarting; strict ingress passes; lock absent; maintenance disabled |
| Operations | READY FOR RC VALIDATION | Canonical operations, upgrade, rollback, backup/restore, and troubleshooting contracts are documented |
| User Acceptance | PENDING RC PILOT | Controlled user pilot remains a Roadmap release gate |
| Administrator Acceptance | ENGINEERING JOURNEY PASS | Administrator critical-browser journey certified before RC identity creation; production RC validation remains pending |
| Security | PASS FOR CANDIDATE CREATION | Production fail-closed audit contract preserved; no security weakening introduced by release-gate remediation |
| Backup and Recovery | DOCUMENTED / REVALIDATE ON RC | Canonical backup, restore, rollback, and recovery procedures are present; exact RC operational validation remains required |
| Documentation | PASS FOR RC CREATION | v1 documentation body, architecture, known limitations, and canonical navigation completed before RC identity creation |

---

# 11. Compatibility

The candidate preserves the supported Atlas v1 architecture and public-contract
boundaries established during release-readiness certification.

The canonical Atlas release version source is `VERSION`.

Component package metadata such as the API and Portal `0.1.0` package versions
is not redefined by the Atlas product release identity.

Any production incompatibility discovered during RC deployment, pilot, or
stabilization is release-blocking unless explicitly bounded and accepted under
the release policy.

---

# 12. Release Metrics

| Metric | Value |
| --- | --- |
| Certified Feature Source | `8b7a5876e8fb1b2054eab7a67685bc7d0b2e9ea5` |
| Release Promotion Commit | `1545133b1576fea0e8a390aa00fcf0efdd3e7e3d` |
| Core Validation | 3440 passed + 104 subtests |
| API Validation | 400 passed + 15 subtests |
| Portal Validation | 247 passed across 34 test files |
| Sports Validation | PASS |
| Release Contracts | PASS |
| Aggregate Release Gate | PASS |
| Sustained-use Certification | 193 / 193 samples across certified 48-hour window |
| Exact RC Production Deployment | Pending controlled retry; first attempt failed closed and remediation is certified |
| RC Deployment-Safety Remediation | PASS |
| Remediation Core Validation | 3446 passed + 104 subtests |
| Remediation Sports Integration | 5 suites passed |
| Focused Release-Safety Validation | 52 passed |
| Controlled User Pilot | Pending |
| Stabilization | Pending |

---

# 13. Rollback Guidance

Rollback must follow the canonical
[`../guides/ROLLBACK_GUIDE.md`](../guides/ROLLBACK_GUIDE.md) and
[`../guides/BACKUP_RESTORE_GUIDE.md`](../guides/BACKUP_RESTORE_GUIDE.md)
procedures.

The RC tag, once created, is an immutable release identity and must not be
moved to represent a later corrective candidate.

If a release-blocking RC defect requires a new candidate, correct the defect,
repeat the applicable certification gates, and create a later release candidate
such as `1.0.0-rc.2` rather than rewriting `v1.0.0-rc.1`.

---

# 14. Approval

## Approval Decision

- [x] Approved for RC identity creation
- [ ] Rejected
- [ ] Deferred pending corrective work

This approval is limited to creation of the Project Atlas `1.0.0-rc.1`
candidate identity after the release-only commit and protected promotion
requirements are satisfied.

It is not approval for final Project Atlas v1.0.0 publication.

## Approval Record

| Field | Value |
| --- | --- |
| Approver | Project Atlas project owner |
| Recorded Approval | Approved for release-candidate identity creation |
| Date | 2026-08-24 |
| Notes | Production RC deployment, pilot, stabilization, freeze, final release notes, final tagging, publication, and stable support remain pending |

---

# 15. References

- [`README.md`](README.md)
- [`V1_RELEASE_PLAN.md`](V1_RELEASE_PLAN.md)
- [`RELEASE_CHECKLIST.md`](RELEASE_CHECKLIST.md)
- [`USER_ACCEPTANCE.md`](USER_ACCEPTANCE.md)
- [`SUSTAINED_USE.md`](SUSTAINED_USE.md)
- [`KNOWN_LIMITATIONS.md`](KNOWN_LIMITATIONS.md)
- [`../../ROADMAP.md`](../../ROADMAP.md)
- [`../../CHANGELOG.md`](../../CHANGELOG.md)
- [`../BUILD_LOG.md`](../BUILD_LOG.md)
- [`../operations/RELEASE_PROMOTION.md`](../operations/RELEASE_PROMOTION.md)
- [`../architecture/DEPLOYMENT_SAFETY.md`](../architecture/DEPLOYMENT_SAFETY.md)

---

# RC Identity Boundary

This record certifies the engineering and repository boundary required to create
Project Atlas `1.0.0-rc.1`.

It does not claim completion of:

- exact-candidate production deployment;
- controlled user pilot;
- stabilization;
- pilot-defect closure;
- release freeze;
- final v1.0 release notes;
- final `v1.0.0` tagging;
- final publication; or
- stable support.

The `Create v1.0 release candidate` Roadmap gate is closed. The candidate was
promoted through the protected release path and immutable annotated
`v1.0.0-rc.1` identity was created and verified.

The separate `Deploy release candidate to production` gate remains open. The
first exact-RC attempt failed closed, production recovery completed, and the
resulting deployment-safety remediation has been certified. A controlled retry
is still required.

The final `v1.0.0` release remains a separate later certification transaction.
