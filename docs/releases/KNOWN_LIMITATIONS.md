# Project Atlas v1.0 Known Limitations

**Document Status:** D.5A v1.0 Release Candidate Documentation
**Applies To:** Project Atlas v1.0
**Document Owner:** Project Atlas Engineering
**Canonical Repository Path:** `docs/releases/KNOWN_LIMITATIONS.md`

---

## 1. Purpose

This document records known, bounded limitations accepted for the Project Atlas
v1.0 release boundary.

A known limitation is not permission to hide a defect or weaken a supported
contract. Atlas release policy permits a limitation only when it remains bounded,
does not violate the supported release contract, does not threaten data integrity
or security, and is explicitly documented and approved.

Release-blocking defects remain release blockers and must not be reclassified as
known limitations merely to ship.

---

## 2. Single-Host Deployment Boundary

Project Atlas v1.0 has been validated on a single-host Linux deployment topology.

The v1.0 release does not claim:

- Kubernetes deployment support;
- clustered high availability;
- multi-host Atlas orchestration;
- automatic host failover; or
- complete multi-host disaster recovery.

This is a supported deployment boundary rather than evidence that the single-host
deployment is unhealthy.

Cluster infrastructure, high availability, resilient storage, and broader
multi-host capabilities remain later-platform work.

---

## 3. Atlas Backup Scope Is Intentionally Bounded

The canonical Atlas recovery archive protects declared Atlas-owned state. It is
not a complete backup of the host, Media stack, or all third-party application
state.

The Atlas recovery archive does not claim complete recovery of:

- Media libraries;
- Jellyfin databases;
- Sonarr databases;
- Radarr databases;
- qBittorrent state;
- Docker Engine;
- the Proxmox host; or
- other third-party state outside the declared Atlas backup contract.

If a production change modifies persistent state outside the Atlas recovery
archive scope, additional backup or recovery protection is required for that
state.

Do not describe the Atlas archive as complete infrastructure disaster recovery.

---

## 4. Same-Host Backup Is Not Independent Disaster Recovery

The normal Atlas backup location is within the same host/storage failure domain
as the current single-host deployment.

Therefore, local Atlas backup retention does not by itself provide independent
host-loss disaster recovery.

When recovery must survive host or storage-domain loss, operators must maintain
an independently protected copy outside that failure domain.

Retention and restore verification remain valuable, but they are not substitutes
for off-host protection.

---

## 5. Restore Timing Is Not an SLO

Controlled v1.0 restore evidence on the tested single-host topology reached writer
restart in roughly 69 seconds.

That observed result is evidence from a specific tested topology. It is **not** a
Service Level Objective (SLO), Service Level Agreement (SLA), or guaranteed
maximum restore duration.

For the current small single-host topology, operators should reserve at least
**5–10 minutes** for a restore-oriented maintenance window and increase that
allowance as state size, storage behavior, provider recovery, and verification
cost increase.

Recovery acceptance remains health-based, not stopwatch-based.

---

## 6. Service Lifecycle Portal Mutation Boundary

Project Atlas v1.0 provides service lifecycle visibility, update-availability
state, health/diagnostic context, and Maintenance History through the supported
administrative surfaces.

The v1.0 Service Lifecycle presentation does not introduce generic Portal
controls for:

- Start;
- Stop;
- Restart;
- Update; or
- Rollback

for arbitrary managed services through the read-only lifecycle/status surface.

Where Atlas supports a production-changing operation, operators must use the
specific canonical transaction and authorization boundary documented for that
operation.

An absent generic lifecycle mutation button is therefore not evidence that the
corresponding lower-level infrastructure capability does not exist.

---

## 7. Accepted Upstream Caddy Security Limitation

Project Atlas v1.0 security acceptance records an approved set of **19 remaining
upstream Caddy HIGH findings** for the v1.0 boundary.

These findings were accepted through the existing Atlas security-review and
release-acceptance process. This document does not redefine, expand, or replace
that security rationale.

Operators and release reviewers must use the certified security evidence as the
authoritative source for:

- exact finding identity;
- applicability;
- upstream ownership;
- compensating controls;
- accepted residual risk; and
- remediation or upgrade expectations.

Any newly discovered critical security issue, any change that invalidates the
approved rationale, or any finding that becomes release-blocking must be handled
under the release/security process rather than silently added to this limitation.

---

## 8. Deferred Scope Is Not Automatically a Known Limitation

The following examples are intentionally outside the Project Atlas v1.0 product
scope and should not be represented as v1.0 defects merely because they are not
implemented:

- Progressive Web App implementation;
- native/mobile companion applications;
- custom roles;
- permission simulation;
- role inheritance;
- advanced quota controls;
- dynamic Portal module navigation;
- full module plugin UI;
- broader Portal/module extensibility;
- Game Server Platform capabilities;
- multi-host Atlas;
- clustered high availability; and
- later disaster-recovery platform work.

The responsive authenticated Portal remains the supported v1.0 mobile
administration experience.

Deferred capabilities remain governed by the Roadmap and future release plans.

---

## 9. Provider Dependencies Are Supported Operating Boundaries

Project Atlas integrates with external and companion services such as Jellyfin,
Seerr, Sonarr, Radarr, qBittorrent, and other configured providers.

Provider unavailability can make provider-backed Atlas features unavailable.

This is not permission to misrepresent unavailable data as authoritative empty
state. Atlas v1.0 is expected to fail closed where provider state cannot be
established reliably.

Provider outage behavior is therefore a supported failure boundary, not a known
limitation that weakens Atlas data-integrity or request-safety contracts.

---

## 10. Storage Exhaustion Is Not an Accepted Limitation

Finite storage capacity is an infrastructure constraint, but unsafe behavior
under storage exhaustion is not an accepted v1.0 limitation.

Atlas is expected to preserve fail-closed storage behavior, retain evidence where
possible, avoid unsafe implicit deletion, and require controlled recovery when
usable capacity is exhausted.

Any storage-exhaustion defect that threatens state integrity, creates unsafe
cleanup behavior, or violates the certified recovery contract remains a defect.

---

## 11. Release Blockers Are Not Known Limitations

The following classes of issue must not be normalized into this document merely
to permit release:

- unresolved release-blocking defects;
- unresolved critical defects;
- data-integrity failures;
- security failures that invalidate the approved security boundary;
- failures of required production validation;
- broken supported user or administrator contracts;
- unresolved ambiguous mutation behavior that can duplicate or corrupt state; or
- hidden/unbounded behavior without a safe documented impact boundary.

Atlas v1.0 may proceed only when the applicable release-readiness gates are
satisfied.

---

## 12. Release-State Boundary

Publication of this Known Limitations document does **not** mean Project Atlas
v1.0 has been released.

The following remain separate release gates until completed and certified:

- create the v1.0 release candidate;
- deploy the release candidate to production;
- complete the controlled user pilot;
- complete the stabilization period;
- resolve pilot defects;
- freeze the release candidate;
- tag `v1.0.0`;
- publish `v1.0.0`; and
- begin stable support.

Release notes also remain a separate artifact and should be finalized against the
frozen release candidate rather than inferred early.

---

## 13. Operator Guidance

Before accepting a limitation during release review:

1. confirm the behavior is inside the supported v1.0 product boundary;
2. confirm the impact is bounded;
3. confirm the supported contract is not violated;
4. confirm there is a safe operating or recovery path where one is required;
5. confirm the limitation does not threaten data integrity or security;
6. confirm it is documented accurately;
7. confirm release approval explicitly accepts it.

If any of these conditions cannot be established, treat the item as a defect,
release blocker, or unresolved release question instead.

---

## 14. Authoritative References

Primary references:

- `../../ROADMAP.md`
- `../guides/ADMINISTRATOR_GUIDE.md`
- `../guides/INSTALLATION_GUIDE.md`
- `../guides/BACKUP_RESTORE_GUIDE.md`
- `../guides/TROUBLESHOOTING_GUIDE.md`
- `../architecture/BACKUP_RECOVERY.md`
- `../architecture/SERVICE_LIFECYCLE.md`
- `../architecture/STORAGE_EXHAUSTION.md`
- `../architecture/UNAVAILABLE_PROVIDER_BEHAVIOR.md`
- `RELEASE_CHECKLIST.md`
- `V1_RELEASE_PLAN.md`
- `USER_ACCEPTANCE.md`
- `SUSTAINED_USE.md`
- `../governance/RELEASE_POLICY.md`
- `../governance/DOCUMENTATION_STANDARD.md`

The Roadmap owns deferred scope. Canonical guides own supported procedures.
Architecture documents own subsystem contracts. Release governance owns the
criteria for accepting or rejecting a limitation.

When these roles differ, do not collapse them into a single claim.
