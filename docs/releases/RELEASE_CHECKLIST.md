# Atlas Release Checklist

**Document Status:** Approved
**Applies To:** All Atlas Releases
**Document Owner:** Project Atlas Engineering
**Last Updated:** 2026-08-02

---

# 1. Purpose

## 1.1 Objective

This document defines the mandatory engineering, operational, documentation,
and user experience validation required before any Atlas release may be
published.

The checklist transforms the Atlas Release Plan into a repeatable release
process that ensures every supported release is stable, documented,
reproducible, and ready for production use.

---

## 1.2 Scope

This checklist applies to:

- major releases;
- minor releases;
- patch releases;
- hotfix releases where applicable.

Additional release-specific validation may be added when required, but the
items defined in this document establish the minimum release gate.

---

## 1.3 Relationship to Other Documents

This checklist should be executed together with:

- Release Plan
- User Acceptance Guide
- Release Policy
- Engineering Charter
- Build Log
- Changelog
- Release Notes

---

# 2. Checklist Usage

Every checklist item must have one of the following outcomes:

- Pass
- Fail
- Not Applicable

Items marked as failed must either:

- be corrected before release; or
- be formally accepted through the Release Policy.

Critical items may never be waived.

---

# 3. Engineering Readiness

## Architecture

- [ ] Public contracts reviewed
- [ ] Architecture remains consistent
- [ ] No unintended breaking changes
- [ ] Compatibility reviewed
- [ ] ADRs updated if required

## Code Quality

- [ ] Coding standards satisfied
- [ ] Static analysis complete
- [ ] Required reviews complete
- [ ] No unresolved critical defects
- [ ] Technical debt reviewed

## Testing

- [ ] Unit tests pass
- [ ] Integration tests pass
- [ ] Regression tests pass
- [ ] CLI validation passes
- [ ] API validation passes
- [ ] Portal validation passes

---

# 4. Repository Readiness

## Repository

- [ ] Working tree clean
- [ ] Branch synchronized
- [ ] Release commit reviewed
- [ ] Version updated
- [ ] Tags prepared

## Documentation

- [ ] Build Log updated
- [ ] Changelog updated
- [ ] Roadmap reviewed
- [ ] Release documentation updated
- [ ] Links validated

## Validation

- [ ] git diff --check passes
- [ ] Repository validation passes
- [ ] No temporary files remain
- [ ] No generated artifacts committed
- [ ] Secrets review complete

---

# 5. Runtime Validation

## Services

- [ ] All required containers healthy
- [ ] Service dependencies satisfied
- [ ] Startup validation completed
- [ ] Shutdown validation completed

## Storage

- [ ] Storage mounted
- [ ] Storage writable
- [ ] Capacity reviewed
- [ ] Permissions verified

## Networking

- [ ] Internal networking validated
- [ ] VPN routing validated
- [ ] DNS validated
- [ ] Reverse proxy validated

## Platform

- [ ] Hardware acceleration validated
- [ ] Scheduled jobs reviewed
- [ ] Logs reviewed
- [ ] No unresolved runtime errors

---

# 6. Operational Readiness

## Startup and Recovery

- [ ] Full-stack startup order validated
- [ ] Service dependency behavior validated
- [ ] Restart recovery validated
- [ ] Interrupted-operation recovery validated
- [ ] Scheduler recovery validated
- [ ] Stale-state recovery validated

## Failure Handling

- [ ] Unavailable-provider behavior validated
- [ ] Storage-full behavior validated
- [ ] VPN failure behavior validated
- [ ] Network interruption behavior validated
- [ ] User-safe outage messaging validated
- [ ] Administrative failures provide actionable guidance

## Maintenance

- [ ] Maintenance-window procedure documented
- [ ] Pre-update backup procedure documented
- [ ] Post-update verification procedure documented
- [ ] Rollback procedure documented
- [ ] Configuration migration procedure documented
- [ ] Schema migration procedure documented where applicable
- [ ] Production maintenance mode reviewed where applicable

## Observability

- [ ] System health visible
- [ ] Service health visible
- [ ] Storage health visible
- [ ] Recent significant failures visible
- [ ] Logs reviewed for unresolved warnings
- [ ] Health output is understandable and actionable

---

# 7. Documentation Readiness

## Core Documentation

- [ ] README documentation current
- [ ] Engineering Guide current
- [ ] Architecture documentation current
- [ ] API documentation current
- [ ] CLI documentation current
- [ ] Portal documentation current
- [ ] Operational documentation current

## Release Records

- [ ] Release Plan reviewed
- [ ] Release Checklist completed
- [ ] User Acceptance completed
- [ ] Release notes completed
- [ ] Release certification completed
- [ ] Known limitations documented
- [ ] Deferred work documented

## Installation and Maintenance

- [ ] Installation instructions validated
- [ ] Configuration instructions validated
- [ ] Upgrade instructions validated
- [ ] Migration instructions validated
- [ ] Backup instructions validated
- [ ] Restore instructions validated
- [ ] Troubleshooting guidance reviewed

## Documentation Quality

- [ ] Local Markdown links validate
- [ ] Commands and examples validate
- [ ] Version references are current
- [ ] Deprecated guidance removed or clearly marked
- [ ] User-facing terminology is consistent
- [ ] Administrator terminology is consistent

---

# 8. Security Review

## Authentication

- [ ] User authentication validated
- [ ] Administrator authentication validated
- [ ] Session behavior validated
- [ ] Sign-out invalidates the session
- [ ] Protected routes reject unauthorized access

## Authorization

- [ ] Role boundaries validated
- [ ] Administrator-only operations protected
- [ ] Mutation paths require intended authorization
- [ ] Disabled or suspended users are handled correctly
- [ ] Invitation permissions validated

## Sensitive Data

- [ ] No secrets committed to the repository
- [ ] No private keys committed
- [ ] No access tokens exposed
- [ ] Sensitive configuration excluded from logs
- [ ] Sensitive API output reviewed
- [ ] Temporary artifacts contain no sensitive information

## Dependencies and Platform

- [ ] Dependency risk reviewed
- [ ] Container image sources reviewed
- [ ] Reverse-proxy security reviewed
- [ ] TLS behavior reviewed
- [ ] File and directory permissions reviewed
- [ ] Least-privilege boundaries reviewed where practical

## Security Findings

- [ ] No unresolved critical security findings
- [ ] Accepted security limitations documented
- [ ] Required remediation completed
- [ ] Security approval recorded

---

# 9. Backup and Recovery Validation

## Backup Coverage

- [ ] Atlas configuration backup validated
- [ ] Identity-state backup validated
- [ ] Invitation-state backup validated
- [ ] Favorites-state backup validated
- [ ] Request-state backup validated
- [ ] Scheduler-state backup validated
- [ ] Module-state backup validated
- [ ] Sports-state backup validated where applicable
- [ ] Retention and cleanup state reviewed

## Backup Integrity

- [ ] Backup completes successfully
- [ ] Backup manifest is present
- [ ] Backup version metadata is correct
- [ ] Backup branch and commit metadata are correct
- [ ] Backup retention behavior validated
- [ ] Backup storage capacity reviewed

## Recovery

- [ ] Restore procedure documented
- [ ] Restore test completed
- [ ] Restored configuration validated
- [ ] Restored state validated
- [ ] Service startup after restore validated
- [ ] Post-restore health validation completed
- [ ] Recovery time expectations documented
- [ ] Single-host backup limitations documented

## Rollback

- [ ] Release rollback path documented
- [ ] Previous version availability confirmed
- [ ] Configuration rollback reviewed
- [ ] Data migration reversibility reviewed
- [ ] Irreversible changes explicitly documented
- [ ] Rollback validation completed where practical

---

# 10. User Experience Certification

## Certification Status

- [ ] User Experience Certification document completed
- [ ] All critical end-user journeys executed
- [ ] Results recorded
- [ ] Defects and usability findings recorded
- [ ] Critical failures resolved
- [ ] Important findings resolved or accepted
- [ ] Approval recorded

## Invitation and Onboarding

- [ ] Invitation is understandable
- [ ] Invitation opens the correct destination
- [ ] Expired invitation behavior is clear
- [ ] Invalid invitation behavior is clear
- [ ] Account creation requirements are clear
- [ ] Validation messages are actionable
- [ ] Registration completion feedback is clear

## Authentication and Navigation

- [ ] Sign-in is reliable
- [ ] Credential errors are understandable
- [ ] Session behavior is predictable
- [ ] Dashboard loads successfully
- [ ] Primary actions are discoverable
- [ ] Navigation is consistent
- [ ] Sign-out is discoverable and reliable

## Media Experience

- [ ] Media browsing is understandable
- [ ] Media search is reliable
- [ ] Empty results provide useful guidance
- [ ] Media detail supports request decisions
- [ ] Request submission is discoverable
- [ ] Request confirmation is clear
- [ ] Request status is visible
- [ ] Duplicate request behavior is clear

## Favorites and Protection

- [ ] Favorites can be added
- [ ] Favorites can be listed
- [ ] Favorites can be removed
- [ ] Favorite state remains consistent
- [ ] Protected-media behavior is understandable
- [ ] Removing a favorite updates protection consistently

## Playback

- [ ] Available media opens correctly
- [ ] Jellyfin handoff is understandable
- [ ] Unavailable media does not show misleading actions
- [ ] Returning to Atlas remains clear

## Error and Performance Experience

- [ ] Critical workflows contain no dead ends
- [ ] Failures are visible
- [ ] Failure messages are actionable
- [ ] Loading states are visible
- [ ] Representative workflows perform acceptably
- [ ] Mobile or supported responsive behavior reviewed

---

# 11. Administrator Experience Certification

## Certification Status

- [ ] Administrator acceptance testing completed
- [ ] All critical administrator journeys executed
- [ ] Results recorded
- [ ] Critical failures resolved
- [ ] Important findings resolved or accepted
- [ ] Approval recorded

## Administrator Access

- [ ] Administrator sign-in validated
- [ ] Administrative routes protected
- [ ] Role enforcement validated
- [ ] Administrative navigation is consistent

## Invitation Management

- [ ] Invitation creation works
- [ ] Invitation detail is visible
- [ ] Invitation expiration is understandable
- [ ] Invitation revocation works
- [ ] Invitation failures provide guidance

## User Management

- [ ] User listing works
- [ ] User detail works
- [ ] Activation and suspension work
- [ ] Role assignment works
- [ ] Administrative impact is clearly communicated
- [ ] Invalid operations are blocked safely

## Request Management

- [ ] Request queue is visible
- [ ] Request detail is visible
- [ ] Approval workflow works where applicable
- [ ] Rejection workflow works where applicable
- [ ] Request state updates clearly
- [ ] Failures provide actionable guidance

## Media and Module Operations

- [ ] Supported media operations work
- [ ] Supported sports operations work
- [ ] Module status is visible
- [ ] Unsupported mutations are not exposed
- [ ] Operational boundaries are clear

## Health and Operations

- [ ] System health is visible
- [ ] Service health is visible
- [ ] Storage state is visible
- [ ] Recent failures are visible
- [ ] Health information suggests a reasonable next action
- [ ] Routine administration does not require CLI use

---

# 12. Release Packaging

## Versioning

- [ ] Release type confirmed
- [ ] Semantic version impact confirmed
- [ ] `VERSION` updated
- [ ] Package metadata updated where applicable
- [ ] CLI version output validated
- [ ] Documentation version references updated
- [ ] Version sources agree

## Release Artifacts

- [ ] Release commit prepared
- [ ] Release notes prepared
- [ ] Known limitations prepared
- [ ] Upgrade guidance prepared
- [ ] Migration guidance prepared where applicable
- [ ] Rollback guidance prepared
- [ ] Checksums or signatures prepared where applicable
- [ ] Source archive reviewed where applicable

## Git Tag

- [ ] Tag name matches the release version
- [ ] Tag points to the certified release commit
- [ ] Annotated or signed tag prepared where supported
- [ ] Pre-release suffix is correct where applicable
- [ ] Tag message reviewed

## Container and Deployment Artifacts

- [ ] Required container images identified
- [ ] Image versions or digests reviewed
- [ ] Compose configuration reviewed
- [ ] Environment-variable requirements documented
- [ ] Deployment examples validated
- [ ] No development-only settings remain
- [ ] Production defaults reviewed

---

# 13. Publication Readiness

## Release Page

- [ ] Release title is correct
- [ ] Release version is correct
- [ ] Release notes are complete
- [ ] Installation or update instructions are included
- [ ] Migration requirements are included
- [ ] Known limitations are included
- [ ] Recovery guidance is referenced
- [ ] Support expectations are clear

## Documentation Publication

- [ ] Release documentation is committed
- [ ] Public documentation links resolve
- [ ] User-facing documentation is discoverable
- [ ] Administrator documentation is discoverable
- [ ] API and CLI references are discoverable
- [ ] Deprecated documentation is clearly identified

## Communication

- [ ] Release summary prepared
- [ ] Intended audience identified
- [ ] Breaking changes called out prominently
- [ ] Required administrator actions called out
- [ ] Security-related changes called out
- [ ] Support boundaries communicated

## Final Publication Gate

- [ ] Release certification approved
- [ ] User Experience Certification approved
- [ ] Administrator Experience Certification approved
- [ ] Release commit pushed
- [ ] Release tag created
- [ ] Publication artifacts match the certified commit
- [ ] No unresolved release blocker remains

---

# 14. Post-Release Validation

## Repository Validation

- [ ] Release tag resolves to the intended commit
- [ ] Version output matches the release
- [ ] Release notes match the released scope
- [ ] Repository working tree is clean
- [ ] Stable branch contains the release commit where applicable

## Installation and Upgrade Validation

- [ ] Clean installation path validated where applicable
- [ ] Supported upgrade path validated
- [ ] Configuration migration validated
- [ ] Schema migration validated where applicable
- [ ] Required services start successfully
- [ ] Post-upgrade health validation passes

## Runtime Smoke Tests

- [ ] Authentication works
- [ ] End-user Portal loads
- [ ] Administrator Portal loads
- [ ] Media discovery works
- [ ] Request workflow works
- [ ] Favorites workflow works
- [ ] Playback handoff works
- [ ] Health visibility works
- [ ] Core notifications work
- [ ] Scheduled jobs operate as expected

## Operational Review

- [ ] Logs reviewed after release
- [ ] Container health reviewed
- [ ] Storage state reviewed
- [ ] Network and VPN state reviewed
- [ ] Backup process reviewed after release
- [ ] No unexpected migration or startup issue remains

## Defect Triage

- [ ] Post-release defects recorded
- [ ] Severity assigned
- [ ] Security defects escalated
- [ ] Patch or emergency release need evaluated
- [ ] Deferred defects assigned to an appropriate milestone

---

# 15. Release Approval

## Release Identity

- **Release Version:** ______________________________
- **Release Type:** _________________________________
- **Branch:** ______________________________________
- **Commit:** ______________________________________
- **Tag:** _________________________________________
- **Certification Date:** __________________________

## Validation Summary

- **Automated Test Result:** ________________________
- **Runtime Validation Result:** ____________________
- **User Experience Result:** _______________________
- **Administrator Experience Result:** ______________
- **Security Review Result:** _______________________
- **Backup and Recovery Result:** ___________________
- **Documentation Review Result:** __________________

## Known Limitations

Record accepted limitations or enter `None`.

~~~text
______________________________________________________________________
______________________________________________________________________
______________________________________________________________________
~~~

## Deferred Work

Record intentionally deferred work or enter `None`.

~~~text
______________________________________________________________________
______________________________________________________________________
______________________________________________________________________
~~~

## Approval Decision

- [ ] Approved for release
- [ ] Rejected
- [ ] Approval deferred pending corrective work

## Approval Record

- **Project Owner or Authorized Maintainer:** ________________________
- **Signature or Recorded Approval:** _______________________________
- **Date:** ________________________________________________________
- **Notes:** _______________________________________________________

---

# 16. References

This checklist is governed and supported by:

- [`README.md`](README.md);
- [`V1_RELEASE_PLAN.md`](V1_RELEASE_PLAN.md);
- [`../governance/ENGINEERING_CHARTER.md`](../governance/ENGINEERING_CHARTER.md);
- [`../governance/DEVELOPMENT_WORKFLOW.md`](../governance/DEVELOPMENT_WORKFLOW.md);
- [`../governance/CODING_STANDARDS.md`](../governance/CODING_STANDARDS.md);
- [`../governance/TESTING_STANDARD.md`](../governance/TESTING_STANDARD.md);
- [`../governance/DOCUMENTATION_STANDARD.md`](../governance/DOCUMENTATION_STANDARD.md);
- [`../governance/ADR_POLICY.md`](../governance/ADR_POLICY.md);
- [`../governance/VERSIONING_AND_CONTRIBUTING.md`](../governance/VERSIONING_AND_CONTRIBUTING.md);
- [`../governance/RELEASE_POLICY.md`](../governance/RELEASE_POLICY.md);
- [`../../ROADMAP.md`](../../ROADMAP.md);
- [`../../CHANGELOG.md`](../../CHANGELOG.md);
- [`../BUILD_LOG.md`](../BUILD_LOG.md).

The dedicated User Acceptance document and release templates will be linked
after those artifacts are completed.

---

# Checklist Completion

This checklist is complete only when:

- every applicable item has an outcome;
- failed items are resolved or handled under the Release Policy;
- critical items pass;
- user and administrator acceptance pass;
- release certification is approved;
- publication and post-release validation are complete;
- the repository accurately represents the released software.

Completion of this checklist must be evidence-based.

Unchecked assumptions, planned validation, or unrecorded results do not satisfy
the Atlas release gate.
