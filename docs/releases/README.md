# Atlas Release Documentation

## Purpose

This directory contains the canonical release engineering and release
certification documentation for Project Atlas.

Where the Governance Library defines how Atlas is engineered, the Release
Library defines how Atlas is planned, prepared, validated, certified, and
delivered.

Release documents are permanent repository records. They preserve release
scope, validation evidence, compatibility expectations, known limitations, and
approval status for Atlas subsystems and product releases.

## Release Philosophy

Atlas releases follow the engineering principles established by the Governance
Library.

Release decisions prioritize:

- stability over novelty;
- reliability over convenience;
- simplicity over unnecessary complexity;
- documentation before release;
- validation before publication;
- the repository as the source of truth;
- user experience as a release requirement.

A release is complete only when engineering, operations, documentation,
certification, and user experience have satisfied the applicable release
requirements.

## Release Documentation

### [`V1_RELEASE_PLAN.md`](V1_RELEASE_PLAN.md)

Defines the contractual scope and execution plan for Atlas v1.0.

### [`RELEASE_CHECKLIST.md`](RELEASE_CHECKLIST.md)

Defines the permanent engineering release gate used for every Atlas release.

The checklist covers:

- engineering readiness;
- repository readiness;
- runtime validation;
- operational readiness;
- documentation readiness;
- security review;
- backup and recovery validation;
- user experience certification;
- administrator experience certification;
- release packaging;
- publication readiness;
- post-release validation;
- release approval.

### [`USER_ACCEPTANCE.md`](USER_ACCEPTANCE.md)

Defines the permanent User Acceptance Certification process for Atlas releases.

The document validates:

- invitation and onboarding;
- account creation;
- sign-in, navigation, and sign-out;
- media discovery and search;
- request submission and status;
- favorites and protected-media behavior;
- Jellyfin playback handoff;
- administrator invitations, users, requests, and media operations;
- health and module visibility;
- routine administration without CLI access;
- accessibility and responsiveness;
- performance, failure, and recovery behavior;
- defect classification and release approval.

### [`RELEASE_TEMPLATE.md`](RELEASE_TEMPLATE.md)

Provides the reusable planning and certification structure for future Atlas
releases.

The template records:

- release identity and scope;
- features, improvements, and bug fixes;
- breaking changes and known limitations;
- upgrade and compatibility requirements;
- validation evidence and release metrics;
- rollback guidance;
- approval and supporting references.

### `RELEASE_NOTES_TEMPLATE.md`

Provides the standard structure for release notes and announcements.

## Release Certification Records

Release certification is the permanent engineering sign-off for an Atlas
subsystem or product release.

A certification records applicable scope, architecture, public interfaces,
testing, runtime validation, documentation coverage, compatibility guarantees,
migration requirements, repository health, known limitations, rollback or
recovery expectations, integration guidance, certification result, and
approval.

Certification summarizes completed evidence. It does not replace tests, runtime
validation, documentation, audits, or repository review.

## Release Workflow

1. Define and approve release scope.
2. Implement the approved requirements.
3. Complete focused and regression validation.
4. Validate supported runtime behavior.
5. Complete operational and recovery validation.
6. Complete user and administrator acceptance.
7. Finalize documentation and release notes.
8. Complete release certification.
9. Review the release commit and version.
10. Publish and perform post-release validation.

## Relationship to Other Records

- [`../../ROADMAP.md`](../../ROADMAP.md) defines planned, active, deferred, and
  completed milestones.
- [`../../CHANGELOG.md`](../../CHANGELOG.md) records notable changes.
- [`../BUILD_LOG.md`](../BUILD_LOG.md) records implementation and validation
  history.
- [`../governance/README.md`](../governance/README.md) defines how Atlas is
  engineered.
- [`../specifications/README.md`](../specifications/README.md) records approved
  sprint intent and scope.

## Certification Boundary

Certification is evidence-based.

A certification must not claim validation that was not actually performed.
Known limitations must be explicit, and release-blocking failures must not be
reclassified solely to permit publication.

## Current Release Records

Existing or planned release records may include:

```text
TEMPLATE.md
RC_M018_SERVICE_LIFECYCLE.md
RC_V1_0.md
```

## Relationship to Governance

The Release Library builds upon the Governance Library.

Governance defines how Atlas is engineered. Release documentation defines how
Atlas is delivered.
